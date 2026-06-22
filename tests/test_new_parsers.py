"""
Tests for new corpus parsers: Pali Canon, Telang Gita, SBE prose, Vedas, Epics.

All parser tests use pytest.skip if the raw corpus file is not present,
so CI passes even without the full corpus downloaded.
"""

import json
from pathlib import Path

import pytest

CORPUS_RAW = Path(__file__).parent.parent / "corpus" / "raw"
SC_DATA = CORPUS_RAW / "sc-data"


# ─── Pali Canon (SuttaCentral bilara) ─────────────────────────────────────────

class TestPaliCanonParser:
    def test_parse_single_mn_sutta(self):
        """Parse one MN JSON file and verify output shape."""
        mn_dir = SC_DATA / "translation" / "en" / "sujato" / "sutta" / "mn"
        if not mn_dir.exists():
            pytest.skip("SuttaCentral data not available")

        from ingestion.parsers.pali_canon_sujato import parse_sutta_file

        json_files = sorted(mn_dir.glob("*_translation-en-sujato.json"))
        assert json_files, "No MN sutta files found"

        chunks = parse_sutta_file(json_files[0])
        assert len(chunks) >= 1

        for c in chunks:
            assert c.scripture == "Majjhima Nikaya"
            assert c.tradition == "buddhist"
            assert c.translator == "Bhikkhu Sujato"
            assert c.license_tier == "A"
            assert c.language == "en"
            assert len(c.text) > 20

    def test_parse_nikaya_mn(self):
        """Parse full MN and verify sutta count."""
        mn_dir = SC_DATA / "translation" / "en" / "sujato" / "sutta" / "mn"
        if not mn_dir.exists():
            pytest.skip("SuttaCentral data not available")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya

        chunks = parse_nikaya(mn_dir, "mn")
        assert len(chunks) >= 100, f"MN should have ≥100 chunks, got {len(chunks)}"

    def test_parse_nikaya_dn(self):
        """Parse full DN."""
        dn_dir = SC_DATA / "translation" / "en" / "sujato" / "sutta" / "dn"
        if not dn_dir.exists():
            pytest.skip("SuttaCentral data not available")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya

        chunks = parse_nikaya(dn_dir, "dn")
        assert len(chunks) >= 20

    def test_no_empty_chunks(self):
        """No chunk should have empty text."""
        mn_dir = SC_DATA / "translation" / "en" / "sujato" / "sutta" / "mn"
        if not mn_dir.exists():
            pytest.skip("SuttaCentral data not available")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya

        chunks = parse_nikaya(mn_dir, "mn")
        for c in chunks:
            assert c.text.strip(), f"Empty chunk found: {c.scripture} ch={c.chapter} v={c.verse}"

    def test_no_duplicate_ids(self):
        """Chunk IDs must be unique within a Nikaya."""
        mn_dir = SC_DATA / "translation" / "en" / "sujato" / "sutta" / "mn"
        if not mn_dir.exists():
            pytest.skip("SuttaCentral data not available")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya

        chunks = parse_nikaya(mn_dir, "mn")
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "Duplicate chunk_ids found in MN"

    def test_all_chunks_have_source_url(self):
        """Every chunk must have a non-empty source URL."""
        mn_dir = SC_DATA / "translation" / "en" / "sujato" / "sutta" / "mn"
        if not mn_dir.exists():
            pytest.skip("SuttaCentral data not available")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya

        chunks = parse_nikaya(mn_dir, "mn")
        for c in chunks:
            assert c.source_url and "suttacentral" in c.source_url.lower()


# ─── Telang Gita ──────────────────────────────────────────────────────────────

class TestTelangGitaParser:
    @pytest.fixture
    def telang_path(self):
        path = CORPUS_RAW / "bhagavad_gita_telang_sbe08.txt"
        if not path.exists():
            pytest.skip("Telang Gita not downloaded")
        return path

    def test_finds_three_texts(self, telang_path):
        """Should find Gita, Sanatsugatiya, and Anugita."""
        from ingestion.parsers.gita_telang import parse_telang_sbe08

        result = parse_telang_sbe08(telang_path)
        assert "gita" in result
        assert "sanatsujatiya" in result
        assert "anugita" in result

    def test_gita_has_multiple_chapters(self, telang_path):
        """
        Bhagavad Gita should produce chunks across multiple chapters.

        Note: this OCR scan has inconsistent chapter header formatting — some
        chapters appear as inline cross-references (e.g. 'CHAPTER III, 13. 53')
        rather than standalone headers, so we cannot guarantee all 18 chapters.
        We should recover most chapter boundaries, including chapter 18.
        """
        from ingestion.parsers.gita_telang import parse_telang_sbe08

        result = parse_telang_sbe08(telang_path)
        gita_chunks = result["gita"]
        assert len(gita_chunks) >= 15, f"Expected ≥15 Gita chunks, got {len(gita_chunks)}"

        chapters = {c.chapter for c in gita_chunks}
        assert len(chapters) >= 15, f"Too few distinct chapters: {sorted(chapters)}"
        assert 1 in chapters and 18 in chapters, f"Expected chapter range to include 1 and 18, got {sorted(chapters)}"

    def test_gita_metadata(self, telang_path):
        """All Gita chunks should have correct translator/year."""
        from ingestion.parsers.gita_telang import parse_telang_sbe08

        result = parse_telang_sbe08(telang_path)
        for c in result["gita"]:
            # Uses distinct name so CorpusIndex doesn't merge with Arnold translation
            assert c.scripture == "Bhagavad Gita (Telang)"
            assert c.translator == "K.T. Telang"
            assert c.year == 1882
            assert c.tradition == "hindu_vedanta"
            assert c.license_tier == "A"

    def test_no_empty_gita_chunks(self, telang_path):
        from ingestion.parsers.gita_telang import parse_telang_sbe08

        result = parse_telang_sbe08(telang_path)
        for c in result["gita"]:
            assert len(c.text.strip()) > 20

    def test_sanatsugatiya_has_content(self, telang_path):
        from ingestion.parsers.gita_telang import parse_telang_sbe08

        result = parse_telang_sbe08(telang_path)
        # Sanatsugatiya may not always be present depending on file format
        if result["sanatsujatiya"]:
            for c in result["sanatsujatiya"]:
                assert c.scripture == "Sanatsugatiya"
                assert len(c.text) > 20


# ─── SBE Prose Parser ─────────────────────────────────────────────────────────

class TestSBEProseParser:
    def test_manu_smriti(self):
        path = CORPUS_RAW / "manu_smriti_buhler_sbe25.txt"
        if not path.exists():
            pytest.skip("Manu Smriti not downloaded")

        from ingestion.parsers.sbe_prose import parse_manu_smriti

        chunks = parse_manu_smriti(path)
        assert len(chunks) >= 10
        for c in chunks:
            assert c.scripture == "Manu Smriti"
            assert c.tradition == "hindu_vedanta"
            assert c.license_tier == "A"
            assert len(c.text.split()) >= 20

    def test_arthashastra(self):
        path = CORPUS_RAW / "arthashastra_shamasastry_1915.txt"
        if not path.exists():
            pytest.skip("Arthashastra not downloaded")

        from ingestion.parsers.sbe_prose import parse_arthashastra

        chunks = parse_arthashastra(path)
        assert len(chunks) >= 5

    def test_milindapanha(self):
        path = CORPUS_RAW / "milindapanha_rhys_davids_1890.txt"
        if not path.exists():
            pytest.skip("Milindapanha not downloaded")

        from ingestion.parsers.sbe_prose import parse_milindapanha

        chunks = parse_milindapanha(path)
        assert len(chunks) >= 5
        for c in chunks:
            assert c.tradition == "buddhist"

    def test_nyaya_sutras(self):
        path = CORPUS_RAW / "nyaya_sutras_vidyabhusana_1913.txt"
        if not path.exists():
            pytest.skip("Nyaya Sutras not downloaded")

        from ingestion.parsers.sbe_prose import parse_nyaya_sutras

        chunks = parse_nyaya_sutras(path)
        assert len(chunks) >= 5

    def test_jain_sutras(self):
        path1 = CORPUS_RAW / "jaina_sutras_part1_jacobi_sbe22.txt"
        if not path1.exists():
            pytest.skip("Jain Sutras Part 1 not downloaded")

        from ingestion.parsers.sbe_prose import parse_jain_sutras

        chunks = parse_jain_sutras(path1, part=1)
        assert len(chunks) >= 5
        for c in chunks:
            assert c.tradition == "jain"

    def test_no_short_chunks(self):
        """No chunk from any SBE parser should be shorter than 20 words."""
        path = CORPUS_RAW / "manu_smriti_buhler_sbe25.txt"
        if not path.exists():
            pytest.skip("Manu Smriti not downloaded")

        from ingestion.parsers.sbe_prose import parse_manu_smriti

        chunks = parse_manu_smriti(path)
        short = [c for c in chunks if len(c.text.split()) < 20]
        assert not short, f"{len(short)} chunks shorter than 20 words"

    def test_manu_has_valid_chapter_numbers(self):
        """Chapter numbering should start at 1 and never be 0/negative."""
        path = CORPUS_RAW / "manu_smriti_buhler_sbe25.txt"
        if not path.exists():
            pytest.skip("Manu Smriti not downloaded")

        from ingestion.parsers.sbe_prose import parse_manu_smriti

        chunks = parse_manu_smriti(path)
        chapters = {c.chapter for c in chunks}
        assert chapters, "No chapters parsed"
        assert min(chapters) >= 1, f"Invalid chapter numbers: {sorted(chapters)}"
        assert 1 in chapters, f"Expected chapter 1 to exist, got {sorted(chapters)}"

    def test_brahma_sutras_shankara(self):
        path = CORPUS_RAW / "brahma_sutras_shankara_sbe34.txt"
        if not path.exists():
            pytest.skip("Brahma Sutras Shankara not downloaded")

        from ingestion.parsers.sbe_prose import parse_brahma_sutras_shankara

        chunks = parse_brahma_sutras_shankara(path)
        assert len(chunks) >= 10

    def test_brahma_sutras_ramanuja(self):
        path = CORPUS_RAW / "brahma_sutras_ramanuja_sbe48.txt"
        if not path.exists():
            pytest.skip("Brahma Sutras Ramanuja not downloaded")

        from ingestion.parsers.sbe_prose import parse_brahma_sutras_ramanuja

        chunks = parse_brahma_sutras_ramanuja(path)
        assert len(chunks) >= 10


# ─── Vedas ────────────────────────────────────────────────────────────────────

class TestVedasParser:
    def test_rig_veda_has_mandalas(self):
        path = CORPUS_RAW / "rigveda_griffith.txt"
        if not path.exists():
            pytest.skip("Rig Veda not downloaded")

        from ingestion.parsers.vedas_griffith import parse_rig_veda

        chunks = parse_rig_veda(path)
        assert len(chunks) >= 100, f"Expected ≥100 hymn chunks, got {len(chunks)}"

        mandalas = {c.chapter for c in chunks}
        # Rig Veda has 10 Mandalas
        assert len(mandalas) >= 8, f"Too few Mandalas: {sorted(mandalas)}"

    def test_rig_veda_metadata(self):
        path = CORPUS_RAW / "rigveda_griffith.txt"
        if not path.exists():
            pytest.skip("Rig Veda not downloaded")

        from ingestion.parsers.vedas_griffith import parse_rig_veda

        chunks = parse_rig_veda(path)
        for c in chunks[:10]:
            assert c.scripture == "Rig Veda"
            assert c.translator == "Ralph T.H. Griffith"
            assert c.tradition == "hindu_vedanta"
            assert c.license_tier == "A"

    def test_rig_veda_no_empty_chunks(self):
        path = CORPUS_RAW / "rigveda_griffith.txt"
        if not path.exists():
            pytest.skip("Rig Veda not downloaded")

        from ingestion.parsers.vedas_griffith import parse_rig_veda

        chunks = parse_rig_veda(path)
        for c in chunks:
            assert len(c.text.split()) >= 15

    def test_atharva_veda_has_books(self):
        path = CORPUS_RAW / "atharva_veda_griffith.txt"
        if not path.exists():
            pytest.skip("Atharva Veda not downloaded")

        from ingestion.parsers.vedas_griffith import parse_atharva_veda

        chunks = parse_atharva_veda(path)
        assert len(chunks) >= 50
        books = {c.chapter for c in chunks}
        assert len(books) >= 5


# ─── Epics ────────────────────────────────────────────────────────────────────

class TestEpicsParser:
    def test_mahabharata_has_parvans(self):
        path = CORPUS_RAW / "mahabharata_ganguli_complete.txt"
        if not path.exists():
            pytest.skip("Mahabharata not downloaded")

        from ingestion.parsers.epics_prose import parse_mahabharata

        chunks = parse_mahabharata(path)
        assert len(chunks) >= 100, f"Expected ≥100 chunks, got {len(chunks)}"

        parvans = {c.chapter for c in chunks}
        assert len(parvans) >= 5, f"Too few Parvans: {sorted(parvans)}"

    def test_mahabharata_metadata(self):
        path = CORPUS_RAW / "mahabharata_ganguli_complete.txt"
        if not path.exists():
            pytest.skip("Mahabharata not downloaded")

        from ingestion.parsers.epics_prose import parse_mahabharata

        chunks = parse_mahabharata(path)
        for c in chunks[:5]:
            assert c.scripture == "Mahabharata"
            assert c.translator == "Kisari Mohan Ganguli"
            assert c.tradition == "hindu_vedanta"
            assert c.license_tier == "A"

    def test_mahabharata_no_short_chunks(self):
        path = CORPUS_RAW / "mahabharata_ganguli_complete.txt"
        if not path.exists():
            pytest.skip("Mahabharata not downloaded")

        from ingestion.parsers.epics_prose import parse_mahabharata

        chunks = parse_mahabharata(path)
        short = [c for c in chunks if len(c.text.split()) < 25]
        assert len(short) == 0, f"{len(short)} chunks shorter than 25 words"

    def test_ramayana_has_kandas(self):
        path = CORPUS_RAW / "ramayana_griffith.txt"
        if not path.exists():
            pytest.skip("Ramayana not downloaded")

        from ingestion.parsers.epics_prose import parse_ramayana

        chunks = parse_ramayana(path)
        assert len(chunks) >= 50

        kandas = {c.chapter for c in chunks}
        assert len(kandas) >= 4, f"Too few Kandas: {sorted(kandas)}"

    def test_ramayana_metadata(self):
        path = CORPUS_RAW / "ramayana_griffith.txt"
        if not path.exists():
            pytest.skip("Ramayana not downloaded")

        from ingestion.parsers.epics_prose import parse_ramayana

        chunks = parse_ramayana(path)
        for c in chunks[:5]:
            assert c.scripture == "Ramayana"
            assert c.translator == "Ralph T.H. Griffith"
            assert c.license_tier == "A"
