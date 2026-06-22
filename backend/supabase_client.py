"""
Supabase service-role client for backend operations.

Uses the SERVICE_ROLE key — bypasses RLS.
NEVER expose this key to the frontend.

Responsibilities:
- Persist conversation messages after LLM generation
- Track per-user query counts for daily quota
- Auto-title conversations from first message
- Verify per-user quota before allowing queries
"""

import os
import re
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

_supabase = None


def get_supabase():
    """Lazy singleton — connects on first call."""
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            return None  # Supabase not configured — graceful degradation
        from supabase import create_client
        _supabase = create_client(url, key)
    return _supabase


def verify_jwt(authorization: str | None) -> str | None:
    """
    Verify a Supabase JWT from the Authorization header.
    Returns the authenticated user_id (UUID string) or None if invalid/missing.

    Usage in endpoints:
        user_id = verify_jwt(request.headers.get("Authorization"))

    The frontend sends: Authorization: Bearer <supabase_access_token>
    Supabase validates the token server-side — no secret needed in our code.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None
    sb = get_supabase()
    if not sb:
        return None
    try:
        result = sb.auth.get_user(token)
        return result.user.id if result.user else None
    except Exception:
        return None


# ── Quota ─────────────────────────────────────────────────────────────────────

PER_USER_DAILY_LIMIT = 50


def get_user_queries_today(user_id: str) -> int:
    """Count queries made by this user today (UTC). Returns 0 if Supabase unavailable."""
    sb = get_supabase()
    if not sb or not user_id:
        return 0
    try:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = sb.table("user_query_log").select("id", count="exact").eq(
            "user_id", user_id
        ).gte("queried_at", f"{today}T00:00:00Z").execute()
        return result.count or 0
    except Exception as e:
        print(f"  Supabase quota check error: {e}")
        return 0


def check_user_quota(user_id: str) -> tuple[bool, int, int]:
    """
    Returns (allowed, used, remaining).
    allowed=True means the user can make another query.
    """
    used = get_user_queries_today(user_id)
    remaining = max(0, PER_USER_DAILY_LIMIT - used)
    return remaining > 0, used, remaining


def log_user_query(user_id: str, conversation_id: str | None, mode: str, model: str):
    """Record a query in the per-user log. Non-blocking — errors are swallowed."""
    sb = get_supabase()
    if not sb or not user_id:
        return
    try:
        sb.table("user_query_log").insert({
            "user_id": user_id,
            "conversation_id": conversation_id,
            "mode": mode,
            "model": model,
        }).execute()
    except Exception as e:
        print(f"  Supabase query log error (non-critical): {e}")


# ── Conversations ──────────────────────────────────────────────────────────────

def _auto_title(text: str, max_len: int = 60) -> str:
    """Generate a conversation title from the first user message."""
    # Strip question mark, truncate cleanly at word boundary
    title = text.strip().rstrip("?").strip()
    if len(title) <= max_len:
        return title
    # Truncate at last space before max_len
    truncated = title[:max_len]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] if last_space > 0 else truncated) + "…"


def ensure_conversation(conversation_id: str | None, user_id: str | None) -> str | None:
    """
    Validate or create a conversation the caller is allowed to write to.

    Rules:
    - conversation_id provided + user_id provided:
        Verify the conversation exists AND is owned by user_id.
        If not owned → return None (caller should not write).
    - conversation_id provided + no user_id:
        Reject — unauthenticated writes to existing conversations are not allowed.
    - no conversation_id + user_id:
        Create a new conversation owned by user_id.
    - no conversation_id + no user_id:
        Return None — anonymous queries don't get persistent conversations.

    Returns the conversation_id to use for persistence, or None to skip persistence.
    """
    sb = get_supabase()
    if not sb:
        return None  # fail-closed: skip persistence if Supabase unavailable

    if conversation_id:
        if not user_id:
            # Unauthenticated request must not write to existing conversations
            return None
        try:
            result = sb.table("conversations").select("id, user_id").eq(
                "id", conversation_id
            ).execute()
            if not result.data:
                return None  # conversation doesn't exist
            owner = result.data[0].get("user_id")
            if owner != user_id:
                # Caller doesn't own this conversation — write denied
                print(f"  Conversation write denied: user {user_id} tried to write to {conversation_id} (owner: {owner})")
                return None
            return conversation_id
        except Exception as e:
            print(f"  Supabase ensure_conversation error: {e}")
            return None

    # No conversation_id — create a new one if authenticated
    if not user_id:
        return None  # anonymous queries don't get persisted

    try:
        result = sb.table("conversations").insert(
            {"user_id": user_id, "shared": False}
        ).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        print(f"  Supabase create conversation error: {e}")
        return None


def persist_messages(
    conversation_id: str,
    user_message: str,
    assistant_message: str,
    citations: list[dict],
    mode: str,
    model: str,
    tokens_used: int,
    is_first_message: bool = False,
) -> tuple[bool, str | None]:
    """
    Persist user + assistant messages to Supabase.
    Returns (success, assistant_message_id) — message_id enables per-answer feedback.
    """
    sb = get_supabase()
    if not sb or not conversation_id:
        return False, None

    try:
        sb.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "user",
            "content": user_message,
        }).execute()

        asst_result = sb.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": assistant_message,
            "citations": citations,
            "mode": mode,
            "model": model,
            "tokens_used": tokens_used,
        }).execute()

        assistant_message_id = (
            asst_result.data[0]["id"] if asst_result.data else None
        )

        if is_first_message:
            title = _auto_title(user_message)
            sb.table("conversations").update({"title": title}).eq(
                "id", conversation_id
            ).execute()

        return True, assistant_message_id

    except Exception as e:
        print(f"  Supabase message persist error (non-critical): {e}")
        return False, None


def get_conversation(conversation_id: str) -> dict | None:
    """Load a conversation + its messages. Returns None if not found."""
    sb = get_supabase()
    if not sb:
        return None
    try:
        conv_result = sb.table("conversations").select("*").eq(
            "id", conversation_id
        ).execute()
        if not conv_result.data:
            return None
        conv = conv_result.data[0]

        msg_result = sb.table("messages").select("*").eq(
            "conversation_id", conversation_id
        ).order("created_at").execute()

        return {"conversation": conv, "messages": msg_result.data or []}
    except Exception as e:
        print(f"  Supabase get conversation error: {e}")
        return None


def list_conversations(user_id: str, limit: int = 30, offset: int = 0) -> list[dict]:
    """List a user's conversations, newest first."""
    sb = get_supabase()
    if not sb or not user_id:
        return []
    try:
        result = sb.table("conversations").select(
            "id, title, shared, created_at, updated_at"
        ).eq("user_id", user_id).order(
            "updated_at", desc=True
        ).range(offset, offset + limit - 1).execute()
        return result.data or []
    except Exception as e:
        print(f"  Supabase list conversations error: {e}")
        return []


def update_conversation(conversation_id: str, user_id: str, updates: dict) -> bool:
    """Update conversation title or shared flag. Returns True only if a row was actually changed."""
    sb = get_supabase()
    if not sb:
        return False
    allowed_fields = {"title", "shared"}
    safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
    if not safe_updates:
        return False
    try:
        result = sb.table("conversations").update(safe_updates).eq(
            "id", conversation_id
        ).eq("user_id", user_id).execute()
        # Supabase returns updated rows — empty means no match (wrong owner or missing)
        return bool(result.data)
    except Exception as e:
        print(f"  Supabase update conversation error: {e}")
        return False


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """Delete a conversation (cascades to messages). Returns True only if a row was deleted."""
    sb = get_supabase()
    if not sb:
        return False
    try:
        result = sb.table("conversations").delete().eq(
            "id", conversation_id
        ).eq("user_id", user_id).execute()
        # Supabase returns deleted rows — empty means no match (wrong owner or missing)
        return bool(result.data)
    except Exception as e:
        print(f"  Supabase delete conversation error: {e}")
        return False
