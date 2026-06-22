"""
Parser for Bhikkhu Sujato's Dhammapada translation (SuttaCentral, CC0).

Structure: bilara JSON files with segment IDs like "dhp{verse}:{line}".
Multiple segments per verse are concatenated.
423 total verses across 26 chapters (vaggas).
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from ingestion.schema import ScriptureChunk

SOURCE_URL = "https://suttacentral.net/dhp"

# Standard Dhammapada vagga (chapter) boundaries
VAGGA_RANGES = [
    (1, 1, 20, "Pairs"),
    (2, 21, 32, "Diligence"),
    (3, 33, 43, "The Mind"),
    (4, 44, 59, "Flowers"),
    (5, 60, 75, "The Fool"),
    (6, 76, 89, "The Astute"),
    (7, 90, 99, "The Perfected Ones"),
    (8, 100, 115, "Thousands"),
    (9, 116, 128, "Wickedness"),
    (10, 129, 145, "The Rod"),
    (11, 146, 156, "Old Age"),
    (12, 157, 166, "The Self"),
    (13, 167, 178, "The World"),
    (14, 179, 196, "The Buddhas"),
    (15, 197, 208, "Happiness"),
    (16, 209, 220, "The Dear"),
    (17, 221, 234, "Anger"),
    (18, 235, 255, "Corruption"),
    (19, 256, 272, "The Just"),
    (20, 273, 289, "The Path"),
    (21, 290, 305, "Miscellaneous"),
    (22, 306, 319, "Hell"),
    (23, 320, 333, "Elephants"),
    (24, 334, 359, "Craving"),
    (25, 360, 382, "Mendicants"),
    (26, 383, 423, "Brahmins"),
]


def _verse_to_chapter(verse_num: int) -> tuple[int, str]:
    """Map absolute verse number to (chapter, chapter_name)."""
    for ch, start, end, name in VAGGA_RANGES:
        if start <= verse_num <= end:
            return ch, name
    return 0, "Unknown"


def parse_dhammapada_sujato(data_dir: Path) -> list[ScriptureChunk]:
    """Parse Sujato's Dhammapada from bilara JSON files."""
    dhp_dir = data_dir / "translation" / "en" / "sujato" / "sutta" / "kn" / "dhp"

    if not dhp_dir.exists():
        raise FileNotFoundError(f"Dhammapada dir not found: {dhp_dir}")

    # Collect all segments from all JSON files
    all_segments: dict[str, str] = {}
    for json_file in sorted(dhp_dir.glob("dhp*_translation-en-sujato.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        all_segments.update(data)

    # Group segments by verse number
    verses: dict[int, list[str]] = defaultdict(list)
    segment_pattern = re.compile(r"^dhp(\d+):(\d+(?:\.\d+)?)$")

    for key, text in all_segments.items():
        match = segment_pattern.match(key)
        if not match:
            continue

        verse_num = int(match.group(1))
        line_id = match.group(2)

        # Skip headers (0.x segments)
        if line_id.startswith("0"):
            continue

        verses[verse_num].append(text.strip())

    # Build chunks
    chunks = []
    for verse_num in sorted(verses.keys()):
        lines = verses[verse_num]
        verse_text = " ".join(lines)

        if len(verse_text) < 5:
            continue

        chapter, chapter_name = _verse_to_chapter(verse_num)

        chunks.append(ScriptureChunk(
            text=verse_text,
            scripture="Dhammapada",
            tradition="buddhist",
            chapter=chapter,
            verse=verse_num,
            translator="Bhikkhu Sujato",
            year=2021,
            language="en",
            license_tier="A",
            source_url=SOURCE_URL,
            chunk_type="verse",
            verse_type="segment",
            themes=_detect_themes(verse_text),
            chapter_name=chapter_name,
        ))

    return chunks


def _detect_themes(text: str) -> list[str]:
    """Basic keyword-based theme tagging for Buddhist concepts."""
    text_lower = text.lower()
    themes = []
    theme_keywords = {
        "suffering": ["suffer", "pain", "sorrow", "grief", "dukkha"],
        "impermanence": ["imperma", "change", "decay", "death", "old age"],
        "mindfulness": ["mindful", "aware", "diligen", "heedful", "vigilant"],
        "compassion": ["compassion", "love", "kindness", "gentle"],
        "wisdom": ["wise", "wisdom", "discern", "understand"],
        "karma": ["action", "deed", "intention", "result", "consequence"],
        "liberation": ["free", "nibbana", "liberat", "release", "unbound"],
        "ethics": ["virtue", "righteous", "evil", "good", "moral", "precept"],
        "meditation": ["meditat", "concentrat", "jhana", "calm", "still"],
        "attachment": ["attach", "cling", "crav", "desire", "thirst"],
    }
    for theme, keywords in theme_keywords.items():
        if any(kw in text_lower for kw in keywords):
            themes.append(theme)
    return themes[:4]


if __name__ == "__main__":
    data_dir = Path(__file__).parent.parent.parent / "corpus" / "raw" / "sc-data"
    if not data_dir.exists():
        print(f"SuttaCentral data not found: {data_dir}")
        print("Run: git clone --depth=1 https://github.com/suttacentral/bilara-data.git corpus/raw/sc-data")
        exit(1)

    chunks = parse_dhammapada_sujato(data_dir)
    print(f"\nParsed {len(chunks)} verse chunks from 26 chapters (vaggas)")
    print(f"\nSample chunk (Verse 1):")
    v1 = [c for c in chunks if c.verse == 1]
    if v1:
        sample = v1[0]
        print(f"  ID: {sample.chunk_id}")
        print(f"  Chapter: {sample.chapter} ({sample.commentary_source})")
        print(f"  Themes: {sample.themes}")
        print(f"  Text: {sample.text[:150]}...")
    print(f"\nChapter distribution:")
    for ch, start, end, name in VAGGA_RANGES:
        count = len([c for c in chunks if c.chapter == ch])
        print(f"  Ch {ch:2d} ({name:20s}): {count} verses")
