"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { ArrowLeft, ChevronLeft, ChevronRight, Bookmark, BookmarkCheck, Share2, MessageCircle, ArrowUp, ArrowDown } from "lucide-react";
import { getChapter, getScriptureDetail, explainVerse, type Verse } from "@/lib/api";
import { saveProgress, addBookmark, removeBookmark, getBookmarksForSlug } from "@/lib/supabase-reader";

/**
 * Normalize raw chunk text into clean display paragraphs.
 *
 * Handles two source text issues:
 * 1. PG/OCR hard word-wraps: single \n within a paragraph → join into space
 * 2. Sujato Pali inline segment numbers: "...mind." 2 "Mendicants…" with no
 *    newline before each number → insert paragraph break before the number
 *
 * Returns an array of {marker, body} where marker is an optional leading
 * paragraph number (Sujato segment index) to render as superscript.
 */
function splitIntoParagraphs(text: string): Array<{ marker: string | null; body: string }> {
  // Step 1: Insert \n\n before Sujato inline paragraph numbers.
  // Pattern: after any sentence-end punctuation (. ! ? : " '), followed by a
  // small integer, followed by an uppercase letter or opening quote.
  // "...mind." 3 "Mendicants…" → "...mind.\n\n3 "Mendicants…"
  const withBreaks = text.replace(
    /([.!?:'""\u201d])\s+(\d{1,3})\s+(?=["A-Z\u201c])/g,
    "$1\n\n$2 "
  );

  // Step 2: Split on paragraph boundaries (double newlines), then join
  // soft word-wrap single newlines within each paragraph into spaces.
  const paras = withBreaks
    .split(/\n{2,}/)
    .map((p) => p.replace(/\n/g, " ").trim())
    .filter((p) => p.length > 0);

  // Step 3: Extract optional leading paragraph number from each paragraph.
  // Matches "1 So I have heard…" or "42 The practices…" at the start.
  const NUM_PREFIX = /^(\d{1,3}) ([\s\S]+)/;
  return paras.map((p) => {
    const m = p.match(NUM_PREFIX);
    // Sanity check: number must be small (not a year like 1885 or large chapter ref)
    if (m && parseInt(m[1]) <= 150) return { marker: m[1], body: m[2] };
    return { marker: null, body: p };
  });
}

/** Same normalization for verse mode (no paragraph markers needed). */
function normalizeParagraphs(text: string): string[] {
  return text
    .split(/\n{2,}/)
    .map((p) => p.replace(/\n/g, " ").trim())
    .filter((p) => p.length > 0);
}

export default function ChapterReadingPage() {
  const params = useParams();
  const slug = params.slug as string;
  const chapter = parseInt(params.chapter as string);

  const [verses, setVerses] = useState<Verse[]>([]);
  const [scriptureName, setScriptureName] = useState("");
  const [totalChapters, setTotalChapters] = useState<number | null>(null);
  const [isReadableText, setIsReadableText] = useState(true); // false = OCR source
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // explanations: keyed by verse number, persists across expand/collapse within same chapter
  const [explanations, setExplanations] = useState<Record<number, string>>({});
  const [expandedExplain, setExpandedExplain] = useState<number | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [bookmarkedVerses, setBookmarkedVerses] = useState<Record<number, string>>({}); // verse → bookmark id

  useEffect(() => {
    // Use allSettled so a Supabase bookmark failure doesn't kill the reading experience
    Promise.allSettled([
      getChapter(slug, chapter),
      getScriptureDetail(slug),
      getBookmarksForSlug(slug),
    ])
      .then(([chapterResult, scriptureResult, bookmarksResult]) => {
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

        // Bookmarks are optional — failure is silent (user may not be logged in)
        if (bookmarksResult.status === "fulfilled") {
          const bookmarkMap: Record<number, string> = {};
          for (const b of bookmarksResult.value) {
            if (b.chapter === chapter) bookmarkMap[b.verse] = b.id;
          }
          setBookmarkedVerses(bookmarkMap);
        }
      })
      .finally(() => setLoading(false));
  }, [slug, chapter]);

  // Auto-scroll to deep-linked verse once verses are loaded
  useEffect(() => {
    if (verses.length > 0 && window.location.hash) {
      const id = window.location.hash.slice(1); // e.g. "verse-7"
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        el.classList.add("ring-2", "ring-accent/50"); // subtle highlight
        setTimeout(() => el.classList.remove("ring-2", "ring-accent/50"), 3000);
      }
    }
  }, [verses]);

  const handleExplain = async (verse: Verse) => {
    if (expandedExplain === verse.verse) {
      setExpandedExplain(null); // collapse — but keep cached explanation
      return;
    }
    setExpandedExplain(verse.verse);
    if (explanations[verse.verse]) return; // already fetched — just show it
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

  const [copiedVerse, setCopiedVerse] = useState<number | null>(null);
  const [scrolled, setScrolled] = useState(false);

  // Track scroll position to show/hide the "back to top" button
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 300);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollToTop = useCallback(() => window.scrollTo({ top: 0, behavior: "smooth" }), []);
  const scrollToBottom = useCallback(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }), []);

  // Save reading progress when chapter loads (after verses are available)
  useEffect(() => {
    if (verses.length > 0) {
      saveProgress(slug, chapter, verses[0].verse).catch(() => {});
    }
  }, [slug, chapter, verses]);

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
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <Link href={`/read/${slug}`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Contents
        </Link>
        <button
          onClick={() => verses[0] && handleBookmark(verses[0])}
          className="rounded-md p-2 text-muted hover:text-accent transition-colors"
          aria-label="Bookmark this chapter"
          title="Bookmark chapter start"
        >
          {bookmarkedVerses[verses[0]?.verse] ? (
            <BookmarkCheck className="h-4 w-4 text-accent" />
          ) : (
            <Bookmark className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Chapter title */}
      <div className="mb-8">
        <p className="text-sm text-muted">{scriptureName}</p>
        <h1 className="font-serif text-xl font-bold">
          {chapterName || `Chapter ${chapter}`}
        </h1>
      </div>

      {/* OCR quality warning — shown for texts not in the curated reading library */}
      {!isReadableText && (
        <div className="mb-6 rounded-xl border border-yellow-500/20 bg-yellow-500/5 px-4 py-3 text-sm text-yellow-600 dark:text-yellow-400">
          <span className="font-semibold">⚠ OCR source</span> — This text was digitized from a historical scan. 
          You may see formatting artifacts, special characters, or imperfect word boundaries. 
          The philosophical content is authentic; only the presentation may be rough.
        </div>
      )}

      {/* Verses — two display modes: verse (boxed, numbered) vs prose (flowing like a book) */}
      <div className={isProse ? "space-y-0" : "space-y-6"}>
        {verses.map((verse) => {
          const isExpanded = expandedExplain === verse.verse;

          // ── PROSE MODE (Vivekananda, commentary, Pali suttas) ────────────────
          // Continuous flowing text like a real book. No cards, no verse numbers.
          // Each chunk may contain multiple paragraphs; we render them separately.
          if (isProse) {
            const paragraphs = splitIntoParagraphs(verse.text);
            return (
              <div
                key={verse.verse}
                id={`verse-${verse.verse}`}
                className="scroll-mt-20"
              >
                {paragraphs.map((para, pi) => (
                  <p key={pi} className="verse-text leading-relaxed text-foreground/90 mb-5">
                    {para.marker && (
                      <sup className="mr-1.5 text-[0.65em] font-mono text-muted select-none">
                        {para.marker}
                      </sup>
                    )}
                    {para.body}
                  </p>
                ))}

                {/* Inline explanation for prose — shown below paragraph */}
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

                {/* Minimal prose actions — shown on hover, stays out of the way */}
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

                {/* Paragraph separator */}
                <div className="border-t border-border/20 mb-2" />
              </div>
            );
          }

          // ── VERSE MODE (Gita, Upanishads, Dhammapada) ─────────────────────────
          // Boxed cards with clear verse numbering — each shloka is a complete teaching.
          return (
            <div
              key={verse.verse}
              id={`verse-${verse.verse}`}
              className="rounded-xl border border-border p-5 scroll-mt-20"
            >
              {/* Verse number + speaker */}
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-mono text-muted bg-surface px-2 py-0.5 rounded">
                  {chapter}.{verse.verse}
                </span>
                {verse.speaker && (
                  <span className="text-xs text-accent font-semibold">{verse.speaker}</span>
                )}
              </div>

              {/* Verse text — soft word-wrap \n joined into spaces, \n\n = new paragraph */}
              <div className="verse-text leading-loose">
                {normalizeParagraphs(verse.text).map((para, bi) => (
                  <p key={bi} className="mb-2 last:mb-0">{para}</p>
                ))}
              </div>

              {/* Actions */}
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
                  title="Bookmark verse"
                >
                  {bookmarkedVerses[verse.verse] ? (
                    <BookmarkCheck className="h-3 w-3 text-accent" />
                  ) : (
                    <Bookmark className="h-3 w-3" />
                  )}
                </button>
                <button
                  onClick={() => handleShare(verse)}
                  className="ml-auto text-xs text-muted hover:text-foreground flex items-center gap-1"
                  aria-label="Copy share link"
                >
                  <Share2 className="h-3 w-3" />
                  {copiedVerse === verse.verse && <span className="text-success">Copied!</span>}
                </button>
              </div>

              {/* Explanation panel (inline) */}
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
            </div>
          );
        })}
      </div>

      {/* Chapter navigation */}
      <div className="flex items-center justify-between mt-10 pt-6 border-t border-border">
        {chapter > 1 ? (
          <Link
            href={`/read/${slug}/${chapter - 1}`}
            className="flex items-center gap-1 text-sm text-muted hover:text-foreground transition-colors"
          >
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
          <Link
            href={`/read/${slug}/${chapter + 1}`}
            className="flex items-center gap-1 text-sm text-muted hover:text-foreground transition-colors"
          >
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

      {/* Floating scroll buttons — fixed to right side, well inside the viewport
          so users don't accidentally hit the browser window edge */}
      <div className="fixed right-6 bottom-8 flex flex-col gap-2 z-50">
        {scrolled && (
          <button
            onClick={scrollToTop}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-surface border border-border shadow-md text-muted hover:text-foreground hover:bg-accent hover:text-white hover:border-accent transition-all"
            aria-label="Scroll to top"
            title="Back to top"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
        <button
          onClick={scrollToBottom}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-surface border border-border shadow-md text-muted hover:text-foreground hover:bg-accent hover:text-white hover:border-accent transition-all"
          aria-label="Scroll to bottom"
          title="Jump to end"
        >
          <ArrowDown className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
