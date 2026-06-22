"""
In-memory corpus index for fast library/reading endpoints.

Loads all processed JSON once at startup. Endpoints query this dict
instead of re-reading files on every request.

Reading quality split:
- READABLE_SCRIPTURES: clean text, human-readable → shown in reading library
- Everything else: may have OCR artifacts → indexed for RAG search only,
  NOT shown in the reading library (would confuse users with garbage text)
"""

import re
import json
from pathlib import Path
from collections import defaultdict


def _make_slug(scripture: str) -> str:
    """Derive URL-safe slug from scripture name."""
    return re.sub(r"[^a-z0-9]+", "-", scripture.lower()).strip("-")


# Scriptures whose text is clean enough for human reading.
# Sources: Project Gutenberg (digitally typeset) or SuttaCentral (CC0 JSON).
# OCR-sourced texts (IA djvu scans) are excluded — they have garbage characters,
# broken words, and scan artifacts that make reading impossible.
# These texts are STILL indexed in Qdrant for RAG search; they're just not
# shown in the reading library.
READABLE_SCRIPTURES: set[str] = {
    # ── Vedanta ────────────────────────────────────────────────────────
    "Bhagavad Gita",               # Arnold 1885, PG #2388 — clean
    "Ashtavakra Gita",             # Richards 1994, scraped — clean
    "Katha Upanishad",             # Müller SBE split — clean
    "Isha Upanishad",              # Müller SBE split — clean
    "Kena Upanishad",              # Müller SBE split — clean
    "Mundaka Upanishad",           # Müller SBE split — clean
    "Prashna Upanishad",           # Müller SBE split — clean
    "Taittiriya Upanishad",        # Müller SBE split — clean
    "Brihadaranyaka Upanishad",    # Müller SBE split — clean
    "Svetasvatara Upanishad",      # Müller SBE split — clean
    "Chandogya Upanishad",         # Müller SBE split — clean
    # "Vivekachudamani" excluded — IA djvu scan, front matter from university library
    # ── Yoga ──────────────────────────────────────────────────────────
    "Yoga Sutras",                 # Johnston 1912, PG #2526 — clean
    # ── Buddhist ──────────────────────────────────────────────────────
    "Dhammapada",                  # Sujato CC0, SuttaCentral JSON — clean
    "Digha Nikaya",                # Sujato CC0, SuttaCentral JSON — clean
    "Majjhima Nikaya",             # Sujato CC0, SuttaCentral JSON — clean
    "Samyutta Nikaya",             # Sujato CC0, SuttaCentral JSON — clean
    "Anguttara Nikaya",            # Sujato CC0, SuttaCentral JSON — clean
    # ── Modern teachers ───────────────────────────────────────────────
    "Vivekananda - Raja-Yoga",
    "Vivekananda - Karma-Yoga",
    "Vivekananda - Jnana-Yoga",
    # ── Sant/Bhakti ───────────────────────────────────────────────────
    "Songs of Kabir",              # PG #6519 — clean
}

# Vivekananda chapters are stored under these names — add dynamically
_VIVEKANANDA_BOOKS = {"Raja-Yoga", "Karma-Yoga", "Jnana-Yoga"}


def _is_readable(scripture: str) -> bool:
    """Check if a scripture should appear in the reading library."""
    if scripture in READABLE_SCRIPTURES:
        return True
    # Catch all Vivekananda books (stored as "Vivekananda - {Book}")
    for book in _VIVEKANANDA_BOOKS:
        if scripture == f"Vivekananda - {book}":
            return True
    return False


class CorpusIndex:
    def __init__(self, corpus_dir: Path):
        self.scriptures: dict[str, dict] = {}       # ALL scriptures (readable + RAG-only)
        self.readable_scriptures: dict[str, dict] = {}  # reading library only
        self.slug_to_scripture: dict[str, str] = {}
        self.chapters: dict[tuple, list] = defaultdict(list)
        self._load(corpus_dir)

    def _load(self, corpus_dir: Path):
        total = 0
        # Group chunks by scripture name first — a single JSON may hold multiple
        # scriptures (e.g. vivekananda_collected.json has Raja/Karma/Jnana Yoga)
        file_chunks: dict[str, list] = defaultdict(list)

        for json_file in sorted(corpus_dir.glob("*.json")):
            chunks = json.loads(json_file.read_text(encoding="utf-8"))
            for chunk in chunks:
                file_chunks[chunk["scripture"]].append(chunk)
            total += len(chunks)

        for scripture, chunks in file_chunks.items():
            readable = _is_readable(scripture)
            sample = chunks[0]
            slug = _make_slug(scripture)
            meta = {
                "scripture": scripture,
                "slug": slug,
                "tradition": sample["tradition"],
                "translator": sample["translator"],
                "year": sample["year"],
                "total_chapters": max(c["chapter"] for c in chunks),
                "total_verses": len(chunks),
                "license_tier": sample["license_tier"],
                "readable": readable,
            }
            self.scriptures[scripture] = meta
            if readable:
                self.readable_scriptures[scripture] = meta
            self.slug_to_scripture[slug] = scripture

            for chunk in chunks:
                key = (chunk["scripture"], chunk["chapter"])
                self.chapters[key].append(chunk)

        # Sort verses within each chapter
        for key in self.chapters:
            self.chapters[key].sort(key=lambda c: c["verse"])

        readable_count = len(self.readable_scriptures)
        print(f"  Corpus index: {len(self.scriptures)} scriptures total "
              f"({readable_count} readable, {len(self.scriptures)-readable_count} RAG-only), "
              f"{total} chunks loaded")

    def list_scriptures(self, readable_only: bool = True) -> list[dict]:
        """List scriptures. readable_only=True returns only human-readable texts
        (excludes OCR garbage sources). readable_only=False returns all."""
        source = self.readable_scriptures if readable_only else self.scriptures
        return list(source.values())

    def get_chapter(self, scripture: str, chapter: int) -> list[dict] | None:
        key = (scripture, chapter)
        verses = self.chapters.get(key)
        return verses if verses else None

    def get_verse(self, scripture: str, chapter: int, verse: int) -> dict | None:
        chapter_verses = self.get_chapter(scripture, chapter)
        if not chapter_verses:
            return None
        for v in chapter_verses:
            if v["verse"] == verse:
                return v
        return None

    def get_context(self, scripture: str, chapter: int, verse: int, window: int = 2) -> list[dict]:
        """Get surrounding ±window verses for context."""
        chapter_verses = self.get_chapter(scripture, chapter)
        if not chapter_verses:
            return []
        return [v for v in chapter_verses if abs(v["verse"] - verse) <= window]

    def resolve_slug(self, slug: str) -> str | None:
        """Convert URL slug back to scripture name. Returns None if not found."""
        return self.slug_to_scripture.get(slug)

    def get_scripture_detail(self, scripture: str) -> dict | None:
        """Get scripture metadata + chapter summaries for the table of contents page."""
        if scripture not in self.scriptures:
            return None

        chapters = []
        for (s, ch), verses in sorted(self.chapters.items()):
            if s != scripture:
                continue
            sample = verses[0] if verses else {}
            chapters.append({
                "chapter": ch,
                "name": sample.get("chapter_name"),
                "verse_count": len(verses),
                "verse_type": sample.get("verse_type", "verse"),
            })

        return {
            "scripture": self.scriptures[scripture],
            "chapters": chapters,
        }
