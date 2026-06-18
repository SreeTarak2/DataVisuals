
# AI Chat Production Deployment Guide

## Overview

This guide covers setup, extension, monitoring, and troubleshooting for the production AI chat system (backend + frontend).

**Architecture:**
- Backend: Python/FastAPI + ReAct Agent + streaming synthesis
- Frontend: React 19+ with Server-Sent Events streaming
- Communication: HTTP POST with `text/event-stream` response (SSE)
- Security: Rate-limiting, prompt injection guard, error categorization
- Resilience: Retries (3 attempts), circuit breaker (120s cooldown)
- Monitoring: Optional Prometheus metrics + structured error logging

---

## Backend Setup

### Prerequisites

- Python 3.11+
- FastAPI app running (assumed at port 8000)
- `llm_router` service with streaming support
- Polars library for dataframe operations
- Redis (optional, for distributed rate-limiting)

### Installation

1. **Ensure all production modules are present:**

```bash
cd version2/backend

# Check these files exist:
ls -la services/agents/chat/chat_agent.py
ls -la services/agents/chat_agent_harness.py
ls -la services/observability/metrics.py
ls -la services/retries/async_utils.py
ls -la services/rate_limiter_chat.py
ls -la services/prompt_injection_guard.py
ls -la services/chat_error_handler.py
```

2. **Verify dependencies in `requirements.txt`:**

```bash
# Should include:
# - fastapi
# - uvicorn
# - polars  # or pandas
# - pydantic
# - prometheus-client  # optional but recommended
```

3. **Install:**

```bash
pip install -r requirements.txt
```

### Configuration

#### Environment Variables

Create `.env` in `version2/backend/`:

```env
# Chat rate-limiting
CHAT_RATE_LIMIT_REQUESTS=30
CHAT_RATE_LIMIT_WINDOW_SECONDS=30

# Circuit breaker (resilience)
CIRCUIT_BREAKER_FAILURE_THRESHOLD=6
CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS=120

# Monitoring
ENABLE_PROMETHEUS_METRICS=true
METRICS_PORT=9090

# LLM timeouts
LLM_SYNTHESIS_TIMEOUT_SECONDS=120
LLM_RETRY_MAX_ATTEMPTS=3

# Debug mode (disables some security checks for dev)
DEBUG=false
```

#### Load Configuration

In `services/ai/ai_service.py` or your entry point:

```python
import os
from dotenv import load_dotenv

load_dotenv()

CHAT_RATE_LIMIT_REQUESTS = int(os.getenv('CHAT_RATE_LIMIT_REQUESTS', '30'))
CHAT_RATE_LIMIT_WINDOW = int(os.getenv('CHAT_RATE_LIMIT_WINDOW_SECONDS', '30'))
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv('CIRCUIT_BREAKER_FAILURE_THRESHOLD', '6'))
```

### Wiring the Streaming Endpoint

#### Route Definition

In your FastAPI app (e.g., `main.py`):

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from services.ai.ai_service import process_chat_message_streaming

app = FastAPI()

@app.post("/api/chat/stream")
async def stream_chat(request: ChatRequest):
    """
    Stream AI chat responses with real-time token emission.
    
    Request body:
      - query (str): The user question
      - dataset_id (str): ID of dataset to analyze
      - user_id (str): User identifier for rate-limiting
    
    Response: Server-Sent Events (text/event-stream)
    """
    return StreamingResponse(
        process_chat_message_streaming(
            query=request.query,
            dataset_id=request.dataset_id,
            user_id=request.user_id,
            df=request.get_dataset(),  # Caller must provide df
        ),
        media_type="text/event-stream"
    )
```

#### Expected Request Body

```json
{
  "query": "What were sales by region in Q4?",
  "dataset_id": "sales_q4",
  "user_id": "user_123"
}
```

### Event-Driven Architecture

The streaming flow:

1. **Request arrives** → `process_chat_message_streaming(query, dataset_id, user_id, df)`
2. **Security checks:**
   - Rate-limit check (token bucket)
   - Prompt injection guard
   - Query sanitization
3. **Agent runs** → `ChatAgent.run_streaming(df, ...)`
   - Reason → Act → Observe loop
   - Yields `thinking_step` events
4. **Synthesis** → `_synthesize_streaming()`
   - Wraps `llm_router.call_streaming()` with retry + circuit-breaker
   - Yields `token` events
   - Emits `response_complete` on finish
5. **Completion** → `done` event with trace

### Extending the Agent

#### Adding a New Tool

In `services/agents/chat/chat_agent.py`:

```python
class ChatAgent:
    def __init__(self, dataframe, schema, tools=None):
        # Default tools: sql, stats, rag, memory
        self.tools = tools or self._default_tools()
    
    def _default_tools(self):
        return {
            'sql': self.execute_sql,
            'stats': self.compute_stats,
            'rag': self.query_knowledge_base,
            'memory': self.query_context_memory,
            'your_new_tool': self.your_new_tool,  # <-- ADD HERE
        }
    
    async def your_new_tool(self, query: str, **kwargs):
        """
        Execute your custom logic.
        
        Returns:
            str: Observation text that the reasoner sees
        """
        result = your_logic_here(query)
        return f"Tool output: {result}"
```

Then update the `_reason` method to consider this tool in the planner prompt.

#### Testing a New Tool

```python
# tests/test_chat_agent.py
import polars as pl
from services.agents.chat.chat_agent import ChatAgent

def test_new_tool():
    df = pl.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
    agent = ChatAgent(dataframe=df, schema="col1:int, col2:string")
    
    # Test tool directly
    result = await agent.your_new_tool("test query")
    assert "Tool output" in result
    
    # Test full agent
    output = await agent.run_streaming(
        query="Can you use your_new_tool?",
        max_iterations=2
    )
    async for event in output:
        print(f"Event: {event['type']}", event.get('content'))
```

---

## Frontend Setup

### Prerequisites

- Node 18+
- npm or pnpm
- React 19+ (or compatible version)
- Vite or webpack build tool

### Installation

1. **Navigate to frontend:**

```bash
cd version2/frontend
pnpm install
```

2. **Verify `StreamingChatMessage` component:**

```bash
ls src/components/StreamingChatMessage.jsx
ls src/components/StreamingChatMessage.module.css
```

### Configuration

#### Environment Variables

Create `.env.local` in `version2/frontend/`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_CHAT_ENDPOINT=/api/chat/stream
VITE_DEBUG=false
```

#### API Client Setup

```javascript
// src/services/chatApi.js
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function* streamChat(query, datasetId, userId) {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, dataset_id: datasetId, user_id: userId }),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6));
          yield event;
        } catch (e) {
          console.error('Failed to parse event:', line, e);
        }
      }
    }
  }
}
```

### Using the Streaming Component

```jsx
import StreamingChatMessage from './components/StreamingChatMessage';

export function ChatPage() {
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState([]);
  
  const handleSubmit = (userQuery) => {
    setQuery(userQuery);
    // StreamingChatMessage handles the streaming internally
  };
  
  return (
    <div className="chat-container">
      <ChatInput onSubmit={handleSubmit} />
      
      {query && (
        <StreamingChatMessage
          query={query}
          datasetId="sales_2024"
          userId={getCurrentUserId()}
          onComplete={(response, trace) => {
            setHistory([...history, { query, response, trace }]);
            setQuery('');
          }}
          onError={(error) => {
            console.error('Chat failed:', error);
            // Show error UI
          }}
        />
      )}
      
      <ChatHistory history={history} />
    </div>
  );
}
```

### Styling & Theming

The component uses CSS Modules (`StreamingChatMessage.module.css`). To integrate with your theme:

```css
/* Override in your global CSS */
:root {
  --chat-bg-dark: #1a1a1a;
  --chat-text-dark: #e0e0e0;
  --chat-spinner-color: #00a8ff;
  --chat-error-color: #ff6b6b;
}

/* Dark mode (already in component) */
@media (prefers-color-scheme: dark) {
  /* Component uses these automatically */
}
```

### Customizing the Component

To customize behavior, extend the component:

```jsx
import StreamingChatMessage from './components/StreamingChatMessage';

export function CustomChatMessage(props) {
  const {
    query,
    datasetId,
    userId,
    onComplete,
    onError,
    showThinkingSteps = true,
    animationSpeed = 'normal',
  } = props;
  
  return (
    <StreamingChatMessage
      {...{ query, datasetId, userId, onComplete, onError }}
      showThinkingIndicators={showThinkingSteps}
      customClass={animationSpeed === 'fast' ? 'fast-animations' : ''}
    />
  );
}
```

---

## Monitoring & Observability

### Prometheus Metrics

If `ENABLE_PROMETHEUS_METRICS=true`, metrics are exported to `/metrics`:

```bash
curl http://localhost:9090/metrics | grep chat
```

**Available metrics:**
- `chat_requests_total` — total requests by endpoint and status
- `chat_request_duration_seconds` — histogram of request latencies
- `rate_limiter_rejections_total` — rejected requests by user
- `injection_attempts_total` — detected injection attempts
- `agent_iterations` — ReAct loop iteration count
- `synthesis_tokens` — tokens generated by LLM

### Structured Logging

All errors and key events are logged with context:

```bash
# View error logs
tail -f backend/logs/error.log | grep "injection\|rate_limit\|circuit_breaker"
```

### Health Check Endpoint

Add to your FastAPI app:

```python
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "chat_endpoint": "/api/chat/stream",
        "circuit_breaker_state": "closed",  # or "open" if down
        "rate_limiter_rate": "30/30s",
    }
```

---

## Troubleshooting

### Issue: Rate Limit Errors on Every Request

**Symptom:** User sees "I'm receiving high traffic..." immediately.

**Causes:**
1. Rate limit too strict for load → increase `CHAT_RATE_LIMIT_REQUESTS`
2. Share state between instances → use Redis or shared rate-limiter
3. User ID collision → verify `user_id` uniqueness

**Fix:**
```env
CHAT_RATE_LIMIT_REQUESTS=100  # Increase from 30
CHAT_RATE_LIMIT_WINDOW_SECONDS=60  # Increase to 1 minute
```

### Issue: Circuit Breaker Always Open

**Symptom:** "Model unavailable. Please try again later."

**Causes:**
1. LLM service is down → check `llm_router` health
2. Timeout too short → increase `LLM_SYNTHESIS_TIMEOUT_SECONDS`
3. Network issue → check connectivity to LLM endpoint

**Fix:**
```bash
# Check LLM status
curl http://llm-service/health

# Temporarily disable circuit-breaker (dev only):
# Set CIRCUIT_BREAKER_FAILURE_THRESHOLD to high value (e.g., 1000)
```

### Issue: Injection Guard Blocks Legitimate Queries

**Symptom:** "Invalid query format. Please rephrase."

**Causes:**
1. Query contains code `(` `)` → legitimate in technical questions
2. Query contains HTML `<` `>` → happens with angle-bracket notation
3. Overly strict regex patterns

**Fix (dev only):**
```python
# In services/prompt_injection_guard.py, reduce strictness:
INJECTION_PATTERNS = [
    # Comment out overly broad patterns
    # (r"(['\"])+", "SQL injection attempt"),  # <-- too broad
]
```

### Issue: Tokens Not Streaming; Fallback Instead

**Symptom:** Response appears all at once, not token-by-token.

**Causes:**
1. LLM not streaming → check `llm_router.call_streaming()` returns async generator
2. Circuit-breaker opened → fallback path activates
3. Frontend not parsing SSE → check browser dev tools Network tab for `text/event-stream` response

**Debug:**
```python
# Test streaming directly
async for token in llm_router.call_streaming("test"):
    print(f"Token: {token}")

# If none print: fallback activates, check circuit-breaker state
```

### Issue: Frontend Component Not Updating

**Symptom:** Spinner appears, but no text, no error.

**Causes:**
1. CORS misconfiguration → browser blocks request
2. API endpoint URL wrong → 404 response
3. EventSource parser fails → JSON parse error

**Debug:**
```javascript
// In browser console
const api = '/api/chat/stream';
fetch(api, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'test', dataset_id: 'test', user_id: 'user1' })
})
.then(r => r.text())
.then(t => console.log(t.slice(0, 200)))  // Print first 200 chars
```

---

## Deployment Checklist

- [ ] Backend: All production modules present and imported
- [ ] Backend: Rate-limiting configured and tested
- [ ] Backend: Prometheus metrics enabled (or logging enabled)
- [ ] Backend: Circuit-breaker thresholds tuned for your LLM latency
- [ ] Backend: Error messages reviewed (no PII, no internal stack traces exposed)
- [ ] Frontend: `StreamingChatMessage` component integrated
- [ ] Frontend: CSS dark/light mode validated
- [ ] Frontend: API endpoint configured (env var `VITE_API_BASE_URL`)
- [ ] Testing: Integration test covering streaming + error paths
- [ ] Testing: Load test with 50+ concurrent users
- [ ] Monitoring: Prometheus dashboard set up
- [ ] Monitoring: Log aggregation configured (e.g., ELK, Datadog)
- [ ] Documentation: Runbook for on-call team
- [ ] Documentation: API schema shared with frontend team

---

## Performance Tips

### Backend

1. **Enable metrics collection** (low overhead):
   ```env
   ENABLE_PROMETHEUS_METRICS=true
   ```

2. **Tune retry backoff** for fast failure feedback:
   ```python
   # In async_utils.py
   delays = [0.5, 1.0, 2.0]  # faster recovery
   ```

3. **Pre-warm circuit breaker** by running a health check:
   ```python
   async def startup_event():
       await ChatAgent(df=dummy_df, schema="").run("dummy query", max_iterations=1)
   ```

### Frontend

1. **Memoize `StreamingChatMessage` to avoid re-renders:**
   ```jsx
   export const ChatMessage = React.memo(StreamingChatMessage);
   ```

2. **Enable CSS animations only if not reduced-motion:**
   ```css
   @media (prefers-reduced-motion: no-preference) {
     @keyframes spin { /* animations */ }
   }
   ```

3. **Lazy-load chart library if not always needed:**
   ```js
   const Plotly = React.lazy(() => import('plotly.js-dist'));
   ```

---

## Support & Resources

- **Backend docs:** See `docs/CHAT_STREAMING_EVENT_SCHEMA.md` for event format
- **Frontend API:** See `StreamingChatMessage.jsx` JSDoc comments
- **Agent extension:** See `services/agents/chat/README.md` (create if needed)
- **Metrics reference:** See Prometheus docs for dashboard setup

---

**Version:** 1.0  
**Last Updated:** 2025  
**Maintained By:** [Your Team]
