/**
 * API client for AntarDarshan backend.
 * All calls go to the FastAPI backend on Hetzner VPS (or localhost in dev).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Citation {
  scripture: string;
  chapter: number;
  verse: number;
  translator: string;
  readable: boolean;  // true = in reading library; false = RAG-only (OCR, not navigable)
}

export interface Scripture {
  scripture: string;
  slug: string;
  tradition: string;
  translator: string;
  year: number;
  total_chapters: number;
  total_verses: number;
  license_tier: string;
  readable?: boolean;  // true = clean text in reading library; false = OCR source
}

export interface ChapterSummary {
  chapter: number;
  name?: string;
  verse_count: number;
  verse_type: string;
}

export interface Verse {
  text: string;
  scripture: string;
  chapter: number;
  verse: number;
  translator: string;
  tradition: string;
  themes: string[];
  speaker?: string;
  chapter_name?: string;
  verse_type: string;
  chunk_type: string;
}

export interface QueryResponse {
  answer: string;
  mode: string;
  citations: Citation[];
  session_id: string;
  latency_ms: number;
  trace_id?: string | null;
  model?: string | null;
  tokens_used?: number | null;
  conversation_id?: string | null;
  conversation_saved?: boolean;
  message_id?: string | null;
}

export interface QuotaStatus {
  status: "available" | "limited" | "exhausted";
  queries_today: number;
  daily_limit: number;
}

// --- API Functions ---

/**
 * Streaming version of queryAI.
 * Calls onToken for each incoming text token (for live display).
 * Returns the final QueryResponse metadata after the stream completes.
 */
export async function queryAIStream(
  query: string,
  sessionId: string | undefined,
  extras: { conversation_id?: string; access_token?: string; log_content?: boolean } | undefined,
  onToken: (token: string) => void,
): Promise<QueryResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (extras?.access_token) headers["Authorization"] = `Bearer ${extras.access_token}`;

  const res = await fetch(`${API_BASE}/api/query/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query,
      session_id: sessionId,
      top_k: 5,
      conversation_id: extras?.conversation_id,
      log_content: extras?.log_content ?? false,
    }),
  });

  if (!res.ok) {
    let detail: unknown = undefined;
    try { detail = (await res.json()).detail; } catch { /* ignore */ }
    throw Object.assign(new Error(`Stream failed: ${res.status}`), { status: res.status, detail });
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let metadata: QueryResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") break;

      try {
        const event = JSON.parse(payload);
        if (event.type === "token") {
          onToken(event.content);
        } else if (event.type === "done") {
          metadata = {
            answer: "",  // answer is accumulated via onToken
            mode: event.mode,
            citations: event.citations,
            session_id: event.session_id,
            latency_ms: 0,  // not tracked in streaming (tokens arrive continuously)
            trace_id: event.trace_id,
            model: event.model,
            tokens_used: event.tokens_used,
            conversation_id: event.conversation_id,
            conversation_saved: event.conversation_saved,
            message_id: event.message_id,
          };
        }
      } catch { /* malformed JSON line, skip */ }
    }
  }

  if (!metadata) throw new Error("Stream ended without metadata");
  return metadata;
}

export async function queryAI(
  query: string,
  sessionId?: string,
  extras?: { conversation_id?: string; access_token?: string }
): Promise<QueryResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (extras?.access_token) {
    headers["Authorization"] = `Bearer ${extras.access_token}`;
  }
  const res = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query,
      session_id: sessionId,
      top_k: 5,
      conversation_id: extras?.conversation_id,
      // user_id is derived server-side from the JWT — never sent from client
    }),
  });
  if (!res.ok) {
    let detail: unknown = undefined;
    try { detail = (await res.json()).detail; } catch { /* ignore */ }
    const err = Object.assign(new Error(`Query failed: ${res.status}`), { status: res.status, detail });
    throw err;
  }
  return res.json();
}

export async function getLibrary(): Promise<Scripture[]> {
  const res = await fetch(`${API_BASE}/api/library`);
  if (!res.ok) throw new Error(`Library fetch failed: ${res.status}`);
  const data = await res.json();
  return data.scriptures;
}

export interface CorpusStats {
  total_texts: number;
  readable_texts: number;
  rag_only_texts: number;
  total_chunks: number;
  readable_chunks: number;
}

export async function getCorpusStats(): Promise<CorpusStats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error(`Stats fetch failed: ${res.status}`);
  return res.json();
}

export async function getScriptureDetail(slug: string): Promise<{ scripture: Scripture; chapters: ChapterSummary[] }> {
  const res = await fetch(`${API_BASE}/api/library/${encodeURIComponent(slug)}`);
  if (!res.ok) throw new Error(`Scripture detail failed: ${res.status}`);
  return res.json();
}

export async function getChapter(slug: string, chapter: number): Promise<{ scripture: string; chapter: number; verses: Verse[] }> {
  const res = await fetch(`${API_BASE}/api/library/${encodeURIComponent(slug)}/${chapter}`);
  if (!res.ok) throw new Error(`Chapter fetch failed: ${res.status}`);
  return res.json();
}

export async function getVerseDetail(slug: string, chapter: number, verse: number): Promise<{ verse: Verse; context_verses: Verse[] }> {
  const res = await fetch(`${API_BASE}/api/library/${encodeURIComponent(slug)}/${chapter}/${verse}`);
  if (!res.ok) throw new Error(`Verse detail failed: ${res.status}`);
  return res.json();
}

export async function explainVerse(scripture: string, chapter: number, verse: number): Promise<{ verse: Verse; explanation: string; context_verses: Verse[] }> {
  const res = await fetch(`${API_BASE}/api/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scripture, chapter, verse }),
  });
  if (!res.ok) throw new Error(`Explain failed: ${res.status}`);
  return res.json();
}

export async function getQuotaStatus(): Promise<QuotaStatus> {
  const res = await fetch(`${API_BASE}/api/quota-status`);
  if (!res.ok) throw new Error(`Quota status failed: ${res.status}`);
  return res.json();
}

/** Derive URL-safe slug from scripture name — must match backend's _make_slug() exactly. */
export function scriptureToSlug(scripture: string): string {
  return scripture.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "");
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/session/${sessionId}`, { method: "DELETE" });
}

// Bookmarks are managed directly via Supabase client in lib/supabase-reader.ts
// No backend /api/bookmarks/* endpoints exist — these functions were removed.
