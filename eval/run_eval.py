"""
Eval scorer for Phase 1 retrieval quality.

Runs all benchmark queries from queries_phase1.json against the live index
and reports pass/fail based on whether expected scriptures appear in top-5 results.

Usage:
    python -m eval.run_eval

Requires: Qdrant running locally with indexed data.
"""

import json
import sys
import time
from pathlib import Path

EVAL_FILE = Path(__file__).parent / "queries_phase1.json"


def run_eval():
    from backend.rag_query import search

    queries = json.loads(EVAL_FILE.read_text())
    results = []
    passed = 0
    failed = 0

    print(f"\nRunning {len(queries)} benchmark queries...\n")
    print(f"{'ID':>3} {'Mode':<12} {'Pass?':<6} {'Query':<50} {'Detail'}")
    print("─" * 120)

    for q in queries:
        query = q["query"]
        expected_scriptures = set(q.get("expected_scriptures", []))
        expected_traditions = set(q.get("expected_traditions", []))
        expected_chapters = set(q.get("expected_chapters", []))
        expected_verses = set(q.get("expected_verses", []))

        try:
            started = time.perf_counter()
            hits = search(query, top_k=5)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
        except Exception as e:
            results.append({"id": q["id"], "pass": False, "error": str(e), "latency_ms": None})
            failed += 1
            print(f"{q['id']:>3} {q.get('mode', '?'):<12} {'FAIL':<6} {query[:50]:<50} ERROR: {e}")
            continue

        retrieved_scriptures = set(h["scripture"] for h in hits)
        retrieved_traditions = set(h["tradition"] for h in hits)
        retrieved_chapters = {h.get("chapter") for h in hits if h.get("chapter") is not None}
        retrieved_verses = {h.get("verse") for h in hits if h.get("verse") is not None}

        # Pass condition: each specified expectation dimension must be satisfied.
        scripture_match = bool(expected_scriptures & retrieved_scriptures) if expected_scriptures else True
        tradition_match = bool(expected_traditions & retrieved_traditions) if expected_traditions else True
        chapter_match = bool(expected_chapters & retrieved_chapters) if expected_chapters else True
        verse_match = bool(expected_verses & retrieved_verses) if expected_verses else True
        is_pass = scripture_match and tradition_match and chapter_match and verse_match

        if is_pass:
            passed += 1
            status = "PASS"
        else:
            failed += 1
            status = "FAIL"
        detail = ""
        if not is_pass:
            parts = []
            if expected_scriptures and not scripture_match:
                parts.append(f"scripture expected={expected_scriptures}, got={retrieved_scriptures}")
            if expected_traditions and not tradition_match:
                parts.append(f"tradition expected={expected_traditions}, got={retrieved_traditions}")
            if expected_chapters and not chapter_match:
                parts.append(f"chapter expected={expected_chapters}, got={retrieved_chapters}")
            if expected_verses and not verse_match:
                parts.append(f"verse expected={expected_verses}, got={retrieved_verses}")
            detail = "; ".join(parts)
        print(f"{q['id']:>3} {q.get('mode', '?'):<12} {status:<6} {query[:50]:<50} {detail}")

        results.append({
            "id": q["id"],
            "pass": is_pass,
            "retrieved_scriptures": list(retrieved_scriptures),
            "retrieved_traditions": list(retrieved_traditions),
            "retrieved_chapters": sorted(x for x in retrieved_chapters if isinstance(x, int)),
            "retrieved_verses": sorted(x for x in retrieved_verses if isinstance(x, int)),
            "expected_scriptures": list(expected_scriptures),
            "expected_traditions": list(expected_traditions),
            "expected_chapters": list(expected_chapters),
            "expected_verses": list(expected_verses),
            "latency_ms": elapsed_ms,
        })

    # Summary
    total = passed + failed
    rate = (passed / total * 100) if total > 0 else 0
    print(f"\n{'='*120}")
    print(f"RESULTS: {passed}/{total} passed ({rate:.0f}%)")
    print(f"  Citation mode: {sum(1 for q, r in zip(queries, results) if q.get('mode') == 'citation' and r['pass'])}/{sum(1 for q in queries if q.get('mode') == 'citation')}")
    print(f"  Well-being mode: {sum(1 for q, r in zip(queries, results) if q.get('mode') == 'well_being' and r['pass'])}/{sum(1 for q in queries if q.get('mode') == 'well_being')}")

    # Save report
    report_path = Path(__file__).parent / "eval_report.json"
    latencies = [r["latency_ms"] for r in results if isinstance(r.get("latency_ms"), int)]
    report = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "rate": rate,
        "p50_latency_ms": sorted(latencies)[len(latencies) // 2] if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
        "results": results,
    }
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n  Report saved: {report_path}")

    return rate >= 60  # Pass threshold: 60% of queries must retrieve expected scripture


if __name__ == "__main__":
    success = run_eval()
    sys.exit(0 if success else 1)
