import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { scriptureToSlug, clearApiCache, getLibrary, getCorpusStats } from "@/lib/api";

// ── scriptureToSlug ───────────────────────────────────────────────────────────

describe("scriptureToSlug", () => {
  it("lowercases and replaces spaces with hyphens", () => {
    expect(scriptureToSlug("Bhagavad Gita")).toBe("bhagavad-gita");
  });

  it("removes special characters", () => {
    expect(scriptureToSlug("Yoga Sutras (Patanjali)")).toBe("yoga-sutras-patanjali");
  });

  it("collapses multiple hyphens", () => {
    expect(scriptureToSlug("Chandogya  Upanishad")).toBe("chandogya-upanishad");
  });

  it("handles already-slug strings unchanged", () => {
    expect(scriptureToSlug("dhammapada")).toBe("dhammapada");
  });
});

// ── API cache ─────────────────────────────────────────────────────────────────

describe("getLibrary cache", () => {
  const mockScriptures = [
    { slug: "gita", name: "Bhagavad Gita", tradition: "hindu_vedanta", readable: true },
  ];

  beforeEach(() => {
    clearApiCache();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ scriptures: mockScriptures }),
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("makes exactly one network request on first call", async () => {
    await getLibrary();
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });

  it("returns cached result on second call — no extra network request", async () => {
    await getLibrary();
    await getLibrary();
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });

  it("makes a new request after cache is cleared", async () => {
    await getLibrary();
    clearApiCache();
    await getLibrary();
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2);
  });

  it("returns the correct scripture data", async () => {
    const result = await getLibrary();
    expect(result).toEqual(mockScriptures);
  });

  it("throws when backend returns non-ok status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503 })
    );
    await expect(getLibrary()).rejects.toThrow("503");
  });
});

describe("getCorpusStats cache", () => {
  const mockStats = {
    total_texts: 44, readable_texts: 21, rag_only_texts: 23,
    total_chunks: 19278, readable_chunks: 8500,
  };

  beforeEach(() => {
    clearApiCache();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => mockStats })
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("caches stats and avoids duplicate requests", async () => {
    await getCorpusStats();
    await getCorpusStats();
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });
});
