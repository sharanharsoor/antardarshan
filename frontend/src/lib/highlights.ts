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

/**
 * Given a paragraph text string and the highlights for the containing verse,
 * returns the ordered list of non-overlapping spans to render.
 *
 * Rules:
 * - For each highlight, find the Nth occurrence of selected_text in paraText
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
    let found = 0;
    let idx = 0;
    while ((idx = paraText.indexOf(h.selected_text, idx)) !== -1) {
      if (found === h.selected_occurrence) {
        raw.push({ start: idx, end: idx + h.selected_text.length, highlight: h });
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
