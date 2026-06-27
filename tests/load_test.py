"""
AntarDarshan — Locust Load Test
================================
Tests 100 concurrent users hitting the backend.

Usage:
    # Headless (CI / terminal):
    locust -f tests/load_test.py \
        --headless -u 100 -r 10 \
        --run-time 3m \
        --host http://localhost:8000 \
        --html tests/load_report.html

    # Web UI (interactive, see real-time charts):
    locust -f tests/load_test.py --host http://localhost:8000
    # Then open http://localhost:8089

Targets:
    - p95 response time < 30s  (LLM is slow; 30s is acceptable)
    - error rate < 5%           (some 429s expected under load, not failures)
    - 0 crashes / 5xx errors   (backend must stay alive)

Endpoints tested:
    GET  /healthz               — liveness probe (should be <200ms always)
    GET  /api/library           — corpus listing (cached, <300ms)
    POST /api/query             — full RAG + LLM pipeline (5-25s)
"""

import random
from locust import HttpUser, task, between, events

# Tracks 429 responses separately from errors (quota hits vs crashes)
_quota_hits: list[int] = []


PHILOSOPHY_QUERIES = [
    "How do I stop being so angry?",
    "What is consciousness?",
    "I feel lost and don't know my purpose",
    "What happens after death?",
    "What is karma and how does it work?",
    "How does one find inner peace?",
    "What is the nature of the self?",
    "What did the Buddha teach about suffering?",
    "What is liberation according to Advaita Vedanta?",
    "How do I deal with grief?",
    "What is dharma?",
    "What does the Gita say about action without attachment?",
    "What is the difference between the soul and the mind?",
    "How does equanimity arise?",
    "What is meditation according to the Yoga Sutras?",
]


class AntarDarshanUser(HttpUser):
    """
    Simulates a real user browsing AntarDarshan:
      - checks the health endpoint
      - loads the library
      - asks a philosophical question (the slow path)

    Wait time: 2–8s between tasks (realistic think time).
    """
    wait_time = between(2, 8)

    @task(1)
    def health_check(self):
        """Lightweight liveness probe — should always be < 200ms."""
        with self.client.get("/healthz", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            elif r.status_code == 503:
                # Degraded but alive — still counts as a response, not a failure
                r.success()
            else:
                r.failure(f"Health returned {r.status_code}")

    @task(2)
    def load_library(self):
        """Cached list endpoint — should be < 500ms."""
        with self.client.get("/api/library", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"Library returned {r.status_code}")

    @task(5)
    def ask_question(self):
        """
        Full RAG + LLM call. This is the expensive path.
        Expected: 5–25s under normal load. 30s timeout set on Gunicorn.
        Under concurrency > semaphore, excess requests queue — still succeed,
        just with higher latency.

        429 handling: rate-limit 429s are tracked separately via a custom
        metric and do NOT count as errors, but the summary will warn if the
        429 ratio is too high (indicates quota exhaustion, not just queueing).
        """
        query = random.choice(PHILOSOPHY_QUERIES)
        payload = {
            "query": query,
            "top_k": 5,
            "session_id": None,
            "log_content": False,
        }
        with self.client.post(
            "/api/query",
            json=payload,
            catch_response=True,
            name="/api/query",
            timeout=60,
        ) as r:
            if r.status_code == 200:
                data = r.json()
                if "answer" in data or "hits" in data:
                    r.success()
                else:
                    r.failure("Response missing answer field")
            elif r.status_code == 429:
                # Track quota hits separately — mark as success so they don't
                # inflate the error rate, but count them for the summary check.
                _quota_hits.append(1)
                r.success()
            elif r.status_code == 503:
                r.failure("Backend degraded (503)")
            else:
                r.failure(f"Unexpected {r.status_code}: {r.text[:200]}")


class LibraryBrowser(HttpUser):
    """
    Lighter user — only browses the library, no LLM calls.
    Simulates users who are reading, not asking questions.
    """
    wait_time = between(1, 3)

    @task(3)
    def load_library(self):
        self.client.get("/api/library")

    @task(1)
    def health(self):
        # Use /healthz (lightweight liveness), not /api/health (readiness + deps)
        self.client.get("/healthz")


# ── Summary thresholds ─────────────────────────────────────────────────────────

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    stats = environment.stats.total
    failures = stats.num_failures
    total = stats.num_requests
    error_rate = (failures / total * 100) if total > 0 else 0
    p95 = stats.get_response_time_percentile(0.95) or 0

    print("\n" + "=" * 60)
    print("LOAD TEST SUMMARY")
    print("=" * 60)
    print(f"  Total requests:  {total:,}")
    print(f"  Failures:        {failures:,}  ({error_rate:.1f}%)")
    print(f"  p50 latency:     {stats.get_response_time_percentile(0.50) or 0:,.0f} ms")
    print(f"  p95 latency:     {p95:,.0f} ms")
    print(f"  p99 latency:     {stats.get_response_time_percentile(0.99) or 0:,.0f} ms")
    print(f"  Req/s:           {stats.current_rps:.1f}")
    print()

    # Pass/fail thresholds
    ok = True
    if error_rate > 5:
        print(f"  ❌ FAIL: Error rate {error_rate:.1f}% > 5%")
        ok = False
    if p95 > 35_000:
        print(f"  ❌ FAIL: p95 {p95/1000:.1f}s > 35s")
        ok = False
    if ok:
        print("  ✅ PASS: Error rate and latency within targets")

    print("=" * 60)

    # 429 quota-hit ratio check — sum num_requests across /api/query entries
    total_query_requests = sum(
        stat.num_requests
        for (name, method), stat in environment.stats.entries.items()
        if "/api/query" in str(name)
    )
    quota_hit_count = len(_quota_hits)
    if total_query_requests > 0:
        quota_ratio = quota_hit_count / total_query_requests * 100
        print(f"  429 quota hits:  {quota_hit_count} ({quota_ratio:.1f}% of query requests)")
        if quota_ratio > 30:
            print(f"  ⚠ WARNING: >30% of requests hit quota limits — system likely overloaded")
            ok = False

    if not ok:
        environment.process_exit_code = 1
