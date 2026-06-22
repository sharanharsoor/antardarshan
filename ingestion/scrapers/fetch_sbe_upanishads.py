"""
Batch fetch all Upanishads from sacred-texts.com SBE pages.

Run this outside the restricted sandbox (full network access needed).
Each Upanishad is spread across multiple HTML pages on sacred-texts.com.

Usage:
    python -m ingestion.scrapers.fetch_sbe_upanishads

After running, the parser at ingestion/parsers/upanishads_muller.py
handles chunking automatically — just add filenames to process_phase1.py.
"""

import re
import time
import httpx
from pathlib import Path

CORPUS_RAW = Path(__file__).parent.parent.parent / "corpus" / "raw"

# SBE page ranges for each Upanishad (sacred-texts.com URL pattern)
# Format: (name, output_file, base_url_template, page_range)
UPANISHAD_PAGES = [
    # SBE Volume 15
    ("Mundaka Upanishad", "mundaka_upanishad_muller.txt", "https://sacred-texts.com/hin/sbe15/sbe150{:02d}.htm", range(16, 22)),
    ("Prashna Upanishad", "prasna_upanishad_muller.txt", "https://sacred-texts.com/hin/sbe15/sbe150{:02d}.htm", range(37, 43)),
    ("Svetasvatara Upanishad", "svetasvatara_upanishad_muller.txt", "https://sacred-texts.com/hin/sbe15/sbe150{:02d}.htm", range(30, 37)),
    # SBE Volume 1 (Kena already done, Chandogya is huge)
    ("Aitareya Upanishad", "aitareya_upanishad_muller.txt", "https://sacred-texts.com/hin/sbe01/sbe010{:02d}.htm", range(180, 220)),
]

HEADERS = {"User-Agent": "Mozilla/5.0 AntarDarshan/0.1 (research, public-domain-texts)"}


def strip_html(html: str) -> str:
    """Extract text content, removing HTML tags and navigation."""
    # Get content between horizontal rules (main text area)
    parts = html.split("---")
    if len(parts) >= 3:
        body = "---".join(parts[2:-2])  # Skip header/footer nav
    else:
        body = html

    # Remove remaining markdown/HTML artifacts
    body = re.sub(r"^#+\s*", "", body, flags=re.MULTILINE)  # Remove # headers
    body = re.sub(r"\*\*|__", "", body)  # Remove bold markers
    body = re.sub(r"^\s*-{3,}\s*$", "", body, flags=re.MULTILINE)  # Remove HR lines
    body = re.sub(r"^Buy this Book.*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"^.*sacred-texts\.com.*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"^.*Footnotes.*$", "\n", body, flags=re.MULTILINE)
    # Remove everything after "Footnotes" or "Next:"
    body = re.split(r"\n(?:Footnotes|Next:)", body)[0]
    return body.strip()


def fetch_upanishad(name: str, output_file: str, url_template: str, pages: range):
    """Fetch all pages of an Upanishad and combine into one text file."""
    output_path = CORPUS_RAW / output_file
    if output_path.exists():
        print(f"  Already exists: {output_file}")
        return

    print(f"\n  Fetching {name} ({len(pages)} pages)...")
    all_text = []

    for page_num in pages:
        url = url_template.format(page_num)
        try:
            resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=20)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            text = strip_html(resp.text)
            if text and len(text) > 50:
                all_text.append(text)
                print(f"    Page {page_num}: {len(text)} chars")
        except Exception as e:
            print(f"    Page {page_num}: ERROR {e}")
        time.sleep(1.5)  # Polite crawl delay

    if all_text:
        combined = "\n\n".join(all_text)
        output_path.write_text(combined, encoding="utf-8")
        print(f"  Saved: {output_file} ({len(combined):,} chars)")
    else:
        print(f"  FAILED: No content fetched for {name}")


def main():
    CORPUS_RAW.mkdir(parents=True, exist_ok=True)
    print("Fetching SBE Upanishads from sacred-texts.com...")
    for name, output_file, url_template, pages in UPANISHAD_PAGES:
        fetch_upanishad(name, output_file, url_template, pages)
    print("\nDone. Run 'python -m ingestion.process_phase1' to process.")


if __name__ == "__main__":
    main()
