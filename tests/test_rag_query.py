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
