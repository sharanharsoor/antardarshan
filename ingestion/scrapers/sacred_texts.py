"""
Scraper for sacred-texts.com — extracts clean text from HTML pages.

Uses httpx + basic HTML parsing (no heavy deps needed for sacred-texts.com's simple HTML).
"""

import re
import time
import httpx
from pathlib import Path


def strip_html_tags(html: str) -> str:
    """Remove HTML tags, decode entities, normalize whitespace."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def download_ashtavakra_gita(output_dir: Path) -> Path:
    """Download all 20 chapters of Ashtavakra Gita from sacred-texts.com."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "ashtavakra_gita_richards.txt"

    if output_path.exists():
        print(f"  Already downloaded: {output_path.name}")
        return output_path

    base_url = "https://sacred-texts.com/hin/agr/agr{:02d}.htm"
    all_text = []

    for chapter in range(1, 21):
        url = base_url.format(chapter)
        print(f"  Fetching chapter {chapter}: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AntarDarshan/0.1 (research; public-domain-texts)"
        }
        try:
            resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

        # Extract body content (between <body> tags)
        body_match = re.search(r"<body[^>]*>(.*?)</body>", resp.text, re.DOTALL | re.IGNORECASE)
        if body_match:
            body_html = body_match.group(1)
        else:
            body_html = resp.text

        clean = strip_html_tags(body_html)

        # Remove navigation/footer boilerplate from sacred-texts
        # These pages have "Next:" links and site nav at bottom
        clean = re.split(r"\n(?:Next:|Return to)", clean)[0].strip()

        all_text.append(f"CHAPTER {chapter}\n\n{clean}")
        time.sleep(1)  # polite crawl delay

    combined = "\n\n---\n\n".join(all_text)
    output_path.write_text(combined, encoding="utf-8")
    print(f"  Saved: {output_path.name} ({len(combined):,} chars, {len(all_text)} chapters)")
    return output_path


if __name__ == "__main__":
    corpus_dir = Path(__file__).parent.parent.parent / "corpus" / "raw"
    download_ashtavakra_gita(corpus_dir)
