"""
Parser for Edwin Arnold's Bhagavad Gita translation (Project Gutenberg #2388).

Arnold's translation is a poetic rendering without individual verse numbers.
Structure: CHAPTER I-XVIII, stanzas separated by blank lines.
Each stanza ≈ 2-5 original Sanskrit verses.
We chunk by stanza and assign sequential stanza numbers within each chapter.
"""

import re
from pathlib import Path
from ingestion.schema import ScriptureChunk

CHAPTER_PATTERN = re.compile(r"^\s*CHAPTER\s+([IVXLC]+)\s*$", re.MULTILINE)
CHAPTER_END_PATTERN = re.compile(r"^\s*HERE END", re.MULTILINE)

ROMAN_MAP = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
    "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18,
}

SOURCE_URL = "https://www.gutenberg.org/ebooks/2388"


def parse_gita_arnold(filepath: Path) -> list[ScriptureChunk]:
    """Parse Arnold's Gita into stanza-level chunks."""
    text = filepath.read_text(encoding="utf-8")
    chunks = []

    # Find all chapter starts
    chapter_starts = list(CHAPTER_PATTERN.finditer(text))

    for i, match in enumerate(chapter_starts):
        roman = match.group(1)
        chapter_num = ROMAN_MAP.get(roman)
        if chapter_num is None:
            continue

        # Extract text between this chapter start and next chapter (or end of file)
        start = match.end()
        if i + 1 < len(chapter_starts):
            end = chapter_starts[i + 1].start()
        else:
            end = len(text)

        chapter_text = text[start:end]

        # Remove the "HERE ENDETH..." footer
        end_match = CHAPTER_END_PATTERN.search(chapter_text)
        if end_match:
            chapter_text = chapter_text[:end_match.start()]

        # Split into stanzas by blank lines (2+ newlines)
        stanzas = re.split(r"\n\s*\n", chapter_text.strip())

        stanza_num = 0
        for stanza in stanzas:
            cleaned = stanza.strip()
            if not cleaned or len(cleaned) < 20:
                continue

            stanza_num += 1
            chunks.append(ScriptureChunk(
                text=cleaned,
                scripture="Bhagavad Gita",
                tradition="hindu_vedanta",
                chapter=chapter_num,
                verse=stanza_num,
                translator="Edwin Arnold",
                year=1885,
                language="en",
                license_tier="A",
                source_url=SOURCE_URL,
                chunk_type="verse",
                verse_type="stanza",
                themes=_detect_themes(cleaned),
            ))

    return chunks


def _detect_themes(text: str) -> list[str]:
    """Basic keyword-based theme detection. Will be improved with embeddings later."""
    text_lower = text.lower()
    themes = []
    theme_keywords = {
        "karma": ["action", "act", "deed", "work", "duty"],
        "dharma": ["dharma", "duty", "righteousness", "law"],
        "devotion": ["devot", "worship", "love", "bhakti", "pray"],
        "knowledge": ["know", "wisdom", "truth", "learn"],
        "yoga": ["yoga", "meditat", "concentrat", "discipline"],
        "detachment": ["detach", "renounc", "let go", "abandon"],
        "self": ["self", "soul", "atman", "spirit"],
        "death": ["death", "die", "born", "birth", "mortal"],
        "liberation": ["free", "liberat", "moksha", "release"],
        "nature": ["nature", "prakriti", "gunas", "creation"],
    }
    for theme, keywords in theme_keywords.items():
        if any(kw in text_lower for kw in keywords):
            themes.append(theme)
    return themes[:4]  # Cap at 4 themes per chunk


if __name__ == "__main__":
    corpus_path = Path(__file__).parent.parent.parent / "corpus" / "raw" / "pg2388.txt"
    if not corpus_path.exists():
        print(f"File not found: {corpus_path}")
        exit(1)

    chunks = parse_gita_arnold(corpus_path)
    print(f"\nParsed {len(chunks)} stanza chunks from 18 chapters")
    print(f"\nSample chunk (Chapter 2, Stanza 1):")
    ch2 = [c for c in chunks if c.chapter == 2]
    if ch2:
        sample = ch2[0]
        print(f"  ID: {sample.chunk_id}")
        print(f"  Chapter: {sample.chapter}, Stanza: {sample.verse}")
        print(f"  Themes: {sample.themes}")
        print(f"  Text: {sample.text[:150]}...")
    print(f"\nChapter distribution:")
    for ch in range(1, 19):
        count = len([c for c in chunks if c.chapter == ch])
        print(f"  Chapter {ch:2d}: {count} stanzas")
