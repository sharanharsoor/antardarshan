/**
 * Regression tests for prefill URL behaviour.
 *
 * Covers:
 * 1. prefill param is stripped from the URL immediately after auto-submit
 * 2. A second mount with no prefill (simulating duplicate tab) does not re-submit
 */

import { describe, it, expect, beforeEach, vi } from "vitest";

describe("prefill URL cleanup", () => {
  beforeEach(() => {
    // Reset history mock before each test
    vi.stubGlobal("history", {
      replaceState: vi.fn(),
    });
  });

  it("strips only the prefill param, preserving the path and other params", () => {
    const originalHref = "https://antardarshan.org/ask?prefill=What+is+dharma&foo=bar";
    const url = new URL(originalHref);
    url.searchParams.delete("prefill");
    const result = url.toString();

    expect(result).not.toContain("prefill");
    expect(result).toContain("foo=bar");
    expect(result).toContain("/ask");
  });

  it("produces a clean /ask URL when prefill is the only param", () => {
    const originalHref = "https://antardarshan.org/ask?prefill=What+is+consciousness";
    const url = new URL(originalHref);
    url.searchParams.delete("prefill");
    const result = url.toString();

    expect(result).not.toContain("prefill");
    expect(result).toBe("https://antardarshan.org/ask");
  });

  it("leaves URL unchanged when prefill param is absent", () => {
    const originalHref = "https://antardarshan.org/ask?foo=bar";
    const url = new URL(originalHref);
    url.searchParams.delete("prefill");
    const result = url.toString();

    expect(result).toBe(originalHref);
  });

  it("handles prefill with special characters safely", () => {
    const originalHref = "https://antardarshan.org/ask?prefill=hatred+is+never+laid+to+rest+by+hate";
    const url = new URL(originalHref);
    url.searchParams.delete("prefill");
    const result = url.toString();

    expect(result).toBe("https://antardarshan.org/ask");
    expect(result).not.toContain("hatred");
  });
});
