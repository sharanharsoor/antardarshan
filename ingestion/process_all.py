"""
AntarDarshan — Full Corpus Processing Pipeline.

Processes all verified raw texts into structured chunks ready for embedding.
Replaces process_phase1.py — handles Phase 1 + Phase 2 corpus.

Usage:
    python -m ingestion.process_all

Output: corpus/processed/*.json — one file per scripture/tradition.

Pre-ingestion validation:
  - Checks file is not HTML-blocked
  - Checks minimum readable English word count
  - Logs skip reasons clearly (no silent failures)

Run time: ~30–60 seconds depending on hardware (all CPU, no GPU needed).
"""

import json
import re
from pathlib import Path

# ── Imports ────────────────────────────────────────────────────────────────────

from ingestion.parsers.gita_arnold import parse_gita_arnold
from ingestion.parsers.ashtavakra import parse_ashtavakra
from ingestion.parsers.dhammapada_sujato import parse_dhammapada_sujato
from ingestion.parsers.yoga_sutras_johnston import parse_yoga_sutras_johnston
from ingestion.parsers.upanishads_muller import parse_upanishad
from ingestion.parsers.vivekananda_prose import parse_vivekananda_chapter
from ingestion.parsers.pali_canon_sujato import parse_pali_canon
from ingestion.parsers.gita_telang import parse_telang_sbe08
from ingestion.parsers.sbe_prose import (
    parse_brahma_sutras_shankara,
    parse_brahma_sutras_ramanuja,
    parse_manu_smriti,
    parse_arthashastra,
    parse_jain_sutras,
    parse_nyaya_sutras,
    parse_vaisheshika_sutras,
    parse_samkhya_karika,
    parse_milindapanha,
    parse_institutes_of_vishnu,
    parse_garuda_purana,
    parse_markandeya_purana,
    parse_agni_purana,
    parse_vivekachudamani,
    parse_psalms_maratha_saints,
    parse_thirukkural,
)
from ingestion.parsers.vedas_griffith import parse_rig_veda, parse_atharva_veda
from ingestion.parsers.epics_prose import parse_mahabharata, parse_ramayana

# ── Paths ──────────────────────────────────────────────────────────────────────

CORPUS_RAW = Path(__file__).parent.parent / "corpus" / "raw"
CORPUS_PROCESSED = Path(__file__).parent.parent / "corpus" / "processed"

# ── Validation ─────────────────────────────────────────────────────────────────

_HTML_SIGNALS = ["<!DOCTYPE", "<html", "cloudflare", "Enable JavaScript"]
_WRONG_BOOKS = [
    "tragedy of the korosko", "watch—work—wait", "shih king",
    "book of poetry", "cicero", "jane allen",
]


def _validate_raw_file(path: Path, min_words: int = 30) -> tuple[bool, str]:
    """
    Pre-ingestion validation gate.
    Returns (is_valid, reason_if_invalid).

    Reads the first 2000 bytes (not just 600) so OCR files with
    front-matter noise (copyright pages, library stamps) are not
    incorrectly rejected.
    """
    if not path.exists():
        return False, f"not found: {path}"

    try:
        sample = path.read_bytes()[:2000].decode("utf-8", errors="ignore")
    except Exception as e:
        return False, f"read error: {e}"

    if any(sig in sample for sig in _HTML_SIGNALS):
        return False, "HTML-blocked (Cloudflare or redirect)"

    if any(wrong in sample.lower() for wrong in _WRONG_BOOKS):
        return False, f"wrong content detected: {sample[:80]!r}"

    english_words = len(re.findall(r"[a-zA-Z]{4,}", sample))
    if english_words < min_words:
        return False, f"too little readable English ({english_words} words in first 2000 bytes)"

    return True, ""


# ── Save helper ────────────────────────────────────────────────────────────────

def _deduplicate_verses(chunks: list) -> list:
    """
    Ensure (chapter, verse) pairs are unique within each scripture/translator stream.

    When the same (chapter, verse) pair appears multiple times for the same
    scripture + translator — due to chapter markers re-appearing in OCR text —
    increment the duplicate verse until it's unique.
    This guarantees unique chunk_ids in Qdrant (no silent overwrites).
    """
    seen: set[tuple[str, str, int, int]] = set()
    for chunk in chunks:
        scripture = getattr(chunk, "scripture", "")
        translator = getattr(chunk, "translator", "")
        ch, v = chunk.chapter, chunk.verse
        while (scripture, translator, ch, v) in seen:
            v += 1
        chunk.verse = v
        seen.add((scripture, translator, ch, v))
    return chunks


def _save(chunks: list, filename: str) -> int:
    if not chunks:
        return 0
    chunks = _deduplicate_verses(chunks)
    output = CORPUS_PROCESSED / filename
    output.write_text(
        json.dumps([c.to_dict() for c in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(chunks)


def _process(label: str, filename: str, parser_fn, *args) -> int:
    """Run one parser with validation and consistent logging."""
    try:
        chunks = parser_fn(*args)
        n = _save(chunks, filename)
        print(f"  ✓ {label}: {n} chunks")
        return n
    except Exception as e:
        print(f"  ✗ {label}: parser error — {e}")
        return 0


# ── Main pipeline ──────────────────────────────────────────────────────────────

def process_all() -> int:
    CORPUS_PROCESSED.mkdir(parents=True, exist_ok=True)
    total = 0

    print("\n" + "=" * 60)
    print("AntarDarshan — Full Corpus Processing")
    print("=" * 60 + "\n")

    # ── PHASE 1: Core texts (already processed, re-running for freshness) ──────

    print("── Phase 1: Core texts ──")

    gita_arnold = CORPUS_RAW / "pg2388.txt"
    ok, reason = _validate_raw_file(gita_arnold)
    if ok:
        total += _process("Bhagavad Gita (Arnold 1885)", "bhagavad_gita_arnold.json",
                          parse_gita_arnold, gita_arnold)
    else:
        print(f"  ✗ Bhagavad Gita (Arnold): {reason}")

    ashtavakra = CORPUS_RAW / "ashtavakra_gita_richards.txt"
    ok, reason = _validate_raw_file(ashtavakra)
    if ok:
        total += _process("Ashtavakra Gita (Richards 1994)", "ashtavakra_gita_richards.json",
                          parse_ashtavakra, ashtavakra)
    else:
        print(f"  ✗ Ashtavakra Gita: {reason}")

    sc_data = CORPUS_RAW / "sc-data"
    if sc_data.exists():
        total += _process("Dhammapada (Sujato CC0)", "dhammapada_sujato.json",
                          parse_dhammapada_sujato, sc_data)
    else:
        print(f"  ✗ Dhammapada: sc-data not found")

    yoga_path = CORPUS_RAW / "pg2526.txt"
    ok, reason = _validate_raw_file(yoga_path)
    if ok:
        total += _process("Yoga Sutras (Johnston 1912)", "yoga_sutras_johnston.json",
                          parse_yoga_sutras_johnston, yoga_path)
    else:
        print(f"  ✗ Yoga Sutras: {reason}")

    # ── Upanishads ─────────────────────────────────────────────────────────────
    upanishad_files = [
        ("katha_upanishad_muller.txt",          "Katha Upanishad",          "katha_upanishad_muller.json"),
        ("isha_upanishad_muller.txt",           "Isha Upanishad",           "isha_upanishad_muller.json"),
        ("kena_upanishad_muller.txt",           "Kena Upanishad",           "kena_upanishad_muller.json"),
        ("mundaka_upanishad_muller.txt",        "Mundaka Upanishad",        "mundaka_upanishad_muller.json"),
        ("prasna_upanishad_muller.txt",         "Prashna Upanishad",        "prashna_upanishad_muller.json"),
        ("taittiriya_upanishad_muller.txt",     "Taittiriya Upanishad",     "taittiriya_upanishad_muller.json"),
        ("brihadaranyaka_upanishad_muller.txt", "Brihadaranyaka Upanishad", "brihadaranyaka_upanishad_muller.json"),
        ("svetasvatara_upanishad_muller.txt",   "Svetasvatara Upanishad",   "svetasvatara_upanishad_muller.json"),
        ("chandogya_upanishad_muller.txt",      "Chandogya Upanishad",      "chandogya_upanishad_muller.json"),
    ]
    for fname, name, outfile in upanishad_files:
        path = CORPUS_RAW / fname
        ok, reason = _validate_raw_file(path)
        if ok:
            total += _process(f"{name} (Müller)", outfile, parse_upanishad, path, name)
        else:
            print(f"  ✗ {name}: {reason}")

    # ── Vivekananda ────────────────────────────────────────────────────────────
    viv_dir = CORPUS_RAW / "vivekananda"
    if viv_dir.exists():
        viv_chapters = [
            ("raja_yoga_ch1_introductory.txt",  "Raja-Yoga",  "Introductory", 1),
            ("raja_yoga_ch2_first_steps.txt",   "Raja-Yoga",  "The First Steps", 2),
            ("raja_yoga_ch3_prana.txt",         "Raja-Yoga",  "Prana", 3),
            ("raja_yoga_ch4_psychic_prana.txt", "Raja-Yoga",  "The Psychic Prana", 4),
            ("karma_yoga_ch1.txt",              "Karma-Yoga", "Karma in its Effect on Character", 1),
            ("karma_yoga_ch3.txt",              "Karma-Yoga", "The Secret of Work", 3),
            ("karma_yoga_ch4.txt",              "Karma-Yoga", "What is Duty?", 4),
            ("karma_yoga_ch7.txt",              "Karma-Yoga", "Freedom", 7),
            ("karma_yoga_ch8.txt",              "Karma-Yoga", "The Ideal of Karma-Yoga", 8),
            ("jnana_yoga_ch1.txt",              "Jnana-Yoga", "The Real and the Apparent Man", 1),
            ("jnana_yoga_ch2.txt",              "Jnana-Yoga", "The Real Nature of Man", 2),
            ("jnana_yoga_ch3.txt",              "Jnana-Yoga", "Maya and Illusion", 3),
            ("jnana_yoga_ch4.txt",              "Jnana-Yoga", "Maya and Evolution", 4),
            ("jnana_yoga_ch5.txt",              "Jnana-Yoga", "Maya and Freedom", 5),
            ("jnana_yoga_ch6.txt",              "Jnana-Yoga", "The Absolute and Manifestation", 6),
        ]
        viv_chunks = []
        for fname, book, chapter_name, ch_num in viv_chapters:
            fpath = viv_dir / fname
            ok, _ = _validate_raw_file(fpath)
            if ok:
                viv_chunks.extend(parse_vivekananda_chapter(fpath, book, chapter_name, ch_num))
        if viv_chunks:
            n = _save(viv_chunks, "vivekananda_collected.json")
            print(f"  ✓ Vivekananda (collected): {n} chunks")
            total += n
        else:
            print("  ✗ Vivekananda: no chapters parsed")

    # ── PHASE 2: New texts ─────────────────────────────────────────────────────

    print("\n── Phase 2: Pali Canon (SuttaCentral CC0) ──")

    if sc_data.exists():
        nikayas_to_parse = {
            "dn": "digha_nikaya_sujato.json",
            "mn": "majjhima_nikaya_sujato.json",
            "sn": "samyutta_nikaya_sujato.json",
            "an": "anguttara_nikaya_sujato.json",
        }
        pali_results = parse_pali_canon(sc_data, nikayas=list(nikayas_to_parse.keys()))
        for code, outfile in nikayas_to_parse.items():
            chunks = pali_results.get(code, [])
            n = _save(chunks, outfile)
            if n:
                total += n
    else:
        print("  ✗ Pali Canon: sc-data directory not found")

    print("\n── Phase 2: Bhagavad Gita (Telang) + bonus texts ──")

    telang = CORPUS_RAW / "bhagavad_gita_telang_sbe08.txt"
    ok, reason = _validate_raw_file(telang)
    if ok:
        try:
            t_result = parse_telang_sbe08(telang)
            for key, outfile, label in [
                ("gita",          "bhagavad_gita_telang.json",  "Bhagavad Gita (Telang 1882)"),
                ("sanatsujatiya", "sanatsujatiya_telang.json",  "Sanatsugatiya (Telang)"),
                ("anugita",       "anugita_telang.json",        "Anugita (Telang)"),
            ]:
                n = _save(t_result.get(key, []), outfile)
                if n:
                    print(f"  ✓ {label}: {n} chunks")
                    total += n
        except Exception as e:
            print(f"  ✗ Telang Gita: {e}")
    else:
        print(f"  ✗ Telang Gita: {reason}")

    print("\n── Phase 2: Vedas ──")

    rig = CORPUS_RAW / "rigveda_griffith.txt"
    ok, reason = _validate_raw_file(rig)
    if ok:
        total += _process("Rig Veda (Griffith 1896)", "rigveda_griffith.json",
                          parse_rig_veda, rig)
    else:
        print(f"  ✗ Rig Veda: {reason}")

    atharva = CORPUS_RAW / "atharva_veda_griffith.txt"
    ok, reason = _validate_raw_file(atharva)
    if ok:
        total += _process("Atharva Veda (Griffith 1895)", "atharva_veda_griffith.json",
                          parse_atharva_veda, atharva)
    else:
        print(f"  ✗ Atharva Veda: {reason}")

    print("\n── Phase 2: Epics ──")

    mbh = CORPUS_RAW / "mahabharata_ganguli_complete.txt"
    ok, reason = _validate_raw_file(mbh)
    if ok:
        total += _process("Mahabharata (Ganguli 1896)", "mahabharata_ganguli.json",
                          parse_mahabharata, mbh)
    else:
        print(f"  ✗ Mahabharata: {reason}")

    ram = CORPUS_RAW / "ramayana_griffith.txt"
    ok, reason = _validate_raw_file(ram)
    if ok:
        total += _process("Ramayana (Griffith 1895)", "ramayana_griffith.json",
                          parse_ramayana, ram)
    else:
        print(f"  ✗ Ramayana: {reason}")

    print("\n── Phase 2: Dharmashastra & Philosophy ──")

    sbe_texts = [
        ("brahma_sutras_shankara_sbe34.txt",  "brahma_sutras_shankara.json",  "Brahma Sutras + Shankara (Thibaut 1890)",  parse_brahma_sutras_shankara),
        ("brahma_sutras_ramanuja_sbe48.txt",  "brahma_sutras_ramanuja.json",  "Brahma Sutras + Ramanuja (Thibaut 1904)",  parse_brahma_sutras_ramanuja),
        ("brahma_sutras_shankara_pg_thibaut.txt", "brahma_sutras_shankara_pg.json", "Brahma Sutras + Shankara (PG clean)", parse_brahma_sutras_shankara),
        ("manu_smriti_buhler_sbe25.txt",      "manu_smriti_buhler.json",      "Manu Smriti (Bühler 1886)",               parse_manu_smriti),
        ("arthashastra_shamasastry_1915.txt", "arthashastra_shamasastry.json","Arthashastra (Shamasastry 1915)",          parse_arthashastra),
        ("nyaya_sutras_vidyabhusana_1913.txt","nyaya_sutras_vidyabhusana.json","Nyaya Sutras (Vidyabhusana 1913)",        parse_nyaya_sutras),
        ("vaisheshika_sutras_sinha_1923.txt", "vaisheshika_sutras_sinha.json","Vaisheshika Sutras (Sinha 1923)",          parse_vaisheshika_sutras),
        ("samkhya_karika_colebrooke_1837.txt","samkhya_karika_colebrooke.json","Samkhya Karika (Colebrooke 1837)",       parse_samkhya_karika),
        ("vivekachudamani_madhavananda_1921.txt","vivekachudamani_madhavananda.json","Vivekachudamani (Madhavananda 1921)",parse_vivekachudamani),
    ]
    for fname, outfile, label, parser_fn in sbe_texts:
        path = CORPUS_RAW / fname
        ok, reason = _validate_raw_file(path)
        if ok:
            total += _process(label, outfile, parser_fn, path)
        else:
            print(f"  ✗ {label}: {reason}")

    print("\n── Phase 2: Buddhist philosophy ──")

    jain_parts = [
        ("jaina_sutras_part1_jacobi_sbe22.txt", "jain_sutras_jacobi_part1.json", "Jain Sutras Part 1 (Jacobi 1884)", 1),
        ("jaina_sutras_part2_jacobi_sbe45.txt", "jain_sutras_jacobi_part2.json", "Jain Sutras Part 2 (Jacobi 1895)", 2),
    ]
    for fname, outfile, label, part in jain_parts:
        path = CORPUS_RAW / fname
        ok, reason = _validate_raw_file(path)
        if ok:
            total += _process(label, outfile, parse_jain_sutras, path, part)
        else:
            print(f"  ✗ {label}: {reason}")

    milinda = CORPUS_RAW / "milindapanha_rhys_davids_1890.txt"
    ok, reason = _validate_raw_file(milinda)
    if ok:
        total += _process("Milindapanha (Rhys Davids 1890)", "milindapanha_rhys_davids.json",
                          parse_milindapanha, milinda)
    else:
        print(f"  ✗ Milindapanha: {reason}")

    print("\n── Phase 2: Puranas ──")

    purana_texts = [
        ("garuda_purana_wood_subrahmanyam_1911.txt", "garuda_purana_wood.json",    "Garuda Purana (Wood 1911)",           parse_garuda_purana),
        ("markandeya_purana_pargiter_1904.txt",      "markandeya_purana_pargiter.json","Markandeya Purana (Pargiter 1904)",parse_markandeya_purana),
        ("agni_purana_mn_dutt_vol1.txt",             "agni_purana_dutt_vol1.json", "Agni Purana Vol.1 (Dutt 1903)",       parse_agni_purana),
        ("agni_purana_mn_dutt_vol2.txt",             "agni_purana_dutt_vol2.json", "Agni Purana Vol.2 (Dutt 1903)",       parse_agni_purana),
        ("institutes_of_vishnu_jolly_sbe07.txt",     "institutes_of_vishnu_jolly.json","Institutes of Vishnu (Jolly 1880)",parse_institutes_of_vishnu),
    ]
    for fname, outfile, label, parser_fn in purana_texts:
        path = CORPUS_RAW / fname
        ok, reason = _validate_raw_file(path)
        if ok:
            total += _process(label, outfile, parser_fn, path)
        else:
            print(f"  ✗ {label}: {reason}")

    print("\n── Phase 2: Sant/Bhakti tradition ──")

    from ingestion.parsers.sbe_prose import parse_sbe_text

    kabir_path = CORPUS_RAW / "songs_of_kabir_tagore.txt"
    ok, reason = _validate_raw_file(kabir_path)
    if ok:
        def _parse_kabir(path):
            raw = path.read_text(encoding="utf-8", errors="ignore")
            # The PG file has a long scholarly intro (Evelyn Underhill, ~600 lines)
            # before the actual poems. Skip everything before "KABIR'S POEMS".
            poems_start = raw.find("KABIR'S POEMS")
            if poems_start > 0:
                raw = raw[poems_start:]
                import tempfile, os
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                )
                tmp.write(raw)
                tmp.flush()
                result = parse_sbe_text(
                    Path(tmp.name), "Songs of Kabir", "sant_bhakti",
                    "Rabindranath Tagore", 1915,
                    "https://www.gutenberg.org/ebooks/6519", chunk_words=300,
                )
                os.unlink(tmp.name)
                return result
            return parse_sbe_text(path, "Songs of Kabir", "sant_bhakti",
                                  "Rabindranath Tagore", 1915,
                                  "https://www.gutenberg.org/ebooks/6519", chunk_words=300)
        total += _process("Songs of Kabir (Tagore tr. 1915)", "songs_of_kabir_tagore.json",
                          _parse_kabir, kabir_path)
    else:
        print(f"  ✗ Songs of Kabir: {reason}")

    psalms_path = CORPUS_RAW / "psalms_of_maratha_saints_macnicol_1919.txt"
    ok, reason = _validate_raw_file(psalms_path)
    if ok:
        total += _process("Psalms of Maratha Saints (Macnicol)", "psalms_maratha_saints.json",
                          parse_psalms_maratha_saints, psalms_path)
    else:
        print(f"  ✗ Psalms of Maratha Saints: {reason}")

    thirukkural_path = CORPUS_RAW / "thirukkural_pope.txt"
    ok, reason = _validate_raw_file(thirukkural_path)
    if ok:
        total += _process("Thirukkural (Pope 1886)", "thirukkural_pope.json",
                          parse_thirukkural, thirukkural_path)
    else:
        print(f"  ✗ Thirukkural: {reason}")

    # ── Summary ────────────────────────────────────────────────────────────────

    processed_files = list(CORPUS_PROCESSED.glob("*.json"))
    print(f"\n{'=' * 60}")
    print(f"DONE: {total:,} total chunks across {len(processed_files)} files")
    print(f"Output: {CORPUS_PROCESSED}/")
    print(f"{'=' * 60}\n")
    return total


if __name__ == "__main__":
    process_all()
