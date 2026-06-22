"""
Tests for query intent analysis.

Focuses on scripture detection correctness and regression guards
for ambiguous names like "Gita".
"""

from backend.query_analysis import analyze_query


def test_ashtavakra_gita_maps_to_ashtavakra():
    intent = analyze_query("What does Ashtavakra Gita say about liberation?")
    assert intent.scripture_filter == "Ashtavakra Gita"
    assert intent.filter_strength == "hard"


def test_generic_gita_maps_to_bhagavad_gita():
    intent = analyze_query("What does the Gita say about duty?")
    assert intent.scripture_filter == "Bhagavad Gita"
    assert intent.filter_strength == "hard"


def test_bhagavad_gita_maps_to_bhagavad_gita():
    intent = analyze_query("In Bhagavad Gita chapter 2, what is karma yoga?")
    assert intent.scripture_filter == "Bhagavad Gita"
    assert intent.filter_strength == "hard"


def test_comparison_mode_detects_multi_tradition_query():
    intent = analyze_query("How does Buddhism compare to Vedanta on the self?")
    assert intent.mode == "comparison"


def test_meditation_query_sets_yoga_tradition_soft_filter():
    intent = analyze_query("meditation and concentration")
    assert intent.mode == "citation"
    assert intent.tradition_filter == "hindu_yoga"
    assert intent.filter_strength == "soft"


def test_grief_query_gets_soft_gita_hint():
    intent = analyze_query("I am going through grief after losing someone")
    assert intent.mode == "well_being"
    assert intent.scripture_filter == "Bhagavad Gita"
    assert intent.filter_strength == "soft"


def test_grief_with_explicit_buddhist_context_does_not_force_gita():
    intent = analyze_query("I feel grief and want a Buddhist perspective")
    assert intent.mode == "well_being"
    assert intent.scripture_filter is None
    assert intent.tradition_filter == "buddhist"
