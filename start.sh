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

# Check Docker/Qdrant
if ! curl -sf http://localhost:6333/health > /dev/null 2>&1; then
    echo "  ⚠ Qdrant not running! Start it with:"
    echo "    docker start qdrant-antardarshan"
    echo "  Or:"
    echo "    docker run -d --name qdrant-antardarshan -p 6333:6333 -v $PROJECT_DIR/qdrant_data:/qdrant/storage qdrant/qdrant"
    echo ""
fi

# Start backend
echo ""
echo "  Starting backend (port 8000)..."
source .venv/bin/activate
EMBED_MODEL=BAAI/bge-m3 uvicorn backend.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "  Waiting for backend..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "  ✓ Backend ready"
        break
    fi
    sleep 1
done

# Start frontend
echo ""
echo "  Starting frontend (port 3000)..."
cd frontend
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
