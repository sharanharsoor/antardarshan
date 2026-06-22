"""
Tests for conversation persistence, per-user query quota, and CRUD endpoints.

Covers:
- backend/supabase_client.py — quota checks, conversation helpers, auto-titling
- /api/conversations (GET, PATCH, DELETE) — CRUD endpoints
- /api/quota-status/user — per-user quota status
- /api/query — quota enforcement and Supabase persistence integration

All tests mock the Supabase client so they run without a live connection.
Integration tests requiring a real Supabase instance are marked @pytest.mark.integration.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ── supabase_client unit tests ─────────────────────────────────────────────────

class TestAutoTitle:
    """Test conversation title generation from first message."""

    def test_short_message_unchanged(self):
        from backend.supabase_client import _auto_title
        assert _auto_title("What is karma?") == "What is karma"

    def test_question_mark_stripped(self):
        from backend.supabase_client import _auto_title
        assert _auto_title("What does the Gita say about duty?") == "What does the Gita say about duty"

    def test_long_message_truncated_at_word_boundary(self):
        from backend.supabase_client import _auto_title
        msg = "This is a very long question about the nature of the self in Advaita Vedanta philosophy and how it differs from Buddhism"
        result = _auto_title(msg, max_len=60)
        assert len(result) <= 62  # <= 60 + "…"
        assert result.endswith("…")
        # Should not cut mid-word
        parts = result[:-1].split(" ")
        assert all(p for p in parts)  # no empty parts from mid-word cut

    def test_exact_max_length_not_truncated(self):
        from backend.supabase_client import _auto_title
        msg = "A" * 60
        result = _auto_title(msg, max_len=60)
        assert result == msg
        assert "…" not in result

    def test_strips_whitespace(self):
        from backend.supabase_client import _auto_title
        assert _auto_title("  What is dharma?  ") == "What is dharma"


class TestQuotaHelpers:
    """Test per-user quota logic."""

    def test_check_quota_no_supabase_always_allows(self):
        """If Supabase is unavailable, quota check should allow (fail-open)."""
        with patch("backend.supabase_client.get_supabase", return_value=None):
            from backend.supabase_client import check_user_quota
            allowed, used, remaining = check_user_quota("user-123")
            assert allowed is True
            assert used == 0

    def test_check_quota_returns_correct_values(self):
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.count = 12
        mock_sb.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_result

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            from backend.supabase_client import check_user_quota, PER_USER_DAILY_LIMIT
            allowed, used, remaining = check_user_quota("user-123")
            assert used == 12
            assert remaining == PER_USER_DAILY_LIMIT - 12
            assert allowed is True

    def test_quota_exhausted_when_at_limit(self):
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.count = 50  # at limit
        mock_sb.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_result

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            from backend.supabase_client import check_user_quota
            allowed, used, remaining = check_user_quota("user-123")
            assert allowed is False
            assert used == 50
            assert remaining == 0

    def test_log_user_query_no_supabase_silent(self):
        """log_user_query must not raise even if Supabase is unavailable."""
        with patch("backend.supabase_client.get_supabase", return_value=None):
            from backend.supabase_client import log_user_query
            log_user_query("user-123", None, "citation", "llama-3.1-8b-instant")


class TestConversationHelpers:
    """Test conversation persistence helpers."""

    def test_persist_messages_no_supabase_silent(self):
        """persist_messages must not raise if Supabase is unavailable."""
        with patch("backend.supabase_client.get_supabase", return_value=None):
            from backend.supabase_client import persist_messages
            persist_messages(
                conversation_id="conv-123",
                user_message="What is karma?",
                assistant_message="Karma is action...",
                citations=[],
                mode="citation",
                model="llama-3.1-8b-instant",
                tokens_used=1200,
            )

    def test_ensure_conversation_returns_existing_when_owner(self):
        """Owner can write to their own conversation."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "conv-existing", "user_id": "user-123"}]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            from backend.supabase_client import ensure_conversation
            result = ensure_conversation("conv-existing", "user-123")
            assert result == "conv-existing"

    def test_ensure_conversation_rejects_non_owner(self):
        """Non-owner cannot write to another user's conversation (IDOR protection)."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "conv-existing", "user_id": "owner-999"}]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            from backend.supabase_client import ensure_conversation
            result = ensure_conversation("conv-existing", "other-user")
            assert result is None  # write denied

    def test_ensure_conversation_rejects_unauthenticated_write(self):
        """No user_id → cannot write to an existing conversation."""
        with patch("backend.supabase_client.get_supabase", return_value=MagicMock()):
            from backend.supabase_client import ensure_conversation
            result = ensure_conversation("conv-existing", None)
            assert result is None

    def test_ensure_conversation_creates_new_when_no_id(self):
        """Authenticated user with no conversation_id gets a new conversation."""
        mock_sb = MagicMock()
        mock_create = MagicMock()
        mock_create.data = [{"id": "conv-new-123"}]
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_create

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            from backend.supabase_client import ensure_conversation
            result = ensure_conversation(None, "user-123")
            assert result == "conv-new-123"

    def test_ensure_conversation_anonymous_gets_no_persistence(self):
        """No user_id + no conversation_id → no persistence."""
        with patch("backend.supabase_client.get_supabase", return_value=MagicMock()):
            from backend.supabase_client import ensure_conversation
            result = ensure_conversation(None, None)
            assert result is None

    def test_get_conversation_returns_none_when_missing(self):
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []  # not found
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            from backend.supabase_client import get_conversation
            result = get_conversation("conv-nonexistent")
            assert result is None


# ── FastAPI endpoint tests ─────────────────────────────────────────────────────

@pytest.fixture
def client():
    from backend.app import app
    return TestClient(app)


class TestConversationEndpoints:
    """Test conversation CRUD HTTP endpoints."""

    def test_get_conversation_not_found(self, client):
        with patch("backend.supabase_client.get_conversation", return_value=None):
            resp = client.get("/api/conversations/nonexistent-id")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"].lower()

    def test_get_conversation_found_as_owner(self, client):
        """Owner (JWT matches user_id) can read private conversation."""
        mock_data = {
            "conversation": {"id": "conv-1", "user_id": "user-1", "title": "Karma", "shared": False, "created_at": "2026-06-21", "updated_at": "2026-06-21"},
            "messages": [
                {"id": "msg-1", "role": "user", "content": "What is karma?", "conversation_id": "conv-1", "citations": None, "mode": None, "model": None, "tokens_used": None, "created_at": "2026-06-21"},
            ],
        }
        with (
            patch("backend.supabase_client.get_conversation", return_value=mock_data),
            patch("backend.supabase_client.verify_jwt", return_value="user-1"),
        ):
            resp = client.get(
                "/api/conversations/conv-1",
                headers={"Authorization": "Bearer fake-test-token"},
            )
            assert resp.status_code == 200
            assert resp.json()["conversation"]["id"] == "conv-1"
            assert len(resp.json()["messages"]) == 1

    def test_get_conversation_private_non_owner_returns_404(self, client):
        """Non-owner cannot access a private conversation — returns 404 (not 403)."""
        mock_data = {
            "conversation": {"id": "conv-1", "user_id": "user-1", "title": "Karma", "shared": False},
            "messages": [],
        }
        with (
            patch("backend.supabase_client.get_conversation", return_value=mock_data),
            patch("backend.supabase_client.verify_jwt", return_value="other-user"),
        ):
            resp = client.get(
                "/api/conversations/conv-1",
                headers={"Authorization": "Bearer fake-test-token"},
            )
            assert resp.status_code == 404

    def test_get_conversation_shared_accessible_without_auth(self, client):
        """Shared conversations are readable by anyone — no auth needed."""
        mock_data = {
            "conversation": {"id": "conv-1", "user_id": "user-1", "title": "Karma", "shared": True},
            "messages": [],
        }
        with (
            patch("backend.supabase_client.get_conversation", return_value=mock_data),
            patch("backend.supabase_client.verify_jwt", return_value=None),
        ):
            resp = client.get("/api/conversations/conv-1")
            assert resp.status_code == 200

    def test_list_conversations_requires_auth(self, client):
        """Without JWT, /api/conversations returns 401."""
        resp = client.get("/api/conversations")
        assert resp.status_code == 401

    def test_list_conversations_with_auth(self, client):
        """With valid JWT, conversations are returned."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.list_conversations", return_value=[]),
        ):
            resp = client.get(
                "/api/conversations",
                headers={"Authorization": "Bearer fake-test-token"},
            )
            assert resp.status_code == 200
            assert resp.json()["conversations"] == []

    def test_delete_conversation_success(self, client):
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.delete_conversation", return_value=True),
        ):
            resp = client.delete(
                "/api/conversations/conv-1",
                headers={"Authorization": "Bearer fake-test-token"},
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    def test_delete_conversation_requires_auth(self, client):
        """Without JWT, delete returns 401."""
        resp = client.delete("/api/conversations/conv-1")
        assert resp.status_code == 401

    def test_user_quota_status_no_auth(self, client):
        """Without JWT, per-user quota fields are null."""
        with patch("backend.supabase_client.verify_jwt", return_value=None):
            resp = client.get("/api/quota-status/user")
            assert resp.status_code == 200
            data = resp.json()
            assert data["per_user_used"] is None

    def test_user_quota_status_with_auth(self, client):
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.check_user_quota", return_value=(True, 12, 38)),
        ):
            resp = client.get(
                "/api/quota-status/user",
                headers={"Authorization": "Bearer fake-test-token"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["per_user_used"] == 12
            assert data["per_user_remaining"] == 38
            assert data["per_user_allowed"] is True


class TestConversationWriteIDOR:
    """Tests that /api/query cannot write to conversations the caller doesn't own."""

    def test_query_with_foreign_conversation_silently_skips_persistence(self, client):
        """Passing another user's conversation_id should not persist messages there.
        The query still returns an answer — only persistence is silently skipped."""
        # ensure_conversation returns None when caller doesn't own the conversation
        with (
            patch("backend.supabase_client.verify_jwt", return_value="attacker-user"),
            patch("backend.supabase_client.check_user_quota", return_value=(True, 0, 50)),
            patch("backend.supabase_client.ensure_conversation", return_value=None),  # IDOR blocked
            patch("backend.supabase_client.persist_messages") as mock_persist,
            patch("backend.supabase_client.log_user_query"),
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.llm.generate_response", return_value=("Answer", None, "llama-3.1-8b-instant", 100)),
        ):
            resp = client.post(
                "/api/query",
                json={"query": "What is karma?", "conversation_id": "victim-conv-id"},
                headers={"Authorization": "Bearer attacker-token"},
            )
            assert resp.status_code == 200  # query still answers
            mock_persist.assert_not_called()  # but nothing was written

    def test_query_with_conversation_id_and_no_jwt_skips_persistence(self, client):
        """conversation_id without JWT → unauthenticated, no write."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value=None),
            patch("backend.supabase_client.ensure_conversation", return_value=None),
            patch("backend.supabase_client.persist_messages") as mock_persist,
            patch("backend.rag_query.search", return_value=[]),
            patch("backend.llm.generate_response", return_value=("Answer", None, "llama-3.1-8b-instant", 100)),
        ):
            resp = client.post(
                "/api/query",
                json={"query": "What is karma?", "conversation_id": "some-conv-id"},
            )
            assert resp.status_code == 200
            mock_persist.assert_not_called()


class TestQueryWithConversation:
    """Test that /api/query correctly passes conversation data to persistence layer."""

    def test_query_enforces_user_quota(self, client):
        """When user has exhausted quota, /api/query returns 429.
        user_id is now derived server-side from the JWT — mock verify_jwt."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.check_user_quota", return_value=(False, 50, 0)),
        ):
            resp = client.post(
                "/api/query",
                json={"query": "What is karma?"},
                headers={"Authorization": "Bearer fake-test-token"},
            )
            assert resp.status_code == 429
            assert resp.json()["detail"]["error"] == "daily_limit_reached"

    def test_query_allows_when_quota_available(self, client):
        """When quota is available, query proceeds normally."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.check_user_quota", return_value=(True, 5, 45)),
            patch("backend.supabase_client.ensure_conversation", return_value="conv-123"),
            patch("backend.supabase_client.get_conversation", return_value={"conversation": {}, "messages": []}),
            patch("backend.supabase_client.persist_messages", return_value=(True, "msg-uuid-123")),
            patch("backend.supabase_client.log_user_query"),
        ):
            with (
                patch("backend.rag_query.search", return_value=[]),
                patch("backend.llm.generate_response", return_value=("Test answer", None, "llama-3.1-8b-instant", 1000)),
            ):
                resp = client.post(
                    "/api/query",
                    json={"query": "What is karma?", "conversation_id": "conv-123"},
                    headers={"Authorization": "Bearer fake-test-token"},
                )
                assert resp.status_code == 200


# ── Conversation grouping util tests ───────────────────────────────────────────

class TestConversationGrouping:
    """Test the date-based grouping utility (frontend logic, tested via Python equivalent)."""

    def test_title_generation(self):
        from backend.supabase_client import _auto_title

        # Edge cases
        assert _auto_title("") == ""
        assert _auto_title("?") == ""
        assert _auto_title("   ") == ""
        assert _auto_title("What is Atman?") == "What is Atman"

    def test_update_conversation_rejects_unknown_fields(self):
        """update_conversation should only allow title and shared fields."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            from backend.supabase_client import update_conversation
            # Should return False for empty/disallowed updates
            result = update_conversation("conv-1", "user-1", {"user_id": "hacker", "unknown": "field"})
            assert result is False

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            from backend.supabase_client import update_conversation
            # Should succeed for allowed fields
            result = update_conversation("conv-1", "user-1", {"title": "New Title", "shared": True})
            assert result is True
