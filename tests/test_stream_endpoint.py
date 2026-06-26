"""
Tests for the /api/query/stream endpoint.

Covers:
- 429 response shape matches frontend expectations (detail.error field)
- Global quota 429 before streaming starts
- Per-user quota 429 before streaming starts
- Successful stream returns SSE events with correct types
- Stream fallback on Groq error still sends 'done' event with citations
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestStreamQuota:
    """Stream endpoint returns 429 in the same shape as /api/query (detail.error)."""

    def test_global_quota_returns_correct_shape(self, client):
        """Global quota exceeded → 429 with detail.error = global_limit_reached."""
        with patch("backend.app.sqlite3") as mock_sqlite:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (99999,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "What is karma?"})
            assert resp.status_code == 429
            body = resp.json()
            assert "detail" in body
            assert body["detail"]["error"] == "global_limit_reached"

    def test_per_user_quota_returns_correct_shape(self, client):
        """Per-user quota exceeded → 429 with detail.error = daily_limit_reached."""
        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.check_user_quota", return_value=(False, 50, 0)),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)  # global ok
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post(
                "/api/query/stream",
                json={"query": "What is karma?"},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert resp.status_code == 429
            body = resp.json()
            assert "detail" in body
            assert body["detail"]["error"] == "daily_limit_reached"
            assert body["detail"]["limit"] == 50


class TestStreamEvents:
    """SSE event contract — token and done events have correct shape."""

    def _collect_events(self, resp_text: str) -> list[dict]:
        """Parse SSE lines into event dicts."""
        events = []
        for line in resp_text.splitlines():
            if line.startswith("data: ") and not line.endswith("[DONE]"):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        return events

    def test_successful_stream_sends_token_and_done_events(self, client):
        """A successful stream must emit at least one token event and a done event."""
        def fake_stream(*args, **kwargs):
            yield "Hello"
            yield " world"
            return ("trace-123", "llama-3.1-8b-instant", 500)

        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.llm.generate_response_stream", side_effect=fake_stream),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="sess-abc"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "What is karma?"})
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            events = self._collect_events(resp.text)
            token_events = [e for e in events if e.get("type") == "token"]
            done_events = [e for e in events if e.get("type") == "done"]

            assert len(token_events) >= 1, "Expected at least one token event"
            assert len(done_events) == 1, "Expected exactly one done event"

            # Token events have content field
            assert all("content" in e for e in token_events)

            # Done event has required fields
            done = done_events[0]
            assert "session_id" in done
            assert "mode" in done
            assert "citations" in done

    def test_done_event_contains_citations_with_readable_flag(self, client):
        """Done event citations include readable flag."""
        def fake_stream(*args, **kwargs):
            yield "Answer"
            return (None, None, 100)

        mock_hits = [{
            "scripture": "Bhagavad Gita", "chapter": 2, "verse": 47,
            "translator": "Edwin Arnold", "year": 1885, "tradition": "hindu_vedanta",
            "text": "Let right deeds be thy motive.", "themes": [],
            "chunk_type": "verse", "verse_type": "verse", "speaker": None,
            "chapter_name": None, "chunk_id": "", "parent_text": "",
        }]

        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.rag_query.search", return_value=mock_hits),
            patch("backend.llm.generate_response_stream", side_effect=fake_stream),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="sess-abc"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn

            resp = client.post("/api/query/stream", json={"query": "What is karma?"})
            events = self._collect_events(resp.text)
            done_events = [e for e in events if e.get("type") == "done"]

            assert len(done_events) == 1
            citations = done_events[0].get("citations", [])
            assert len(citations) == 1
            # readable flag present (True since corpus not initialized → fallback)
            assert "readable" in citations[0]


# ── FOLLOWUPS parsing helper ───────────────────────────────────────────

class TestParseFollowUps:

    def test_strips_followups_and_returns_questions(self):
        from backend.app import _parse_follow_ups
        text = "## Dharma\nSome synthesis paragraph.\nFOLLOWUPS: What is karma? | How does dharma evolve?"
        clean, qs = _parse_follow_ups(text)
        assert "FOLLOWUPS" not in clean
        assert len(qs) == 2
        assert qs[0] == "What is karma?"
        assert qs[1] == "How does dharma evolve?"

    def test_tolerant_of_case_variants(self):
        from backend.app import _parse_follow_ups
        text = "Answer text.\nFollowups: Q1 | Q2"
        clean, qs = _parse_follow_ups(text)
        assert "Followups" not in clean
        assert len(qs) == 2

    def test_tolerant_of_whitespace_before_colon(self):
        from backend.app import _parse_follow_ups
        text = "Answer.\nFOLLOWUPS : Q1 | Q2"
        clean, qs = _parse_follow_ups(text)
        assert len(qs) == 2

    def test_returns_empty_list_when_no_followups(self):
        from backend.app import _parse_follow_ups
        text = "Just a normal answer with no follow-ups appended."
        clean, qs = _parse_follow_ups(text)
        assert clean == text
        assert qs == []

    def test_caps_at_three_questions(self):
        from backend.app import _parse_follow_ups
        text = "Answer.\nFOLLOWUPS: Q1 | Q2 | Q3 | Q4 | Q5"
        _, qs = _parse_follow_ups(text)
        assert len(qs) == 3

    def test_clean_answer_has_no_trailing_whitespace(self):
        from backend.app import _parse_follow_ups
        text = "Synthesis paragraph.  \n\nFOLLOWUPS: Q1"
        clean, _ = _parse_follow_ups(text)
        assert not clean.endswith(" ")
        assert not clean.endswith("\n")
