"""
Tests for POST /api/feedback.

Covers:
- Anonymous feedback (no JWT) — recorded in SQLite only
- Authenticated feedback without message_id — insert path
- Authenticated feedback with message_id — upsert path (dedup enforcement)
- Invalid rating values are accepted (validated by DB constraint, not API)
- Non-critical: Supabase failure does not break the endpoint response
"""

import pytest
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


def _feedback_payload(**kwargs):
    base = {"rating": 1, "mode": "citation"}
    base.update(kwargs)
    return base


class TestFeedbackAnonymous:

    def test_anonymous_feedback_returns_ok(self, client):
        """No JWT → feedback still returns 200 (stored in SQLite only)."""
        with patch("backend.llm.score_trace"):
            response = client.post("/api/feedback", json=_feedback_payload())
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_negative_rating_returns_ok(self, client):
        """Thumbs-down (rating=-1) is accepted."""
        with patch("backend.llm.score_trace"):
            response = client.post("/api/feedback", json=_feedback_payload(rating=-1))
        assert response.status_code == 200
        assert response.json()["ok"] is True


class TestFeedbackAuthenticated:

    def test_with_message_id_calls_upsert(self, client):
        """Authenticated feedback with message_id triggers upsert path."""
        mock_sb = MagicMock()
        # Message ownership check returns the message
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": "msg-1"}])
        # Conversation ownership check
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[{"user_id": "user-1", "id": "conv-1"}])

        upsert_chain = MagicMock()
        upsert_chain.execute.return_value = MagicMock()
        mock_sb.table.return_value.upsert.return_value = upsert_chain

        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.llm.score_trace"):
            response = client.post("/api/feedback",
                json=_feedback_payload(
                    conversation_id="conv-1",
                    message_id="msg-1",
                    rating=1,
                    comment="Great answer",
                ),
                headers={"Authorization": "Bearer tok"},
            )

        assert response.status_code == 200
        assert response.json()["ok"] is True
        # Upsert must have been called (not insert)
        mock_sb.table.return_value.upsert.assert_called_once()
        upsert_call_kwargs = mock_sb.table.return_value.upsert.call_args
        assert upsert_call_kwargs[1].get("on_conflict") == "user_id,message_id"

    def test_without_message_id_calls_insert(self, client):
        """Feedback without message_id (e.g. anonymous session) uses insert."""
        mock_sb = MagicMock()
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock()
        mock_sb.table.return_value.insert.return_value = insert_chain
        # Conversation check returns nothing (no conv_id provided)

        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.llm.score_trace"):
            response = client.post("/api/feedback",
                json=_feedback_payload(rating=-1, comment="Missed the scripture"),
                headers={"Authorization": "Bearer tok"},
            )

        assert response.status_code == 200
        # Insert called (not upsert) because no message_id
        mock_sb.table.return_value.insert.assert_called_once()

    def test_supabase_failure_does_not_break_response(self, client):
        """
        Feedback is non-critical — even if Supabase is down,
        the endpoint returns ok: True.
        """
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value \
            .execute.side_effect = Exception("DB unavailable")

        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.llm.score_trace"):
            response = client.post("/api/feedback",
                json=_feedback_payload(
                    conversation_id="conv-1", message_id="msg-1",
                ),
                headers={"Authorization": "Bearer tok"},
            )

        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_comment_is_stored_with_feedback(self, client):
        """Comment text is passed through to the upsert payload."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[{"id": "msg-2"}])
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[{"user_id": "user-1", "id": "conv-1"}])
        upsert_chain = MagicMock()
        upsert_chain.execute.return_value = MagicMock()
        mock_sb.table.return_value.upsert.return_value = upsert_chain

        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.llm.score_trace"):
            client.post("/api/feedback",
                json=_feedback_payload(
                    conversation_id="conv-1", message_id="msg-2",
                    rating=-1, comment="Wrong tradition cited",
                ),
                headers={"Authorization": "Bearer tok"},
            )

        upsert_payload = mock_sb.table.return_value.upsert.call_args[0][0]
        assert upsert_payload["comment"] == "Wrong tradition cited"
        assert upsert_payload["rating"] == -1
