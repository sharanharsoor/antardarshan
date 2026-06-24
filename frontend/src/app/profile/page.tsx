"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  BookOpen, Bookmark, Highlighter, MessageCircle,
  CheckCircle2, ChevronRight, StickyNote, Trash2,
} from "lucide-react";
import { createClient } from "@/utils/supabase/client";
import {
  getAllProgress, getAllBookmarks, getAllHighlights, getQueriesThisMonth,
  removeBookmark, deleteHighlight,
  type ReadingProgress, type Bookmark as BM, type Highlight,
} from "@/lib/supabase-reader";
import { listConversations, deleteConversation, clearQueryLog, type Conversation } from "@/lib/conversations";
import { getLibrary, type Scripture } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ProgressWithMeta extends ReadingProgress {
  scripture_name: string;
  total_chapters: number;
  percent: number;
  completed: boolean;
}

interface Stats {
  questions_this_month: number;
  bookmarks: number;
  highlights: number;
  books_completed: number;
}

type TabId = "reading" | "bookmarks" | "highlights" | "conversations";

const HIGHLIGHT_COLOR_BG: Record<Highlight["color"], string> = {
  yellow: "bg-yellow-200/80 dark:bg-yellow-500/30",
  green:  "bg-green-200/80 dark:bg-green-500/30",
  blue:   "bg-blue-200/80 dark:bg-blue-500/30",
  pink:   "bg-pink-200/80 dark:bg-pink-500/30",
};

const HIGHLIGHT_DOT: Record<Highlight["color"], string> = {
  yellow: "bg-yellow-400",
  green:  "bg-green-400",
  blue:   "bg-blue-400",
  pink:   "bg-pink-400",
};

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ icon, label, sublabel, value, onClear }: {
  icon: React.ReactNode; label: string; sublabel?: string;
  value: number | undefined; onClear?: () => void;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="flex flex-col gap-1 rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <div className="text-accent">{icon}</div>
        {onClear && !confirming && (
          <button
            onClick={() => setConfirming(true)}
            className="text-[10px] text-muted/50 hover:text-red-500 transition-colors"
          >
            Clear
          </button>
        )}
        {onClear && confirming && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-muted">Sure?</span>
            <button
              onClick={() => { setConfirming(false); onClear(); }}
              className="text-[10px] text-red-500 hover:text-red-600 font-medium"
            >
              Yes
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="text-[10px] text-muted hover:text-foreground"
            >
              No
            </button>
          </div>
        )}
      </div>
      <p className="text-2xl font-bold text-foreground">
        {value === undefined ? <span className="h-6 w-12 animate-pulse rounded bg-border block" /> : value}
      </p>
      <p className="text-xs text-muted">{label}</p>
      {sublabel && <p className="text-[10px] text-muted/50 leading-tight">{sublabel}</p>}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const router = useRouter();

  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Lazy initializer reads URL hash once on client mount — no useEffect needed
  const [activeTab, setActiveTab] = useState<TabId>(() => {
    if (typeof window === "undefined") return "reading";
    const hash = window.location.hash.slice(1) as TabId;
    return (["reading", "bookmarks", "highlights", "conversations"] as const).includes(hash)
      ? hash : "reading";
  });
  const [colorFilter, setColorFilter] = useState<Highlight["color"] | "all">("all");

  const [inProgress, setInProgress] = useState<ProgressWithMeta[]>([]);
  const [completed, setCompleted] = useState<ProgressWithMeta[]>([]);
  const [bookmarks, setBookmarks] = useState<BM[]>([]);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  async function loadProfile() {
    try {
    const [rawProgress, library, allBm, allHl, convs, queriesCount] = await Promise.all([
      getAllProgress(),
      getLibrary(),
      getAllBookmarks(),
      getAllHighlights(),
      listConversations(100),
      getQueriesThisMonth(),
    ]);

    // Join progress with library metadata
    const slugToScripture = Object.fromEntries(library.map((s: Scripture) => [s.slug, s]));
    const progressWithMeta: ProgressWithMeta[] = rawProgress
      .filter((p) => slugToScripture[p.slug])
      .map((p) => {
        const s = slugToScripture[p.slug];
        const percent = Math.min(100, Math.round((p.chapter / s.total_chapters) * 100));
        return {
          ...p,
          scripture_name: s.scripture,
          total_chapters: s.total_chapters,
          percent,
          completed: p.chapter >= s.total_chapters,
        };
      });

    setInProgress(progressWithMeta.filter((p) => !p.completed));
    setCompleted(progressWithMeta.filter((p) => p.completed));
    setBookmarks(allBm);
    setHighlights(allHl);
    setConversations(convs);
    setStats({
      questions_this_month: queriesCount,
      bookmarks: allBm.length,
      highlights: allHl.length,
      books_completed: progressWithMeta.filter((p) => p.completed).length,
    });
    } catch {
      // Library/backend unavailable — still show empty profile rather than freezing
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user) { router.replace("/"); return; }
      setUserEmail(user.email ?? null);
      loadProfile();
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDeleteBookmark = async (id: string) => {
    const ok = await removeBookmark(id);
    if (ok) {
      setBookmarks((prev) => prev.filter((b) => b.id !== id));
      setStats((prev) => prev ? { ...prev, bookmarks: prev.bookmarks - 1 } : prev);
    }
  };

  const handleDeleteHighlight = async (id: string) => {
    const ok = await deleteHighlight(id);
    if (ok) {
      setHighlights((prev) => prev.filter((h) => h.id !== id));
      setStats((prev) => prev ? { ...prev, highlights: prev.highlights - 1 } : prev);
    }
  };

  const [confirmDeleteConvId, setConfirmDeleteConvId] = useState<string | null>(null);

  const handleDeleteConversation = async (id: string) => {
    const ok = await deleteConversation(id);
    if (ok) setConversations((prev) => prev.filter((c) => c.id !== id));
    setConfirmDeleteConvId(null);
    // Note: stats.questions_this_month is from user_query_log (query history),
    // which is kept even when conversations are deleted — it's an analytics log.
  };

  // ── Derived data ─────────────────────────────────────────────────────────────

  const filteredHighlights = colorFilter === "all"
    ? highlights
    : highlights.filter((h) => h.color === colorFilter);

  // Group bookmarks by scripture name
  const bookmarksByScripture = bookmarks.reduce<Record<string, BM[]>>((acc, bm) => {
    acc[bm.scripture] = acc[bm.scripture] ?? [];
    acc[bm.scripture].push(bm);
    return acc;
  }, {});

  // Group highlights by slug, sorted within each group by chapter then verse
  const highlightsBySlug = filteredHighlights.reduce<Record<string, Highlight[]>>((acc, h) => {
    acc[h.slug] = acc[h.slug] ?? [];
    acc[h.slug].push(h);
    return acc;
  }, {});
  // Sort within each scripture by chapter, then verse
  Object.values(highlightsBySlug).forEach((hs) =>
    hs.sort((a, b) => a.chapter !== b.chapter ? a.chapter - b.chapter : a.verse - b.verse)
  );

  // ── Loading skeleton ──────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 space-y-6">
        <div className="h-8 w-40 animate-pulse rounded bg-surface border border-border" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-surface border border-border" />
          ))}
        </div>
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-surface border border-border" />
          ))}
        </div>
      </div>
    );
  }

  const allBooks = [...inProgress, ...completed];

  const tabs: { id: TabId; label: string; count: number }[] = [
    { id: "reading",       label: "Reading",       count: allBooks.length },
    { id: "bookmarks",     label: "Bookmarks",     count: bookmarks.length },
    { id: "highlights",    label: "Highlights",    count: highlights.length },
    { id: "conversations", label: "Conversations", count: conversations.length },
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-2xl font-bold text-foreground">My Journey</h1>
        {userEmail && <p className="text-sm text-muted mt-1">{userEmail}</p>}
      </div>

      {/* Stats — order matches tabs: Reading, Bookmarks, Highlights, Conversations */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <StatCard icon={<CheckCircle2 className="h-4 w-4" />}   label="Books completed"    value={stats?.books_completed} />
        <StatCard icon={<Bookmark className="h-4 w-4" />}        label="Bookmarks"           value={stats?.bookmarks} />
        <StatCard icon={<Highlighter className="h-4 w-4" />}     label="Highlights"          value={stats?.highlights} />
        <StatCard
          icon={<MessageCircle className="h-4 w-4" />}
          label="Queries sent"
          value={stats?.questions_this_month}
          sublabel="last 30 days · metadata only, no question content stored"
          onClear={async () => {
            const ok = await clearQueryLog();
            if (ok) setStats((prev) => prev ? { ...prev, questions_this_month: 0 } : prev);
          }}
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border mb-6 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => { setActiveTab(tab.id); window.history.replaceState(null, "", `#${tab.id}`); }}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm whitespace-nowrap transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? "border-accent text-accent font-medium"
                : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className="rounded-full bg-surface border border-border px-1.5 py-0.5 text-[10px] text-muted">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Reading tab ─────────────────────────────────────────────────────── */}
      {activeTab === "reading" && (
        <div className="space-y-3">
          {inProgress.length === 0 && completed.length === 0 && (
            <div className="text-center py-16 text-muted">
              <BookOpen className="h-8 w-8 mx-auto mb-3 opacity-40" />
              <p>No reading progress yet.</p>
              <Link href="/library" className="text-sm text-accent hover:underline mt-2 inline-block">
                Browse the library →
              </Link>
            </div>
          )}

          {/* Single unified list — no "completed" label since we track visits not actual completion.
              Books at 100% show a ✓ icon; everything else shows a progress bar. */}
          {[...inProgress, ...completed].map((p) => (
            <Link
              key={p.slug}
              href={`/read/${p.slug}/${p.chapter}`}
              className="flex items-center gap-4 rounded-xl border border-border bg-surface p-4 hover:border-accent/40 transition-colors group"
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm text-foreground truncate">{p.scripture_name}</p>
                <p className="text-xs text-muted mt-0.5">
                  Chapter {p.chapter} of {p.total_chapters}
                  {p.completed && <span className="ml-2 text-success">· All chapters visited</span>}
                </p>
                <div className="mt-2 h-1.5 w-full rounded-full bg-border overflow-hidden">
                  <div
                    className="h-full rounded-full bg-accent transition-all"
                    style={{ width: `${p.percent}%` }}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {p.completed
                  ? <CheckCircle2 className="h-4 w-4 text-success" />
                  : <span className="text-xs text-muted">{p.percent}%</span>
                }
                <ChevronRight className="h-4 w-4 text-muted group-hover:text-accent transition-colors" />
              </div>
            </Link>
          ))}

          <p className="text-xs text-muted/60 pt-2 text-center">
            Progress is tracked by chapters visited. To reset, simply continue reading from where you left off.
          </p>
        </div>
      )}

      {/* ── Bookmarks tab ───────────────────────────────────────────────────── */}
      {activeTab === "bookmarks" && (
        <div className="space-y-6">
          {bookmarks.length === 0 && (
            <div className="text-center py-16 text-muted">
              <Bookmark className="h-8 w-8 mx-auto mb-3 opacity-40" />
              <p>No bookmarks yet.</p>
              <p className="text-sm mt-1">Bookmark verses while reading to find them here.</p>
            </div>
          )}
          {Object.entries(bookmarksByScripture).map(([scripture, bms]) => (
            <div key={scripture}>
              <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">
                {scripture} <span className="normal-case font-normal">({bms.length})</span>
              </h2>
              <div className="space-y-2">
                {bms.map((bm) => (
                  <div key={bm.id} className="flex items-center rounded-lg border border-border bg-surface group hover:border-accent/40 transition-colors overflow-hidden">
                    <Link
                      href={`/read/${bm.slug}/${bm.chapter}#verse-${bm.verse}`}
                      className="flex-1 px-4 py-3 text-sm text-foreground"
                    >
                      Chapter {bm.chapter}, Verse {bm.verse}
                    </Link>
                    <div className="flex items-center gap-2 px-3 py-3 shrink-0">
                      <button
                        onClick={() => handleDeleteBookmark(bm.id)}
                        className="p-0.5 text-muted/30 hover:text-red-500 transition-colors"
                        title="Remove bookmark"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                      <div className="w-px h-3 bg-border/60" />
                      <Link href={`/read/${bm.slug}/${bm.chapter}#verse-${bm.verse}`}>
                        <ChevronRight className="h-3.5 w-3.5 text-muted group-hover:text-accent transition-colors" />
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Highlights tab ──────────────────────────────────────────────────── */}
      {activeTab === "highlights" && (
        <div className="space-y-4">
          {highlights.length === 0 && (
            <div className="text-center py-16 text-muted">
              <Highlighter className="h-8 w-8 mx-auto mb-3 opacity-40" />
              <p>No highlights yet.</p>
              <p className="text-sm mt-1">Select text while reading to highlight it.</p>
            </div>
          )}

          {highlights.length > 0 && (
            <>
              {/* Color filter */}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => setColorFilter("all")}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    colorFilter === "all"
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-border text-muted hover:border-accent/40"
                  }`}
                >
                  All ({highlights.length})
                </button>
                {(["yellow", "green", "blue", "pink"] as const).map((color) => {
                  const count = highlights.filter((h) => h.color === color).length;
                  if (count === 0) return null;
                  return (
                    <button
                      key={color}
                      onClick={() => setColorFilter(color)}
                      className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-colors ${
                        colorFilter === color
                          ? "border-accent bg-accent/10 text-accent"
                          : "border-border text-muted hover:border-accent/40"
                      }`}
                    >
                      <span className={`h-2.5 w-2.5 rounded-full ${HIGHLIGHT_DOT[color]}`} />
                      {count}
                    </button>
                  );
                })}
              </div>

              <div className="space-y-6">
                {Object.entries(highlightsBySlug).map(([slug, hs]) => {
                  const displayName = slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                  return (
                    <div key={slug}>
                      <h2 className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">
                        {displayName} <span className="normal-case font-normal">({hs.length})</span>
                      </h2>
                      <div className="space-y-2">
                        {hs.map((h) => (
                          <div key={h.id} className="rounded-xl border border-border bg-surface p-4">
                            <div className="flex items-start justify-between gap-3">
                              <p className={`text-sm rounded px-1.5 py-0.5 inline-block ${HIGHLIGHT_COLOR_BG[h.color]}`}>
                                &ldquo;{h.selected_text}&rdquo;
                              </p>
                              <div className="flex items-center gap-2 shrink-0">
                                <button
                                  onClick={() => handleDeleteHighlight(h.id)}
                                  className="p-0.5 text-muted/30 hover:text-red-500 transition-colors"
                                  title="Delete highlight"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                                <div className="w-px h-3 bg-border/60" />
                                <Link
                                  href={`/read/${h.slug}/${h.chapter}#verse-${h.verse}`}
                                  className="text-xs text-accent hover:underline"
                                >
                                  Ch {h.chapter}.{h.verse} →
                                </Link>
                              </div>
                            </div>
                            {h.note && (
                              <div className="mt-2 flex items-start gap-1.5 rounded-lg bg-citation-bg px-3 py-2 text-xs text-muted">
                                <StickyNote className="h-3 w-3 shrink-0 mt-0.5 text-accent" />
                                <span>{h.note}</span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Conversations tab ───────────────────────────────────────────────── */}
      {activeTab === "conversations" && (
        <div className="space-y-2">
          {conversations.length === 0 && (
            <div className="text-center py-16 text-muted">
              <MessageCircle className="h-8 w-8 mx-auto mb-3 opacity-40" />
              <p>No conversations yet.</p>
              <Link href="/ask" className="text-sm text-accent hover:underline mt-2 inline-block">
                Start asking →
              </Link>
            </div>
          )}
          {conversations.map((conv) => (
            <div key={conv.id} className="flex items-center rounded-xl border border-border bg-surface group hover:border-accent/40 transition-colors overflow-hidden">
              <Link
                href={`/ask/c/${conv.id}`}
                className="flex flex-1 min-w-0 items-center gap-3 px-4 py-3"
              >
                <MessageCircle className="h-4 w-4 text-muted shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-foreground truncate">{conv.title || "Untitled conversation"}</p>
                  <p className="text-xs text-muted mt-0.5">
                    {new Date(conv.updated_at).toLocaleDateString("en-IN", {
                      day: "numeric", month: "short", year: "numeric",
                    })}
                  </p>
                </div>
              </Link>
              <div className="flex items-center gap-2 px-3 shrink-0">
                {confirmDeleteConvId === conv.id ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-muted">Delete?</span>
                    <button onClick={() => handleDeleteConversation(conv.id)} className="text-[10px] text-red-500 hover:text-red-600 font-medium">Yes</button>
                    <button onClick={() => setConfirmDeleteConvId(null)} className="text-[10px] text-muted hover:text-foreground">No</button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDeleteConvId(conv.id)}
                    className="p-0.5 text-muted/30 hover:text-red-500 transition-colors"
                    title="Delete conversation"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
                <div className="w-px h-3 bg-border/60" />
                <Link href={`/ask/c/${conv.id}`}>
                  <ChevronRight className="h-3.5 w-3.5 text-muted group-hover:text-accent transition-colors" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
