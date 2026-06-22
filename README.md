# AntarDarshan — अन्तर्दर्शन

**Inner Vision Through Ancient Wisdom**

An AI assistant for Indian philosophy — citation-grounded answers from the Bhagavad Gita, Upanishads, Dhammapada, Yoga Sutras, Mahabharata, and 40+ other classical texts.

> Free forever. No ads.

---

## What It Does

- **Ask** any question about Indian philosophy and get answers grounded in actual scripture citations
- **Read** classical texts in a clean, distraction-free reading interface  
- **Explore** across traditions — Vedanta, Buddhism, Yoga, Jainism, Bhakti
- **Compare** how different traditions answer the same question
- **Bookmark and highlight** passages as you read

---

## Tech Stack

| Layer | Technology |
|---|---|
| **RAG Pipeline** | bge-m3 embeddings, Qdrant vector DB (hybrid dense + sparse) |
| **LLM** | Groq (Llama 3.1 8B / Llama 4 Scout 17B) |
| **Backend** | FastAPI (Python) |
| **Frontend** | Next.js 16, Tailwind CSS |
| **Database** | Supabase (PostgreSQL + Auth) |
| **Observability** | LangFuse |
| **Hosting** | Hetzner VPS (~$6/month) + Vercel (free) |

---

## Corpus

19,278 chunks from 43 classical texts including:
- Bhagavad Gita (Arnold, 1885)
- 10 Principal Upanishads (Müller)
- Dhammapada, Digha Nikaya, Majjhima Nikaya, Samyutta Nikaya, Anguttara Nikaya (Sujato CC0)
- Yoga Sutras of Patanjali (Johnston)
- Ashtavakra Gita (Richards)
- Vivekananda — Raja-Yoga, Karma-Yoga, Jnana-Yoga
- Songs of Kabir (Tagore)
- Mahabharata, Manu Smriti, Brahma Sutras, and more

All sources are public domain (pre-1928) or CC0.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Qdrant](https://qdrant.tech/) running locally or on a server
- [Groq API key](https://console.groq.com) (free tier)
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
# Edit .env with your Groq, Supabase, HuggingFace keys

# Frontend
cd frontend
npm install
cd ..

# Start everything
./start.sh
```

### Corpus Setup (first time)

```bash
# Download and process texts
python -m ingestion.process_all

# Embed into Qdrant (takes 30-60 min, bge-m3 on CPU)
python -m ingestion.embed_and_load --mode prod

# Verify
python -m ingestion.admin verify
python -m eval.run_eval  # should pass >90%
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (free tier, 14,400 queries/day) |
| `QDRANT_URL` | Qdrant server URL (default: http://localhost:6333) |
| `EMBED_MODEL` | Embedding model (default: BAAI/bge-m3) |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (backend only) |
| `HF_TOKEN` | HuggingFace token (optional, for model downloads) |
| `LANGFUSE_PUBLIC_KEY` | LangFuse observability (optional) |
| `LANGFUSE_SECRET_KEY` | LangFuse observability (optional) |

---

## Project Structure

```
antardarshan/
├── backend/          # FastAPI backend
│   ├── app.py        # API endpoints
│   ├── rag_query.py  # RAG pipeline
│   ├── llm.py        # LLM generation + streaming
│   └── corpus_index.py  # In-memory corpus index
├── frontend/         # Next.js frontend
│   └── src/
│       ├── app/      # Pages (ask, library, read, profile)
│       └── components/  # Shared components
├── ingestion/        # Corpus pipeline
│   ├── parsers/      # Per-source text parsers
│   ├── embed_and_load.py  # Qdrant embedding
│   └── admin.py      # Incremental indexing CLI
├── tests/            # 207 tests
├── eval/             # Retrieval quality benchmarks
├── supabase/
│   └── migrations/   # Supabase schema migrations
└── sources/          # Approved sources config
```

---

## Running Tests

```bash
# Backend (207 tests)
pytest tests/ -q

# Frontend
cd frontend && npm run lint && npm run build

# Retrieval quality
python -m eval.run_eval  # target: ≥90%
```

---

## License

Code: MIT  
Corpus texts: Public domain (pre-1928) or CC0  
See `DATA-SOURCES.md` for full attribution.
