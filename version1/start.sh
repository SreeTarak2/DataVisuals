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
    echo "⚠️  OpenAI API key not found. Using local LLM instead."
    echo "   To use OpenAI, set OPENAI_API_KEY environment variable"
    echo "   or create backend/.env file with your API key:"
    echo "   cp backend/env.example backend/.env"
    echo ""
fi

# Check if using remote Ollama
if grep -q "ac85071ebb10.ngrok-free.app" backend/.env 2>/dev/null || grep -q "ac85071ebb10.ngrok-free.app" backend/env.example 2>/dev/null; then
    echo "🌐 Using remote Ollama instance on Google Colab"
    echo "   URL: https://ac85071ebb10.ngrok-free.app"
    echo "   Model: llama3:instruct"
    echo ""
else
    # Check if Ollama is running (for local LLM)
    if ! pgrep -x "ollama" > /dev/null; then
        echo "🤖 Ollama not running. Setting up local LLM..."
        ./setup_ollama.sh
        echo ""
    fi
fi

# Start backend
echo "🔧 Starting backend..."
cd backend

# Copy env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
fi

if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Activating virtual environment..."
source venv/bin/activate

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🌐 Starting FastAPI server..."
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
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
