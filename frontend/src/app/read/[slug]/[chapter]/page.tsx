"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { ArrowLeft, ChevronLeft, ChevronRight, Bookmark, BookmarkCheck, Share2, MessageCircle, ArrowUp, ArrowDown, Trash2, X } from "lucide-react";
import { getChapter, getScriptureDetail, explainVerse, type Verse } from "@/lib/api";
import {
  saveProgress, addBookmark, removeBookmark, getBookmarksForSlug,
  getHighlightsForChapter, saveHighlight, deleteHighlight, updateHighlightNote,
  updateHighlightColor, getCurrentUserId, type Highlight,
} from "@/lib/supabase-reader";
import { HIGHLIGHT_BG, resolveHighlightSpans } from "@/lib/highlights";

// ── Text normalization helpers ────────────────────────────────────────────────

/**
 * Normalize raw chunk text into clean display paragraphs.
 * Handles PG/OCR hard word-wraps and Sujato Pali inline segment numbers.
 * Returns an array of {marker, body}.
 */
function splitIntoParagraphs(text: string): Array<{ marker: string | null; body: string }> {
  const withBreaks = text.replace(
    /([.!?:'""\u201d])\s+(\d{1,3})\s+(?=["A-Z\u201c])/g,
    "$1\n\n$2 "
  );
  const paras = withBreaks
    .split(/\n{2,}/)
    .map((p) => p.replace(/\n/g, " ").trim())
    .filter((p) => p.length > 0);

  const NUM_PREFIX = /^(\d{1,3}) ([\s\S]+)/;
  return paras.map((p) => {
    const m = p.match(NUM_PREFIX);
    if (m && parseInt(m[1]) <= 150) return { marker: m[1], body: m[2] };
    return { marker: null, body: p };
  });
}

function normalizeParagraphs(text: string): string[] {
  return text
    .split(/\n{2,}/)
    .map((p) => p.replace(/\n/g, " ").trim())
    .filter((p) => p.length > 0);
}

// ── Highlight rendering ───────────────────────────────────────────────────────
// Logic lives in src/lib/highlights.ts (exported for unit tests).
// This wrapper handles the React-specific rendering (JSX nodes).

function renderParaWithHighlights(
  paraText: string,
  verseHighlights: Highlight[],
  onHighlightClick: (h: Highlight) => void,
): React.ReactNode {
  if (verseHighlights.length === 0) return paraText;
  const spans = resolveHighlightSpans(paraText, verseHighlights);
  if (spans.length === 0) return paraText;

  const nodes: React.ReactNode[] = [];
  let pos = 0;
  for (const s of spans) {
    if (s.start > pos) nodes.push(paraText.slice(pos, s.start));
    nodes.push(
      <mark
        key={s.highlight.id}
        className={`${HIGHLIGHT_BG[s.highlight.color]} rounded-sm cursor-pointer`}
        title={s.highlight.note ?? "Click to add note"}
        onClick={() => onHighlightClick(s.highlight)}
      >
        {paraText.slice(s.start, s.end)}
        {s.highlight.note && (
          <sup className="ml-0.5 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-accent text-[9px] font-bold text-white not-italic align-middle">❝</sup>
        )}
      </mark>
    );
    pos = s.end;
  }
  if (pos < paraText.length) nodes.push(paraText.slice(pos));
  return <>{nodes}</>;
}

// ── Inline note panel ─────────────────────────────────────────────────────────

function InlineNotePanel({
  activeNote, noteText, savingNote, onNoteChange, onSave, onSkip, onDelete,
}: {
  activeNote: Highlight;
  noteText: string;
  savingNote: boolean;
  onNoteChange: (v: string) => void;
  onSave: () => void;
  onSkip: () => void;
  onDelete: () => void;
})
{
  const showSave = noteText.trim().length > 0 || activeNote.note !== null;
  return (
    <div
      className="mt-3 rounded-lg border border-border/60 p-3 text-sm"
      style={{ background: "var(--color-surface)" }}
    >
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-muted italic truncate flex-1 mr-2">
          &ldquo;{activeNote.selected_text.slice(0, 55)}{activeNote.selected_text.length > 55 ? "…" : ""}&rdquo;
        </p>
        <button
          onClick={onDelete}
          className="flex items-center gap-1 text-xs text-red-500/70 hover:text-red-500 whitespace-nowrap shrink-0"
        >
          <Trash2 className="h-3 w-3" />
          Remove
        </button>
      </div>
      <textarea
        className="w-full text-sm bg-transparent border border-border/60 rounded-lg p-2 resize-none focus:outline-none focus:ring-1 focus:ring-accent"
        placeholder="Add a note (optional)…"
        rows={2}
        value={noteText}
        onChange={(e) => onNoteChange(e.target.value)}
        autoFocus
      />
      <div className="flex items-center justify-end gap-2 mt-2">
        <button
          onClick={onSkip}
          className="text-xs text-muted hover:text-foreground px-3 py-1.5 rounded-lg border border-border"
        >
          Skip
        </button>
        {showSave && (
          <button
            onClick={onSave}
            disabled={savingNote}
            className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent-hover disabled:opacity-50"
          >
            {savingNote ? "Saving…" : noteText.trim() ? "Save note" : "Clear note"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChapterReadingPage() {
  const params = useParams();
  const slug = params.slug as string;
  const chapter = parseInt(params.chapter as string);

  const [verses, setVerses] = useState<Verse[]>([]);
  const [scriptureName, setScriptureName] = useState("");
  const [totalChapters, setTotalChapters] = useState<number | null>(null);
  const [isReadableText, setIsReadableText] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [explanations, setExplanations] = useState<Record<number, string>>({});
  const [expandedExplain, setExpandedExplain] = useState<number | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [bookmarkedVerses, setBookmarkedVerses] = useState<Record<number, string>>({});
  const [copiedVerse, setCopiedVerse] = useState<number | null>(null);
  const [scrolled, setScrolled] = useState(false);

  // Highlights state
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [selectionToolbar, setSelectionToolbar] = useState<{
    text: string; verseId: number; x: number; y: number;
  } | null>(null);
  const [activeNote, setActiveNote] = useState<Highlight | null>(null);
  const [noteText, setNoteText] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [highlightError, setHighlightError] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  // ── Data loading ────────────────────────────────────────────────────────────

  useEffect(() => {
    Promise.allSettled([
      getChapter(slug, chapter),
      getScriptureDetail(slug),
      getBookmarksForSlug(slug),
      getHighlightsForChapter(slug, chapter),
      getCurrentUserId(),
    ]).then(([chapterResult, scriptureResult, bookmarksResult, highlightsResult, userIdResult]) => {
      if (chapterResult.status === "rejected" || scriptureResult.status === "rejected") {
        setError("Could not load chapter.");
        return;
      }
      const chapterData = chapterResult.value;
      const scriptureData = scriptureResult.value;
      setVerses(chapterData.verses);
      setScriptureName(chapterData.scripture);
      setTotalChapters(scriptureData.scripture.total_chapters);
      setIsReadableText(scriptureData.scripture.readable !== false);

      if (bookmarksResult.status === "fulfilled") {
        const bMap: Record<number, string> = {};
        for (const b of bookmarksResult.value) {
          if (b.chapter === chapter) bMap[b.verse] = b.id;
        }
        setBookmarkedVerses(bMap);
      }

      if (highlightsResult.status === "fulfilled") {
        setHighlights(highlightsResult.value);
      }
      if (userIdResult.status === "fulfilled") {
        setCurrentUserId(userIdResult.value);
      }
    }).finally(() => setLoading(false));
  }, [slug, chapter]);

  // Auto-scroll to deep-linked verse
  useEffect(() => {
    if (verses.length > 0 && window.location.hash) {
      const el = document.getElementById(window.location.hash.slice(1));
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        el.classList.add("ring-2", "ring-accent/50");
        setTimeout(() => el.classList.remove("ring-2", "ring-accent/50"), 3000);
      }
    }
  }, [verses]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 300);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Save reading progress when chapter loads
  useEffect(() => {
    if (verses.length > 0) {
      saveProgress(slug, chapter, verses[0].verse).catch(() => {});
    }
  }, [slug, chapter, verses]);

  // ── Text selection → highlight toolbar ─────────────────────────────────────

  useEffect(() => {
    const handleMouseUp = () => {
      // Small delay so selection is fully committed before we read it
      setTimeout(() => {
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed) return;

        const text = selection.toString().trim();
        if (text.length < 3 || text.length > 400) return;

        const range = selection.getRangeAt(0);
        const container = range.commonAncestorContainer;
        const node = container.nodeType === Node.ELEMENT_NODE
          ? (container as Element)
          : container.parentElement;
        const verseEl = node?.closest("[data-verse-id]");
        if (!verseEl) return;

        const verseId = parseInt(verseEl.getAttribute("data-verse-id") ?? "0");
        const rect = range.getBoundingClientRect();
        setSelectionToolbar({
          text,
          verseId,
          x: rect.left + rect.width / 2,
          y: rect.top - 8,  // viewport-relative — toolbar renders fixed
        });
      }, 10);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelectionToolbar(null);
        setActiveNote(null);
        window.getSelection()?.removeAllRanges();
      }
    };

    // Clear toolbar when selection is collapsed (user clicked away)
    const handleSelectionChange = () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) setSelectionToolbar(null);
    };

    document.addEventListener("mouseup", handleMouseUp);
    document.addEventListener("touchend", handleMouseUp as EventListener);
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("selectionchange", handleSelectionChange);
    return () => {
      document.removeEventListener("mouseup", handleMouseUp);
      document.removeEventListener("touchend", handleMouseUp as EventListener);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("selectionchange", handleSelectionChange);
    };
  }, []);

  // Close note panel when clicking outside the verse card that contains it
  useEffect(() => {
    if (!activeNote) return;
    const handleMouseDown = (e: MouseEvent) => {
      const verseEl = document.querySelector(`[data-verse-id="${activeNote.verse}"]`);
      if (verseEl && !verseEl.contains(e.target as Node)) {
        setActiveNote(null);
      }
    };
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [activeNote]);

  // ── Highlight actions ───────────────────────────────────────────────────────

  const handleHighlight = async (color: Highlight["color"]) => {
    if (!selectionToolbar) return;
    if (!currentUserId) {
      setHighlightError("Sign in to save highlights.");
      setTimeout(() => setHighlightError(null), 3000);
      return;
    }
    const { text, verseId } = selectionToolbar;
    const verse = verses.find((v) => v.verse === verseId);
    if (!verse) return;

    // Determine occurrence index
    let occurrence = 0;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) {
      const range = selection.getRangeAt(0);
      const verseEl = document.querySelector(`[data-verse-id="${verseId}"]`);
      if (verseEl) {
        try {
          const preRange = document.createRange();
          preRange.setStart(verseEl, 0);
          preRange.setEnd(range.startContainer, range.startOffset);
          const textBefore = preRange.toString();
          occurrence = (textBefore.match(
            new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g")
          ) ?? []).length;
        } catch { /* ignore range errors */ }
      }
    }

    // If same text at same occurrence already highlighted, update color instead of duplicating
    const existing = highlights.find(
      (h) => h.verse === verseId && h.selected_text === text && h.selected_occurrence === occurrence
    );
    if (existing) {
      setHighlights((prev) => prev.map((h) => h.id === existing.id ? { ...h, color } : h));
      setSelectionToolbar(null);
      window.getSelection()?.removeAllRanges();
      updateHighlightColor(existing.id, color); // fire-and-forget
      return;
    }

    // Optimistic: show immediately, revert if save fails
    const tempId = `temp-${crypto.randomUUID()}`;
    const optimistic: Highlight = {
      id: tempId, slug, chapter, verse: verseId,
      selected_text: text, selected_occurrence: occurrence,
      color, note: null,
      created_at: new Date().toISOString(),
    };
    setHighlights((prev) => [...prev, optimistic]);
    setSelectionToolbar(null);
    window.getSelection()?.removeAllRanges();

    const saved = await saveHighlight(slug, chapter, verseId, text, occurrence, color);
    if (saved) {
      setHighlights((prev) => prev.map((h) => h.id === tempId ? saved : h));
      // Auto-open note panel immediately after highlight is saved
      setActiveNote(saved);
      setNoteText("");
    } else {
      setHighlights((prev) => prev.filter((h) => h.id !== tempId));
      setHighlightError("Could not save highlight — please try again.");
      setTimeout(() => setHighlightError(null), 4000);
    }
  };

  const handleHighlightClick = useCallback((h: Highlight) => {
    setActiveNote(h);
    setNoteText(h.note ?? "");
  }, []);

  const handleSaveNote = async () => {
    if (!activeNote) return;
    setSavingNote(true);
    const newNote = noteText.trim() || null;
    const ok = await updateHighlightNote(activeNote.id, noteText);
    if (ok) {
      setHighlights((prev) =>
        prev.map((h) => h.id === activeNote.id ? { ...h, note: newNote } : h)
      );
      setActiveNote(null);
    }
    setSavingNote(false);
  };

  const handleDeleteHighlight = async (id: string) => {
    const ok = await deleteHighlight(id);
    if (ok) {
      setHighlights((prev) => prev.filter((h) => h.id !== id));
      setActiveNote(null);
    }
  };

  // ── Other handlers ──────────────────────────────────────────────────────────

  const handleExplain = async (verse: Verse) => {
    if (expandedExplain === verse.verse) { setExpandedExplain(null); return; }
    setExpandedExplain(verse.verse);
    if (explanations[verse.verse]) return;
    setExplaining(true);
    try {
      const result = await explainVerse(verse.scripture, verse.chapter, verse.verse);
      setExplanations((prev) => ({ ...prev, [verse.verse]: result.explanation }));
    } catch {
      setExplanations((prev) => ({ ...prev, [verse.verse]: "Could not generate explanation. Please try again." }));
    } finally {
      setExplaining(false);
    }
  };

  const handleBookmark = async (verse: Verse) => {
    const existing = bookmarkedVerses[verse.verse];
    if (existing) {
      await removeBookmark(existing);
      setBookmarkedVerses((prev) => { const n = { ...prev }; delete n[verse.verse]; return n; });
    } else {
      const id = await addBookmark(slug, verse.scripture, verse.chapter, verse.verse);
      if (id) setBookmarkedVerses((prev) => ({ ...prev, [verse.verse]: id }));
    }
  };

  const handleShare = (verse: Verse) => {
    const url = `${window.location.origin}/read/${slug}/${chapter}/${verse.verse}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopiedVerse(verse.verse);
      setTimeout(() => setCopiedVerse(null), 2000);
    });
  };

  const scrollToTop = useCallback(() => window.scrollTo({ top: 0, behavior: "smooth" }), []);
  const scrollToBottom = useCallback(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }), []);

  // ── Loading / error states ──────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-surface border border-border" />
        ))}
      </div>
    );
  }

  if (error || verses.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-muted mb-4">{error || "No verses found."}</p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
          >
            Retry
          </button>
          <Link href={`/read/${slug}`} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface">
            Back to Contents
          </Link>
        </div>
      </div>
    );
  }

  const chapterName = verses[0]?.chapter_name;
  const isProse = verses[0]?.chunk_type === "prose";

  return (
    <div className="mx-auto max-w-2xl px-6 py-8 pr-8">

      {/* Floating selection toolbar — fixed to viewport so it follows scroll */}
      {selectionToolbar && (
        <div
          className="fixed z-50 flex items-center gap-1.5 rounded-xl border border-border shadow-2xl px-2.5 py-2"
          style={{
            left: selectionToolbar.x,
            top: selectionToolbar.y,
            transform: "translateX(-50%) translateY(-100%)",
            background: "var(--color-surface)",
          }}
          onMouseDown={(e) => e.preventDefault()}
        >
          {(["yellow", "green", "blue", "pink"] as const).map((color) => (
            <button
              key={color}
              onClick={() => handleHighlight(color)}
              className={`h-5 w-5 rounded-full border-2 border-white/80 shadow-sm hover:scale-125 transition-transform ${
                color === "yellow" ? "bg-yellow-400" :
                color === "green"  ? "bg-green-400"  :
                color === "blue"   ? "bg-blue-400"   :
                                     "bg-pink-400"
              }`}
              title={`Highlight ${color}`}
            />
          ))}
          <div className="h-4 w-px bg-border mx-0.5" />
          <Link
            href={`/ask?draft=${encodeURIComponent(
              `[${scriptureName}, Ch.${chapter}] "${selectionToolbar.text.slice(0, 300)}" — `
            )}`}
            className="text-xs text-accent font-medium hover:underline px-0.5 whitespace-nowrap"
            onClick={() => { setSelectionToolbar(null); window.getSelection()?.removeAllRanges(); }}
          >
            ✨ Ask AI
          </Link>
          <button
            onClick={() => { setSelectionToolbar(null); window.getSelection()?.removeAllRanges(); }}
            className="ml-0.5 text-muted hover:text-foreground"
            title="Dismiss"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Highlight save error toast */}
      {highlightError && (
        <div className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-border bg-surface px-4 py-2 text-sm text-muted shadow-lg">
          {highlightError}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center mb-6">
        <Link href={`/read/${slug}`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Contents
        </Link>
      </div>

      {/* Chapter title */}
      <div className="mb-8">
        <p className="text-sm text-muted">{scriptureName}</p>
        <h1 className="font-serif text-xl font-bold">
          {chapterName || `Chapter ${chapter}`}
        </h1>
      </div>

      {/* OCR quality warning */}
      {!isReadableText && (
        <div className="mb-6 rounded-xl border border-yellow-500/20 bg-yellow-500/5 px-4 py-3 text-sm text-yellow-600 dark:text-yellow-400">
          <span className="font-semibold">⚠ OCR source</span> — This text was digitized from a historical scan.
          You may see formatting artifacts, special characters, or imperfect word boundaries.
          The philosophical content is authentic; only the presentation may be rough.
        </div>
      )}

      {/* Verses */}
      <div className={isProse ? "space-y-0" : "space-y-6"}>
        {verses.map((verse) => {
          const isExpanded = expandedExplain === verse.verse;
          const verseHighlights = highlights.filter((h) => h.verse === verse.verse);

          // ── PROSE MODE ────────────────────────────────────────────────────
          if (isProse) {
            const paragraphs = splitIntoParagraphs(verse.text);
            // Find which paragraph index contains the active note's text (for inline positioning)
            const activeNoteParaIdx = activeNote?.verse === verse.verse
              ? paragraphs.findIndex((p) => p.body.includes(activeNote.selected_text))
              : -1;

            return (
              <div key={verse.verse} id={`verse-${verse.verse}`} data-verse-id={verse.verse} className="scroll-mt-20">
                {paragraphs.map((para, pi) => (
                  <div key={pi}>
                    <p className="verse-text leading-relaxed text-foreground/90 mb-5">
                      {para.marker && (
                        <sup className="mr-1.5 text-[0.65em] font-mono text-muted select-none">
                          {para.marker}
                        </sup>
                      )}
                      {renderParaWithHighlights(para.body, verseHighlights, handleHighlightClick)}
                    </p>
                    {/* Note panel appears right after the paragraph containing the highlight */}
                    {pi === activeNoteParaIdx && (
                      <InlineNotePanel
                        activeNote={activeNote!}
                        noteText={noteText}
                        savingNote={savingNote}
                        onNoteChange={setNoteText}
                        onSave={handleSaveNote}
                        onSkip={() => setActiveNote(null)}
                        onDelete={() => handleDeleteHighlight(activeNote!.id)}
                      />
                    )}
                  </div>
                ))}

                {isExpanded && (
                  <div className="mb-6 rounded-lg bg-citation-bg border-l-2 border-accent/40 p-4 text-sm">
                    {explaining && !explanations[verse.verse] ? (
                      <div className="flex gap-1 py-2">
                        <span className="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: "0ms" }} />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: "150ms" }} />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: "300ms" }} />
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap">{explanations[verse.verse]}</div>
                    )}
                  </div>
                )}

                <div className="flex items-center gap-3 mb-6 opacity-0 hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleExplain(verse)}
                    className="text-xs text-accent hover:underline flex items-center gap-1"
                  >
                    <MessageCircle className="h-3 w-3" />
                    {isExpanded ? "Hide note" : "Add note"}
                  </button>
                  <Link
                    href={`/ask?prefill=${encodeURIComponent(verse.text.slice(0, 200))}`}
                    className="text-xs text-muted hover:text-accent"
                  >
                    Discuss this
                  </Link>
                  <button
                    onClick={() => handleShare(verse)}
                    className="ml-auto text-xs text-muted hover:text-foreground flex items-center gap-1"
                    aria-label="Copy share link"
                  >
                    <Share2 className="h-3 w-3" />
                    {copiedVerse === verse.verse && <span className="text-success">Copied!</span>}
                  </button>
                </div>

                <div className="border-t border-border/20 mb-2" />
              </div>
            );
          }

          // ── VERSE MODE ────────────────────────────────────────────────────
          return (
            <div
              key={verse.verse}
              id={`verse-${verse.verse}`}
              data-verse-id={verse.verse}
              className="rounded-xl border border-border p-5 scroll-mt-20"
            >
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-mono text-muted bg-surface px-2 py-0.5 rounded">
                  {chapter}.{verse.verse}
                </span>
                {verse.speaker && (
                  <span className="text-xs text-accent font-semibold">{verse.speaker}</span>
                )}
              </div>

              <div className="verse-text leading-loose">
                {normalizeParagraphs(verse.text).map((para, bi) => (
                  <p key={bi} className="mb-2 last:mb-0">
                    {renderParaWithHighlights(para, verseHighlights, handleHighlightClick)}
                  </p>
                ))}
              </div>

              <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50">
                <button
                  onClick={() => handleExplain(verse)}
                  className="text-xs text-accent hover:underline flex items-center gap-1"
                >
                  <MessageCircle className="h-3 w-3" />
                  {isExpanded ? "Hide meaning" : "What does this mean?"}
                </button>
                <Link
                  href={`/ask?prefill=${encodeURIComponent(verse.text.slice(0, 200))}`}
                  className="text-xs text-muted hover:text-accent flex items-center gap-1"
                >
                  Discuss this
                </Link>
                <button
                  onClick={() => handleBookmark(verse)}
                  className="text-xs text-muted hover:text-accent flex items-center gap-1 transition-colors"
                  aria-label="Bookmark this verse"
                >
                  {bookmarkedVerses[verse.verse] ? (
                    <BookmarkCheck className="h-3 w-3 text-accent" />
                  ) : (
                    <Bookmark className="h-3 w-3" />
                  )}
                </button>
                {verseHighlights.length > 0 && (
                  <span className="text-xs text-muted/60 ml-1">
                    {verseHighlights.length} highlight{verseHighlights.length !== 1 ? "s" : ""}
                  </span>
                )}
                <button
                  onClick={() => handleShare(verse)}
                  className="ml-auto text-xs text-muted hover:text-foreground flex items-center gap-1"
                  aria-label="Copy share link"
                >
                  <Share2 className="h-3 w-3" />
                  {copiedVerse === verse.verse && <span className="text-success">Copied!</span>}
                </button>
              </div>

              {isExpanded && (
                <div className="mt-3 rounded-lg bg-citation-bg p-4">
                  {explaining && !explanations[verse.verse] ? (
                    <div className="flex gap-1 py-2">
                      <span className="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: "0ms" }} />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: "150ms" }} />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: "300ms" }} />
                    </div>
                  ) : (
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                      <ReactMarkdown>{explanations[verse.verse]}</ReactMarkdown>
                    </div>
                  )}
                </div>
              )}

              {/* Inline note panel for verse mode */}
              {activeNote?.verse === verse.verse && (
                <InlineNotePanel
                  activeNote={activeNote}
                  noteText={noteText}
                  savingNote={savingNote}
                  onNoteChange={setNoteText}
                  onSave={handleSaveNote}
                  onSkip={() => setActiveNote(null)}
                  onDelete={() => handleDeleteHighlight(activeNote.id)}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Chapter navigation */}
      <div className="flex items-center justify-between mt-10 pt-6 border-t border-border">
        {chapter > 1 ? (
          <Link href={`/read/${slug}/${chapter - 1}`} className="flex items-center gap-1 text-sm text-muted hover:text-foreground transition-colors">
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Link>
        ) : (
          <span className="text-sm text-muted/40 flex items-center gap-1">
            <ChevronLeft className="h-4 w-4" />
            Previous
          </span>
        )}

        <span className="text-sm text-muted">
          Ch {chapter}{totalChapters ? ` of ${totalChapters}` : ""}
        </span>

        {totalChapters === null || chapter < totalChapters ? (
          <Link href={`/read/${slug}/${chapter + 1}`} className="flex items-center gap-1 text-sm text-muted hover:text-foreground transition-colors">
            Next
            <ChevronRight className="h-4 w-4" />
          </Link>
        ) : (
          <span className="text-sm text-muted/40 flex items-center gap-1">
            Next
            <ChevronRight className="h-4 w-4" />
          </span>
        )}
      </div>

      {/* Floating scroll buttons */}
      <div className="fixed right-6 bottom-8 flex flex-col gap-2 z-40">
        {scrolled && (
          <button
            onClick={scrollToTop}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-surface border border-border shadow-md text-muted hover:text-foreground hover:bg-accent hover:text-white hover:border-accent transition-all"
            aria-label="Scroll to top"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
        <button
          onClick={scrollToBottom}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-surface border border-border shadow-md text-muted hover:text-foreground hover:bg-accent hover:text-white hover:border-accent transition-all"
          aria-label="Scroll to bottom"
        >
          <ArrowDown className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
