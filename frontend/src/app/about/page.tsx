export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12 space-y-12">

      {/* About */}
      <section>
        <h1 className="font-serif text-3xl font-bold mb-3">About AntarDarshan</h1>
        <p className="text-muted leading-relaxed">
          AntarDarshan (<span className="font-devanagari">अन्तर्दर्शन</span>) means <em>inner vision</em>.
          It is a free platform for exploring Indian philosophical traditions — Vedanta, Yoga, Buddhist,
          Jain, Sikh, and Sant/Bhakti — through citation-grounded AI answers and a curated reading library.
          Every AI response cites the original scripture passage so you can read the source yourself.
        </p>
      </section>

      {/* Philosophy */}
      <section>
        <h2 className="font-serif text-xl font-semibold mb-3">Our approach</h2>
        <ul className="space-y-2 text-sm text-muted list-disc list-inside">
          <li>AI answers are grounded in real scripture passages, not hallucinated summaries.</li>
          <li>44 scriptures indexed — 21 with clean readable text in the library, 23 classical texts indexed for search.</li>
          <li>Free forever. No ads. No paywalls.</li>
          <li>Privacy-first: your Q&amp;A content is not stored for analytics by default.</li>
        </ul>
      </section>

      {/* Wisdom Wall Guidelines — id="wisdom-guidelines" so the link anchors directly */}
      <section id="wisdom-guidelines">
        <h2 className="font-serif text-xl font-semibold mb-1">Wisdom Wall guidelines</h2>
        <p className="text-sm text-muted mb-4">
          The Wisdom Wall is a community space for sharing spiritual experiences and philosophical reflections.
          All posts are reviewed by AI before publishing.
        </p>
        <div className="rounded-xl border border-border bg-surface p-5 space-y-3 text-sm">
          <p className="font-medium text-foreground">Posts must:</p>
          <ul className="space-y-2 text-muted list-disc list-inside">
            <li>Relate to Indian philosophy, spiritual experiences, or personal growth through philosophical insight</li>
            <li>Be a genuine personal reflection, insight, or philosophical thought</li>
            <li>Not contain spam, advertisements, services, or promotional content</li>
            <li>Not contain political opinions or divisive content</li>
            <li>Not contain harmful, offensive, or inappropriate material</li>
            <li>Not contain personal attacks or hate speech</li>
            <li>If contact info is included, it must be for spiritual connection only — no business solicitation</li>
          </ul>

          <div className="border-t border-border/40 pt-3 text-xs text-muted/70 space-y-1">
            <p><strong>Limits:</strong> 5 posts per day · 5 submission attempts per day (approved or rejected both count)</p>
            <p><strong>Contact info:</strong> Hidden automatically after 15 days for privacy</p>
            <p><strong>Auto-removal:</strong> Posts with &gt;40% downvotes and at least 5 votes are removed after 7 days</p>
            <p><strong>Appeals:</strong> Contact us via the email in the footer if you believe a post was incorrectly rejected</p>
          </div>
        </div>
      </section>

      {/* Privacy */}
      <section>
        <h2 className="font-serif text-xl font-semibold mb-3">Privacy</h2>
        <div className="text-sm text-muted space-y-2">
          <p>Your Q&amp;A questions and answers are <strong>not stored for analytics</strong> by default. You can enable content logging to help improve the service using the 🔓 toggle in the Ask page.</p>
          <p>When you delete a conversation, all messages are permanently deleted. Query activity metadata (mode, model, timestamp — no question text) is retained for quota tracking and can be cleared from your <a href="/profile#conversations" className="text-accent hover:underline">profile page</a>.</p>
          <p>Wisdom Wall contact info you provide is hidden from public view after 15 days and deleted along with your post when you delete it.</p>
        </div>
      </section>

    </div>
  );
}
