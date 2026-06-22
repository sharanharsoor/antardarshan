# Indian Philosophy AI — Combined Plan (All 3 LLMs)

> **How this file works:** This is the living consensus document. All three AI plans (Claude Opus 4, OpenAI Codex 5.3, Claude Sonnet 4.6) have been synthesized here. The user + all three LLMs must agree on this before implementation begins. Add your agreements, disagreements, or amendments below the `## LLM Agreements` section at the bottom.

**Date created:** 2026-06-15  
**Product name:** AntarDarshan (अन्तर्दर्शन) — "inner vision/insight"  
**Status:** ✅ APPROVED v5 — all decisions resolved, ready for execution  
**Source plans:**
- `claude-opus-4-plan.md`
- `indian_philosophy_ai_mvp_Codex-5.3.plan.md`
- `plan-sonnet-4-6.md`

See `DATA-SOURCES.md` for the comprehensive data registry (separate file, maintained independently).

---

## 0. Locked Constraints (User-Confirmed)

- Product remains **100% free forever** with daily query limits.
- **No paid tier, no freemium gating, no feature-paywall coupling.**
- Data-source legality is the primary success factor; architecture is finalized only after data-source sign-off.
- Implementation starts only after user + all 3 LLMs agree on:
  - `COMBINED-PLAN.md`
  - `DATA-SOURCES.md`

---

## 1. Product Vision

An AI assistant that gives people citation-grounded answers from the depth of Sanatan Dharma and Indian philosophical traditions — not surface summaries, but actual verse references, Sanskrit terms, and cross-tradition perspectives. When someone is stressed, grieving, or seeking meaning, this system surfaces what the texts actually say, not what a generic LLM vaguely remembers.

**Scope of traditions (in order of priority):**
1. Vedanta (Advaita, Vishishtadvaita, Dvaita)
2. Yoga philosophy (Patanjali + commentaries)
3. Samkhya, Nyaya, Vaisheshika, Mimamsa
4. Buddhist philosophy (Theravada, Madhyamaka, Yogacara)
5. Jain philosophy
6. Sikh tradition
7. Sant/Bhakti tradition (Kabir, Mirabai, Tukaram, Vivekananda)

---

## 2. The Most Important Decision: Architecture

**All three LLMs unanimously agree: RAG first, fine-tuning optional and secondary.**

### Why NOT fine-tuning as the primary strategy

- Fine-tuning teaches a model *how to behave*, not *what to know*. It compresses frequent patterns and forgets the long tail — exactly the deep texts (Manu Smriti, Tripura Rahasya, Ribhu Gita) that make this product unique.
- You cannot audit which fact came from which source after fine-tuning. For a product whose core value proposition is accurate citations, this is architecturally backwards.
- 100 Colab GPU hours with QLoRA on a 7B model will not beat a well-built RAG + Claude Haiku. You will spend weeks and end up with a system that hallucinates Sanskrit verse numbers.
- Fine-tuning locks you to one model. RAG lets you swap Claude for GPT-5 or Llama 4 when something better ships.

### When fine-tuning does make sense (Phase 4+)

Use RAFT (Retrieval-Augmented Fine-Tuning) to teach the model to:
- Read retrieved Sanskrit/philosophical chunks better
- Adopt a reflective, contemplative response register (not clinical, not preachy)
- Handle Sanskrit transliteration and verse-numbering conventions consistently

Do this only after:
- Retrieval quality is stable and validated
- You have 500+ real user queries as training signal
- You have identified specific behavioral gaps that prompting alone cannot fix

---

## 3. Architecture

### System Flow

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│  Mode Router                    │
│  - Citation mode (research)     │
│  - Well-being mode (guidance)   │
│  - Text exploration mode        │
│  - Tradition comparison mode    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Query Analysis                 │
│  - detect: tradition, text ref, │
│    theme, verse citation, lang  │
│  - safety check (crisis lang)   │
└──────────────┬──────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  Hybrid Retrieval                        │
│  ├── Dense (semantic): bge-m3 embeddings │
│  │       └── Qdrant vector search        │
│  └── Sparse (lexical): BM25              │
│          └── Typesense / Qdrant sparse   │
└──────────────┬───────────────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Re-ranker                      │
│  (cross-encoder: BGE or Cohere) │
│  Top 5-7 chunks selected        │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  LLM Generation                 │
│  - Constrained to retrieved     │
│    context only                 │
│  - Citation-required prompting  │
│  - Mode-specific system prompt  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Citation & Evidence Layer      │
│  - Verify cited verse exists    │
│    in corpus DB before showing  │
│  - Entailment check (claim      │
│    grounded in retrieved chunk) │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Safety & Escalation Layer      │
│  - Detect crisis language       │
│  - Never give medical advice    │
│  - Escalate to helplines when   │
│    warranted                    │
└──────────────┬──────────────────┘
               │
               ▼
         Final Response
   {text, chapter, verse, translator,
    tradition, source_url, license_tier}
```

### Conversation Modes (from Codex 5.3 + Opus 4)

1. **Citation mode** — "What does the Gita say about action?" → strict references, chapter/verse, Sanskrit term
2. **Well-being mode** — "I'm anxious about a decision" → empathy first, then grounded shlokas; no medical claims
3. **Text exploration** — "Walk me through Ashtavakra Gita Chapter 1" → verse-by-verse guided reading
4. **Tradition comparison** — "How does Advaita differ from Madhyamaka on emptiness?" → cross-corpus retrieval, labeled by tradition

### Chunk Schema (must be implemented exactly this way from day 1)

```json
{
  "text": "The wise man lets go of all results, whether good or bad...",
  "scripture": "Bhagavad Gita",
  "tradition": "hindu_vedanta",
  "chapter": 2,
  "verse": 50,
  "sanskrit": "योगः कर्मसु कौशलम्",
  "translator": "Edwin Arnold",
  "year": 1885,
  "language": "en",
  "license_tier": "A",
  "source_url": "https://www.gutenberg.org/ebooks/2388",
  "themes": ["karma", "action", "equanimity", "work"],
  "chunk_type": "verse",
  "verse_type": "stanza",
  "speaker": null,
  "chapter_name": null,
  "commentary_source": null
}
```

**Critical rule:** Never mix translators in one retrieval result without labeling. "Gita 2.47" reads differently in Arnold vs Telang — the user must know which they're reading.

---

## 3b. Advanced RAG Architecture (NOT Naive Cosine Similarity)

> **Principle:** One-size-fits-all RAG doesn't work for philosophical texts. A verse's meaning depends on its surrounding context, its tradition, and its commentarial history. Our retrieval must account for this.

### Why Naive RAG Fails for This Product

| Failure mode | Example | Why it happens |
|---|---|---|
| Context loss | "You are the witness" (AG 1.7) retrieved without knowing it's part of a 20-verse teaching sequence | Chunks lose meaning when isolated |
| Lexical mismatch | User asks about "duty" but text uses "dharma" and "svadharma" | Dense-only search misses Sanskrit/Pali terms |
| Cross-tradition blending | Retrieving a Vedantic verse for a Buddhist question because both mention "emptiness" | No tradition-aware filtering |
| Abstract query gap | User says "I'm feeling lost" — doesn't lexically match any verse | Raw question embedding doesn't match ancient text |

### Four Techniques We Use (Combined)

#### 1. Contextual Retrieval (Anthropic technique, 2024)

At INDEX time (one-time cost, ~$0 on Groq free tier), use an LLM to prepend 50-100 tokens of context to each chunk:

```
BEFORE (raw chunk):
"You are the one witness of everything, and are always totally free."

AFTER (contextualized chunk, what gets embedded):
"[From Ashtavakra Gita Chapter 1, verse 7. Ashtavakra teaches King Janaka 
about witness-consciousness (sakshi) as the true Self, within a dialogue 
on Advaita liberation.] You are the one witness of everything, and are 
always totally free."
```

**Impact:** Reduces retrieval failures by 49-67% (Anthropic's benchmarks). The embedding now captures WHERE this verse sits in the philosophical argument, not just WHAT it says in isolation.

**Cost:** 979 chunks × ~200 tokens each = ~200K tokens through Groq Llama 8B = well within 14,400 RPD free limit. One-time job.

**Phase 3 scale note:** At 100K+ chunks, contextual indexing = ~20M tokens = ~3 days of free-tier Groq 8B (14,400 RPD × ~1K tokens/request). Run as overnight batch job. Still $0, just takes time.

#### 2. Parent-Child Architecture

```
┌─────────────────────────────────────────────────────────┐
│  PARENT (stored in Qdrant payload, NOT indexed)         │
│  = surrounding 5-10 verses + chapter introduction       │
│  → Passed to LLM at generation time for full context    │
└─────────────────────────────────────────────────────────┘
        ▲ pointer
┌─────────────────────────────────────────────────────────┐
│  CHILD (indexed as vector)                              │
│  = single verse + contextual prefix                     │
│  → Used for precise retrieval matching                  │
└─────────────────────────────────────────────────────────┘
```

**Why this matters:** Gita verse 2.47 ("karmaṇy evādhikāras te") only makes full sense in the context of verses 2.39-2.53 (the Buddhi Yoga section). The LLM needs that flow to give a deep answer, but retrieval needs the single verse for precision.

**Implementation:** Each Qdrant point stores:
- `vector`: embedding of contextual child chunk
- `payload.text`: the verse text
- `payload.parent_text`: surrounding 5-10 verses (stored, not embedded)
- `payload.metadata`: all schema fields (scripture, chapter, verse, tradition, etc.)

#### 3. Query Decomposition (for Cross-Tradition Queries)

When user asks: "How do Advaita Vedanta and Buddhism differ on the nature of self?"

```
Original query
    │
    ├── Sub-query 1: "Advaita Vedanta teaching on the Self (Atman)"
    │   └── filter: tradition = hindu_vedanta
    │
    ├── Sub-query 2: "Buddhist teaching on non-self (anatta)"
    │   └── filter: tradition = buddhist
    │
    └── Synthesize: LLM compares retrieved chunks side-by-side
        with explicit tradition labels
```

This prevents the dangerous failure of retrieving only one tradition and presenting it as the full picture.

#### 4. HyDE (Hypothetical Document Embeddings) for Abstract Queries

For well-being queries like "I'm going through a difficult time and feeling lost":

```
Step 1 — Generate hypothetical answer (fast, 8B model):
  "Ancient texts suggest that suffering arises from attachment and 
   identification with the impermanent. The Gita teaches equanimity 
   in the face of pleasure and pain. The Dhammapada teaches that 
   the mind creates its own suffering..."

Step 2 — Embed THIS hypothetical answer (not the raw question)

Step 3 — Retrieve verses that match the hypothetical answer's embedding
  → Gets BG 2.14, AG 15.3, Dhp 1-2 (much better matches than raw query)
```

**When to use HyDE:** Only for abstract/emotional queries. For direct questions like "What is Gita 2.47?" — use BM25 direct match, no HyDE needed. The query analysis step routes this.

### Combined Pipeline (at query time)

```
User Query
    │
    ▼
┌────────────────────────────────────────┐
│  Query Analysis (fast, rule-based)     │
│  ├── Direct verse lookup? → BM25 only │
│  ├── Conceptual question? → HyDE      │
│  ├── Cross-tradition? → Decompose     │
│  └── Well-being/abstract? → HyDE      │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  Hybrid Retrieval                      │
│  ├── Dense: bge-m3 on contextual       │
│  │   chunks (cosine similarity)        │
│  ├── Sparse: BM25 on contextual        │
│  │   chunks (exact term match)         │
│  └── Metadata filter: tradition,       │
│      scripture, chapter (if detected)  │
│  Result: top-20 candidates             │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  Re-ranker (cross-encoder)             │
│  Score top-20 → select top-5           │
│  Diversity: max 2 from same chapter    │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  Parent Expansion                      │
│  For each top-5 child chunk:           │
│  → Fetch parent_text (5-10 verses)     │
│  → Pass PARENT context to LLM          │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  LLM Generation                        │
│  - Sees full parent context            │
│  - Citation-required prompting         │
│  - Tradition-labeled output            │
│  - Multi-translation awareness         │
└──────────────┬─────────────────────────┘
               │
               ▼
         Final Response
```

### Multiple Translations Strategy

When multiple free translations of the same text exist (e.g., Arnold + Telang for Gita):

1. **Ingest ALL translations** — each gets its own chunks with different `translator` field
2. **Retrieve the best match** — the contextual embedding picks the most relevant translation for the query
3. **Show alternatives** — after the primary response, offer: "Also available in: [Edwin Arnold, 1885] | [K.T. Telang, 1882]"
4. **Never blend without disclosure** — if showing multiple translations of the same verse, always label which is which

### Corpus Expansion Strategy

**Phase 1 (done):** 979 chunks (3 texts) — validates pipeline
**Phase 2 target:** ~20,000 chunks — expand to:
  - All 10 principal Upanishads (Müller SBE)
  - Brahma Sutras (Thibaut SBE, 2 commentary versions)
  - Yoga Sutras (Johnston + Vivekananda)
  - Gita Telang translation (SBE Vol. 8) — second translation
  - Vivekananda Complete Works (8 volumes)
  - SuttaCentral full Nikāyas (Sujato CC0 — already cloned, just needs parsers)
  - Manu Smriti (Bühler SBE Vol. 25)
  - Thirukkural (Pope 1886)

**Phase 3 target:** ~100,000+ chunks — everything in DATA-SOURCES.md:
  - Mahabharata philosophical parvas (Ganguli)
  - Ramayana (Griffith + Dutt)
  - All four Vedas (Griffith)
  - Puranas (Bhagavatam, Vishnu, Devi Bhagavata)
  - Jain sutras (Jacobi SBE)
  - Guru Granth Sahib
  - Shankaracharya complete minor works (GRETIL Sanskrit)
  - accesstoinsight.org commentary library

**Qdrant capacity:** 200K chunks × 1024-dim bge-m3 ≈ 1.5 GB. Well within VPS limits.

**Parser scaling strategy:** Each source format needs its own parser, but they all output the same `ScriptureChunk` schema. The incremental pipeline handles new sources without re-embedding existing ones.

---

## 4. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Embeddings | `BAAI/bge-m3` (self-hosted) | Multilingual, handles Sanskrit transliteration, open source — run once at ingestion on Colab (free), run at query-time on same VPS as backend |
| Vector DB | Qdrant Cloud free tier → self-hosted on $6 VPS | Hybrid search (dense + sparse), metadata filtering, 1GB free covers full Phase 1+2 corpus |
| Keyword index | Qdrant sparse vectors (built-in) | BM25 for exact verse number / Sanskrit term lookup — no extra service |
| **LLM — Deep queries** | **Groq + Llama 4 Scout 17B** | **⚠️ CORRECTED (Opus 4): 1,000 req/day free (NOT 14,400), 30,000 TPM. Reserve for philosophical reasoning, tradition comparison, distress queries.** |
| **LLM — Simple queries** | **Groq + Llama 3.1 8B Instant** | **14,400 req/day free, 6,000 TPM. Verse lookups, daily wisdom, FAQ. RAG context does the heavy lifting; 8B is adequate for synthesis.** |
| **LLM — At limit** | **Graceful daily limit message** | **⚠️ CHANGED (Opus 4): No Gemini overflow — privacy concern for well-being product. Show cached wisdom + "come back tomorrow."** |
| Orchestration | LlamaIndex | Better document chunking for structured religious texts than LangChain |
| Observability | LangFuse Cloud (Hobby, free) | 50K traces/month, $0. Track failed retrievals, citation misses, latency. Replaces manual eval infra. |
| Scraping (HTML sources) | Crawl4AI | Clean markdown extraction from sacred-texts.com, Wikisource. Not needed for Gutenberg (.txt) or SuttaCentral (JSON). |
| Chunking | `chunking-strategy` (user's library, editable) | Custom scripture parsers using BaseChunker. Sentence/paragraph strategies for prose. |
| Structured output (optional) | Instructor | NOT mandatory for MVP. Add only if LLM consistently fails to return valid JSON for citation schema or entailment checks. Pydantic + Groq JSON mode is the default path. |
| Backend | FastAPI (Python) | Async, clean, standard |
| Cache | Redis (Upstash serverless free tier) | Cache frequent verse lookups — top 1,000 queries cost $0 after first hit |
| Auth | Supabase Auth (free tier) | Free up to 50,000 MAUs, handles social login |
| Web frontend | Next.js 14+ (App Router) | SSR for SEO, React ecosystem |
| Mobile | React Native (Expo) | Single codebase for iOS + Android |
| Hosting (backend + Qdrant + bge-m3) | Single Hetzner VPS CX22 (~$6/month) | 4 vCPU, 8GB RAM — runs FastAPI + Qdrant + bge-m3 query inference comfortably |
| Hosting (web) | Vercel (free tier) | Next.js native, free forever for a personal/small project |
| Domain / CDN | Cloudflare | Free CDN, DDoS, proxy — put in front of Hetzner VPS |

### LLM Routing Logic (CORRECTED — Opus 4, verified June 2026)

```
Incoming query
    │
    ├── Query complexity classification (by system — fast heuristic)
    │   │
    │   ├── SIMPLE (verse lookup, FAQ, daily wisdom, known-answer):
    │   │   └── Check Llama 3.1 8B headroom (14,400 RPD)
    │   │       ├── Available → Llama 3.1 8B Instant
    │   │       └── At limit → show "daily limit reached" + cached verse
    │   │
    │   └── DEEP (philosophical reasoning, tradition comparison, distress, multi-hop):
    │       └── Check Llama 4 Scout 17B headroom (1,000 RPD)
    │           ├── Available → Llama 4 Scout 17B
    │           └── At limit → fall back to 8B (if available) → else daily limit
    │
    └── BOTH at limit → "You've reached today's limit. Reflect on this verse: [cached]."
```

### Why Tiered Routing (Not Single Model)

| | Llama 3.1 8B | Llama 4 Scout 17B |
|---|---|---|
| Free req/day | **14,400** | **1,000** |
| TPM (free) | 6,000 | 30,000 |
| Reasoning quality | Adequate with strong RAG context | Strong — MoE architecture |
| Sanskrit term handling | Mediocre solo, fine with retrieved context | Better |
| **Role** | **Workhorse (simple queries)** | **Reserved (deep queries)** |

**Key insight:** With good RAG, the gap between 8B and 17B narrows dramatically. When you've already retrieved the exact verse + commentary, the model only needs to synthesize and present — not reason from scratch. The 8B model handles this well for 90% of queries. Reserve the 17B for the 10% requiring actual cross-tradition reasoning or multi-hop philosophical inference.

**Total daily capacity:** ~15,400 queries (14,400 simple + 1,000 deep). At 10 queries/user/day average = ~1,500 DAU supported on free tier alone.

### Free Infrastructure Cost Summary

| Component | Service | Cost/month |
|---|---|---|
| LLM (simple queries) | Groq free tier — Llama 3.1 8B (14,400 RPD) | $0 |
| LLM (deep queries) | Groq free tier — Llama 4 Scout 17B (1,000 RPD) | $0 |
| Vector DB | Qdrant Cloud 1GB free → self-hosted | $0 → $0 (included in VPS) |
| Embeddings (query) | bge-m3 on VPS | $0 (included in VPS) |
| Backend | Hetzner CX22 VPS | ~$6/month |
| Cache | Upstash Redis free tier | $0 |
| Auth | Supabase free tier | $0 |
| Web hosting | Vercel free tier | $0 |
| CDN | Cloudflare free | $0 |
| **Total** | | **~$6/month** |

**Capacity:** ~15,400 queries/day total (14,400 simple + 1,000 deep) = ~1,500 DAU at 10 queries/user/day.

**When to upgrade:** At sustained 1,500+ DAU, add a credit card for Groq Developer tier. Llama 4 Scout 17B paid = $0.11/M input + $0.34/M output. At 2K deep queries/day with 3K tokens each = ~$0.66/day = ~$20/month. Still very cheap. The 8B model at $0.05/M input is effectively free even at scale.

---

## 5. Data Strategy

**See `DATA-SOURCES.md` for the full registry.** This is the most important document.

### License tiers (from Sonnet 4.6 plan)

| Tier | Definition | Action |
|---|---|---|
| A | Public domain OR CC0 — commercially safe, no restrictions | Ingest immediately |
| B | Attribution required, share-alike, or license needs verification | Verify before ingesting; may restrict some derivative works |
| C | Non-commercial only (CC BY-NC or similar) | Use only if product is 100% free and non-commercial in operation (no paid access, ad-monetized access, or sponsor-gated features) |
| X | Copyright enforced — do not use | Never ingest |

### Source governance (from Codex 5.3 plan)

- Every chunk must carry a `license_tier` field
- Keep a machine-readable `source-allowlist.yaml` and `source-denylist.yaml`
- Every source must be verified and documented before any crawl job starts
- Include removal workflow: if a source later asserts copyright, all chunks from that source can be deleted by filtering on `source_url`
- Legal review required before ingesting any Tier B source into a commercial product

---

## 6. Phase Plan

### Phase 0 — Governance (Week 1)
- Finalize `DATA-SOURCES.md` with license verification for every source
- Create `source-allowlist.yaml` with ingestion rules and attribution obligations
- Create `source-denylist.yaml` with reasons
- Legal checklist: what counts as commercial use, which jurisdictions matter (India + US)

### Phase 1 — Data Pipeline (Weeks 2–3)
- Ingest Tier A corpus only (see DATA-SOURCES.md priority list)
- **Scrapers:** Gutenberg (.txt direct download), SuttaCentral (git clone JSON), sacred-texts.com + Wikisource (Crawl4AI → markdown)
- **Scripture parsers (3 separate, NOT one generic chunker):**
  - `gita_arnold_parser.py` — handles "Chapter N / Verse N" patterns in Arnold's translation
  - `ashtavakra_parser.py` — handles numbered couplets (no chapter headers in some editions)
  - `dhammapada_sujato_parser.py` — handles SuttaCentral JSON segment structure
  - All three output the same chunk schema (scripture, chapter, verse, translator, tradition, license_tier)
- Embed with bge-m3, store in Qdrant with BM25 sparse vectors
- Validate: can the system correctly retrieve "Gita 2.47" and "Ashtavakra Gita 1.3"?
- **Key insight:** Read 30 min of raw text from each source BEFORE writing parsers. Verse boundary patterns differ wildly.

### Phase 1.5 — VPS Provisioning (before any endpoint goes live)
- Provision Hetzner CX22 VPS (Ubuntu 22.04)
- Install Qdrant (Docker), configure systemd service
- Upload Qdrant snapshot from Colab embedding
- Set up Cloudflare Tunnel or nginx reverse proxy
- Configure .env on VPS with production Groq/LangFuse/Supabase keys
- Verify: Qdrant is accessible, bge-m3 loads on CPU, FastAPI starts

### Phase 2 — RAG Core (Weeks 3–4)
- FastAPI endpoints: query → retrieve → rerank → generate → validate citation
- **LangFuse tracing from day 1** — wire traces on the very first working endpoint. Every RAG call emits a trace. Do not defer.
- **Rate limiting (slowapi + Upstash Redis):** per-IP 60 req/hour anonymous, per-user 100 req/hour signed-in. Prevents single script from exhausting Groq budget.
- System prompt engineering: citation-required, tradition-aware, contemplative tone
- Entailment check: claim must be supported by retrieved chunk
- Citation verification: cited verse must exist in corpus before returning to user
- Mode router: citation vs well-being vs exploration

### Phase 3 — Safety Layer (Week 4)
- Crisis language classifier (stress, grief, suicidal ideation)
- Escalation responses with appropriate resources (iCall India: 9152987821, Vandrevala Foundation: 1860-2662-345)
- No medical or psychiatric claims in well-being mode
- Tradition-aware guardrails: don't blend Advaita reasoning into a Dvaita question

### Phase 4 — Web MVP (Weeks 5–6)
- Next.js chat interface with citation display
- **Scripture Library + Reading Mode** (see Section 18 below)
- **Daily wisdom (NO LLM call):** use `hash(date) % corpus_size` to pick one verse deterministically. LLM only called if user clicks "Tell me more." Saves ~365 LLM requests/year.
- User feedback on each response (thumbs up/down, "citation wrong" flag)
- Waitlist / invite-only beta

### Phase 5 — Validate (Weeks 6–8)
- 50+ real user queries across traditions, manually evaluated
- Eval metrics: citation precision, faithfulness score, unsafe response rate, p95 latency
- Iterate on chunking, prompting, retrieval before building mobile
- Confirm stable free-tier operations under daily limits (no monetization path in MVP)

### Phase 6 — Mobile (Weeks 8–12)
- React Native (Expo) app
- Push notifications for daily wisdom
- Offline cache for bookmarked verses
- Voice input (especially for older users)
- App Store + Play Store submission

### Phase 7 — Domain Adaptation (Post-PMF, Month 4+)
- RAFT fine-tuning only after: retrieval stable, 500+ real queries collected, specific behavioral gaps identified
- Improve Hindi/Sanskrit response quality and transliteration consistency (support already enabled from day 1)
- Community features: user-submitted questions, curated collections

---

## 7. Business Model

### Decided: 100% Free Product (Locked)

**The product is free from day one. No payment tier, no freemium, no paywalls.**

This is a deliberate decision with two major consequences:

1. **Some Tier C sources are usable with strict interpretation.** GRETIL Sanskrit originals, selected accesstoinsight.org and SuttaCentral NC translations are candidates if terms are respected. This requires per-source policy checks.

2. **⚠️ This decision is binding for source legality.** If monetization is ever introduced, Tier C material must be removed before rollout. The `license_tier` field exists to support this fast removal workflow.

**Cost math (free architecture):**
- LLM: $0 (Groq free tier, 14,400 queries/day)
- All other infra: ~$6/month (Hetzner VPS)
- Per-query cost: effectively $0 until sustained 200+ DAU

**Current policy:** no monetization planning in MVP. Focus remains on corpus quality, legal safety, retrieval quality, and user trust.

---

## 8. Infrastructure & Hosting

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  YOUR MACBOOK (development only)                            │
│  ├── Write code, test locally                               │
│  ├── Push to GitHub                                         │
│  └── Your laptop can be OFF — users never touch it          │
└──────────────────────────┬──────────────────────────────────┘
                           │ git push / deploy
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  HETZNER VPS CX22 (~$6/month) — THE CLOUD SERVER           │
│  4 vCPU, 8GB RAM, 40GB disk, public IPv4                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  FastAPI backend (serves /api/* endpoints)            │  │
│  │  Qdrant (vector DB — all embeddings stored here)      │  │
│  │  bge-m3 model (query-time embedding, CPU inference)   │  │
│  │  SQLite (/data/query_logs.db — anonymous analytics)   │  │
│  │  Cloudflare Tunnel / reverse proxy                    │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ API calls
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Groq API     │  │ Upstash      │  │ Supabase     │
│ (LLM, free)  │  │ Redis (free) │  │ Auth (free)  │
└──────────────┘  └──────────────┘  └──────────────┘

┌─────────────────────────────────────────────────────────────┐
│  VERCEL (free tier) — FRONTEND                              │
│  Serves antardarshan.com (Next.js)                          │
│  Calls Hetzner VPS API for all data                         │
└─────────────────────────────────────────────────────────────┘

USER FLOW:
User → antardarshan.com (Vercel) → /api/* (Hetzner VPS) → Groq (LLM) → Response
```

### Cost Table (MVP stage)

| Service | What it does | Cost/month |
|---|---|---|
| Hetzner CX22 VPS | Backend + Qdrant + bge-m3 + SQLite logs | ~$6 |
| Groq API — Llama 3.1 8B | Simple queries (14,400 RPD) | $0 (free tier) |
| Groq API — Llama 4 Scout 17B | Deep queries (1,000 RPD) | $0 (free tier) |
| Upstash Redis | Cache frequent verse lookups | $0 (free tier) |
| LangFuse Cloud (Hobby) | Observability — trace failures, latency, eval | $0 (free, 50K traces/month) |
| Supabase Auth | User login (50K MAU free) | $0 (free tier) |
| Vercel | Next.js frontend hosting | $0 (free tier) |
| Cloudflare | CDN + DDoS + domain proxy | $0 (free tier) |
| Domain (antardarshan.com or .ai) | Product domain | ~$1/month (~$12/year) |
| **Total** | | **~$6–7/month** |

### Data Storage on the VPS

| Data | Storage | Size estimate |
|---|---|---|
| Qdrant vector DB (all embeddings) | Disk on VPS | ~200 MB for Phase 1 corpus |
| SQLite query logs (anonymous) | `/data/query_logs.db` on VPS | <50 MB for first 100K queries |
| bge-m3 model weights (CPU) | Disk on VPS | ~2 GB |
| Raw corpus files (backup) | Disk on VPS | ~500 MB |
| **Total disk usage** | | **~3 GB of 40 GB available** |

**Daily capacity:** ~15,400 queries/day (14,400 simple + 1,000 deep) = ~1,500 DAU supported.

**Ingestion cost (one-time):** Run bge-m3 on Google Colab (free T4 GPU) to embed the full corpus. Save Qdrant snapshot. Upload to VPS. After that, query-time embedding runs on the VPS with CPU inference (~50ms per query — fast enough).

### RAM Budget (Hetzner CX22 = 8GB)

| Component | RAM usage |
|---|---|
| OS + systemd | ~1 GB |
| FastAPI backend | ~200 MB |
| Qdrant (Phase 1 index) | ~400 MB |
| bge-m3 (FP32, full) | ~2 GB |
| SQLite + misc | ~100 MB |
| **Total (Phase 1)** | **~3.7 GB (headroom: 4.3 GB)** |

**Phase 2 concern:** As corpus grows (Phase 2+), Qdrant index grows. By Phase 2 we may hit ~5-6GB total.

**Mitigation (back pocket — do NOT mix models):**
- ⚠️ You CANNOT use bge-small for queries if corpus was embedded with bge-m3. Vector spaces don't match. Same model must be used for both.
- **Option A (preferred):** Use ONNX-quantized bge-m3 (INT8) for query-time. ~500MB instead of 2GB. Minimal quality loss. Ingestion stays FP32 on Colab.
- **Option B:** Upgrade to Hetzner CX32 (16GB RAM, ~$12/month) when RAM pressure hits. Still very cheap.
- **Option C (nuclear):** Re-embed entire corpus with a smaller model (bge-base-en-v1.5, ~440MB). One-time Colab job + Qdrant snapshot re-upload.

### Incremental Indexing (Community Contributions)

**Design principle:** The ingestion pipeline supports incremental runs from day 1. New sources are added without re-embedding existing content.

**How it works:**

```
sources/
├── approved-sources.yaml     ← master list of all approved URLs + license tier
├── community/                ← PRs from contributors land here
│   └── new-source.yaml       ← contributor adds: URL, license proof, text name
└── ingestion-manifest.json   ← tracks what's already been ingested (URL → timestamp + chunk_count)
```

**Pipeline logic:**
```
1. Read approved-sources.yaml
2. Compare against ingestion-manifest.json
3. For each URL NOT in manifest:
   a. Download/crawl raw text
   b. Parse into verse-level chunks (using appropriate parser)
   c. Embed with bge-m3 (on Colab for batch, or VPS for small additions)
   d. Upsert into Qdrant (native operation — adds new points, doesn't touch existing)
   e. Update manifest: mark URL as ingested with timestamp + chunk count
4. Done. Existing embeddings untouched.
```

**Qdrant upsert is key:** Each chunk gets a deterministic ID = `hash(source_url + chapter + verse)`. If the same verse is re-ingested (e.g., source updated), it overwrites in place. No duplicates, no full reindex.

**Community contribution workflow (public GitHub repo):**
1. Contributor opens PR adding a YAML entry to `sources/community/`
2. Entry must include: text name, URL, license tier, license proof URL, tradition
3. Maintainer reviews license claim → merges if valid
4. Next pipeline run (cron every 3-7 days, or manual trigger) picks up new sources
5. Pipeline embeds + upserts only the new content
6. Contributor gets attribution in the app ("Contributed by @username")

**Example community contribution file:**
```yaml
# sources/community/yoga-vasistha-mitra.yaml
text_name: "Yoga Vasistha (Laghu)"
translator: "K. Narayanaswami Aiyer"
year: 1896
tradition: hindu_vedanta
license_tier: A
license_proof: "https://www.gutenberg.org/ebooks/10270"  # PD, pre-1928
source_url: "https://www.gutenberg.org/cache/epub/10270/pg10270.txt"
parser: gutenberg_verse  # which parser to use
contributor: "@github_username"
date_added: "2026-07-01"
```

### Environment Setup (.env)

Required before any pipeline or backend code runs:
```
GROQ_API_KEY=gsk_...                    # Free tier key from console.groq.com
QDRANT_URL=http://localhost:6333        # Local Qdrant on VPS (or Qdrant Cloud URL during dev)
QDRANT_API_KEY=                         # Only if using Qdrant Cloud
LANGFUSE_PUBLIC_KEY=pk-...              # From langfuse.com (free Hobby tier)
LANGFUSE_SECRET_KEY=sk-...             # From langfuse.com
SUPABASE_URL=https://xxx.supabase.co   # For auth
SUPABASE_ANON_KEY=eyJ...               # Public anon key
```

### Anonymous Query Logging (SQLite)

```sql
CREATE TABLE query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT NOT NULL,
    response_summary TEXT,
    citations_used TEXT,          -- JSON array: ["BG 2.11", "BG 2.13"]
    mode TEXT,                    -- citation | well_being | exploration | comparison
    model_used TEXT,              -- llama-3.1-8b | llama-4-scout-17b
    latency_ms INTEGER,
    thumbs_rating INTEGER,       -- NULL, 1 (up), -1 (down)
    tradition_detected TEXT,     -- hindu_vedanta | buddhist | jain | sikh
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- No user_id column. No IP. No session. Fully anonymous.
```

**Purpose:** Improve retrieval quality over time. Find gaps. Build eval dataset. Never linked to any user.

**Privacy guarantee:** Even if someone gains access to this DB, they cannot identify who asked what. There is no join path to a user.

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Hallucinated citations | Post-process: verify cited verse exists in DB before returning response |
| Mixing traditions incorrectly | Metadata filtering: if user asks Buddhist concept, filter retrieval to Buddhist corpus |
| Copyright violation | Tier A+C only; all sources in DATA-SOURCES.md; removal workflow in place via `source_url` filter |
| Groq rate limit during spikes | Redis cache cuts repeat query cost to zero; tiered model routing (14,400 simple + 1,000 deep); graceful daily limit message for edge cases |
| ~~Gemini privacy~~ | ~~REMOVED by Opus 4~~ — No Gemini overflow. Privacy > availability for a well-being product. Daily limit is acceptable. |
| Unsafe advice in well-being mode | Safety classifier + escalation layer; crisis language detection; no medical claims |
| Accidentally adding monetization | Legal tripwire: Tier C source check required before any paid feature ships |
| Groq model quality gap | Tiered: Scout 17B for deep queries, 8B for simple. If Scout quality still insufficient, upgrade to Groq paid + Llama 3.3 70B ($0.59/M input) — still cheap. |
| Scope creep | Ship Vedanta core first (Gita + 10 Upanishads + Ashtavakra Gita); add traditions iteratively |

---

## 10. What Makes This Defensible

1. **Data curation is the moat.** Anyone can plug texts into a vector DB. The value is: verse-level chunking, translator provenance, cross-tradition tagging, and reliable citation verification.
2. **Retrieval + prompt tuning is the second moat.** Getting an LLM to reason *within* a philosophical framework rather than *about* it takes careful iteration.
3. **Safety design for well-being use case.** Most LLMs are not designed for users in distress. A well-designed escalation layer and empathy-first prompting creates real trust.
4. **Long tail advantage.** RAG outperforms fine-tuning specifically on long-tail, less-popular knowledge (per EMNLP 2024 research). Manu Smriti, Ribhu Gita, Tripura Rahasya — this is exactly where RAG shines and generic LLMs fail.

---

## 11. Immediate Next Steps (before any code)

1. Finalize `DATA-SOURCES.md` with legal confidence labels and ingestion status (`approved`, `blocked`, `needs_permission`)
2. Freeze a Phase 1 corpus shortlist (20-40 sources max) with direct URLs and license proof references
3. ✅ ~~Decide LLM~~ — **Decided: Groq tiered routing — Llama 4 Scout 17B (1,000 RPD, deep) + Llama 3.1 8B (14,400 RPD, simple). No Gemini.**
4. ✅ ~~Commercial or free?~~ — **Decided: 100% free forever with daily limits.**
5. ✅ ~~Hindi support?~~ — **Decided: Yes from day 1.**
6. ✅ ~~Multi-commentary handling?~~ — **Decided: primary translation + expandable alternatives.**
7. Start implementation only after user + all 3 LLMs mark agreement blocks as complete

---

## 12. Open Questions (to resolve before implementation)

- [x] ~~**LLM choice**~~ — **Resolved: Tiered routing — Llama 4 Scout 17B (1,000 RPD, deep) + Llama 3.1 8B (14,400 RPD, simple). No Gemini overflow (privacy concern). Corrected by Opus 4.**
- [x] ~~**Start commercial or free?**~~ — **Resolved: 100% free from day 1**
- [x] ~~**Hindi support from day 1 or V2?**~~ — **Resolved by Opus 4: YES from day 1.** bge-m3 handles Hindi natively. Accept Hindi/Hinglish queries. Embed Sanskrit originals in Devanagari. Respond in user's language.
- [x] ~~**Who runs the ingestion pipeline?**~~ — **Resolved: Google Colab (free) for one-time bge-m3 embedding. Hetzner VPS for query-time inference.**
- [x] ~~**How to handle multi-commentary?**~~ — **Resolved by Opus 4: Show primary translation by default. Expandable "Other perspectives" below. Mode-dependent (citation mode = mention others; comparison mode = show all side by side; exploration mode = user picks school).**
- [ ] **Final Phase 1 ingest list:** exact 20-40 sources with legal status = `approved` *(resolves naturally during Step 2 — DATA-SOURCES.md priority list already defines the order; this becomes `approved-sources.yaml` at scaffold time)*
- [x] ~~**Attribution template:**~~ **Resolved (Opus 4 handles during ingestion).** Every Tier B/C chunk carries attribution in metadata. Display format: "Source: [Scripture], [Translator] ([Year]) — [License note]"
- [ ] **GRETIL verification:** Spot-check 10 individual files during Step 2 to confirm CC BY-NC-SA. *(Not a blocker — GRETIL texts are Phase 2/3, not Phase 1 core.)*
- [x] ~~**Manu Smriti content policy:**~~ **Resolved (User agrees with Opus 4 proposal).** Present text with historical context. Do not present caste/gender hierarchy verses as prescriptive guidance. System prompt: "When citing Manu Smriti verses on social hierarchy, note the historical period (~200 BCE–200 CE) and that these reflect the social norms of that era, not universal spiritual guidance."
- [x] ~~**Daily limit UX:**~~ **Resolved (User decision).** Show remaining query count explicitly. Display: "Simple queries: X/14,400 remaining | Deep queries: Y/1,000 remaining | Resets in: HH:MM." Decrement visibly on each use.
- [x] ~~**Product name:**~~ **Resolved: AntarDarshan (अन्तर्दर्शन) — "inner vision/insight." Domain: antardarshan.com or antardarshan.ai**
- [x] ~~**User data storage:**~~ **Resolved (below).** No user query storage in MVP. Anonymous analytics only. Optional conversation history in V2 (user-controlled, deletable).

---

## 13. Execution Sprint Plan (Agreed Next)

### Step 0 — Pre-flight (30 min)
- Confirm chunking library fixes are complete.
- Install local editable package: `pip install -e ./chunking`.
- Verify import path: `python3 -c "from chunking_strategy import ChunkerOrchestrator; print('OK')"`.

### Step 1 — Project Scaffold (1 hour)
- Finalize repository layout:
  - `ingestion/scrapers/` (`gutenberg.py`, `sacred_texts.py`, `suttacentral.py`)
  - `ingestion/chunkers/scripture_verse_chunker.py`
  - `ingestion/pipeline.py`
  - `ingestion/config.yaml`
  - `corpus/raw/` and `corpus/processed/`
  - `backend/` (placeholder for Phase 2 FastAPI)
  - `eval/` (benchmark queries + scoring scripts)
- Add legal control files in scaffold:
  - `source-allowlist.yaml`
  - `source-denylist.yaml`
  - `source-manifest.yaml` (`license_tier` + `ingestion_status`)

### Step 2 — Pull 3 Core Texts (1-2 hours)
- Ingest only clean/high-confidence starters:
  1. Ashtavakra Gita (John Richards PD) — canonical proof from WisdomLib; raw text from current reachable mirror
  2. Bhagavad Gita (Arnold) — Project Gutenberg #2388
  3. Dhammapada (Sujato CC0) — SuttaCentral GitHub
- Store untouched artifacts in `corpus/raw/` with source and license proof metadata.

### Step 3 — Build `ScriptureVerseChunker` (2-3 hours)
- Create custom chunker extending `BaseChunker`.
- Parse verse boundaries per-source format.
- Emit full metadata schema for every chunk:
  - `scripture`, `chapter`, `verse`, `translator`, `tradition`, `license_tier`, `source_url`
- Register with `@register_chunker` so it works via orchestrator pipeline.

### Step 4 — Embed + Load Qdrant (1-2 hours)
- Use bge-m3 on Colab T4 for Phase 1 chunks.
- Persist Qdrant snapshot and load locally for retrieval validation.

### Step 5 — Retrieval Validation (1-2 hours)
- Run 25-50 benchmark queries.
- Verify citation accuracy and verse retrieval correctness (e.g., Gita references, Ashtavakra self-queries).
- Tune chunking + metadata before corpus expansion.

### Pre-Execution Locks (must resolve before Phase 2 corpus expansion)

1. **Ashtavakra reproducibility lock:** Canonical source = John Richards PD declaration (wisdomlib.org). Fetched artifact = tamilnation.co mirror. Store file hash in `ingestion-manifest.json` so all agents ingest the exact same text.
2. **Gray-source policy:** All `X/Verify` and legal-gray entries (Ramana Maharshi, Swami Sivananda, Project Madurai) are **excluded from first public launch.** Only sources with explicit `approved` status appear in the product.
3. **Phase 2 priority list (P0):** Lock one ordered list for next corpus sprint — Upanishads (Müller SBE), Yoga Sutras (Johnston), Gita Telang, Vivekananda Vol. 1-2. This is the convergence point for all implementation work.

---

## LLM Agreements / Amendments

> Each LLM should add its name, the date reviewed, and either ✅ agree or specific amendments.

**Claude Sonnet 4.6** (author of this synthesis) — 2026-06-15, updated 2026-06-16 (v3)  
✅ Agrees with full plan including all amendments. **Additions this pass:** Section 15 (corpus scope — go broad, 350K chunk target), Section 16 (non-generic RAG architecture — HyDE, multi-query, tradition-partitioned retrieval, Sanskrit BM25 boost, context expansion). **CRAG-lite elevated** from Codex's review into main RAG pipeline (Step 7b) — critical for citation trust. **Reading Mode:** approved for MVP, with 3 critical implementation fixes (query budget accounting, "Explain this" direct lookup bypass, bookmark UPSERT schema fix) and 1 addition (shareable verse URLs for organic sharing). **Puranas:** data additions correct, Vayu Purana verify-flag maintained.

**Claude Opus 4** — 2026-06-15  
⚠️ **AGREES WITH AMENDMENTS.** Key corrections and additions below:

### Amendment 1: CRITICAL — Groq Free Tier Numbers Are Wrong

The plan states Llama 4 Scout 17B gets 14,400 req/day. **This is incorrect.**

Verified from Groq docs and multiple sources (June 2026):

| Model | RPM | RPD | TPM | TPD |
|---|---|---|---|---|
| llama-3.1-8b-instant | 30 | **14,400** | 6,000 | 500,000 |
| meta-llama/llama-4-scout-17b-16e-instruct | 30 | **1,000** | 30,000 | 500,000 |
| llama-3.3-70b-versatile | 30 | **1,000** | 12,000 | 100,000 |
| openai/gpt-oss-120b | 30 | **1,000** | 8,000 | 200,000 |
| qwen/qwen3-32b | 60 | **1,000** | 6,000 | 500,000 |

**Impact:** 1,000 RPD on Scout 17B means only ~1,000 philosophical queries/day total on the best free model. NOT 14,400.

**Revised LLM strategy (Opus 4 proposal):**

Use a **tiered model routing** approach:

```
Incoming query
    │
    ├── Query type analysis
    │   ├── Simple verse lookup / daily wisdom / FAQ
    │   │       └── Llama 3.1 8B Instant (14,400 RPD, good enough with strong RAG context)
    │   │
    │   ├── Deep philosophical question / tradition comparison / distress guidance
    │   │       └── Llama 4 Scout 17B (1,000 RPD, reserve for quality-critical queries)
    │   │
    │   └── Both at limit → "Daily limit reached" message (NO Gemini fallback — see Amendment 2)
```

**Why this works:** RAG does 80% of the work. For a simple "what does Gita 2.47 say?" query, the 8B model is perfectly adequate when you've already retrieved the exact verse + commentary. Reserve the 17B MoE model for queries requiring actual reasoning across traditions.

**Total effective daily capacity:** ~15,400 queries (14,400 simple + 1,000 deep). More than enough for MVP and early growth.

**When to upgrade:** At sustained 200+ DAU, add a credit card for Groq Developer tier. Llama 4 Scout 17B on paid = $0.11/M input + $0.34/M output — roughly $0.0003/query for a 500-token response with 2K context. Still nearly free.

### Amendment 2: Remove Gemini Overflow — Privacy Concern

The plan uses Gemini 2.5 Flash-Lite as overflow with a "data training disclosure." I disagree with this for a **well-being product** where users share personal distress.

**Problem:** A user says "I'm anxious about my father's death, what does the Gita say about grief?" — routing this through Gemini's free tier (where Google may use prompts for training) is an ethical and trust violation, even with disclosure.

**Replacement:** When both Groq models are at limit, show a graceful message:
- "You've reached today's limit. Here's a verse to reflect on: [cached daily wisdom]. Come back tomorrow."
- Or queue the query for next reset (Groq resets daily, not monthly).

**No overflow LLM needed.** The tiered approach (14,400 + 1,000) gives 15,400 queries/day. If that's not enough, you have a good problem — upgrade to Groq paid tier ($0.11/M tokens, still nearly free).

### Amendment 3: Additional Data Sources Missing

The following are missing from DATA-SOURCES.md and need to be added:

1. **Manu Smriti (Laws of Manu)** — Georg Bühler, SBE Vol. 25 (1886) — Tier A. This was in the user's original request. One of the most important Dharmashastra texts.
2. **Thirukkural** — G.U. Pope (1886) — Tier A. Tamil philosophical masterpiece, 1330 couplets on virtue, wealth, and love. Available on Internet Archive and Project Madurai.
3. **Arthashastra** — R. Shamasastry (1915) — Tier A. Kautilya's treatise on statecraft and philosophy of governance.
4. **Sutta Nipata** — V. Fausböll, SBE Vol. 10 Part 2 (1881) — Tier A. Among the oldest Buddhist texts.
5. **Institutes of Vishnu** — Julius Jolly, SBE Vol. 7 (1880) — Tier A.
6. **Shankaracharya minor works** (Atmabodha, Aparokshanubhuti, Bhaja Govindam, Tattva Bodha) — Sanskrit on GRETIL (Tier C, usable), some old English translations on Internet Archive.
7. **Panchadasi** (Vidyaranya) — available on wisdomlib.org, verify translator/license.

I have updated DATA-SOURCES.md separately with full details.

### Amendment 4: Hindi from Day 1 — Yes

bge-m3 handles Hindi natively. The question in "Open Questions" about Hindi support should be resolved: **include Hindi originals from Phase 1 where available.** Many users will ask questions in Hindi or Hinglish. The embedding model handles it; the retrieval won't break. The LLM (Llama models) handles Hindi well.

Specifically:
- Embed Sanskrit originals (GRETIL) — helps when users type Sanskrit terms in Devanagari
- Accept queries in Hindi — bge-m3 handles this out of the box
- Response language: follow the user's query language (if they ask in Hindi, respond in Hindi)

### Amendment 5: "Free Forever" Framing

The user said "completely free forever with daily limits." The plan should reflect this more precisely:
- **Free**: no payment ever required to use the product
- **Daily limit**: when LLM quota is exhausted for the day, users wait until next day
- **Not "free as in no cost to us"**: we still pay ~$6/month VPS. If costs grow, accept transparent donations (not tied to features) OR apply for open-source grants (Anthropic's, Google's, etc.)
- **Tier C sources remain safe** as long as donations never gate access to features

### Amendment 6: Multi-Commentary Handling (Resolving Open Question)

For the open question "How to handle multi-commentary on same verse?" — my recommendation:

**Show the primary translation by default. Offer expandable "Other perspectives" below.**

```
User: "What does Brahma Sutra 1.1.1 mean?"

Response:
"Athāto brahma-jijñāsā — Now, therefore, the enquiry into Brahman."

[Shankara's reading]: The word "now" indicates that... [Advaita interpretation]

▼ Other commentaries on this sutra:
  • Ramanuja: [Vishishtadvaita reading]
  • Madhva: [Dvaita reading]
```

Tag each commentary chunk with `commentator` field. Let the mode router decide:
- Citation mode: show primary translation, mention others exist
- Tradition comparison mode: show all side by side
- Exploration mode: let user pick their school preference

### Summary of Opus 4 Position

| Item | Status |
|---|---|
| Architecture (RAG first) | ✅ Fully agree |
| Data governance (tier system, removal workflow) | ✅ Fully agree |
| Free product decision | ✅ Fully agree |
| Tier C unlocked | ✅ Fully agree |
| Groq as primary LLM provider | ✅ Agree — but numbers must be corrected |
| Llama 4 Scout 17B as sole model | ❌ Disagree — use tiered routing (8B for simple, 17B for deep) |
| Gemini as overflow | ❌ Disagree — privacy risk for well-being product; use graceful daily limit instead |
| bge-m3 for embeddings | ✅ Agree (better than my original text-embedding-3-large suggestion for a free product) |
| LlamaIndex over LangChain | ✅ Agree (better structured document support) |
| Qdrant for vector DB | ✅ Agree |
| $6/month Hetzner VPS | ✅ Agree — this is the right call |
| Phase plan ordering | ✅ Agree |
| Safety/escalation layer | ✅ Agree — critical for well-being use case |
| Entailment check | ✅ Agree — prevents hallucinated claims |

---

**OpenAI Codex 5.3** — 2026-06-15  
✅ **AGREES WITH AMENDMENTS.** Core alignment:

1. **Data-first gate is mandatory.** No implementation until `DATA-SOURCES.md` has a locked shortlist with legal confidence and ingestion status.
2. **Free-forever policy is accepted and reflected.** Remove freemium/payment planning from MVP scope.
3. **Tier C requires stricter interpretation.** "Free app" alone is not sufficient for every source; enforce per-source ToS checks and avoid broad assumptions.
4. **Do not use social-media transcript scraping.** Platform ToS and source rights are too risky for this product.
5. **Architecture is correct.** RAG-first + citation verification + entailment + safety layer is the right design for this domain.
6. **Vendor lock-in mitigation needed.** Keep model provider adapter from day 1 so Groq, Anthropic, or OpenAI can be swapped without re-architecting retrieval.
7. **Phase 1 scope must stay narrow.** Launch with high-confidence canonical corpus first, then expand.

**User** — 2026-06-16  
✅ **AGREES.** Decisions made:
- Product name: **AntarDarshan** (अन्तर्दर्शन)
- Manu Smriti: historical context approach (Opus 4 proposal accepted)
- Daily limit UX: show explicit count + reset timer (not graceful degrade)
- GRETIL: proceed with Opus 4's spot-check approach
- Attribution: Opus 4 handles during ingestion
- Project Madurai: use if 90%+ legally safe, drop if risky
- User data: no query storage in MVP, anonymous analytics only

---

## 13. Resolved: User Data Storage Policy

**Decision:** Do NOT store user queries in the database for MVP.

**Rationale:**
- Users share personal distress (grief, anxiety, life decisions) — logging this violates trust
- India's DPDP Act (2023) and GDPR create compliance overhead for personal data
- Tier C source licenses may prohibit data collection for model improvement
- Aligns with "privacy > availability" principle (same reason we removed Gemini overflow)

**What we DO store (anonymous, no PII):**
- Aggregate topic counts (which scriptures/themes are most queried)
- Thumbs up/down per response (to identify weak retrieval areas)
- Error rates, latency metrics (operational health)

**What we DON'T store:**
- User query text
- Conversation history
- User IP or device fingerprint beyond session

**V2 (post-PMF):** Add optional conversation history — user-controlled, user can delete anytime, stored only if they explicitly opt in. Never used for pretraining.

---

## 14. Resolved: Project Madurai Licensing

**Decision:** SAFE TO USE. The Thirukkural text (G.U. Pope, 1886) is public domain regardless of Project Madurai's hosting.

**Reasoning:**
- The underlying translation is from 1886 (author died 1908) — unambiguously PD worldwide
- Project Madurai's terms say "freely distribute, keep header intact" — this applies to their digitized file format
- We can alternatively source the same PD text from Internet Archive (where it's marked `NOT_IN_COPYRIGHT`)
- Embedding text into a vector DB is transformative use — not redistribution of the original file
- **Action:** Source from Internet Archive instead of Project Madurai to avoid any ambiguity. Same text, cleaner provenance.

---

## 15. Corpus Scope Decision (Sonnet 4.6 — 2026-06-16)

**Decision: Go broad. Ingest all freely available PD/CC0 Indian philosophy texts across all traditions.**

### Why maximum corpus matters

The product's value is accessing depth that generic LLMs miss — Manu Smriti, Ashtavakra Gita, Ribhu Gita, the full Pali Canon. Every additional text strengthens this moat. The infrastructure handles it; the only cost is ingestion time (run on Colab).

### Realistic corpus size and infrastructure impact

| Phase | Texts | Est. chunks | Qdrant size |
|---|---|---|---|
| Phase 1 (done) | Gita (Arnold), Ashtavakra, Dhammapada | ~1K | ~4MB |
| Phase 2 | SBE translations, Vivekananda, Yoga Sutras, Sutta Nipata, Upanishads | ~20K | ~80MB |
| Phase 3 | Full Pali Canon (Sujato CC0), Ganguli Mahabharata (phil. parvas), GRETIL Sanskrit | ~200K | ~800MB |
| Phase 4 | Full Mahabharata narrative, Vedas, Sant tradition, Puranas | ~350K total | ~1.4GB vectors + ~700MB overhead |

**Full corpus fits on the Hetzner VPS** (40GB disk). RAM: ~2–3GB for Qdrant at full corpus + bge-m3 ONNX INT8 (~500MB) + FastAPI = ~4.5GB of 8GB. Fine.

**Qdrant Cloud free tier (1GB) won't hold Phase 3+.** Use self-hosted Qdrant on VPS from Phase 2 onwards — always planned.

### Multiple translations of same text: YES

Include all PD translations of major texts. Arnold + Telang + Besant for Gita, for example. Each captures different registers and interpretive angles. The `translator` field in the chunk schema handles this — same verse, different translator = different `chunk_id`, no collision. UI shows primary translation with "Other translations" expandable.

### Phased ingestion order (expanded)

**Phase 2 targets (next sprint after embedding Phase 1):**
1. All 10 principal Upanishads — Müller, SBE Vols. 1 & 15
2. Yoga Sutras — Charles Johnston (PG #2526) + Vivekananda's Raja Yoga commentary
3. Brahma Sutras + Shankara + Ramanuja commentaries — Thibaut, SBE
4. Vivekananda Complete Works (8 volumes) — Wikisource
5. Sutta Nipata — Fausböll, SBE (oldest Buddhist text) + Sujato CC0
6. Bhagavata Purana Books 1, 2, 11 — J.M. Sanyal
7. Manu Smriti — Bühler, SBE Vol. 25
8. Thirukkural — G.U. Pope, Internet Archive
9. Jain sutras — Jacobi, SBE Vols. 22 & 45
10. Dhammapada Müller (SBE) as second translation alongside Sujato
11. Vivekachudamani — Madhavananda (1921, Internet Archive)
12. Gita — Telang translation (SBE Vol. 8) as second translation alongside Arnold

**Phase 3 targets:**
1. Full Pali Canon — Sujato CC0 (bilara-data GitHub, 100K+ segments)
2. Mahabharata philosophical parvas — Ganguli (Shanti, Udyoga, Anushasana parvas)
3. Sanskrit originals — GRETIL (CC BY-NC-SA, usable since product is free)
4. Arthashastra — Shamasastry (1915)
5. Minor Shankara works — Atmabodha, Aparokshanubhuti, Bhaja Govindam

**Specific teacher sources in scope:**
- Swami Vivekananda — Complete Works, fully PD ✅
- Sri Ramakrishna — Sayings (PG #9358, PD) ✅
- Swami Dayananda Saraswati — Satyarth Prakash (1875, PD) ✅
- Shankaracharya — minor works via GRETIL + old IA translations ✅
- Ramana Maharshi — pre-1931 publications (Upadesa Saram, Ulladu Narpadu) — **verify legal status first** ⚠️
- Madhvacharya — academic SBE-era translations where available (scarce)
- Ramanujacharya — via Thibaut's Brahma Sutra commentary (SBE) ✅

---

## 16. Custom RAG Architecture for AntarDarshan (Sonnet 4.6 — 2026-06-16)

**Decision: Do not use generic RAG. The pipeline is specifically designed for Indian philosophical text retrieval.**

### Why generic RAG fails here

1. **Sanskrit vocabulary mismatch**: A query with "Brahman" needs exact lexical matching, not semantic neighbors like "God" or "ultimate reality." Generic dense-only retrieval blurs this.
2. **Emotionally-phrased well-being queries**: "I'm grieving my father" contains zero philosophical vocabulary. Neither dense nor BM25 retrieves the correct grief-related shlokas without augmentation.
3. **Cross-tradition comparison**: "How does Advaita differ from Buddhism on consciousness?" requires parallel retrieval from two separate tradition partitions — a single retrieval call mixes results incorrectly.
4. **Context starvation**: Most verses are cryptic without 2–3 surrounding verses. Standard RAG returns only the matched chunk; the LLM then hallucinates context.

### The AntarDarshan retrieval pipeline

```
Query (EN / HI / SA / Hinglish)
    │
    ├── STEP 1: Fast pre-processing (rule-based, <10ms)
    │   ├── Detect direct verse reference (BG 2.47, Gita chapter 2 verse 47)
    │   │   └── YES → bypass vector search, direct Qdrant lookup by (scripture, ch, verse)
    │   ├── Detect Sanskrit terms → flag for BM25 weight boost (1.5×)
    │   ├── Detect tradition scope: all | specific school | cross-tradition
    │   └── Detect mode: citation | well_being | exploration | comparison
    │
    ├── STEP 2: Query expansion (mode-specific, adds retrieval signal)
    │   │
    │   ├── CITATION MODE → Multi-query decomposition
    │   │   "What does Gita say about karma and action?"
    │   │   → ["karma Bhagavad Gita", "nishkama karma", "action without attachment"]
    │   │   Retrieve each → merge with Reciprocal Rank Fusion (RRF)
    │   │
    │   ├── WELL-BEING MODE → HyDE (Hypothetical Document Embeddings)
    │   │   "I lost my father and feel lost"
    │   │   → Mini LLM call: generate a 2-sentence hypothetical philosophical passage
    │   │     "The soul is eternal and death is but a transition; grief arises from
    │   │      attachment to the impermanent form..."
    │   │   → Embed the hypothesis → search with it alongside original query
    │   │   → Dramatically improves recall for emotionally-phrased queries
    │   │   Note: use 8B for HyDE generation (costs 1 of 14,400 simple requests)
    │   │
    │   └── COMPARISON MODE → Parallel tradition-partitioned retrieval
    │       "How does Advaita differ from Buddhism on self?"
    │       → Query A: retrieve from hindu_vedanta partition
    │       → Query B: retrieve from buddhist partition (simultaneously)
    │       → Rerank each set independently
    │       → Present side by side with tradition labels — no mixing
    │
    ├── STEP 3: Hybrid retrieval (Qdrant native)
    │   ├── Dense vectors: bge-m3 cosine similarity
    │   ├── Sparse vectors: BM25 (Sanskrit terms boosted 1.5×)
    │   ├── Metadata filter: tradition, scripture, license_tier
    │   └── Merge: Reciprocal Rank Fusion — outperforms weighted sum
    │
    ├── STEP 4: Context window expansion (post-retrieval)
    │   ├── For each retrieved chunk, fetch the ±2 surrounding verses
    │   ├── Context verses injected into [CONTEXT] section of LLM prompt
    │   └── Only the matched verse is cited — context is background, not attributed
    │
    ├── STEP 5: Cross-encoder reranking (BGE-reranker-v2-m3)
    │   └── Top 20 candidates → Top 5–7 final chunks (run on VPS CPU, ~100ms)
    │
    ├── STEP 6: Generation (Groq, mode-specific system prompt)
    │   ├── Must only cite from retrieved context (hard constraint in prompt)
    │   ├── Citation format: Scripture, Chapter X, Verse Y (Translator, Year)
    │   └── Response language follows user's query language
    │
    └── STEP 7: Verification layer
        ├── Citation check: verify (scripture, ch, verse) exists in Qdrant before returning
        └── Entailment check: each factual claim must appear in retrieved chunk text
```

### Key technique: HyDE for well-being mode

This is the single most impactful technique for AntarDarshan beyond basic RAG.

Standard retrieval fails for: *"I'm scared about my father's health"* — there's no philosophical vocabulary to match against.

HyDE fixes this:
1. Ask 8B model: *"Generate a 2-sentence passage from Indian philosophy about fear and illness"*
2. Model produces: *"Fear arises from attachment to the transient body; the Gita reminds us that what is eternal cannot be touched by illness or death"*
3. Embed this passage → its vector IS close to relevant Gita verses about mortality, equanimity, and the eternal soul
4. Retrieve against this embedding — finds the right verses

Cost: 1 extra LLM call per well-being query (uses 8B simple budget). Worth it.

### Key technique: Tradition-partitioned parallel retrieval

For comparison mode, run TWO searches simultaneously with metadata filters:
- Search A: `filter: {tradition: "hindu_vedanta"}` → top 5 Vedantic results
- Search B: `filter: {tradition: "buddhist"}` → top 5 Buddhist results

Never merge these sets. Rerank each independently. Present labeled:
```
Advaita Vedanta says: [verse from Vivekachudamani]
Buddhism says: [verse from Dhammapada]
```

### Step 7b: CRAG-lite retrieval confidence check (critical — elevated from Codex review)

This is the most important safeguard for citation trust. The worst RAG failure for AntarDarshan is **confident wrong citation** — the LLM generates a plausible answer citing "Kena Upanishad 2.4" which doesn't exist or says the opposite. Users cannot verify this.

CRAG (Corrective RAG) adds a retrieval quality gate before generation:

```
After reranking → check retrieval confidence score
    │
    ├── Score HIGH (top chunk similarity > 0.75): proceed to generation normally
    │
    ├── Score MEDIUM (0.5–0.75): expand query + run second-pass retrieval
    │   └── If second pass improves score → proceed
    │
    └── Score LOW (< 0.5): DO NOT generate a cited answer
        └── Return: "I found references to related concepts but nothing that
             directly addresses your question in the corpus. The closest is:
             [verse] — does this help, or would you like me to explore further?"
```

This honest degradation is the correct behavior for a product built on citation trust. Never bluff when retrieval is weak.

**Implementation:** Use the reranker's confidence scores as the gate. BGE-reranker-v2-m3 returns normalized scores; anything below 0.5 on the top chunk indicates weak retrieval.

### What is NOT included (yet)

- **GraphRAG** (Microsoft): Designed for large narrative documents; overkill for verse-level structured texts. Revisit at Phase 3+ if cross-text relationship mapping becomes valuable.
- **ColBERT**: Token-level late interaction; better quality but requires Qdrant experimental support and more complex deployment. Add after MVP if retrieval quality gaps persist.
- **RAPTOR**: Hierarchical document summarization; add in V2 when corpus is large enough that book-level summaries add value (e.g., "summarize what the Mahabharata says about dharma").

### Implementation order

1. **Phase 1 RAG (MVP):** Hybrid retrieval + reranking + CRAG-lite confidence check + citation verification
2. **Add HyDE:** After testing shows well-being mode retrieval is weak on emotional queries
3. **Add parallel tradition retrieval:** When comparison mode is built
4. **Add GraphRAG/RAPTOR:** Post-PMF only if specific gaps identified

---

## 17. Codex 5.3 Review Update (2026-06-16)

### Verified current status (Steps 1-3)

- Confirmed in-repo: 3 parsers, 3 processed JSON outputs, single command orchestration (`python -m ingestion.process_phase1`).
- Confirmed chunk counts from processed artifacts: Bhagavad Gita (240) + Ashtavakra Gita (316) + Dhammapada (423) = **979 total**.
- Confirmed schema-level support for `verse_type` (`stanza | verse | segment`) is implemented and populated.

### Critical data/provenance correction

- `Project Gutenberg #10311` is not Ashtavakra Gita (currently Thomas Edison "Around the World on the Phonograph"). It must not remain in any "core ingest" execution checklist.
- For Ashtavakra, keep:
  - `license_proof_url`: public-domain declaration page
  - `source_url_canonical`: canonical edition landing/source page
  - `source_url_fetched`: actual mirror/file used for ingestion
- This prevents legal/audit drift when mirrors change but licensing remains tied to a canonical edition.

### Scope decision: "all free texts"

- Product direction is correct: **ingest all legally usable free texts**, not just a narrow shortlist.
- Execution policy is phased, not "all at once":
  1. Quality-locked core corpus (already underway)
  2. Major canon expansion (Upanishads, Vedanta sutra/commentary, major Buddhist corpora)
  3. Teacher corpus expansion (Vivekananda, Ramakrishna PD works, other approved sources)
  4. Community PR ingestion with strict approval gate
- Success metric for breadth: every approved source has `ingestion_status`, parser owner, and backlog priority (P0/P1/P2), so coverage becomes trackable rather than aspirational.

### Advanced RAG + SQL track (non-generic, product-specific)

- Keep vector RAG core, but add a **retrieval planner**:
  - `direct_reference` (e.g., "Gita 2.47") -> exact lookup path, skip semantic search
  - `semantic_question` -> hybrid dense+sparse retrieval + rerank
  - `comparison` -> parallel tradition-partition retrieval
  - `well_being` -> HyDE-assisted retrieval
- Add **SQL evidence layer** (Postgres/SQLite) for structured guarantees:
  - exact verse index (`scripture`, `chapter`, `verse`, `translator`, `verse_type`)
  - license/provenance tables for auditable citations
  - eval/query analytics tables for offline quality tuning
- Add **CRAG-lite retrieval validator** before generation:
  - score retrieval confidence
  - if confidence low, expand query / run second-pass retrieval
  - if still low, return explicit low-confidence response instead of bluffing
- This is the practical middle path: much stronger than naive cosine RAG, without premature GraphRAG complexity.

---

## 18. Scripture Library + Reading Mode (MVP Feature)

> **User decision (2026-06-16):** Include in MVP, not V2. Users can browse, read, bookmark, and get AI-assisted explanations while reading.

### Feature Description

The product has TWO main modes:
1. **Q&A Mode** (anonymous) — ask questions, get cited answers from across all traditions
2. **Reading Mode** (requires account) — browse scriptures, read sequentially, bookmark progress, ask AI to explain what you're reading

### Reading Mode UX Flow

```
Library Page (browse all scriptures)
    │
    ├── Filter by: Tradition | Language | Scripture
    │
    ├── Categories shown:
    │   ├── Vedanta (Gita, Upanishads, Brahma Sutras, Ashtavakra...)
    │   ├── Yoga (Yoga Sutras, Vivekananda's Raja Yoga)
    │   ├── Buddhist (Dhammapada, Nikāyas, Sutta Nipata)
    │   ├── Epics (Mahabharata philosophical sections, Ramayana)
    │   ├── Puranas (Vishnu, Bhagavata, Garuda, Markandeya, Agni)
    │   ├── Dharmashastra (Manu Smriti, Arthashastra)
    │   ├── Jain (Tattvartha Sutra, Uttaradhyayana)
    │   ├── Sikh (Guru Granth Sahib, Japji Sahib)
    │   └── Tamil (Thirukkural)
    │
    └── Click on a scripture → Reading View
        │
        ├── Sequential display: Chapter → Verses (one at a time or page)
        ├── [Bookmark] button → saves (user_id, scripture, chapter, verse)
        ├── [Explain this] button → sends verse + context to AI
        │   └── AI responds with meaning, Sanskrit terms, cross-references
        ├── [Next] / [Previous] navigation
        └── Resume reading: returns to last bookmarked position
```

### Privacy Model (Clear Separation)

| Feature | Stores user_id? | Stored where? | User action required? |
|---------|-----------------|---------------|----------------------|
| Q&A (ask a question) | NO | Anonymous SQLite log | None — just ask |
| Reading progress | YES | Supabase `bookmarks` table | Must sign up / log in |
| Bookmarks | YES | Supabase `bookmarks` table | Click "Bookmark" |
| Conversation history | NO (MVP) | Not stored | — |

**Explicit user consent:** "Sign up to save your reading progress. Your questions remain private and anonymous."

### Database Schema (Supabase, free tier)

```sql
-- Already have: auth.users (Supabase handles this)

-- Reading progress / bookmarks
CREATE TABLE bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    scripture TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    translator TEXT,
    bookmark_type TEXT DEFAULT 'progress',  -- 'progress' | 'saved' | 'highlight'
    note TEXT,  -- optional user note on the verse
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for quick "resume reading" lookup
CREATE INDEX idx_bookmarks_user_scripture ON bookmarks(user_id, scripture, bookmark_type);
```

**Size:** Each bookmark = ~200 bytes. 10K users × 20 bookmarks = ~40 MB. Supabase free tier (500 MB) still handles this comfortably for MVP.

### API Endpoints (FastAPI)

```
GET  /api/library                          → list all available scriptures + metadata
GET  /api/library/{scripture}              → chapter list for a scripture
GET  /api/library/{scripture}/{chapter}    → all verses in a chapter
GET  /api/library/{scripture}/{ch}/{verse} → single verse + surrounding context

POST /api/bookmarks                        → save bookmark (requires auth)
GET  /api/bookmarks                        → list user's bookmarks (requires auth)
GET  /api/bookmarks/resume/{scripture}     → get last reading position (requires auth)

POST /api/explain                          → AI explanation of a verse (anonymous, uses RAG)
```

### Cost Impact: No New Paid Infrastructure

- Scripture data is ALREADY in our corpus (same JSON files serve both RAG and reading)
- Bookmarks stored in Supabase free tier (already in stack)
- No new infrastructure needed
- The "Explain this" button is just a Q&A query with the verse pre-filled — same RAG pipeline
- Incremental cost exists only in query budget consumption (8B/17B limits), not in new services

### Why This Makes the Product Sticky

1. **Daily return habit:** User comes back to continue reading where they left off
2. **Account creation hook:** Reading progress is the only reason to create an account, since Q&A is anonymous. Without reading mode, Supabase Auth has no purpose at MVP.
3. **Deeper engagement:** Reading + AI explanation is more valuable than Q&A alone
4. **Content discovery:** Users find texts they didn't know existed
5. **Organic sharing:** Shareable verse URLs: `antardarshan.com/read/bhagavad-gita/2/47` — no account needed to view, opens directly to that verse. This is the viral sharing mechanism.
6. **Corpus validation:** If users actually READ the texts, we'll quickly find parsing errors or missing verses

### Critical Implementation Notes (Sonnet 4.6 — 2026-06-16)

**Fix 1: "Explain this" must count against daily query budget.**
The "Explain this" button is a simple query. It must decrement the 8B counter (14,400 RPD). A user clicking "Explain" every few verses during a reading session would otherwise exhaust a large portion of the day's capacity unaccounted for. Show the remaining query count in reading mode, same as Q&A mode.

**Fix 2: "Explain this" should NOT run full hybrid retrieval.**
When the user clicks "Explain this" on verse Gita 2.47 during reading, we already have the verse. Do not run vector search. Instead:
1. Fetch the verse + surrounding ±2 verses directly from Qdrant by exact `(scripture, chapter, verse)` lookup
2. Inject as context into the LLM prompt
3. Ask the model to explain

This is 5× faster and more accurate than semantic search on a known verse.

**Fix 3: Bookmark schema has an `updated_at` bug — must fix before implementing.**
Without a trigger, `updated_at` never updates. A user reading the Gita will accumulate hundreds of duplicate "progress" rows. Fix with UPSERT:
```sql
-- Use UPSERT for reading progress (one row per user per scripture)
INSERT INTO bookmarks (user_id, scripture, chapter, verse, bookmark_type)
VALUES ($1, $2, $3, $4, 'progress')
ON CONFLICT (user_id, scripture)
WHERE bookmark_type = 'progress'
DO UPDATE SET chapter = $3, verse = $4, updated_at = NOW();

-- Add unique constraint for this to work:
CREATE UNIQUE INDEX idx_progress_unique
ON bookmarks(user_id, scripture)
WHERE bookmark_type = 'progress';
```

**Add: Shareable verse URLs**
`antardarshan.com/read/{scripture-slug}/{chapter}/{verse}` must be a public, shareable URL. No account required to view. Account required to bookmark. Implement as a Next.js dynamic route with SSR (good for SEO — each verse gets its own page that search engines can index).

**Fix 4: Library catalog must be approval-gated.**
Only show sources with `ingestion_status = approved` in reading UI. Do not expose blocked/gray sources in browse lists. This keeps legal posture clean and avoids user confusion.

**Fix 5: Add Supabase RLS + data deletion requirements.**
`bookmarks` must enforce Row Level Security so users can access only their own rows. Also provide user-facing "Delete my reading data" endpoint that clears bookmarks/progress for privacy compliance and trust.

**Fix 6: Rate-limit /api/explain and reuse daily budget counters.**
Reading mode and Q&A mode must share one query budget ledger. Add per-user/IP rate limiting for anonymous explain calls to prevent free-tier exhaustion attacks.

### Go/No-Go recommendation

Reading Mode is feasible and valuable, but ship it with guardrails:
1. Legal gate (`approved` only catalog)
2. Auth gate (RLS + deletion endpoint)
3. Budget gate (shared counters + rate limit)

With these three in place, this feature is a real differentiator, not just UI polish.

