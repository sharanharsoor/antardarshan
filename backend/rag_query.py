"""
AntarDarshan — Hybrid RAG Query Pipeline.

Full pipeline:
1. Query analysis (detect scripture, tradition, mode)
2. Hybrid retrieval (dense + sparse + metadata filter + RRF)
3. Cross-encoder reranking (top-20 → top-5)
4. Return ranked results for LLM synthesis

Supports both prod mode (bge-m3 hybrid) and dev mode (MiniLM dense-only).
"""

import os
import math
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition, MatchValue, Filter, SearchParams,
    Prefetch, FusionQuery, Fusion,
)

from backend.query_analysis import analyze_query, QueryIntent

load_dotenv()

COLLECTION_NAME = "antardarshan_v1"
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")

# Singletons
_model = None
_client = None
_reranker = None


def _get_client():
    global _client
    if _client is None:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        _client = QdrantClient(url=qdrant_url)
    return _client


def _get_model():
    """Load the embedding model (bge-m3 for prod, MiniLM for dev)."""
    global _model
    if _model is None:
        # Set HF token before model load to suppress auth warnings
        import os as _os
        hf_token = _os.getenv("HF_TOKEN")
        if hf_token:
            _os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
            _os.environ["HF_TOKEN"] = hf_token

        if EMBED_MODEL == "BAAI/bge-m3":
            from FlagEmbedding import BGEM3FlagModel
            _model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
        else:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _get_reranker():
    """Load cross-encoder reranker on CPU (lazy, first call only).

    Force CPU explicitly — on Mac with Apple Silicon, loading the reranker on MPS
    (the default) alongside bge-m3 causes out-of-memory errors because both models
    compete for the same 64GB unified memory pool. CPU inference adds ~100ms but
    eliminates OOM crashes entirely.
    """
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", device="cpu")
        except Exception as e:
            print(f"  Reranker load failed: {e}. Skipping reranking.")
            _reranker = "disabled"
    return _reranker if _reranker != "disabled" else None


def _encode_query(query: str):
    """Encode query — returns (dense_vector, sparse_dict_or_None)."""
    model = _get_model()

    if EMBED_MODEL == "BAAI/bge-m3":
        output = model.encode([query], return_dense=True, return_sparse=True)
        dense = output["dense_vecs"][0]
        sparse = output["lexical_weights"][0] if output["lexical_weights"] else None
        return dense.tolist(), sparse
    else:
        embedding = model.encode([query])[0]
        return embedding.tolist(), None


def _build_filter(intent: QueryIntent) -> Filter | None:
    """Build Qdrant metadata filter from query intent."""
    conditions = []

    if intent.scripture_filter and intent.filter_strength == "hard":
        conditions.append(
            FieldCondition(key="scripture", match=MatchValue(value=intent.scripture_filter))
        )
    elif intent.tradition_filter and intent.filter_strength == "hard":
        conditions.append(
            FieldCondition(key="tradition", match=MatchValue(value=intent.tradition_filter))
        )

    return Filter(must=conditions) if conditions else None


def _balance_by_source(
    hits: list[dict],
    max_per_source: int = 2,
    total_cap: int = 20,
) -> list[dict]:
    """
    Cap results per scripture to prevent one large corpus dominating.

    This is the generic solution to corpus imbalance — the "Mahabharata problem".
    No matter how many chunks a single source contributes (today 26%, tomorrow 50%),
    each source is limited to `max_per_source` results in the reranking pool.

    The hits are assumed to be pre-sorted by relevance (RRF score). We walk them
    in order and select greedily — best-scoring chunks first, capped per source.

    Why this works better than score thresholds:
    - Score thresholds need per-corpus calibration (brittle)
    - Per-source capping is O(n) in candidates, calibration-free, and scales linearly
      with corpus size — adding 100K more Mahabharata chunks changes nothing

    Args:
        hits: Retrieval results sorted by relevance (best first)
        max_per_source: Maximum chunks allowed from any single scripture
        total_cap: Maximum total candidates to pass to reranker
    """
    if not hits:
        return []

    unique_sources = {
        hit.get("scripture", "") or "__unknown__"
        for hit in hits
    }
    # Adapt cap when only a few sources are available, so we can still fill total_cap.
    # This keeps behavior generic as corpus composition changes.
    effective_max_per_source = max(max_per_source, math.ceil(total_cap / max(1, len(unique_sources))))

    source_counts: dict[str, int] = {}
    balanced: list[dict] = []

    for hit in hits:
        scripture = hit.get("scripture", "") or "__unknown__"
        count = source_counts.get(scripture, 0)
        if count < effective_max_per_source:
            balanced.append(hit)
            source_counts[scripture] = count + 1
        if len(balanced) >= total_cap:
            break

    return balanced


def _rerank(query: str, hits: list[dict], top_k: int = 5) -> list[dict]:
    """Rerank hits using cross-encoder. Returns top_k best."""
    reranker = _get_reranker()
    if not reranker or len(hits) <= top_k:
        return hits[:top_k]

    pairs = [(query, h["text"]) for h in hits]
    scores = reranker.predict(pairs)

    for hit, score in zip(hits, scores):
        hit["rerank_score"] = float(score)

    hits.sort(key=lambda h: h.get("rerank_score", 0), reverse=True)
    return hits[:top_k]


def _extract_point(point) -> dict:
    """Extract payload from a Qdrant point into a dict."""
    payload = point.payload or {}
    return {
        "score": point.score,
        "text": payload.get("text", ""),
        "scripture": payload.get("scripture", ""),
        "chapter": payload.get("chapter", 0),
        "verse": payload.get("verse", 0),
        "translator": payload.get("translator", ""),
        "tradition": payload.get("tradition", ""),
        "parent_text": payload.get("parent_text", ""),
        "year": payload.get("year", ""),
    }


def _hybrid_retrieve(dense_vector, sparse_dict, qdrant_filter, limit: int) -> list[dict]:
    """Run hybrid retrieval (dense + sparse RRF) with optional filter. Falls back gracefully."""
    client = _get_client()
    try:
        if sparse_dict:
            from qdrant_client.models import SparseVector as SV
            sparse_indices = []
            sparse_values = []
            for idx, value in sparse_dict.items():
                try:
                    sparse_indices.append(int(idx))
                    sparse_values.append(float(value))
                except (TypeError, ValueError):
                    continue
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                prefetch=[
                    Prefetch(query=dense_vector, using="dense", limit=limit, filter=qdrant_filter),
                    Prefetch(
                        query=SV(indices=sparse_indices, values=sparse_values),
                        using="bm25", limit=limit, filter=qdrant_filter,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=limit,
            )
        else:
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=dense_vector, using="dense",
                limit=limit, query_filter=qdrant_filter,
            )
        return [_extract_point(p) for p in results.points]
    except Exception:
        # Fallback: simple dense without named vectors (old collection compat)
        # Keep metadata filter applied so hard-filter intent is not lost.
        try:
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=dense_vector,
                limit=limit,
                query_filter=qdrant_filter,
            )
        except TypeError:
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=dense_vector,
                limit=limit,
                filter=qdrant_filter,
            )
        return [_extract_point(p) for p in results.points]


# Traditions that appear in the corpus — used for comparison partitioning
_TRADITION_KEYWORDS: dict[str, list[str]] = {
    "hindu_vedanta":  ["vedant", "advaita", "dvaita", "upanishad", "gita", "brahman", "atman", "vivekananda"],
    "buddhist":       ["buddh", "dhamma", "theravada", "pali", "nirvana", "anatta", "dhammapada"],
    "hindu_yoga":     ["yoga", "patanjali", "samadhi", "pranayama"],
    "jain":           ["jain", "mahavir"],
    "sikh":           ["sikh", "gurbani", "granth"],
    "sant_bhakti":    ["kabir", "mirabai", "bhakti"],
}


def _comparison_search(query: str, dense_vector, sparse_dict, top_k: int = 5) -> list[dict]:
    """
    Parallel tradition-partitioned retrieval for comparison queries.

    Critical design: reranks WITHIN each tradition first, then takes the top N
    from each and merges. This guarantees Buddhist sources appear alongside
    Vedanta sources even when Vedanta-heavy texts (Vivekananda) score higher
    semantically — because Dhammapada verses don't explicitly say
    "I am comparing myself to Vedanta" but they do contain the relevant teachings.
    """
    q_lower = query.lower()
    target_traditions = [
        t for t, keywords in _TRADITION_KEYWORDS.items()
        if any(kw in q_lower for kw in keywords)
    ]

    # Need at least 2 traditions for a meaningful comparison
    if len(target_traditions) < 2:
        return []

    # Guaranteed quota per tradition (at minimum 2, balanced across traditions)
    guarantee_per_tradition = max(1, top_k // len(target_traditions))
    per_tradition_fetch = max(8, top_k * 3)
    seeded_hits: list[dict] = []
    pooled_hits: list[dict] = []

    for tradition in target_traditions:
        tfilter = Filter(must=[
            FieldCondition(key="tradition", match=MatchValue(value=tradition))
        ])
        # Retrieve ample candidates per tradition so reranker has material to work with.
        candidates = _hybrid_retrieve(dense_vector, sparse_dict, tfilter, limit=per_tradition_fetch)

        # Rerank within this tradition's results only — then take guaranteed quota
        top_for_tradition = _rerank(query, candidates, top_k=max(guarantee_per_tradition, top_k))
        if not top_for_tradition:
            continue

        # Keep at least one seed hit per tradition, then pool the rest.
        seeded_hits.append(top_for_tradition[0])
        pooled_hits.extend(top_for_tradition[1:])

    if not seeded_hits:
        return []

    merged = seeded_hits + pooled_hits
    merged = _balance_by_source(merged, max_per_source=2, total_cap=max(top_k * 4, top_k))
    return _rerank(query, merged, top_k=top_k)


def _inject_soft_filter_candidates(
    hits: list[dict],
    dense_vector,
    sparse_dict,
    intent: QueryIntent,
    fallback_limit: int = 12,
) -> list[dict]:
    """
    If soft intent target is missing from initial hybrid hits, retrieve targeted
    candidates and prepend them before balancing/reranking.
    """
    if intent.filter_strength != "soft":
        return hits

    if intent.scripture_filter:
        target = intent.scripture_filter
        if any(h.get("scripture") == target for h in hits):
            return hits
        target_filter = Filter(must=[
            FieldCondition(key="scripture", match=MatchValue(value=target))
        ])
        target_hits = _hybrid_retrieve(dense_vector, sparse_dict, target_filter, limit=fallback_limit)
        return target_hits + hits

    if intent.tradition_filter:
        target = intent.tradition_filter
        if any(h.get("tradition") == target for h in hits):
            return hits
        target_filter = Filter(must=[
            FieldCondition(key="tradition", match=MatchValue(value=target))
        ])
        target_hits = _hybrid_retrieve(dense_vector, sparse_dict, target_filter, limit=fallback_limit)
        return target_hits + hits

    return hits


def _ensure_soft_target_presence(
    final_hits: list[dict],
    candidate_hits: list[dict],
    intent: QueryIntent,
    top_k: int,
) -> list[dict]:
    """Ensure at least one soft-target item survives final ranking."""
    if intent.filter_strength != "soft":
        return final_hits[:top_k]

    if intent.scripture_filter and not any(h.get("scripture") == intent.scripture_filter for h in final_hits):
        fallback = next((h for h in candidate_hits if h.get("scripture") == intent.scripture_filter), None)
        if fallback:
            merged = [fallback] + [h for h in final_hits if h != fallback]
            return merged[:top_k]

    if intent.tradition_filter and not any(h.get("tradition") == intent.tradition_filter for h in final_hits):
        fallback = next((h for h in candidate_hits if h.get("tradition") == intent.tradition_filter), None)
        if fallback:
            merged = [fallback] + [h for h in final_hits if h != fallback]
            return merged[:top_k]

    return final_hits[:top_k]


def search(query: str, top_k: int = 5) -> list[dict]:
    """Full hybrid search pipeline: analyze → retrieve → balance → rerank.

    Pipeline:
      1. Query analysis — detect scripture/tradition/mode
      2. Hybrid retrieval — dense + sparse RRF, fetch 50 candidates
      3. Source balancing — cap per-scripture (generic corpus imbalance fix)
      4. Reranking — cross-encoder on balanced pool → top_k final results

    The source-balancing step is the generic solution to the corpus dominance
    problem: no single text can dominate results regardless of how large its
    chunk count grows. Today's Mahabharata (26% of corpus), tomorrow's 50%
    corpus — the cap applies uniformly. Configurable via MAX_PER_SOURCE.
    """

    # Step 1: Query analysis
    intent = analyze_query(query)

    # Step 2: Encode query (dense + sparse in one pass for bge-m3)
    dense_vector, sparse_dict = _encode_query(query)

    # Step 3: Retrieve candidates — fetch more so balancing has material to work with
    RETRIEVE_K = 50  # larger pool = better diversity after balancing
    MAX_PER_SOURCE = 2  # max chunks from any single scripture in the final pool

    if intent.mode == "comparison":
        # Parallel per-tradition retrieval — guarantees primary sources from each tradition.
        # Already balanced internally; skip generic source-cap here.
        hits = _comparison_search(query, dense_vector, sparse_dict, top_k)
        if hits:
            return hits
        # Fallback: no clear traditions, fall through to standard retrieval

    # Standard retrieval path
    qfilter = _build_filter(intent)
    hits = _hybrid_retrieve(dense_vector, sparse_dict, qfilter, RETRIEVE_K)
    hits = _inject_soft_filter_candidates(hits, dense_vector, sparse_dict, intent, fallback_limit=12)

    # Soft boost: move matching scripture to top without excluding others
    if intent.scripture_filter and intent.filter_strength == "soft":
        target = intent.scripture_filter
        hits.sort(key=lambda h: (0 if h["scripture"] == target else 1, -h.get("score", 0)))
    elif intent.tradition_filter and intent.filter_strength == "soft":
        target = intent.tradition_filter
        hits.sort(key=lambda h: (0 if h["tradition"] == target else 1, -h.get("score", 0)))

    # Step 4: Source balancing — prevent any one corpus dominating the reranker input
    # If a hard scripture filter is active, skip balancing (user asked for a specific text)
    if not (intent.scripture_filter and intent.filter_strength == "hard"):
        hits = _balance_by_source(hits, max_per_source=MAX_PER_SOURCE, total_cap=20)

    # Step 5: Rerank balanced pool → final top_k
    final_hits = _rerank(query, hits, top_k=top_k)
    return _ensure_soft_target_presence(final_hits, hits, intent, top_k)


def detect_mode(query: str) -> str:
    """Detect query mode using the query analysis module."""
    intent = analyze_query(query)
    return intent.mode
