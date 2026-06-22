"""
Process Phase 1 corpus: parse raw texts into structured chunks and save as JSON.

Run this after downloading raw texts to corpus/raw/.
Output goes to corpus/processed/ as JSON files ready for embedding.

Usage:
    python -m ingestion.process_phase1
"""

import json
from pathlib import Path

from ingestion.parsers.gita_arnold import parse_gita_arnold
from ingestion.parsers.ashtavakra import parse_ashtavakra
from ingestion.parsers.dhammapada_sujato import parse_dhammapada_sujato
from ingestion.parsers.yoga_sutras_johnston import parse_yoga_sutras_johnston
from ingestion.parsers.upanishads_muller import parse_upanishad
from ingestion.parsers.vivekananda_prose import parse_vivekananda_chapter


CORPUS_RAW = Path(__file__).parent.parent / "corpus" / "raw"
CORPUS_PROCESSED = Path(__file__).parent.parent / "corpus" / "processed"


def _save_chunks(chunks, filename: str) -> int:
    output = CORPUS_PROCESSED / filename
    output.write_text(
        json.dumps([c.to_dict() for c in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(chunks)


def process_all():
    CORPUS_PROCESSED.mkdir(parents=True, exist_ok=True)
    total_chunks = 0

    # 1. Bhagavad Gita (Arnold)
    gita_path = CORPUS_RAW / "pg2388.txt"
    if gita_path.exists():
        chunks = parse_gita_arnold(gita_path)
        _save_chunks(chunks, "bhagavad_gita_arnold.json")
        print(f"✓ Bhagavad Gita (Arnold): {len(chunks)} chunks")
        total_chunks += len(chunks)
    else:
        print(f"✗ Bhagavad Gita: not found at {gita_path}")

    # 2. Ashtavakra Gita (Richards)
    ashtavakra_path = CORPUS_RAW / "ashtavakra_gita_richards.txt"
    if ashtavakra_path.exists():
        chunks = parse_ashtavakra(ashtavakra_path)
        _save_chunks(chunks, "ashtavakra_gita_richards.json")
        print(f"✓ Ashtavakra Gita (Richards): {len(chunks)} chunks")
        total_chunks += len(chunks)
    else:
        print(f"✗ Ashtavakra Gita: not found at {ashtavakra_path}")

    # 3. Dhammapada (Sujato, CC0)
    sc_data_path = CORPUS_RAW / "sc-data"
    if sc_data_path.exists():
        chunks = parse_dhammapada_sujato(sc_data_path)
        _save_chunks(chunks, "dhammapada_sujato.json")
        print(f"✓ Dhammapada (Sujato): {len(chunks)} chunks")
        total_chunks += len(chunks)
    else:
        print(f"✗ Dhammapada: SuttaCentral data not found at {sc_data_path}")

    # 4. Yoga Sutras (Johnston)
    yoga_path = CORPUS_RAW / "pg2526.txt"
    if yoga_path.exists():
        chunks = parse_yoga_sutras_johnston(yoga_path)
        _save_chunks(chunks, "yoga_sutras_johnston.json")
        print(f"✓ Yoga Sutras (Johnston): {len(chunks)} chunks")
        total_chunks += len(chunks)
    else:
        print(f"✗ Yoga Sutras: not found at {yoga_path}")

    # 5. Upanishads (Müller SBE)
    upanishad_files = {
        "katha_upanishad_muller.txt": "Katha Upanishad",
        "isha_upanishad_muller.txt": "Isha Upanishad",
        "kena_upanishad_muller.txt": "Kena Upanishad",
        "mundaka_upanishad_muller.txt": "Mundaka Upanishad",
        "prasna_upanishad_muller.txt": "Prashna Upanishad",
        "taittiriya_upanishad_muller.txt": "Taittiriya Upanishad",
        "brihadaranyaka_upanishad_muller.txt": "Brihadaranyaka Upanishad",
        "svetasvatara_upanishad_muller.txt": "Svetasvatara Upanishad",
        "chandogya_upanishad_muller.txt": "Chandogya Upanishad",
    }
    for filename, name in upanishad_files.items():
        path = CORPUS_RAW / filename
        if path.exists():
            chunks = parse_upanishad(path, name)
            safe_name = name.lower().replace(" ", "_")
            _save_chunks(chunks, f"{safe_name}_muller.json")
            print(f"✓ {name} (Müller): {len(chunks)} chunks")
            total_chunks += len(chunks)
        else:
            print(f"✗ {name}: not found at {path}")

    # 6. Vivekananda (prose — Raja-Yoga, Karma-Yoga, Jnana-Yoga)
    vivekananda_dir = CORPUS_RAW / "vivekananda"
    if vivekananda_dir.exists():
        # Process all available chapter files
        vivekananda_chapters = [
            ("raja_yoga_ch1_introductory.txt", "Raja-Yoga", "Introductory", 1),
            ("raja_yoga_ch2_first_steps.txt", "Raja-Yoga", "The First Steps", 2),
            ("raja_yoga_ch3_prana.txt", "Raja-Yoga", "Prana", 3),
            ("raja_yoga_ch4_psychic_prana.txt", "Raja-Yoga", "The Psychic Prana", 4),
            ("raja_yoga_ch5_control.txt", "Raja-Yoga", "Control of Psychic Prana", 5),
            ("raja_yoga_ch6_dharana.txt", "Raja-Yoga", "Pratyahara and Dharana", 6),
            ("raja_yoga_ch7_samadhi.txt", "Raja-Yoga", "Dhyana and Samadhi", 7),
            ("raja_yoga_ch8_brief.txt", "Raja-Yoga", "Raja-Yoga in Brief", 8),
            ("karma_yoga_ch1.txt", "Karma-Yoga", "Karma in its Effect on Character", 1),
            ("karma_yoga_ch2.txt", "Karma-Yoga", "Each is Great in His Own Place", 2),
            ("karma_yoga_ch3.txt", "Karma-Yoga", "The Secret of Work", 3),
            ("karma_yoga_ch4.txt", "Karma-Yoga", "What is Duty?", 4),
            ("karma_yoga_ch5.txt", "Karma-Yoga", "We Help Ourselves Not the World", 5),
            ("karma_yoga_ch6.txt", "Karma-Yoga", "Non-Attachment", 6),
            ("karma_yoga_ch7.txt", "Karma-Yoga", "Freedom", 7),
            ("karma_yoga_ch8.txt", "Karma-Yoga", "The Ideal of Karma-Yoga", 8),
            ("jnana_yoga_ch1.txt", "Jnana-Yoga", "The Real and the Apparent Man", 1),
            ("jnana_yoga_ch2.txt", "Jnana-Yoga", "The Real Nature of Man", 2),
            ("jnana_yoga_ch3.txt", "Jnana-Yoga", "Maya and Illusion", 3),
            ("jnana_yoga_ch4.txt", "Jnana-Yoga", "Maya and Evolution", 4),
            ("jnana_yoga_ch5.txt", "Jnana-Yoga", "Maya and Freedom", 5),
            ("jnana_yoga_ch6.txt", "Jnana-Yoga", "The Absolute and Manifestation", 6),
        ]
        all_viv_chunks = []
        for filename, book, chapter_name, chapter_num in vivekananda_chapters:
            path = vivekananda_dir / filename
            if path.exists():
                chunks = parse_vivekananda_chapter(path, book, chapter_name, chapter_num)
                all_viv_chunks.extend(chunks)

        if all_viv_chunks:
            _save_chunks(all_viv_chunks, "vivekananda_collected.json")
            print(f"✓ Vivekananda (collected): {len(all_viv_chunks)} chunks")
            total_chunks += len(all_viv_chunks)
        else:
            print(f"✗ Vivekananda: no chapter files found in {vivekananda_dir}")

    print(f"\n{'='*50}")
    print(f"Total: {total_chunks} chunks ready for embedding")
    print(f"Output: {CORPUS_PROCESSED}/")
    return total_chunks


if __name__ == "__main__":
    process_all()
