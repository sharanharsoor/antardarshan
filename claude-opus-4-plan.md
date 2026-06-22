# Indian Philosophy AI — Full Product Plan

**Model**: Claude Opus 4 (Anthropic)  
**Date**: June 15, 2026  
**Project**: Indian Philosophy AI — RAG-based product for deep philosophical guidance

---

## Overview

Build a RAG-based AI product specializing in Indian philosophy (Hindu, Buddhist, Jain, Sikh) that provides deep, citation-backed philosophical guidance using Claude API as the base model, deployed as a web app + mobile app with a freemium model.

---

## Architecture Decision: RAG + Claude API

**Why NOT fine-tuning:**
- Fine-tuning injects style, not knowledge. You need exact citations (verse numbers, chapter refs).
- A fine-tuned 7B model will hallucinate references and lose general reasoning ability.
- You'd be locked to one model forever. RAG lets you swap Claude for GPT-5 or whatever wins next year.

**Why RAG:**
- Verifiable citations: every answer can point to "Ashtavakra Gita 1.3" or "Kena Upanishad 2.4"
- Structured corpus: Indian philosophical texts are perfectly suited for retrieval (verse/chapter structure)
- Iterate on data independently of the model
- Cost-effective: only pay per query, no GPU rental

---

## Phase 1: Data Collection and Structuring (Week 1-3)

### Publicly Available / Public Domain Sources

**Hindu — Vedanta Core (ship first):**
- Bhagavad Gita (18 chapters, 700 verses) — sacred-texts.com, gitasupersite.iitk.ac.in
- Principal Upanishads (Isha, Kena, Katha, Prashna, Mundaka, Mandukya, Taittiriya, Aitareya, Chandogya, Brihadaranyaka) — multiple public domain translations
- Ashtavakra Gita (20 chapters) — freely available, multiple translations
- Yoga Vasistha (condensed version ~4000 verses) — Swami Venkatesananda's rendering
- Vivekachudamani (Shankaracharya) — public domain
- Brahma Sutras with Shankara Bhashya — sacred-texts.com

**Hindu — Broader:**
- Yoga Sutras of Patanjali (196 sutras + commentaries)
- Bhagavata Purana (selected philosophical sections: Books 1, 2, 11)
- Swami Vivekananda Complete Works (8 volumes, ~4000 pages) — freely on belurmath.org
- Gospel of Sri Ramakrishna — public domain
- Ribhu Gita, Avadhuta Gita, Tripura Rahasya — available on archive.org

**Buddhist:**
- Dhammapada (423 verses) — multiple PD translations
- Heart Sutra, Diamond Sutra — public domain
- Selections from Majjhima Nikaya / Digha Nikaya — accesstoinsight.org (freely redistributable with attribution)
- Nagarjuna's Mulamadhyamakakarika — academic translations available
- Bodhicaryavatara (Shantideva) — public domain translations exist

**Jain:**
- Tattvartha Sutra (Umasvati) — public domain
- Samayasara (Kundakunda) — available on jainworld.com
- Uttaradhyayana Sutra — sacred-texts.com

**Sikh:**
- Guru Granth Sahib — freely available on sikhitothemax.org, searchgurbani.com (Sikh community encourages sharing)
- Japji Sahib, Sukhmani Sahib — public domain

**Key crawl targets:**
- sacred-texts.com (massive public domain archive)
- wisdomlib.org (well-structured, multiple traditions)
- gitasupersite.iitk.ac.in (IIT Kanpur project, verse-by-verse with Sanskrit + translations)
- accesstoinsight.org (Buddhist Pali Canon, free for redistribution)
- swamij.com (Yoga Sutras, well-structured)
- archive.org (out-of-copyright books)

**CANNOT USE (copyrighted):**
- Osho talks — Osho International Foundation enforces aggressively
- Sadhguru talks — Isha Foundation owns all content
- Modern translations (Eknath Easwaran, etc.) — copyrighted

### Data Structure per Chunk

```json
{
  "text_name": "Ashtavakra Gita",
  "tradition": "hindu_vedanta",
  "chapter": 1,
  "verse": 3,
  "sanskrit": "...",
  "translation": "...",
  "commentary": "...",
  "commentator": "Swami Chinmayananda",
  "themes": ["self-knowledge", "liberation", "witness-consciousness"],
  "embedding": [...]
}
```

### Chunking Strategy

- **Primary chunk**: Single verse + its translation + commentary (typically 100-300 tokens)
- **Context window**: Include 2 verses before and after for retrieval context
- **Commentary chunks**: Longer commentaries split at paragraph boundaries, linked back to verse
- **Topical cross-references**: Tag verses with themes (suffering, karma, liberation, devotion, meditation, ethics) for metadata filtering

---

## Phase 2: RAG Pipeline (Week 3-5)

### Tech Stack

- **Embedding model**: OpenAI text-embedding-3-large (3072 dim) — best multilingual performance, handles Sanskrit transliterations
- **Vector DB**: Qdrant (self-hosted) or Pinecone (managed) — metadata filtering, hybrid search support
- **Keyword search**: BM25 via Qdrant's built-in sparse vectors — catches exact verse references that semantic search misses
- **Base LLM**: Claude Sonnet via API — best at nuanced reasoning, long context, respectful tone
- **Orchestration**: Python + LangChain (or raw implementation) — RAG pipeline, prompt management
- **Backend API**: FastAPI (Python) — async, fast, simple
- **Caching**: Redis — cache frequent queries, rate limiting

### Retrieval Strategy

```
User Query
    |
    v
[Query Analysis] — detect: tradition, text reference, theme, verse citation
    |
    v
[Hybrid Retrieval]
    |--- Semantic search (top 10 by cosine similarity)
    |--- Keyword/BM25 search (top 5, catches verse numbers)
    |--- Metadata filter (if tradition/text specified)
    |
    v
[Re-ranking] — cross-encoder reranker scores relevance
    |
    v
[Top 5 chunks → LLM context window]
    |
    v
[Claude API] — system prompt instructs citation format, philosophical depth
    |
    v
[Response with citations]
```

### System Prompt Design (critical for quality)

The system prompt will instruct the model to:
- Always cite source text, chapter, and verse
- Reason from the philosophical framework of the referenced tradition (don't mix Advaita reasoning with Dvaita texts)
- Provide Sanskrit/Pali terms with transliteration and meaning
- Be conversational but grounded — not preachy, not academic
- When the user is in distress, lead with empathy, then wisdom
- Never claim authority — present what the texts say, let the user internalize

---

## Phase 3: Product Build (Week 5-8)

### Web App

- **Framework**: Next.js 14+ (App Router)
- **UI**: Clean, minimal, warm aesthetic. Think calm.com meets philosophy.
- **Key pages**:
  - Chat interface (main product)
  - Browse texts (searchable library)
  - Daily wisdom (one verse/passage daily, shareable)
  - Bookmarks / saved conversations
  - About / traditions explained

### Mobile App

- **Framework**: React Native (Expo) — shared logic with web where possible
- **Key features**: Push notification for daily wisdom, offline saved bookmarks, voice input

### Freemium Model

- **Free tier**: 10 queries/day, basic chat, daily wisdom, browse library
- **Premium ($7-9/month)**: Unlimited queries, conversation history, deeper follow-ups, tradition-specific modes, export/share, no ads
- **Cost math**: At ~$0.02/query average (embedding + Claude API), 10 free queries/day = $0.20/user/day = $6/user/month. You need ~30-40% conversion to break even on free users.

---

## Phase 4: Deployment and Hosting (Week 8-10)

- **Backend (FastAPI)**: Railway / Render / AWS ECS — $20-50/month initially
- **Vector DB (Qdrant)**: Qdrant Cloud or self-host on Railway — $25-50/month
- **Redis**: Upstash (serverless) — $10/month
- **Web frontend**: Vercel (Next.js) — Free tier to $20/month
- **Mobile**: Expo EAS for builds, App Store / Play Store — $100/year (Apple) + $25 (Google)
- **Claude API**: Anthropic — Variable, ~$0.02/query
- **Domain + misc**: $15/year

**Total initial cost: ~$100-150/month** before any users. Scales with usage primarily through API costs.

---

## Phased Rollout

1. **MVP (Week 1-5)**: Vedanta core texts only (Gita + 10 Upanishads + Ashtavakra Gita + Yoga Vasistha). Web chat only. Invite-only beta.
2. **V1 (Week 5-8)**: Add Yoga Sutras, Vivekananda, Buddhist core texts. Public web launch. Freemium.
3. **V1.5 (Week 8-12)**: Mobile app. Jain + Sikh texts. Daily wisdom feature. Push notifications.
4. **V2 (Month 4+)**: Community features, user-submitted questions, curated collections, multi-language support (Hindi, Tamil, etc.)

---

## Risks and Mitigations

- **Hallucinated citations**: Post-processing — verify cited verse exists in DB before showing. Show "source not found" if unverifiable.
- **Mixing traditions incorrectly**: Metadata filtering — if user asks about Buddhist concept, only retrieve from Buddhist corpus.
- **Copyright issues with translations**: Use only pre-1930 translations or explicitly freely-licensed ones. Document provenance for every source.
- **High API costs at scale**: Cache popular queries in Redis. Use cheaper model (Haiku) for simple lookups, Sonnet for deep discussion.
- **Low conversion rate**: Make free tier genuinely useful. Paywall depth, not access.

---

## What Makes This Defensible

- **The data curation is the moat.** Anyone can plug texts into a vector DB. Your value is: proper chunking at verse-level, correct metadata, cross-references between traditions, and quality commentary selection.
- **The system prompt and retrieval tuning is the second moat.** Getting Claude to reason *within* a philosophical framework (not just about it) takes iteration.
- **Network effects later**: user questions become a dataset of "what people actually struggle with" — this informs better retrieval and content gaps.

---

## Immediate Next Steps

1. Crawl and structure 3-4 core texts (Gita, Ashtavakra Gita, Katha Upanishad, Dhammapada)
2. Build a minimal RAG pipeline with FastAPI + Qdrant
3. Test query quality manually with 50+ real questions
4. Iterate on chunking/prompting before building any UI

---

## Implementation Todos

- [ ] Identify and list all freely available source URLs for Phase 1 texts. Verify license/public domain status.
- [ ] Build Python scripts to crawl, parse, and structure texts into verse-level JSON with metadata.
- [ ] Set up embedding pipeline: chunk texts, generate embeddings, store in Qdrant with metadata.
- [ ] Build minimal RAG prototype: FastAPI endpoint → retrieve chunks → Claude API → cited response.
- [ ] Iterate on system prompt and retrieval quality. Test with 50+ real queries across traditions.
- [ ] Build Next.js web app with chat interface, text browser, and daily wisdom.
- [ ] Add authentication (Clerk/NextAuth) and payment integration (Stripe) for freemium model.
- [ ] Build React Native (Expo) mobile app with chat, daily wisdom push notifications, and offline bookmarks.
- [ ] Deploy full stack: backend on Railway/Render, Qdrant Cloud, frontend on Vercel, mobile on stores.
