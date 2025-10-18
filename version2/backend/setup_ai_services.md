# AI Services Setup Guide

## Option 1: Install Ollama Locally (Recommended)

### 1. Install Ollama
```bash
# On Linux/macOS
curl -fsSL https://ollama.ai/install.sh | sh

# Or download from https://ollama.ai/download
```

### 2. Start Ollama Service
```bash
ollama serve
```

### 3. Pull Required Models
```bash
ollama pull llama3.1
ollama pull mistral:7b
```

### 4. Verify Installation
```bash
curl http://localhost:11434/api/tags
```

## Option 2: Use External AI Services

### Update Environment Variables
Create a `.env` file in the backend directory:

```bash
# For external Ollama instance
LLAMA_BASE_URL=https://your-ollama-instance.com
MISTRAL_BASE_URL=https://your-ollama-instance.com

# Or for different AI providers
OLLAMA_BASE_URL=https://your-ai-service.com
```

### Option 3: Use Mock Mode (Development Only)

If you want to test without AI services, you can modify the config to use mock responses.

## Current Configuration

The system is currently configured to use:
- Local Ollama at `http://localhost:11434`
- Models: `llama3.1` for most tasks
- Fallback error handling when services are unavailable

## Testing the Setup

1. Start the backend server:
```bash
cd /home/vamsi/nothing/datasage/version2/backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. Test AI service connectivity:
```bash
curl -X POST http://localhost:8000/api/test-ai
```

## Troubleshooting

### Connection Errors
- Check if Ollama is running: `curl http://localhost:11434/api/tags`
- Verify model is installed: `ollama list`
- Check firewall/network settings

### Model Not Found
- Pull the required model: `ollama pull llama3.1`
- Check model name in config matches installed model

### Ngrok Issues
- Ngrok URLs expire and change frequently
- Use local Ollama or stable external services
- Update ngrok URL in config if using external tunnel

