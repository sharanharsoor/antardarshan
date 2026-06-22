"""
Unit tests for SessionStore (backed by llm-smartmem Memory).

Tests: session creation, async message storage, token-aware context,
TTL expiry, LRU eviction, deletion, privacy contract, and API endpoints.
"""

import time
import pytest
from backend.sessions import SessionStore, LLM_CONTEXT_MAX_TOKENS


@pytest.fixture
def store():
    return SessionStore()


class TestSessionCreation:
    def test_creates_unique_session_ids(self, store):
        ids = {store.create_session() for _ in range(100)}
        assert len(ids) == 100

    def test_session_id_is_16_hex_chars(self, store):
        sid = store.create_session()
        assert len(sid) == 16
        int(sid, 16)  # Must be valid hex

    def test_session_exists_after_creation(self, store):
        sid = store.create_session()
        assert store.session_exists(sid) is True

    def test_nonexistent_session_does_not_exist(self, store):
        assert store.session_exists("doesnotexist1234") is False

    def test_new_session_has_empty_context(self, store):
        import asyncio
        sid = store.create_session()
        ctx = asyncio.run(store.get_context(sid))
        assert ctx == []


class TestMessageStorage:
    @pytest.mark.asyncio
    async def test_add_and_retrieve_messages(self, store):
        sid = store.create_session()
        await store.add_message(sid, "user", "What is dharma?")
        await store.add_message(sid, "assistant", "Dharma is...")
        ctx = await store.get_context(sid)
        assert len(ctx) == 2
        assert ctx[0] == {"role": "user", "content": "What is dharma?"}
        assert ctx[1] == {"role": "assistant", "content": "Dharma is..."}

    @pytest.mark.asyncio
    async def test_message_order_preserved(self, store):
        sid = store.create_session()
        for i in range(5):
            await store.add_message(sid, "user", f"Q{i}")
        ctx = await store.get_context(sid)
        contents = [m["content"] for m in ctx]
        assert contents == ["Q0", "Q1", "Q2", "Q3", "Q4"]

    @pytest.mark.asyncio
    async def test_add_to_nonexistent_session_is_safe(self, store):
        # Should not raise
        await store.add_message("fakeid1234567890", "user", "Hello")

    @pytest.mark.asyncio
    async def test_get_context_from_nonexistent_returns_empty(self, store):
        result = await store.get_context("fakeid1234567890")
        assert result == []


class TestTokenAwareContext:
    """Verify that llm-smartmem's token-based truncation works correctly.
    
    Unlike the old fixed-message-count approach, the new system truncates
    based on actual token count — smarter and respects LLM budget constraints.
    """

    @pytest.mark.asyncio
    async def test_context_respects_max_tokens(self, store):
        """Context returned never exceeds the requested token budget."""
        from llmem.utils.tokens import count_message_tokens
        sid = store.create_session()
        # Add a lot of content
        for i in range(20):
            await store.add_message(sid, "user", f"Question number {i} about karma and dharma and the nature of the soul according to Indian philosophy")
            await store.add_message(sid, "assistant", f"Answer {i}: The nature of karma as described in the Bhagavad Gita chapter 2 verse 47 teaches...")

        ctx = await store.get_context(sid, max_tokens=LLM_CONTEXT_MAX_TOKENS)
        token_count = count_message_tokens(ctx)
        assert token_count <= LLM_CONTEXT_MAX_TOKENS

    @pytest.mark.asyncio
    async def test_context_keeps_most_recent_turns(self, store):
        """When truncating, recent turns are preserved over older ones."""
        sid = store.create_session()
        for i in range(30):
            await store.add_message(sid, "user", f"Old question {i} " * 50)  # bulky
        # Add one short, distinctive recent message
        await store.add_message(sid, "user", "MOST_RECENT_QUERY")
        ctx = await store.get_context(sid, max_tokens=200)
        contents = [m["content"] for m in ctx]
        assert "MOST_RECENT_QUERY" in contents, "Most recent message must survive truncation"

    @pytest.mark.asyncio
    async def test_context_returns_list_of_role_content_dicts(self, store):
        """Output format must be [{role, content}, ...] for Groq API compatibility."""
        sid = store.create_session()
        await store.add_message(sid, "user", "Hello")
        ctx = await store.get_context(sid)
        assert isinstance(ctx, list)
        for msg in ctx:
            assert "role" in msg
            assert "content" in msg
            assert set(msg.keys()) == {"role", "content"}


class TestTTLExpiry:
    def test_expired_session_is_not_found(self, store):
        sid = store.create_session()
        store._sessions[sid]["last_active"] = time.time() - 90000  # 25h ago
        assert store.session_exists(sid) is False

    @pytest.mark.asyncio
    async def test_expired_session_returns_empty_context(self, store):
        sid = store.create_session()
        await store.add_message(sid, "user", "Hello")
        store._sessions[sid]["last_active"] = time.time() - 90000
        ctx = await store.get_context(sid)
        assert ctx == []

    def test_active_access_refreshes_last_active(self, store):
        sid = store.create_session()
        original = store._sessions[sid]["last_active"]
        time.sleep(0.01)
        store.session_exists(sid)  # Any access refreshes TTL
        assert store._sessions[sid]["last_active"] >= original


class TestDeletion:
    def test_delete_removes_session(self, store):
        sid = store.create_session()
        store.delete_session(sid)
        assert store.session_exists(sid) is False

    def test_delete_nonexistent_is_safe(self, store):
        store.delete_session("doesnotexist1234")  # Must not raise

    @pytest.mark.asyncio
    async def test_context_empty_after_delete(self, store):
        sid = store.create_session()
        await store.add_message(sid, "user", "Hello")
        store.delete_session(sid)
        ctx = await store.get_context(sid)
        assert ctx == []


class TestLRUEviction:
    def test_active_count_is_accurate(self, store):
        initial = store.active_count
        s1 = store.create_session()
        s2 = store.create_session()
        assert store.active_count == initial + 2
        store.delete_session(s1)
        assert store.active_count == initial + 1

    def test_evicts_when_over_max(self):
        import backend.sessions as sm
        original = sm.MAX_SESSIONS
        sm.MAX_SESSIONS = 3
        try:
            small_store = SessionStore()
            for _ in range(5):
                small_store.create_session()
            assert small_store.active_count <= 3
        finally:
            sm.MAX_SESSIONS = original


class TestPrivacyContract:
    def test_sessions_have_no_user_id_field(self, store):
        """No user identity must ever be attached to a Q&A session."""
        sid = store.create_session()
        session_data = store._sessions[sid]
        assert "user_id" not in session_data
        assert "ip" not in session_data
        assert "email" not in session_data

    @pytest.mark.asyncio
    async def test_context_messages_have_only_role_and_content(self, store):
        """Output must only contain role+content — no user identity fields."""
        sid = store.create_session()
        await store.add_message(sid, "user", "What is karma?")
        ctx = await store.get_context(sid)
        assert len(ctx) == 1
        assert set(ctx[0].keys()) == {"role", "content"}

    def test_session_backed_by_memory_object(self, store):
        """Each session must use a llm-smartmem Memory object, not a plain list."""
        from llmem import Memory
        sid = store.create_session()
        memory = store._sessions[sid]["memory"]
        assert isinstance(memory, Memory)


class TestAPIEndpoints:
    def test_delete_session_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        from unittest.mock import patch

        with TestClient(app) as client:
            with (
                patch("backend.rag_query.search", return_value=[]),
                patch("backend.llm.generate_response", return_value=("Test answer", None, "llama-3.1-8b-instant", 100)),
                patch("backend.supabase_client.verify_jwt", return_value=None),
            ):
                r = client.post("/api/query", json={"query": "What is dharma?"})
                assert r.status_code == 200
                session_id = r.json().get("session_id")
                assert session_id is not None

                r = client.delete(f"/api/session/{session_id}")
                assert r.status_code == 200
                assert r.json()["cleared"] is True

    def test_delete_nonexistent_session_is_safe(self):
        from fastapi.testclient import TestClient
        from backend.app import app

        with TestClient(app) as client:
            r = client.delete("/api/session/doesnotexist1234")
            assert r.status_code == 200

    def test_health_includes_active_session_count(self):
        from fastapi.testclient import TestClient
        from backend.app import app

        with TestClient(app) as client:
            r = client.get("/api/health")
            data = r.json()
            assert "active_sessions" in data
            assert isinstance(data["active_sessions"], int)

    def test_session_id_returned_on_first_query(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        from unittest.mock import patch

        with TestClient(app) as client:
            with (
                patch("backend.rag_query.search", return_value=[]),
                patch("backend.llm.generate_response", return_value=("Test answer", None, "llama-3.1-8b-instant", 100)),
                patch("backend.supabase_client.verify_jwt", return_value=None),
            ):
                r = client.post("/api/query", json={"query": "What is consciousness?"})
                data = r.json()
                assert "session_id" in data
                assert len(data["session_id"]) == 16
