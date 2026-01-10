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

echo "Starting Backend..."
cd backend
# Check if venv exists
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Warning: venv not found in backend directory."
fi

# Use -u for unbuffered output
python -u main.py &
BACKEND_PID=$!

echo "Starting Celery Worker..."
celery -A tasks.celery_app worker --loglevel=info &
CELERY_PID=$!

cd ..

echo "Starting Frontend..."
cd frontend
pnpm dev &
FRONTEND_PID=$!
cd ..

echo "Servers started. Logs will appear below. Press Ctrl+C to stop."
wait
