"""
Batch fetch Vivekananda's works from Wikisource.

Run this with full network access. Fetches key chapters from Raja-Yoga,
Karma-Yoga, and Jnana-Yoga (Volume 1-2).

Usage:
    python -m ingestion.scrapers.fetch_vivekananda
"""

import re
import time
import httpx
from pathlib import Path

CORPUS_RAW = Path(__file__).parent.parent.parent / "corpus" / "raw" / "vivekananda"
BASE_URL = "https://en.wikisource.org/wiki/The_Complete_Works_of_Swami_Vivekananda"
# ?action=raw returns wikitext — clean, no HTML needed
RAW_URL = "https://en.wikisource.org/w/index.php?title=The_Complete_Works_of_Swami_Vivekananda/{path}&action=raw"
HEADERS = {"User-Agent": "Mozilla/5.0 AntarDarshan/0.1 (research, public-domain-texts)"}


def extract_wikitext(wikitext: str) -> str:
    """Convert Wikisource wikitext to clean plain text.

    Uses ?action=raw which returns wikitext — much simpler than parsing HTML.
    """
    text = wikitext

    # Remove templates {{...}} (navigation, headers, footers)
    # Nested templates need iterative removal
    for _ in range(5):
        text = re.sub(r'\{\{[^{}]*\}\}', '', text)

    # Remove [[File:...]] and [[Image:...]] embeds
    text = re.sub(r'\[\[(?:File|Image):[^\]]*\]\]', '', text, flags=re.IGNORECASE)

    # Convert [[link|display]] → display text
    text = re.sub(r'\[\[[^\]|]*\|([^\]]*)\]\]', r'\1', text)
    # Convert [[link]] → link text
    text = re.sub(r'\[\[([^\]]*)\]\]', r'\1', text)

    # Strip bold/italic markup
    text = re.sub(r"'''(.*?)'''", r'\1', text)
    text = re.sub(r"''(.*?)''", r'\1', text)

    # Convert wiki headings to plain text
    text = re.sub(r'^={1,6}\s*(.*?)\s*={1,6}\s*$', r'\1', text, flags=re.MULTILINE)

    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # Strip remaining HTML tags (rare in wikitext but possible)
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    text = text.replace('&#160;', ' ').replace('&mdash;', '—').replace('&ndash;', '–')

    # Remove category lines and __NOINDEX__ etc
    text = re.sub(r'^\[\[Category:.*\]\]\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^__[A-Z]+__\s*$', '', text, flags=re.MULTILINE)

    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# Key chapters to fetch (most philosophically relevant)
CHAPTERS = [
    # Raja-Yoga (Volume 1) — meditation and mind control
    ("Volume_1/Raja-Yoga/Introductory", "raja_yoga_ch1_introductory.txt", "Raja-Yoga", "Introductory", 1),
    ("Volume_1/Raja-Yoga/The_First_Steps", "raja_yoga_ch2_first_steps.txt", "Raja-Yoga", "The First Steps", 2),
    ("Volume_1/Raja-Yoga/Prana", "raja_yoga_ch3_prana.txt", "Raja-Yoga", "Prana", 3),
    ("Volume_1/Raja-Yoga/The_Psychic_Prana", "raja_yoga_ch4_psychic_prana.txt", "Raja-Yoga", "The Psychic Prana", 4),
    ("Volume_1/Raja-Yoga/The_Control_of_the_Psychic_Prana", "raja_yoga_ch5_control.txt", "Raja-Yoga", "Control of Psychic Prana", 5),
    ("Volume_1/Raja-Yoga/Pratyahara_and_Dharana", "raja_yoga_ch6_dharana.txt", "Raja-Yoga", "Pratyahara and Dharana", 6),
    ("Volume_1/Raja-Yoga/Dhyana_and_Samadhi", "raja_yoga_ch7_samadhi.txt", "Raja-Yoga", "Dhyana and Samadhi", 7),
    ("Volume_1/Raja-Yoga/Raja-Yoga_in_Brief", "raja_yoga_ch8_brief.txt", "Raja-Yoga", "Raja-Yoga in Brief", 8),

    # Karma-Yoga (Volume 1) — action and duty
    ("Volume_1/Karma-Yoga/Karma_in_its_Effect_on_Character", "karma_yoga_ch1.txt", "Karma-Yoga", "Karma in its Effect on Character", 1),
    ("Volume_1/Karma-Yoga/Each_Is_Great_in_His_Own_Place", "karma_yoga_ch2.txt", "Karma-Yoga", "Each is Great in His Own Place", 2),
    ("Volume_1/Karma-Yoga/The_Secret_of_Work", "karma_yoga_ch3.txt", "Karma-Yoga", "The Secret of Work", 3),
    ("Volume_1/Karma-Yoga/What_is_Duty%3F", "karma_yoga_ch4.txt", "Karma-Yoga", "What is Duty?", 4),
    ("Volume_1/Karma-Yoga/We_Help_Ourselves,_not_the_World", "karma_yoga_ch5.txt", "Karma-Yoga", "We Help Ourselves Not the World", 5),
    ("Volume_1/Karma-Yoga/Non-Attachment_Is_Complete_Self-Abnegation", "karma_yoga_ch6.txt", "Karma-Yoga", "Non-Attachment is Complete Self-Abnegation", 6),
    ("Volume_1/Karma-Yoga/Freedom", "karma_yoga_ch7.txt", "Karma-Yoga", "Freedom", 7),
    ("Volume_1/Karma-Yoga/The_Ideal_of_Karma-Yoga", "karma_yoga_ch8.txt", "Karma-Yoga", "The Ideal of Karma-Yoga", 8),

    # Jnana-Yoga (Volume 2) — knowledge and Vedanta
    ("Volume_2/Jnana-Yoga/The_Real_and_the_Apparent_Man", "jnana_yoga_ch1.txt", "Jnana-Yoga", "The Real and the Apparent Man", 1),
    ("Volume_2/Jnana-Yoga/The_Real_Nature_of_Man", "jnana_yoga_ch2.txt", "Jnana-Yoga", "The Real Nature of Man", 2),
    ("Volume_2/Jnana-Yoga/Maya_and_Illusion", "jnana_yoga_ch3.txt", "Jnana-Yoga", "Maya and Illusion", 3),
    ("Volume_2/Jnana-Yoga/Maya_and_the_Evolution_of_the_Conception_of_God", "jnana_yoga_ch4.txt", "Jnana-Yoga", "Maya and the Evolution of the Conception of God", 4),
    ("Volume_2/Jnana-Yoga/Maya_and_Freedom", "jnana_yoga_ch5.txt", "Jnana-Yoga", "Maya and Freedom", 5),
    ("Volume_2/Jnana-Yoga/The_Absolute_and_Manifestation", "jnana_yoga_ch6.txt", "Jnana-Yoga", "The Absolute and Manifestation", 6),
]


def fetch_chapter(url_path: str, filename: str, force: bool = False):
    """Fetch a single chapter from Wikisource, extracting clean text from HTML."""
    output_path = CORPUS_RAW / filename

    if output_path.exists() and not force:
        # Check if it's a stale HTML file (starts with <!DOCTYPE)
        first_line = output_path.read_text(encoding="utf-8", errors="ignore")[:20]
        if first_line.startswith("<!"):
            print(f"  Re-fetching {filename} (stale HTML)")
        else:
            print(f"  Already exists: {filename}")
            return True

    url = RAW_URL.format(path=url_path)
    try:
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        clean_text = extract_wikitext(resp.text)
        output_path.write_text(clean_text, encoding="utf-8")
        print(f"  Fetched: {filename} ({len(clean_text):,} chars clean text)")
        return True
    except Exception as e:
        print(f"  FAILED: {filename} — {e}")
        return False


def main():
    import sys
    force = "--force" in sys.argv  # Re-fetch and clean all, even existing

    CORPUS_RAW.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(CHAPTERS)} Vivekananda chapters from Wikisource...\n")

    success = 0
    for url_path, filename, book, chapter_name, chapter_num in CHAPTERS:
        if fetch_chapter(url_path, filename, force=force):
            success += 1
        time.sleep(2)  # Polite crawl delay

    print(f"\n{success}/{len(CHAPTERS)} chapters successfully saved.")
    print("Next: Run 'python -m ingestion.process_phase1' to regenerate corpus.")


if __name__ == "__main__":
    main()
