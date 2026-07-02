"""
LLM generation layer for AntarDarshan.

Supports two providers via environment variables:
  TOGETHER_API_KEY  — use Together AI (gpt-oss-20b by default, no hard rate limits)
  GROQ_API_KEY      — use Groq (Llama 4 Scout 17B, very fast, 6k TPM cap)

Together AI takes priority if both keys are present.
Set LLM_MODEL to override the default model for either provider.
"""

import os
import time
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

# ── Provider selection ─────────────────────────────────────────────────────────
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")

_USE_TOGETHER = bool(TOGETHER_API_KEY)

if _USE_TOGETHER:
    from openai import OpenAI as _OpenAI
    MODEL_SIMPLE = os.getenv("LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    MODEL_DEEP   = os.getenv("LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    _PROVIDER    = "together"
else:
    from groq import Groq as _Groq
    MODEL_SIMPLE = os.getenv("LLM_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    MODEL_DEEP   = os.getenv("LLM_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    _PROVIDER    = "groq"

_client = None


def _get_client():
    global _client
    if _client is None:
        if _USE_TOGETHER:
            _client = _OpenAI(
                api_key=TOGETHER_API_KEY,
                base_url="https://api.together.xyz/v1",
                timeout=90.0,
            )
        elif GROQ_API_KEY:
            from groq import Groq
            _client = Groq(api_key=GROQ_API_KEY, timeout=60.0)
    return _client


# LangFuse observability — traces every LLM call
_langfuse = None


def _get_langfuse():
    global _langfuse
    if _langfuse is None:
        pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        sk = os.getenv("LANGFUSE_SECRET_KEY", "")
        host = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        if pk and sk:
            _langfuse = Langfuse(public_key=pk, secret_key=sk, host=host)
    return _langfuse

_CITATION_RULE = """
CONVERSATION PRIORITY: If the user's question refers to something from our conversation (their name, something they said, a previous answer), answer from conversation history — do not use retrieved sources for personal/contextual questions.

CITATIONS (strict): Only cite [Source N] entries from the list below. Copy scripture name, chapter, verse exactly. Never invent verse numbers. If sources don't cover the question, say so.

FORMAT: You MUST respond in markdown. Start immediately with a ## heading (no preamble).
Use one section per retrieved source — aim to cover ALL provided sources, up to 5 sections. Each section must follow this EXACT pattern — no deviations:

## Section Title
One complete intro sentence that stands alone (never end with a colon, "mentions that", or "states that").

> "Exact quote text." — Scripture Name, Ch.X, V.Y

2-3 sentences OUTSIDE the blockquote. Explain: (1) what the quote reveals that isn't obvious from reading it alone, (2) why this insight matters for the question asked, (3) how it relates to or differs from what other traditions say. Write for someone intelligent but unfamiliar with Indian philosophy — assume no prior knowledge of the scripture or tradition.

---
STRICT RULES:
- The blockquote contains ONLY the quoted text and attribution. The explanation always comes AFTER the blockquote, never inside it.
- ## Synthesis contains ONLY flowing prose — no blockquotes, no new quotes, no bullet points. Make it substantive — at least 3 sentences that tie together the key thread across all cited passages.
- Never use [Source N] inline — cite scripture name directly in the blockquote attribution.
- Open with the sharpest, most direct answer — not "X is a complex/multifaceted concept".
- Skip any retrieved passage that demeans a group of people based on gender, caste, or birth — cite a different source instead.

After your Synthesis, on a new line write exactly:
FOLLOWUPS: [question 1] | [question 2]
Each question must be directly and completely answerable using the [Source N] passages provided above — do not suggest questions about topics absent from the sources. Write at most 2 questions. If you cannot find 2 fully grounded questions, write 1 or none."""

SYSTEM_PROMPTS = {
    "citation": f"""You are AntarDarshan, an AI assistant specializing in Indian philosophy.
You answer questions using ONLY the retrieved scripture passages provided in [Source N] blocks below.

Rules:
- Quote the retrieved verses directly and explain their meaning in depth.
- Be conversational but grounded — not preachy, not academic.
- Never claim authority — present what the texts say.
- If multiple traditions are represented, label each clearly.
- Do NOT repeat the same scripture in multiple sections. Merge related passages into one section.
{_CITATION_RULE}""",

    "well_being": f"""You are AntarDarshan, an AI companion for those seeking wisdom in difficult times.
You draw from Indian philosophical traditions to offer grounded perspective.

Rules:
- Lead with empathy — acknowledge the person's feelings first.
- Then offer relevant wisdom from the retrieved passages.
- Never give medical, psychiatric, or legal advice.
- Never claim the texts can "fix" someone's problems — offer wisdom as a lens, not a prescription.
- If distress seems severe, mention: iCall India (9152987821) or Vandrevala Foundation (1860-2662-345).
{_CITATION_RULE}""",

    "exploration": f"""You are AntarDarshan, a guide for reading Indian philosophical texts.
Help the user deeply understand the verse they are reading.

Rules:
- Explain what the verse means literally, philosophically, and practically.
- Explain key Sanskrit/Pali terms with their meanings.
- Reference the surrounding verses (provided in context) to show the flow of argument.
- Make the explanation accessible to someone new to Indian philosophy.
{_CITATION_RULE}""",

    "conversational": """You are AntarDarshan, an AI assistant specializing in Indian philosophy.
The user is asking a conversational follow-up about something already discussed above.

Rules:
- Answer from the conversation context — do NOT cite new scriptures or add [Source N] blocks.
- Respond as flowing prose, NO section headings, NO bullet points.
- 2-3 paragraphs maximum.
- Start directly with the insight, not with "Based on what was discussed..." or similar.
- Speak with perspective — give the actual synthesis the user is asking for, not a summary of what you already said.""",

    "comparison": f"""You are AntarDarshan, facilitating cross-tradition philosophical comparison.
Present perspectives from each tradition side by side using ONLY the retrieved sources.

Rules:
- NEVER blend traditions without explicit labels.
- Present each tradition's view separately.
- Note genuine differences honestly — do not force agreement.
- Use proper terminology for each tradition (Atman vs Anatta, Brahman vs Sunyata, etc.).
- If a tradition is not represented in the retrieved sources, say so — do not invent coverage.
{_CITATION_RULE}""",
}


def _build_context(hits: list[dict], max_chunk_chars: int | None = None) -> str:
    """
    Format retrieved chunks as LLM context.

    max_chunk_chars: if None, sends full text (default — best quality).
    Only set this when a provider returns a 413/context-too-large error.
    The retry path in generate_response() handles progressive reduction.
    """
    parts = []
    for i, hit in enumerate(hits, 1):
        citation = f"{hit['scripture']}, Ch.{hit['chapter']}, V.{hit['verse']} ({hit['translator']}, {hit.get('year', '')})"
        text = hit["text"]

        if max_chunk_chars and len(text) > max_chunk_chars:
            cut = text[:max_chunk_chars]
            last_sent = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            text = cut[:last_sent + 1] if last_sent > 100 else cut + "…"

        parts.append(f"[Source {i}] {citation}\n{text}")

        if hit.get("parent_text"):
            # Parent context also trimmed when in fallback mode, full otherwise
            parent = hit["parent_text"]
            if max_chunk_chars:
                parent = parent[:400]
            parts.append(f"[Surrounding context for Source {i}]: {parent}")

    return "\n\n".join(parts)


def generate_response(
    query: str,
    hits: list[dict],
    mode: str = "citation",
    use_deep_model: bool = False,
    conversation_history: list[dict] | None = None,
    log_content: bool | None = None,
) -> tuple[str, str | None, str | None, int]:
    """Generate a cited response using Groq LLM. Always returns (answer, trace_id, model, tokens)."""
    client = _get_client()
    if not client:
        return _fallback_response(query, hits)  # 4-tuple
    # log_content from request takes priority over env var
    if log_content is None:
        log_content = os.getenv("LANGFUSE_LOG_CONTENT", "false").lower() == "true"
    model = MODEL_DEEP if use_deep_model else MODEL_SIMPLE
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["citation"])
    context = _build_context(hits)

    messages = [{"role": "system", "content": system_prompt}]

    # conversation_history is already token-aware — llm-smartmem's get_context_async()
    # truncated it to fit within LLM_CONTEXT_MAX_TOKENS before it arrived here.
    # Do NOT slice again: that would discard valid recent context within budget.
    if conversation_history:
        messages.extend(conversation_history)

    source_ids = ", ".join(f"[Source {i+1}]" for i in range(len(hits)))
    messages.append(
        {"role": "user", "content": f"""The ONLY sources you are allowed to cite are: {source_ids}

Retrieved passages:

{context}

---

User's question: {query}

Answer using ONLY the sources listed above. If a source does not support a claim, do not make that claim. Do not cite any chapter or verse number not present in the sources."""},
    )

    # LangFuse trace — log metadata only, NOT message content.
    # User queries may contain sensitive information — never log query text.
    # We trace operational signals (mode, model, token counts, latency) without
    # sending any user-identifiable content to a third-party service.
    lf = _get_langfuse()
    trace = None
    generation = None
    # log_content is now set from the request parameter (user preference)
    # falling back to the env var for the non-streaming path

    if lf:
        trace = lf.trace(
            name="rag_generation",
            input={"query": query} if log_content else None,
            metadata={"mode": mode, "model": model, "num_hits": len(hits),
                      "history_turns": len(conversation_history or []) // 2},
        )
        generation = trace.generation(
            name="llm_generation", model=model,
            input={"messages": messages} if log_content else {"mode": mode, "num_sources": len(hits)},
            metadata={"mode": mode, "temperature": 0.3},
        )

    try:
        start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=3072,
        )
        answer = response.choices[0].message.content

        if generation:
            generation.end(
                output=answer if log_content else {"answer_length": len(answer), "mode": mode},
                usage={"input": response.usage.prompt_tokens, "output": response.usage.completion_tokens},
                metadata={"latency_s": time.time() - start},
            )
        trace_id = trace.id if trace else None
        # Flush immediately so trace appears in dashboard without waiting for batch interval
        lf = _get_langfuse()
        if lf:
            lf.flush()
        return answer, trace_id, model, response.usage.prompt_tokens + response.usage.completion_tokens
    except Exception as e:
        err_str = str(e)

        # Provider signalled the request is too large (e.g. Groq 413 TPM limit,
        # OpenAI 400 context_length_exceeded). Try progressively smaller context
        # without giving up — quality degrades gracefully.
        is_too_large = "413" in err_str or "context_length_exceeded" in err_str or "too large" in err_str.lower()

        if is_too_large:
            # Two-stage fallback:
            # Stage 1: keep all sources but cap each chunk at 1,200 chars
            # Stage 2: drop to 3 sources + cap at 800 chars
            for n_hits, max_chars, label in [
                (len(hits), 1_200, "stage-1: trimmed chunks"),
                (min(3, len(hits)), 800, "stage-2: fewer + shorter"),
            ]:
                print(f"  Context too large — retrying ({label})...")
                try:
                    trimmed_context = _build_context(hits[:n_hits], max_chunk_chars=max_chars)
                    source_ids = ", ".join(f"[Source {i+1}]" for i in range(n_hits))

                    retry_messages = [{"role": "system", "content": system_prompt}]
                    if conversation_history:
                        retry_messages.extend(conversation_history)
                    retry_messages.append({"role": "user", "content": (
                        f"The ONLY sources you are allowed to cite are: {source_ids}\n\n"
                        f"Retrieved passages:\n\n{trimmed_context}\n\n---\n\n"
                        f"User's question: {query}\n\n"
                        f"Answer using ONLY the sources listed above."
                    )})

                    retry_resp = client.chat.completions.create(
                        model=model, messages=retry_messages,
                        temperature=0.3, max_tokens=1024,
                    )
                    answer = retry_resp.choices[0].message.content
                    print(f"  Retry succeeded ({label}).")
                    return (
                        answer,
                        trace.id if trace else None,
                        model,
                        retry_resp.usage.prompt_tokens + retry_resp.usage.completion_tokens,
                    )
                except Exception as retry_err:
                    if "413" not in str(retry_err) and "context_length_exceeded" not in str(retry_err):
                        break  # Different error — stop retrying
                    print(f"  Still too large, trying next stage...")

        if generation:
            generation.end(output={"error": type(e).__name__}, level="ERROR")
        print(f"  LLM API error: {e}")
        return _fallback_response(query, hits)  # already returns 4-tuple


def generate_response_stream(
    query: str,
    hits: list[dict],
    mode: str = "citation",
    use_deep_model: bool = False,
    conversation_history: list[dict] | None = None,
    log_content: bool | None = None,
):
    """
    Streaming version of generate_response.
    Yields plain text tokens as they arrive from Groq.
    Returns (trace_id, model, total_tokens) when exhausted via StopIteration.

    Usage:
        gen = generate_response_stream(query, hits, mode=mode)
        try:
            while True:
                token = next(gen)
                yield token
        except StopIteration as e:
            trace_id, model, tokens = e.value
    """
    client = _get_client()
    if not client:
        # Fallback: yield the full fallback response as one chunk
        text, _, _, _ = _fallback_response(query, hits)
        yield text
        return None, None, 0

    model = MODEL_DEEP if use_deep_model else MODEL_SIMPLE
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["citation"])
    context = _build_context(hits)
    if log_content is None:
        log_content = os.getenv("LANGFUSE_LOG_CONTENT", "false").lower() == "true"

    source_ids = ", ".join(f"[Source {i+1}]" for i in range(len(hits)))
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": (
        f"The ONLY sources you are allowed to cite are: {source_ids}\n\n"
        f"Retrieved passages:\n\n{context}\n\n---\n\n"
        f"User's question: {query}\n\n"
        f"Answer using ONLY the sources listed above."
    )})

    lf = _get_langfuse()
    trace = None
    if lf:
        trace = lf.trace(
            name="rag_generation",
            input={"query": query} if log_content else None,
            metadata={"mode": mode, "model": model, "num_hits": len(hits),
                      "history_turns": len(conversation_history or []) // 2},
        )

    def _attempt_stream(attempt_messages, attempt_hits, max_tok=3072):
        kwargs: dict = dict(model=model, messages=attempt_messages,
                            temperature=0.3, max_tokens=max_tok, stream=True)
        if _USE_TOGETHER:
            # Together AI requires explicit opt-in to get usage in streaming chunks
            kwargs["stream_options"] = {"include_usage": True}
        return client.chat.completions.create(**kwargs)

    # Retry stages matching the non-streaming endpoint
    retry_stages = [
        (messages, hits, 3072, "original"),
        (None, hits, 1024, "stage-1: trimmed chunks"),      # trimmed context
        (None, hits[:3], 1024, "stage-2: fewer sources"),   # fewer sources
    ]

    stream = None
    for stage_messages, stage_hits, max_tok, label in retry_stages:
        try:
            if stage_messages is None:
                # Rebuild context with trimmed chunks
                trimmed_ctx = _build_context(stage_hits, max_chunk_chars=1_200)
                src_ids = ", ".join(f"[Source {i+1}]" for i in range(len(stage_hits)))
                stage_messages = [{"role": "system", "content": system_prompt}]
                if conversation_history:
                    stage_messages.extend(conversation_history)
                stage_messages.append({"role": "user", "content": (
                    f"The ONLY sources you are allowed to cite are: {src_ids}\n\n"
                    f"Retrieved passages:\n\n{trimmed_ctx}\n\n---\n\n"
                    f"User's question: {query}\n\nAnswer using ONLY the sources listed above."
                )})
                if label != "original":
                    print(f"  Streaming context too large — retrying ({label})...")
            stream = _attempt_stream(stage_messages, stage_hits, max_tok)
            break
        except Exception as e:
            if "413" in str(e) or "too large" in str(e).lower():
                continue  # try next stage
            print(f"  LLM streaming error: {e}")
            text, _, _, _ = _fallback_response(query, hits)
            yield text
            return None, None, 0

    if stream is None:
        text, _, _, _ = _fallback_response(query, hits)
        yield text
        return None, None, 0

    try:
        full_answer = []
        prompt_tokens = 0
        completion_tokens = 0

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full_answer.append(delta.content)
                yield delta.content
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens

        answer = "".join(full_answer)
        total_tokens = prompt_tokens + completion_tokens
        trace_id = trace.id if trace else None

        if trace:
            trace.generation(
                name="llm_generation", model=model,
                input={"messages": stage_messages} if log_content else {"mode": mode, "num_sources": len(hits)},
                output=answer if log_content else {"answer_length": len(answer)},
                usage={"input": prompt_tokens, "output": completion_tokens},
            )
            lf.flush()

        return trace_id, model, total_tokens

    except Exception as e:
        print(f"  LLM streaming error: {e}")
        text, _, _, _ = _fallback_response(query, hits)
        yield text
        return None, None, 0


def score_trace(trace_id: str, rating: int, comment: str | None = None, log_content: bool = False):
    """
    Attach user feedback score to a LangFuse trace.
    comment is only forwarded when log_content=True (user opted into content logging).
    """
    lf = _get_langfuse()
    if not lf or not trace_id:
        return
    try:
        lf.score(
            trace_id=trace_id,
            name="user_feedback",
            value=rating,
            # Only include comment text if user has opted into content logging
            comment=comment if (log_content and comment) else None,
        )
        lf.flush()
    except Exception as e:
        print(f"  LangFuse score error (non-critical): {e}")


def _fallback_response(query: str, hits: list[dict]) -> tuple[str, None, None, int]:
    """Fallback when Groq is unavailable — returns same 4-tuple as generate_response."""
    lines = ["Here are the most relevant passages for your question:\n"]
    for i, hit in enumerate(hits[:3], 1):
        citation = f"{hit['scripture']}, Ch.{hit['chapter']}, V.{hit['verse']} ({hit['translator']})"
        lines.append(f"**[{i}] {citation}**")
        lines.append(f"> {hit['text'][:300]}")
        lines.append("")
    lines.append("---")
    lines.append("*Note: LLM synthesis unavailable. Showing raw retrieval results.*")
    return "\n".join(lines), None, None, 0
