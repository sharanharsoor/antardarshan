"""
Step 4: Embed Phase 1+ chunks with bge-m3 (hybrid: dense + sparse) and load into Qdrant.

Uses BGEM3FlagModel from FlagEmbedding which generates BOTH dense (1024-dim) and
SPLADE-style sparse vectors in a single forward pass. This enables hybrid search
(semantic + lexical) in Qdrant without separate BM25 infrastructure.

Usage:
    # Production (bge-m3, hybrid dense+sparse):
    python -m ingestion.embed_and_load --mode prod

    # Dev (fast validation with MiniLM, dense only):
    python -m ingestion.embed_and_load --mode dev

Supports incremental indexing: deterministic chunk IDs mean re-running
only upserts — existing vectors are overwritten in place, never duplicated.
"""

import json
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# FP16 halves RAM (~1GB vs ~2GB). Default OFF for CPU safety.
# Set BGE_FP16=true on Apple Silicon / GPU environments.
_use_fp16: bool = os.getenv("BGE_FP16", "false").lower() == "true"
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, SparseVectorParams, SparseVector,
    NamedVector, NamedSparseVector,
)

load_dotenv()

CORPUS_PROCESSED = Path(__file__).parent.parent / "corpus" / "processed"
COLLECTION_NAME = "antardarshan_v1"


def load_all_chunks() -> list[dict]:
    """Load all processed JSON chunks from corpus/processed/."""
    all_chunks = []
    for json_file in sorted(CORPUS_PROCESSED.glob("*.json")):
        chunks = json.loads(json_file.read_text(encoding="utf-8"))
        all_chunks.extend(chunks)
        print(f"  Loaded {len(chunks)} chunks from {json_file.name}")
    print(f"  Total: {len(all_chunks)} chunks")
    return all_chunks


def build_embedding_text(chunk: dict) -> str:
    """Build the text to embed — includes contextual prefix for better retrieval."""
    parts = []
    scripture = chunk.get("scripture", "")
    chapter = chunk.get("chapter", "")
    tradition = chunk.get("tradition", "")
    chapter_name = chunk.get("chapter_name", "")
    speaker = chunk.get("speaker", "")

    context = f"From {scripture}, Chapter {chapter}"
    if chapter_name:
        context += f" ({chapter_name})"
    context += f". Tradition: {tradition}."
    if speaker:
        context += f" Speaker: {speaker}."

    parts.append(context)
    parts.append(chunk["text"])
    return " ".join(parts)


def build_parent_text(chunk: dict, all_chunks: list[dict]) -> str:
    """Build parent context: surrounding +/-2 verses from the same scripture+chapter."""
    scripture = chunk["scripture"]
    chapter = chunk["chapter"]
    verse = chunk["verse"]

    siblings = [
        c for c in all_chunks
        if c["scripture"] == scripture and c["chapter"] == chapter
        and abs(c["verse"] - verse) <= 2 and c["verse"] != verse
    ]
    siblings.sort(key=lambda c: c["verse"])

    if not siblings:
        return ""
    return " | ".join(f"[{s['verse']}] {s['text'][:200]}" for s in siblings)


def embed_prod(texts: list[str]):
    """Encode with bge-m3 — returns both dense and sparse vectors in one pass."""
    from FlagEmbedding import BGEM3FlagModel

    print("  Loading BAAI/bge-m3 (production, 1024 dims + sparse)...")
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=_use_fp16)

    print(f"  Encoding {len(texts)} texts (dense + sparse in one pass)...")
    output = model.encode(texts, return_dense=True, return_sparse=True, batch_size=16)

    dense_vectors = output["dense_vecs"]  # numpy array [n, 1024]
    sparse_dicts = output["lexical_weights"]  # list of dicts {token_id: weight}

    print(f"  Generated {len(dense_vectors)} dense (1024d) + {len(sparse_dicts)} sparse vectors")
    return dense_vectors, sparse_dicts, 1024


def embed_dev(texts: list[str]):
    """Encode with MiniLM for fast dev iteration (dense only, no sparse)."""
    from sentence_transformers import SentenceTransformer

    print("  Loading all-MiniLM-L6-v2 (dev mode, 384 dims, dense only)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    print(f"  Generated {len(embeddings)} dense vectors (384d)")
    return embeddings, None, 384


def create_collection(client: QdrantClient, dim: int, has_sparse: bool):
    """Create Qdrant collection with dense + optional sparse vector support."""
    collections = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in collections:
        existing_config = client.get_collection(COLLECTION_NAME).config.params.vectors
        # Check if dims match (handles both named and unnamed vector configs)
        if hasattr(existing_config, "size"):
            existing_dim = existing_config.size
        elif isinstance(existing_config, dict) and "dense" in existing_config:
            existing_dim = existing_config["dense"].size
        else:
            existing_dim = 0

        if existing_dim == dim:
            print(f"  Collection '{COLLECTION_NAME}' exists with correct dims ({dim}). Reusing.")
            return
        else:
            print(f"  Dimension mismatch ({existing_dim} → {dim}). Recreating...")
            client.delete_collection(COLLECTION_NAME)

    vectors_config = {"dense": VectorParams(size=dim, distance=Distance.COSINE)}
    sparse_config = {"bm25": SparseVectorParams()} if has_sparse else None

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=vectors_config,
        sparse_vectors_config=sparse_config,
    )
    mode_str = "dense + sparse (hybrid)" if has_sparse else "dense only"
    print(f"  Created collection '{COLLECTION_NAME}' ({mode_str}, dim={dim})")


def upsert_chunks(client: QdrantClient, chunks: list[dict], dense_vectors, sparse_dicts, has_sparse: bool):
    """Upsert all chunks with vectors into Qdrant. Deterministic IDs for idempotency."""
    points = []
    for i, chunk in enumerate(chunks):
        # Fallback: derive deterministic ID from content if chunk_id missing
        if "chunk_id" in chunk and chunk["chunk_id"]:
            point_id = int(chunk["chunk_id"], 16) % (2**63)
        else:
            import hashlib
            key = f"{chunk.get('scripture','')}-{chunk.get('chapter','')}-{chunk.get('verse','')}-{chunk.get('translator','')}"
            point_id = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**63)

        # Build vectors
        vector_data = {"dense": dense_vectors[i].tolist()}

        # Build sparse vector if available
        sparse_data = None
        if has_sparse and sparse_dicts and sparse_dicts[i]:
            indices = list(sparse_dicts[i].keys())
            values = list(sparse_dicts[i].values())
            if indices:
                sparse_data = {"bm25": SparseVector(indices=indices, values=values)}

        point = PointStruct(
            id=point_id,
            vector=vector_data,
            payload={
                "text": chunk["text"],
                "scripture": chunk["scripture"],
                "tradition": chunk["tradition"],
                "chapter": chunk["chapter"],
                "verse": chunk["verse"],
                "translator": chunk["translator"],
                "year": chunk["year"],
                "language": chunk["language"],
                "license_tier": chunk["license_tier"],
                "source_url": chunk["source_url"],
                "themes": chunk.get("themes", []),
                "chunk_type": chunk.get("chunk_type", "verse"),
                "verse_type": chunk.get("verse_type", "verse"),
                "speaker": chunk.get("speaker"),
                "chapter_name": chunk.get("chapter_name"),
                "chunk_id": chunk.get("chunk_id", ""),
                "parent_text": chunk.get("_parent_text", ""),
            },
        )

        if sparse_data:
            point.vector.update(sparse_data)

        points.append(point)

    # Upsert in batches
    batch_size = 64
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)
        print(f"  Upserted batch {i // batch_size + 1}/{(len(points) + batch_size - 1) // batch_size}")

    print(f"  Total points in collection: {client.count(COLLECTION_NAME).count}")


def main():
    parser = argparse.ArgumentParser(description="Embed and load chunks into Qdrant (hybrid)")
    parser.add_argument("--mode", choices=["dev", "prod"], default="prod",
                        help="dev=fast MiniLM dense-only, prod=bge-m3 dense+sparse hybrid")
    parser.add_argument("--chunk-size", type=int, default=2000,
                        help="Encode + upsert N chunks at a time to limit peak RAM usage (default: 2000)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"AntarDarshan — Hybrid Embed + Load ({args.mode} mode)")
    print(f"Chunk size: {args.chunk_size} (encode + upsert per batch)")
    print(f"{'='*60}\n")

    # 1. Load all chunks (just metadata, no vectors yet)
    print("[1/4] Loading processed chunks...")
    all_chunks = load_all_chunks()

    # 2. Build parent context (needs full corpus in memory, but it's just text — small)
    print("\n[2/4] Building parent context (±2 verses)...")
    for chunk in all_chunks:
        chunk["_parent_text"] = build_parent_text(chunk, all_chunks)
    with_parent = sum(1 for c in all_chunks if c["_parent_text"])
    print(f"  {with_parent}/{len(all_chunks)} chunks have parent context.")

    # 3+4. Connect to Qdrant, create collection on first batch, then encode+upsert in windows
    print(f"\n[3/4] Connecting to Qdrant...")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)
    has_sparse = (args.mode == "prod")
    collection_created = False

    # Load the model ONCE outside the loop
    if args.mode == "prod":
        from FlagEmbedding import BGEM3FlagModel
        print("  Loading BAAI/bge-m3 (production)...")
        model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=_use_fp16)
    else:
        from sentence_transformers import SentenceTransformer
        print("  Loading all-MiniLM-L6-v2 (dev)...")
        model = SentenceTransformer("all-MiniLM-L6-v2")

    print(f"\n[4/4] Encoding + uploading in windows of {args.chunk_size}...")
    total = len(all_chunks)
    n_windows = (total + args.chunk_size - 1) // args.chunk_size

    for w_idx in range(n_windows):
        start = w_idx * args.chunk_size
        end = min(start + args.chunk_size, total)
        window = all_chunks[start:end]

        print(f"\n  Window {w_idx+1}/{n_windows}: chunks {start+1}–{end} ({len(window)} chunks)")

        texts = [build_embedding_text(c) for c in window]

        if args.mode == "prod":
            output = model.encode(texts, return_dense=True, return_sparse=True, batch_size=16)
            dense_vectors = output["dense_vecs"]
            sparse_dicts = output["lexical_weights"]
            dim = 1024
        else:
            dense_vectors = model.encode(texts, show_progress_bar=False, batch_size=32)
            sparse_dicts = None
            dim = 384

        # Create collection on first window
        if not collection_created:
            create_collection(client, dim, has_sparse)
            collection_created = True

        upsert_chunks(client, window, dense_vectors, sparse_dicts, has_sparse)
        print(f"  ✓ Window {w_idx+1} done. Qdrant total: {client.count(COLLECTION_NAME).count:,}")

    # 5. Final verification
    final_count = client.count(COLLECTION_NAME).count
    print(f"\n{'='*60}")
    print(f"DONE.")
    print(f"  Total chunks embedded: {total:,}")
    print(f"  Qdrant points:         {final_count:,}")
    print(f"  Mode: {args.mode} ({'dense + sparse hybrid' if has_sparse else 'dense only'})")
    if final_count != total:
        print(f"  ⚠ Mismatch! Run 'python -m ingestion.admin verify' to diagnose.")
    else:
        print(f"  ✅ All good. Restart backend and test retrieval quality.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
