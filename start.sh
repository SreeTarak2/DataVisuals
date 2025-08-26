#!/bin/bash

echo "🚀 Starting DataSage AI..."

# Check if MongoDB is running
if ! pgrep -x "mongod" > /dev/null; then
    echo "⚠️  MongoDB is not running. Please start MongoDB first:"
    echo "   sudo systemctl start mongod"
    echo "   or"
    echo "   brew services start mongodb-community"
    echo ""
fi

# Check OpenAI API key
if [ -z "$OPENAI_API_KEY" ] && [ ! -f "backend/.env" ]; then
    echo "⚠️  OpenAI API key not found. Please set OPENAI_API_KEY environment variable"
    echo "   or create backend/.env file with your API key:"
    echo "   cp backend/env.example backend/.env"
    echo "   # Then edit backend/.env and add your OpenAI API key"
    echo ""
fi

# Start backend
echo "🔧 Starting backend..."
cd backend
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Activating virtual environment..."
source venv/bin/activate

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🌐 Starting FastAPI server..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend
echo "🎨 Starting frontend..."
cd ../frontend

echo "📦 Installing dependencies..."
npm install

echo "🌐 Starting React development server..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ DataSage AI is starting up!"
echo ""
echo "📊 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo "🎨 Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Servers stopped"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Wait for both processes
wait
