/**
 * Highlight rendering utilities for the reading page.
 * Extracted to a separate module so they can be unit-tested independently.
 */
import type { Highlight } from "./supabase-reader";

export const HIGHLIGHT_BG: Record<Highlight["color"], string> = {
  yellow: "bg-yellow-200/80 dark:bg-yellow-500/35",
  green:  "bg-green-200/80 dark:bg-green-500/35",
  blue:   "bg-blue-200/80 dark:bg-blue-500/35",
  pink:   "bg-pink-200/80 dark:bg-pink-500/35",
};

export type HighlightSpan = {
  start: number;
  end: number;
  highlight: Highlight;
};

/** Collapse all whitespace variants (\r\n, \t, multiple spaces) to a single space. */
export function normalizeWs(s: string): string {
  return s.replace(/[\r\n\t]+/g, " ").replace(/  +/g, " ").trim();
}

/**
 * Given a paragraph text string and the highlights for the containing verse,
 * returns the ordered list of non-overlapping spans to render.
 *
 * CONTRACT: `paraText` must already be whitespace-normalized (call
 * `normalizeWs(paraText)` before passing in). The returned span positions are
 * relative to this normalized string — the caller must use the SAME normalized
 * string for slicing. `renderParaWithHighlights` does this correctly.
 *
 * Only `selected_text` is normalized internally (handles \r\n from browser
 * selections on Windows). `paraText` is used as-is to keep positions stable.
 *
 * Rules:
 * - For each highlight, find the Nth occurrence of normalized selected_text
 *   where N = selected_occurrence.
 * - Sort by start position.
 * - Overlapping spans are dropped (first-by-position wins).
 */
export function resolveHighlightSpans(
  paraText: string,
  verseHighlights: Highlight[],
): HighlightSpan[] {
  const raw: HighlightSpan[] = [];

  for (const h of verseHighlights) {
    // Only normalize selected_text — paraText is pre-normalized by the caller
    const normalizedSelected = normalizeWs(h.selected_text);
    if (!normalizedSelected) continue;
    let found = 0;
    let idx = 0;
    while ((idx = paraText.indexOf(normalizedSelected, idx)) !== -1) {
      if (found === h.selected_occurrence) {
        raw.push({ start: idx, end: idx + normalizedSelected.length, highlight: h });
        break;
      }
      found++;
      idx++;
    }
  }

  if (raw.length === 0) return [];

  raw.sort((a, b) => a.start - b.start);

  // Drop overlapping spans
  const resolved: HighlightSpan[] = [];
  let pos = 0;
  for (const span of raw) {
    if (span.start >= pos) {
      resolved.push(span);
      pos = span.end;
    }
  }
  return resolved;
}
