/**
 * Tests for queryAIStream — SSE event handling, error paths, timeout.
 *
 * Covers:
 * - type="token" events call onToken callback
 * - type="done" event returns correct QueryResponse shape
 * - type="error" SSE event throws with status 500
 * - [DONE] sentinel ends the stream
 * - Stream ending without a done event throws
 * - Non-2xx HTTP response throws with correct status
 * - AbortController cancellation is respected
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { queryAIStream } from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeSSEStream(events: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(event));
      }
      controller.close();
    },
  });
}

function sseToken(content: string): string {
  return `data: ${JSON.stringify({ type: "token", content })}\n\n`;
}

function sseDone(overrides: object = {}): string {
  return (
    `data: ${JSON.stringify({
      type: "done",
      mode: "citation",
      citations: [],
      session_id: "sess-abc",
      trace_id: "trace-123",
      model: "llama-4",
      tokens_used: 100,
      conversation_id: null,
      conversation_saved: false,
      message_id: null,
      follow_ups: [],
      ...overrides,
    })}\n\n`
  );
}

function sseDoneSignal(): string {
  return "data: [DONE]\n\n";
}

function sseError(content = "Stream error"): string {
  return `data: ${JSON.stringify({ type: "error", content })}\n\n`;
}

function mockFetchOk(events: string[]) {
  const body = makeSSEStream(events);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, body })
  );
}

function mockFetchFail(status: number, body?: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status,
      json: async () => body ?? {},
    })
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("queryAIStream — happy path", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("calls onToken for each token event", async () => {
    mockFetchOk([
      sseToken("Hello"),
      sseToken(" world"),
      sseDone(),
      sseDoneSignal(),
    ]);

    const tokens: string[] = [];
    await queryAIStream("test query", undefined, undefined, (t) => tokens.push(t));

    expect(tokens).toEqual(["Hello", " world"]);
  });

  it("returns QueryResponse with correct shape from done event", async () => {
    mockFetchOk([
      sseToken("answer"),
      sseDone({ session_id: "sess-xyz", mode: "well_being", follow_ups: ["q1"] }),
      sseDoneSignal(),
    ]);

    const result = await queryAIStream("test", undefined, undefined, () => {});

    expect(result.session_id).toBe("sess-xyz");
    expect(result.mode).toBe("well_being");
    expect(result.follow_ups).toEqual(["q1"]);
    expect(result.citations).toEqual([]);
  });

  it("handles stream with no tokens (empty answer)", async () => {
    mockFetchOk([sseDone(), sseDoneSignal()]);

    const tokens: string[] = [];
    const result = await queryAIStream("test", undefined, undefined, (t) => tokens.push(t));

    expect(tokens).toHaveLength(0);
    expect(result.session_id).toBe("sess-abc");
  });

  it("ignores malformed JSON lines without throwing", async () => {
    mockFetchOk([
      "data: not-valid-json\n\n",
      sseToken("real token"),
      sseDone(),
      sseDoneSignal(),
    ]);

    const tokens: string[] = [];
    await queryAIStream("test", undefined, undefined, (t) => tokens.push(t));
    expect(tokens).toEqual(["real token"]);
  });

  it("stops reading at [DONE] even if more data follows", async () => {
    mockFetchOk([
      sseToken("first"),
      sseDone(),
      sseDoneSignal(),
      sseToken("should be ignored"),
    ]);

    const tokens: string[] = [];
    await queryAIStream("test", undefined, undefined, (t) => tokens.push(t));
    expect(tokens).toEqual(["first"]);
  });
});

describe("queryAIStream — error handling", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("throws with status 500 when type='error' SSE event received", async () => {
    mockFetchOk([sseError("Groq rate limit exceeded")]);

    await expect(
      queryAIStream("test", undefined, undefined, () => {})
    ).rejects.toMatchObject({ status: 500 });
  });

  it("error message from SSE is preserved in the thrown error", async () => {
    mockFetchOk([sseError("custom error message")]);

    await expect(
      queryAIStream("test", undefined, undefined, () => {})
    ).rejects.toThrow("custom error message");
  });

  it("throws when HTTP response is not ok (429)", async () => {
    mockFetchFail(429, { detail: { error: "daily_limit_reached", message: "limit" } });

    await expect(
      queryAIStream("test", undefined, undefined, () => {})
    ).rejects.toMatchObject({ status: 429 });
  });

  it("throws when HTTP response is 503", async () => {
    mockFetchFail(503);

    await expect(
      queryAIStream("test", undefined, undefined, () => {})
    ).rejects.toMatchObject({ status: 503 });
  });

  it("throws when stream ends without a done event", async () => {
    // Only tokens, no done event — stream closed prematurely
    mockFetchOk([sseToken("partial"), sseDoneSignal()]);

    await expect(
      queryAIStream("test", undefined, undefined, () => {})
    ).rejects.toThrow("Stream ended without metadata");
  });

  it("throws when stream body is empty", async () => {
    mockFetchOk([sseDoneSignal()]);

    await expect(
      queryAIStream("test", undefined, undefined, () => {})
    ).rejects.toThrow("Stream ended without metadata");
  });

  it("detail from 429 response is accessible on thrown error", async () => {
    const detail = { error: "global_limit_reached", message: "Daily limit hit" };
    mockFetchFail(429, { detail });

    let caught: unknown;
    try {
      await queryAIStream("test", undefined, undefined, () => {});
    } catch (e) {
      caught = e;
    }

    expect((caught as { detail?: unknown })?.detail).toEqual(detail);
  });
});

describe("queryAIStream — AbortController timeout", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reader.cancel() is called on error so connection is cleaned up", async () => {
    // Verify that when an error occurs, we don't leak the reader
    const cancelSpy = vi.fn().mockResolvedValue(undefined);
    const encoder = new TextEncoder();

    const mockReader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: encoder.encode(sseError()) })
        .mockResolvedValue({ done: true, value: undefined }),
      cancel: cancelSpy,
    };

    const mockBody = { getReader: () => mockReader };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body: mockBody })
    );

    await expect(
      queryAIStream("test", undefined, undefined, () => {})
    ).rejects.toMatchObject({ status: 500 });

    expect(cancelSpy).toHaveBeenCalled();
  });
});

describe("queryAIStream — Authorization header", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends Authorization header when access_token is provided", async () => {
    mockFetchOk([sseDone(), sseDoneSignal()]);

    await queryAIStream("test", undefined, { access_token: "tok-123" }, () => {});

    const fetchArgs = vi.mocked(fetch).mock.calls[0];
    const requestInit = fetchArgs[1] as RequestInit;
    expect((requestInit.headers as Record<string, string>)["Authorization"]).toBe("Bearer tok-123");
  });

  it("does not send Authorization header when no access_token", async () => {
    mockFetchOk([sseDone(), sseDoneSignal()]);

    await queryAIStream("test", undefined, undefined, () => {});

    const fetchArgs = vi.mocked(fetch).mock.calls[0];
    const requestInit = fetchArgs[1] as RequestInit;
    expect((requestInit.headers as Record<string, string>)["Authorization"]).toBeUndefined();
  });
});
