#!/bin/bash

echo "🚀 Starting DataSage AI v2.0..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python3 first."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Start backend
echo "🔧 Starting backend server..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 5

# Start frontend
echo "🎨 Starting frontend server..."
cd ../frontend
npm install
npm run dev &
FRONTEND_PID=$!

echo "✅ DataSage AI v2.0 is running!"
echo "📊 Frontend: http://localhost:3000"
echo "🔧 Backend: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"

# Function to cleanup on exit
cleanup() {
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT

# Wait for processes
wait

