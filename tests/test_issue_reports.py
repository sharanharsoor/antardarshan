"""
Tests for POST /api/issues (text issue reporting in reading mode).

Covers:
- 401 when not authenticated
- 422 for invalid issue_type
- 422 for invalid chapter (< 1)
- Successful report returns ok=True + saved=True
- Supabase failure returns ok=True + saved=False (non-fatal)
- All valid issue_type values accepted
- Admin CLI command registered and exits gracefully
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.app import app, VALID_ISSUE_TYPES


@pytest.fixture
def client():
    return TestClient(app)


class TestIssueReportPost:

    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/api/issues", json={
            "slug": "bhagavad-gita", "scripture": "Bhagavad Gita",
            "chapter": 2, "issue_type": "ocr_garbage",
        })
        assert resp.status_code == 401

    def test_invalid_issue_type_rejected(self, client):
        with patch("backend.supabase_client.verify_jwt", return_value="user-123"):
            resp = client.post("/api/issues", json={
                "slug": "bhagavad-gita", "scripture": "Bhagavad Gita",
                "chapter": 2, "issue_type": "invalid_type",
            }, headers={"Authorization": "Bearer fake"})
            assert resp.status_code == 422

    def test_chapter_zero_rejected(self, client):
        with patch("backend.supabase_client.verify_jwt", return_value="user-123"):
            resp = client.post("/api/issues", json={
                "slug": "bhagavad-gita", "scripture": "Bhagavad Gita",
                "chapter": 0, "issue_type": "ocr_garbage",
            }, headers={"Authorization": "Bearer fake"})
            assert resp.status_code == 422

    def test_successful_report_returns_saved_true(self, client):
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])

            resp = client.post("/api/issues", json={
                "slug": "bhagavad-gita", "scripture": "Bhagavad Gita",
                "chapter": 2, "verse": 47, "issue_type": "ocr_garbage",
                "comment": "Text is garbled on this verse",
            }, headers={"Authorization": "Bearer fake"})

            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["saved"] is True

    def test_supabase_failure_returns_saved_false(self, client):
        """DB failure is non-fatal — endpoint returns 200 with saved=False."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_sb.return_value.table.side_effect = Exception("DB down")

            resp = client.post("/api/issues", json={
                "slug": "bhagavad-gita", "scripture": "Bhagavad Gita",
                "chapter": 2, "issue_type": "ocr_garbage",
            }, headers={"Authorization": "Bearer fake"})

            assert resp.status_code == 200
            assert resp.json()["saved"] is False

    def test_verse_is_optional(self, client):
        """Verse number is optional — chapter-level reports are valid."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])

            resp = client.post("/api/issues", json={
                "slug": "bhagavad-gita", "scripture": "Bhagavad Gita",
                "chapter": 2, "issue_type": "formatting",
            }, headers={"Authorization": "Bearer fake"})

            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    @pytest.mark.parametrize("issue_type", sorted(VALID_ISSUE_TYPES))
    def test_all_valid_issue_types_accepted(self, client, issue_type):
        """Every issue_type in VALID_ISSUE_TYPES must be accepted."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-123"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])

            resp = client.post("/api/issues", json={
                "slug": "test-slug", "scripture": "Test",
                "chapter": 1, "issue_type": issue_type,
            }, headers={"Authorization": "Bearer fake"})

            assert resp.status_code == 200, f"Failed for issue_type={issue_type}"

    def test_insert_payload_has_required_fields(self, client):
        """Verify the insert call includes all required DB fields."""
        with (
            patch("backend.supabase_client.verify_jwt", return_value="user-abc"),
            patch("backend.supabase_client.get_supabase") as mock_sb,
        ):
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])

            client.post("/api/issues", json={
                "slug": "dhammapada", "scripture": "Dhammapada",
                "chapter": 1, "verse": 5, "issue_type": "wrong_content",
                "comment": "Wrong source",
            }, headers={"Authorization": "Bearer fake"})

            payload = mock_table.insert.call_args[0][0]
            assert payload["user_id"] == "user-abc"
            assert payload["slug"] == "dhammapada"
            assert payload["scripture"] == "Dhammapada"
            assert payload["chapter"] == 1
            assert payload["verse"] == 5
            assert payload["issue_type"] == "wrong_content"
            assert payload["comment"] == "Wrong source"
            assert payload["status"] == "open"

    def test_comment_max_length_enforced(self, client):
        with patch("backend.supabase_client.verify_jwt", return_value="user-123"):
            resp = client.post("/api/issues", json={
                "slug": "test", "scripture": "Test", "chapter": 1,
                "issue_type": "other", "comment": "x" * 1001,
            }, headers={"Authorization": "Bearer fake"})
            assert resp.status_code == 422


class TestIssueAdminCLI:

    def test_issues_command_registered(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "ingestion.admin", "--help"],
            capture_output=True, text=True,
            cwd="/Users/sharsoor/Desktop/exp/person/bhagwatgita",
        )
        assert "issues" in result.stdout

    def test_issues_status_filter_options(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "ingestion.admin", "issues", "--help"],
            capture_output=True, text=True,
            cwd="/Users/sharsoor/Desktop/exp/person/bhagwatgita",
        )
        for status in ["open", "acknowledged", "fixed", "wontfix", "all"]:
            assert status in result.stdout

    def test_issues_no_supabase_exits_gracefully(self, capsys):
        import argparse, os
        from ingestion.admin import cmd_issues
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""}):
            args = argparse.Namespace(status="open")
            cmd_issues(args)
            assert "ERROR" in capsys.readouterr().out
