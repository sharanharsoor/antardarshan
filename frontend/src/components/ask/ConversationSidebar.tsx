"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { MessageSquare, Trash2, Share2, Edit2, Check, X, Plus, Search } from "lucide-react";
import {
  listConversations,
  deleteConversation,
  shareConversation,
  renameConversation,
  groupConversationsByDate,
  type Conversation,
} from "@/lib/conversations";

interface ConversationSidebarProps {
  currentConversationId?: string;
  onNewChat: () => void;
}

function ConversationItem({
  conv,
  currentId,
  onDelete,
  onShare,
  onRename,
}: {
  conv: Conversation;
  currentId?: string;
  onDelete: (id: string) => void;
  onShare: (id: string) => Promise<boolean>;
  onRename: (id: string, title: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(conv.title || "");
  const [copied, setCopied] = useState(false);

  return (
    <div
      className={`group relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
        conv.id === currentId
          ? "bg-accent/10 text-foreground"
          : "text-muted hover:bg-background hover:text-foreground"
      }`}
    >
      {editing ? (
        <div className="flex flex-1 items-center gap-1 min-w-0">
          <input
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="flex-1 bg-transparent border-b border-accent text-sm focus:outline-none min-w-0"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") { onRename(conv.id, editValue); setEditing(false); }
              if (e.key === "Escape") setEditing(false);
            }}
          />
          <button onClick={() => { onRename(conv.id, editValue); setEditing(false); }}>
            <Check className="h-3 w-3 text-success shrink-0" />
          </button>
          <button onClick={() => setEditing(false)}>
            <X className="h-3 w-3 text-muted shrink-0" />
          </button>
        </div>
      ) : (
        <>
          <Link href={`/ask/c/${conv.id}`} className="flex flex-1 items-center gap-2 min-w-0">
            <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted/60" />
            <span className="truncate text-[13px] leading-snug">
              {conv.title || "New conversation"}
            </span>
            {conv.shared && (
              <span className="shrink-0 text-[10px] text-accent/70">shared</span>
            )}
          </Link>

          {/* Actions on hover */}
          <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
            <button
              onClick={() => { setEditing(true); setEditValue(conv.title || ""); }}
              className="rounded p-1 text-muted hover:text-foreground"
              title="Rename"
            >
              <Edit2 className="h-3 w-3" />
            </button>
            <button
              onClick={async () => {
                const ok = await onShare(conv.id);
                if (ok) { setCopied(true); setTimeout(() => setCopied(false), 2000); }
              }}
              className="rounded p-1 text-muted hover:text-foreground"
              title={copied ? "Copied!" : "Share"}
            >
              {copied ? <Check className="h-3 w-3 text-success" /> : <Share2 className="h-3 w-3" />}
            </button>
            <button
              onClick={() => onDelete(conv.id)}
              className="rounded p-1 text-muted hover:text-error"
              title="Delete"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function DateGroup({
  label,
  conversations,
  currentId,
  onDelete,
  onShare,
  onRename,
}: {
  label: string;
  conversations: Conversation[];
  currentId?: string;
  onDelete: (id: string) => void;
  onShare: (id: string) => Promise<boolean>;
  onRename: (id: string, title: string) => void;
}) {
  if (!conversations.length) return null;
  return (
    <div className="mb-2">
      <p className="px-3 py-1.5 text-[11px] font-semibold text-muted/50 uppercase tracking-wider">
        {label}
      </p>
      {conversations.map((conv) => (
        <ConversationItem
          key={conv.id}
          conv={conv}
          currentId={currentId}
          onDelete={onDelete}
          onShare={onShare}
          onRename={onRename}
        />
      ))}
    </div>
  );
}

export function ConversationSidebar({ currentConversationId, onNewChat }: ConversationSidebarProps) {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const reload = useCallback(() => {
    listConversations(100).then(setConversations).finally(() => setLoading(false));
  }, []);

  useEffect(() => { reload(); }, [reload]);

  // Reload list when active conversation changes — catches newly created conversations
  // (window.history.replaceState keeps the sidebar mounted so mount-only reload isn't enough)
  useEffect(() => {
    if (currentConversationId) reload();
  }, [currentConversationId, reload]);

  // Reload when an answer completes — picks up auto-generated title from backend
  useEffect(() => {
    const handler = () => reload();
    window.addEventListener("conversation-updated", handler);
    return () => window.removeEventListener("conversation-updated", handler);
  }, [reload]);

  const handleDelete = async (id: string) => {
    const ok = await deleteConversation(id);
    if (ok) {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (id === currentConversationId) router.push("/ask");
    }
  };

  const handleShare = async (id: string) => {
    const url = await shareConversation(id);
    if (url) {
      await navigator.clipboard.writeText(url);
      reload();
      return true;
    }
    return false;
  };

  const handleRename = async (id: string, title: string) => {
    const ok = await renameConversation(id, title);
    if (ok) setConversations((prev) => prev.map((c) => c.id === id ? { ...c, title } : c));
  };

  // Filter by search
  const filtered = search.trim()
    ? conversations.filter((c) =>
        (c.title || "New conversation").toLowerCase().includes(search.toLowerCase())
      )
    : conversations;

  const grouped = groupConversationsByDate(filtered);

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-border bg-surface">
      {/* New chat */}
      <div className="p-3 border-b border-border">
        <button
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-muted hover:bg-background hover:text-foreground transition-colors"
        >
          <Plus className="h-4 w-4" />
          New conversation
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b border-border">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted/50" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations…"
            className="w-full rounded-lg bg-background pl-8 pr-3 py-2 text-xs placeholder:text-muted/40 focus:outline-none focus:ring-1 focus:ring-accent/30"
          />
        </div>
      </div>

      {/* Conversation list — all grouped by date, no "All" button */}
      <div className="flex-1 overflow-y-auto py-2">
        {loading ? (
          <div className="space-y-2 px-3 py-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-8 animate-pulse rounded bg-background" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-muted/50">
            {search ? "No conversations match." : "No conversations yet."}
          </p>
        ) : (
          <>
            <DateGroup label="Today"      conversations={grouped.today}     currentId={currentConversationId} onDelete={handleDelete} onShare={handleShare} onRename={handleRename} />
            <DateGroup label="Yesterday"  conversations={grouped.yesterday} currentId={currentConversationId} onDelete={handleDelete} onShare={handleShare} onRename={handleRename} />
            <DateGroup label="This week"  conversations={grouped.thisWeek}  currentId={currentConversationId} onDelete={handleDelete} onShare={handleShare} onRename={handleRename} />
            <DateGroup label="Older"      conversations={grouped.older}     currentId={currentConversationId} onDelete={handleDelete} onShare={handleShare} onRename={handleRename} />
          </>
        )}
      </div>
    </aside>
  );
}
