"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, BookOpen } from "lucide-react";
import { getScriptureDetail, type Scripture, type ChapterSummary } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

export default function ChapterListPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [scripture, setScripture] = useState<Scripture | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSignedIn, setIsSignedIn] = useState<boolean | null>(null);

  useEffect(() => {
    getScriptureDetail(slug)
      .then((data) => {
        setScripture(data.scripture);
        setChapters(data.chapters);
      })
      .catch(() => setError("Could not load scripture. Tap to retry."))
      .finally(() => setLoading(false));

    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => {
      setIsSignedIn(!!user);
    });
  }, [slug]);

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-14 animate-pulse rounded-lg bg-surface border border-border mb-2" />
        ))}
      </div>
    );
  }

  if (error || !scripture) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-muted mb-4">{error || "Scripture not found."}</p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
          >
            Retry
          </button>
          <Link href="/library" className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface">
            Back to Library
          </Link>
        </div>
      </div>
    );
  }

  const totalVerses = chapters.reduce((sum, c) => sum + c.verse_count, 0);

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      {/* Back nav */}
      <Link href="/library" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground mb-6 transition-colors">
        <ArrowLeft className="h-4 w-4" />
        Library
      </Link>

      {/* Scripture header */}
      <div className="mb-6">
        <h1 className="font-serif text-2xl font-bold mb-1">{scripture.scripture}</h1>
        <p className="text-sm text-muted">
          {scripture.translator}, {scripture.year} &middot; {chapters.length} chapters &middot; {totalVerses} verses
        </p>
      </div>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="h-1.5 w-full rounded-full bg-surface border border-border overflow-hidden">
          <div className="h-full rounded-full bg-accent/40" style={{ width: "0%" }} />
        </div>
        {isSignedIn === false && (
          <p className="text-xs text-muted mt-1">Sign in to track reading progress</p>
        )}
      </div>

      {/* Chapter list */}
      <div className="space-y-1">
        {chapters.map((ch) => (
          <Link
            key={ch.chapter}
            href={`/read/${slug}/${ch.chapter}`}
            className="flex items-center justify-between rounded-lg border border-border px-4 py-3 hover:bg-surface hover:border-accent/30 transition-all group"
          >
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-surface text-xs font-medium text-muted group-hover:bg-accent/10 group-hover:text-accent">
                {ch.chapter}
              </span>
              <div>
                <p className="text-sm font-medium group-hover:text-accent transition-colors">
                  {ch.name || `Chapter ${ch.chapter}`}
                </p>
                <p className="text-xs text-muted">{ch.verse_count} {ch.verse_type === "prose" ? "paragraphs" : "verses"}</p>
              </div>
            </div>
            <BookOpen className="h-4 w-4 text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
          </Link>
        ))}
      </div>

      {/* Ask CTA */}
      <div className="mt-8 text-center">
        <Link
          href={`/ask?prefill=${encodeURIComponent(`Tell me about ${scripture.scripture}`)}`}
          className="text-sm text-accent hover:underline"
        >
          Ask about this text &rarr;
        </Link>
      </div>
    </div>
  );
}
