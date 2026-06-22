"""
Parser for Indian epics — Mahabharata (Ganguli) and Ramayana (Griffith).

Mahabharata (15MB, IA OCR):
  - 18 Parvans (books), each with many Adhyayas (chapters)
  - Focus: philosophical Parvans first (Shanti, Udyoga, Bhishma)
  - Chunk at paragraph level (~400 words) with Parvan/Adhyaya metadata

Ramayana (Griffith, 2.4MB, PG):
  - 7 Kandas (books) with Sargas (cantos)
  - Verse translation — chunk by Sarga (~30-80 verses each)

Both are massive texts. We parse ALL of them but the philosophical sections
are most valuable for retrieval. The metadata (parvan/kanda) enables
filtering during comparison queries.
"""

import re
from pathlib import Path

from ingestion.schema import ScriptureChunk

MAHABHARATA_URL = "https://archive.org/details/the-mahabharata-of-krishna-dwaipayana-vyasa-complete-18-volumes-kisari-mohan-ganguli_202008"
RAMAYANA_URL = "https://www.gutenberg.org/ebooks/24869"

# Parvans of the Mahabharata (philosophical value rating)
MAHABHARATA_PARVANS = {
    "adi": (1, "Adi Parva"),
    "sabha": (2, "Sabha Parva"),
    "vana": (3, "Vana Parva"),
    "virata": (4, "Virata Parva"),
    "udyoga": (5, "Udyoga Parva"),          # high philosophical value
    "bhishma": (6, "Bhishma Parva"),         # contains the Gita
    "drona": (7, "Drona Parva"),
    "karna": (8, "Karna Parva"),
    "shalya": (9, "Shalya Parva"),
    "sauptika": (10, "Sauptika Parva"),
    "stri": (11, "Stri Parva"),
    "shanti": (12, "Shanti Parva"),          # HIGHEST philosophical value
    "anushasana": (13, "Anushasana Parva"),  # high philosophical value
    "ashvamedhika": (14, "Ashvamedhika Parva"),
    "ashramavasika": (15, "Ashramavasika Parva"),
    "mausala": (16, "Mausala Parva"),
    "mahaprasthanika": (17, "Mahaprasthanika Parva"),
    "svargarohanika": (18, "Svargarohanika Parva"),
}

RAMAYANA_KANDAS = {
    "bala": (1, "Bala Kanda"),
    "ayodhya": (2, "Ayodhya Kanda"),
    "aranya": (3, "Aranya Kanda"),
    "kishkindha": (4, "Kishkindha Kanda"),
    "sundara": (5, "Sundara Kanda"),
    "yuddha": (6, "Yuddha Kanda"),
    "uttara": (7, "Uttara Kanda"),
}

THEME_KEYWORDS = {
    "dharma": ["dharma", "duty", "righteousness", "law", "virtue"],
    "karma": ["karma", "action", "deed", "consequence"],
    "moksha": ["liberation", "moksha", "release", "freedom", "salvation"],
    "kingship": ["king", "ruler", "justice", "governance", "kingdom"],
    "war": ["battle", "war", "warrior", "fight", "hero", "army"],
    "devotion": ["devotion", "worship", "love", "bhakti", "devotee"],
    "wisdom": ["wisdom", "knowledge", "sage", "truth", "understand"],
    "creation": ["creation", "origin", "brahma", "universe", "manifest"],
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


def _is_readable(text: str, min_words: int = 25) -> bool:
    return len(re.findall(r"[a-zA-Z]{3,}", text)) >= min_words


def _is_toc_paragraph(text: str) -> bool:
    """Detect table-of-contents paragraphs (list of titles, no prose sentences)."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return True
    # If most lines end in "Parva" or "Kanda" — it's a ToC listing
    parva_count = sum(1 for l in lines if re.search(r"\bParva\b|\bKanda\b|\bSarga\b", l, re.IGNORECASE))
    if len(lines) > 3 and parva_count / len(lines) > 0.5:
        return True
    # If all lines are short (< 8 words) with no sentence punctuation — ToC
    long_lines = [l for l in lines if len(l.split()) > 7]
    sentences = re.findall(r"[.!?]", text)
    if not long_lines and not sentences:
        return True
    return False


PARVAN_PATTERN = re.compile(
    r"\b(ADI|SABHA|VANA|ARANYAKA|VIRATA|UDYOGA|BHISHMA|DRONA|KARNA|"
    r"SHALYA|SAUPTIKA|STRI|SHANTI|SANTI|ANUSHASANA|ASHVAMEDHIKA|ASVAMEDHA|"
    r"ASHRAMAVASIKA|MAUSALA|MAHAPRASTHANIKA|SVARGAROHANIKA)\s+PARVA",
    re.IGNORECASE,
)

ADHYAYA_PATTERN = re.compile(r"SECTION\s+(\d+)", re.IGNORECASE)


def parse_mahabharata(filepath: Path, chunk_words: int = 400) -> list[ScriptureChunk]:
    """
    Parse Ganguli's complete Mahabharata translation.

    Chunks at paragraph level within each Parvan.
    Shanti Parva and Anushasana Parva are the most philosophically rich —
    they contain Bhishma's teachings on dharma, governance, and liberation.
    """
    raw = filepath.read_text(encoding="utf-8", errors="ignore")
    text = _ocr_clean(raw)

    # Strip front matter
    start_match = re.search(r"\bADI\s+PARVA\b", text, re.IGNORECASE)
    if start_match:
        text = text[start_match.start():]

    chunks: list[ScriptureChunk] = []

    # Split by Parvan
    parvan_splits = list(PARVAN_PATTERN.finditer(text))
    if not parvan_splits:
        # No clear parvan markers — parse as single giant prose block
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        current: list[str] = []
        verse = 1
        for para in paragraphs:
            current.append(para)
            if len(" ".join(current).split()) >= chunk_words:
                combined = " ".join(current)
                if _is_readable(combined):
                    chunks.append(ScriptureChunk(
                        text=combined, scripture="Mahabharata",
                        tradition="hindu_vedanta", chapter=1, verse=verse,
                        translator="Kisari Mohan Ganguli", year=1896,
                        language="en", license_tier="A", source_url=MAHABHARATA_URL,
                        chunk_type="prose", verse_type="verse",
                        themes=_detect_themes(combined),
                    ))
                current = []
                verse += 1
        if current:
            combined = " ".join(current)
            if _is_readable(combined):
                chunks.append(ScriptureChunk(
                    text=combined, scripture="Mahabharata",
                    tradition="hindu_vedanta", chapter=1, verse=verse,
                    translator="Kisari Mohan Ganguli", year=1896,
                    language="en", license_tier="A", source_url=MAHABHARATA_URL,
                    chunk_type="prose", verse_type="verse",
                    themes=_detect_themes(combined),
                ))
        return chunks

    for i, parvan_match in enumerate(parvan_splits):
        parvan_name_raw = parvan_match.group(1).lower()
        # Normalize parvan name
        parvan_key = parvan_name_raw.replace("santi", "shanti").replace("aranyaka", "vana")
        parvan_num, parvan_display = MAHABHARATA_PARVANS.get(parvan_key, (i + 1, f"{parvan_name_raw.title()} Parva"))

        p_start = parvan_match.end()
        p_end = parvan_splits[i + 1].start() if i + 1 < len(parvan_splits) else len(text)
        parvan_text = text[p_start:p_end]

        # Chunk parvan into ~400-word chunks
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", parvan_text) if p.strip()]
        current: list[str] = []
        verse = 1

        for para in paragraphs:
            if len(para.split()) < 4:
                continue
            if _is_toc_paragraph(para):
                continue
            current.append(para)
            combined = " ".join(current)

            if len(combined.split()) >= chunk_words:
                if _is_readable(combined):
                    chunks.append(ScriptureChunk(
                        text=combined,
                        scripture="Mahabharata",
                        tradition="hindu_vedanta",
                        chapter=parvan_num,
                        verse=verse,
                        translator="Kisari Mohan Ganguli",
                        year=1896,
                        language="en",
                        license_tier="A",
                        source_url=MAHABHARATA_URL,
                        chunk_type="prose",
                        verse_type="verse",
                        chapter_name=parvan_display,
                        themes=_detect_themes(combined),
                    ))
                current = []
                verse += 1

        # Emit remainder of parvan
        if current:
            combined = " ".join(current)
            if _is_readable(combined):
                chunks.append(ScriptureChunk(
                    text=combined,
                    scripture="Mahabharata",
                    tradition="hindu_vedanta",
                    chapter=parvan_num,
                    verse=verse,
                    translator="Kisari Mohan Ganguli",
                    year=1896,
                    language="en",
                    license_tier="A",
                    source_url=MAHABHARATA_URL,
                    chunk_type="prose",
                    verse_type="verse",
                    chapter_name=parvan_display,
                    themes=_detect_themes(combined),
                ))

    return chunks


# Griffith's Ramayana uses CANTO numbering, not Kanda names
# We split by BOOK (7 books = 7 Kandas) then CANTO within each
RAMAYANA_BOOK_PATTERN = re.compile(r"\bBOOK\s+([IVXLC]+|\d+)\b", re.IGNORECASE)
RAMAYANA_CANTO_PATTERN = re.compile(r"\bCANTO\s+([IVXLC]+|\d+)\.?\b", re.IGNORECASE)

KANDA_PATTERN = RAMAYANA_BOOK_PATTERN  # alias for back-compat


def parse_ramayana(filepath: Path, chunk_words: int = 400) -> list[ScriptureChunk]:
    """Parse Griffith's Ramayana — chunks by Kanda at paragraph level."""
    raw = filepath.read_text(encoding="utf-8", errors="ignore")
    text = _ocr_clean(raw)

    # Strip PG header
    pg_match = re.search(r"\*\*\*\s*START OF.*?\*\*\*", text, re.IGNORECASE)
    if pg_match:
        text = text[pg_match.end():]

    chunks: list[ScriptureChunk] = []

    # Griffith's Ramayana uses BOOK I-VII structure with CANTO sub-sections
    book_splits = list(RAMAYANA_BOOK_PATTERN.finditer(text))

    if not book_splits:
        # Fallback: parse as single prose stream
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        current: list[str] = []
        verse = 1
        for para in paragraphs:
            current.append(para)
            if len(" ".join(current).split()) >= chunk_words:
                combined = " ".join(current)
                if _is_readable(combined):
                    chunks.append(ScriptureChunk(
                        text=combined, scripture="Ramayana",
                        tradition="hindu_vedanta", chapter=1, verse=verse,
                        translator="Ralph T.H. Griffith", year=1895,
                        language="en", license_tier="A", source_url=RAMAYANA_URL,
                        chunk_type="prose", verse_type="verse",
                        themes=_detect_themes(combined),
                    ))
                current = []
                verse += 1
        if current:
            combined = " ".join(current)
            if _is_readable(combined):
                chunks.append(ScriptureChunk(
                    text=combined, scripture="Ramayana",
                    tradition="hindu_vedanta", chapter=1, verse=verse,
                    translator="Ralph T.H. Griffith", year=1895,
                    language="en", license_tier="A", source_url=RAMAYANA_URL,
                    chunk_type="prose", verse_type="verse",
                    themes=_detect_themes(combined),
                ))
        return chunks

    kanda_names = ["Bala Kanda", "Ayodhya Kanda", "Aranya Kanda",
                   "Kishkindha Kanda", "Sundara Kanda", "Yuddha Kanda", "Uttara Kanda"]

    for i, book_match in enumerate(book_splits):
        try:
            kanda_num = _roman_to_int(book_match.group(1))
        except Exception:
            kanda_num = i + 1

        kanda_display = kanda_names[kanda_num - 1] if 1 <= kanda_num <= 7 else f"Book {kanda_num}"

        k_start = book_match.end()
        k_end = book_splits[i + 1].start() if i + 1 < len(book_splits) else len(text)
        kanda_text = text[k_start:k_end]

        # Group cantos into chunks
        canto_splits = list(RAMAYANA_CANTO_PATTERN.finditer(kanda_text))

        if canto_splits:
            # Aggregate cantos into ~chunk_words chunks
            current: list[str] = []
            verse = 1
            for j, canto in enumerate(canto_splits):
                c_start = canto.end()
                c_end = canto_splits[j + 1].start() if j + 1 < len(canto_splits) else len(kanda_text)
                canto_text = kanda_text[c_start:c_end].strip()
                if len(canto_text.split()) < 5:
                    continue
                current.append(canto_text)
                combined = " ".join(current)
                if len(combined.split()) >= chunk_words:
                    if _is_readable(combined):
                        chunks.append(ScriptureChunk(
                            text=combined, scripture="Ramayana",
                            tradition="hindu_vedanta", chapter=kanda_num, verse=verse,
                            translator="Ralph T.H. Griffith", year=1895,
                            language="en", license_tier="A", source_url=RAMAYANA_URL,
                            chunk_type="prose", verse_type="verse",
                            chapter_name=kanda_display,
                            themes=_detect_themes(combined),
                        ))
                    current = []
                    verse += 1
            if current:
                combined = " ".join(current)
                if _is_readable(combined):
                    chunks.append(ScriptureChunk(
                        text=combined, scripture="Ramayana",
                        tradition="hindu_vedanta", chapter=kanda_num, verse=verse,
                        translator="Ralph T.H. Griffith", year=1895,
                        language="en", license_tier="A", source_url=RAMAYANA_URL,
                        chunk_type="prose", verse_type="verse",
                        chapter_name=kanda_display,
                        themes=_detect_themes(combined),
                    ))
        else:
            # No canto markers — use paragraph chunking
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", kanda_text) if p.strip()]
            current = []
            verse = 1
            for para in paragraphs:
                if len(para.split()) < 4:
                    continue
                current.append(para)
                combined = " ".join(current)
                if len(combined.split()) >= chunk_words:
                    if _is_readable(combined):
                        chunks.append(ScriptureChunk(
                            text=combined, scripture="Ramayana",
                            tradition="hindu_vedanta", chapter=kanda_num, verse=verse,
                            translator="Ralph T.H. Griffith", year=1895,
                            language="en", license_tier="A", source_url=RAMAYANA_URL,
                            chunk_type="prose", verse_type="verse",
                            chapter_name=kanda_display,
                            themes=_detect_themes(combined),
                        ))
                    current = []
                    verse += 1
            if current:
                combined = " ".join(current)
                if _is_readable(combined):
                    chunks.append(ScriptureChunk(
                        text=combined, scripture="Ramayana",
                        tradition="hindu_vedanta", chapter=kanda_num, verse=verse,
                        translator="Ralph T.H. Griffith", year=1895,
                        language="en", license_tier="A", source_url=RAMAYANA_URL,
                        chunk_type="prose", verse_type="verse",
                        chapter_name=kanda_display,
                        themes=_detect_themes(combined),
                    ))

    return chunks
