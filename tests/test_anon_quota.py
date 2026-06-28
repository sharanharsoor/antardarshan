"""
Tests for the anonymous daily query cap (ANON_DAILY_LIMIT).

Covers:
- _get_and_increment_anon_count: increments correctly, returns new count
- _get_anon_count: reads without incrementing
- /api/query: rejects anonymous requests at limit with anon_limit_reached
- /api/query: allows authenticated requests even when anon limit is exceeded
- /api/query/stream: same enforcement parity as /api/query
- _get_and_increment_anon_count: fail-open on SQLite error (returns 0)
- Error response shape matches frontend expectations (error + limit + message)
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import backend.app as app_module
from backend.app import app, ANON_DAILY_LIMIT, _get_and_increment_anon_count, _get_anon_count


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a fresh SQLite DB for counter tests."""
    db_path = tmp_path / "test_quotas.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS anon_daily_counts (
            date TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    return db_path


# ── Counter unit tests ────────────────────────────────────────────────────────

class TestAnonCounter:

    def test_first_increment_returns_one(self, tmp_db):
        with patch.object(app_module, "DB_PATH", tmp_db):
            result = _get_and_increment_anon_count("2026-06-28")
        assert result == 1

    def test_second_increment_returns_two(self, tmp_db):
        with patch.object(app_module, "DB_PATH", tmp_db):
            _get_and_increment_anon_count("2026-06-28")
            result = _get_and_increment_anon_count("2026-06-28")
        assert result == 2

    def test_different_dates_are_independent(self, tmp_db):
        with patch.object(app_module, "DB_PATH", tmp_db):
            _get_and_increment_anon_count("2026-06-28")
            _get_and_increment_anon_count("2026-06-28")
            result_new_day = _get_and_increment_anon_count("2026-06-29")
        assert result_new_day == 1

    def test_get_count_does_not_increment(self, tmp_db):
        with patch.object(app_module, "DB_PATH", tmp_db):
            _get_and_increment_anon_count("2026-06-28")
            before = _get_anon_count("2026-06-28")
            _get_anon_count("2026-06-28")  # second read
            after = _get_anon_count("2026-06-28")
        assert before == after == 1

    def test_get_count_returns_zero_for_new_day(self, tmp_db):
        with patch.object(app_module, "DB_PATH", tmp_db):
            result = _get_anon_count("2099-01-01")
        assert result == 0

    def test_fail_open_on_sqlite_error(self):
        """On OperationalError, counter returns 0 (fail-open — request proceeds)."""
        with patch("backend.app.sqlite3") as mock_sqlite:
            mock_sqlite.OperationalError = sqlite3.OperationalError
            mock_sqlite.connect.side_effect = sqlite3.OperationalError("locked")

            result = _get_and_increment_anon_count("2026-06-28")

        assert result == 0, "Fail-open: lock error must not crash the request"

    def test_anon_daily_limit_constant(self):
        """ANON_DAILY_LIMIT must be a positive integer."""
        assert isinstance(ANON_DAILY_LIMIT, int)
        assert ANON_DAILY_LIMIT > 0


# ── /api/query endpoint tests ─────────────────────────────────────────────────

class TestAnonQueryEndpoint:

    def _base_patches(self, anon_count=0):
        """Patches that let the request reach the anon quota check."""
        return [
            patch("backend.app.sqlite3") ,
            patch("backend.supabase_client.verify_jwt", return_value=None),
        ]

    def test_anonymous_request_blocked_at_limit(self, client):
        """Anonymous request when counter > ANON_DAILY_LIMIT → 429 anon_limit_reached."""
        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.app._get_and_increment_anon_count",
                  return_value=ANON_DAILY_LIMIT + 1),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)  # global quota ok
            mock_sqlite.connect.return_value = mock_conn
            mock_sqlite.OperationalError = sqlite3.OperationalError

            resp = client.post("/api/query", json={"query": "What is karma?"})

        assert resp.status_code == 429
        body = resp.json()
        assert body["detail"]["error"] == "anon_limit_reached"
        assert body["detail"]["limit"] == ANON_DAILY_LIMIT
        assert "Sign in" in body["detail"]["message"] or "sign in" in body["detail"]["message"].lower()

    def test_anonymous_request_allowed_under_limit(self, client):
        """Anonymous request when counter ≤ ANON_DAILY_LIMIT is NOT blocked here."""
        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.app._get_and_increment_anon_count",
                  return_value=ANON_DAILY_LIMIT),
            # Still need to mock the rest of the pipeline to avoid real calls
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.llm.generate_response",
                  return_value=("answer", "trace", "model", 100)),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="s"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn
            mock_sqlite.OperationalError = sqlite3.OperationalError

            resp = client.post("/api/query", json={"query": "What is karma?"})

        # Should not get 429 for anon limit (may get 200 or other limit)
        assert resp.status_code != 429 or resp.json()["detail"]["error"] != "anon_limit_reached"

    def test_authenticated_user_bypasses_anon_cap(self, client):
        """Authenticated user is exempt from anonymous cap even if it's exceeded."""
        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.check_user_quota",
                  return_value=(True, 5, 45)),
            patch("backend.app._get_and_increment_anon_count") as mock_counter,
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.llm.generate_response",
                  return_value=("answer", "trace", "model", 100)),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="s"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn
            mock_sqlite.OperationalError = sqlite3.OperationalError

            resp = client.post(
                "/api/query", json={"query": "What is karma?"},
                headers={"Authorization": "Bearer token"},
            )

        # Authenticated users must NEVER hit the anon counter
        mock_counter.assert_not_called()
        assert resp.status_code != 429 or resp.json()["detail"]["error"] != "anon_limit_reached"


# ── /api/query/stream parity ──────────────────────────────────────────────────

class TestAnonStreamEndpoint:

    def test_stream_blocked_at_anon_limit(self, client):
        """/api/query/stream enforces the same anon cap as /api/query."""
        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.app._get_and_increment_anon_count",
                  return_value=ANON_DAILY_LIMIT + 5),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn
            mock_sqlite.OperationalError = sqlite3.OperationalError

            resp = client.post("/api/query/stream", json={"query": "test"})

        assert resp.status_code == 429
        body = resp.json()
        assert body["detail"]["error"] == "anon_limit_reached"

    def test_stream_authenticated_bypasses_anon_cap(self, client):
        """/api/query/stream: authenticated users never hit the anon counter."""
        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value="user-abc"),
            patch("backend.supabase_client.check_user_quota",
                  return_value=(True, 1, 49)),
            patch("backend.app._get_and_increment_anon_count") as mock_counter,
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.rag_query.detect_mode", return_value="citation"),
            patch("backend.llm.generate_response_stream",
                  side_effect=lambda *a, **k: iter([])),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.supabase_client.log_user_query"),
            patch("backend.supabase_client.persist_messages", return_value=(False, None)),
            patch("backend.supabase_client.get_conversation", return_value=None),
            patch("backend.sessions.sessions.session_exists", return_value=False),
            patch("backend.sessions.sessions.create_session", return_value="s"),
            patch("backend.sessions.sessions.get_context", return_value=[]),
            patch("backend.sessions.sessions.add_message"),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn
            mock_sqlite.OperationalError = sqlite3.OperationalError

            client.post(
                "/api/query/stream", json={"query": "test"},
                headers={"Authorization": "Bearer tok"},
            )

        mock_counter.assert_not_called()


# ── Error shape contract ───────────────────────────────────────────────────────

class TestAnonLimitErrorShape:

    def test_error_shape_has_required_fields(self, client):
        """anon_limit_reached error must have error, limit, and message fields."""
        with (
            patch("backend.app.sqlite3") as mock_sqlite,
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.app._get_and_increment_anon_count",
                  return_value=ANON_DAILY_LIMIT + 1),
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = (0,)
            mock_sqlite.connect.return_value = mock_conn
            mock_sqlite.OperationalError = sqlite3.OperationalError

            resp = client.post("/api/query", json={"query": "test"})

        detail = resp.json()["detail"]
        assert "error" in detail
        assert "limit" in detail
        assert "message" in detail
        assert detail["limit"] == ANON_DAILY_LIMIT
        assert isinstance(detail["message"], str)
        assert len(detail["message"]) > 10
