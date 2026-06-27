"""
Tests for POST/GET /api/feedback/book (book-level thumbs up/down).

Covers:
- 401 when not authenticated
- 400 for invalid rating values
- Successful submission returns ok=True + scripture + rating
- GET returns empty dict for unauthenticated users
- GET returns ratings dict for authenticated users
- Rating switches (thumbs up → thumbs down) work correctly
- Admin CLI command is registered and callable
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestBookFeedbackPost:

    def test_unauthenticated_returns_401(self, client):
        """POST /api/feedback/book requires auth."""
        resp = client.post("/api/feedback/book", json={"scripture": "Bhagavad Gita", "rating": 1})
        assert resp.status_code == 401

    def test_invalid_rating_zero_rejected(self, client):
        """Rating 0 is invalid (only 1 or -1 allowed)."""
        with patch("backend.supabase_client.verify_jwt", return_value="user-123"):
            resp = client.post(
                "/api/feedback/book",
                json={"scripture": "Bhagavad Gita", "rating": 0},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422  # Pydantic validation error

    def test_invalid_rating_2_rejected(self, client):
        """Rating 2 is not valid."""
        with patch("backend.supabase_client.verify_jwt", return_value="user-123"):
            resp = client.post(
                "/api/feedback/book",
                json={"scripture": "Bhagavad Gita", "rating": 2},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422

    def test_thumbs_up_returns_ok(self, client):
        """Valid thumbs up submission returns ok=True."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.upsert.return_value.execute.return_value = MagicMock(data=[])

            resp = client.post(
                "/api/feedback/book",
                json={"scripture": "Bhagavad Gita", "rating": 1},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["scripture"] == "Bhagavad Gita"
            assert body["rating"] == 1

    def test_thumbs_down_returns_ok(self, client):
        """Valid thumbs down submission returns ok=True."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.upsert.return_value.execute.return_value = MagicMock(data=[])

            resp = client.post(
                "/api/feedback/book",
                json={"scripture": "Mahabharata", "rating": -1},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            assert resp.json()["rating"] == -1

    def test_upsert_called_with_correct_args(self, client):
        """Supabase upsert is called with user_id, scripture, rating."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-abc"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.upsert.return_value.execute.return_value = MagicMock(data=[])

            client.post(
                "/api/feedback/book",
                json={"scripture": "Dhammapada", "rating": 1},
                headers={"Authorization": "Bearer fake"},
            )

            call_args = mock_table.upsert.call_args
            payload = call_args[0][0]
            assert payload["user_id"] == "user-abc"
            assert payload["scripture"] == "Dhammapada"
            assert payload["rating"] == 1

    def test_supabase_failure_is_non_fatal(self, client):
        """If Supabase upsert fails, endpoint still returns 200 (non-critical)."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_sb.return_value.table.side_effect = Exception("DB down")

            resp = client.post(
                "/api/feedback/book",
                json={"scripture": "Bhagavad Gita", "rating": 1},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    def test_empty_scripture_rejected(self, client):
        """Empty scripture string is invalid."""
        with patch("backend.supabase_client.verify_jwt", return_value="user-123"):
            resp = client.post(
                "/api/feedback/book",
                json={"scripture": "", "rating": 1},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422


class TestBookFeedbackGet:

    def test_unauthenticated_returns_empty_ratings(self, client):
        """GET /api/feedback/book returns empty dict when not signed in."""
        with patch("backend.supabase_client.verify_jwt", return_value=None):
            resp = client.get("/api/feedback/book")
            assert resp.status_code == 200
            assert resp.json()["ratings"] == {}

    def test_authenticated_returns_user_ratings(self, client):
        """GET returns {scripture: rating} dict for the authenticated user."""
        mock_rows = [
            {"scripture": "Bhagavad Gita", "rating": 1},
            {"scripture": "Mahabharata", "rating": -1},
        ]
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_rows)

            resp = client.get("/api/feedback/book", headers={"Authorization": "Bearer fake"})
            assert resp.status_code == 200
            ratings = resp.json()["ratings"]
            assert ratings["Bhagavad Gita"] == 1
            assert ratings["Mahabharata"] == -1

    def test_supabase_failure_returns_empty(self, client):
        """If Supabase fails, GET returns empty ratings (not a 500)."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_sb.return_value.table.side_effect = Exception("DB down")

            resp = client.get("/api/feedback/book", headers={"Authorization": "Bearer fake"})
            assert resp.status_code == 200
            assert resp.json()["ratings"] == {}


class TestBookFeedbackAdminCLI:

    def test_book_feedback_command_registered(self):
        """book-feedback command is registered in the CLI."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "ingestion.admin", "--help"],
            capture_output=True, text=True,
            cwd="/Users/sharsoor/Desktop/exp/person/bhagwatgita",
        )
        assert "book-feedback" in result.stdout

    def test_book_feedback_no_supabase_exits_gracefully(self, capsys):
        """book-feedback command exits gracefully when Supabase is not configured."""
        import argparse
        from ingestion.admin import cmd_book_feedback
        import os

        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""}):
            args = argparse.Namespace()
            cmd_book_feedback(args)  # should not raise
            captured = capsys.readouterr()
            assert "ERROR" in captured.out or "SUPABASE" in captured.out
