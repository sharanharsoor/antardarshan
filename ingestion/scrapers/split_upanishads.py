"""
Split upanishads_muller_complete.txt into individual Upanishad files.

No network access needed — all content is already on disk.
Run this once to fix the partial Mundaka and Prashna files and
add Taittiriya, Brihadaranyaka, and other Upanishads from the complete text.

Usage:
    python -m ingestion.scrapers.split_upanishads
"""

import re
from pathlib import Path

CORPUS_RAW = Path(__file__).parent.parent.parent / "corpus" / "raw"
COMPLETE_FILE = CORPUS_RAW / "upanishads_muller_complete.txt"


# Section markers and their output filenames — ordered by position in the file.
# Each entry: (start_marker_regex, output_filename, upanishad_name)
SECTIONS = [
    (r"^MUNDAKA-UPANISHAD",        "mundaka_upanishad_muller.txt",       "Mundaka Upanishad"),
    (r"^TAITTIRIYAKA-UPANISHAD",   "taittiriya_upanishad_muller.txt",    "Taittiriya Upanishad"),
    (r"^BRIHADARANYAKA-UPANISHAD", "brihadaranyaka_upanishad_muller.txt","Brihadaranyaka Upanishad"),
    (r"^PRASNA-UPANISHAD",         "prasna_upanishad_muller.txt",        "Prashna Upanishad"),
]


def split_upanishads(overwrite: bool = False) -> None:
    if not COMPLETE_FILE.exists():
        print(f"ERROR: {COMPLETE_FILE} not found. Nothing to split.")
        return

    text = COMPLETE_FILE.read_text(encoding="utf-8")
    print(f"Loaded {COMPLETE_FILE.name} ({len(text):,} chars, {text.count(chr(10)):,} lines)")

    # Find start positions of every section
    markers = []
    for start_re, output_file, name in SECTIONS:
        m = re.search(start_re, text, re.MULTILINE)
        if m:
            markers.append((m.start(), output_file, name))
        else:
            print(f"  WARNING: '{start_re}' not found in complete file")

    # Sort by position so we can slice between consecutive markers
    markers.sort(key=lambda x: x[0])

    for i, (start_pos, output_file, name) in enumerate(markers):
        # Section ends at the start of the next section (or end of file)
        end_pos = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        section_text = text[start_pos:end_pos].strip()

        output_path = CORPUS_RAW / output_file
        if output_path.exists() and not overwrite:
            # Check if the existing file is a partial (small size)
            existing_size = output_path.stat().st_size
            new_size = len(section_text.encode("utf-8"))
            if existing_size >= new_size * 0.9:
                print(f"  Skip {output_file} (existing file is {existing_size:,} bytes, same size)")
                continue
            print(f"  Replacing partial {output_file} ({existing_size:,} bytes → {new_size:,} bytes)")

        output_path.write_text(section_text, encoding="utf-8")
        # Quick verse count estimate
        verse_count = len(re.findall(r"^\d+\.", section_text, re.MULTILINE))
        print(f"  Saved: {output_file} ({len(section_text):,} chars, ~{verse_count} verse markers)")

    print("\nDone. Run 'python -m ingestion.process_phase1' to re-process all texts.")
    print("Add new filenames to process_phase1.py upanishad_files dict to include them.")


if __name__ == "__main__":
    import sys
    overwrite = "--overwrite" in sys.argv
    split_upanishads(overwrite=overwrite)
