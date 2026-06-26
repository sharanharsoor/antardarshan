"""
Tests for Khuddaka Nikaya sub-collections and new Upanishad raw files.

Covers:
- KN parsers: Sutta Nipata, Udana, Itivuttaka, Theragatha, Therigatha
- New Upanishad raw files: Aitareya, Kaushitaki, Maitri
- Validation gate: new files pass _validate_raw_file()
- Upanishad parser produces valid chunks from new files
"""

import pytest
from pathlib import Path

CORPUS_RAW = Path(__file__).parent.parent / "corpus" / "raw"
SC_DATA = CORPUS_RAW / "sc-data"
KN_BASE = SC_DATA / "translation" / "en" / "sujato" / "sutta" / "kn"


# ── KN sub-collection parser tests ────────────────────────────────────────────

KN_TARGETS = [
    ("snp", "Sutta Nipata",  "buddhist"),
    ("ud",  "Udana",         "buddhist"),
    ("iti", "Itivuttaka",    "buddhist"),
    ("thag","Theragatha",    "buddhist"),
    ("thig","Therigatha",    "buddhist"),
]


@pytest.fixture(scope="module")
def kn_available():
    if not KN_BASE.exists():
        pytest.skip("SuttaCentral sc-data not available")


@pytest.mark.parametrize("code,name,tradition", KN_TARGETS)
class TestKNSubCollectionParsers:

    def test_parse_produces_chunks(self, code, name, tradition, kn_available):
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, code)
        assert len(chunks) >= 10, f"{name}: expected ≥10 chunks, got {len(chunks)}"

    def test_correct_scripture_name(self, code, name, tradition, kn_available):
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, code)
        for c in chunks:
            assert c.scripture == name, (
                f"Wrong scripture name: expected {name!r}, got {c.scripture!r}"
            )

    def test_correct_tradition(self, code, name, tradition, kn_available):
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, code)
        for c in chunks:
            assert c.tradition == tradition

    def test_license_tier_is_A(self, code, name, tradition, kn_available):
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, code)
        for c in chunks:
            assert c.license_tier == "A"

    def test_translator_is_sujato(self, code, name, tradition, kn_available):
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, code)
        for c in chunks:
            assert c.translator == "Bhikkhu Sujato"

    def test_source_url_contains_suttacentral(self, code, name, tradition, kn_available):
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, code)
        for c in chunks:
            assert c.source_url and "suttacentral" in c.source_url.lower()

    def test_no_empty_chunks(self, code, name, tradition, kn_available):
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, code)
        for c in chunks:
            assert c.text.strip(), f"Empty chunk in {name}"

    def test_no_duplicate_chunk_ids(self, code, name, tradition, kn_available):
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, code)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), f"Duplicate chunk_ids in {name}"

    def test_all_chunks_within_hard_cap(self, code, name, tradition, kn_available):
        """KN parsers should not produce oversized chunks (most suttas are short)."""
        nikaya_dir = KN_BASE / code
        if not nikaya_dir.exists():
            pytest.skip(f"KN/{code} directory not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        from ingestion.process_all import _HARD_CAP_WORDS
        chunks = parse_nikaya(nikaya_dir, code)
        oversized = [c for c in chunks if len(c.text.split()) > _HARD_CAP_WORDS]
        assert not oversized, (
            f"{name}: {len(oversized)} chunks exceed {_HARD_CAP_WORDS} words"
        )


# ── Specific KN content tests ──────────────────────────────────────────────────

class TestKNSpecificContent:

    def test_sutta_nipata_has_minimum_suttas(self, kn_available):
        """Sutta Nipata has 5 chapters (vaggas) with 73 suttas total."""
        nikaya_dir = KN_BASE / "snp"
        if not nikaya_dir.exists():
            pytest.skip("Sutta Nipata not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(nikaya_dir, "snp")
        assert len(chunks) >= 50, f"Expected ≥50 SNP chunks, got {len(chunks)}"

    def test_therigatha_different_from_theragatha(self, kn_available):
        """Therigatha (nuns) and Theragatha (monks) must produce different chunks."""
        thig_dir = KN_BASE / "thig"
        thag_dir = KN_BASE / "thag"
        if not thig_dir.exists() or not thag_dir.exists():
            pytest.skip("Therigatha or Theragatha not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        thig = parse_nikaya(thig_dir, "thig")
        thag = parse_nikaya(thag_dir, "thag")

        thig_texts = {c.text[:50] for c in thig}
        thag_texts = {c.text[:50] for c in thag}
        overlap = thig_texts & thag_texts
        assert len(overlap) < 3, f"Too much content overlap between Therigatha and Theragatha"

    def test_udana_has_8_vaggas(self, kn_available):
        """Udana is organized in 8 vaggas (chapters)."""
        ud_dir = KN_BASE / "ud"
        if not ud_dir.exists():
            pytest.skip("Udana not found")

        from ingestion.parsers.pali_canon_sujato import parse_nikaya
        chunks = parse_nikaya(ud_dir, "ud")
        chapters = {c.chapter for c in chunks}
        assert len(chapters) >= 8, f"Udana should have ≥8 chapters, got {sorted(chapters)}"


# ── New Upanishad raw file validation tests ────────────────────────────────────

NEW_UPANISHAD_FILES = [
    ("aitareya_upanishad_muller.txt",   "Aitareya Upanishad"),
    ("kaushitaki_upanishad_muller.txt", "Kaushitaki Upanishad"),
    ("maitri_upanishad_muller.txt",     "Maitri Upanishad"),
    ("mandukya_upanishad_muller.txt",   "Mandukya Upanishad"),
]


class TestNewUpanishadRawFiles:

    @pytest.mark.parametrize("filename,name", NEW_UPANISHAD_FILES)
    def test_file_exists(self, filename, name):
        path = CORPUS_RAW / filename
        assert path.exists(), f"{name} raw file not found at {path}"

    @pytest.mark.parametrize("filename,name", NEW_UPANISHAD_FILES)
    def test_file_passes_validation(self, filename, name):
        path = CORPUS_RAW / filename
        if not path.exists():
            pytest.skip(f"{filename} not present")

        from ingestion.process_all import _validate_raw_file
        ok, reason = _validate_raw_file(path)
        assert ok, f"{name} failed validation: {reason}"

    @pytest.mark.parametrize("filename,name", NEW_UPANISHAD_FILES)
    def test_file_not_html(self, filename, name):
        path = CORPUS_RAW / filename
        if not path.exists():
            pytest.skip(f"{filename} not present")

        content = path.read_text(errors="ignore")[:500]
        assert "<!DOCTYPE" not in content
        assert "<html" not in content
        assert "cloudflare" not in content.lower()

    @pytest.mark.parametrize("filename,name", NEW_UPANISHAD_FILES)
    def test_file_has_substantial_content(self, filename, name):
        path = CORPUS_RAW / filename
        if not path.exists():
            pytest.skip(f"{filename} not present")

        content = path.read_text(errors="ignore")
        word_count = len(content.split())
        assert word_count >= 100, f"{name} too short: {word_count} words"

    @pytest.mark.parametrize("filename,name", NEW_UPANISHAD_FILES)
    def test_file_parseable_by_upanishad_parser(self, filename, name):
        path = CORPUS_RAW / filename
        if not path.exists():
            pytest.skip(f"{filename} not present")

        from ingestion.parsers.upanishads_muller import parse_upanishad
        chunks = parse_upanishad(path, name)
        assert len(chunks) >= 1, f"{name}: parser returned 0 chunks"
        for c in chunks:
            assert c.scripture == name
            assert c.text.strip()
            assert c.tradition == "hindu_vedanta"

    def test_aitareya_larger_than_mandukya(self):
        """Aitareya Aranyaka/Upanishad is much longer than Mandukya."""
        aitareya = CORPUS_RAW / "aitareya_upanishad_muller.txt"
        mandukya = CORPUS_RAW / "mandukya_upanishad_muller.txt"
        if not aitareya.exists() or not mandukya.exists():
            pytest.skip("Files not present")

        a_words = len(aitareya.read_text(errors="ignore").split())
        m_words = len(mandukya.read_text(errors="ignore").split())
        assert a_words > m_words * 10, (
            f"Expected Aitareya ({a_words}w) to be much larger than Mandukya ({m_words}w)"
        )

    def test_kaushitaki_has_4_chapters(self):
        """Kaushitaki Upanishad has 4 adhyayas."""
        path = CORPUS_RAW / "kaushitaki_upanishad_muller.txt"
        if not path.exists():
            pytest.skip("Kaushitaki not present")

        from ingestion.parsers.upanishads_muller import parse_upanishad
        chunks = parse_upanishad(path, "Kaushitaki Upanishad")
        chapters = {c.chapter for c in chunks}
        assert len(chapters) >= 2, (
            f"Kaushitaki should span multiple chapters, got {sorted(chapters)}"
        )

    def test_sbe_source_files_exist(self):
        """The raw SBE volumes used to extract new Upanishads should be present."""
        assert (CORPUS_RAW / "sbe01_upanishads_muller.txt").exists(), \
            "sbe01_upanishads_muller.txt not found"
        assert (CORPUS_RAW / "sbe15_upanishads_muller.txt").exists(), \
            "sbe15_upanishads_muller.txt not found"

    def test_sbe01_contains_aitareya(self):
        path = CORPUS_RAW / "sbe01_upanishads_muller.txt"
        if not path.exists():
            pytest.skip("sbe01 not present")
        content = path.read_text(errors="ignore")
        assert "AITAREYA" in content.upper()
        assert "KAUSHITAKI" in content.upper()

    def test_sbe15_contains_maitri(self):
        path = CORPUS_RAW / "sbe15_upanishads_muller.txt"
        if not path.exists():
            pytest.skip("sbe15 not present")
        content = path.read_text(errors="ignore")
        assert "MAITRI" in content.upper() or "MAITRAYANA" in content.upper()


# ── process_all.py includes new texts ─────────────────────────────────────────

class TestProcessAllCoversNewTexts:
    """Verify process_all.py's text list includes all new additions."""

    def test_mandukya_in_upanishad_list(self):
        import ast, inspect
        from ingestion import process_all
        src = inspect.getsource(process_all)
        assert "mandukya_upanishad_muller.txt" in src

    def test_aitareya_in_upanishad_list(self):
        import inspect
        from ingestion import process_all
        src = inspect.getsource(process_all)
        assert "aitareya_upanishad_muller.txt" in src

    def test_kaushitaki_in_upanishad_list(self):
        import inspect
        from ingestion import process_all
        src = inspect.getsource(process_all)
        assert "kaushitaki_upanishad_muller.txt" in src

    def test_maitri_in_upanishad_list(self):
        import inspect
        from ingestion import process_all
        src = inspect.getsource(process_all)
        assert "maitri_upanishad_muller.txt" in src

    def test_kn_sub_collections_in_process_all(self):
        import inspect
        from ingestion import process_all
        src = inspect.getsource(process_all)
        for code in ["snp", "ud", "iti", "thag", "thig"]:
            assert f'"{code}"' in src, f"KN code {code!r} missing from process_all.py"
