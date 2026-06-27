#!/bin/bash
# AntarDarshan — Start Backend + Frontend
# Kills existing processes on ports 8000 and 3000, then restarts both.

set -e

PROJECT_DIR="/Users/sharsoor/Desktop/exp/person/bhagwatgita"
cd "$PROJECT_DIR"

echo "═══════════════════════════════════════════════════════════"
echo "  AntarDarshan — Starting Services"
echo "═══════════════════════════════════════════════════════════"

# Kill anything on port 8000 (backend)
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "  Killing existing process on port 8000..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Kill anything on port 3000 (frontend)
if lsof -ti:3000 > /dev/null 2>&1; then
    echo "  Killing existing process on port 3000..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Start Qdrant (Docker) — start existing container or create a new one
echo "  Starting Qdrant..."
# Qdrant health check uses root path '/' — '/health' returns 404 on this version
if docker ps -a --format '{{.Names}}' | grep -q "^qdrant-antardarshan$"; then
    docker start qdrant-antardarshan > /dev/null 2>&1
else
    docker run -d --name qdrant-antardarshan \
        -p 6333:6333 \
        -v "$PROJECT_DIR/qdrant_data:/qdrant/storage" \
        qdrant/qdrant > /dev/null 2>&1
fi

# Wait for Qdrant to be ready
for i in {1..15}; do
    if curl -sf http://localhost:6333/ > /dev/null 2>&1; then
        echo "  ✓ Qdrant ready"
        break
    fi
    sleep 1
    if [ "$i" -eq 15 ]; then
        echo "  ✗ Qdrant failed to start. Is Docker running?"
        exit 1
    fi
done

# Start backend — Gunicorn with 2 UvicornWorkers (I/O-bound, handles concurrent requests)
# Each worker is an independent async event loop. Scale up with -w on production VPS.
echo ""
echo "  Starting backend (port 8000, 2 workers)..."
source .venv/bin/activate
# Mac: uvicorn directly (no forking — PyTorch/Metal crashes on fork via Loky).
# Production Linux VPS: use Gunicorn instead:
#   WORKERS=${GUNICORN_WORKERS:-4}
#   EMBED_MODEL=BAAI/bge-m3 gunicorn backend.app:app \
#       -w "$WORKERS" -k uvicorn.workers.UvicornWorker \
#       --bind 0.0.0.0:8000 --timeout 120 --graceful-timeout 30 --log-level warning
EMBED_MODEL=BAAI/bge-m3 uvicorn backend.app:app \
    --host 0.0.0.0 --port 8000 \
    --log-level warning &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend to be ready — fail-fast if it never starts
echo "  Waiting for backend..."
BACKEND_READY=false
for i in {1..30}; do
    if curl -sf http://localhost:8000/healthz > /dev/null 2>&1; then
        echo "  ✓ Backend ready"
        BACKEND_READY=true
        break
    fi
    sleep 1
done

if [ "$BACKEND_READY" = false ]; then
    echo ""
    echo "  ✗ Backend failed to start within 30s. Check logs above."
    echo "  ✗ Is Qdrant running? docker start qdrant-antardarshan"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Start frontend — clear .next cache first to prevent stale compiled modules
echo ""
echo "  Starting frontend (port 3000)..."
cd frontend
rm -rf .next
npm run dev &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"
cd ..

sleep 3
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✓ AntarDarshan running:"
echo "    Frontend: http://localhost:3000"
echo "    Backend:  http://localhost:8000"
echo "    Qdrant:   http://localhost:6333"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo "═══════════════════════════════════════════════════════════"

# Wait for both — Ctrl+C kills everything
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
