"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { BookOpen } from "lucide-react";
import { getLibrary, type Scripture } from "@/lib/api";

const TRADITION_LABELS: Record<string, string> = {
  hindu_vedanta: "Vedanta",
  hindu_yoga: "Yoga",
  buddhist: "Buddhist",
  jain: "Jain",
  sikh: "Sikh",
  sant_bhakti: "Sant/Bhakti",
};

const TRADITION_COLORS: Record<string, string> = {
  hindu_vedanta: "bg-[var(--color-vedanta)]",
  hindu_yoga: "bg-[var(--color-yoga)]",
  buddhist: "bg-[var(--color-buddhist)]",
  jain: "bg-[var(--color-jain)]",
  sikh: "bg-[var(--color-sikh)]",
  sant_bhakti: "bg-[var(--color-bhakti)]",
};

function LibraryLoading() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-40 animate-pulse rounded-xl bg-surface border border-border" />
        ))}
      </div>
    </div>
  );
}

function LibraryPageContent() {
  const searchParams = useSearchParams();
  const [scriptures, setScriptures] = useState<Scripture[]>([]);
  // Initialise from URL ?filter= so landing-page tradition cards deep-link correctly
  const [filter, setFilter] = useState<string>(searchParams.get("filter") ?? "all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLibrary()
      .then(setScriptures)
      .catch(() => setError("Could not load library. Tap to retry."))
      .finally(() => setLoading(false));
  }, []);

  const traditions = [...new Set(scriptures.map((s) => s.tradition))];
  const filtered = filter === "all" ? scriptures : scriptures.filter((s) => s.tradition === filter);

  // Group by tradition
  const grouped = filtered.reduce<Record<string, Scripture[]>>((acc, s) => {
    acc[s.tradition] = acc[s.tradition] || [];
    acc[s.tradition].push(s);
    return acc;
  }, {});

  if (loading) {
    return <LibraryLoading />;
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-muted mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="font-serif text-3xl font-bold mb-6">Scripture Library</h1>

      {/* Filter tabs */}
      <div className="flex flex-wrap gap-2 mb-8">
        <button
          onClick={() => setFilter("all")}
          className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
            filter === "all" ? "bg-accent text-white" : "border border-border text-muted hover:bg-surface"
          }`}
        >
          All ({scriptures.length})
        </button>
        {traditions.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
              filter === t ? "bg-accent text-white" : "border border-border text-muted hover:bg-surface"
            }`}
          >
            {TRADITION_LABELS[t] || t} ({scriptures.filter((s) => s.tradition === t).length})
          </button>
        ))}
      </div>

      {/* Scripture grid grouped by tradition */}
      {Object.entries(grouped).map(([tradition, texts]) => (
        <div key={tradition} className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <div className={`h-3 w-3 rounded-full ${TRADITION_COLORS[tradition] || "bg-muted"}`} />
            <h2 className="text-lg font-semibold">{TRADITION_LABELS[tradition] || tradition}</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {texts.map((scripture) => (
              <Link
                key={scripture.slug}
                href={`/read/${scripture.slug}`}
                className="group rounded-xl border border-border p-5 hover:bg-surface hover:border-accent/30 transition-all"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-serif font-semibold text-base group-hover:text-accent transition-colors">
                    {scripture.scripture}
                  </h3>
                  <BookOpen className="h-4 w-4 text-muted group-hover:text-accent transition-colors" />
                </div>

                <div className="space-y-1 text-sm text-muted">
                  <p>{scripture.total_chapters} chapters &middot; {scripture.total_verses} verses</p>
                  <p>{scripture.translator}, {scripture.year}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      ))}

      {/* Stats footer */}
      <div className="text-center text-sm text-muted mt-8 pt-6 border-t border-border space-y-1">
        <p>
          {scriptures.length} texts with clean readable text shown above
        </p>
        <p className="text-xs text-muted/70">
          Additional classical texts (Mahabharata, Ramayana, Manu Smriti, Arthashastra, Agni Purana&hellip;)
          are indexed for AI search but excluded from reading view due to OCR quality.
        </p>
      </div>
    </div>
  );
}

export default function LibraryPage() {
  return (
    <Suspense fallback={<LibraryLoading />}>
      <LibraryPageContent />
    </Suspense>
  );
}
