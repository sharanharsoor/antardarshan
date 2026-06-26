"""
Index Khuddaka Nikaya sub-collections already present in sc-data.

Texts: Sutta Nipata, Udana, Itivuttaka, Theragatha, Therigatha
All are CC0 (Bhikkhu Sujato translations, SuttaCentral).
Run with: python -m ingestion.index_kn_subcollections
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

ROOT = Path(__file__).parent.parent
SC_DATA = ROOT / "corpus" / "raw" / "sc-data"
CORPUS_PROCESSED = ROOT / "corpus" / "processed"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "antardarshan_v1"

KN_TARGETS = [
    ("snp", "sutta_nipata.json"),   # Sutta Nipata — among the oldest Buddhist texts
    ("ud", "udana.json"),           # Udana — 80 inspired utterances of the Buddha
    ("iti", "itivuttaka.json"),     # Itivuttaka — So It Was Said
    ("thag", "theragatha.json"),    # Theragatha — Verses of the Elder Monks
    ("thig", "therigatha.json"),    # Therigatha — Verses of the Elder Nuns
]


def main():
    from ingestion.parsers.pali_canon_sujato import parse_nikaya, NIKAYA_META
    from ingestion.embed_and_load import embed_prod, build_embedding_text, build_parent_text, upsert_chunks
    from ingestion.process_all import _save

    client = QdrantClient(url=QDRANT_URL)
    base = SC_DATA / "translation" / "en" / "sujato" / "sutta" / "kn"

    for code, outfile_name in KN_TARGETS:
        nikaya_dir = base / code
        if not nikaya_dir.exists():
            print(f"  ✗ {code} not found at {nikaya_dir}")
            continue

        name = NIKAYA_META.get(code, (code.upper(),))[0]
        print(f"\n{'='*60}")
        print(f"Processing: {name} ({code.upper()})")
        print(f"{'='*60}")

        chunks = parse_nikaya(nikaya_dir, code)
        if not chunks:
            print(f"  ✗ No chunks parsed for {code}")
            continue

        print(f"  Parsed {len(chunks)} chunks")

        # Reuse the main processing save path so hard-cap + dedupe behavior stays identical.
        _save(chunks, outfile_name)
        out_file = CORPUS_PROCESSED / outfile_name
        chunk_dicts = json.loads(out_file.read_text(encoding="utf-8"))
        print(f"  Saved → {out_file.name}")

        # Build parent context
        print(f"  Building parent context...")
        for chunk in chunk_dicts:
            chunk["_parent_text"] = build_parent_text(chunk, chunk_dicts)

        # Embed
        texts = [build_embedding_text(c) for c in chunk_dicts]
        print(f"  Embedding {len(texts)} chunks with bge-m3...")
        dense_vectors, sparse_dicts, dim = embed_prod(texts)

        # Upsert
        print(f"  Uploading to Qdrant...")
        upsert_chunks(client, chunk_dicts, dense_vectors, sparse_dicts, has_sparse=True)
        print(f"  ✅ {name}: {len(chunk_dicts)} chunks indexed")

    print(f"\n{'='*60}")
    print(f"Done. Run: python -m ingestion.admin status")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
