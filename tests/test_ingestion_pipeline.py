"""
Unit tests for ingestion pipeline functions.

Tests build_embedding_text() and build_parent_text() in embed_and_load.py.
These are critical: they determine what gets embedded and what context
the LLM receives at generation time.
"""

from ingestion.embed_and_load import build_embedding_text, build_parent_text


def _make_chunk(scripture="Bhagavad Gita", chapter=2, verse=47,
                tradition="hindu_vedanta", chapter_name="", speaker="",
                text="You have a right to perform your actions."):
    return {
        "scripture": scripture,
        "chapter": chapter,
        "verse": verse,
        "tradition": tradition,
        "chapter_name": chapter_name,
        "speaker": speaker,
        "text": text,
    }


class TestBuildEmbeddingText:
    def test_includes_scripture_name(self):
        chunk = _make_chunk(scripture="Ashtavakra Gita")
        result = build_embedding_text(chunk)
        assert "Ashtavakra Gita" in result

    def test_includes_chapter_number(self):
        chunk = _make_chunk(chapter=5)
        result = build_embedding_text(chunk)
        assert "5" in result

    def test_includes_tradition(self):
        chunk = _make_chunk(tradition="buddhist")
        result = build_embedding_text(chunk)
        assert "buddhist" in result

    def test_includes_verse_text(self):
        chunk = _make_chunk(text="The eternal soul cannot be cut by weapons.")
        result = build_embedding_text(chunk)
        assert "eternal soul cannot be cut" in result

    def test_chapter_name_included_when_present(self):
        chunk = _make_chunk(chapter_name="Pairs")
        result = build_embedding_text(chunk)
        assert "Pairs" in result

    def test_chapter_name_not_mentioned_when_empty(self):
        chunk = _make_chunk(chapter_name="")
        result = build_embedding_text(chunk)
        # Should not have empty parentheses
        assert "()" not in result

    def test_speaker_included_when_present(self):
        chunk = _make_chunk(speaker="Janaka")
        result = build_embedding_text(chunk)
        assert "Janaka" in result

    def test_context_prefix_comes_before_text(self):
        chunk = _make_chunk(text="VERSE_MARKER", chapter=3)
        result = build_embedding_text(chunk)
        context_pos = result.index("Chapter 3")
        text_pos = result.index("VERSE_MARKER")
        assert context_pos < text_pos


class TestBuildParentText:
    def _make_corpus(self):
        """Create a minimal corpus for testing parent context building."""
        return [
            _make_chunk(scripture="Test", chapter=1, verse=v, text=f"Verse {v} text.")
            for v in range(1, 11)
        ]

    def test_excludes_the_verse_itself(self):
        corpus = self._make_corpus()
        target = corpus[4]  # verse 5
        result = build_parent_text(target, corpus)
        # Should not contain "[5]" (the target verse marker)
        assert "[5]" not in result

    def test_includes_adjacent_verses(self):
        corpus = self._make_corpus()
        target = corpus[4]  # verse 5
        result = build_parent_text(target, corpus)
        assert "[3]" in result
        assert "[4]" in result
        assert "[6]" in result
        assert "[7]" in result

    def test_does_not_include_distant_verses(self):
        corpus = self._make_corpus()
        target = corpus[4]  # verse 5
        result = build_parent_text(target, corpus)
        assert "[1]" not in result
        assert "[10]" not in result

    def test_empty_for_isolated_verse(self):
        # Single verse in a chapter — no siblings
        corpus = [_make_chunk(scripture="A", chapter=1, verse=1, text="Only verse.")]
        result = build_parent_text(corpus[0], corpus)
        assert result == ""

    def test_respects_chapter_boundary(self):
        # Two chapters, target is last verse of chapter 1
        corpus = [
            _make_chunk(scripture="A", chapter=1, verse=8, text="Ch1 V8"),
            _make_chunk(scripture="A", chapter=1, verse=9, text="Ch1 V9"),
            _make_chunk(scripture="A", chapter=1, verse=10, text="Ch1 V10"),  # target
            _make_chunk(scripture="A", chapter=2, verse=11, text="Ch2 V11"),  # different chapter
            _make_chunk(scripture="A", chapter=2, verse=12, text="Ch2 V12"),
        ]
        target = corpus[2]  # Ch1 V10
        result = build_parent_text(target, corpus)
        assert "[8]" in result
        assert "[9]" in result
        # Ch2 V11 and V12 should NOT appear (different chapter)
        assert "[11]" not in result
        assert "[12]" not in result

    def test_does_not_cross_scripture_boundary(self):
        corpus = [
            _make_chunk(scripture="Gita", chapter=1, verse=9, text="Gita V9"),
            _make_chunk(scripture="Gita", chapter=1, verse=10, text="Gita V10"),  # target
            _make_chunk(scripture="Dhammapada", chapter=1, verse=11, text="Dhp V11"),
        ]
        target = corpus[1]  # Gita V10
        result = build_parent_text(target, corpus)
        assert "Dhp V11" not in result
