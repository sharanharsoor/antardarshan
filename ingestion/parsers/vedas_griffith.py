"""
Parser for Griffith's Veda translations (all in IA djvu format).

Handles:
  - Rig Veda (rigveda_griffith.txt) — 10 Mandalas, 1028 hymns
  - Atharva Veda (atharva_veda_griffith.txt) — 20 books

Strategy: chunk at hymn level. Each hymn is a natural complete unit
(invocation to a deity, usually 5-25 verses). Hymns are identified
by their "HYMN N." or numbered headers in Griffith's format.

Mandala/Book → chapter, Hymn → verse in our schema.
"""

import re
from pathlib import Path

from ingestion.schema import ScriptureChunk

RIG_VEDA_URL = "https://archive.org/details/hymnsrigveda00unkngoog"
ATHARVA_VEDA_URL = "https://archive.org/details/hymnsatharvaved00unkngoog"

THEME_KEYWORDS = {
    "agni": ["agni", "fire", "flame", "hearth", "altar"],
    "indra": ["indra", "thunder", "rain", "warrior", "soma"],
    "varuna": ["varuna", "rita", "cosmic order", "truth", "waters"],
    "vishnu": ["vishnu", "pervades", "three strides"],
    "soma": ["soma", "plant", "drink", "sacrifice", "immortal"],
    "creation": ["creat", "origin", "born", "manifest", "exist"],
    "dharma": ["dharma", "law", "order", "righteous", "truth"],
    "prayer": ["prayer", "praise", "worship", "hymn", "chant"],
    "wisdom": ["wisdom", "know", "understand", "sage", "seer"],
    "immortality": ["immortal", "deathless", "eternal", "heaven"],
}


def _ocr_clean(text: str) -> str:
    text = re.sub(r"\n\s*\d{1,4}\s*\n", "\n", text)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def _detect_themes(text: str) -> list[str]:
    t = text.lower()
    return [theme for theme, kws in THEME_KEYWORDS.items() if any(kw in t for kw in kws)][:4]


def _strip_header(text: str, start_marker: str = "MANDALA") -> str:
    """Strip PG/IA boilerplate before the first Mandala or Book."""
    pg_match = re.search(r"\*\*\*\s*START OF.*?\*\*\*", text, re.IGNORECASE)
    if pg_match:
        text = text[pg_match.end():]

    start = re.search(r"\b" + start_marker + r"\b", text, re.IGNORECASE)
    if start:
        return text[start.start():]
    return text


# Rig Veda uses BOOK I-X as top-level divisions, HYMN within each book
# (IA OCR scan has spaced-out text: "BOOK  I." and "HYMN  IV.")
RIG_BOOK_PATTERN = re.compile(r"\bBOOK\s+([IVXLC]+|\d+)\b", re.IGNORECASE)
RIG_HYMN_PATTERN = re.compile(r"\bHYMN\s+([IVXLC]+|\d+)\.?\b", re.IGNORECASE)
# Keep MANDALA_PATTERN as alias for compatibility
MANDALA_PATTERN = RIG_BOOK_PATTERN

BOOK_PATTERN = re.compile(r"\bBOOK\s+([IVXLC]+|\d+)\b", re.IGNORECASE)
ATHARVA_HYMN_PATTERN = re.compile(r"\bHYMN\s+([IVXLC]+|\d+)\.?\b", re.IGNORECASE)


def _roman_to_int(roman: str) -> int:
    """Convert Roman numeral string to integer. Falls back to int() for digits."""
    try:
        return int(roman)
    except ValueError:
        pass
    roman = roman.upper()
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    result = 0
    prev = 0
    for ch in reversed(roman):
        v = vals.get(ch, 0)
        result += v if v >= prev else -v
        prev = v
    return result if result > 0 else 1


def parse_rig_veda(filepath: Path) -> list[ScriptureChunk]:
    """Parse Griffith's Rig Veda — chunks at hymn level (Mandala + Hymn)."""
    raw = filepath.read_text(encoding="utf-8", errors="ignore")
    text = _strip_header(raw, "BOOK")
    text = _ocr_clean(text)

    chunks: list[ScriptureChunk] = []

    # Split by Book (top-level division in Rig Veda)
    mandala_splits = list(RIG_BOOK_PATTERN.finditer(text))
    if not mandala_splits:
        return []

    for i, mand_match in enumerate(mandala_splits):
        mandala_num = _roman_to_int(mand_match.group(1))
        mand_start = mand_match.end()
        mand_end = mandala_splits[i + 1].start() if i + 1 < len(mandala_splits) else len(text)
        mandala_text = text[mand_start:mand_end]

        # Split mandala by hymn
        hymn_splits = list(RIG_HYMN_PATTERN.finditer(mandala_text))
        if not hymn_splits:
            # No hymn markers — treat whole mandala as one chunk if small enough
            if len(mandala_text.split()) > 30:
                chunks.append(ScriptureChunk(
                    text=mandala_text.strip()[:2000],
                    scripture="Rig Veda",
                    tradition="hindu_vedanta",
                    chapter=mandala_num, verse=1,
                    translator="Ralph T.H. Griffith",
                    year=1896, language="en",
                    license_tier="A",
                    source_url=RIG_VEDA_URL,
                    chunk_type="verse", verse_type="verse",
                    chapter_name=f"Book {mandala_num}",
                    themes=_detect_themes(mandala_text),
                ))
            continue

        for j, hymn_match in enumerate(hymn_splits):
            hymn_num = _roman_to_int(hymn_match.group(1))
            h_start = hymn_match.end()
            h_end = hymn_splits[j + 1].start() if j + 1 < len(hymn_splits) else len(mandala_text)
            hymn_text = mandala_text[h_start:h_end].strip()

            if not hymn_text or len(hymn_text.split()) < 15:
                continue

            chunks.append(ScriptureChunk(
                text=hymn_text[:3000],  # cap very long hymns
                scripture="Rig Veda",
                tradition="hindu_vedanta",
                chapter=mandala_num,
                verse=hymn_num,
                translator="Ralph T.H. Griffith",
                year=1896,
                language="en",
                license_tier="A",
                source_url=RIG_VEDA_URL,
                chunk_type="verse",
                verse_type="verse",
                chapter_name=f"Book {mandala_num}",
                themes=_detect_themes(hymn_text),
            ))

    return chunks


def parse_atharva_veda(filepath: Path) -> list[ScriptureChunk]:
    """Parse Griffith's Atharva Veda — chunks at hymn level (Book + Hymn)."""
    raw = filepath.read_text(encoding="utf-8", errors="ignore")
    text = _strip_header(raw, "BOOK")
    text = _ocr_clean(text)

    chunks: list[ScriptureChunk] = []

    book_splits = list(BOOK_PATTERN.finditer(text))
    if not book_splits:
        return []

    for i, book_match in enumerate(book_splits):
        book_num = _roman_to_int(book_match.group(1))
        b_start = book_match.end()
        b_end = book_splits[i + 1].start() if i + 1 < len(book_splits) else len(text)
        book_text = text[b_start:b_end]

        hymn_splits = list(ATHARVA_HYMN_PATTERN.finditer(book_text))
        if not hymn_splits:
            if len(book_text.split()) > 30:
                chunks.append(ScriptureChunk(
                    text=book_text.strip()[:2000],
                    scripture="Atharva Veda",
                    tradition="hindu_vedanta",
                    chapter=book_num, verse=1,
                    translator="Ralph T.H. Griffith",
                    year=1895, language="en",
                    license_tier="A",
                    source_url=ATHARVA_VEDA_URL,
                    chunk_type="verse", verse_type="verse",
                    chapter_name=f"Book {book_num}",
                    themes=_detect_themes(book_text),
                ))
            continue

        for j, hymn_match in enumerate(hymn_splits):
            hymn_num = _roman_to_int(hymn_match.group(1))
            h_start = hymn_match.end()
            h_end = hymn_splits[j + 1].start() if j + 1 < len(hymn_splits) else len(book_text)
            hymn_text = book_text[h_start:h_end].strip()

            if not hymn_text or len(hymn_text.split()) < 10:
                continue

            chunks.append(ScriptureChunk(
                text=hymn_text[:2000],
                scripture="Atharva Veda",
                tradition="hindu_vedanta",
                chapter=book_num,
                verse=hymn_num,
                translator="Ralph T.H. Griffith",
                year=1895,
                language="en",
                license_tier="A",
                source_url=ATHARVA_VEDA_URL,
                chunk_type="verse",
                verse_type="verse",
                chapter_name=f"Book {book_num}",
                themes=_detect_themes(hymn_text),
            ))

    return chunks
