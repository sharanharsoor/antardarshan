"""
Parser for Swami Vivekananda's lectures and essays (Wikisource, PD).

Unlike verse-based texts, Vivekananda's works are continuous prose.
We chunk by paragraph, grouping 2-3 paragraphs per chunk for context.
Each chunk carries the chapter/lecture title for retrieval context.
"""

import re
from pathlib import Path
from ingestion.schema import ScriptureChunk

SOURCE_URL = "https://en.wikisource.org/wiki/The_Complete_Works_of_Swami_Vivekananda"


def parse_vivekananda_chapter(filepath: Path, book_name: str, chapter_name: str, chapter_num: int) -> list[ScriptureChunk]:
    """Parse a single Vivekananda chapter/lecture into paragraph-level chunks."""
    text = filepath.read_text(encoding="utf-8")
    chunks = []

    # Reject stale HTML files — they produce garbage chunks
    if text.lstrip().startswith("<!") or "<html" in text[:200]:
        raise ValueError(
            f"{filepath.name} is raw HTML, not clean text. "
            f"Re-fetch with: python -m ingestion.scrapers.fetch_vivekananda --force"
        )

    # Remove footer/nav artifacts
    text = re.split(r"\n(?:Retrieved from|Public domain|This work|Categories:)", text)[0].strip()

    # Split into paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    # Filter out very short paragraphs (headers, nav artifacts)
    paragraphs = [p for p in paragraphs if len(p) > 80]

    # Group paragraphs into chunks of 2 for good context
    para_num = 0
    for i in range(0, len(paragraphs), 2):
        group = paragraphs[i:i+2]
        chunk_text = "\n\n".join(group)

        if len(chunk_text) < 100:
            continue

        para_num += 1
        chunks.append(ScriptureChunk(
            text=chunk_text,
            scripture=f"Vivekananda - {book_name}",
            tradition="hindu_vedanta",
            chapter=chapter_num,
            verse=para_num,
            translator="Swami Vivekananda",
            year=1896,
            language="en",
            license_tier="A",
            source_url=SOURCE_URL,
            chunk_type="prose",
            verse_type="stanza",
            chapter_name=chapter_name,
            themes=_detect_themes(chunk_text),
        ))

    return chunks


def _detect_themes(text: str) -> list[str]:
    """Theme detection for Vivekananda's writings."""
    t = text.lower()
    themes = []
    kw = {
        "yoga": ["yoga", "meditat", "concentrat", "samadhi"],
        "vedanta": ["vedanta", "brahman", "atman", "advaita", "non-dual"],
        "religion": ["religion", "god", "worship", "faith", "spiritual"],
        "knowledge": ["knowledge", "science", "truth", "reason", "experience"],
        "mind": ["mind", "thought", "consciousness", "psychic", "mental"],
        "freedom": ["free", "liberat", "moksha", "bondage"],
        "service": ["service", "love", "humanity", "help", "charity"],
        "strength": ["strength", "courage", "fear", "weak", "power"],
    }
    for theme, keywords in kw.items():
        if any(k in t for k in keywords):
            themes.append(theme)
    return themes[:4]


if __name__ == "__main__":
    # Test with any fetched chapter
    test_path = Path(__file__).parent.parent.parent / "corpus" / "raw" / "vivekananda_raja_yoga_intro.txt"
    if test_path.exists():
        chunks = parse_vivekananda_chapter(test_path, "Raja-Yoga", "Introductory", 1)
        print(f"Raja-Yoga Intro: {len(chunks)} chunks")
        if chunks:
            print(f"  Sample: {chunks[0].text[:150]}...")
    else:
        print(f"Test file not found: {test_path}")
        print("Fetch with: WebFetch → wikisource Vivekananda Raja-Yoga")
