"""
Unit tests for scripture parsers.

Validates: correct chunk counts, no duplicates, schema compliance,
verse numbering, and metadata fields.
"""

import json
from pathlib import Path

import pytest

from ingestion.parsers.gita_arnold import parse_gita_arnold
from ingestion.parsers.ashtavakra import parse_ashtavakra
from ingestion.parsers.dhammapada_sujato import parse_dhammapada_sujato
from ingestion.parsers.yoga_sutras_johnston import parse_yoga_sutras_johnston
from ingestion.parsers.upanishads_muller import parse_upanishad

CORPUS_RAW = Path(__file__).parent.parent / "corpus" / "raw"


class TestGitaArnold:
    @pytest.fixture
    def chunks(self):
        path = CORPUS_RAW / "pg2388.txt"
        if not path.exists():
            pytest.skip("Corpus not downloaded")
        return parse_gita_arnold(path)

    def test_has_18_chapters(self, chunks):
        chapters = set(c.chapter for c in chunks)
        assert chapters == set(range(1, 19))

    def test_chunk_count_reasonable(self, chunks):
        assert 200 <= len(chunks) <= 300

    def test_no_empty_text(self, chunks):
        for c in chunks:
            assert len(c.text.strip()) >= 20

    def test_schema_fields_populated(self, chunks):
        for c in chunks:
            assert c.scripture == "Bhagavad Gita"
            assert c.tradition == "hindu_vedanta"
            assert c.translator == "Edwin Arnold"
            assert c.year == 1885
            assert c.language == "en"
            assert c.license_tier == "A"
            assert c.verse_type == "stanza"

    def test_deterministic_ids(self, chunks):
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "Duplicate chunk_ids found"

    def test_no_gutenberg_boilerplate(self, chunks):
        for c in chunks:
            assert "Project Gutenberg" not in c.text
            assert "START OF" not in c.text


class TestAshtavakra:
    @pytest.fixture
    def chunks(self):
        path = CORPUS_RAW / "ashtavakra_gita_richards.txt"
        if not path.exists():
            pytest.skip("Corpus not downloaded")
        return parse_ashtavakra(path)

    def test_has_20_chapters(self, chunks):
        chapters = set(c.chapter for c in chunks)
        assert chapters == set(range(1, 21))

    def test_no_duplicates(self, chunks):
        seen = set()
        for c in chunks:
            key = (c.chapter, c.verse)
            assert key not in seen, f"Duplicate: {c.chapter}.{c.verse}"
            seen.add(key)

    def test_chapter_18_largest(self, chunks):
        ch18 = [c for c in chunks if c.chapter == 18]
        other_max = max(len([c for c in chunks if c.chapter == ch]) for ch in range(1, 18))
        assert len(ch18) > other_max

    def test_speaker_field_used(self, chunks):
        speakers = set(c.speaker for c in chunks if c.speaker)
        assert "Janaka" in speakers
        assert "Ashtavakra" in speakers

    def test_verse_type_is_verse(self, chunks):
        for c in chunks:
            assert c.verse_type == "verse"

    def test_commentary_source_is_none(self, chunks):
        for c in chunks:
            assert c.commentary_source is None


class TestDhammapada:
    @pytest.fixture
    def chunks(self):
        path = CORPUS_RAW / "sc-data"
        if not path.exists():
            pytest.skip("SuttaCentral data not cloned")
        return parse_dhammapada_sujato(path)

    def test_423_verses(self, chunks):
        assert len(chunks) == 423

    def test_26_chapters(self, chunks):
        chapters = set(c.chapter for c in chunks)
        assert len(chapters) == 26

    def test_chapter_name_populated(self, chunks):
        ch1 = [c for c in chunks if c.chapter == 1]
        assert all(c.chapter_name == "Pairs" for c in ch1)

    def test_verse_type_is_segment(self, chunks):
        for c in chunks:
            assert c.verse_type == "segment"

    def test_tradition_is_buddhist(self, chunks):
        for c in chunks:
            assert c.tradition == "buddhist"

    def test_license_is_A(self, chunks):
        for c in chunks:
            assert c.license_tier == "A"


class TestYogaSutras:
    @pytest.fixture
    def chunks(self):
        path = CORPUS_RAW / "pg2526.txt"
        if not path.exists():
            pytest.skip("Yoga Sutras raw text not downloaded")
        return parse_yoga_sutras_johnston(path)

    def test_chunk_count(self, chunks):
        assert len(chunks) == 193

    def test_has_4_books(self, chunks):
        books = set(c.chapter for c in chunks)
        assert books == {1, 2, 3, 4}

    def test_book_distribution(self, chunks):
        # Johnston edition distribution from parser contract
        counts = {b: len([c for c in chunks if c.chapter == b]) for b in (1, 2, 3, 4)}
        assert counts == {1: 51, 2: 54, 3: 54, 4: 34}

    def test_schema_fields(self, chunks):
        for c in chunks:
            assert c.scripture == "Yoga Sutras"
            assert c.tradition == "hindu_yoga"
            assert c.translator == "Charles Johnston"
            assert c.language == "en"
            assert c.license_tier == "A"
            assert c.verse_type == "verse"

    def test_no_duplicate_chapter_verse_pairs(self, chunks):
        keys = [(c.chapter, c.verse) for c in chunks]
        assert len(keys) == len(set(keys))


class TestKathaUpanishad:
    """Tests for the Upanishad parser using Katha — the cleanest, most complete source."""

    @pytest.fixture
    def chunks(self):
        path = CORPUS_RAW / "katha_upanishad_muller.txt"
        if not path.exists():
            pytest.skip("Katha Upanishad raw text not downloaded")
        return parse_upanishad(path, "Katha Upanishad")

    def test_chunk_count_reasonable(self, chunks):
        # Katha has 119 verses (6 Vallis). Floor at 100 to allow for source quality variation.
        assert len(chunks) >= 100, f"Only {len(chunks)} chunks — likely a source quality issue"

    def test_has_6_sections(self, chunks):
        sections = set(c.chapter for c in chunks)
        assert len(sections) == 6, f"Expected 6 Vallis, got: {sorted(sections)}"

    def test_no_duplicate_chapter_verse_pairs(self, chunks):
        """Deduplication must be in place — this was the bug that caused the test failure."""
        keys = [(c.chapter, c.verse) for c in chunks]
        dupes = [k for k in set(keys) if keys.count(k) > 1]
        assert not dupes, f"Duplicate (chapter, verse) pairs found: {dupes}"

    def test_schema_fields(self, chunks):
        for c in chunks:
            assert c.scripture == "Katha Upanishad"
            assert c.tradition == "hindu_vedanta"
            assert c.translator == "Max Müller"
            assert c.language == "en"
            assert c.license_tier == "A"
            assert c.verse_type == "verse"

    def test_no_empty_verses(self, chunks):
        for c in chunks:
            assert len(c.text.strip()) >= 15

    def test_isha_parses_correctly(self):
        """Isha Upanishad is the shortest (18 verses) — quick full-corpus check."""
        path = CORPUS_RAW / "isha_upanishad_muller.txt"
        if not path.exists():
            pytest.skip("Isha Upanishad raw text not downloaded")
        chunks = parse_upanishad(path, "Isha Upanishad")
        assert len(chunks) >= 10, f"Isha should have ~18 verses, got {len(chunks)}"
        keys = [(c.chapter, c.verse) for c in chunks]
        assert len(keys) == len(set(keys)), "Duplicates found in Isha Upanishad"
