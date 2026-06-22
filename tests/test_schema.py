"""
Unit tests for the ScriptureChunk schema.

Validates: deterministic IDs, serialization, field types.
"""

from ingestion.schema import ScriptureChunk


def test_chunk_id_deterministic():
    c1 = ScriptureChunk(
        text="Test verse", scripture="Gita", tradition="hindu_vedanta",
        chapter=2, verse=47, translator="Arnold", year=1885,
        language="en", license_tier="A", source_url="http://example.com"
    )
    c2 = ScriptureChunk(
        text="Test verse", scripture="Gita", tradition="hindu_vedanta",
        chapter=2, verse=47, translator="Arnold", year=1885,
        language="en", license_tier="A", source_url="http://example.com"
    )
    assert c1.chunk_id == c2.chunk_id


def test_different_translator_different_id():
    c1 = ScriptureChunk(
        text="Same verse", scripture="Gita", tradition="hindu_vedanta",
        chapter=2, verse=47, translator="Arnold", year=1885,
        language="en", license_tier="A", source_url="http://a.com"
    )
    c2 = ScriptureChunk(
        text="Same verse", scripture="Gita", tradition="hindu_vedanta",
        chapter=2, verse=47, translator="Telang", year=1882,
        language="en", license_tier="A", source_url="http://b.com"
    )
    assert c1.chunk_id != c2.chunk_id


def test_to_dict_includes_chunk_id():
    c = ScriptureChunk(
        text="Test", scripture="AG", tradition="hindu_vedanta",
        chapter=1, verse=1, translator="Richards", year=1994,
        language="en", license_tier="A", source_url="http://x.com"
    )
    d = c.to_dict()
    assert "chunk_id" in d
    assert len(d["chunk_id"]) == 16


def test_to_dict_has_all_fields():
    c = ScriptureChunk(
        text="Test", scripture="AG", tradition="hindu_vedanta",
        chapter=1, verse=1, translator="Richards", year=1994,
        language="en", license_tier="A", source_url="http://x.com",
        speaker="Janaka", chapter_name="Liberation", themes=["self"]
    )
    d = c.to_dict()
    required_fields = ["text", "scripture", "tradition", "chapter", "verse",
                       "translator", "year", "language", "license_tier",
                       "source_url", "themes", "speaker", "chapter_name",
                       "commentary_source", "chunk_type", "verse_type", "chunk_id"]
    for field in required_fields:
        assert field in d, f"Missing field: {field}"


def test_chunk_id_is_hex():
    c = ScriptureChunk(
        text="Test", scripture="AG", tradition="hindu_vedanta",
        chapter=1, verse=1, translator="Richards", year=1994,
        language="en", license_tier="A", source_url="http://x.com"
    )
    int(c.chunk_id, 16)  # Should not raise
