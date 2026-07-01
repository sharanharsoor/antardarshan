"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, BookOpen, Sparkles } from "lucide-react";
import { getCorpusStats, type CorpusStats } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DailyWisdom {
  text: string;
  scripture: string;
  slug: string;
  chapter: number;
  verse: number;
  translator: string;
  year: number;
  tradition_color: string;
}

const EXAMPLE_QUERIES = [
  "How do I stop being so angry?",
  "What is consciousness?",
  "How does Vedanta differ from Buddhism on the self?",
  "What happens after death?",
  "hatred is never laid to rest by hate",
  "What did Arjuna fear, and how did Krishna respond?",
];


export default function LandingPage() {
  const [query, setQuery] = useState("");
  const router = useRouter();
  const [dailyWisdom, setDailyWisdom] = useState<DailyWisdom | null>(null);
  const [corpusStats, setCorpusStats] = useState<CorpusStats | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/daily-wisdom`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => d && setDailyWisdom(d))
      .catch(() => {});
    getCorpusStats().then(setCorpusStats).catch(() => {});
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/ask?prefill=${encodeURIComponent(query.trim())}`);
    }
  };

  return (
    // Full viewport height, flex-col so content fills and centers vertically
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center px-4 py-4">
      <div className="w-full max-w-2xl">

        {/* Hero */}
        <div className="text-center mb-6">
          <h1 className="font-serif text-4xl md:text-5xl font-bold mb-2">AntarDarshan</h1>
          <p className="text-muted text-base">Inner Vision Through Ancient Wisdom</p>
        </div>

        {/* Search */}
        <form onSubmit={handleSubmit} className="relative mb-4">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask anything about Indian philosophy..."
            className="w-full rounded-xl border border-border bg-surface py-4 pl-12 pr-24 text-lg placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent"
            autoFocus
          />
          <button
            type="submit"
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-hover transition-colors"
          >
            Ask
          </button>
        </form>

        {/* Example queries — 2×2 grid, text-left chips; 1-col on mobile */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-6">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => router.push(`/ask?prefill=${encodeURIComponent(q)}`)}
              className="rounded-xl border border-border px-4 py-3 text-sm text-muted hover:bg-surface hover:text-foreground hover:border-accent/30 active:scale-[0.98] transition-all text-left leading-snug"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Daily wisdom */}
        <div className="relative overflow-hidden rounded-xl border border-accent/20 bg-gradient-to-br from-surface to-background px-6 py-5 mb-6">
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-accent/80 via-accent/40 to-transparent rounded-l-xl" />
          <div className="flex items-center gap-2 mb-2 ml-2">
            <Sparkles className="h-3.5 w-3.5 text-accent" />
            <span className="text-xs font-semibold uppercase tracking-wider text-accent">Daily Wisdom</span>
          </div>
          {dailyWisdom ? (
            <>
              <blockquote className="ml-2 text-base md:text-lg leading-relaxed font-serif italic text-foreground/90">
                &ldquo;{dailyWisdom.text}&rdquo;
              </blockquote>
              <div className="ml-2 mt-2 flex items-center gap-2">
                <div className={`h-1.5 w-1.5 rounded-full bg-[var(--color-${dailyWisdom.tradition_color})]`} />
                <Link
                  href={`/read/${dailyWisdom.slug}/${dailyWisdom.chapter}`}
                  className="text-xs text-muted hover:text-accent transition-colors hover:underline underline-offset-2"
                >
                  {dailyWisdom.scripture}, Ch.{dailyWisdom.chapter}.{dailyWisdom.verse} — {dailyWisdom.translator}
                </Link>
              </div>
            </>
          ) : (
            <>
              <blockquote className="ml-2 text-base md:text-lg leading-relaxed font-serif italic text-foreground/90">
                &ldquo;You are the one witness of everything, and are always totally free.&rdquo;
              </blockquote>
              <div className="ml-2 mt-2 flex items-center gap-2">
                <div className="h-1.5 w-1.5 rounded-full bg-[var(--color-vedanta)]" />
                <p className="text-xs text-muted">Ashtavakra Gita, Ch.1.7 — John Richards</p>
              </div>
            </>
          )}
        </div>

        {/* CTAs */}
        <div className="flex gap-3 justify-center">
          <Link
            href="/library"
            className="flex items-center gap-2 rounded-lg border border-border px-5 py-2.5 text-sm font-medium hover:bg-surface transition-colors"
          >
            <BookOpen className="h-4 w-4" />
            Browse Library
          </Link>
          <Link
            href="/ask"
            className="flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent-hover transition-colors"
          >
            Start a conversation
          </Link>
        </div>

        {/* Corpus stats — honest signal of depth */}
        <div className="text-center mt-5 space-y-0.5">
          {corpusStats ? (
            <>
              <p className="text-xs text-muted/70">
                <span className="text-foreground/80 font-medium">{corpusStats.total_texts} scriptures</span>
                {" · "}
                <span className="text-foreground/80 font-medium">{corpusStats.total_chunks.toLocaleString()} passages</span>
                {" "}indexed for AI search
              </p>
              <p className="text-[11px] text-muted/50">
                {corpusStats.readable_texts} with readable text in library
                {" · "}
                {corpusStats.rag_only_texts} classical texts indexed for search only
                {" · "}
                <a
                  href="https://github.com/sharanharsoor/antardarshan"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center hover:text-muted/80 transition-colors"
                  aria-label="Open source on GitHub"
                  title="Open source on GitHub"
                >
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                  </svg>
                </a>
              </p>
            </>
          ) : null}
        </div>

      </div>
    </div>
  );
}
