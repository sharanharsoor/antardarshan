"""
Generic parser for Sacred Books of the East (SBE) prose texts.

Handles: Brahma Sutras, Manu Smriti, Jain Sutras, Nyaya Sutras,
         Vaisheshika Sutras, Samkhya Karika, Milindapanha,
         Institutes of Vishnu, and similar SBE-format texts.

These texts share a common structure:
  - Project Gutenberg or IA header (stripped)
  - Numbered sections/sutras + prose commentary
  - Chapter/book headers in uppercase or Roman numerals

OCR quality: IA djvu scans have character-level noise but
readable word structure. Pre-processing normalizes spacing.
Minimum chunk size enforced to filter out OCR garbage lines.
"""

import re
from pathlib import Path

from ingestion.schema import ScriptureChunk

# Generic theme detection for dharmashastra / philosophical texts
THEME_KEYWORDS = {
    "dharma": ["dharma", "duty", "law", "righteousness", "virtue"],
    "karma": ["karma", "action", "consequence", "deed", "result"],
    "liberation": ["liberation", "moksha", "freedom", "release", "salvation"],
    "brahman": ["brahman", "brahma", "supreme", "absolute", "self"],
    "ethics": ["ethics", "conduct", "righteous", "virtue", "sin"],
    "ritual": ["ritual", "sacrifice", "penance", "rite", "ceremony"],
    "knowledge": ["knowledge", "wisdom", "understanding", "science"],
    "non-violence": ["non-violence", "ahimsa", "harmless", "gentle"],
    "logic": ["inference", "perception", "syllogism", "proof", "valid"],
    "caste": ["brahmin", "kshatriya", "vaishya", "shudra", "caste"],
}

# Patterns for chapter/section headers in SBE texts
CHAPTER_PATTERNS = [
    re.compile(r"^(?:BOOK|CHAPTER|ADHYAYA|CHAPTER|SECTION|PART)\s+([IVXLC]+|\d+)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^([IVXLC]{1,8})\.\s*$", re.MULTILINE),
    re.compile(r"^\d+\.\s{2,}", re.MULTILINE),  # numbered sections
]
HEADER_PATTERN = re.compile(
    r"^(?:BOOK|CHAPTER|ADHYAYA|PRAPATHAKA|VARGA|SECTION|PART)\s+([IVXLC]+|\d+)",
    re.IGNORECASE,
)

# PG/IA boilerplate to strip (anything before first real content)
BOILERPLATE_END_PATTERNS = [
    r"End of the Project Gutenberg",
    r"START OF (THE |THIS )?PROJECT GUTENBERG",
    r"Produced by",
    r"This eBook was produced",
]


def _ocr_clean(text: str) -> str:
    """Normalize OCR artifacts common in IA djvu scans."""
    # Remove embedded page numbers
    text = re.sub(r"\n\s*\d{1,4}\s*\n", "\n", text)
    # Fix mid-word hyphenation breaks
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # Collapse runs of punctuation/symbols from OCR noise
    text = re.sub(r"[^\w\s.,;:!?()\[\]\"'—–-]{3,}", " ", text)
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def _strip_boilerplate(text: str) -> str:
    """Remove PG/IA header and footer, find start of actual content."""
    # Find start: look for first CHAPTER/BOOK/section marker or first long paragraph
    # after usual PG boilerplate (~first 3000 chars)
    start = 0

    # PG texts: START OF THE PROJECT GUTENBERG EBOOK line
    pg_match = re.search(r"\*\*\*\s*START OF.*?\*\*\*", text, re.IGNORECASE)
    if pg_match:
        start = pg_match.end()

    # IA texts: look for a chapter/content marker after first 2000 chars
    if start == 0:
        for pattern in CHAPTER_PATTERNS[:2]:
            m = pattern.search(text, 500)
            if m and m.start() < 15000:
                start = m.start()
                break

    # PG footer
    end = len(text)
    pg_end = re.search(r"\*\*\*\s*END OF.*?\*\*\*", text)
    if pg_end:
        end = pg_end.start()

    return text[start:end]


def _detect_themes(text: str) -> list[str]:
    t = text.lower()
    return [theme for theme, kws in THEME_KEYWORDS.items() if any(kw in t for kw in kws)][:4]


def _is_readable(text: str, min_words: int = 20) -> bool:
    """Check if a chunk has enough readable English content."""
    words = re.findall(r"[a-zA-Z]{3,}", text)
    return len(words) >= min_words


def _roman_to_int(value: str) -> int | None:
    value = value.strip().upper()
    if not value:
        return None
    if value.isdigit():
        return int(value)

    roman_vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(value):
        current = roman_vals.get(ch)
        if current is None:
            return None
        if current < prev:
            total -= current
        else:
            total += current
            prev = current
    return total if total > 0 else None


def parse_sbe_text(
    filepath: Path,
    scripture: str,
    tradition: str,
    translator: str,
    year: int,
    source_url: str,
    chunk_words: int = 400,
    min_chunk_words: int = 30,
) -> list[ScriptureChunk]:
    """
    Generic SBE prose text parser.

    Reads an SBE text file, strips boilerplate, and produces
    paragraph-grouped chunks of approximately `chunk_words` words each.

    Args:
        filepath: Path to the raw text file
        scripture: Display name (e.g., "Manu Smriti")
        tradition: Tradition code (e.g., "hindu_vedanta", "jain", "buddhist")
        translator: Translator name
        year: Year of translation
        source_url: Source URL for provenance
        chunk_words: Target words per chunk
        min_chunk_words: Minimum words to emit a chunk

    Returns:
        List of ScriptureChunks
    """
    raw = filepath.read_text(encoding="utf-8", errors="ignore")
    text = _strip_boilerplate(raw)
    text = _ocr_clean(text)

    if not text or not _is_readable(text, 50):
        return []

    # Split by double newlines (paragraphs) and group into chunks
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: list[ScriptureChunk] = []
    current_parts: list[str] = []
    chapter = 1
    verse = 1
    chapter_name: str | None = None
    # Track used (chapter, verse) pairs to prevent duplicates caused by
    # repeated chapter markers in OCR text (e.g. Book I appearing multiple times)
    _used_pairs: set[tuple[int, int]] = set()

    def _next_verse(ch: int, v: int) -> int:
        """Return v or the next available verse number for this chapter."""
        while (ch, v) in _used_pairs:
            v += 1
        return v

    def _emit_current(combined_text: str) -> bool:
        nonlocal chunks, chapter, verse, chapter_name
        if not _is_readable(combined_text, min_chunk_words):
            return False
        verse = _next_verse(chapter, verse)
        _used_pairs.add((chapter, verse))
        chunks.append(ScriptureChunk(
            text=combined_text,
            scripture=scripture,
            tradition=tradition,
            chapter=chapter,
            verse=verse,
            translator=translator,
            year=year,
            language="en",
            license_tier="A",
            source_url=source_url,
            chunk_type="prose",
            verse_type="verse",
            chapter_name=chapter_name,
            themes=_detect_themes(combined_text),
        ))
        return True

    for para in paragraphs:
        # Detect chapter header and advance chapter metadata.
        header_match = HEADER_PATTERN.match(para) if len(para) < 120 else None
        if header_match:
            # Emit any pending chunk
            if current_parts:
                combined = " ".join(current_parts)
                if _emit_current(combined):
                    verse += 1
                current_parts = []

            parsed_chapter = _roman_to_int(header_match.group(1))
            if parsed_chapter is not None:
                chapter = parsed_chapter
            elif chunks:
                chapter += 1
            verse = 1
            chapter_name = para.strip()
            continue

        # Skip very short OCR garbage lines
        if len(para.split()) < 4:
            continue

        current_parts.append(para)
        combined = " ".join(current_parts)

        if len(combined.split()) >= chunk_words:
            if _emit_current(combined):
                verse += 1
            current_parts = []

    # Emit final remaining chunk
    if current_parts:
        combined = " ".join(current_parts)
        _emit_current(combined)

    return chunks


# ── Convenience wrappers for each specific text ────────────────────────────

def parse_manu_smriti(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Manu Smriti", "hindu_vedanta",
        "Georg Bühler", 1886,
        "https://archive.org/details/lawsofmanu00manuuoft",
    )


def parse_arthashastra(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Arthashastra", "hindu_vedanta",
        "R. Shamasastry", 1915,
        "https://archive.org/details/kautilyas-arthashastra",
    )


def parse_brahma_sutras_shankara(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Brahma Sutras (Shankara commentary)", "hindu_vedanta",
        "George Thibaut", 1890,
        "https://archive.org/details/mlbd.vedantasutras00vol-34.bada",
    )


def parse_brahma_sutras_ramanuja(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Brahma Sutras (Ramanuja commentary)", "hindu_vedanta",
        "George Thibaut", 1904,
        "https://archive.org/details/thevedantasutras07297gut",
    )


def parse_jain_sutras(filepath: Path, part: int) -> list[ScriptureChunk]:
    # Distinct names so CorpusIndex doesn't merge Part 1 (SBE 22) and Part 2 (SBE 45)
    name = "Jain Sutras (SBE 22)" if part == 1 else "Jain Sutras (SBE 45)"
    url = ("https://archive.org/details/gainastras0022unse"
           if part == 1
           else "https://archive.org/details/mlbd.gainasutraspart20000vol-45.unse")
    return parse_sbe_text(filepath, name, "jain",
                          "Hermann Jacobi", 1884 if part == 1 else 1895, url)


def parse_nyaya_sutras(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Nyaya Sutras", "hindu_vedanta",
        "Satisa Chandra Vidyabhusana", 1913,
        "https://archive.org/details/TheNyayaSutrasOfGotama",
    )


def parse_vaisheshika_sutras(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Vaisheshika Sutras", "hindu_vedanta",
        "Nandalal Sinha", 1923,
        "https://archive.org/details/thevaiasesikasut00kanauoft",
    )


def parse_samkhya_karika(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Samkhya Karika", "hindu_vedanta",
        "Henry Thomas Colebrooke", 1837,
        "https://archive.org/details/dli.ministry.22344",
        chunk_words=300,  # shorter text, smaller chunks
    )


def parse_milindapanha(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Milindapanha", "buddhist",
        "T.W. Rhys Davids", 1890,
        "https://archive.org/details/questionsofkingm01davi",
    )


def parse_institutes_of_vishnu(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Institutes of Vishnu", "hindu_vedanta",
        "Julius Jolly", 1880,
        "https://archive.org/details/sacredbooksofeas07mull",
    )


def parse_garuda_purana(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Garuda Purana", "hindu_vedanta",
        "Ernest Wood & S.V. Subrahmanyam", 1911,
        "https://archive.org/details/in.ernet.dli.2015.45762",
    )


def parse_markandeya_purana(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Markandeya Purana", "hindu_vedanta",
        "F.E. Pargiter", 1904,
        "https://archive.org/details/in.ernet.dli.2015.47519",
    )


def parse_agni_purana(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Agni Purana", "hindu_vedanta",
        "Manmatha Nath Dutt", 1903,
        "https://archive.org/details/in.ernet.dli.2015.279469",
    )


def parse_vivekachudamani(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Vivekachudamani", "hindu_vedanta",
        "Swami Madhavananda", 1921,
        "https://archive.org/details/vivekachudamanio00sankrich",
        chunk_words=300,
    )


def parse_psalms_maratha_saints(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Psalms of Maratha Saints", "sant_bhakti",
        "Nicol Macnicol", 1919,
        "https://archive.org/details/psalmsofmarathas00macnuoft",
        chunk_words=300,
    )


def parse_thirukkural(filepath: Path) -> list[ScriptureChunk]:
    return parse_sbe_text(
        filepath, "Thirukkural", "sant_bhakti",
        "G.U. Pope", 1886,
        "https://archive.org/details/tiruvalluvanayan00tiruuoft",
        chunk_words=250,
    )
