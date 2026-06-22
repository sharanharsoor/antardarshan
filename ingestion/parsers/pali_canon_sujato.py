"""
Parser for SuttaCentral bilara-data translations (Bhikkhu Sujato, CC0).

Handles all five Nikayas: MN, DN, SN, AN, KN (and sub-collections).

One JSON file = one sutta. Segments keyed as "{sutta_id}:{section}.{line}".
  - Segments 0.x → title/heading (used for metadata, not body text)
  - Segments N.x → body paragraphs for section N

Chunking strategy:
  - Short suttas (<600 words): one chunk per sutta
  - Long suttas (≥600 words): split by major section number (1.x, 2.x, ...)
    combining all lines within each section into one chunk

The Anattalakkhana Sutta (MN109/SN22.59) is in here — the Buddha's primary
teaching on anatta (no-self) that answers "What does Buddhism say about the self?"
"""

import json
import re
from pathlib import Path

from ingestion.schema import ScriptureChunk

SOURCE_URL = "https://suttacentral.net"

NIKAYA_META = {
    "dn": ("Digha Nikaya", "Long Discourses"),
    "mn": ("Majjhima Nikaya", "Middle Discourses"),
    "sn": ("Samyutta Nikaya", "Linked Discourses"),
    "an": ("Anguttara Nikaya", "Numbered Discourses"),
    "kn": ("Khuddaka Nikaya", "Minor Collection"),
    # KN sub-collections
    "dhp": ("Dhammapada", "Verses on the Dhamma"),
    "ud": ("Udana", "Inspired Utterances"),
    "iti": ("Itivuttaka", "So It Was Said"),
    "snp": ("Sutta Nipata", "The Sutta Nipata"),
    "thag": ("Theragatha", "Verses of the Elder Monks"),
    "thig": ("Therigatha", "Verses of the Elder Nuns"),
}

# Themes for Buddhist suttas
THEME_KEYWORDS = {
    "anatta": ["self", "no-self", "not-self", "anatta", "identity", "soul", "who", "what am"],
    "impermanence": ["imperman", "chang", "decay", "mortal", "death", "pass away", "anicca"],
    "dukkha": ["suffer", "stress", "pain", "dukkha", "dissatisf", "unsatisf"],
    "nibbana": ["nibbana", "nirvana", "liberation", "freedom", "unbound", "extinguish"],
    "mindfulness": ["mindful", "aware", "observe", "present", "heedful", "diligen"],
    "dependent_origination": ["dependent", "condition", "arising", "craving", "ignorance", "birth"],
    "ethics": ["precept", "virtue", "moral", "right action", "right speech", "right livelihood"],
    "meditation": ["meditat", "jhana", "concentrat", "samadhi", "calm", "still", "breath"],
    "compassion": ["compassion", "loving-kindness", "metta", "karuna", "goodwill"],
    "wisdom": ["wisdom", "understanding", "knowledge", "discern", "insight", "panna"],
}

MAX_WORDS_PER_CHUNK = 600


def _detect_themes(text: str) -> list[str]:
    t = text.lower()
    return [theme for theme, kws in THEME_KEYWORDS.items() if any(kw in t for kw in kws)][:4]


def _nikaya_code(sutta_id: str) -> str:
    """Extract nikaya code from sutta ID. E.g. 'mn22' → 'mn', 'sn22.59' → 'sn'."""
    m = re.match(r"^([a-z]+)", sutta_id.lower())
    return m.group(1) if m else "unknown"


def _sutta_chapter_verse(sutta_id: str) -> tuple[int, int]:
    """
    Extract (chapter, verse) from sutta ID.

    Handles two formats:
      Simple:   mn22  → (1, 22)   — MN/DN use sequential numbering, chapter=1
      Compound: an1.2 → (1, 2)    — AN/SN encode chapter.verse in ID
                sn22.59 → (22, 59)
    """
    m = re.search(r"(\d+)(?:\.(\d+))?$", sutta_id)
    if not m:
        return 1, 1
    first = int(m.group(1))
    second = int(m.group(2)) if m.group(2) else None
    if second is not None:
        # Compound ID: first = chapter (nipata/samyutta), second = verse
        return first, second
    else:
        # Simple ID: single sequential number, all in chapter 1
        return 1, first


def parse_sutta_file(filepath: Path) -> list[ScriptureChunk]:
    """
    Parse one SuttaCentral bilara JSON file into verse-level chunks.
    Handles both short and long suttas correctly.
    """
    data: dict[str, str] = json.loads(filepath.read_text(encoding="utf-8"))
    if not data:
        return []

    # Extract sutta ID from first key
    first_key = next(iter(data))
    sutta_id = first_key.split(":")[0]
    nikaya_code = _nikaya_code(sutta_id)

    # Nikaya metadata
    nikaya_name, _ = NIKAYA_META.get(nikaya_code, (nikaya_code.upper(), nikaya_code.upper()))
    scripture_name = nikaya_name

    # Collect title (segment 0.x) and body segments
    title_parts: list[str] = []
    body_by_section: dict[int, list[str]] = {}

    for key, value in data.items():
        if not value or not value.strip():
            continue
        # Key format: "{sutta_id}:{section}.{line}"
        try:
            seg_part = key.split(":")[1]
            section_str, _ = seg_part.split(".", 1)
            section = int(section_str)
        except (IndexError, ValueError):
            continue

        text = value.strip()
        if not text:
            continue

        if section == 0:
            title_parts.append(text)
        else:
            body_by_section.setdefault(section, []).append(text)

    sutta_title = " — ".join(title_parts) if title_parts else sutta_id
    chapter_name = sutta_title  # use for chapter_name field

    # Flatten body text per section
    sections = sorted(body_by_section.keys())
    section_texts: dict[int, str] = {
        sec: " ".join(body_by_section[sec])
        for sec in sections
    }

    full_text = " ".join(section_texts.values())
    if not full_text.strip() or len(full_text.split()) < 10:
        return []

    chunks: list[ScriptureChunk] = []

    # Determine canonical chapter and verse from sutta ID
    sutta_chapter, sutta_verse = _sutta_chapter_verse(sutta_id)

    # Decide chunking: short suttas → one chunk; long → split by section
    total_words = len(full_text.split())

    if total_words < MAX_WORDS_PER_CHUNK or not sections:
        # One chunk for the whole sutta
        chunks.append(ScriptureChunk(
            text=full_text,
            scripture=scripture_name,
            tradition="buddhist",
            chapter=sutta_chapter,
            verse=sutta_verse,
            translator="Bhikkhu Sujato",
            year=2021,
            language="en",
            license_tier="A",
            source_url=f"{SOURCE_URL}/{sutta_id}",
            chunk_type="prose",
            verse_type="segment",
            chapter_name=chapter_name,
            themes=_detect_themes(full_text),
        ))
    else:
        # Split by section — each major section (1, 2, 3...) becomes a chunk
        current_text_parts: list[str] = []
        chunk_part = 0  # sub-part counter for long suttas

        for sec in sections:
            sec_text = section_texts[sec]
            current_text_parts.append(sec_text)
            combined = " ".join(current_text_parts)

            # Emit chunk when we reach word limit or end of sections
            is_last = sec == sections[-1]
            if len(combined.split()) >= MAX_WORDS_PER_CHUNK or is_last:
                if combined.strip():
                    chunks.append(ScriptureChunk(
                        text=combined.strip(),
                        scripture=scripture_name,
                        tradition="buddhist",
                        chapter=sutta_chapter,
                        verse=sutta_verse * 1000 + chunk_part,  # unique within chapter
                        translator="Bhikkhu Sujato",
                        year=2021,
                        language="en",
                        license_tier="A",
                        source_url=f"{SOURCE_URL}/{sutta_id}",
                        chunk_type="prose",
                        verse_type="segment",
                        chapter_name=f"{chapter_name} (part {chunk_part + 1})" if chunk_part > 0 else chapter_name,
                        themes=_detect_themes(combined),
                    ))
                    current_text_parts = []
                    chunk_part += 1

    return chunks


def parse_nikaya(nikaya_dir: Path, nikaya_code: str) -> list[ScriptureChunk]:
    """
    Parse all suttas in a Nikaya directory.

    Args:
        nikaya_dir: Path to the nikaya directory containing *_translation-en-sujato.json files
        nikaya_code: 'mn', 'dn', 'sn', 'an', or 'kn'
    """
    if not nikaya_dir.exists():
        return []

    chunks: list[ScriptureChunk] = []
    # SN and AN have subdirectories (sn38/, sn22/, etc.) — use recursive glob
    json_files = sorted(nikaya_dir.rglob("*_translation-en-sujato.json"))

    for json_file in json_files:
        try:
            sutta_chunks = parse_sutta_file(json_file)
            chunks.extend(sutta_chunks)
        except Exception as e:
            print(f"  Warning: failed to parse {json_file.name}: {e}")

    return chunks


def parse_pali_canon(sc_data_dir: Path, nikayas: list[str] | None = None) -> dict[str, list[ScriptureChunk]]:
    """
    Parse all requested Nikayas from the SuttaCentral bilara-data directory.

    Args:
        sc_data_dir: Path to sc-data/ directory
        nikayas: List of nikaya codes to parse. Defaults to ['mn', 'dn', 'sn', 'an'].
                 'kn' sub-collections are handled separately.

    Returns:
        Dict mapping nikaya_code → list of ScriptureChunks
    """
    if nikayas is None:
        nikayas = ["dn", "mn", "sn", "an"]

    base = sc_data_dir / "translation" / "en" / "sujato" / "sutta"
    results: dict[str, list[ScriptureChunk]] = {}

    for code in nikayas:
        nikaya_dir = base / code
        if not nikaya_dir.exists():
            print(f"  ✗ {code.upper()} directory not found: {nikaya_dir}")
            continue

        chunks = parse_nikaya(nikaya_dir, code)
        results[code] = chunks
        nikaya_name = NIKAYA_META.get(code, (code.upper(),))[0]
        print(f"  ✓ {nikaya_name} ({code.upper()}): {len(chunks)} chunks from {code.upper()}")

    return results
