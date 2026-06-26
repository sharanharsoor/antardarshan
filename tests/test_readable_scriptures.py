"""
Tests for READABLE_SCRIPTURES registry and _is_readable() logic.

Covers all additions made in the 2026-06-27 corpus expansion session:
- Mahabharata, Ramayana (epics)
- Sutta Nipata, Udana, Itivuttaka, Theragatha, Therigatha (KN sub-collections)
- Mandukya, Aitareya, Kaushitaki, Maitri Upanishads (new Upanishads)
- Vivekananda dynamic pattern still works
- RAG-only texts correctly excluded
"""

import pytest
from pathlib import Path

from backend.corpus_index import READABLE_SCRIPTURES, _is_readable


# ── _is_readable() unit tests ──────────────────────────────────────────────────

class TestIsReadable:

    # Core Vedanta — always been there
    def test_bhagavad_gita_readable(self):
        assert _is_readable("Bhagavad Gita")

    def test_ashtavakra_gita_readable(self):
        assert _is_readable("Ashtavakra Gita")

    def test_yoga_sutras_readable(self):
        assert _is_readable("Yoga Sutras")

    # Original 9 Upanishads
    def test_katha_upanishad_readable(self):
        assert _is_readable("Katha Upanishad")

    def test_isha_upanishad_readable(self):
        assert _is_readable("Isha Upanishad")

    def test_kena_upanishad_readable(self):
        assert _is_readable("Kena Upanishad")

    def test_mundaka_upanishad_readable(self):
        assert _is_readable("Mundaka Upanishad")

    def test_prashna_upanishad_readable(self):
        assert _is_readable("Prashna Upanishad")

    def test_taittiriya_upanishad_readable(self):
        assert _is_readable("Taittiriya Upanishad")

    def test_brihadaranyaka_upanishad_readable(self):
        assert _is_readable("Brihadaranyaka Upanishad")

    def test_svetasvatara_upanishad_readable(self):
        assert _is_readable("Svetasvatara Upanishad")

    def test_chandogya_upanishad_readable(self):
        assert _is_readable("Chandogya Upanishad")

    # New Upanishads added 2026-06-27
    def test_mandukya_upanishad_readable(self):
        assert _is_readable("Mandukya Upanishad")

    def test_aitareya_upanishad_readable(self):
        assert _is_readable("Aitareya Upanishad")

    def test_kaushitaki_upanishad_readable(self):
        assert _is_readable("Kaushitaki Upanishad")

    def test_maitri_upanishad_readable(self):
        assert _is_readable("Maitri Upanishad")

    # Epics added 2026-06-27
    def test_mahabharata_readable(self):
        assert _is_readable("Mahabharata")

    def test_ramayana_readable(self):
        assert _is_readable("Ramayana")

    # KN sub-collections added 2026-06-27
    def test_sutta_nipata_readable(self):
        assert _is_readable("Sutta Nipata")

    def test_udana_readable(self):
        assert _is_readable("Udana")

    def test_itivuttaka_readable(self):
        assert _is_readable("Itivuttaka")

    def test_theragatha_readable(self):
        assert _is_readable("Theragatha")

    def test_therigatha_readable(self):
        assert _is_readable("Therigatha")

    # Main Nikayas
    def test_digha_nikaya_readable(self):
        assert _is_readable("Digha Nikaya")

    def test_majjhima_nikaya_readable(self):
        assert _is_readable("Majjhima Nikaya")

    def test_samyutta_nikaya_readable(self):
        assert _is_readable("Samyutta Nikaya")

    def test_anguttara_nikaya_readable(self):
        assert _is_readable("Anguttara Nikaya")

    def test_dhammapada_readable(self):
        assert _is_readable("Dhammapada")

    def test_songs_of_kabir_readable(self):
        assert _is_readable("Songs of Kabir")

    # Vivekananda dynamic pattern
    def test_vivekananda_raja_yoga_readable(self):
        assert _is_readable("Vivekananda - Raja-Yoga")

    def test_vivekananda_karma_yoga_readable(self):
        assert _is_readable("Vivekananda - Karma-Yoga")

    def test_vivekananda_jnana_yoga_readable(self):
        assert _is_readable("Vivekananda - Jnana-Yoga")

    # RAG-only — must NOT be readable
    def test_manu_smriti_not_readable(self):
        assert not _is_readable("Manu Smriti")

    def test_arthashastra_not_readable(self):
        assert not _is_readable("Arthashastra")

    def test_agni_purana_not_readable(self):
        assert not _is_readable("Agni Purana")

    def test_markandeya_purana_not_readable(self):
        assert not _is_readable("Markandeya Purana")

    def test_nyaya_sutras_not_readable(self):
        assert not _is_readable("Nyaya Sutras")

    def test_vaisheshika_sutras_not_readable(self):
        assert not _is_readable("Vaisheshika Sutras")

    def test_nonexistent_scripture_not_readable(self):
        assert not _is_readable("Fake Scripture XYZ")

    def test_partial_match_not_readable(self):
        """Substring match must not make something readable."""
        assert not _is_readable("Katha")           # not "Katha Upanishad"
        assert not _is_readable("Mahabharata Epic") # not exact "Mahabharata"

    def test_case_sensitivity(self):
        """Names are case-sensitive — wrong case must return False."""
        assert not _is_readable("bhagavad gita")
        assert not _is_readable("MAHABHARATA")
        assert not _is_readable("sutta nipata")


# ── READABLE_SCRIPTURES set completeness ──────────────────────────────────────

class TestReadableScripturesSet:

    def test_all_13_principal_upanishads_present(self):
        """All 13 principal Upanishads (Mukhya Upanishads) must be readable."""
        principal = [
            "Isha Upanishad",
            "Kena Upanishad",
            "Katha Upanishad",
            "Prashna Upanishad",
            "Mundaka Upanishad",
            "Mandukya Upanishad",
            "Taittiriya Upanishad",
            "Aitareya Upanishad",
            "Chandogya Upanishad",
            "Brihadaranyaka Upanishad",
            "Svetasvatara Upanishad",
            "Kaushitaki Upanishad",
            "Maitri Upanishad",
        ]
        missing = [u for u in principal if u not in READABLE_SCRIPTURES]
        assert not missing, f"Principal Upanishads missing from READABLE_SCRIPTURES: {missing}"

    def test_five_kn_sub_collections_present(self):
        kn_texts = ["Sutta Nipata", "Udana", "Itivuttaka", "Theragatha", "Therigatha"]
        missing = [t for t in kn_texts if t not in READABLE_SCRIPTURES]
        assert not missing, f"KN texts missing: {missing}"

    def test_epics_present(self):
        assert "Mahabharata" in READABLE_SCRIPTURES
        assert "Ramayana" in READABLE_SCRIPTURES

    def test_minimum_size(self):
        """Set must have grown with all additions — floor check."""
        assert len(READABLE_SCRIPTURES) >= 30, (
            f"READABLE_SCRIPTURES too small: {len(READABLE_SCRIPTURES)} entries"
        )

    def test_no_duplicates_in_set(self):
        """Sets cannot have duplicates by definition — verify no entry appears twice
        when we convert from set to list (sanity check for refactors)."""
        as_list = list(READABLE_SCRIPTURES)
        assert len(as_list) == len(set(as_list))


# ── CorpusIndex integration: readable flag propagates correctly ────────────────

class TestCorpusIndexReadableFlag:
    """Integration tests against the actual corpus — skipped without processed data."""

    CORPUS_PROCESSED = Path(__file__).parent.parent / "corpus" / "processed"

    @pytest.fixture()
    def index(self):
        from backend.corpus_index import CorpusIndex
        if not self.CORPUS_PROCESSED.exists() or not list(self.CORPUS_PROCESSED.glob("*.json")):
            pytest.skip("Corpus not processed")
        return CorpusIndex(self.CORPUS_PROCESSED)

    def test_mahabharata_in_readable_library(self, index):
        readable = {s["scripture"] for s in index.list_scriptures(readable_only=True)}
        assert "Mahabharata" in readable

    def test_ramayana_in_readable_library(self, index):
        readable = {s["scripture"] for s in index.list_scriptures(readable_only=True)}
        assert "Ramayana" in readable

    def test_sutta_nipata_in_readable_library(self, index):
        readable = {s["scripture"] for s in index.list_scriptures(readable_only=True)}
        assert "Sutta Nipata" in readable

    def test_therigatha_in_readable_library(self, index):
        readable = {s["scripture"] for s in index.list_scriptures(readable_only=True)}
        assert "Therigatha" in readable

    def test_manu_smriti_not_in_readable_library(self, index):
        readable = {s["scripture"] for s in index.list_scriptures(readable_only=True)}
        assert "Manu Smriti" not in readable

    def test_all_readable_are_in_readable_scriptures(self, index):
        """Every scripture the index exposes as readable must be in READABLE_SCRIPTURES."""
        for s in index.list_scriptures(readable_only=True):
            assert _is_readable(s["scripture"]), (
                f"Corpus index says {s['scripture']!r} is readable "
                f"but _is_readable() returns False"
            )
