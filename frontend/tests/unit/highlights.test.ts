import { describe, it, expect } from "vitest";
import { resolveHighlightSpans, normalizeWs } from "@/lib/highlights";

describe("normalizeWs", () => {
  it("collapses \\r\\n to a single space", () => {
    expect(normalizeWs("word1\r\nword2")).toBe("word1 word2");
  });

  it("collapses \\n to a single space", () => {
    expect(normalizeWs("word1\nword2")).toBe("word1 word2");
  });

  it("collapses tabs to a single space", () => {
    expect(normalizeWs("word1\tword2")).toBe("word1 word2");
  });

  it("collapses multiple spaces to one", () => {
    expect(normalizeWs("word1  word2")).toBe("word1 word2");
  });

  it("trims leading and trailing whitespace", () => {
    expect(normalizeWs("  hello world  ")).toBe("hello world");
  });

  it("leaves already-clean strings unchanged", () => {
    expect(normalizeWs("clean text here")).toBe("clean text here");
  });
});
import type { Highlight } from "@/lib/supabase-reader";

const makeHighlight = (overrides: Partial<Highlight> = {}): Highlight => ({
  id: "h1",
  slug: "gita",
  chapter: 1,
  verse: 1,
  selected_text: "test",
  selected_occurrence: 0,
  normalized_text_hash: null,
  color: "yellow",
  note: null,
  created_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

describe("resolveHighlightSpans", () => {
  it("returns empty array when no highlights", () => {
    expect(resolveHighlightSpans("some text", [])).toEqual([]);
  });

  it("returns empty array when text not found in paragraph", () => {
    const h = makeHighlight({ selected_text: "missing phrase" });
    expect(resolveHighlightSpans("some other text here", [h])).toEqual([]);
  });

  it("returns correct span for single highlight", () => {
    const h = makeHighlight({ id: "h1", selected_text: "wise" });
    const spans = resolveHighlightSpans("The wise man acts without attachment", [h]);
    expect(spans).toHaveLength(1);
    expect(spans[0].start).toBe(4);
    expect(spans[0].end).toBe(8);
    expect(spans[0].highlight).toBe(h);
  });

  it("returns multiple non-overlapping spans sorted by position", () => {
    const h1 = makeHighlight({ id: "h1", selected_text: "wise" });
    const h2 = makeHighlight({ id: "h2", selected_text: "acts", color: "green" });
    const spans = resolveHighlightSpans("The wise man acts without attachment", [h1, h2]);
    expect(spans).toHaveLength(2);
    expect(spans[0].start).toBeLessThan(spans[1].start);
    expect(spans[0].highlight.id).toBe("h1");
    expect(spans[1].highlight.id).toBe("h2");
  });

  it("drops overlapping spans — earlier position wins", () => {
    const h1 = makeHighlight({ id: "h1", selected_text: "wise man acts" });
    const h2 = makeHighlight({ id: "h2", selected_text: "man" });
    const spans = resolveHighlightSpans("The wise man acts without attachment", [h1, h2]);
    expect(spans).toHaveLength(1);
    expect(spans[0].highlight.id).toBe("h1"); // h1 starts at 4, h2 at 9 but inside h1
  });

  it("handles selected_occurrence=1 (second occurrence)", () => {
    const h = makeHighlight({ selected_text: "the", selected_occurrence: 1 });
    // "the" appears at index 0 and 16
    const text = "the wise man and the fool both act";
    const spans = resolveHighlightSpans(text, [h]);
    expect(spans).toHaveLength(1);
    expect(text.slice(spans[0].start, spans[0].end)).toBe("the");
    expect(spans[0].start).toBe(17); // second occurrence
  });

  it("returns empty when occurrence index exceeds actual count", () => {
    const h = makeHighlight({ selected_text: "the", selected_occurrence: 5 });
    // "the" only appears twice
    const spans = resolveHighlightSpans("the man and the woman", [h]);
    expect(spans).toHaveLength(0);
  });

  it("handles text at the very start of paragraph", () => {
    const h = makeHighlight({ selected_text: "Knowing" });
    const text = "Knowing yourself is the beginning of wisdom";
    const spans = resolveHighlightSpans(text, [h]);
    expect(spans[0].start).toBe(0);
    expect(spans[0].end).toBe(7);
  });

  it("handles text at the very end of paragraph", () => {
    const h = makeHighlight({ selected_text: "wisdom" });
    const text = "Knowing yourself is the beginning of wisdom";
    const spans = resolveHighlightSpans(text, [h]);
    expect(spans[0].end).toBe(text.length);
  });

  it("matches when selected_text has \\r\\n but paraText has space (cross-platform selection)", () => {
    // selected_text captured with Windows line ending, paraText is normalized
    const h = makeHighlight({ selected_text: "the wise\r\nman" });
    const text = "The path of the wise man leads to peace";
    const spans = resolveHighlightSpans(text, [h]);
    expect(spans).toHaveLength(1);
    expect(text.slice(spans[0].start, spans[0].end)).toBe("the wise man");
  });
});
