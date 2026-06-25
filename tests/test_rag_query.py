from backend import rag_query
from backend.query_analysis import QueryIntent


def _hit(scripture: str, tradition: str, score: float = 1.0) -> dict:
    return {
        "scripture": scripture,
        "tradition": tradition,
        "text": f"{scripture} sample text",
        "score": score,
        "chapter": 1,
        "verse": 1,
        "translator": "t",
    }


def test_balance_by_source_caps_dominant_source():
    hits = [
        _hit("Mahabharata", "hindu_vedanta", 0.99),
        _hit("Mahabharata", "hindu_vedanta", 0.98),
        _hit("Mahabharata", "hindu_vedanta", 0.97),
        _hit("Mahabharata", "hindu_vedanta", 0.96),
        _hit("Bhagavad Gita", "hindu_vedanta", 0.95),
        _hit("Dhammapada", "buddhist", 0.94),
        _hit("Katha Upanishad", "hindu_vedanta", 0.93),
    ]

    balanced = rag_query._balance_by_source(hits, max_per_source=2, total_cap=6)
    counts = {}
    for hit in balanced:
        counts[hit["scripture"]] = counts.get(hit["scripture"], 0) + 1

    assert counts.get("Mahabharata", 0) == 2
    assert len(balanced) <= 6


def test_balance_by_source_relaxes_when_few_sources():
    hits = [
        _hit("SourceA", "hindu_vedanta", 0.99),
        _hit("SourceA", "hindu_vedanta", 0.98),
        _hit("SourceA", "hindu_vedanta", 0.97),
        _hit("SourceA", "hindu_vedanta", 0.96),
        _hit("SourceB", "buddhist", 0.95),
        _hit("SourceB", "buddhist", 0.94),
        _hit("SourceB", "buddhist", 0.93),
        _hit("SourceB", "buddhist", 0.92),
    ]

    balanced = rag_query._balance_by_source(hits, max_per_source=2, total_cap=8)
    assert len(balanced) == 8


def test_comparison_search_respects_top_k(monkeypatch):
    def fake_hybrid(_dense, _sparse, qdrant_filter, limit):
        # Filter has exactly one tradition in comparison mode.
        tradition = qdrant_filter.must[0].match.value
        return [
            _hit(f"{tradition}-source-{i}", tradition, score=1 - i * 0.01)
            for i in range(limit)
        ]

    def fake_rerank(_query, hits, top_k=5):
        return hits[:top_k]

    monkeypatch.setattr(rag_query, "_hybrid_retrieve", fake_hybrid)
    monkeypatch.setattr(rag_query, "_rerank", fake_rerank)

    results = rag_query._comparison_search(
        "compare vedanta and buddhist teachings on self",
        dense_vector=[],
        sparse_dict=None,
        top_k=5,
    )

    assert len(results) <= 5
    traditions = {hit["tradition"] for hit in results}
    assert "hindu_vedanta" in traditions
    assert "buddhist" in traditions


def test_hybrid_retrieve_fallback_keeps_filter(monkeypatch):
    class DummyResults:
        points = []

    class DummyClient:
        def __init__(self):
            self.calls = []

        def query_points(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise RuntimeError("first call fails")
            return DummyResults()

    dummy = DummyClient()
    monkeypatch.setattr(rag_query, "_get_client", lambda: dummy)

    sentinel_filter = object()
    out = rag_query._hybrid_retrieve([0.1, 0.2], None, sentinel_filter, limit=5)

    assert out == []
    assert len(dummy.calls) == 2
    assert (
        dummy.calls[1].get("query_filter") is sentinel_filter
        or dummy.calls[1].get("filter") is sentinel_filter
    )


def test_inject_soft_scripture_candidates_when_missing(monkeypatch):
    def fake_hybrid(_dense, _sparse, qdrant_filter, limit):
        target = qdrant_filter.must[0].match.value
        return [_hit(target, "hindu_vedanta", 0.9) for _ in range(limit)]

    monkeypatch.setattr(rag_query, "_hybrid_retrieve", fake_hybrid)
    intent = QueryIntent(
        mode="well_being",
        scripture_filter="Bhagavad Gita",
        filter_strength="soft",
    )
    hits = [_hit("Mahabharata", "hindu_vedanta", 0.8)]
    out = rag_query._inject_soft_filter_candidates(hits, [], None, intent, fallback_limit=2)

    assert len(out) >= 3
    assert out[0]["scripture"] == "Bhagavad Gita"


def test_inject_soft_tradition_candidates_skips_when_present(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Should not fetch fallback when tradition already present")

    monkeypatch.setattr(rag_query, "_hybrid_retrieve", fail_if_called)
    intent = QueryIntent(
        mode="citation",
        tradition_filter="hindu_yoga",
        filter_strength="soft",
    )
    hits = [_hit("Yoga Sutras", "hindu_yoga", 0.9), _hit("Dhammapada", "buddhist", 0.8)]
    out = rag_query._inject_soft_filter_candidates(hits, [], None, intent, fallback_limit=2)

    assert out == hits


def test_ensure_soft_scripture_target_presence():
    intent = QueryIntent(
        mode="well_being",
        scripture_filter="Bhagavad Gita",
        filter_strength="soft",
    )
    candidates = [_hit("Bhagavad Gita", "hindu_vedanta", 0.95), _hit("Mahabharata", "hindu_vedanta", 0.9)]
    final = [_hit("Mahabharata", "hindu_vedanta", 0.9), _hit("Dhammapada", "buddhist", 0.8)]

    out = rag_query._ensure_soft_target_presence(final, candidates, intent, top_k=2)
    assert out[0]["scripture"] == "Bhagavad Gita"


def test_ensure_soft_tradition_target_presence():
    intent = QueryIntent(
        mode="citation",
        tradition_filter="hindu_yoga",
        filter_strength="soft",
    )
    candidates = [_hit("Yoga Sutras", "hindu_yoga", 0.95), _hit("Dhammapada", "buddhist", 0.9)]
    final = [_hit("Dhammapada", "buddhist", 0.9), _hit("Majjhima Nikaya", "buddhist", 0.85)]

    out = rag_query._ensure_soft_target_presence(final, candidates, intent, top_k=2)
    assert out[0]["tradition"] == "hindu_yoga"


# ── Reading-mode retrieval helpers ────────────────────────────────────

def _hits_mixed(target: str, n_target: int, n_other: int) -> list[dict]:
    """Build a hit list with n_target from target scripture and n_other from 'OtherBook'."""
    return (
        [_hit(target, "buddhist") for _ in range(n_target)] +
        [_hit("OtherBook", "hindu_vedanta") for _ in range(n_other)]
    )


def test_balance_for_reading_mode_caps_non_target():
    from backend.rag_query import _balance_for_reading_mode
    hits = _hits_mixed("Samyutta Nikaya", n_target=6, n_other=6)
    balanced = _balance_for_reading_mode(hits, target="Samyutta Nikaya",
                                          max_per_source=2, target_max=4, total_cap=20)
    from_target = [h for h in balanced if h["scripture"] == "Samyutta Nikaya"]
    from_other  = [h for h in balanced if h["scripture"] == "OtherBook"]
    assert len(from_target) == 4   # target allowed up to target_max=4
    assert len(from_other)  == 2   # non-target capped at max_per_source=2


def test_balance_for_reading_mode_handles_sparse_target():
    """If the target book has fewer results than target_max, we take what's available."""
    from backend.rag_query import _balance_for_reading_mode
    hits = _hits_mixed("Samyutta Nikaya", n_target=2, n_other=10)
    balanced = _balance_for_reading_mode(hits, target="Samyutta Nikaya",
                                          max_per_source=2, target_max=4, total_cap=20)
    from_target = [h for h in balanced if h["scripture"] == "Samyutta Nikaya"]
    assert len(from_target) == 2   # only 2 available, that's all we get


def test_ensure_reading_mode_presence_swaps_in_when_needed():
    """If reranker demotes target results, ensure_reading_mode_presence swaps them in."""
    from backend.rag_query import _ensure_reading_mode_presence
    # Final hits: only 1 from target (reranker demoted others)
    final = [_hit("Samyutta Nikaya", "buddhist")] + [_hit("OtherBook", "hindu_vedanta") for _ in range(4)]
    # Candidates pool has more target hits available
    candidates = [_hit("Samyutta Nikaya", "buddhist") for _ in range(5)] + \
                 [_hit("OtherBook", "hindu_vedanta") for _ in range(5)]
    result = _ensure_reading_mode_presence(final, candidates, "Samyutta Nikaya", min_hits=3, top_k=5)
    from_target = [h for h in result if h["scripture"] == "Samyutta Nikaya"]
    assert len(from_target) >= 3
    assert len(result) == 5


def test_ensure_reading_mode_presence_no_change_when_already_enough():
    """Does not alter results when target already meets min_hits."""
    from backend.rag_query import _ensure_reading_mode_presence
    final = [_hit("Samyutta Nikaya", "buddhist") for _ in range(3)] + \
            [_hit("OtherBook", "hindu_vedanta") for _ in range(2)]
    result = _ensure_reading_mode_presence(final, final, "Samyutta Nikaya", min_hits=3, top_k=5)
    assert result == final[:5]


def test_ratio_based_min_hits():
    """Ratio policy: top_k=5→3, top_k=3→2, top_k=10→6."""
    assert max(1, round(5  * 0.6)) == 3
    assert max(1, round(3  * 0.6)) == 2
    assert max(1, round(10 * 0.6)) == 6
    assert max(1, round(1  * 0.6)) == 1  # never goes below 1
