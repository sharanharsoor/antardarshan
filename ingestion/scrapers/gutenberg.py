"""
Download plain text files from Project Gutenberg.

Gutenberg texts are direct .txt downloads — no HTML parsing needed.
Strips the PG header/footer boilerplate automatically.
"""

import httpx
from pathlib import Path
import re


PG_HEADER_END = re.compile(
    r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE,
)
PG_FOOTER_START = re.compile(
    r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE,
)


def download_gutenberg(url: str, output_dir: Path) -> Path:
    """Download a Gutenberg .txt and strip boilerplate. Returns path to cleaned file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = url.split("/")[-1]
    raw_path = output_dir / f"raw_{filename}"
    clean_path = output_dir / filename

    if clean_path.exists():
        print(f"  Already downloaded: {clean_path.name}")
        return clean_path

    print(f"  Downloading {url}...")
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    raw_text = resp.text

    # Strip PG header
    header_match = PG_HEADER_END.search(raw_text)
    if header_match:
        raw_text = raw_text[header_match.end():]

    # Strip PG footer
    footer_match = PG_FOOTER_START.search(raw_text)
    if footer_match:
        raw_text = raw_text[:footer_match.start()]

    clean_text = raw_text.strip()
    clean_path.write_text(clean_text, encoding="utf-8")
    print(f"  Saved: {clean_path.name} ({len(clean_text):,} chars)")
    return clean_path


if __name__ == "__main__":
    from pathlib import Path

    corpus_dir = Path(__file__).parent.parent.parent / "corpus" / "raw"

    # Phase 1 Gutenberg texts
    sources = [
        "https://www.gutenberg.org/cache/epub/2388/pg2388.txt",   # Gita (Arnold)
        "https://www.gutenberg.org/cache/epub/10311/pg10311.txt",  # Ashtavakra Gita
    ]

    for url in sources:
        download_gutenberg(url, corpus_dir)
