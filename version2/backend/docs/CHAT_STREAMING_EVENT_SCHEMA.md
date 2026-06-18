
# Chat Streaming Event Schema

## Overview

The AI chat streaming endpoint (`POST /api/chat/stream`) uses **Server-Sent Events (SSE)** to stream responses in real-time. This document defines all event types and their structure.

## Event Format

Each event is a JSON object prefixed with `data: ` on its own line:

```
data: {"type":"token","content":" world"}
data: {"type":"response_complete","full_response":"Hello world"}
```

## Event Types

### 1. `thinking_step`

Indicates progress within the agent's reasoning loop. Used to show thinking indicators in the UI.

```json
{
  "type": "thinking_step",
  "label": "Analyzing your question",
  "step": 1
}
```

**Fields:**
- `label` (string): Human-readable description of current step
- `step` (number): Sequential step counter for UI progress bars

**Usage in UI:** Display as a loading indicator or progress message.

---

### 2. `token`

A streamed text token. The synthesis model emits real tokens as they're generated.

```json
{
  "type": "token",
  "content": " There "
}
```

**Fields:**
- `content` (string): The token text (may include spaces, punctuation)

**Usage in UI:** Append to accumulated response text. Display with a blinking cursor if streaming is ongoing.

---

### 3. `response_complete`

Signals the end of the streaming response and provides the full response text. This event arrives in two scenarios:

**Scenario A: Tokens were streamed**
```json
{
  "type": "response_complete",
  "full_response": "The sales increased by 15% last quarter..."
}
```

**Scenario B: No tokens were streamed (fallback)**
```json
{
  "type": "response_complete",
  "full_response": "Complete answer without streaming..."
}
```

**Fields:**
- `full_response` (string): Complete accumulated response text

**Usage in UI:** 
- If tokens have been displayed, this confirms the stream is complete.
- If NO tokens arrived before this event, render `full_response` immediately (fallback mode). This handles cases where the agent's synthesis didn't emit tokens (e.g., circuit-breaker fallback).

---

### 4. `chart`

Chart or visualization configuration to render alongside the text response.

```json
{
  "type": "chart",
  "chart_config": {
    "data": [{"x": [...], "y": [...], "type": "bar"}],
    "layout": {"title": "Sales Trend", "xaxis": {...}},
    "position": "primary"
  }
}
```

**Fields:**
- `chart_config` (object): Plotly chart specification (compatible with Plotly.js)

**Usage in UI:** Pass to Plotly.newPlot() or your chart library.

---

### 5. `error`

Indicates an error occurred during processing. An error event ends the stream.

```json
{
  "type": "error",
  "content": "Authentication failed. Please log in again.",
  "category": "auth_error",
  "recoverable": false
}
```

**Fields:**
- `content` (string): User-friendly error message (always safe to display)
- `category` (string): Error type: `rate_limited`, `auth_error`, `model_error`, `network_error`, `timeout`, `dataset_error`, `unknown`
- `recoverable` (boolean): Whether the user can retry (false for auth errors)

**Usage in UI:** Display error message. Show "Try again" button only if `recoverable === true`. For `rate_limited`, add a backoff timer.

---

### 6. `done`

Final event signaling completion of the entire request.

```json
{
  "type": "done",
  "trace": {
    "tools_used": ["sql", "stats"],
    "iterations": 2
  },
  "insights": ["Revenue up 15%"],
  "data_summary": "Analyzed Q4 sales data"
}
```

**Fields:**
- `trace` (object): Debugging info
  - `tools_used` (array): Which agent tools ran (e.g., `["sql", "stats", "rag", "memory"]`)
  - `iterations` (number): Number of ReAct loop iterations
- `insights` (array, optional): Key findings extracted by the agent
- `data_summary` (string, optional): Compact summary of data used

**Usage in UI:** 
- Close loading/thinking indicators
- Store trace data for debugging
- Display insights as badges or summary cards if available
- Fire completion callback

---

## Streaming Workflow Diagram

```
User sends query
    ↓
[Validation checks] → error event → done
    ↓
thinking_step (step 1: "Analyzing...")
    ↓
[Agent decision: which tool to run]
    ↓
thinking_step (step 2: "Running SQL...")
    ↓
[Tool executes]
    ↓
[Agent decides: more tools or synthesize?]
    ↓
thinking_step (step 3: "Preparing answer...")
    ↓
[Synthesis: LLM streams tokens]
    ├→ token / token / token / ...
    ├→ response_complete
    └→ done
```

## Error Handling in UI

```javascript
// Pseudocode
const events = streamFrom('/api/chat/stream', params);

for await (const event of events) {
  if (event.type === 'error') {
    showErrorMessage(event.content);
    if (!event.recoverable) {
      disableRetryButton();
    }
    break;  // Stream ends after error
  }
  
  if (event.type === 'thinking_step') {
    setLoadingMessage(event.label);
  }
  
  if (event.type === 'token') {
    appendToResponse(event.content);
  }
  
  if (event.type === 'response_complete') {
    // If no tokens arrived, render the full response
    if (!hasReceivedTokens) {
      renderFull Response(event.full_response);
    }
    hideLoadingCursor();
  }
  
  if (event.type === 'done') {
    clearLoadingState();
    recordAgentTrace(event.trace);
  }
}
```

## Rate Limiting

When a `rate_limited` error occurs:
- Display: "I'm receiving high traffic. Please try again in a few moments."
- Implement exponential backoff: 1s → 2s → 4s
- After 3 failed attempts, show "Service temporarily unavailable" with a longer retry window (e.g., 60s)

## Fallback Scenarios

### Scenario 1: Tokens Streamed Normally
```
token "Hello"  
token " "  
token "world"  
response_complete {"full_response": "Hello world"}  
done
```
→ UI displays tokens as they arrive, then finalizes.

### Scenario 2: Fallback (No Tokens)
```
thinking_step {"label": "Analyzing..."}  
thinking_step {"label": "Preparing..."}  
response_complete {"full_response": "Hello world"}  
done
```
→ UI waits for `response_complete`, then renders the full response at once.

### Scenario 3: Error Mid-Stream
```
token "The sales"  
error {"content": "Model timeout", "recoverable": true}  
done (implicitly implied)
```
→ UI displays partial response and shows error. User can retry.

## Frontend Implementation Checklist

- [ ] Parse Server-Sent Events from `text/event-stream` response
- [ ] Handle `response_complete` even if no tokens arrived (fallback mode)
- [ ] Show thinking indicators for `thinking_step` events
- [ ] Append tokens to display buffer on `token` events
- [ ] Display blinking cursor while `isLoading && hasTokens`
- [ ] Show error message and disable retry if `recoverable === false`
- [ ] Render chart if `chart` event arrives
- [ ] Emit completion callback on `done` event
- [ ] Implement rate-limit backoff for `rate_limited` category errors
- [ ] Validate all JSON event parsing (wrap in try/catch)
- [ ] Abort stream on component unmount (AbortController)

---

## Example Frontend Usage

```jsx
import StreamingChatMessage from './StreamingChatMessage';

function ChatPage() {
  const [query, setQuery] = useState('');
  
  return (
    <div>
      <input 
        value={query} 
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask me about your data..."
      />
      
      <StreamingChatMessage
        query={query}
        datasetId="abc123"
        userId="user456"
        onComplete={(result) => {
          console.log('Chat complete:', result);
        }}
        onError={(error) => {
          console.error('Chat error:', error);
        }}
      />
    </div>
  );
}
```
