"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, BookOpen, Sparkles, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { getLibrary, getCorpusStats, type Scripture, type CorpusStats } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { ConversationSidebar } from "@/components/ask/ConversationSidebar";

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
  "What does the Gita say about duty?",
  "I'm going through a difficult time",
  "How does Vedanta differ from Buddhism on the self?",
];

// Must match TRADITION_LABELS in library/page.tsx exactly
const TRADITION_CONFIG = [
  { key: "hindu_vedanta", name: "Vedanta",    colorClass: "bg-[var(--color-vedanta)]" },
  { key: "buddhist",      name: "Buddhist",   colorClass: "bg-[var(--color-buddhist)]" },
  { key: "hindu_yoga",    name: "Yoga",       colorClass: "bg-[var(--color-yoga)]" },
  { key: "sant_bhakti",   name: "Sant/Bhakti",colorClass: "bg-[var(--color-bhakti)]" },
];

function buildTraditionCounts(scriptures: Scripture[]) {
  const counts: Record<string, number> = {};
  for (const s of scriptures) {
    counts[s.tradition] = (counts[s.tradition] ?? 0) + 1;
  }
  return TRADITION_CONFIG.map((t) => ({
    ...t,
    count: counts[t.key] ? `${counts[t.key]} text${counts[t.key] > 1 ? "s" : ""}` : "coming soon",
  }));
}

export default function LandingPage() {
  const [query, setQuery] = useState("");
  const router = useRouter();
  const [traditions, setTraditions] = useState(
    TRADITION_CONFIG.map((t) => ({ ...t, count: "…" }))
  );
  const [corpusStats, setCorpusStats] = useState<CorpusStats | null>(null);
  const [dailyWisdom, setDailyWisdom] = useState<DailyWisdom | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    getLibrary()
      .then((scriptures) => setTraditions(buildTraditionCounts(scriptures)))
      .catch(() => {});
    getCorpusStats()
      .then(setCorpusStats)
      .catch(() => {});

    fetch(`${API_BASE}/api/daily-wisdom`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => d && setDailyWisdom(d))
      .catch(() => {});

    // Check if logged in to show sidebar
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setIsLoggedIn(!!data.user);
    });
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/ask?prefill=${encodeURIComponent(query.trim())}`);
    }
  };

  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">

      {/* Reuse the same ConversationSidebar as the Ask page — consistent UX */}
      {isLoggedIn && sidebarOpen && (
        <div className="hidden md:block">
          <ConversationSidebar
            onNewChat={() => {
              // Clear sessionStorage so AskPageCore starts with a blank slate,
              // not the restored previous conversation
              sessionStorage.removeItem("antardarshan_messages");
              sessionStorage.removeItem("antardarshan_session_id");
              router.push("/ask");
            }}
          />
        </div>
      )}


      {/* Main content — centered, scrollable */}
      <div className="flex-1 overflow-y-auto">

      {/* Sidebar toggle — in the flow at the top, not absolute positioned */}
      {isLoggedIn && (
        <div className="hidden md:flex items-center px-3 pt-2">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className="rounded-md p-1.5 text-muted hover:text-foreground hover:bg-surface transition-colors"
            title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </button>
        </div>
      )}

      <div className="mx-auto max-w-3xl px-4 py-10">

      {/* Hero */}
      <div className="text-center mb-12">
        <h1 className="font-serif text-4xl md:text-5xl font-bold mb-3">
          AntarDarshan
        </h1>
        <p className="text-muted text-lg">Inner Vision Through Ancient Wisdom</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSubmit} className="relative mb-8">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask anything about Indian philosophy..."
          className="w-full rounded-xl border border-border bg-surface py-4 pl-12 pr-24 text-lg placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <button
          type="submit"
          className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-hover hover:shadow-[0_0_16px_rgba(196,133,76,0.3)] transition-all duration-200"
        >
          Ask
        </button>
      </form>

      {/* Example queries */}
      <div className="mb-12 flex flex-wrap gap-2 justify-center">
        {EXAMPLE_QUERIES.map((q) => (
          <button
            key={q}
            onClick={() => router.push(`/ask?prefill=${encodeURIComponent(q)}`)}
            className="rounded-full border border-border px-4 py-2 text-sm text-muted hover:bg-surface hover:text-foreground hover:border-accent/30 active:scale-[0.97] transition-all duration-150"
          >
            &ldquo;{q}&rdquo;
          </button>
        ))}
      </div>

      {/* Tradition cards — clickable, each tinted with its tradition color */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-12">
        {traditions.map((t) => (
          <Link
            key={t.name}
            href={`/library?filter=${t.key}`}
            className="group relative overflow-hidden rounded-lg border border-border p-4 text-center hover:border-accent/40 transition-all duration-200"
          >
            <div className={`absolute inset-0 ${t.colorClass} opacity-[0.04] group-hover:opacity-[0.08] transition-opacity`} />
            <div className="relative">
              <div className={`mx-auto mb-2 h-2.5 w-10 rounded-full ${t.colorClass} opacity-80`} />
              <p className="font-medium text-sm">{t.name}</p>
              <p className="text-xs text-muted mt-0.5">{t.count}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Daily wisdom — premium visual weight, the unique identity piece */}
      <div className="relative overflow-hidden rounded-2xl border border-accent/20 bg-gradient-to-br from-surface to-background p-8 mb-10">
        {/* Subtle saffron accent line */}
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-accent/80 via-accent/40 to-transparent rounded-l-2xl" />

        <div className="flex items-center gap-2 mb-4 ml-3">
          <Sparkles className="h-4 w-4 text-accent" />
          <span className="text-xs font-semibold uppercase tracking-wider text-accent">Daily Wisdom</span>
        </div>

        {dailyWisdom ? (
          <>
            <blockquote className="ml-3 text-xl md:text-2xl leading-relaxed font-serif italic text-foreground/90">
              &ldquo;{dailyWisdom.text}&rdquo;
            </blockquote>
            <div className="ml-3 mt-5 flex items-center gap-2">
              <div className={`h-1.5 w-1.5 rounded-full bg-[var(--color-${dailyWisdom.tradition_color})]`} />
              <Link
                href={`/read/${dailyWisdom.slug}/${dailyWisdom.chapter}`}
                className="text-sm text-muted hover:text-accent transition-colors underline-offset-2 hover:underline"
                title="Read this chapter in the library"
              >
                {dailyWisdom.scripture}, Ch.{dailyWisdom.chapter}, Verse {dailyWisdom.verse} — {dailyWisdom.translator}, {dailyWisdom.year}
              </Link>
            </div>
          </>
        ) : (
          <>
            <blockquote className="ml-3 text-xl md:text-2xl leading-relaxed font-serif italic text-foreground/90">
              &ldquo;You are the one witness of everything, and are always totally free.
              The cause of your bondage is that you see the witness as something other than this.&rdquo;
            </blockquote>
            <div className="ml-3 mt-5 flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-[var(--color-vedanta)]" />
              <p className="text-sm text-muted">Ashtavakra Gita, Ch.1, Verse 7 — John Richards, 1994</p>
            </div>
          </>
        )}
      </div>

      {/* CTAs */}
      <div className="flex flex-col sm:flex-row gap-3 justify-center mb-8">
        <Link
          href="/library"
          className="flex items-center justify-center gap-2 rounded-lg border border-border px-6 py-3 text-sm font-medium hover:bg-surface transition-colors"
        >
          <BookOpen className="h-4 w-4" />
          Browse Library
        </Link>
        <Link
          href="/ask"
          className="flex items-center justify-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-medium text-white hover:bg-accent-hover transition-colors"
        >
          Start Asking
        </Link>
      </div>

      {/* Footer tagline */}
      <div className="text-center text-sm text-muted space-y-1">
        <p>Free forever. No ads.</p>
        {corpusStats && (
          <>
            <p>
              <span className="text-foreground font-medium">{corpusStats.total_texts} scriptures</span>
              {" · "}
              <span className="text-foreground font-medium">{corpusStats.total_chunks.toLocaleString()} passages</span>
              {" "}indexed for AI search
            </p>
            <p className="text-xs text-muted/70">
              {corpusStats.readable_texts} with readable text in library
              {" · "}
              {corpusStats.rag_only_texts} classical texts indexed for search only
            </p>
          </>
        )}
      </div>

      </div>
      </div>
    </div>
  );
}
