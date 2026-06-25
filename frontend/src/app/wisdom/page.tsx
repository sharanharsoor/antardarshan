"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ThumbsUp, ThumbsDown, Edit2, Trash2, Plus, X, Phone, Mail, ChevronDown } from "lucide-react";

const MAX_DAILY_ATTEMPTS = 5; // matches backend wisdom.py MAX_MOD_ATTEMPTS_PER_DAY
import { createClient } from "@/utils/supabase/client";
import {
  getWisdomPosts, createPost, editPost, deletePost, votePost,
  getDisplayName, setDisplayName, type WisdomPost,
} from "@/lib/wisdom";

// ── Post card ─────────────────────────────────────────────────────────

function PostCard({
  post, currentUserId, onVote, onEdit, onDelete,
}: {
  post: WisdomPost;
  currentUserId: string | null;
  onVote: (id: string, vote: "up" | "down") => void;
  onEdit: (post: WisdomPost) => void;
  onDelete: (id: string) => void;
}) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  // is_owner is set by backend from verified JWT — correct even after display name changes
  const isOwner = !!currentUserId && post.is_owner;
  const showContact = !post.contact_hidden_at && (post.contact_email || post.contact_phone);
  const date = new Date(post.created_at).toLocaleDateString("en-IN", {
    day: "numeric", month: "short",
  });

  return (
    <div className="rounded-2xl border border-border/60 bg-surface p-5 space-y-4 hover:border-accent/30 transition-colors duration-200 group">
      {/* Decorative quote mark */}
      <div className="text-4xl leading-none text-accent/25 font-serif select-none -mb-2">❝</div>

      {/* Content — serif font, more readable */}
      <p className="font-serif text-base leading-relaxed text-foreground/85 whitespace-pre-wrap">{post.content}</p>

      {/* Contact info */}
      {showContact && (
        <div className="rounded-lg border border-accent/10 bg-accent/5 px-3 py-2.5 text-xs text-muted space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-accent/60">Connect</p>
          {post.contact_email && (
            <div className="flex items-center gap-2">
              <Mail className="h-3 w-3 text-accent/50" />
              <span>{post.contact_email}</span>
            </div>
          )}
          {post.contact_phone && (
            <div className="flex items-center gap-2">
              <Phone className="h-3 w-3 text-accent/50" />
              <span>{post.contact_phone}</span>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="border-t border-border/30 pt-3 flex items-center justify-between gap-2">
        <div className="flex flex-col">
          <span className="text-xs font-medium text-accent">{post.display_name}</span>
          <span className="text-[10px] text-muted/60">
            {date}{post.is_edited ? " · edited" : ""}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Votes */}
          <button
            onClick={() => onVote(post.id, "up")}
            disabled={!currentUserId}
            className="flex items-center gap-1 text-xs text-muted hover:text-success disabled:opacity-30 transition-colors"
            title={currentUserId ? "Upvote" : "Sign in to vote"}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
            <span>{post.upvotes}</span>
          </button>
          <button
            onClick={() => onVote(post.id, "down")}
            disabled={!currentUserId}
            className="flex items-center gap-1 text-xs text-muted hover:text-error disabled:opacity-30 transition-colors"
            title={currentUserId ? "Downvote" : "Sign in to vote"}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </button>

          {/* Owner actions */}
          {isOwner && (
            confirmingDelete ? (
              <div className="flex items-center gap-1.5 ml-1">
                <span className="text-[10px] text-muted">Delete?</span>
                <button onClick={() => { onDelete(post.id); setConfirmingDelete(false); }} className="text-[10px] text-error font-medium">Yes</button>
                <button onClick={() => setConfirmingDelete(false)} className="text-[10px] text-muted">No</button>
              </div>
            ) : (
              <div className="flex items-center gap-1 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => onEdit(post)} className="p-1 text-muted/50 hover:text-accent transition-colors" title="Edit">
                  <Edit2 className="h-3 w-3" />
                </button>
                <button onClick={() => setConfirmingDelete(true)} className="p-1 text-muted/50 hover:text-error transition-colors" title="Delete">
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}

// ── Submit / Edit form ────────────────────────────────────────────────

function PostForm({
  editingPost, displayName, onSubmit, onCancel,
}: {
  editingPost: WisdomPost | null;
  displayName: string;
  onSubmit: (content: string, email?: string, phone?: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [content, setContent] = useState(editingPost?.content ?? "");
  const [email, setEmail] = useState(editingPost?.contact_email ?? "");
  const [phone, setPhone] = useState(editingPost?.contact_phone ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showContact, setShowContact] = useState(
    !!(editingPost?.contact_email || editingPost?.contact_phone)
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) { setError("Content cannot be empty."); return; }
    if (content.length > 2000) { setError("Content exceeds 2000 characters."); return; }
    setSubmitting(true);
    setError(null);
    await onSubmit(content.trim(), email.trim() || undefined, phone.trim() || undefined);
    setSubmitting(false);
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">
          {editingPost ? "Edit your post" : "Share your wisdom"}
        </p>
        <button onClick={onCancel} className="text-muted hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      <p className="text-xs text-muted">Posting as <span className="text-accent font-medium">{displayName}</span></p>

      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Share a spiritual experience, insight, or philosophical reflection..."
          rows={5}
          className="w-full bg-transparent border border-border rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-accent"
          autoFocus
        />
        <p className="text-[11px] text-muted/60 text-right">{content.length}/2000</p>

        {/* Optional contact info */}
        <button
          type="button"
          onClick={() => setShowContact((v) => !v)}
          className="text-xs text-muted hover:text-accent flex items-center gap-1"
        >
          <ChevronDown className={`h-3 w-3 transition-transform ${showContact ? "rotate-180" : ""}`} />
          {showContact ? "Hide contact options" : "Add optional contact info"}
        </button>

        {showContact && (
          <div className="space-y-2 rounded-lg border border-border/50 p-3">
            <p className="text-[11px] text-muted/60">
              Optional. Only shown for 15 days. For spiritual connection only.
            </p>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email (optional)"
              className="w-full bg-transparent border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Phone (optional)"
              className="w-full bg-transparent border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
        )}

        {error && <p className="text-xs text-error">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="text-sm text-muted hover:text-foreground px-4 py-2 rounded-lg border border-border"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="text-sm bg-accent text-white rounded-lg px-4 py-2 hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? "Submitting…" : editingPost ? "Save changes" : "Post"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Display name setup ────────────────────────────────────────────────

function DisplayNameSetup({ onSet }: { onSet: (name: string) => void }) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!name.trim() || name.length > 50) { setError("Display name must be 1–50 characters."); return; }
    setSaving(true);
    const result = await setDisplayName(name.trim());
    setSaving(false);
    if (result.ok) onSet(name.trim());
    else setError(result.error ?? "Could not save display name. Please try again.");
  };

  return (
    <div className="rounded-xl border border-accent/20 bg-surface p-6 text-center space-y-4 max-w-md mx-auto">
      <p className="font-serif text-lg font-medium">Choose your Wisdom Wall name</p>
      <p className="text-sm text-muted">This is how your posts will appear to others. You can change it later.</p>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Your display name"
        maxLength={50}
        className="w-full bg-transparent border border-border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
        autoFocus
        onKeyDown={(e) => e.key === "Enter" && handleSave()}
      />
      {error && <p className="text-xs text-error">{error}</p>}
      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full bg-accent text-white rounded-lg py-2.5 text-sm hover:bg-accent-hover disabled:opacity-50"
      >
        {saving ? "Saving…" : "Set display name"}
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────

export default function WisdomWallPage() {
  const router = useRouter();
  const [posts, setPosts] = useState<WisdomPost[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [displayName, setDisplayNameState] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingPost, setEditingPost] = useState<WisdomPost | null>(null);
  const [submitMessage, setSubmitMessage] = useState<{ type: "success" | "error" | "rejected"; text: string; persistent?: boolean } | null>(null);
  const [needsDisplayName, setNeedsDisplayName] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    // Initial auth check
    supabase.auth.getUser().then(({ data: { user } }) => {
      setCurrentUserId(user?.id ?? null);
      if (user) getDisplayName().then(setDisplayNameState);
    });
    // React to actual sign-in / sign-out transitions — update identity + reload feed.
    // Skip INITIAL_SESSION: that fires on every mount and the initial useEffect already loads.
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "INITIAL_SESSION") return;
      const uid = session?.user?.id ?? null;
      setCurrentUserId(uid);
      if (uid) getDisplayName().then(setDisplayNameState);
      else setDisplayNameState(null);
      setPage(1);
      setPosts([]);
      setLoading(true);
      getWisdomPosts(1, 10).then(({ posts: newPosts }) => {
        setPosts(newPosts);
        setHasMore(newPosts.length === 10);
        setLoading(false);
      });
    });
    return () => subscription.unsubscribe();
  }, []);

  const loadPosts = useCallback(async (p: number) => {
    setLoading(true);
    const { posts: newPosts } = await getWisdomPosts(p, 10);
    if (p === 1) setPosts(newPosts);
    else setPosts((prev) => [...prev, ...newPosts]);
    setHasMore(newPosts.length === 10);
    setLoading(false);
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { loadPosts(1); }, [loadPosts]);

  const handleVote = async (postId: string, vote: "up" | "down") => {
    if (!currentUserId) return;
    const result = await votePost(postId, vote);
    if (result.ok) {
      // Optimistic UI update
      setPosts((prev) => prev.map((p) => {
        if (p.id !== postId) return p;
      if (vote === "up") {
          return { ...p, upvotes: p.upvotes + (result.action === "removed" ? -1 : 1),
                   downvotes: result.action === "changed" ? Math.max(p.downvotes - 1, 0) : p.downvotes };
        } else {
          return { ...p, downvotes: p.downvotes + (result.action === "removed" ? -1 : 1),
                   upvotes: result.action === "changed" ? Math.max(p.upvotes - 1, 0) : p.upvotes };
        }
      }));
    }
  };

  const handleSubmit = async (content: string, email?: string, phone?: string) => {
    if (!currentUserId) { router.push("/ask"); return; }
    if (!displayName) { setNeedsDisplayName(true); return; }

    const result = editingPost
      ? await editPost(editingPost.id, content, email, phone)
      : await createPost(content, email, phone);

    if (result.status === "approved") {
      setShowForm(false);
      setEditingPost(null);
      setSubmitMessage({ type: "success", text: editingPost ? "Post updated!" : "Post shared to the Wisdom Wall!" });
      setTimeout(() => setSubmitMessage(null), 4000);
      loadPosts(1);
    } else if (result.status === "rejected") {
      // Persistent — user must close manually so they can read the rejection reason
      setSubmitMessage({ type: "rejected", text: result.message ?? "Post rejected. Please review the Wisdom Wall guidelines.", persistent: true });
    } else {
      setSubmitMessage({ type: "error", text: result.message ?? "Something went wrong.", persistent: result.error_type === "moderation_limit" || result.error_type === "daily_post_limit" });
      if (!result.error_type) setTimeout(() => setSubmitMessage(null), 6000);
    }
  };

  const handleDelete = async (postId: string) => {
    const ok = await deletePost(postId);
    if (ok) setPosts((prev) => prev.filter((p) => p.id !== postId));
  };

  return (
    <div className="min-h-[calc(100vh-3.5rem)]">

      {/* Atmospheric header */}
      <div className="relative overflow-hidden border-b border-border/40 bg-gradient-to-b from-accent/5 to-transparent px-4 py-12 text-center">
        {/* Decorative background text */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none overflow-hidden">
          <span className="text-[12rem] font-serif text-accent/[0.04] leading-none">❝</span>
        </div>
        <div className="relative">
          <h1 className="font-serif text-4xl font-bold mb-2">Wisdom Wall</h1>
          <p className="text-muted max-w-md mx-auto text-sm leading-relaxed">
            Spiritual experiences and philosophical reflections from the community. Every voice a lamp, every thought a gift.
          </p>
          {currentUserId && (
            <button
              onClick={() => {
                if (!displayName) { setNeedsDisplayName(true); return; }
                setEditingPost(null);
                setShowForm(true);
              }}
              className="mt-6 inline-flex items-center gap-2 rounded-full bg-accent text-white px-6 py-2.5 text-sm hover:bg-accent-hover transition-colors shadow-lg"
            >
              <Plus className="h-4 w-4" />
              Share your wisdom
            </button>
          )}
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-4 py-8">

      {/* Display name setup modal */}
      {needsDisplayName && (
        <div className="mb-6">
          <DisplayNameSetup onSet={(name) => {
            setDisplayNameState(name);
            setNeedsDisplayName(false);
            setShowForm(true);
          }} />
        </div>
      )}

      {/* Submit form */}
      {showForm && displayName && (
        <div className="mb-6">
          <PostForm
            editingPost={editingPost}
            displayName={displayName}
            onSubmit={handleSubmit}
            onCancel={() => { setShowForm(false); setEditingPost(null); }}
          />
        </div>
      )}

      {/* Feedback message */}
      {submitMessage && (
        <div className={`mb-4 rounded-lg border px-4 py-3 text-sm ${
          submitMessage.type === "success" ? "border-success/30 bg-success/10 text-success" :
          submitMessage.type === "rejected" ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-700 dark:text-yellow-300" :
          "border-error/30 bg-error/10 text-error"
        }`}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <p>{submitMessage.text}</p>
              {submitMessage.type === "rejected" && (
                <div className="mt-2 text-xs opacity-80 space-y-0.5">
                  <p className="font-medium">Wisdom Wall Guidelines — posts must:</p>
                  <p>• Relate to Indian philosophy, spiritual experiences, or personal growth</p>
                  <p>• Be a genuine personal reflection, insight, or philosophical thought</p>
                  <p>• Not contain spam, ads, political content, or harmful material</p>
                  <p className="mt-1 opacity-70">Each attempt (approved or rejected) counts toward your {MAX_DAILY_ATTEMPTS} daily limit.</p>
                </div>
              )}
            </div>
            {submitMessage.persistent && (
              <button
                onClick={() => setSubmitMessage(null)}
                className="shrink-0 opacity-60 hover:opacity-100 transition-opacity mt-0.5"
                aria-label="Dismiss"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      )}


      {/* Not logged in banner */}
      {!currentUserId && (
        <div className="mb-6 rounded-xl border border-accent/20 bg-surface px-4 py-3 text-sm text-muted text-center">
          <button onClick={() => router.push("/ask")} className="text-accent hover:underline">Sign in</button>
          {" "}to share your own wisdom or vote on posts.
        </div>
      )}

      {/* Posts feed */}
      {loading && posts.length === 0 ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-surface border border-border" />
          ))}
        </div>
      ) : posts.length === 0 ? (
        <div className="text-center py-16 text-muted">
          <p className="text-lg mb-2">No posts yet.</p>
          <p className="text-sm">Be the first to share your wisdom.</p>
        </div>
      ) : (
        <div>
          {/* 2-column masonry grid */}
          <div className="columns-1 sm:columns-2 gap-4">
            {posts.map((post) => (
              <div key={post.id} className="break-inside-avoid mb-4">
                <PostCard
                  post={post}
                  currentUserId={currentUserId}
                  onVote={handleVote}
                  onEdit={(p) => {
                    if (!displayName) { setNeedsDisplayName(true); return; }
                    setEditingPost(p);
                    setShowForm(true);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  onDelete={handleDelete}
                />
              </div>
            ))}
          </div>

          {hasMore && (
            <button
              onClick={() => { const next = page + 1; setPage(next); loadPosts(next); }}
              disabled={loading}
              className="w-full mt-4 py-3 text-sm text-muted hover:text-foreground border border-border rounded-xl hover:bg-surface transition-colors disabled:opacity-50"
            >
              {loading ? "Loading…" : "Load more"}
            </button>
          )}
        </div>
      )}

      {/* Guidelines */}
      <p className="text-center text-xs text-muted/50 mt-10">
        Posts are moderated for spiritual and philosophical content.{" "}
        <a href="/about#wisdom-guidelines" className="hover:text-muted underline underline-offset-2">Community guidelines</a>
      </p>
    </div>
    </div>
  );
}
