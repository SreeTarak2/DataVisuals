#!/bin/bash

# Function to kill processes on exit
cleanup() {
    echo "Stopping servers..."
    # Check if variables are set before killing
    if [ -n "$FRONTEND_PID" ]; then kill $FRONTEND_PID; fi
    if [ -n "$BACKEND_PID" ]; then kill $BACKEND_PID; fi
    if [ -n "$CELERY_PID" ]; then kill $CELERY_PID; fi
    exit
}

trap cleanup SIGINT SIGTERM

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "Starting Backend..."

# Create or recreate venv if needed
if [ ! -d "$BACKEND_DIR/venv" ] || [ ! -f "$BACKEND_DIR/venv/bin/pip" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$BACKEND_DIR/venv"
fi

# Check if dependencies need to be installed
REQUIREMENTS_FILE="$BACKEND_DIR/requirements.txt"
CHECKSUM_FILE="$BACKEND_DIR/.requirements_checksum"
CURRENT_CHECKSUM=$(md5sum "$REQUIREMENTS_FILE" 2>/dev/null | cut -d' ' -f1)

if [ ! -f "$CHECKSUM_FILE" ] || [ "$(cat "$CHECKSUM_FILE" 2>/dev/null)" != "$CURRENT_CHECKSUM" ]; then
    echo "Dependencies changed or not installed. Installing..."
    (
        cd "$BACKEND_DIR"
        source venv/bin/activate
        pip install -q -r requirements.txt
        # Install torch (CPU) + sentence-transformers separately to save disk
        pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
        pip install -q sentence-transformers --no-cache-dir
    )
    # Save the checksum after successful installation
    echo "$CURRENT_CHECKSUM" > "$CHECKSUM_FILE"
    echo "Dependencies installed successfully."
else
    echo "Dependencies already up to date. Skipping installation."
fi

# Start backend with auto-reload
(
    cd "$BACKEND_DIR"
    source venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) &
BACKEND_PID=$!

echo "Starting Celery Worker with auto-reload..."
(
    cd "$BACKEND_DIR"
    source venv/bin/activate
    celery -A tasks.celery_app worker --loglevel=info --autoreload
) &
CELERY_PID=$!

echo "Starting Frontend..."
cd frontend
pnpm dev &
FRONTEND_PID=$!
cd ..

echo "Servers started. Logs will appear below. Press Ctrl+C to stop."
wait
