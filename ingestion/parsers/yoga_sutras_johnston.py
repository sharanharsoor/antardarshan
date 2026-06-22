"""
Parser for Charles Johnston's Yoga Sutras of Patanjali (Project Gutenberg #2526).

Structure: 4 Books, sutras numbered sequentially within each book.
Each sutra is a numbered line followed by commentary paragraphs.
We chunk each sutra + its commentary as one unit.
"""

import re
from pathlib import Path
from ingestion.schema import ScriptureChunk

BOOK_PATTERN = re.compile(r"^BOOK\s+(I+V?)\s*$", re.MULTILINE)
SUTRA_PATTERN = re.compile(r"^(\d+)\.\s+(.+)", re.MULTILINE)

ROMAN_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4}
SOURCE_URL = "https://www.gutenberg.org/ebooks/2526"


def parse_yoga_sutras_johnston(filepath: Path) -> list[ScriptureChunk]:
    """Parse Johnston's Yoga Sutras into sutra-level chunks (sutra + commentary)."""
    text = filepath.read_text(encoding="utf-8")
    chunks = []

    # Find book boundaries
    book_starts = list(BOOK_PATTERN.finditer(text))

    for i, match in enumerate(book_starts):
        roman = match.group(1)
        book_num = ROMAN_MAP.get(roman)
        if book_num is None:
            continue

        start = match.end()
        end = book_starts[i + 1].start() if i + 1 < len(book_starts) else len(text)
        book_text = text[start:end]

        # Find all sutras in this book
        sutra_matches = list(SUTRA_PATTERN.finditer(book_text))

        for j, sm in enumerate(sutra_matches):
            sutra_num = int(sm.group(1))
            sutra_text = sm.group(2).strip()

            # Get commentary: text between this sutra and next sutra (or end of book)
            commentary_start = sm.end()
            if j + 1 < len(sutra_matches):
                commentary_end = sutra_matches[j + 1].start()
            else:
                commentary_end = len(book_text)

            commentary = book_text[commentary_start:commentary_end].strip()

            # Combine sutra + commentary for embedding (context-rich)
            full_text = sutra_text
            if commentary and len(commentary) > 20:
                full_text = f"{sutra_text}\n\n{commentary}"

            # Skip intro sections that got picked up
            if sutra_num == 0 or len(full_text) < 20:
                continue

            chunks.append(ScriptureChunk(
                text=full_text,
                scripture="Yoga Sutras",
                tradition="hindu_yoga",
                chapter=book_num,
                verse=sutra_num,
                translator="Charles Johnston",
                year=1912,
                language="en",
                license_tier="A",
                source_url=SOURCE_URL,
                chunk_type="verse",
                verse_type="verse",
                chapter_name=f"Book {roman}",
                themes=_detect_themes(full_text),
            ))

    return chunks


def _detect_themes(text: str) -> list[str]:
    """Basic theme detection for yoga concepts."""
    text_lower = text.lower()
    themes = []
    theme_keywords = {
        "meditation": ["meditat", "concentrat", "contemplat", "samadhi", "dhyana"],
        "mind": ["mind", "thought", "psychic", "mental", "consciousness"],
        "liberation": ["liberat", "free", "emancipat", "kaivalya"],
        "practice": ["practice", "discipline", "effort", "persist"],
        "obstacles": ["obstacle", "hinder", "distract", "pain", "ignorance"],
        "powers": ["power", "mastery", "attain", "perfection", "siddhi"],
        "detachment": ["detach", "renounc", "dispassion", "non-attach"],
        "knowledge": ["knowledge", "wisdom", "discern", "illumin"],
    }
    for theme, keywords in theme_keywords.items():
        if any(kw in text_lower for kw in keywords):
            themes.append(theme)
    return themes[:4]


if __name__ == "__main__":
    corpus_path = Path(__file__).parent.parent.parent / "corpus" / "raw" / "pg2526.txt"
    if not corpus_path.exists():
        print(f"File not found: {corpus_path}")
        exit(1)

    chunks = parse_yoga_sutras_johnston(corpus_path)
    print(f"\nParsed {len(chunks)} sutra chunks from 4 books")
    print(f"\nSample (Book I, Sutra 1):")
    s1 = [c for c in chunks if c.chapter == 1 and c.verse == 1]
    if s1:
        print(f"  {s1[0].text[:200]}...")
    print(f"\nBook distribution:")
    for b in range(1, 5):
        count = len([c for c in chunks if c.chapter == b])
        print(f"  Book {b}: {count} sutras")
