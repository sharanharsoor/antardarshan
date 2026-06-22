"""
Parser for John Richards' Ashtavakra Gita translation (PD, 1994).

Structure: verses numbered as X.Y where X=chapter (1-20), Y=verse within chapter.
Each verse is a single line or short paragraph ending with the verse number.
Pattern: "verse text X.Y"
"""

import re
from pathlib import Path
from ingestion.schema import ScriptureChunk

VERSE_PATTERN = re.compile(r"(.+?)\s+(\d+)\.(\d+)\s*$", re.DOTALL)
SOURCE_URL = "https://www.wisdomlib.org/hinduism/book/ashtavakra-gita"


def parse_ashtavakra(filepath: Path) -> list[ScriptureChunk]:
    """Parse Richards' Ashtavakra Gita into verse-level chunks."""
    text = filepath.read_text(encoding="utf-8")
    chunks = []
    seen_verses: set[tuple[int, int]] = set()

    # Split by blank lines to get verse blocks
    blocks = re.split(r"\n\s*\n", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Match verse pattern: text followed by chapter.verse number
        match = VERSE_PATTERN.match(block)
        if not match:
            continue

        verse_text = match.group(1).strip()
        chapter = int(match.group(2))
        verse = int(match.group(3))

        if len(verse_text) < 10:
            continue

        # Skip duplicates (ToC repeats first verse of each chapter)
        if (chapter, verse) in seen_verses:
            continue
        seen_verses.add((chapter, verse))

        # Remove speaker prefix if present (e.g., "Janaka:" or "Ashtavakra:")
        speaker = None
        speaker_match = re.match(r"^(Janaka|Ashtavakra):\s*", verse_text)
        if speaker_match:
            speaker = speaker_match.group(1)
            verse_text = verse_text[speaker_match.end():]

        chunks.append(ScriptureChunk(
            text=verse_text,
            scripture="Ashtavakra Gita",
            tradition="hindu_vedanta",
            chapter=chapter,
            verse=verse,
            translator="John Richards",
            year=1994,
            language="en",
            license_tier="A",
            source_url=SOURCE_URL,
            chunk_type="verse",
            verse_type="verse",
            themes=_detect_themes(verse_text),
            speaker=speaker,
        ))

    return chunks


def _detect_themes(text: str) -> list[str]:
    """Basic keyword-based theme tagging."""
    text_lower = text.lower()
    themes = []
    theme_keywords = {
        "self-knowledge": ["awareness", "consciousness", "witness", "self"],
        "liberation": ["free", "liberat", "bondage", "bound"],
        "detachment": ["detach", "renounc", "abandon", "indifferen"],
        "illusion": ["illusion", "delusion", "ignorance", "unreal", "imagin"],
        "non-duality": ["one", "non-dual", "undivid", "all-pervading"],
        "peace": ["peace", "happy", "joy", "bliss", "content"],
        "action": ["action", "doer", "deed", "act"],
        "mind": ["mind", "thought", "think", "desire"],
    }
    for theme, keywords in theme_keywords.items():
        if any(kw in text_lower for kw in keywords):
            themes.append(theme)
    return themes[:4]


if __name__ == "__main__":
    corpus_path = Path(__file__).parent.parent.parent / "corpus" / "raw" / "ashtavakra_gita_richards.txt"
    if not corpus_path.exists():
        print(f"File not found: {corpus_path}")
        exit(1)

    chunks = parse_ashtavakra(corpus_path)
    print(f"\nParsed {len(chunks)} verse chunks from 20 chapters")
    print(f"\nSample chunk (Chapter 1, Verse 1):")
    ch1 = [c for c in chunks if c.chapter == 1 and c.verse == 1]
    if ch1:
        sample = ch1[0]
        print(f"  ID: {sample.chunk_id}")
        print(f"  Speaker: {sample.commentary_source}")
        print(f"  Themes: {sample.themes}")
        print(f"  Text: {sample.text[:150]}...")
    print(f"\nChapter distribution:")
    for ch in range(1, 21):
        count = len([c for c in chunks if c.chapter == ch])
        if count > 0:
            print(f"  Chapter {ch:2d}: {count} verses")
