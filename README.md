# AntarDarshan — अन्तर्दर्शन

**Inner Vision Through Ancient Wisdom**

An AI assistant for Indian philosophy — citation-grounded answers drawn from the Upanishads, Bhagavad Gita, Dhammapada, Mahabharata, and 50+ classical texts across Hindu, Buddhist, Jain, and Bhakti traditions.

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#running-tests)
[![License](https://img.shields.io/badge/code-MIT-blue)](#license)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black)](https://nextjs.org)

---

## What It Does

| Feature | Description |
|---|---|
| 💬 **Ask** | Get scripture-grounded answers to any philosophical question, with numbered citations |
| 📖 **Read** | Browse 50+ classical texts in a clean, distraction-free reading interface |
| 🔖 **Highlight & Note** | Save passages and add personal notes as you read |
| 🌐 **Multi-tradition** | Vedanta, Buddhism, Yoga, Jainism, Bhakti — all in one place |
| 🧵 **Conversations** | Persistent chat history with follow-up question suggestions |
| 🌟 **Wisdom Wall** | Community space for sharing insights from the texts |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **RAG Pipeline** | bge-m3 (hybrid dense + sparse), bge-reranker-v2-m3 cross-encoder, Qdrant |
| **LLM** | Together AI — Llama 3.3 70B (Groq fallback) |
| **Backend** | FastAPI (Python 3.11+) |
| **Frontend** | Next.js 14, Tailwind CSS |
| **Database** | Supabase (PostgreSQL + Auth + RLS) |
| **Observability** | LangFuse |
| **Hosting** | Hetzner VPS + Vercel |

---

## Corpus

50+ classical texts across traditions — all public domain (pre-1928) or CC0:

**Hindu Philosophy**
- All 13 principal Upanishads (Müller, SBE)
- Bhagavad Gita (Arnold 1885 + Telang 1882)
- Mahabharata + Ramayana (Ganguli / Griffith)
- Rig Veda + Atharva Veda (Griffith)
- Brahma Sutras with Shankara & Ramanuja commentaries
- Yoga Sutras (Johnston), Ashtavakra Gita (Richards)
- Samkhya Karika, Nyaya Sutras, Vaisheshika Sutras, Arthashastra, Manu Smriti

**Buddhist Philosophy**
- Four Pali Nikayas: Digha, Majjhima, Samyutta, Anguttara (Sujato CC0)
- Khuddaka Nikaya: Dhammapada, Sutta Nipata, Udana, Itivuttaka, Theragatha, Therigatha
- Milindapanha (Rhys Davids)

**Jain & Bhakti**
- Jain Sutras Parts 1 & 2 (Jacobi)
- Songs of Kabir (Tagore), Psalms of Maratha Saints, Thirukkural
- Vivekananda — Raja-Yoga, Karma-Yoga, Jnana-Yoga

Full source attribution, license verification, and download provenance in [`CORPUS.md`](CORPUS.md).

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Qdrant](https://qdrant.tech/) running locally
- [Together AI API key](https://api.together.xyz) (pay-as-you-go) or [Groq API key](https://console.groq.com) (free tier)
- [Supabase](https://supabase.com) project (free tier)

### Setup

```bash
# Clone
git clone https://github.com/sharanharsoor/antardarshan.git
cd antardarshan

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and fill in your keys
cp .env.example .env

# Frontend
cd frontend && npm install && cd ..

# Start everything
./start.sh
```

### Corpus Setup (first time)

```bash
# Process all texts into chunks
python -m ingestion.process_all

# Embed into Qdrant  (~30-60 min on CPU)
python -m ingestion.embed_and_load --mode prod

# Verify and benchmark
python -m ingestion.admin verify
python -m eval.run_eval          # target: ≥90%
```

### Adding a new text

```bash
# Add a single new scripture incrementally (no full re-embed needed)
python -m ingestion.admin add corpus/raw/my_text.txt \
  --scripture "Text Name" \
  --tradition hindu_vedanta \
  --translator "Translator" \
  --year 1900
```

---

## Environment Variables

Copy `.env.example` to `.env`:

| Variable | Description |
|---|---|
| `TOGETHER_API_KEY` | Together AI key (primary LLM provider) |
| `GROQ_API_KEY` | Groq key (fallback if Together not set) |
| `GLOBAL_DAILY_LIMIT` | Org-wide query cap per day (default: `15400`, set `0` to disable) |
| `QDRANT_URL` | Qdrant server URL (default: `http://localhost:6333`) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (backend only) |
| `EMBED_MODEL` | Embedding model (default: `BAAI/bge-m3`) |
| `LANGFUSE_PUBLIC_KEY` | LangFuse observability (optional) |
| `LANGFUSE_SECRET_KEY` | LangFuse observability (optional) |

---

## Project Structure

```
antardarshan/
├── backend/              # FastAPI API server
│   ├── app.py            # API endpoints
│   ├── rag_query.py      # Hybrid retrieval + reranking pipeline
│   ├── llm.py            # LLM generation + streaming
│   └── corpus_index.py   # In-memory scripture index
├── frontend/             # Next.js application
│   └── src/
│       ├── app/          # Pages: ask, library, read, profile, wisdom
│       └── components/   # Header, sidebar, ask core, highlights
├── ingestion/            # Corpus pipeline
│   ├── parsers/          # Per-source text parsers (20+ parsers)
│   ├── process_all.py    # Full corpus processing
│   ├── embed_and_load.py # Qdrant embedding + upload
│   └── admin.py          # Incremental indexing CLI
├── tests/                # Test suite (600 tests — 496 backend + 104 frontend)
├── eval/                 # Retrieval quality benchmarks (25 queries)
├── supabase/migrations/  # Database schema
└── CORPUS.md             # Full corpus attribution + legal status
```

---

## Running Tests

```bash
# Full test suite
pytest tests/ -v

# Frontend
cd frontend && npm run lint && npm run test

# Retrieval quality benchmark
python -m eval.run_eval        # target: ≥90%

# Index health check
python -m ingestion.admin verify
```

---

## License

Code: **MIT**

Corpus texts: Public domain (pre-1928 US) or CC0. See [`CORPUS.md`](CORPUS.md) for full per-source attribution, license proof, and removal paths.
