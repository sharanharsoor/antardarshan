"""
Session management for multi-turn conversations.

Uses llm-smartmem (Memory) for token-aware context management.
Each session gets its own Memory object — token budget is respected
automatically, no manual message slicing needed.

Privacy model (from COMBINED-PLAN.md Section 13):
- Sessions live in RAM only, never written to disk or DB
- Auto-expire after 24 hours (or server restart)
- No user_id attached to sessions — anonymous by design
- SQLite logs only store mode/citations/latency (never query text)
- Reading mode bookmarks are the ONLY feature that stores user identity
  (opt-in via Supabase Auth)
"""

import time
import uuid
from collections import OrderedDict
from threading import Lock

from llmem import Memory

MAX_SESSIONS = 10_000
SESSION_TTL_SECONDS = 86_400  # 24 hours

# Max tokens passed to the LLM from conversation history.
# Leaves room for retrieved corpus context (~3K tokens) within Groq's 6K TPM.
LLM_CONTEXT_MAX_TOKENS = 3_000


class SessionStore:
    """In-memory session store with TTL and LRU eviction.

    Each session contains a llm-smartmem Memory object that handles
    token-aware context — history is trimmed to token budget automatically,
    not by a fixed message count.
    """

    def __init__(self):
        self._sessions: OrderedDict[str, dict] = OrderedDict()
        self._lock = Lock()

    def create_session(self) -> str:
        """Create a new anonymous session. Returns a 16-char hex session_id."""
        session_id = uuid.uuid4().hex[:16]
        with self._lock:
            self._evict_expired()
            self._sessions[session_id] = {
                "memory": Memory(max_tokens=LLM_CONTEXT_MAX_TOKENS),
                "created_at": time.time(),
                "last_active": time.time(),
            }
            # LRU eviction — pop oldest when over limit
            while len(self._sessions) > MAX_SESSIONS:
                self._sessions.popitem(last=False)
        return session_id

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a conversation turn to session memory (async).

        Memory handles token tracking and auto-compression internally.
        """
        memory = self._get_memory(session_id)
        if memory:
            await memory.add_async(content, role=role)

    async def get_context(
        self,
        session_id: str,
        max_tokens: int = LLM_CONTEXT_MAX_TOKENS,
    ) -> list[dict]:
        """Get token-aware conversation context for the LLM (async).

        Returns [] for new or expired sessions.
        The returned list is always within max_tokens — llm-smartmem
        truncates from oldest first if needed.
        """
        memory = self._get_memory(session_id)
        if not memory:
            return []
        return await memory.get_context_async(max_tokens=max_tokens)

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists and is not expired. Refreshes last_active on hit."""
        with self._lock:
            if session_id not in self._sessions:
                return False
            session = self._sessions[session_id]
            if time.time() - session["last_active"] > SESSION_TTL_SECONDS:
                del self._sessions[session_id]
                return False
            session["last_active"] = time.time()  # refresh TTL on access
            return True

    def delete_session(self, session_id: str) -> None:
        """Explicitly remove a session (called on 'New Conversation')."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def _get_memory(self, session_id: str) -> Memory | None:
        """Fetch the Memory object for a session, refreshing last_active.

        Returns None if the session is missing or has expired.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            if time.time() - session["last_active"] > SESSION_TTL_SECONDS:
                del self._sessions[session_id]
                return None
            session["last_active"] = time.time()
            return session["memory"]

    def _evict_expired(self) -> None:
        """Remove all TTL-expired sessions. Call inside _lock."""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s["last_active"] > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]

    @property
    def active_count(self) -> int:
        """Number of live (non-expired) sessions."""
        with self._lock:
            self._evict_expired()
            return len(self._sessions)


# Singleton — shared across the entire app lifetime
sessions = SessionStore()
