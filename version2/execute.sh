#!/bin/bash

# Function to kill processes on exit
cleanup() {
    echo "Stopping servers..."
    if [ -n "$FRONTEND_PID" ]; then kill $FRONTEND_PID 2>/dev/null; fi
    if [ -n "$BACKEND_PID" ]; then kill $BACKEND_PID 2>/dev/null; fi
    exit
}

trap cleanup SIGINT SIGTERM

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "================================================"
echo "  Signal — Starting Dev Environment"
echo "================================================"

# ── Python virtual environment ────────────────────────────────────────────────
if [ ! -d "$BACKEND_DIR/.venv" ] || [ ! -f "$BACKEND_DIR/.venv/bin/python" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$BACKEND_DIR/.venv"
fi

# ── Dependencies (uv sync) ───────────────────────────────────────────────────
echo "Installing backend dependencies..."
(
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    uv sync
    # sentence-transformers pulls GPU torch by default — override to CPU-only
    uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --force-reinstall
)
echo "Dependencies installed."

# ── Start Backend (FastAPI with auto-reload) ──────────────────────────────────
echo "Starting Backend..."
(
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) &
BACKEND_PID=$!

# ── Start Frontend (Vite dev server) ──────────────────────────────────────────
echo "Starting Frontend..."
(
    cd "$FRONTEND_DIR"
    pnpm dev
) &
FRONTEND_PID=$!

echo ""
echo "================================================"
echo "  Servers starting..."
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  Press Ctrl+C to stop all"
echo "================================================"
echo ""

# Wait for any child to exit (or Ctrl+C)
wait
