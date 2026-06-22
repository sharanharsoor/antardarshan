"""
Unified chunk schema for AntarDarshan.

Every parser must output chunks conforming to this schema.
This is the contract between ingestion and the vector DB.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import hashlib
import json


@dataclass
class ScriptureChunk:
    """One atomic unit of scripture for embedding + retrieval."""

    text: str
    scripture: str
    tradition: str  # hindu_vedanta | hindu_yoga | buddhist | jain | sikh | sant_bhakti
    chapter: int
    verse: int
    translator: str
    year: int
    language: str  # en | sa | pi | ta | pa (English, Sanskrit, Pali, Tamil, Punjabi)
    license_tier: str  # A | B | C
    source_url: str
    themes: list[str] = field(default_factory=list)
    sanskrit: Optional[str] = None
    speaker: Optional[str] = None  # speaker within the text (e.g., "Janaka", "Krishna", "Arjuna")
    chapter_name: Optional[str] = None  # named section/vagga (e.g., "Pairs", "Sankhya Yoga")
    commentary_source: Optional[str] = None  # which commentary is quoted (e.g., "Shankara bhashya")
    chunk_type: str = "verse"  # verse | commentary | prose
    verse_type: str = "verse"  # verse (canonical 1:1 mapping) | stanza (poetic grouping) | segment (SuttaCentral IDs)

    @property
    def chunk_id(self) -> str:
        """Deterministic ID for Qdrant upsert. Same verse = same ID = idempotent."""
        raw = f"{self.source_url}|{self.scripture}|{self.chapter}|{self.verse}|{self.translator}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["chunk_id"] = self.chunk_id
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
