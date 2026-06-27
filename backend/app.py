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
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

# ── Concurrency control ────────────────────────────────────────────────────────
# Limits simultaneous LLM calls per worker. Prevents runaway Groq usage and
# CPU thrashing from too many concurrent bge-m3 reranker calls.
# With 2 Gunicorn workers × 15 = 30 max in-flight LLM calls across the process.
_LLM_SEM_LIMIT = 15

class _TrackedSemaphore:
    """asyncio.Semaphore wrapper that exposes available slot count without
    relying on the private ._value attribute."""
    def __init__(self, limit: int):
        self._sem = asyncio.Semaphore(limit)
        self._limit = limit
        self._active = 0

    async def __aenter__(self):
        await self._sem.acquire()
        self._active += 1
        return self

    async def __aexit__(self, *_):
        self._active -= 1
        self._sem.release()

    @property
    def slots_free(self) -> int:
        return self._limit - self._active

_LLM_SEMAPHORE = _TrackedSemaphore(_LLM_SEM_LIMIT)

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
    from backend.rag_query import _get_model, _get_reranker, _get_client
    from backend.corpus_index import CorpusIndex
    print("Loading embedding model (BGE-M3)...")
    _get_model()
    print("Loading reranker (BGE-reranker-v2-m3)...")
    _get_reranker()
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


# Set DISABLE_RATE_LIMIT=true to bypass rate limiting (load testing / local dev).
# In production this must always be false/unset.
_rate_limit_enabled = os.getenv("DISABLE_RATE_LIMIT", "false").lower() != "true"
limiter = Limiter(key_func=get_remote_address, enabled=_rate_limit_enabled)

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
    follow_ups: list[str] = []


def _parse_follow_ups(text: str) -> tuple[str, list[str]]:
    """
    Extract and strip the FOLLOWUPS section appended by the LLM.
    Returns (clean_answer, questions_list).
    Tolerant of case/whitespace variants (e.g. 'Followups :' or 'FOLLOWUPS:').
    """
    import re as _re
    m = _re.search(r'\n\s*FOLLOWUPS?\s*:\s*(.+)', text, _re.IGNORECASE | _re.DOTALL)
    if not m:
        return text, []
    clean = text[:m.start()].rstrip()
    questions = [q.strip() for q in m.group(1).split('|') if q.strip()][:3]
    return clean, questions


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


@app.get("/healthz")
async def liveness():
    """Lightweight liveness probe — never pings dependencies.
    Kubernetes/load balancer should use this for liveness (restart on fail).
    Returns 200 as long as the process is alive."""
    return {"status": "alive"}


@app.get("/api/health")
async def health():
    """
    Health check. Returns 200 when all dependencies are up, 503 when degraded.
    Used by Gunicorn readiness probe and load balancer health checks.
    """
    from backend.sessions import sessions
    checks: dict[str, str] = {}
    degraded = False

    # 1. Qdrant
    try:
        from qdrant_client import QdrantClient
        _qc = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), timeout=3)
        _qc.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"
        degraded = True

    # 2. Corpus index (in-memory)
    try:
        corpus = app.state.corpus
        checks["corpus"] = f"ok ({len(corpus.scriptures)} scriptures)"
    except Exception:
        checks["corpus"] = "not loaded"
        degraded = True

    # 3. LLM semaphore headroom
    checks["llm_slots_free"] = str(_LLM_SEMAPHORE.slots_free)

    status_code = 503 if degraded else 200
    body = {
        "status": "degraded" if degraded else "ok",
        "service": "antardarshan",
        "version": "0.1.0",
        "active_sessions": sessions.active_count,
        "checks": checks,
    }
    return JSONResponse(content=body, status_code=status_code)


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

    # 1. Global org-level daily limit (SQLite) — run in thread (blocking I/O)
    GLOBAL_DAILY_LIMIT = 15_400
    def _check_global_quota():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            today = datetime.now(_tz.utc).strftime("%Y-%m-%d")
            row = conn.execute(
                "SELECT COUNT(*) FROM query_logs WHERE DATE(created_at) = ?", (today,)
            ).fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception:
            return 0
    _global_used = await asyncio.to_thread(_check_global_quota)

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

    # 2. Per-user daily limit (Supabase) — run in thread (blocking HTTP)
    user_id = await asyncio.to_thread(verify_jwt, request.headers.get("Authorization"))
    if user_id:
        allowed, used, remaining = await asyncio.to_thread(check_user_quota, user_id)
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

    from backend.query_analysis import is_conversational_followup

    mode = detect_mode(req.query)

    # Skip RAG retrieval for conversational follow-ups (summaries, opinions, clarifications).
    # These should be answered from conversation history, not new scripture retrieval.
    if is_conversational_followup(req.query) and history:
        hits = []
        mode = "conversational"
    else:
        # search() is CPU-bound (bge-m3 encode + reranker) — run in thread
        hits = await asyncio.to_thread(search, req.query, top_k=req.top_k)

    use_deep = (mode in ("comparison", "well_being"))

    async with _LLM_SEMAPHORE:
        # generate_response() blocks on Groq HTTP (5-15s) — run in thread
        raw_answer, trace_id, model_used, tokens_used = await asyncio.to_thread(
            generate_response,
            req.query, hits, mode=mode, use_deep_model=use_deep,
            conversation_history=history if history else None,
            log_content=req.log_content,
        )
    latency_ms = int((time.time() - start) * 1000)

    # Parse immediately — use clean_answer everywhere so neither session memory
    # nor persisted transcripts contain the raw FOLLOWUPS: control text.
    answer, follow_ups = _parse_follow_ups(raw_answer)

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
        follow_ups=follow_ups,
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

            # Upsert on (user_id, message_id) so re-rating updates the existing row
            # rather than creating duplicates. Falls back to insert for null message_id.
            if verified_msg_id:
                sb.table("feedback_responses").upsert({
                    "user_id": user_id,
                    "conversation_id": verified_conv_id,
                    "message_id": verified_msg_id,
                    "rating": req.rating,
                    "comment": req.comment,
                }, on_conflict="user_id,message_id").execute()
            else:
                sb.table("feedback_responses").insert({
                    "user_id": user_id,
                    "conversation_id": verified_conv_id,
                    "message_id": None,
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

    # ── Quota checks — identical to non-streaming endpoint, all in threads ──────
    GLOBAL_DAILY_LIMIT = 15_400
    from datetime import datetime, timezone as _tz2

    def _check_global_quota_stream():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            today = datetime.now(_tz2.utc).strftime("%Y-%m-%d")
            row = conn.execute(
                "SELECT COUNT(*) FROM query_logs WHERE DATE(created_at) = ?", (today,)
            ).fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception:
            return 0

    _global_used2 = await asyncio.to_thread(_check_global_quota_stream)

    if _global_used2 >= GLOBAL_DAILY_LIMIT:
        return JSONResponse(status_code=429, content={"detail": {
            "error": "global_limit_reached", "limit": GLOBAL_DAILY_LIMIT,
            "message": "Daily query limit reached. Come back tomorrow.",
        }})

    from backend.supabase_client import check_user_quota, log_user_query, persist_messages, ensure_conversation, verify_jwt, get_conversation
    from backend.sessions import sessions
    stream_user_id = await asyncio.to_thread(verify_jwt, request.headers.get("Authorization"))
    if stream_user_id:
        allowed, _, _ = await asyncio.to_thread(check_user_quota, stream_user_id)
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

    from backend.query_analysis import is_conversational_followup
    if is_conversational_followup(req.query) and history:
        hits = []
        mode = "conversational"
    else:
        hits = await asyncio.to_thread(search, req.query, top_k=req.top_k)

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
        """
        Thread+queue pattern: generate_response_stream() runs in a thread pool
        worker. Tokens arrive via asyncio.Queue so next(gen) never blocks the
        event loop. The semaphore is held for the full stream lifetime.

        Client disconnect safety: stop_event signals the producer thread to
        exit early. Without this, a full bounded queue would cause the producer
        to block indefinitely on fut.result() after the consumer is cancelled.
        """
        import threading
        stop_event = threading.Event()
        # Bounded queue — producer blocks when full (backpressure for slow clients)
        token_queue: asyncio.Queue = asyncio.Queue(maxsize=32)
        loop = asyncio.get_running_loop()
        result_holder: list = []

        def _run_stream():
            """Blocking generator — runs in thread pool, pushes to bounded queue."""
            try:
                _gen = generate_response_stream(
                    req.query, hits, mode=mode, use_deep_model=use_deep,
                    conversation_history=history if history else None,
                    log_content=req.log_content,
                )
                try:
                    while not stop_event.is_set():
                        token = next(_gen)
                        fut = asyncio.run_coroutine_threadsafe(
                            token_queue.put(("token", token)), loop
                        )
                        # Timeout prevents permanent block if consumer cancelled
                        try:
                            fut.result(timeout=5.0)
                        except Exception:
                            break  # consumer gone or timed out — exit cleanly
                except StopIteration as e:
                    result_holder.append(e.value)
            except Exception as exc:
                result_holder.append(None)
                if not stop_event.is_set():
                    asyncio.run_coroutine_threadsafe(
                        token_queue.put(("error", str(exc))), loop
                    )
            finally:
                asyncio.run_coroutine_threadsafe(
                    token_queue.put(("done", None)), loop
                )

        answer_parts = []
        trace_id = None
        model_used = None
        tokens_used = 0

        async with _LLM_SEMAPHORE:
            gen_future = loop.run_in_executor(None, _run_stream)

            try:
                while True:
                    event_type, payload = await token_queue.get()
                    if event_type == "done":
                        break
                    if event_type == "error":
                        yield f"data: {_json.dumps({'type': 'error', 'content': 'Stream error'})}\n\n"
                        break
                    answer_parts.append(payload)
                    yield f"data: {_json.dumps({'type': 'token', 'content': payload})}\n\n"
            except asyncio.CancelledError:
                # Client disconnected — signal producer and wait briefly for cleanup
                stop_event.set()
                try:
                    await asyncio.wait_for(asyncio.wrap_future(gen_future), timeout=2.0)
                except (asyncio.TimeoutError, Exception):
                    pass
                return

            await asyncio.wait_for(asyncio.wrap_future(gen_future), timeout=5.0)

        if result_holder and result_holder[0]:
            trace_id, model_used, tokens_used = result_holder[0]

        raw_answer = "".join(answer_parts)

        # Shared tolerant parser — handles case/whitespace variants
        answer, follow_ups = _parse_follow_ups(raw_answer)

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

        # Final metadata event — include follow_ups so frontend can show suggestion chips
        yield f"data: {_json.dumps({'type': 'done', 'session_id': session_id, 'mode': mode, 'citations': citations, 'conversation_id': conv_id, 'conversation_saved': conv_saved, 'message_id': msg_id, 'trace_id': trace_id, 'model': model_used, 'tokens_used': tokens_used, 'follow_ups': follow_ups})}\n\n"
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

    async with _LLM_SEMAPHORE:
        explanation_text, _, _, _ = await asyncio.to_thread(
            generate_response,
            f"Explain this verse in depth: {verse['text']}",
            hits,
            mode="exploration",
            use_deep_model=False,
        )
    return {"verse": verse, "explanation": explanation_text, "context_verses": context_verses}


# ══════════════════════════════════════════════════════════════════════
# Wisdom Wall endpoints
# ══════════════════════════════════════════════════════════════════════

class WisdomPostRequest(BaseModel):
    content: str
    contact_email: str | None = None
    contact_phone: str | None = None


class WisdomVoteRequest(BaseModel):
    vote: str  # "up" or "down"


class DisplayNameRequest(BaseModel):
    display_name: str


@app.get("/api/wisdom")
@limiter.limit("120/minute")
async def list_wisdom_posts(
    request: Request,
    page: int = 1,
    per_page: int = 10,
    user_display_name: str | None = None,
):
    """
    Public feed. Paginated by creation date (newest first), 10 per page.
    Optionally filter by user display_name.
    """
    from backend.supabase_client import get_supabase, verify_jwt
    sb = get_supabase()
    if not sb:
        raise HTTPException(503, "Database unavailable")

    # Clamp pagination to safe bounds
    page     = max(1, page)
    per_page = max(1, min(50, per_page))

    # Determine authenticated user so we can mark is_owner on each post
    auth_user_id = verify_jwt(request.headers.get("Authorization"))

    offset = (page - 1) * per_page
    # Include user_id so we can compute is_owner; it won't be forwarded to the client
    q = sb.table("wisdom_posts") \
        .select("id, user_id, display_name, content, contact_email, contact_phone, "
                "contact_hidden_at, upvotes, downvotes, is_edited, created_at, updated_at") \
        .eq("is_removed", False) \
        .eq("moderation_status", "approved") \
        .order("created_at", desc=True) \
        .range(offset, offset + per_page - 1)

    if user_display_name:
        q = q.ilike("display_name", user_display_name)

    result = q.execute()
    posts = result.data or []

    for p in posts:
        # Mark ownership via verified user_id, never expose raw user_id
        p["is_owner"] = bool(auth_user_id and p.get("user_id") == auth_user_id)
        del p["user_id"]
        # Mask contact info once past retention window
        if p.get("contact_hidden_at"):
            p["contact_email"] = None
            p["contact_phone"] = None

    return {"posts": posts, "page": page, "per_page": per_page}


@app.post("/api/wisdom")
@limiter.limit("10/minute")
async def create_wisdom_post(request: Request, req: WisdomPostRequest):
    """Create a Wisdom Wall post. Runs LLM moderation. Auth required."""
    from backend.supabase_client import get_supabase, verify_jwt
    from backend.wisdom import (
        moderate_post, get_post_count_today, get_mod_attempts_today,
        increment_mod_attempts, MAX_POSTS_PER_DAY, MAX_MOD_ATTEMPTS_PER_DAY, MAX_POST_CHARS,
    )

    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(401, "Authentication required")

    content = req.content.strip()
    if not content:
        raise HTTPException(400, "Content cannot be empty")
    if len(content) > MAX_POST_CHARS:
        raise HTTPException(400, f"Content exceeds {MAX_POST_CHARS} characters")

    sb = get_supabase()
    if not sb:
        raise HTTPException(503, "Database unavailable")

    # Rate limit: MAX_POSTS_PER_DAY posts per day (see backend/wisdom.py)
    posts_today = get_post_count_today(sb, user_id)
    if posts_today >= MAX_POSTS_PER_DAY:
        raise HTTPException(429, detail={"error": "daily_post_limit",
            "used": posts_today, "limit": MAX_POSTS_PER_DAY,
            "message": f"You can post at most {MAX_POSTS_PER_DAY} times per day. Come back tomorrow."})

    # Rate limit: max moderation attempts per day
    attempts_used = get_mod_attempts_today(sb, user_id)
    if attempts_used >= MAX_MOD_ATTEMPTS_PER_DAY:
        raise HTTPException(429, detail={"error": "moderation_limit",
            "used": attempts_used, "limit": MAX_MOD_ATTEMPTS_PER_DAY,
            "message": f"You've used all {MAX_MOD_ATTEMPTS_PER_DAY} submission attempts for today. Come back tomorrow."})

    # Fetch display name
    profile = sb.table("user_profiles").select("display_name") \
        .eq("user_id", user_id).limit(1).execute()
    if not profile.data:
        raise HTTPException(400, detail={"error": "no_display_name",
            "message": "Set a display name before posting."})
    display_name = profile.data[0]["display_name"]

    # LLM moderation (always increments the attempt counter)
    increment_mod_attempts(sb, user_id)
    approved, reason = moderate_post(content)

    if not approved:
        return {"status": "rejected", "reason": reason,
                "message": f"Post rejected: {reason}. Please review the Wisdom Wall guidelines."}

    # Insert post
    row = sb.table("wisdom_posts").insert({
        "user_id":       user_id,
        "display_name":  display_name,
        "content":       content,
        "contact_email": req.contact_email or None,
        "contact_phone": req.contact_phone or None,
        "moderation_status": "approved",
    }).select().execute()

    post_data = row.data[0] if row.data else None
    return {"status": "approved", "post": post_data}


@app.patch("/api/wisdom/{post_id}")
@limiter.limit("20/minute")
async def edit_wisdom_post(request: Request, post_id: str, req: WisdomPostRequest):
    """Edit own post. Re-runs LLM moderation. Counts against daily attempt limit."""
    from datetime import datetime, timezone
    from backend.supabase_client import get_supabase, verify_jwt
    from backend.wisdom import (
        moderate_post, get_mod_attempts_today, increment_mod_attempts,
        MAX_MOD_ATTEMPTS_PER_DAY, MAX_POST_CHARS,
    )

    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(401, "Authentication required")

    content = req.content.strip()
    if not content:
        raise HTTPException(400, "Content cannot be empty")
    if len(content) > MAX_POST_CHARS:
        raise HTTPException(400, f"Content exceeds {MAX_POST_CHARS} characters")

    sb = get_supabase()
    if not sb:
        raise HTTPException(503, "Database unavailable")

    # Verify ownership
    existing = sb.table("wisdom_posts").select("user_id") \
        .eq("id", post_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user_id:
        raise HTTPException(404, "Post not found")

    if get_mod_attempts_today(sb, user_id) >= MAX_MOD_ATTEMPTS_PER_DAY:
        raise HTTPException(429, detail={"error": "moderation_limit",
            "message": "Moderation limit reached. Try again tomorrow."})

    increment_mod_attempts(sb, user_id)
    approved, reason = moderate_post(content)

    if not approved:
        return {"status": "rejected", "reason": reason,
                "message": f"Edit rejected: {reason}. Original post unchanged."}

    row = sb.table("wisdom_posts").update({
        "content":       content,
        "contact_email": req.contact_email or None,
        "contact_phone": req.contact_phone or None,
        "is_edited":     True,
        "updated_at":    datetime.now(timezone.utc).isoformat(),
    }).eq("id", post_id).select().execute()

    post_data = row.data[0] if row.data else None
    return {"status": "approved", "post": post_data}


@app.delete("/api/wisdom/{post_id}")
@limiter.limit("20/minute")
async def delete_wisdom_post(request: Request, post_id: str):
    """Delete own post (hard delete)."""
    from backend.supabase_client import get_supabase, verify_jwt

    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(401, "Authentication required")

    sb = get_supabase()
    if not sb:
        raise HTTPException(503, "Database unavailable")

    existing = sb.table("wisdom_posts").select("user_id") \
        .eq("id", post_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user_id:
        raise HTTPException(404, "Post not found")

    sb.table("wisdom_posts").delete().eq("id", post_id).execute()
    return {"ok": True}


@app.post("/api/wisdom/{post_id}/vote")
@limiter.limit("60/minute")
async def vote_wisdom_post(request: Request, post_id: str, req: WisdomVoteRequest):
    """Upvote or downvote a post. Toggle off by voting same direction twice."""
    from backend.supabase_client import get_supabase, verify_jwt

    if req.vote not in ("up", "down"):
        raise HTTPException(400, "vote must be 'up' or 'down'")

    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(401, "Authentication required")

    sb = get_supabase()
    if not sb:
        raise HTTPException(503, "Database unavailable")

    result = sb.rpc("cast_wisdom_vote", {
        "p_post_id": post_id,
        "p_user_id": user_id,
        "p_vote":    req.vote,
    }).execute()

    action = result.data if result.data else "updated"
    return {"ok": True, "action": action}


@app.get("/api/wisdom/me/display-name")
@limiter.limit("60/minute")
async def get_display_name(request: Request):
    """Get the current user's Wisdom Wall display name."""
    from backend.supabase_client import get_supabase, verify_jwt

    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(401, "Authentication required")

    sb = get_supabase()
    if not sb:
        raise HTTPException(503, "Database unavailable")

    row = sb.table("user_profiles").select("display_name") \
        .eq("user_id", user_id).limit(1).execute()
    return {"display_name": row.data[0]["display_name"] if row.data else None}


@app.put("/api/wisdom/me/display-name")
@limiter.limit("10/minute")
async def set_display_name(request: Request, req: DisplayNameRequest):
    """Set or update the Wisdom Wall display name (one per account)."""
    from backend.supabase_client import get_supabase, verify_jwt

    user_id = verify_jwt(request.headers.get("Authorization"))
    if not user_id:
        raise HTTPException(401, "Authentication required")

    name = req.display_name.strip()
    if not name or len(name) > 50:
        raise HTTPException(400, "Display name must be 1–50 characters")

    sb = get_supabase()
    if not sb:
        raise HTTPException(503, "Database unavailable")

    try:
        sb.table("user_profiles").upsert(
            {"user_id": user_id, "display_name": name},
            on_conflict="user_id",
        ).execute()
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, detail={"error": "name_taken",
                "message": f"'{name}' is already taken. Please choose a different display name."})
        raise HTTPException(503, "Could not save display name")
    return {"ok": True, "display_name": name}


@app.post("/api/wisdom/cron/maintenance")
@limiter.limit("5/hour")
async def wisdom_cron_maintenance(request: Request):
    """
    Daily maintenance: hide old contact info + auto-remove high-downvote posts.
    Protected by a secret header in production (add CRON_SECRET to .env).
    """
    from backend.supabase_client import get_supabase
    from backend.wisdom import run_daily_maintenance

    cron_secret = os.getenv("CRON_SECRET")
    if not cron_secret:
        raise HTTPException(503, "CRON_SECRET not configured — set it in .env before using this endpoint")
    provided = request.headers.get("X-Cron-Secret")
    if provided != cron_secret:
        raise HTTPException(403, "Invalid cron secret")

    sb = get_supabase()
    if not sb:
        raise HTTPException(503, "Database unavailable")

    result = run_daily_maintenance(sb)
    return {"ok": True, **result}
