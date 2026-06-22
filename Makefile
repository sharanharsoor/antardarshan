# AntarDarshan — Development Commands

.PHONY: test serve process eval check

# Run all unit tests
test:
	source .venv/bin/activate && pytest tests/ -v

# Start FastAPI server
serve:
	source .venv/bin/activate && uvicorn backend.app:app --reload --port 8000

# Process all corpus texts into chunks
process:
	source .venv/bin/activate && python -m ingestion.process_phase1

# Run retrieval evaluation (requires Qdrant running)
eval:
	source .venv/bin/activate && python -m eval.run_eval

# Quick health check (requires server running)
check:
	@curl -sf http://localhost:8000/api/health && echo " ✓ Server OK" || echo " ✗ Server down"
	@curl -sf http://localhost:6333/collections && echo " ✓ Qdrant OK" || echo " ✗ Qdrant down"

# Embed and load into Qdrant (dev mode)
embed-dev:
	source .venv/bin/activate && python -m ingestion.embed_and_load --mode dev

# Embed and load into Qdrant (production bge-m3)
embed-prod:
	source .venv/bin/activate && python -m ingestion.embed_and_load --mode prod

# Install dependencies
install:
	python3 -m venv .venv
	source .venv/bin/activate && pip install -r requirements.txt
	source .venv/bin/activate && pip install pytest pytest-asyncio httpx
