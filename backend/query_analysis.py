"""
Query analysis for AntarDarshan.

Detects:
- Explicit scripture names → metadata filter (hard or soft)
- Tradition scope → metadata filter
- Mode (citation, well_being, comparison, exploration)
- Sanskrit/Pali terms for BM25 boosting

Returns structured filters for the hybrid retrieval pipeline.
"""

import re
from dataclasses import dataclass, field


# Scripture name patterns (order matters — more specific first)
SCRIPTURE_PATTERNS = [
    (r"\b(?:ashtavakra[\s-]?gita|ashtavakra)\b", "Ashtavakra Gita"),
    (r"\b(?:bhagavad[\s-]?gita|bg)\b", "Bhagavad Gita"),
    # Generic "gita" falls back to Bhagavad Gita only after specific Gita texts.
    (r"\bgita\b", "Bhagavad Gita"),
    (r"\b(?:katha[\s-]?upanishad|katha)\b", "Katha Upanishad"),
    (r"\b(?:isha[\s-]?upanishad|isha)\b", "Isha Upanishad"),
    (r"\b(?:kena[\s-]?upanishad|kena)\b", "Kena Upanishad"),
    (r"\b(?:mundaka[\s-]?upanishad|mundaka)\b", "Mundaka Upanishad"),
    (r"\b(?:prashna[\s-]?upanishad|prashna)\b", "Prashna Upanishad"),
    (r"\b(?:taittiriya[\s-]?upanishad|taittiriya)\b", "Taittiriya Upanishad"),
    (r"\b(?:brihadaranyaka[\s-]?upanishad|brihadaranyaka)\b", "Brihadaranyaka Upanishad"),
    (r"\b(?:svetasvatara[\s-]?upanishad|svetasvatara)\b", "Svetasvatara Upanishad"),
    (r"\b(?:chandogya[\s-]?upanishad|chandogya)\b", "Chandogya Upanishad"),
    (r"\b(?:dhammapada|dhammpada)\b", "Dhammapada"),
    (r"\b(?:yoga[\s-]?sutra|patanjali)\b", "Yoga Sutras"),
    (r"\b(?:upanishad)s?\b", None),  # generic "upanishads" → tradition filter only
    (r"\b(?:vivekananda|swami vivekananda)\b", None),  # → filter tradition + partial scripture name
]

TRADITION_PATTERNS = [
    # Note: leading \b but no trailing \b on partial stems (e.g. "buddh" must match "Buddhist")
    (r"\b(?:vedant|advaita|dvaita|vishishtadvaita|vedanta|hindu)", "hindu_vedanta"),
    (r"\b(?:buddh|theravada|pali|dhamma|sutta)",                  "buddhist"),
    (r"\b(?:yoga|patanjali|samadhi|pranayama|meditation|concentration|dhyana)", "hindu_yoga"),
    (r"\b(?:jain|mahavir|tattvartha)",                            "jain"),
    (r"\b(?:sikh|gurbani|nanak)",                                 "sikh"),
]

# Mode detection
WELL_BEING_SIGNALS = [
    "feel", "anxious", "grief", "lost", "stress", "scared", "worry",
    "sad", "depress", "help me", "suffering", "pain", "lonely", "confused",
    "angry", "afraid", "hopeless", "meaningless", "purpose",
]

COMPARISON_WORDS = ["differ", "compar", "vs ", "versus", "contrast", "between"]

EXPLORATION_SIGNALS = ["walk me through", "explain chapter", "what does verse", "guide me", "read through"]

# Well-being hint routing for grief/bereavement style prompts.
# Keep this soft and only when no explicit scripture/tradition is requested.
WELL_BEING_SCRIPTURE_HINTS = [
    (r"\b(?:grief|bereavement|mourning|losing someone|loss)\b", "Bhagavad Gita"),
]


@dataclass
class QueryIntent:
    """Structured output of query analysis."""
    mode: str = "citation"  # citation | well_being | comparison | exploration
    scripture_filter: str | None = None  # exact scripture name to filter for
    tradition_filter: str | None = None  # tradition to filter for
    filter_strength: str = "soft"  # "hard" = must match, "soft" = boost but don't exclude
    detected_terms: list[str] = field(default_factory=list)  # Sanskrit/key terms detected


def analyze_query(query: str) -> QueryIntent:
    """Analyze a user query and return structured intent + filters."""
    q_lower = query.lower()
    intent = QueryIntent()

    # --- Detect mode ---
    traditions_mentioned = []
    for pattern, tradition in TRADITION_PATTERNS:
        if re.search(pattern, q_lower):
            traditions_mentioned.append(tradition)

    if len(traditions_mentioned) >= 2 or any(w in q_lower for w in COMPARISON_WORDS):
        intent.mode = "comparison"
    elif any(s in q_lower for s in WELL_BEING_SIGNALS):
        intent.mode = "well_being"
    elif any(s in q_lower for s in EXPLORATION_SIGNALS):
        intent.mode = "exploration"
    else:
        intent.mode = "citation"

    # --- Detect scripture ---
    for pattern, scripture_name in SCRIPTURE_PATTERNS:
        if re.search(pattern, q_lower, re.IGNORECASE):
            if scripture_name:
                intent.scripture_filter = scripture_name
                # If user explicitly names a scripture, use hard filter
                intent.filter_strength = "hard"
            break

    # --- Detect tradition (if no specific scripture) ---
    if not intent.scripture_filter and traditions_mentioned:
        intent.tradition_filter = traditions_mentioned[0]
        intent.filter_strength = "soft"

    # --- Soft scripture hints for emotional queries without explicit tradition/scripture ---
    if intent.mode == "well_being" and not intent.scripture_filter and not traditions_mentioned:
        for pattern, scripture_name in WELL_BEING_SCRIPTURE_HINTS:
            if re.search(pattern, q_lower):
                intent.scripture_filter = scripture_name
                intent.filter_strength = "soft"
                break

    # --- For comparison mode, don't filter (need results from multiple traditions) ---
    if intent.mode == "comparison":
        intent.filter_strength = "soft"

    return intent
