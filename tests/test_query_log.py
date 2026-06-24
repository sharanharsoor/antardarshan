"""
Tests for DELETE /api/query-log endpoint.

Covers:
- 401 when no JWT provided
- 401 when JWT is invalid
- 200 with deleted count on success
- 503 when Supabase is unavailable
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestDeleteQueryLog:

    def test_returns_401_without_auth(self, client):
        """No Authorization header → 401."""
        response = client.delete("/api/query-log")
        assert response.status_code == 401

    def test_returns_401_with_invalid_jwt(self, client):
        """Invalid token → 401."""
        with patch("backend.supabase_client.verify_jwt", return_value=None):
            response = client.delete(
                "/api/query-log",
                headers={"Authorization": "Bearer bad-token"},
            )
        assert response.status_code == 401

    def test_returns_200_and_deleted_count_on_success(self, client):
        """Valid JWT + Supabase available → deletes rows, returns count."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "row1"}, {"id": "row2"}]
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = mock_result

        with patch("backend.supabase_client.verify_jwt", return_value="user-123"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.delete(
                "/api/query-log",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["deleted"] == 2

    def test_returns_503_when_supabase_unavailable(self, client):
        """Supabase client returns None → 503."""
        with patch("backend.supabase_client.verify_jwt", return_value="user-123"), \
             patch("backend.supabase_client.get_supabase", return_value=None):
            response = client.delete(
                "/api/query-log",
                headers={"Authorization": "Bearer valid-token"},
            )
        assert response.status_code == 503

    def test_returns_503_when_supabase_raises(self, client):
        """Supabase raises an exception → 503, not 500."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.side_effect = \
            Exception("connection reset")

        with patch("backend.supabase_client.verify_jwt", return_value="user-123"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.delete(
                "/api/query-log",
                headers={"Authorization": "Bearer valid-token"},
            )
        assert response.status_code == 503

    def test_returns_zero_deleted_when_no_rows(self, client):
        """No rows to delete → ok: True, deleted: 0."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = mock_result

        with patch("backend.supabase_client.verify_jwt", return_value="user-123"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.delete(
                "/api/query-log",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert response.status_code == 200
        assert response.json()["deleted"] == 0
