"""
Tests for Wisdom Wall — backend endpoints, moderation helper, and cron job.

Covers:
- is_conversational_followup() (pure function)
- moderate_post() (mocked Groq client)
- run_daily_maintenance() (mocked Supabase)
- GET /api/wisdom (public feed)
- POST /api/wisdom (auth, rate limits, moderation gate)
- DELETE /api/wisdom/{id} (auth, ownership)
- POST /api/wisdom/{id}/vote (auth)
- GET/PUT /api/wisdom/me/display-name
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app import app
from backend.query_analysis import is_conversational_followup
from backend.wisdom import moderate_post, run_daily_maintenance


@pytest.fixture
def client():
    return TestClient(app)


# ── is_conversational_followup ─────────────────────────────────────────

class TestIsConversationalFollowup:

    def test_end_conclusion_according_to_you(self):
        assert is_conversational_followup("what is the end conclusion according to you?") is True

    def test_what_do_you_think(self):
        assert is_conversational_followup("what do you think?") is True

    def test_summarize(self):
        assert is_conversational_followup("summarize what you said") is True

    def test_in_your_opinion(self):
        assert is_conversational_followup("in your opinion") is True

    def test_can_you_explain_more(self):
        assert is_conversational_followup("can you explain more") is True

    def test_tell_me_more(self):
        assert is_conversational_followup("tell me more") is True

    def test_simplify(self):
        assert is_conversational_followup("simplify this") is True

    def test_real_question_dharma(self):
        assert is_conversational_followup("what is dharma?") is False

    def test_real_question_karma_yoga(self):
        assert is_conversational_followup("tell me about karma yoga") is False

    def test_real_question_gita(self):
        assert is_conversational_followup("what is the gita") is False

    def test_real_question_how(self):
        assert is_conversational_followup("how does meditation work?") is False

    def test_empty_string_not_followup(self):
        # Empty is not a meaningful followup — treat as real query
        assert is_conversational_followup("") is False

    def test_very_short_non_philosophical(self):
        # "nice" has no philosophical keywords — likely conversational
        assert is_conversational_followup("nice") is True

    def test_very_short_with_what(self):
        # "what" contains a philosophical keyword — don't mark as followup
        assert is_conversational_followup("what") is False


# ── moderate_post ──────────────────────────────────────────────────────

class TestModeratePost:

    def test_approves_spiritual_content(self):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "APPROVED"
        with patch("backend.wisdom._get_mod_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_resp
            mock_client_fn.return_value = mock_client
            approved, reason = moderate_post("The Bhagavad Gita teaches us about detachment.")
        assert approved is True
        assert reason == "approved"

    def test_rejects_off_topic_content(self):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "REJECTED: This is a political advertisement."
        with patch("backend.wisdom._get_mod_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_resp
            mock_client_fn.return_value = mock_client
            approved, reason = moderate_post("Vote for me in the upcoming election!")
        assert approved is False
        assert "political" in reason.lower()

    def test_fails_open_when_llm_unavailable(self):
        """If Groq is down, posts are approved (fail open) to not block users."""
        with patch("backend.wisdom._get_mod_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("503 Service Unavailable")
            mock_client_fn.return_value = mock_client
            approved, reason = moderate_post("Any content here")
        assert approved is True

    def test_fails_open_when_no_client(self):
        with patch("backend.wisdom._get_mod_client", return_value=None):
            approved, reason = moderate_post("Anything")
        assert approved is True

    def test_unclear_response_approves(self):
        """If model returns something neither APPROVED nor REJECTED, approve."""
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "I cannot determine the appropriateness."
        with patch("backend.wisdom._get_mod_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_resp
            mock_client_fn.return_value = mock_client
            approved, _ = moderate_post("Some content")
        assert approved is True


# ── run_daily_maintenance ─────────────────────────────────────────────

class TestRunDailyMaintenance:

    def _make_sb(self, posts_data):
        """Build a minimal Supabase mock for maintenance tests."""
        chain = MagicMock()
        # contact info update chain
        chain.table.return_value.update.return_value.is_.return_value.lt.return_value.execute.return_value = MagicMock()
        # select posts for auto-remove
        result = MagicMock()
        result.data = posts_data
        chain.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = result
        # update is_removed
        chain.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        return chain

    def test_removes_high_downvote_posts(self):
        posts = [{"id": "p1", "upvotes": 2, "downvotes": 8}]  # 80% downvotes, well above 40%
        sb = self._make_sb(posts)
        result = run_daily_maintenance(sb)
        assert result["posts_removed"] == 1

    def test_keeps_low_downvote_posts(self):
        posts = [{"id": "p2", "upvotes": 9, "downvotes": 1}]  # 10% downvotes
        sb = self._make_sb(posts)
        result = run_daily_maintenance(sb)
        assert result["posts_removed"] == 0

    def test_requires_minimum_votes(self):
        """Posts with fewer than 5 total votes are never auto-removed."""
        posts = [{"id": "p3", "upvotes": 0, "downvotes": 4}]  # 100% downvotes but only 4 total
        sb = self._make_sb(posts)
        result = run_daily_maintenance(sb)
        assert result["posts_removed"] == 0

    def test_exact_threshold_not_removed(self):
        """Exactly 40% downvotes: not removed (must be > 40%)."""
        posts = [{"id": "p4", "upvotes": 6, "downvotes": 4}]  # exactly 40%, 10 total
        sb = self._make_sb(posts)
        result = run_daily_maintenance(sb)
        assert result["posts_removed"] == 0


# ── GET /api/wisdom ────────────────────────────────────────────────────

class TestWisdomFeed:

    def _feed_posts(self):
        return [{"id": "p1", "user_id": "user-abc", "display_name": "Sage",
                 "content": "Truth is one.",
                 "contact_email": None, "contact_phone": None, "contact_hidden_at": None,
                 "upvotes": 5, "downvotes": 0, "is_edited": False,
                 "created_at": "2026-06-25T00:00:00Z", "updated_at": "2026-06-25T00:00:00Z"}]

    def test_public_feed_returns_200(self, client):
        chain = MagicMock()
        chain.table.return_value.select.return_value.eq.return_value.eq.return_value \
            .order.return_value.range.return_value.execute.return_value = MagicMock(data=self._feed_posts())
        with patch("backend.supabase_client.get_supabase", return_value=chain), \
             patch("backend.supabase_client.verify_jwt", return_value=None):
            response = client.get("/api/wisdom?page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert "posts" in data
        # user_id must not be exposed to client
        assert "user_id" not in data["posts"][0]
        assert "is_owner" in data["posts"][0]

    def test_contact_info_masked_when_hidden(self, client):
        posts = [{"id": "p1", "user_id": "user-xyz", "display_name": "Sage",
                  "content": "Truth.",
                  "contact_email": "secret@example.com", "contact_phone": "9999",
                  "contact_hidden_at": "2026-06-10T00:00:00Z",
                  "upvotes": 1, "downvotes": 0, "is_edited": False,
                  "created_at": "2026-06-01T00:00:00Z", "updated_at": "2026-06-01T00:00:00Z"}]
        chain = MagicMock()
        chain.table.return_value.select.return_value.eq.return_value.eq.return_value \
            .order.return_value.range.return_value.execute.return_value = MagicMock(data=posts)
        with patch("backend.supabase_client.get_supabase", return_value=chain), \
             patch("backend.supabase_client.verify_jwt", return_value=None):
            response = client.get("/api/wisdom")
        assert response.status_code == 200
        post = response.json()["posts"][0]
        assert post["contact_email"] is None
        assert post["contact_phone"] is None


# ── POST /api/wisdom ───────────────────────────────────────────────────

class TestCreateWisdomPost:

    def test_returns_401_without_auth(self, client):
        response = client.post("/api/wisdom", json={"content": "Hello"})
        assert response.status_code == 401

    def test_returns_400_for_empty_content(self, client):
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=MagicMock()):
            response = client.post("/api/wisdom",
                json={"content": ""},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 400

    def test_returns_400_when_no_display_name(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[])  # no profile
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.wisdom.get_post_count_today", return_value=0), \
             patch("backend.wisdom.get_mod_attempts_today", return_value=0), \
             patch("backend.wisdom.increment_mod_attempts"), \
             patch("backend.wisdom.moderate_post", return_value=(True, "approved")):
            response = client.post("/api/wisdom",
                json={"content": "Deep philosophy here"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "no_display_name"

    def test_returns_429_when_daily_post_limit_hit(self, client):
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=MagicMock()), \
             patch("backend.wisdom.get_post_count_today", return_value=50):
            response = client.post("/api/wisdom",
                json={"content": "Extra post"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 429
        assert response.json()["detail"]["error"] == "daily_post_limit"

    def test_returns_rejected_when_moderation_fails(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[{"display_name": "Sage"}])
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.wisdom.get_post_count_today", return_value=0), \
             patch("backend.wisdom.get_mod_attempts_today", return_value=0), \
             patch("backend.wisdom.increment_mod_attempts"), \
             patch("backend.wisdom.moderate_post", return_value=(False, "Political content not allowed")):
            response = client.post("/api/wisdom",
                json={"content": "Vote for me!"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"


# ── DELETE /api/wisdom/{id} ───────────────────────────────────────────

class TestDeleteWisdomPost:

    def test_returns_401_without_auth(self, client):
        response = client.delete("/api/wisdom/some-id")
        assert response.status_code == 401

    def test_returns_404_when_not_owner(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[{"user_id": "other-user"}])
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.delete("/api/wisdom/post-id",
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 404

    def test_deletes_own_post(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[{"user_id": "user-1"}])
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.delete("/api/wisdom/post-id",
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 200
        assert response.json()["ok"] is True


# ── Display name endpoints ─────────────────────────────────────────────

class TestDisplayName:

    def test_get_returns_null_when_not_set(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[])
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.get("/api/wisdom/me/display-name",
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 200
        assert response.json()["display_name"] is None

    def test_set_display_name_success(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.put("/api/wisdom/me/display-name",
                json={"display_name": "WiseSage"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 200
        assert response.json()["display_name"] == "WiseSage"

    def test_set_empty_display_name_rejected(self, client):
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=MagicMock()):
            response = client.put("/api/wisdom/me/display-name",
                json={"display_name": ""},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 400

    def test_duplicate_display_name_returns_409(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.side_effect = \
            Exception("duplicate key value violates unique constraint")
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.put("/api/wisdom/me/display-name",
                json={"display_name": "AlreadyTaken"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 409
        assert response.json()["detail"]["error"] == "name_taken"


# ── PATCH /api/wisdom/{id} ─────────────────────────────────────────────

class TestEditWisdomPost:

    def test_returns_401_without_auth(self, client):
        response = client.patch("/api/wisdom/some-id", json={"content": "Updated"})
        assert response.status_code == 401

    def test_returns_400_for_empty_content(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[{"user_id": "user-1"}])
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.wisdom.get_mod_attempts_today", return_value=0), \
             patch("backend.wisdom.increment_mod_attempts"), \
             patch("backend.wisdom.moderate_post", return_value=(True, "approved")):
            response = client.patch("/api/wisdom/post-id",
                json={"content": "   "},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 400

    def test_returns_404_when_not_owner(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[{"user_id": "other-user"}])
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.patch("/api/wisdom/post-id",
                json={"content": "Updated"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 404

    def test_edit_rejected_content_returns_rejected_not_saved(self, client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[{"user_id": "user-1"}])
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.wisdom.get_mod_attempts_today", return_value=0), \
             patch("backend.wisdom.increment_mod_attempts"), \
             patch("backend.wisdom.moderate_post", return_value=(False, "Spam content")):
            response = client.patch("/api/wisdom/post-id",
                json={"content": "Buy now!!"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        # Ensure DB update was NOT called (content not saved)
        assert not mock_sb.table.return_value.update.called


# ── POST /api/wisdom/{id}/vote ────────────────────────────────────────

class TestVoteWisdomPost:

    def test_returns_401_without_auth(self, client):
        response = client.post("/api/wisdom/some-id/vote", json={"vote": "up"})
        assert response.status_code == 401

    def test_returns_400_for_invalid_vote_direction(self, client):
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=MagicMock()):
            response = client.post("/api/wisdom/p1/vote",
                json={"vote": "sideways"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 400

    def test_upvote_calls_rpc(self, client):
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value = MagicMock(data="added")
        with patch("backend.supabase_client.verify_jwt", return_value="user-1"), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.post("/api/wisdom/p1/vote",
                json={"vote": "up"},
                headers={"Authorization": "Bearer tok"})
        assert response.status_code == 200
        assert response.json()["ok"] is True
        mock_sb.rpc.assert_called_once_with("cast_wisdom_vote",
            {"p_post_id": "p1", "p_user_id": "user-1", "p_vote": "up"})


# ── POST /api/wisdom/cron/maintenance ─────────────────────────────────

class TestWisdomCron:

    def test_returns_503_when_secret_not_configured(self, client):
        with patch.dict("os.environ", {}, clear=True), \
             patch("backend.supabase_client.get_supabase", return_value=MagicMock()):
            response = client.post("/api/wisdom/cron/maintenance",
                headers={"X-Cron-Secret": "any"})
        assert response.status_code == 503

    def test_returns_403_with_wrong_secret(self, client):
        with patch.dict("os.environ", {"CRON_SECRET": "correct-secret"}), \
             patch("backend.supabase_client.get_supabase", return_value=MagicMock()):
            response = client.post("/api/wisdom/cron/maintenance",
                headers={"X-Cron-Secret": "wrong-secret"})
        assert response.status_code == 403

    def test_returns_200_with_correct_secret(self, client):
        mock_sb = MagicMock()
        # Mock the maintenance chain
        mock_sb.table.return_value.update.return_value.is_.return_value.lt.return_value.execute.return_value = MagicMock()
        select_result = MagicMock()
        select_result.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = select_result

        with patch.dict("os.environ", {"CRON_SECRET": "my-secret"}), \
             patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            response = client.post("/api/wisdom/cron/maintenance",
                headers={"X-Cron-Secret": "my-secret"})
        assert response.status_code == 200
        assert response.json()["ok"] is True
