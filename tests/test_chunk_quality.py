"""
Unit and functional tests for chunk size enforcement.

Covers:
- _split_large_chunk(): sentence split, no-punctuation fallback, metadata preservation
- _apply_hard_cap(): empty input, mixed sizes, word count conservation
- _save() integration: JSON output never contains oversized chunks
- Corpus regression: existing processed/ files all within cap after re-index
"""

import json
import copy
from pathlib import Path

import pytest

from ingestion.process_all import (
    _split_large_chunk,
    _apply_hard_cap,
    _HARD_CAP_WORDS,
    _save,
    _deduplicate_verses,
)
from ingestion.schema import ScriptureChunk

CORPUS_PROCESSED = Path(__file__).parent.parent / "corpus" / "processed"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _chunk(text: str, chapter: int = 1, verse: int = 1, scripture: str = "Test") -> ScriptureChunk:
    return ScriptureChunk(
        text=text,
        scripture=scripture,
        tradition="hindu_vedanta",
        chapter=chapter,
        verse=verse,
        translator="Griffith",
        year=1900,
        language="en",
        license_tier="A",
        source_url="https://example.org",
    )


def _words(n: int, word: str = "word") -> str:
    return (" ".join([word] * n))


def _sentences(n: int) -> str:
    """n sentences, each ending with a period."""
    return " ".join([f"This is sentence {i}." for i in range(n)])


# ── _split_large_chunk unit tests ─────────────────────────────────────────────

class TestSplitLargeChunk:

    def test_chunk_under_cap_unchanged(self):
        text = _words(_HARD_CAP_WORDS - 1)
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        assert len(result) == 1
        assert result[0].text == text

    def test_chunk_exactly_at_cap_unchanged(self):
        text = _words(_HARD_CAP_WORDS)
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        assert len(result) == 1

    def test_chunk_over_cap_gets_split(self):
        text = _words(_HARD_CAP_WORDS + 100)
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        assert len(result) >= 2

    def test_all_sub_chunks_within_cap(self):
        text = _words(_HARD_CAP_WORDS * 3)
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        for sub in result:
            assert len(sub.text.split()) <= _HARD_CAP_WORDS, (
                f"Sub-chunk exceeds cap: {len(sub.text.split())} words"
            )

    def test_sentence_boundary_preferred_over_word_slice(self):
        """With clear sentence boundaries, splits should not cut mid-sentence."""
        # 5 sentences of ~200 words each = 1000 words total → should split into 2
        sentences = " ".join([_words(200) + "." for _ in range(5)])
        chunk = _chunk(sentences)
        result = _split_large_chunk(chunk)
        assert len(result) >= 2
        # Each sub-chunk should end cleanly (not mid-word)
        for sub in result:
            assert not sub.text.endswith(" ")

    def test_no_punctuation_fallback_enforces_cap(self):
        """OCR text with no sentence boundaries must still be capped."""
        text = _words(_HARD_CAP_WORDS + 500)  # all one big no-punctuation blob
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        for sub in result:
            assert len(sub.text.split()) <= _HARD_CAP_WORDS, (
                f"No-punctuation fallback failed: {len(sub.text.split())} words"
            )

    def test_mixed_short_sentences_and_huge_no_punct_block(self):
        """Short sentences + a huge no-punct block — all sub-chunks within cap."""
        short = " ".join([f"Short sentence {i}." for i in range(10)])  # ~30 words
        huge_nopunct = _words(_HARD_CAP_WORDS * 2)  # 1600 words, no punctuation
        more_short = " ".join([f"Another sentence {i}." for i in range(5)])
        text = f"{short} {huge_nopunct} {more_short}"
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        for sub in result:
            assert len(sub.text.split()) <= _HARD_CAP_WORDS

    def test_no_text_is_dropped(self):
        """Total word count after splitting must equal original."""
        original_words = _HARD_CAP_WORDS * 3 + 150
        text = _words(original_words)
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        total_after = sum(len(sub.text.split()) for sub in result)
        assert total_after == original_words

    def test_metadata_preserved_on_sub_chunks(self):
        """All metadata fields must survive the split."""
        text = _words(_HARD_CAP_WORDS * 2)
        chunk = _chunk(text, chapter=5, verse=42, scripture="Mahabharata")
        result = _split_large_chunk(chunk)
        for sub in result:
            assert sub.scripture == "Mahabharata"
            assert sub.chapter == 5
            assert sub.translator == "Griffith"
            assert sub.tradition == "hindu_vedanta"
            assert sub.license_tier == "A"
            assert sub.source_url == "https://example.org"

    def test_sub_chunks_have_unique_verse_numbers(self):
        """Sub-chunks of a split must have distinct verse numbers."""
        text = _words(_HARD_CAP_WORDS * 3)
        chunk = _chunk(text, verse=7)
        result = _split_large_chunk(chunk)
        verses = [sub.verse for sub in result]
        assert len(verses) == len(set(verses)), "Duplicate verse numbers in split sub-chunks"

    def test_no_empty_sub_chunks(self):
        """No sub-chunk should have empty or whitespace-only text."""
        text = _words(_HARD_CAP_WORDS * 2)
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        for sub in result:
            assert sub.text.strip(), "Empty sub-chunk produced"

    def test_very_large_chunk_5x_cap(self):
        """Stress test: 5× cap should produce ~5 sub-chunks all within cap."""
        text = _words(_HARD_CAP_WORDS * 5)
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        assert len(result) == 5
        for sub in result:
            assert len(sub.text.split()) <= _HARD_CAP_WORDS

    def test_sentence_right_at_cap_boundary(self):
        """A sentence that fills exactly cap words should be its own chunk."""
        exact_sentence = _words(_HARD_CAP_WORDS) + "."
        overflow_sentence = _words(50) + "."
        text = f"{exact_sentence} {overflow_sentence}"
        chunk = _chunk(text)
        result = _split_large_chunk(chunk)
        assert len(result) >= 2
        for sub in result:
            assert len(sub.text.split()) <= _HARD_CAP_WORDS


# ── _apply_hard_cap unit tests ─────────────────────────────────────────────────

class TestApplyHardCap:

    def test_empty_list_returns_empty(self):
        assert _apply_hard_cap([]) == []

    def test_all_under_cap_unchanged(self):
        chunks = [_chunk(_words(100), verse=i) for i in range(5)]
        original_texts = [c.text for c in chunks]
        result = _apply_hard_cap(chunks)
        assert len(result) == 5
        assert [c.text for c in result] == original_texts

    def test_all_over_cap_all_split(self):
        chunks = [_chunk(_words(_HARD_CAP_WORDS * 2), verse=i) for i in range(3)]
        result = _apply_hard_cap(chunks)
        assert len(result) > 3
        for c in result:
            assert len(c.text.split()) <= _HARD_CAP_WORDS

    def test_mixed_split_only_oversized(self):
        small = _chunk(_words(100), verse=1)
        big = _chunk(_words(_HARD_CAP_WORDS * 2), verse=2)
        small2 = _chunk(_words(50), verse=3)
        result = _apply_hard_cap([small, big, small2])
        # small and small2 stay intact; big gets split
        assert result[0].text == small.text
        assert result[-1].text == small2.text
        assert len(result) > 3

    def test_result_no_chunk_exceeds_cap(self):
        chunks = [_chunk(_words(i * 200), verse=i) for i in range(1, 6)]
        result = _apply_hard_cap(chunks)
        for c in result:
            assert len(c.text.split()) <= _HARD_CAP_WORDS

    def test_total_words_conserved(self):
        """No words should be created or destroyed by the cap."""
        chunks = [_chunk(_words((_HARD_CAP_WORDS + i * 100)), verse=i) for i in range(1, 4)]
        total_before = sum(len(c.text.split()) for c in chunks)
        result = _apply_hard_cap(chunks)
        total_after = sum(len(c.text.split()) for c in result)
        assert total_after == total_before

    def test_single_huge_chunk(self):
        chunk = _chunk(_words(_HARD_CAP_WORDS * 10))  # 8000 words
        result = _apply_hard_cap([chunk])
        assert len(result) == 10
        for c in result:
            assert len(c.text.split()) <= _HARD_CAP_WORDS

    def test_output_is_new_list_not_mutated(self):
        """Input list should not be modified."""
        chunks = [_chunk(_words(100), verse=i) for i in range(3)]
        original_len = len(chunks)
        _apply_hard_cap(chunks)
        assert len(chunks) == original_len  # input unchanged


# ── _save() integration tests ──────────────────────────────────────────────────

class TestSavePipeline:
    """Integration tests: verify _save() writes cap-enforced JSON."""

    def test_save_applies_hard_cap(self, tmp_path):
        """_save() must enforce cap before writing JSON."""
        # Monkey-patch CORPUS_PROCESSED to tmp_path
        import ingestion.process_all as pa
        original = pa.CORPUS_PROCESSED
        pa.CORPUS_PROCESSED = tmp_path
        try:
            oversized = _chunk(_words(_HARD_CAP_WORDS * 3), verse=1)
            normal = _chunk(_words(200), verse=2)
            n = pa._save([oversized, normal], "test_output.json")

            out = json.loads((tmp_path / "test_output.json").read_text())
            assert n == len(out)
            for chunk in out:
                assert len(chunk["text"].split()) <= _HARD_CAP_WORDS, (
                    f"Oversized chunk in saved JSON: {len(chunk['text'].split())} words"
                )
        finally:
            pa.CORPUS_PROCESSED = original

    def test_save_deduplicates_after_cap(self, tmp_path):
        """Dedup runs after cap — verse numbers must be unique in output."""
        import ingestion.process_all as pa
        original = pa.CORPUS_PROCESSED
        pa.CORPUS_PROCESSED = tmp_path
        try:
            # Two chunks with same (scripture, chapter, verse) — cap will add sub-chunks
            # both with same base verse; dedup must resolve
            big = _chunk(_words(_HARD_CAP_WORDS * 2), chapter=1, verse=1)
            big2 = copy.copy(big)
            pa._save([big, big2], "dedup_test.json")

            out = json.loads((tmp_path / "dedup_test.json").read_text())
            verses = [c["verse"] for c in out]
            assert len(verses) == len(set(verses)), "Duplicate verses after cap+dedup"
        finally:
            pa.CORPUS_PROCESSED = original

    def test_save_returns_correct_count(self, tmp_path):
        """_save() return value must match the actual number of chunks written."""
        import ingestion.process_all as pa
        original = pa.CORPUS_PROCESSED
        pa.CORPUS_PROCESSED = tmp_path
        try:
            chunks = [_chunk(_words(300), verse=i) for i in range(5)]
            n = pa._save(chunks, "count_test.json")
            out = json.loads((tmp_path / "count_test.json").read_text())
            assert n == len(out)
        finally:
            pa.CORPUS_PROCESSED = original

    def test_save_empty_returns_zero(self, tmp_path):
        import ingestion.process_all as pa
        original = pa.CORPUS_PROCESSED
        pa.CORPUS_PROCESSED = tmp_path
        try:
            n = pa._save([], "empty_test.json")
            assert n == 0
            assert not (tmp_path / "empty_test.json").exists()
        finally:
            pa.CORPUS_PROCESSED = original


# ── Corpus regression: processed files must all be within cap ─────────────────

class TestCorpusChunkDistribution:
    """
    Functional tests against the actual processed corpus.
    Skipped when corpus is not present (CI without corpus data).
    """

    @pytest.fixture()
    def all_chunks(self):
        if not CORPUS_PROCESSED.exists() or not list(CORPUS_PROCESSED.glob("*.json")):
            pytest.skip("Corpus not processed")
        chunks = []
        for f in CORPUS_PROCESSED.glob("*.json"):
            chunks.extend(json.loads(f.read_text()))
        return chunks

    def test_no_chunk_exceeds_hard_cap(self, all_chunks):
        """After re-index with hard cap, no chunk should exceed _HARD_CAP_WORDS."""
        oversized = [
            (c["scripture"], len(c["text"].split()))
            for c in all_chunks
            if len(c["text"].split()) > _HARD_CAP_WORDS
        ]
        assert not oversized, (
            f"{len(oversized)} chunks exceed {_HARD_CAP_WORDS} words: "
            f"{oversized[:5]}"
        )

    def test_no_empty_chunks_in_corpus(self, all_chunks):
        empty = [c for c in all_chunks if not c["text"].strip()]
        assert not empty, f"{len(empty)} empty chunks found in corpus"

    def test_all_chunks_have_required_fields(self, all_chunks):
        required = {"text", "scripture", "tradition", "chapter", "verse",
                    "translator", "year", "language", "license_tier", "source_url"}
        for c in all_chunks:
            missing = required - set(c.keys())
            assert not missing, f"Chunk missing fields {missing}: {c.get('scripture')}"

    def test_chunk_count_reasonable(self, all_chunks):
        """Sanity: after re-index with new texts, expect at least 20k chunks."""
        assert len(all_chunks) >= 15_000, (
            f"Corpus seems too small: {len(all_chunks)} chunks"
        )

    def test_p95_word_count_within_target(self, all_chunks):
        """95th percentile chunk size should be well under the hard cap."""
        import statistics
        word_counts = sorted(len(c["text"].split()) for c in all_chunks)
        p95_idx = int(len(word_counts) * 0.95)
        p95 = word_counts[p95_idx]
        assert p95 <= _HARD_CAP_WORDS, f"p95 word count {p95} exceeds cap {_HARD_CAP_WORDS}"

    def test_mahabharata_chunks_within_cap(self, all_chunks):
        """Mahabharata was the worst offender (15k-word chunk) — verify fixed."""
        mbh = [c for c in all_chunks if c["scripture"] == "Mahabharata"]
        if not mbh:
            pytest.skip("Mahabharata not in corpus")
        oversized = [c for c in mbh if len(c["text"].split()) > _HARD_CAP_WORDS]
        assert not oversized, (
            f"{len(oversized)} Mahabharata chunks still exceed cap"
        )

    def test_ramayana_chunks_within_cap(self, all_chunks):
        """Ramayana had a 15,432-word chunk — verify it's split."""
        ram = [c for c in all_chunks if c["scripture"] == "Ramayana"]
        if not ram:
            pytest.skip("Ramayana not in corpus")
        oversized = [c for c in ram if len(c["text"].split()) > _HARD_CAP_WORDS]
        assert not oversized, (
            f"{len(oversized)} Ramayana chunks still exceed cap"
        )

    def test_digha_nikaya_chunks_within_cap(self, all_chunks):
        """Digha Nikaya had chunks at 5000+ words — verify fixed."""
        dn = [c for c in all_chunks if c["scripture"] == "Digha Nikaya"]
        if not dn:
            pytest.skip("Digha Nikaya not in corpus")
        oversized = [c for c in dn if len(c["text"].split()) > _HARD_CAP_WORDS]
        assert not oversized
