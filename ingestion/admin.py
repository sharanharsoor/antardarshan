"""
AntarDarshan — Incremental Indexing Admin CLI

Commands:
    python -m ingestion.admin status
        Show which files are indexed, total chunks, Qdrant point count.

    python -m ingestion.admin add <raw_file.txt> --scripture "Name" --tradition hindu_vedanta ...
        Parse + embed a single new raw file and upsert into Qdrant.
        Only the new file is processed — existing vectors are untouched.

    python -m ingestion.admin remove --scripture "Scripture Name"
        Delete all Qdrant points for that scripture by payload filter.
        Also removes the processed JSON from corpus/processed/.

    python -m ingestion.admin reindex --scripture "Scripture Name"
        Remove + re-add a single scripture (use after fixing its parser/source).

    python -m ingestion.admin verify
        Cross-check processed JSON chunk count vs Qdrant point count.
        Reports any mismatches.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

load_dotenv()

ROOT = Path(__file__).parent.parent
CORPUS_PROCESSED = ROOT / "corpus" / "processed"
CORPUS_RAW = ROOT / "corpus" / "raw"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "antardarshan_v1"


def _get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def _embed_chunks(chunks: list[dict]) -> tuple:
    """Embed chunks with bge-m3. Returns (dense_vectors, sparse_dicts)."""
    from ingestion.embed_and_load import embed_prod, build_embedding_text, build_parent_text

    print(f"  Building parent context for {len(chunks)} chunks...")
    # For parent context, only use sibling chunks from the same file
    for chunk in chunks:
        chunk["_parent_text"] = build_parent_text(chunk, chunks)

    texts = [build_embedding_text(c) for c in chunks]
    print(f"  Embedding {len(texts)} chunks with bge-m3...")
    dense_vectors, sparse_dicts, dim = embed_prod(texts)
    return dense_vectors, sparse_dicts, dim


def _upsert_to_qdrant(client: QdrantClient, chunks: list[dict], dense_vectors, sparse_dicts):
    """Upsert chunks into Qdrant."""
    from ingestion.embed_and_load import upsert_chunks
    upsert_chunks(client, chunks, dense_vectors, sparse_dicts, has_sparse=True)


def cmd_status(args):
    """Show index state: processed files vs Qdrant."""
    client = _get_client()

    try:
        total_points = client.count(COLLECTION_NAME).count
    except Exception:
        total_points = 0
        print("  ⚠ Qdrant collection not found or not running.")

    print(f"\n{'='*60}")
    print(f"AntarDarshan — Index Status")
    print(f"{'='*60}")

    json_files = sorted(CORPUS_PROCESSED.glob("*.json"))
    scripture_counts: dict[str, int] = {}

    for jf in json_files:
        chunks = json.loads(jf.read_text())
        for chunk in chunks:
            scripture = chunk.get("scripture", "")
            if scripture:
                scripture_counts[scripture] = scripture_counts.get(scripture, 0) + 1

    total_chunks = sum(scripture_counts.values())

    print(f"\nProcessed JSON files: {len(json_files)}")
    print(f"Total chunks in JSON: {total_chunks}")
    print(f"Qdrant points:        {total_points}")

    delta = total_points - total_chunks
    if delta == 0:
        print(f"Status: ✅ In sync")
    elif delta > 0:
        print(f"Status: ⚠  Qdrant has {delta} extra stale points (run full re-embed)")
    else:
        print(f"Status: ⚠  Qdrant missing {abs(delta)} points (run re-embed)")

    print(f"\n{'Scripture':<45} {'Chunks':>8}")
    print("-" * 55)
    for scripture, count in sorted(scripture_counts.items()):
        print(f"  {scripture:<43} {count:>8,}")
    print(f"\n  {'TOTAL':<43} {total_chunks:>8,}")


def cmd_add(args):
    """Parse + embed a single new file and upsert into Qdrant."""
    from ingestion.parsers.sbe_prose import parse_sbe_text

    raw_path = Path(args.file)
    if not raw_path.exists():
        # Try relative to corpus/raw
        raw_path = CORPUS_RAW / args.file
    if not raw_path.exists():
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)

    scripture = args.scripture
    tradition = args.tradition
    translator = args.translator
    year = int(args.year)
    source_url = args.source_url or ""
    out_name = args.output or f"{scripture.lower().replace(' ', '_').replace('(','').replace(')','')}.json"
    out_path = CORPUS_PROCESSED / out_name

    print(f"\nAdding: {scripture}")
    print(f"  Source: {raw_path}")
    print(f"  Output: {out_path}")

    # Parse
    chunks = parse_sbe_text(
        raw_path, scripture, tradition, translator, year, source_url
    )
    if not chunks:
        print(f"ERROR: Parser returned 0 chunks. Check the file format.")
        sys.exit(1)

    print(f"  Parsed {len(chunks)} chunks")

    # Save JSON
    out_path.write_text(json.dumps([c.to_dict() for c in chunks], ensure_ascii=False, indent=2))
    print(f"  Saved to {out_path.name}")

    # Embed + upsert
    chunk_dicts = [c.to_dict() for c in chunks]
    dense, sparse, _ = _embed_chunks(chunk_dicts)

    client = _get_client()
    _upsert_to_qdrant(client, chunk_dicts, dense, sparse)
    print(f"\n✅ Done. {scripture}: {len(chunks)} chunks added to Qdrant.")


def cmd_remove(args):
    """Remove a scripture from Qdrant and processed JSON."""
    scripture = args.scripture
    client = _get_client()

    # Delete from Qdrant by payload filter
    print(f"\nRemoving '{scripture}' from Qdrant...")
    result = client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="scripture", match=MatchValue(value=scripture))]
        ),
    )
    print(f"  Qdrant delete result: {result}")

    # Remove scripture chunks from processed JSON.
    # For multi-scripture files, rewrite only the remaining chunks.
    removed_files = []
    rewritten_files = []
    removed_chunk_count = 0
    for jf in CORPUS_PROCESSED.glob("*.json"):
        chunks = json.loads(jf.read_text())
        if not chunks:
            continue

        kept = [c for c in chunks if c.get("scripture") != scripture]
        removed_here = len(chunks) - len(kept)
        if removed_here == 0:
            continue

        removed_chunk_count += removed_here
        if kept:
            jf.write_text(json.dumps(kept, ensure_ascii=False, indent=2))
            rewritten_files.append((jf.name, removed_here, len(kept)))
        else:
            jf.unlink()
            removed_files.append(jf.name)

    if removed_files:
        print(f"  Deleted JSON: {', '.join(removed_files)}")
    if rewritten_files:
        for fname, removed_here, kept_count in rewritten_files:
            print(f"  Updated JSON: {fname} (removed {removed_here}, kept {kept_count})")
    if not removed_files and not rewritten_files:
        print(f"  No processed JSON found for '{scripture}'")
    else:
        print(f"  Removed {removed_chunk_count} chunk(s) from processed corpus")

    print(f"\n✅ Done. '{scripture}' removed.")


def cmd_verify(args):
    """Cross-check JSON chunks vs Qdrant points per scripture.

    Handles two real-world cases correctly:
    - Multi-scripture JSON files (e.g. vivekananda_collected.json stores Raja/Karma/Jnana-Yoga)
    - Same scripture name across multiple JSON files (e.g. two Brahma Sutras Shankara editions)

    Both cases previously caused false mismatch reports. Now we aggregate by scripture
    name across all JSON files before comparing to Qdrant.
    """
    client = _get_client()

    print(f"\n{'='*60}")
    print(f"Index Verification")
    print(f"{'='*60}\n")

    # Aggregate JSON counts by scripture name across ALL files
    json_counts: dict[str, int] = {}
    for jf in sorted(CORPUS_PROCESSED.glob("*.json")):
        chunks = json.loads(jf.read_text())
        for chunk in chunks:
            scripture = chunk.get("scripture", "")
            if scripture:
                json_counts[scripture] = json_counts.get(scripture, 0) + 1

    all_good = True
    for scripture, json_count in sorted(json_counts.items()):
        qdrant_count = client.count(
            COLLECTION_NAME,
            count_filter=Filter(
                must=[FieldCondition(key="scripture", match=MatchValue(value=scripture))]
            ),
        ).count

        if json_count == qdrant_count:
            print(f"  ✅ {scripture}: {json_count} chunks")
        else:
            print(f"  ❌ {scripture}: JSON={json_count}, Qdrant={qdrant_count} (delta={qdrant_count - json_count:+d})")
            all_good = False

    total_json = sum(json_counts.values())
    total_qdrant = client.count(COLLECTION_NAME).count
    print(f"\n  Total JSON: {total_json:,} | Total Qdrant: {total_qdrant:,}")
    print(f"\n{'All in sync ✅' if all_good else 'Mismatches found — run reindex for affected scriptures ⚠'}")


def cmd_reindex(args):
    """Remove + re-add a single scripture."""
    print(f"\nReindexing: {args.scripture}")
    cmd_remove(args)
    print("\nNote: reindex removed the processed JSON.")
    print("Run 'python -m ingestion.admin add <raw_file> --scripture ...' to re-add.")


def cmd_book_feedback(args):
    """Show book feedback ratings aggregated per scripture (thumbs up/down counts)."""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        return

    try:
        from supabase import create_client
        sb = create_client(url, key)
        rows = sb.table("feedback_books").select("scripture,rating").execute()
    except Exception as e:
        print(f"ERROR: Could not fetch book feedback: {e}")
        return

    if not rows.data:
        print("No book feedback recorded yet.")
        return

    from collections import defaultdict
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"up": 0, "down": 0})
    for row in rows.data:
        key_name = row["scripture"]
        if row["rating"] == 1:
            counts[key_name]["up"] += 1
        else:
            counts[key_name]["down"] += 1

    print(f"\n{'='*60}")
    print(f"Book Feedback — {len(counts)} texts rated")
    print(f"{'='*60}\n")
    print(f"  {'Scripture':<45} {'👍':>4} {'👎':>4}")
    print("  " + "-" * 55)

    # Sort by total feedback volume (most-rated first)
    for scripture, c in sorted(counts.items(), key=lambda x: -(x[1]["up"] + x[1]["down"])):
        print(f"  {scripture:<45} {c['up']:>4} {c['down']:>4}")

    total_up = sum(c["up"] for c in counts.values())
    total_down = sum(c["down"] for c in counts.values())
    print(f"\n  Total: {total_up + total_down} ratings — {total_up} up, {total_down} down\n")


def cmd_issues(args):
    """Show open issue reports grouped by scripture (OCR errors, wrong content, etc.)."""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        return

    status_filter = getattr(args, "status", "open")

    try:
        from supabase import create_client
        sb = create_client(url, key)
        query = sb.table("issue_reports").select("scripture,chapter,verse,issue_type,comment,status,created_at")
        if status_filter != "all":
            query = query.eq("status", status_filter)
        rows = query.order("created_at", desc=True).execute()
    except Exception as e:
        print(f"ERROR: Could not fetch issues: {e}")
        return

    if not rows.data:
        print(f"No {status_filter} issue reports found.")
        return

    from collections import defaultdict
    by_scripture: dict[str, list] = defaultdict(list)
    for row in rows.data:
        by_scripture[row["scripture"]].append(row)

    print(f"\n{'='*70}")
    print(f"Issue Reports ({status_filter}) — {len(rows.data)} total")
    print(f"{'='*70}\n")

    for scripture, issues in sorted(by_scripture.items()):
        print(f"  {scripture} ({len(issues)} issues)")
        for r in issues:
            loc = f"Ch {r['chapter']}" + (f" V{r['verse']}" if r.get("verse") else "")
            comment = f" — {r['comment'][:60]}" if r.get("comment") else ""
            print(f"    [{r['status']:12s}] {loc:10s} {r['issue_type']:20s}{comment}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="AntarDarshan incremental indexing admin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show index status")

    # add
    p_add = sub.add_parser("add", help="Add a new scripture file")
    p_add.add_argument("file", help="Path to raw text file")
    p_add.add_argument("--scripture", required=True, help="Scripture display name")
    p_add.add_argument("--tradition", required=True,
                       choices=["hindu_vedanta","hindu_yoga","buddhist","jain","sikh","sant_bhakti","other"])
    p_add.add_argument("--translator", required=True)
    p_add.add_argument("--year", required=True)
    p_add.add_argument("--source-url", default="")
    p_add.add_argument("--output", help="Output JSON filename (auto-derived if not set)")

    # remove
    p_rm = sub.add_parser("remove", help="Remove a scripture from index")
    p_rm.add_argument("--scripture", required=True, help="Exact scripture name to remove")

    # reindex
    p_ri = sub.add_parser("reindex", help="Remove a scripture (re-add manually)")
    p_ri.add_argument("--scripture", required=True)

    # verify
    sub.add_parser("verify", help="Cross-check JSON vs Qdrant counts")

    # book-feedback
    sub.add_parser("book-feedback", help="Show thumbs up/down counts per scripture")

    # issues
    p_issues = sub.add_parser("issues", help="Show user-reported text issues")
    p_issues.add_argument("--status", default="open",
                          choices=["open", "acknowledged", "fixed", "wontfix", "all"],
                          help="Filter by status (default: open)")

    args = parser.parse_args()
    {
        "status": cmd_status,
        "add": cmd_add,
        "remove": cmd_remove,
        "reindex": cmd_reindex,
        "verify": cmd_verify,
        "book-feedback": cmd_book_feedback,
        "issues": cmd_issues,
    }[args.command](args)


if __name__ == "__main__":
    main()
