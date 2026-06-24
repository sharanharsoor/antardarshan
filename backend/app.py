"""
AntarDarshan — FastAPI Backend

Endpoints:
- POST /api/query        → RAG Q&A (anonymous)
- GET  /api/library      → list available scriptures
- GET  /api/library/{scripture}/{chapter}  → verses in a chapter
- POST /api/explain      → explain a specific verse (for reading mode)
- GET  /api/health       → health check

Run: uvicorn backend.app:app --reload --port 8000
"""

import os
import time
import json
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

CORPUS_PROCESSED = Path(__file__).parent.parent / "corpus" / "processed"
DB_PATH = Path(__file__).parent.parent / "data" / "query_logs.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load model, connect Qdrant, build corpus index."""
    from backend.rag_query import _get_model, _get_client
    from backend.corpus_index import CorpusIndex
    print("Loading embedding model...")
    _get_model()
    print("Connecting to Qdrant...")
    _get_client()
    print("Building corpus index...")
    app.state.corpus = CorpusIndex(CORPUS_PROCESSED)
    _init_db()
    print("AntarDarshan backend ready.")
    yield
    # Shutdown: flush LangFuse queue so last traces aren't lost
    from backend.llm import _get_langfuse
    lf = _get_langfuse()
    if lf:
        lf.flush()


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AntarDarshan API",
    description="Indian Philosophy AI — citation-grounded answers from ancient texts",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten to explicit origins when frontend is deployed
    allow_credentials=False,  # Cannot be True with origins=["*"] — browsers reject it
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)
    session_id: str | None = None
    conversation_id: str | None = None
    log_content: bool = False  # privacy-safe default: only operational metrics logged, no Q&A text
    # user_id intentionally omitted — derived server-side from JWT Authorization header


class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    shared: bool | None = None

class ExplainRequest(BaseModel):
    scripture: str
    chapter: int
    verse: int

class QueryResponse(BaseModel):
    answer: str
    mode: str
    citations: list[dict]
    latency_ms: int
    session_id: str
    trace_id: str | None = None
    model: str | None = None
    tokens_used: int | None = None
    conversation_id: str | None = None
    conversation_saved: bool = False
    message_id: str | None = None         # Supabase ID of the assistant message (for feedback)


class FeedbackRequest(BaseModel):
    trace_id: str | None = None
    rating: int
    comment: str | None = None
    mode: str | None = None
    conversation_id: str | None = None  # for Supabase feedback_responses
    message_id: str | None = None       # for Supabase feedback_responses


# --- DB ---

def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text TEXT DEFAULT NULL,
            response_summary TEXT,
            citations_used TEXT,
            mode TEXT,
            model_used TEXT,
            latency_ms INTEGER,
            thumbs_rating INTEGER,
            tradition_detected TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _log_query(mode: str, citations: list, latency_ms: int, tradition: str = None):
    """Log anonymous analytics only. NEVER stores query text (privacy decision, Section 13)."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO query_logs (citations_used, mode, latency_ms, tradition_detected) VALUES (?, ?, ?, ?)",
            (json.dumps(citations), mode, latency_ms, tradition),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# --- Endpoints ---

@app.get("/api/daily-wisdom")
async def daily_wisdom(request: Request):
    """
    Returns one verse deterministically selected by today's UTC date.
    Same verse all day, changes every midnight UTC — zero LLM cost.
    Only picks from the readable (clean-text) corpus.
    """
    import hashlib
    from datetime import datetime, timezone

    corpus = request.app.state.corpus
    readable = corpus.list_scriptures(readable_only=True)

    # Collect all chunks from readable scriptures
    all_chunks = []
    for meta in readable:
        scripture = meta["scripture"]
        chapters = {
            ch for (s, ch) in corpus.chapters.keys() if s == scripture
        }
        for ch in chapters:
            all_chunks.extend(corpus.chapters[(scripture, ch)])

    if not all_chunks:
        return {"error": "No corpus available"}

    # Filter to display-ready chunks:
    # - Complete sentences (no truncation needed)
    # - No OCR footnote markers like [FN#l6]
    # - Short enough to display fully in the card (≤ 350 chars)
    # - Long enough to be meaningful (≥ 60 chars)
    import re
    OCR_JUNK = re.compile(r'\[FN|footnote|\[f\.|^\s*\d+\s*$', re.IGNORECASE)

    display_chunks = [
        c for c in all_chunks
        if 60 <= len(c["text"]) <= 350
        and not OCR_JUNK.search(c["text"])
    ]

    # Fall back to all chunks if filter is too aggressive
    candidate_pool = display_chunks if len(display_chunks) > 100 else all_chunks

    # Deterministic daily selection: sha256(YYYY-MM-DD) → stable index
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest = hashlib.sha256(today.encode()).hexdigest()
    idx = int(digest, 16) % len(candidate_pool)
    chunk = candidate_pool[idx]

    text = chunk["text"].strip()

    tradition_colors = {
        "hindu_vedanta": "vedanta",
        "hindu_yoga": "yoga",
        "buddhist": "buddhist",
        "sant_bhakti": "bhakti",
        "jain": "jain",
    }

    # Build slug for linking to the reading page
    import re as _re
    slug = _re.sub(r"[^a-z0-9]+", "-", chunk["scripture"].lower()).strip("-")

    return {
        "text": text,
        "scripture": chunk["scripture"],
        "slug": slug,
        "chapter": chunk["chapter"],
        "verse": chunk["verse"],
        "translator": chunk["translator"],
        "year": chunk["year"],
        "tradition": chunk["tradition"],
        "tradition_color": tradition_colors.get(chunk["tradition"], "vedanta"),
        "date": today,
    }


@app.get("/api/health")
async def health():
    from backend.sessions import sessions
    return {
        "status": "ok",
        "service": "antardarshan",
        "version": "0.1.0",
        "active_sessions": sessions.active_count,
    }


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    """Explicitly clear a conversation session. Client calls this on 'New Conversation'."""
    from backend.sessions import sessions
    sessions.delete_session(session_id)
    return {"cleared": True, "session_id": session_id}


@app.post("/api/query", response_model=QueryResponse)
@limiter.limit("60/hour")
async def query_endpoint(request: Request, req: QueryRequest):
    """Main RAG Q&A endpoint (anonymous, multi-turn via session_id)."""
    from backend.rag_query import search, detect_mode
    from backend.llm import generate_response
    from backend.sessions import sessions

    start = time.time()

    # ── Quota checks — BEFORE RAG/LLM (save CPU/cost for over-quota users) ──
    from backend.supabase_client import check_user_quota, log_user_query, persist_messages, ensure_conversation, verify_jwt
    from fastapi import HTTPException
    from datetime import datetime, timezone as _tz

    # 1. Global org-level daily limit (SQLite)
    GLOBAL_DAILY_LIMIT = 15_400
    try:
        _conn = sqlite3.connect(str(DB_PATH))
        _today = datetime.now(_tz.utc).strftime("%Y-%m-%d")
        _row = _conn.execute(
            "SELECT COUNT(*) FROM query_logs WHERE DATE(created_at) = ?", (_today,)
        ).fetchone()
        _conn.close()
        _global_used = _row[0] if _row else 0
    except Exception:
        _global_used = 0

    if _global_used >= GLOBAL_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "global_limit_reached",
                "used": _global_used,
                "limit": GLOBAL_DAILY_LIMIT,
                "message": "Daily query limit reached. Come back tomorrow.",
            },
        )

    # 2. Per-user daily limit (Supabase)
    user_id = verify_jwt(request.headers.get("Authorization"))
    if user_id:
        allowed, used, remaining = check_user_quota(user_id)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "daily_limit_reached",
                    "used": used,
                    "limit": 50,
                    "message": "You've used today's 50 queries. Resets at midnight UTC.",
                },
            )

    # Session management: create or reuse
    session_id = req.session_id
    if not session_id or not sessions.session_exists(session_id):
        session_id = sessions.create_session()

    # Token-aware context via llm-smartmem — stays within Groq TPM budget
    history = await sessions.get_context(session_id)

    mode = detect_mode(req.query)
    hits = search(req.query, top_k=req.top_k)
    use_deep = (mode in ("comparison", "well_being"))

    answer, trace_id, model_used, tokens_used = generate_response(
        req.query, hits, mode=mode, use_deep_model=use_deep,
        conversation_history=history if history else None,
        log_content=req.log_content,
    )
    latency_ms = int((time.time() - start) * 1000)

    # Store turns in session memory — llm-smartmem handles token tracking
    await sessions.add_message(session_id, "user", req.query)
    await sessions.add_message(session_id, "assistant", answer)

    # Tag each citation with readable=True/False so the frontend knows
    # whether to show it as a clickable link (readable library) or plain text
    # (RAG-only OCR sources that would lead to "could not load" errors).
    try:
        readable_scriptures = {
            s["scripture"] for s in request.app.state.corpus.list_scriptures(readable_only=True)
        }
    except AttributeError:
        readable_scriptures = set()  # corpus not initialized (e.g. in tests) — treat all as readable
    citations = [
        {
            "scripture": h["scripture"],
            "chapter": h["chapter"],
            "verse": h["verse"],
            "translator": h["translator"],
            "readable": h["scripture"] in readable_scriptures if readable_scriptures else True,
        }
        for h in hits
    ]

    tradition = hits[0]["tradition"] if hits else None
    _log_query(mode, citations, latency_ms, tradition)

    # ── Supabase persistence ──────────────────────────────────────────────
    conversation_id = req.conversation_id
    conversation_saved = False
    assistant_message_id: str | None = None

    if conversation_id or user_id:
        # Validates ownership if conversation_id provided; creates new if not.
        # Returns None if caller doesn't own the conversation (IDOR protection).
        conversation_id = ensure_conversation(conversation_id, user_id)

    if conversation_id:
        from backend.supabase_client import get_conversation
        existing = get_conversation(conversation_id)
        is_first = not existing or len(existing.get("messages", [])) == 0

        conversation_saved, assistant_message_id = persist_messages(
            conversation_id=conversation_id,
            user_message=req.query,
            assistant_message=answer,
            citations=citations,
            mode=mode,
            model=model_used or "",
            tokens_used=tokens_used or 0,
            is_first_message=is_first,
        )

    # Log per-user query count
    if user_id:
        log_user_query(user_id, conversation_id, mode, model_used or "")

    return QueryResponse(
        answer=answer, mode=mode, citations=citations,
        latency_ms=latency_ms, session_id=session_id,
        trace_id=trace_id, model=model_used, tokens_used=tokens_used,
        conversation_id=conversation_id,
        conversation_saved=conversation_saved,
        message_id=assistant_message_id if conversation_saved else None,
    )


@app.get("/api/stats")
async def corpus_stats(request: Request):
    """Full corpus statistics — total texts and chunks across all sources,
    including those indexed for RAG but not shown in the reading library."""
    corpus = request.app.state.corpus
    all_scriptures = corpus.list_scriptures(readable_only=False)
    readable = corpus.list_scriptures(readable_only=True)
    total_chunks = sum(s["total_verses"] for s in all_scriptures)
    readable_chunks = sum(s["total_verses"] for s in readable)
    return {
        "total_texts": len(all_scriptures),
        "readable_texts": len(readable),
        "rag_only_texts": len(all_scriptures) - len(readable),
        "total_chunks": total_chunks,
        "readable_chunks": readable_chunks,
    }


@app.get("/api/library")
async def list_library(request: Request, all: bool = False):
    """List scriptures in the reading library (clean text only by default).

    ?all=true returns everything including OCR-quality texts (useful for RAG debugging).
    """
    return {"scriptures": request.app.state.corpus.list_scriptures(readable_only=not all)}


@app.get("/api/library/{scripture}")
async def get_scripture_detail(request: Request, scripture: str):
    """Get scripture metadata + chapter list (table of contents). Accepts slug or full name."""
    corpus = request.app.state.corpus
    # Try as slug first, then as direct name
    resolved = corpus.resolve_slug(scripture) or scripture
    detail = corpus.get_scripture_detail(resolved)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Scripture '{scripture}' not found")
    return detail


@app.get("/api/library/{scripture}/{chapter}")
async def get_chapter(request: Request, scripture: str, chapter: int):
    """Get all verses for a specific scripture and chapter. Accepts slug or full name."""
    corpus = request.app.state.corpus
    resolved = corpus.resolve_slug(scripture) or scripture
    verses = corpus.get_chapter(resolved, chapter)
    if not verses:
        raise HTTPException(status_code=404, detail=f"Scripture '{scripture}' chapter {chapter} not found")
    return {"scripture": resolved, "chapter": chapter, "verses": verses}


@app.get("/api/library/{scripture}/{chapter}/{verse}")
async def get_verse_detail(request: Request, scripture: str, chapter: int, verse: int):
    """Get a single verse + surrounding context. For reading mode deep-links."""
    corpus = request.app.state.corpus
    resolved = corpus.resolve_slug(scripture) or scripture
    v = corpus.get_verse(resolved, chapter, verse)
    if not v:
        raise HTTPException(status_code=404, detail=f"{scripture} {chapter}.{verse} not found")
    context = corpus.get_context(resolved, chapter, verse, window=2)
    return {"verse": v, "context_verses": context}


@app.get("/api/quota-status")
async def quota_status():
    """Global query availability status. Frontend shows green/yellow/red dot."""
    from datetime import timezone, datetime
    daily_limit = 15_400  # 14,400 simple + 1,000 deep

    try:
        conn = sqlite3.connect(str(DB_PATH))
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) FROM query_logs WHERE DATE(created_at) = ?", (today_utc,)
        ).fetchone()
        conn.close()
        queries_today = row[0] if row else 0
    except Exception:
        queries_today = 0

    if queries_today >= daily_limit:
        status = "exhausted"
    elif queries_today >= daily_limit * 0.8:
        status = "limited"
    else:
        status = "available"

    return {"status": status, "queries_today": queries_today, "daily_limit": daily_limit}


@app.get("/api/quota-status/user")
async def user_quota_status(request: Request):
    """Per-user query quota — user identity derived from JWT."""
    from backend.supabase_client import check_user_quota, PER_USER_DAILY_LIMIT, verify_jwt
    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        return {"per_user_used": None, "per_user_limit": None, "per_user_remaining": None}
    allowed, used, remaining = check_user_quota(user_id)
    return {
        "per_user_used": used,
        "per_user_limit": PER_USER_DAILY_LIMIT,
        "per_user_remaining": remaining,
        "per_user_allowed": allowed,
    }


# ── Conversation CRUD ──────────────────────────────────────────────────────────

@app.get("/api/conversations")
async def list_user_conversations(request: Request, limit: int = 30, offset: int = 0):
    """List the authenticated user's conversations, newest first."""
    from backend.supabase_client import list_conversations, verify_jwt
    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    convs = list_conversations(user_id, limit=limit, offset=offset)
    return {"conversations": convs, "total": len(convs)}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation_detail(request: Request, conversation_id: str):
    """
    Load a conversation + all its messages.
    Access rules: owner (any auth) OR shared=true (no auth needed).
    Private conversations return 404 to non-owners (don't leak existence).
    """
    from backend.supabase_client import get_conversation, verify_jwt
    from fastapi import HTTPException

    data = get_conversation(conversation_id)
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv = data["conversation"]
    user_id = verify_jwt(request.headers.get("Authorization"))
    is_owner = user_id and user_id == conv.get("user_id")
    is_shared = conv.get("shared", False)

    if not is_owner and not is_shared:
        # Return 404 not 403 — don't reveal that the conversation exists
        raise HTTPException(status_code=404, detail="Conversation not found")

    return data


@app.patch("/api/conversations/{conversation_id}")
@limiter.limit("60/hour")
async def update_conversation_endpoint(request: Request, conversation_id: str, req: ConversationUpdateRequest):
    """Update conversation title or shared flag. Requires valid JWT."""
    from backend.supabase_client import update_conversation, verify_jwt
    from fastapi import HTTPException
    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    updates = {}
    if req.title is not None:
        updates["title"] = req.title
    if req.shared is not None:
        updates["shared"] = req.shared
    success = update_conversation(conversation_id, user_id, updates)
    return {"ok": success}


@app.delete("/api/conversations/{conversation_id}")
@limiter.limit("60/hour")
async def delete_conversation_endpoint(request: Request, conversation_id: str):
    """Delete a conversation and all its messages. Requires valid JWT."""
    from backend.supabase_client import delete_conversation, verify_jwt
    from fastapi import HTTPException
    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    success = delete_conversation(conversation_id, user_id)
    return {"ok": success}


@app.delete("/api/query-log")
@limiter.limit("10/hour")
async def delete_query_log(request: Request):
    """
    Delete all query-log entries for the authenticated user.
    This removes activity metadata (mode, model, timestamp) kept for quota.
    Does NOT affect conversations or messages — those are deleted separately.
    Requires valid JWT.
    """
    from backend.supabase_client import get_supabase, verify_jwt
    from fastapi import HTTPException
    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        result = sb.table("user_query_log").delete().eq("user_id", user_id).execute()
        deleted = len(result.data) if result.data else 0
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not clear query log: {e}")


@app.post("/api/feedback")
@limiter.limit("120/hour")
async def submit_feedback(request: Request, req: FeedbackRequest):
    """
    Record user feedback (thumbs up/down) on an AI response.
    Triple-write: LangFuse (observability) + SQLite (analytics) + Supabase (user history).
    """
    if req.rating not in (1, -1):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="rating must be 1 or -1")

    # 1. Score the LangFuse trace
    if req.trace_id:
        from backend.llm import score_trace
        # Derive log_content from server env ceiling — feedback comment is PII-adjacent
        _log_content_allowed = os.getenv("LANGFUSE_LOG_CONTENT", "false").lower() == "true"
        score_trace(req.trace_id, req.rating, req.comment, log_content=_log_content_allowed)

    # 2. SQLite for local analytics (feedback_log created lazily if needed)
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT,
                rating INTEGER,
                mode TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "INSERT INTO feedback_log (trace_id, rating, mode) VALUES (?, ?, ?)",
            (req.trace_id, req.rating, req.mode),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  Feedback SQLite error (non-critical): {e}")

    # 3. Supabase — ties feedback to the exact user + conversation + message
    from backend.supabase_client import get_supabase, verify_jwt
    user_id = verify_jwt(request.headers.get("Authorization"))
    sb = get_supabase()
    if sb and user_id:
        try:
            # 1. Verify conversation belongs to this user
            verified_conv_id = None
            if req.conversation_id:
                conv_check = sb.table("conversations").select("id").eq(
                    "id", req.conversation_id
                ).eq("user_id", user_id).execute()
                if conv_check.data:
                    verified_conv_id = req.conversation_id

            # 2. Verify message belongs to the verified conversation
            verified_msg_id = None
            if req.message_id and verified_conv_id:
                msg_check = sb.table("messages").select("id").eq(
                    "id", req.message_id
                ).eq("conversation_id", verified_conv_id).execute()
                if msg_check.data:
                    verified_msg_id = req.message_id

            sb.table("feedback_responses").insert({
                "user_id": user_id,
                "conversation_id": verified_conv_id,
                "message_id": verified_msg_id,
                "rating": req.rating,
                "comment": req.comment,
            }).execute()
        except Exception as e:
            print(f"  Feedback Supabase error (non-critical): {e}")

    return {"ok": True}


@app.post("/api/query/stream")
@limiter.limit("60/hour")
async def query_endpoint_stream(request: Request, req: QueryRequest):
    """
    Streaming Q&A endpoint — tokens arrive one by one (SSE).
    Final event contains citations, conversation_id, trace_id.

    Event format:
        data: {"type": "token", "content": "..."}   ← each LLM token
        data: {"type": "done", "citations": [...], "conversation_id": "...", ...}
        data: [DONE]  ← stream end sentinel
    """
    import json as _json
    from backend.rag_query import search, detect_mode
    from backend.llm import generate_response_stream

    # ── Quota checks (same as non-streaming endpoint) ─────────────────────────
    GLOBAL_DAILY_LIMIT = 15_400
    try:
        _conn2 = sqlite3.connect(str(DB_PATH))
        _today2 = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
        _row2 = _conn2.execute("SELECT COUNT(*) FROM query_logs WHERE DATE(created_at) = ?", (_today2,)).fetchone()
        _conn2.close()
        _global_used2 = _row2[0] if _row2 else 0
    except Exception:
        _global_used2 = 0

    if _global_used2 >= GLOBAL_DAILY_LIMIT:
        return JSONResponse(status_code=429, content={"detail": {
            "error": "global_limit_reached", "limit": GLOBAL_DAILY_LIMIT,
            "message": "Daily query limit reached. Come back tomorrow.",
        }})

    from backend.supabase_client import check_user_quota, log_user_query, persist_messages, ensure_conversation, verify_jwt, get_conversation
    from backend.sessions import sessions
    stream_user_id = verify_jwt(request.headers.get("Authorization"))
    if stream_user_id:
        allowed, _, _ = check_user_quota(stream_user_id)
        if not allowed:
            return JSONResponse(status_code=429, content={"detail": {
                "error": "daily_limit_reached", "limit": 50,
                "message": "You've used today's 50 queries. Resets at midnight UTC.",
            }})

    # ── RAG retrieval (blocking, before stream starts) ────────────────────────
    stream_start_time = time.time()
    session_id = req.session_id
    if not session_id or not sessions.session_exists(session_id):
        session_id = sessions.create_session()

    history = await sessions.get_context(session_id)
    mode = detect_mode(req.query)
    hits = search(req.query, top_k=req.top_k)
    use_deep = mode in ("comparison", "well_being")

    try:
        readable_scriptures = {s["scripture"] for s in request.app.state.corpus.list_scriptures(readable_only=True)}
    except AttributeError:
        readable_scriptures = set()
    citations = [
        {"scripture": h["scripture"], "chapter": h["chapter"], "verse": h["verse"],
         "translator": h["translator"], "readable": h["scripture"] in readable_scriptures if readable_scriptures else True}
        for h in hits
    ]

    async def event_stream():
        gen = generate_response_stream(
            req.query, hits, mode=mode, use_deep_model=use_deep,
            conversation_history=history if history else None,
            log_content=req.log_content,
        )
        answer_parts = []
        trace_id = None
        model_used = None
        tokens_used = 0

        try:
            while True:
                token = next(gen)
                answer_parts.append(token)
                yield f"data: {_json.dumps({'type': 'token', 'content': token})}\n\n"
        except StopIteration as e:
            if e.value:
                trace_id, model_used, tokens_used = e.value

        answer = "".join(answer_parts)

        # Post-stream: persist, log
        await sessions.add_message(session_id, "user", req.query)
        await sessions.add_message(session_id, "assistant", answer)

        conv_id = req.conversation_id
        conv_saved = False
        msg_id = None
        if conv_id or stream_user_id:
            conv_id = ensure_conversation(conv_id, stream_user_id)
        if conv_id:
            existing = get_conversation(conv_id)
            is_first = not existing or len(existing.get("messages", [])) == 0
            conv_saved, msg_id = persist_messages(
                conversation_id=conv_id, user_message=req.query,
                assistant_message=answer, citations=citations, mode=mode,
                model=model_used or "", tokens_used=tokens_used, is_first_message=is_first,
            )
        if stream_user_id:
            log_user_query(stream_user_id, conv_id, mode, model_used or "")

        _log_query(mode, citations, int((time.time() - stream_start_time) * 1000), hits[0]["tradition"] if hits else None)

        # Final metadata event
        yield f"data: {_json.dumps({'type': 'done', 'session_id': session_id, 'mode': mode, 'citations': citations, 'conversation_id': conv_id, 'conversation_saved': conv_saved, 'message_id': msg_id, 'trace_id': trace_id, 'model': model_used, 'tokens_used': tokens_used})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/explain")
@limiter.limit("60/hour")
async def explain_verse(request: Request, req: ExplainRequest):
    """Explain a specific verse (for reading mode). Counts toward per-user quota."""
    from backend.llm import generate_response
    from backend.supabase_client import check_user_quota, verify_jwt

    # Per-user quota check — same as /api/query
    explain_user_id = verify_jwt(request.headers.get("Authorization"))
    if explain_user_id:
        allowed, used, _ = check_user_quota(explain_user_id)
        if not allowed:
            raise HTTPException(status_code=429, detail={
                "error": "daily_limit_reached", "used": used, "limit": 50,
                "message": "You've used today's 50 queries. Resets at midnight UTC.",
            })

    corpus = request.app.state.corpus
    verse = corpus.get_verse(req.scripture, req.chapter, req.verse)
    if not verse:
        raise HTTPException(status_code=404, detail=f"{req.scripture} {req.chapter}.{req.verse} not found")

    context_verses = corpus.get_context(req.scripture, req.chapter, req.verse, window=2)

    hits = [{"text": v["text"], "scripture": v["scripture"], "chapter": v["chapter"],
             "verse": v["verse"], "translator": v["translator"], "tradition": v["tradition"],
             "parent_text": "", "year": v.get("year", "")} for v in context_verses]

    explanation_text, _, _, _ = generate_response(
        f"Explain this verse in depth: {verse['text']}",
        hits,
        mode="exploration",
        use_deep_model=False,
    )
    return {"verse": verse, "explanation": explanation_text, "context_verses": context_verses}
