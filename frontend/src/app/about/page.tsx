"use client";
import { useEffect, useState } from "react";

function AboutContent() {
  const [stats, setStats] = useState<{ total_texts?: number; readable_texts?: number; rag_only_texts?: number } | null>(null);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/stats`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => d && setStats(d))
      .catch(() => {});
  }, []);

  const total = stats?.total_texts ?? 54;
  const readable = stats?.readable_texts ?? 32;
  const ragOnly = stats?.rag_only_texts ?? 22;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 space-y-10">

      <section>
        <h1 className="font-serif text-3xl font-bold mb-4">About AntarDarshan</h1>
        <p className="text-muted leading-relaxed">
          AntarDarshan (<span className="font-devanagari">अन्तर्दर्शन</span>) means <em>inner vision</em>.
          It started as a simple question: what if you could have a conversation with the wisdom of the Gita,
          the Upanishads, the Dhammapada, and actually see where the answer comes from?
        </p>
        <p className="text-muted leading-relaxed mt-3">
          Every answer cites the original passage so you can read it in context, question it, and go deeper.
          No paraphrasing without proof. No wisdom without a source.
        </p>
      </section>

      <section>
        <h2 className="font-serif text-xl font-semibold mb-3">What&apos;s inside</h2>
        <p className="text-sm text-muted leading-relaxed">
          {total} scriptures indexed across Vedanta, Yoga, Buddhist, Jain, and Sant/Bhakti traditions.{" "}
          {readable} have clean readable text you can browse like a book.{" "}
          The remaining {ragOnly} are older scanned texts — they power the AI search but aren&apos;t formatted for direct reading.
        </p>
        <p className="text-sm text-muted leading-relaxed mt-2">
          There&apos;s no advertising here. Your questions aren&apos;t stored or used for training by default.
          If you want to help improve the AI&apos;s quality, you can opt in to content logging from the Ask page.
        </p>
      </section>

      <section id="wisdom-guidelines">
        <h2 className="font-serif text-xl font-semibold mb-2">Wisdom Wall</h2>
        <p className="text-sm text-muted mb-4 leading-relaxed">
          The Wisdom Wall is where people share their own reflections: personal experiences, insights, or
          thoughts connected to Indian philosophy. Every post is reviewed by AI before it goes live.
        </p>
        <div className="rounded-xl border border-border bg-surface p-5 text-sm space-y-3">
          <p className="font-medium text-foreground">Posts should be about:</p>
          <ul className="space-y-1.5 text-muted list-disc list-inside">
            <li>Genuine personal reflections on Indian philosophy or spiritual life</li>
            <li>Experiences, insights, or questions rooted in that tradition</li>
          </ul>
          <p className="font-medium text-foreground mt-2">Posts will be rejected if they contain:</p>
          <ul className="space-y-1.5 text-muted list-disc list-inside">
            <li>Spam, promotion, or anything you&apos;re selling</li>
            <li>Political opinions or divisive content</li>
            <li>Personal attacks or harmful material</li>
          </ul>
          <div className="border-t border-border/40 pt-3 text-xs text-muted/70 space-y-1">
            <p>5 posts per day · 5 submission attempts per day</p>
            <p>Contact info (if shared) is hidden after 15 days automatically</p>
            <p>Posts with many downvotes are removed after a week</p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="font-serif text-xl font-semibold mb-3">Open source</h2>
        <p className="text-sm text-muted leading-relaxed">
          The whole codebase (RAG pipeline, scripture parsers, reading interface) is on GitHub.
          If you want to contribute a new scripture, fix something, or just see how it works, it&apos;s all there.
        </p>
        <a
          href="https://github.com/sharanharsoor/antardarshan"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-2 text-sm text-accent hover:underline"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
          </svg>
          github.com/sharanharsoor/antardarshan
        </a>
      </section>

      <section>
        <h2 className="font-serif text-xl font-semibold mb-3">Your data</h2>
        <div className="text-sm text-muted space-y-2 leading-relaxed">
          <p>
            Your questions and answers aren&apos;t stored for analytics by default. You stay in control. There&apos;s
            a toggle in the Ask page if you want to opt in.
          </p>
          <p>
            When you delete a conversation, it&apos;s gone permanently. The only thing that stays is a tiny log
            of activity (no question text, just timestamps and model info) used for daily query limits.
            You can clear that too from your <a href="/profile#conversations" className="text-accent hover:underline">profile page</a>.
          </p>
          <p>
            Contact info you share on the Wisdom Wall is hidden from public view after 15 days and deleted
            when you delete your post.
          </p>
        </div>
      </section>

    </div>
  );
}

export default function AboutPage() {
  return <AboutContent />;
}
