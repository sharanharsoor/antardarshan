"""
Wisdom Wall — LLM moderation helper and Supabase helpers.

Uses a separate Groq key (GROQ_MODERATION_KEY) for moderation so the main
Q&A budget is not affected. Falls back to GROQ_API_KEY if not set.
"""

import os
from datetime import datetime, timezone, timedelta

from groq import Groq

GROQ_MOD_KEY   = os.getenv("GROQ_MODERATION_KEY") or os.getenv("GROQ_API_KEY")
MODEL_MOD      = "llama-3.1-8b-instant"   # Free tier; moderation needs no RAG context
MAX_MOD_TOKENS = 150
MAX_POST_CHARS = 2000
MAX_POSTS_PER_DAY = 5
MAX_MOD_ATTEMPTS_PER_DAY = 5
CONTACT_HIDE_DAYS = 15
AUTOREMOVE_DAYS   = 7
AUTOREMOVE_VOTE_THRESHOLD = 0.40  # downvote ratio
AUTOREMOVE_MIN_VOTES      = 5

GUIDELINES = """
1. Content must relate to Indian philosophy, spiritual experiences, or personal growth through philosophical insight.
2. No spam, advertisements, services, or promotional content.
3. No political opinions or divisive content.
4. No harmful, offensive, or inappropriate content.
5. No personal attacks or hate speech.
6. Posts should be genuine personal reflections, spiritual experiences, or philosophical thoughts.
7. Contact info (if provided) must only be for spiritual connection purposes — no business solicitation.
"""

_mod_client = None

def _get_mod_client():
    global _mod_client
    if _mod_client is None and GROQ_MOD_KEY:
        _mod_client = Groq(api_key=GROQ_MOD_KEY)
    return _mod_client


def moderate_post(content: str) -> tuple[bool, str]:
    """
    Check a post against Wisdom Wall guidelines using Llama 8B.
    Returns (is_approved: bool, reason: str).

    INTENTIONAL FAIL-OPEN: If Groq is unavailable or returns an unclear response,
    posts are approved rather than blocked. Rationale: a brief outage should not
    prevent all Wisdom Wall submissions; the cron job auto-removes downvoted
    content, and admins can hard-delete via Supabase if needed.
    Revisit for V2 if abuse becomes a problem.
    """
    client = _get_mod_client()
    if not client:
        return True, "approved"

    system = f"""You are a content moderator for AntarDarshan, an Indian philosophy platform.
Guidelines:{GUIDELINES}
Evaluate the post. Reply ONLY with:
- APPROVED   (if it follows the guidelines)
- REJECTED: [specific reason]   (if it violates any guideline)

Be lenient with genuine spiritual content. Only reject clearly inappropriate posts."""

    try:
        resp = client.chat.completions.create(
            model=MODEL_MOD,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"Post:\n{content[:MAX_POST_CHARS]}"},
            ],
            max_tokens=MAX_MOD_TOKENS,
            temperature=0.0,
        )
        result = resp.choices[0].message.content.strip()
        if result.startswith("APPROVED"):
            return True, "approved"
        elif result.startswith("REJECTED:"):
            return False, result[9:].strip()
        return True, "approved"   # unclear → approve
    except Exception:
        return True, "approved"   # fail open


# ── Supabase helpers ──────────────────────────────────────────────────

def get_post_count_today(sb, user_id: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    result = sb.table("wisdom_posts") \
        .select("id") \
        .eq("user_id", user_id) \
        .gte("created_at", today) \
        .execute()
    return len(result.data) if result.data else 0


def get_mod_attempts_today(sb, user_id: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    row = sb.table("wisdom_mod_attempts") \
        .select("attempts") \
        .eq("user_id", user_id) \
        .eq("attempt_date", today) \
        .limit(1) \
        .execute()
    return row.data[0]["attempts"] if row.data else 0


def increment_mod_attempts(sb, user_id: str):
    today = datetime.now(timezone.utc).date().isoformat()
    # Upsert: insert or increment
    sb.rpc("increment_wisdom_mod_attempts", {
        "p_user_id": user_id,
        "p_date":    today,
    }).execute()


def run_daily_maintenance(sb):
    """
    Called by the cron endpoint or scheduled task. Idempotent.
    1. Hide contact info on posts older than CONTACT_HIDE_DAYS.
    2. Auto-remove posts exceeding downvote threshold.
    """
    now = datetime.now(timezone.utc)
    hide_before    = (now - timedelta(days=CONTACT_HIDE_DAYS)).isoformat()
    remove_before  = (now - timedelta(days=AUTOREMOVE_DAYS)).isoformat()

    # 1. Hide contact info
    sb.table("wisdom_posts") \
        .update({"contact_hidden_at": now.isoformat()}) \
        .is_("contact_hidden_at", "null") \
        .lt("created_at", hide_before) \
        .execute()

    # 2. Auto-remove high-downvote posts
    candidates = sb.table("wisdom_posts") \
        .select("id, upvotes, downvotes") \
        .eq("is_removed", False) \
        .lt("created_at", remove_before) \
        .execute()

    removed = 0
    for p in (candidates.data or []):
        total = p["upvotes"] + p["downvotes"]
        if total >= AUTOREMOVE_MIN_VOTES:
            ratio = p["downvotes"] / total
            if ratio > AUTOREMOVE_VOTE_THRESHOLD:
                sb.table("wisdom_posts").update({"is_removed": True}) \
                    .eq("id", p["id"]).execute()
                removed += 1

    return {"contact_hidden": "updated", "posts_removed": removed}
