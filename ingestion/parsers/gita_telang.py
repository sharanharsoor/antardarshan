"""
Parser for K.T. Telang's SBE Vol. 8 translation (1882, 2nd ed. 1898).

The file bhagavad_gita_telang_sbe08.txt contains THREE texts:
  1. Bhagavad Gita (18 chapters, ~700 shlokas) — the primary text
  2. Sanatsugatiya (philosophical dialogue on brahman and immortality)
  3. Anugita (Krishna's further teachings to Arjuna after the war)

This parser extracts all three as separate scripture entries.

Telang's Gita uses verse-by-verse numbered prose, unlike Arnold's poetic stanzas.
This gives proper chapter.verse granularity matching the original Sanskrit numbering.

OCR quality note: the text has OCR artifacts (diacritics rendered as special chars,
occasional mid-word line breaks, page numbers embedded). Pre-processing normalizes these.
"""

import re
from pathlib import Path

from ingestion.schema import ScriptureChunk

SOURCE_URL = "https://sacred-texts.com/hin/sbe08/index.htm"
SOURCE_URL_IA = "https://archive.org/details/sacredbooksofeas08mull"

# Marker patterns for the three texts
GITA_CHAPTER_PATTERN = re.compile(
    # Match "CHAPTER I." / "CHAPTER II." as standalone headers (2+ blank lines before)
    # Uses negative lookbehind for alphanumeric to exclude inline refs like "chapter VI, stanza"
    r"\n{2,}\s*CHAPTER\s+([IVXLC]+)\.?\s*\n",
    re.IGNORECASE,
)
# Some OCR sections encode chapter boundaries as inline references:
# "CHAPTER III, 13. 53"
GITA_INLINE_CHAPTER_PATTERN = re.compile(
    r"\n{1,}\s*CHAPTER\s+([IVXLC]+)\s*,\s*\d+\.\s*\d+\s*\n",
    re.IGNORECASE,
)

SANATSUJATIYA_MARKER = re.compile(r"SANATSUGAT[AI]YA", re.IGNORECASE)
ANUGITA_MARKER = re.compile(r"THE\s+ANUGITA", re.IGNORECASE)

ROMAN_MAP = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
    "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18,
}
EXPECTED_GITA_CHAPTERS = tuple(range(1, 19))

THEME_KEYWORDS = {
    "karma": ["action", "act", "deed", "work", "duty", "perform"],
    "dharma": ["dharma", "duty", "righteousness", "law"],
    "devotion": ["devot", "worship", "love", "bhakti", "adore"],
    "knowledge": ["know", "wisdom", "truth", "science", "understand"],
    "yoga": ["yoga", "meditat", "concentrat", "discipline", "union"],
    "detachment": ["detach", "renounc", "abandon", "desire", "fruit"],
    "self": ["self", "soul", "atman", "spirit", "being"],
    "brahman": ["brahman", "brahma", "absolute", "supreme", "eternal"],
}


def _ocr_clean(text: str) -> str:
    """Clean OCR artifacts from IA djvu scan."""
    # Remove embedded page numbers (standalone digits on their own line)
    text = re.sub(r"\n\s*\d{1,4}\s*\n", "\n", text)
    # Fix mid-word line breaks common in OCR: "admi-\nnistered" → "administered"
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def _detect_themes(text: str) -> list[str]:
    t = text.lower()
    return [theme for theme, kws in THEME_KEYWORDS.items() if any(kw in t for kw in kws)][:4]


def _roman_to_int(roman: str) -> int | None:
    return ROMAN_MAP.get(roman.upper())


def _collect_chapter_markers(text: str) -> list[tuple[int, int, int]]:
    """
    Collect candidate chapter markers as (start, end, chapter_num).
    Includes both standalone and inline OCR chapter formats.
    """
    markers: list[tuple[int, int, int]] = []
    for pattern in (GITA_CHAPTER_PATTERN, GITA_INLINE_CHAPTER_PATTERN):
        for match in pattern.finditer(text):
            chapter_num = _roman_to_int(match.group(1))
            if chapter_num is None:
                continue
            markers.append((match.start(), match.end(), chapter_num))
    markers.sort(key=lambda item: item[0])
    return markers


def _select_ordered_gita_chapters(
    markers: list[tuple[int, int, int]],
    max_span_chars: int = 260000,
) -> list[tuple[int, int, int]]:
    """
    Choose the best ascending I→XVIII chapter sequence from noisy OCR markers.
    """
    if not markers:
        return []

    by_chapter: dict[int, list[tuple[int, int, int]]] = {}
    for marker in markers:
        by_chapter.setdefault(marker[2], []).append(marker)

    first_chapter_markers = by_chapter.get(1, [])
    if not first_chapter_markers:
        return []

    best_sequence: list[tuple[int, int, int]] = []
    for first in first_chapter_markers[:5]:
        sequence = [first]
        first_pos = first[0]
        prev_pos = first_pos

        for chapter_num in EXPECTED_GITA_CHAPTERS[1:]:
            candidates = by_chapter.get(chapter_num, [])
            next_marker = next(
                (
                    marker
                    for marker in candidates
                    if marker[0] > prev_pos and marker[0] - first_pos <= max_span_chars
                ),
                None,
            )
            if next_marker is None:
                break
            sequence.append(next_marker)
            prev_pos = next_marker[0]

        if len(sequence) > len(best_sequence):
            best_sequence = sequence
        if len(best_sequence) == 18:
            break

    return best_sequence


def _find_text_boundaries(text: str) -> tuple[int, int, int]:
    """
    Find where each of the three texts starts.
    Returns (gita_start, sanat_start, anugita_start).
    sanat_start or anugita_start = -1 if not found.

    Key constraint: all positions must be in ascending order.
    The Sanatsugatiya and Anugita appear in the title page as well as in the
    actual content — we search for body content only, well past the title section.
    """
    chapter_markers = _select_ordered_gita_chapters(_collect_chapter_markers(text))
    if chapter_markers:
        gita_start = chapter_markers[0][0]
        gita_tail = chapter_markers[-1][0]
    else:
        # ponytail: conservative fallback when OCR chapter markers fail;
        # ceiling is weaker boundaries, upgrade path is explicit marker map.
        gita_start = 0
        gita_tail = 0

    # Sanatsugatiya comes after the Gita chapter run
    sanat_search_start = max(gita_tail + 1, gita_start + 20000)
    sanat_match = SANATSUJATIYA_MARKER.search(text, sanat_search_start)
    sanat_start = sanat_match.start() if sanat_match else -1

    # Anugita comes after Sanatsugatiya
    anugita_search_start = sanat_start + 1 if sanat_start > 0 else sanat_search_start
    anugita_match = ANUGITA_MARKER.search(text, anugita_search_start)
    anugita_start = anugita_match.start() if anugita_match else -1

    # Enforce ascending positions (critical for safe slicing)
    if sanat_start != -1 and sanat_start <= gita_start:
        sanat_start = -1
    if anugita_start != -1:
        if sanat_start != -1 and anugita_start <= sanat_start:
            retry = ANUGITA_MARKER.search(text, sanat_start + 1)
            anugita_start = retry.start() if retry else -1
        if anugita_start != -1 and anugita_start <= gita_start:
            anugita_start = -1

    return gita_start, sanat_start, anugita_start


def _parse_gita_chapters(gita_text: str) -> list[ScriptureChunk]:
    """Parse Bhagavad Gita section into chapter-level chunks."""
    chunks: list[ScriptureChunk] = []

    chapter_markers = _select_ordered_gita_chapters(_collect_chapter_markers(gita_text))
    if not chapter_markers:
        # Fallback: treat whole text as one chunk
        cleaned = _ocr_clean(gita_text)
        if len(cleaned) > 100:
            chunks.append(ScriptureChunk(
                text=cleaned[:3000],
                scripture="Bhagavad Gita",
                tradition="hindu_vedanta",
                chapter=1, verse=1,
                translator="K.T. Telang",
                year=1882, language="en",
                license_tier="A",
                source_url=SOURCE_URL_IA,
                chunk_type="prose", verse_type="verse",
                themes=_detect_themes(cleaned),
            ))
        return chunks

    for i, marker in enumerate(chapter_markers):
        start = marker[1]
        chapter_num = marker[2]
        end = chapter_markers[i + 1][0] if i + 1 < len(chapter_markers) else len(gita_text)
        chapter_text = _ocr_clean(gita_text[start:end])

        if len(chapter_text.strip()) < 50:
            continue

        # Split long chapters into ~500-word chunks
        words = chapter_text.split()
        chunk_size = 500
        verse_num = 1

        for j in range(0, len(words), chunk_size):
            chunk_words = words[j:j + chunk_size]
            chunk_text = " ".join(chunk_words)

            if len(chunk_text.strip()) < 50:
                continue

            chunks.append(ScriptureChunk(
                text=chunk_text,
                # Distinct name so CorpusIndex reading library stays clean
                # (Arnold's is the primary reading translation; Telang adds RAG depth)
                scripture="Bhagavad Gita (Telang)",
                tradition="hindu_vedanta",
                chapter=chapter_num,
                verse=verse_num,
                translator="K.T. Telang",
                year=1882,
                language="en",
                license_tier="A",
                source_url=SOURCE_URL_IA,
                chunk_type="prose",
                verse_type="verse",
                chapter_name=f"Chapter {chapter_num}",
                themes=_detect_themes(chunk_text),
            ))
            verse_num += 1

    return chunks


def _parse_supplementary(text: str, scripture_name: str, tradition: str = "hindu_vedanta") -> list[ScriptureChunk]:
    """Parse Sanatsugatiya or Anugita as prose chunks."""
    cleaned = _ocr_clean(text)
    if not cleaned or len(cleaned.split()) < 30:
        return []

    chunks: list[ScriptureChunk] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    # Group into ~400-word chunks
    current: list[str] = []
    verse_num = 1

    for para in paragraphs:
        current.append(para)
        combined = " ".join(current)
        if len(combined.split()) >= 400:
            chunks.append(ScriptureChunk(
                text=combined,
                scripture=scripture_name,
                tradition=tradition,
                chapter=1,
                verse=verse_num,
                translator="K.T. Telang",
                year=1882,
                language="en",
                license_tier="A",
                source_url=SOURCE_URL_IA,
                chunk_type="prose",
                verse_type="verse",
                themes=_detect_themes(combined),
            ))
            current = []
            verse_num += 1

    # Emit remaining
    if current:
        combined = " ".join(current)
        if len(combined.split()) >= 20:
            chunks.append(ScriptureChunk(
                text=combined,
                scripture=scripture_name,
                tradition=tradition,
                chapter=1,
                verse=verse_num,
                translator="K.T. Telang",
                year=1882,
                language="en",
                license_tier="A",
                source_url=SOURCE_URL_IA,
                chunk_type="prose",
                verse_type="verse",
                themes=_detect_themes(combined),
            ))

    return chunks


def parse_telang_sbe08(filepath: Path) -> dict[str, list[ScriptureChunk]]:
    """
    Parse bhagavad_gita_telang_sbe08.txt and extract all three texts.

    Returns:
        Dict with keys 'gita', 'sanatsujatiya', 'anugita' → list of ScriptureChunks
    """
    raw_text = filepath.read_text(encoding="utf-8", errors="ignore")

    gita_start, sanat_start, anugita_start = _find_text_boundaries(raw_text)

    # Extract text segments
    gita_end = sanat_start if sanat_start > 0 else (anugita_start if anugita_start > 0 else len(raw_text))
    gita_text = raw_text[gita_start:gita_end]

    results: dict[str, list[ScriptureChunk]] = {}

    # 1. Bhagavad Gita (18 chapters)
    gita_chunks = _parse_gita_chapters(gita_text)
    results["gita"] = gita_chunks

    # 2. Sanatsugatiya (if present)
    if sanat_start > 0:
        sanat_end = anugita_start if anugita_start > 0 else len(raw_text)
        sanat_text = raw_text[sanat_start:sanat_end]
        results["sanatsujatiya"] = _parse_supplementary(sanat_text, "Sanatsugatiya")
    else:
        results["sanatsujatiya"] = []

    # 3. Anugita (if present)
    if anugita_start > 0:
        anugita_text = raw_text[anugita_start:]
        results["anugita"] = _parse_supplementary(anugita_text, "Anugita")
    else:
        results["anugita"] = []

    return results
