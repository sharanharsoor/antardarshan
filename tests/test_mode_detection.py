"""
Unit tests for query mode detection.

Ensures correct routing to citation/well_being/exploration/comparison modes.
"""

from backend.rag_query import detect_mode


class TestCitationMode:
    def test_simple_question(self):
        assert detect_mode("What does the Gita say about karma?") == "citation"

    def test_verse_reference(self):
        assert detect_mode("Explain Bhagavad Gita chapter 2 verse 47") == "citation"

    def test_concept_query(self):
        assert detect_mode("What is dharma?") == "citation"


class TestWellBeingMode:
    def test_grief(self):
        assert detect_mode("I am going through grief after losing my father") == "well_being"

    def test_anxiety(self):
        assert detect_mode("I feel anxious about my future") == "well_being"

    def test_stress(self):
        assert detect_mode("I am stressed about work and life") == "well_being"

    def test_sadness(self):
        assert detect_mode("I feel sad and lonely") == "well_being"

    def test_lost(self):
        assert detect_mode("I feel lost and don't know my purpose") == "well_being"


class TestComparisonMode:
    def test_vedanta_vs_buddhism(self):
        assert detect_mode("How does Vedanta differ from Buddhism on the self?") == "comparison"

    def test_buddhism_vedanta_reverse(self):
        assert detect_mode("How does Buddhism compare to Advaita?") == "comparison"

    def test_advaita_dvaita(self):
        assert detect_mode("What is the difference between Advaita and Dvaita?") == "comparison"

    def test_two_traditions_mentioned(self):
        assert detect_mode("Buddhist and Jain views on non-violence") == "comparison"


class TestExplorationMode:
    def test_walk_through(self):
        assert detect_mode("Walk me through Ashtavakra Gita chapter 1") == "exploration"

    def test_guide(self):
        assert detect_mode("Guide me through the Dhammapada") == "exploration"
