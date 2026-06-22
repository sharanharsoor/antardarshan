"""
Unit tests for CorpusIndex.

Tests in-memory index correctness: scripture listing, chapter lookup,
verse lookup, context window, and boundary conditions.
"""

import pytest
from pathlib import Path
from backend.corpus_index import CorpusIndex

CORPUS_PROCESSED = Path(__file__).parent.parent / "corpus" / "processed"


@pytest.fixture(scope="module")
def index():
    if not CORPUS_PROCESSED.exists() or not list(CORPUS_PROCESSED.glob("*.json")):
        pytest.skip("Corpus not processed")
    return CorpusIndex(CORPUS_PROCESSED)


class TestListScriptures:
    def test_returns_at_least_four_scriptures(self, index):
        """Count grows as corpus expands — test the floor, not an exact number."""
        scriptures = index.list_scriptures()
        assert len(scriptures) >= 4

    def test_scripture_names_present(self, index):
        names = {s["scripture"] for s in index.list_scriptures()}
        assert "Bhagavad Gita" in names
        assert "Ashtavakra Gita" in names
        assert "Dhammapada" in names
        assert "Yoga Sutras" in names

    def test_required_metadata_fields(self, index):
        for s in index.list_scriptures():
            assert "scripture" in s
            assert "tradition" in s
            assert "translator" in s
            assert "year" in s
            assert "total_chapters" in s
            assert "total_verses" in s
            assert "license_tier" in s

    def test_dhammapada_has_26_chapters(self, index):
        dhp = next(s for s in index.list_scriptures() if s["scripture"] == "Dhammapada")
        assert dhp["total_chapters"] == 26

    def test_gita_has_18_chapters(self, index):
        gita = next(s for s in index.list_scriptures() if s["scripture"] == "Bhagavad Gita")
        assert gita["total_chapters"] == 18


class TestGetChapter:
    def test_dhammapada_ch1_has_20_verses(self, index):
        verses = index.get_chapter("Dhammapada", 1)
        assert len(verses) == 20

    def test_verses_sorted_by_verse_number(self, index):
        verses = index.get_chapter("Bhagavad Gita", 2)
        nums = [v["verse"] for v in verses]
        assert nums == sorted(nums)

    def test_missing_scripture_returns_none(self, index):
        result = index.get_chapter("Fake Scripture", 1)
        assert result is None

    def test_missing_chapter_returns_none(self, index):
        result = index.get_chapter("Dhammapada", 999)
        assert result is None

    def test_all_verses_in_chapter_share_scripture(self, index):
        verses = index.get_chapter("Ashtavakra Gita", 1)
        assert all(v["scripture"] == "Ashtavakra Gita" for v in verses)
        assert all(v["chapter"] == 1 for v in verses)

    def test_no_duplicate_verse_numbers_within_any_chapter(self, index):
        """
        Within each (scripture, chapter, translator) triple, verse numbers must be unique.

        The same (scripture, chapter) CAN have multiple translators — that is intentional
        for multi-translation corpus (e.g. Arnold + Telang Gita, Sujato + Müller Dhammapada).
        We enforce uniqueness per translator within each chapter.
        """
        from collections import defaultdict
        for (scripture, chapter), verses in index.chapters.items():
            by_translator: dict[str, list[int]] = defaultdict(list)
            for v in verses:
                by_translator[v.get("translator", "")].append(v["verse"])
            for translator, verse_nums in by_translator.items():
                assert len(verse_nums) == len(set(verse_nums)), (
                    f"Duplicate verse numbers in {scripture!r} ch={chapter} "
                    f"translator={translator!r}: {[vn for vn in set(verse_nums) if verse_nums.count(vn) > 1][:5]}"
                )


class TestGetVerse:
    def test_returns_correct_verse(self, index):
        verse = index.get_verse("Dhammapada", 1, 1)
        assert verse is not None
        assert verse["scripture"] == "Dhammapada"
        assert verse["chapter"] == 1
        assert verse["verse"] == 1

    def test_missing_verse_returns_none(self, index):
        result = index.get_verse("Dhammapada", 1, 999)
        assert result is None

    def test_missing_scripture_returns_none(self, index):
        result = index.get_verse("Fake", 1, 1)
        assert result is None

    def test_verse_has_text(self, index):
        verse = index.get_verse("Ashtavakra Gita", 1, 1)
        assert verse is not None
        assert len(verse["text"]) > 10


class TestGetContext:
    def test_context_includes_target_verse(self, index):
        context = index.get_context("Dhammapada", 1, 5, window=2)
        verse_nums = [v["verse"] for v in context]
        assert 5 in verse_nums

    def test_context_window_size(self, index):
        context = index.get_context("Dhammapada", 1, 10, window=2)
        verse_nums = [v["verse"] for v in context]
        assert all(abs(n - 10) <= 2 for n in verse_nums)

    def test_context_at_first_verse_has_fewer_results(self, index):
        context_start = index.get_context("Dhammapada", 1, 1, window=2)
        context_mid = index.get_context("Dhammapada", 1, 10, window=2)
        # First verse can't have verses before it
        assert len(context_start) < len(context_mid)

    def test_context_does_not_cross_chapter_boundary(self, index):
        # Dhammapada Ch.1 last verse is 20, Ch.2 starts at 21
        context = index.get_context("Dhammapada", 1, 20, window=2)
        assert all(v["chapter"] == 1 for v in context)

    def test_missing_scripture_returns_empty(self, index):
        result = index.get_context("Fake", 1, 1, window=2)
        assert result == []
