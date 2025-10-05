#!/bin/bash

echo "🔧 Setting up Ollama for DataSage AI..."

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "📦 Installing Ollama..."
    
    # Install Ollama
    curl -fsSL https://ollama.ai/install.sh | sh
    
    # Add Ollama to PATH
    echo 'export PATH="$PATH:/usr/local/bin"' >> ~/.bashrc
    source ~/.bashrc
else
    echo "✅ Ollama is already installed"
fi

# Start Ollama service
echo "🚀 Starting Ollama service..."
ollama serve &

# Wait a moment for service to start
sleep 3

# Pull the lightweight model
echo "📥 Downloading lightweight model (llama3.2:3b)..."
ollama pull llama3.2:3b

echo "✅ Ollama setup complete!"
echo ""
echo "📊 Ollama is now running on http://localhost:11434"
echo "🤖 Model 'llama3.2:3b' is ready to use"
echo ""
echo "To test Ollama:"
echo "  ollama run llama3.2:3b"
echo ""
echo "To stop Ollama:"
echo "  pkill ollama"

