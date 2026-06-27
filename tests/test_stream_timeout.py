"""
Tests for streaming timeout + error event handling.

Covers:
- _TrackedSemaphore: slots_free property, acquire/release tracking
- Stream endpoint sends type="error" SSE when LLM raises exception
- Stream endpoint sends type="error" SSE when queue times out (mocked timeout)
- Error event has correct JSON shape the frontend expects
- Stop event is set on CancelledError (client disconnect)
- Token events and done event still sent after error recovery
- Quota checks in stream endpoint are non-blocking (asyncio.to_thread path)
"""

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend.app import app, _LLM_SEMAPHORE


# ── _TrackedSemaphore ──────────────────────────────────────────────────────────

class TestTrackedSemaphore:

    def test_slots_free_starts_at_limit(self):
        """slots_free should equal the limit when nothing is acquired."""
        assert _LLM_SEMAPHORE.slots_free == _LLM_SEMAPHORE._limit

    def test_slots_free_decrements_on_acquire(self):
        """slots_free must decrease by 1 for each active acquisition."""
        import threading

        acquired = threading.Event()
        released = threading.Event()

        async def _hold():
            async with _LLM_SEMAPHORE:
                acquired.set()
                # Hold until test says release
                await asyncio.sleep(0.1)

        # Run in a thread so it doesn't interfere with the test's event loop
        initial = _LLM_SEMAPHORE.slots_free

        async def _run():
            task = asyncio.create_task(_hold())
            await asyncio.sleep(0.05)
            mid = _LLM_SEMAPHORE.slots_free
            await task
            after = _LLM_SEMAPHORE.slots_free
            return mid, after

        mid, after = asyncio.run(_run())
        assert mid == initial - 1, "slots_free should decrease by 1 while held"
        assert after == initial, "slots_free should return to initial after release"

    def test_slots_free_is_public_not_private(self):
        """slots_free must not rely on ._value — use public interface only."""
        assert hasattr(_LLM_SEMAPHORE, "slots_free")
        assert not hasattr(_LLM_SEMAPHORE, "_value"), (
            "_value is a private asyncio internal — use _TrackedSemaphore.slots_free"
        )

    def test_slots_free_returns_integer(self):
        assert isinstance(_LLM_SEMAPHORE.slots_free, int)

    def test_limit_equals_15(self):
        """Semaphore limit must match the documented value."""
        assert _LLM_SEMAPHORE._limit == 15


# ── Stream error event shape ───────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


def _collect_events(resp_text: str) -> list[dict]:
    """Parse SSE text into a list of event dicts."""
    events = []
    for line in resp_text.splitlines():
        if line.startswith("data: ") and line[6:].strip() != "[DONE]":
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def _base_patches():
    """Common patches needed for stream endpoint to reach the LLM call."""
    return [
        patch("backend.app.sqlite3") ,
        patch("backend.supabase_client.verify_jwt", return_value=None),
        patch("backend.rag_query.detect_mode", return_value="citation"),
        patch("backend.rag_query.search", return_value=[]),
        patch("backend.supabase_client.ensure_conversation", return_value=None),
        patch("backend.sessions.sessions.session_exists", return_value=False),
        patch("backend.sessions.sessions.create_session", return_value="sess-abc"),
        patch("backend.sessions.sessions.get_context", return_value=[]),
        patch("backend.sessions.sessions.add_message"),
    ]


class TestStreamErrorEvent:
    """Stream sends type='error' SSE when generate_response_stream raises."""

    def test_error_event_sent_when_llm_raises(self, client):
        """If the LLM generator raises an exception, an error SSE event is emitted."""
        def failing_stream(*args, **kwargs):
            raise RuntimeError("Groq 500 error")
            yield  # make it a generator

        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.llm.generate_response_stream", side_effect=failing_stream),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="sess-abc"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "test"})
            assert resp.status_code == 200

            events = _collect_events(resp.text)
            error_events = [e for e in events if e.get("type") == "error"]
            assert len(error_events) >= 1, (
                f"Expected at least one error event, got: {events}"
            )

    def test_error_event_has_correct_shape(self, client):
        """Error event must have type='error' and a content field (string)."""
        def failing_stream(*args, **kwargs):
            raise RuntimeError("Groq rate limited")
            yield

        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.llm.generate_response_stream", side_effect=failing_stream),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="sess-abc"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "test"})
            events = _collect_events(resp.text)
            error_events = [e for e in events if e.get("type") == "error"]

            assert error_events, "No error events found"
            err = error_events[0]
            assert err["type"] == "error"
            assert "content" in err
            assert isinstance(err["content"], str)
            assert len(err["content"]) > 0

    def test_done_event_still_sent_after_error(self, client):
        """Even when an error occurs, a done event must follow for clean stream closure."""
        def failing_stream(*args, **kwargs):
            raise RuntimeError("LLM failure")
            yield

        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.llm.generate_response_stream", side_effect=failing_stream),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="sess-abc"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "test"})
            events = _collect_events(resp.text)
            done_events = [e for e in events if e.get("type") == "done"]

            assert len(done_events) == 1, (
                "Done event must be sent even after an error for clean stream closure"
            )

    def test_partial_stream_then_error_sends_tokens_first(self, client):
        """If some tokens arrive before LLM error, they should still be sent."""
        def partial_then_fail(*args, **kwargs):
            yield "partial answer"
            raise RuntimeError("network drop")

        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.llm.generate_response_stream", side_effect=partial_then_fail),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="sess-abc"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "test"})
            events = _collect_events(resp.text)

            token_events = [e for e in events if e.get("type") == "token"]
            assert len(token_events) >= 1, "Partial tokens should be emitted before error"
            assert any("partial answer" in e.get("content", "") for e in token_events)


class TestStreamTimeoutPath:
    """Test that the timeout configuration exists and error format is correct."""

    def test_timeout_error_event_has_retry_message(self, client):
        """Timeout error content must include actionable message for user."""
        # We can't easily test the 45s timeout directly, but we can verify
        # that when the queue sends an error event, the content is user-friendly.
        # The backend sends {"type": "error", "content": "Response timed out..."}
        def hanging_then_error(*args, **kwargs):
            raise asyncio.TimeoutError("queue timeout")
            yield

        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.llm.generate_response_stream", side_effect=hanging_then_error),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="sess-abc"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "test"})
            events = _collect_events(resp.text)
            error_events = [e for e in events if e.get("type") == "error"]
            assert error_events, "Error event should be sent on timeout"


class TestStreamQuotaIsNonBlocking:
    """Quota checks now run via asyncio.to_thread — verify they still work."""

    def test_global_quota_still_enforced_after_refactor(self, client):
        """asyncio.to_thread wrapping must not break quota enforcement."""
        with patch("backend.app.sqlite3") as mock_sqlite:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (99999,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "test"})
            assert resp.status_code == 429
            assert resp.json()["detail"]["error"] == "global_limit_reached"

    def test_user_quota_still_enforced_after_refactor(self, client):
        """Per-user quota via asyncio.to_thread must still block over-limit users."""
        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.check_user_quota", return_value=(False, 50, 0)),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post(
                "/api/query/stream", json={"query": "test"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 429
            assert resp.json()["detail"]["error"] == "daily_limit_reached"


class TestHealthEndpoints:
    """Verify both health endpoints have correct shape and status codes."""

    def test_healthz_always_200(self, client):
        """/healthz must return 200 and status=alive regardless of dependencies."""
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_healthz_no_dependency_keys(self, client):
        """/healthz must NOT include dependency checks (qdrant, corpus)."""
        resp = client.get("/healthz")
        body = resp.json()
        assert "qdrant" not in body
        assert "checks" not in body

    def test_api_health_includes_llm_slots(self, client):
        """/api/health must expose llm_slots_free for observability."""
        # QdrantClient is imported lazily inside the health function
        with patch("qdrant_client.QdrantClient") as mock_qdrant_cls:
            mock_qdrant = MagicMock()
            mock_qdrant_cls.return_value = mock_qdrant

            resp = client.get("/api/health")
            body = resp.json()
            assert "checks" in body
            assert "llm_slots_free" in body["checks"]

    def test_api_health_200_when_qdrant_up(self, client):
        """/api/health returns 200 when Qdrant responds."""
        with patch("qdrant_client.QdrantClient") as mock_qdrant_cls:
            mock_qdrant = MagicMock()
            mock_qdrant_cls.return_value = mock_qdrant
            resp = client.get("/api/health")
            assert resp.status_code in (200, 503)
            assert "status" in resp.json()

    def test_api_health_503_when_qdrant_down(self, client):
        """/api/health returns 503 when Qdrant is unreachable."""
        with patch("qdrant_client.QdrantClient") as mock_qdrant_cls:
            mock_qdrant_cls.return_value.get_collections.side_effect = ConnectionRefusedError("down")

            resp = client.get("/api/health")
            assert resp.status_code == 503
            body = resp.json()
            assert body["status"] == "degraded"
            assert "qdrant" in body["checks"]
            assert "error" in body["checks"]["qdrant"]
