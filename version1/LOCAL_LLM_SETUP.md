# Local LLM Setup for DataSage AI

DataSage AI now supports local LLM inference using Ollama, which allows you to run the application without requiring an OpenAI API key.

## Quick Start

1. **Run the setup script:**
   ```bash
   ./setup_ollama.sh
   ```

2. **Start DataSage AI:**
   ```bash
   ./start.sh
   ```

The application will automatically use the local LLM when no OpenAI API key is provided.

## Manual Setup

### 1. Install Ollama

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Start Ollama Service

```bash
ollama serve
```

### 3. Download a Model

```bash
# Lightweight model (recommended)
ollama pull llama3.2:3b

# Or a more capable model (requires more resources)
ollama pull llama3.2:7b
```

### 4. Configure DataSage AI

Edit `backend/.env`:

```env
# Use local LLM
USE_LOCAL_LLM=true
LOCAL_LLM_URL=http://localhost:11434
LOCAL_LLM_MODEL=llama3.2:3b

# Leave OpenAI key empty
OPENAI_API_KEY=
```

## Available Models

### Lightweight Models (Recommended for most systems)
- `llama3.2:3b` - 3B parameters, ~2GB RAM
- `phi3:mini` - 3.8B parameters, ~2.3GB RAM
- `gemma2:2b` - 2B parameters, ~1.6GB RAM

### Medium Models (Better quality, more resources)
- `llama3.2:7b` - 7B parameters, ~4.7GB RAM
- `phi3:medium` - 14B parameters, ~8.4GB RAM

### Large Models (Best quality, high resources)
- `llama3.2:13b` - 13B parameters, ~7.3GB RAM
- `llama3.2:70b` - 70B parameters, ~40GB RAM

## Performance Tips

1. **Choose the right model size** based on your system's RAM
2. **Close other applications** when running larger models
3. **Use SSD storage** for better model loading performance
4. **Monitor system resources** during first-time model loading

## Troubleshooting

### Ollama not starting
```bash
# Check if Ollama is running
ps aux | grep ollama

# Restart Ollama
pkill ollama
ollama serve
```

### Model not found
```bash
# List available models
ollama list

# Pull the model
ollama pull llama3.2:3b
```

### Out of memory
- Try a smaller model (e.g., `llama3.2:3b` instead of `llama3.2:7b`)
- Close other applications
- Check available RAM: `free -h`

### Slow responses
- The first request after starting Ollama may be slow (model loading)
- Subsequent requests should be faster
- Consider using a smaller model for better performance

## Switching Between Local and OpenAI

To use OpenAI instead of local LLM:

1. Set your OpenAI API key in `backend/.env`:
   ```env
   OPENAI_API_KEY=your_api_key_here
   USE_LOCAL_LLM=false
   ```

2. Restart the application:
   ```bash
   ./start.sh
   ```

## Fallback Behavior

If both OpenAI and local LLM are unavailable, DataSage AI will use rule-based responses that provide basic data analysis guidance and visualization recommendations.

