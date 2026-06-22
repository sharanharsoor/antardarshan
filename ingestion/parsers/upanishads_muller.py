"""
Parser for Max Müller's Upanishad translations (SBE Vols. 1 & 15, 1879-1884).

Structure: Adhyayas (books) → Vallis/Khandas (chapters) → numbered verses.
Each verse is a numbered paragraph. Commentary/parenthetical notes in () are
included as they provide essential context in Müller's translation.

Supports: Katha, Isha, Kena, Mundaka, Prashna, Svetasvatara, Chandogya,
Brihadaranyaka, Taittiriya, Aitareya Upanishads.
"""

import re
from pathlib import Path
from ingestion.schema import ScriptureChunk

SOURCE_URL_TEMPLATE = "https://sacred-texts.com/hin/sbe{vol}/index.htm"

# Maps Upanishad names to their SBE volume
UPANISHAD_VOLUMES = {
    "Katha Upanishad": "15",
    "Isha Upanishad": "01",
    "Kena Upanishad": "01",
    "Mundaka Upanishad": "15",
    "Prashna Upanishad": "15",
    "Svetasvatara Upanishad": "15",
    "Chandogya Upanishad": "01",
    "Brihadaranyaka Upanishad": "15",
    "Taittiriya Upanishad": "15",
    "Aitareya Upanishad": "01",
}

VALLI_PATTERN = re.compile(
    r"^(?:#{1,4}\s*)?(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+"
    r"(?:VALLI|VALLÎ|KHANDA|KHANDÂ|ADHYAYA|ADHYÂYA|PRAPÂTHAKA|MUNDAKA|PRAPAATHAKA"
    r"|PRASHNA|QUESTION|ANUVAKA|VARGA)\.?",
    re.IGNORECASE | re.MULTILINE,
)

SECTION_NAMES = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4,
    "FIFTH": 5, "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8,
}

VERSE_PATTERN = re.compile(r"^(\d+)\.\s+(.+?)(?=\n\d+\.\s|\n#{1,4}\s|\Z)", re.MULTILINE | re.DOTALL)
ADHYAYA_PATTERN = re.compile(
    r"^#{1,4}\s*(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH)\s+ADHYAYA",
    re.IGNORECASE | re.MULTILINE,
)


def parse_upanishad(filepath: Path, upanishad_name: str) -> list[ScriptureChunk]:
    """Parse a single Upanishad from a text file into verse-level chunks."""
    text = filepath.read_text(encoding="utf-8")
    chunks = []

    # Normalize inline verse numbers to start of line.
    # Some SBE texts (Mundaka, Prashna) pack multiple numbered verses on one line:
    #   "1. BRAHMA was the first... 2. Whatever Brahma told..."
    # The VERSE_PATTERN requires verse numbers at line start (^), so we split them.
    # Only split at numbers preceded by sentence-ending punctuation + space.
    text = re.sub(r'([.!?\'"])\s{1,2}(\d+)\.\s+', r'\1\n\2. ', text)

    # Remove intro/summary/metadata at the top (before first structural marker)
    first_section = ADHYAYA_PATTERN.search(text) or VALLI_PATTERN.search(text)
    if first_section:
        text = text[first_section.start():]

    vol = UPANISHAD_VOLUMES.get(upanishad_name, "15")
    source_url = SOURCE_URL_TEMPLATE.format(vol=vol)
    seen_verses: set[tuple[int, int]] = set()  # (chapter, verse) dedup

    # Split into sections (Adhyayas or Vallis)
    current_section = 1
    section_markers = list(VALLI_PATTERN.finditer(text))

    # If we have section markers, use them for chapter numbering
    if section_markers:
        for i, marker in enumerate(section_markers):
            section_start = marker.end()
            section_end = section_markers[i + 1].start() if i + 1 < len(section_markers) else len(text)
            section_text = text[section_start:section_end]

            # Determine section number from marker text
            marker_text = marker.group(0).upper()
            section_num = 1
            for name, num in SECTION_NAMES.items():
                if name in marker_text:
                    section_num = num
                    break

            # Extract verses from this section
            verses = VERSE_PATTERN.findall(section_text)
            for verse_num_str, verse_text in verses:
                verse_num = int(verse_num_str)
                cleaned = _clean_verse(verse_text)
                if len(cleaned) < 15:
                    continue
                if (section_num, verse_num) in seen_verses:
                    continue
                seen_verses.add((section_num, verse_num))

                chunks.append(ScriptureChunk(
                    text=cleaned,
                    scripture=upanishad_name,
                    tradition="hindu_vedanta",
                    chapter=section_num,
                    verse=verse_num,
                    translator="Max Müller",
                    year=1884 if vol == "15" else 1879,
                    language="en",
                    license_tier="A",
                    source_url=source_url,
                    chunk_type="verse",
                    verse_type="verse",
                    themes=_detect_themes(cleaned),
                ))
    else:
        # No section markers — treat entire text as one chapter
        verses = VERSE_PATTERN.findall(text)
        for verse_num_str, verse_text in verses:
            verse_num = int(verse_num_str)
            cleaned = _clean_verse(verse_text)
            if len(cleaned) < 15:
                continue
            if (1, verse_num) in seen_verses:
                continue
            seen_verses.add((1, verse_num))

            chunks.append(ScriptureChunk(
                text=cleaned,
                scripture=upanishad_name,
                tradition="hindu_vedanta",
                chapter=1,
                verse=verse_num,
                translator="Max Müller",
                year=1884 if vol == "15" else 1879,
                language="en",
                license_tier="A",
                source_url=source_url,
                chunk_type="verse",
                verse_type="verse",
                themes=_detect_themes(cleaned),
            ))

    return chunks


def _clean_verse(text: str) -> str:
    """Clean verse text: normalize whitespace, remove markdown artifacts."""
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip().rstrip("'\"")
    return text


def _detect_themes(text: str) -> list[str]:
    """Theme detection for Upanishadic concepts."""
    t = text.lower()
    themes = []
    kw = {
        "brahman": ["brahman", "brahma", "supreme", "absolute"],
        "atman": ["self", "atman", "soul", "spirit"],
        "death": ["death", "die", "mortal", "immortal"],
        "knowledge": ["know", "wisdom", "vidya", "understand"],
        "meditation": ["meditat", "contemplat", "worship"],
        "liberation": ["free", "liberat", "release", "escape"],
        "creation": ["creat", "origin", "born", "manifest"],
        "maya": ["illusion", "ignorance", "darkness", "unreal"],
    }
    for theme, keywords in kw.items():
        if any(k in t for k in keywords):
            themes.append(theme)
    return themes[:4]


if __name__ == "__main__":
    corpus_raw = Path(__file__).parent.parent.parent / "corpus" / "raw"

    katha_path = corpus_raw / "katha_upanishad_muller.txt"
    if katha_path.exists():
        chunks = parse_upanishad(katha_path, "Katha Upanishad")
        print(f"\nKatha Upanishad: {len(chunks)} verse chunks")
        if chunks:
            print(f"  Sections: {sorted(set(c.chapter for c in chunks))}")
            print(f"  Sample (1.1): {chunks[0].text[:120]}...")
            for ch in sorted(set(c.chapter for c in chunks)):
                count = len([c for c in chunks if c.chapter == ch])
                print(f"  Section {ch}: {count} verses")
    else:
        print(f"Not found: {katha_path}")
