# DataSage Chat System — Complete Technical Analysis

> **Generated**: February 10, 2026  
> **Scope**: Backend chat API, AI service, streaming, RAG, and frontend integration

---

## Table of Contents

1. [Endpoints & Communication](#1-endpoints--communication)
2. [Conversation Management](#2-conversation-management)
3. [Context & RAG Pipeline](#3-context--rag-pipeline)
4. [Output Behavior](#4-output-behavior)
5. [Guardrails & Security](#5-guardrails--security)
6. [Performance & Rate Limiting](#6-performance--rate-limiting)
7. [Architecture Diagram](#7-architecture-diagram)
8. [Known Issues & Improvement Opportunities](#8-known-issues--improvement-opportunities)
9. [File Reference](#9-file-reference)

---

## 1. Endpoints & Communication

### Primary Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/datasets/{dataset_id}/chat` | HTTP chat (fallback) |
| `WebSocket` | `/api/ws/chat?token={jwt}` | **Primary** — streaming chat |
| `GET` | `/api/conversations` | List all user conversations |
| `GET` | `/api/conversations/{id}` | Get single conversation |
| `DELETE` | `/api/conversations/{id}` | Delete conversation |

### Request Schema (HTTP)

```python
class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None
```

### WebSocket Message Format

```json
{
  "message": "What are the top products by revenue?",
  "datasetId": "dataset_object_id",
  "conversationId": "optional_conversation_id",
  "streaming": true
}
```

### WebSocket Response Types

| Type | Payload | Description |
|------|---------|-------------|
| `status` | `{status, clientMessageId, rate_limit_remaining}` | Processing started |
| `token` | `{content}` | Single token for streaming |
| `response_complete` | `{fullResponse}` | Complete text response |
| `chart` | `{chartConfig}` | Hydrated Plotly chart data |
| `done` | `{conversationId, chartConfig}` | Final event |
| `error` | `{detail}` | Error message |

---

## 2. Conversation Management

### Storage

- **Database**: MongoDB `conversations` collection
- **Schema**:
  ```python
  {
      "_id": ObjectId,
      "user_id": str,
      "dataset_id": str,
      "created_at": datetime,
      "updated_at": datetime,
      "messages": [
          {"role": "user" | "ai", "content": str, "chart_config": Optional[dict]}
      ]
  }
  ```

### Limits

| Limit | Value |
|-------|-------|
| Max messages per conversation | 500 |
| Warning threshold | 1000 messages |
| Max conversations returned | 200 (in list endpoint) |

### History Handling

- **Full history** is passed to LLM (no windowing or summarization)
- Conversation is **dataset-scoped** — security check prevents cross-dataset access
- Messages include `chart_config` if AI generated a chart

---

## 3. Context & RAG Pipeline

### Context Types Sent to LLM

| Context | Included | Source |
|---------|----------|--------|
| Dataset schema (columns + types) | ✅ | `PromptFactory.rich_context` |
| Sample values per column | ✅ | `column_metadata` |
| Row count | ✅ | `dataset_overview` |
| Conversation history | ✅ | Full `messages[]` array |
| RAG chunks (vector search) | ✅ | FAISS + reranker |
| User filters / dashboard state | ❌ | Not implemented |
| System prompt | ✅ | `CONVERSATIONAL_SYSTEM_PROMPT` |

### Smart Context Selection

The system uses **adaptive context** based on query type:

```python
# "Tiny" context for casual queries:
"Dataset has 10,000 rows and 15 columns. Column names: col1, col2, ..."

# "Rich" context for analytical queries (triggered by keywords):
"total", "sum", "average", "revenue", "compare", "trend", "kpi", etc.
```

### Query Rewriting

Before sending to LLM, queries are rewritten via `query_rewrite.py`:
- Preserves meaning strictly
- Removes filler words and ambiguity
- **NOT shown to user** (internal only)
- Includes validation to prevent empty/too-short rewrites

### RAG Pipeline

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│  FAISS Vector Search            │
│  - k=10 initial retrieval       │
│  - score_threshold=0.3          │
│  - Embedding: BAAI/bge-large    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Reranker Service               │
│  - top_k=5 after reranking      │
│  - score_threshold=0.4          │
│  - use_diversity=True           │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Context Assembly               │
│  - max_tokens=2000              │
│  - Fallback: full context       │
└─────────────────────────────────┘
```

### Chunk Types (RAG)

| Type | Content |
|------|---------|
| `schema` | High-level dataset overview |
| `column` | Individual column metadata + statistics |
| `sample` | Representative data rows |
| `relationship` | Column correlations and patterns |
| `statistics` | Aggregated dataset statistics |

---

## 4. Output Behavior

### Response Types

| Type | Supported | Notes |
|------|-----------|-------|
| Pure text answer | ✅ | Markdown formatted |
| Text + chart config | ✅ | JSON chart specification |
| Text + rendered chart | ✅ | Hydrated Plotly traces |
| Follow-up question | ❌ | Not automatic |
| Error/clarification | ✅ | With suggestions |

### Response Schema

```python
class ConversationalResponse(BaseModel):
    response_text: str  # 1-5000 chars
    chart_config: Optional[Dict[str, Any]] = None
    confidence: str = "High" | "Medium" | "Low"
```

### Chart Generation Flow

**HTTP Mode:**
1. LLM returns `chart_config` in JSON response
2. Column validation + fuzzy matching
3. Hydration to Plotly traces
4. Auto-rendered in frontend

**Streaming Mode:**
1. Text streams token-by-token
2. After completion, keyword detection: `["chart", "histogram", "bar", "pie", ...]`
3. If triggered → second LLM call for chart config
4. Chart sent via WebSocket `type: "chart"`

### Chart Type Support

```python
chart_type_map = {
    "bar": ChartType.BAR,
    "line": ChartType.LINE,
    "pie": ChartType.PIE,
    "scatter": ChartType.SCATTER,
    "histogram": ChartType.HISTOGRAM,
    "heatmap": ChartType.HEATMAP,
    "box": ChartType.BOX_PLOT,
    "treemap": ChartType.TREEMAP,
    "grouped_bar": ChartType.GROUPED_BAR,
    "area": ChartType.AREA
}
```

### Column Matching (Error Recovery)

When LLM suggests wrong column names:

1. **Exact match** → 1.0 confidence
2. **Case-insensitive** → 0.98 confidence
3. **Normalized** (spaces/underscores) → 0.95 confidence
4. **Synonym match** → 0.85 confidence
5. **Fuzzy match** (SequenceMatcher) → threshold 0.6

---

## 5. Guardrails & Security

### Prompt Injection Protection

Blocked patterns (`prompt_sanitizer.py`):

```python
INJECTION_PATTERNS = [
    r'ignore\s+previous\s+instructions',
    r'you\s+are\s+now\s+a',
    r'pretend\s+to\s+be',
    r'new\s+system\s+prompt',
    r'\[INST\]', r'<<SYS>>', r'<\|im_start\|>',
    r'reveal\s+your\s+system\s+prompt',
    r'execute\s+code',
    r"'\s*;\s*drop\s+table",  # SQL injection
    # ... 20+ patterns total
]
```

### Query Limits

| Limit | Value |
|-------|-------|
| Max query length | 2000 characters |
| Injection pattern action | Replace with `[FILTERED]` |

### Off-Topic Detection

Triggers that return a polite redirect:

```python
off_topic_triggers = [
    "hello", "hi", "hey", "good morning", "how are you",
    "thank you", "who is", "what is the capital", "weather",
    "joke", "what time", "news", "stock", "who are you", "bye"
]
```

Response:
> "I'm a specialized data analytics assistant. I can help with trends, charts, forecasts..."

### Data Grounding

System prompt enforces:
- Use ONLY exact column names from context
- Never invent data points or statistics
- State limitations explicitly if data is insufficient

---

## 6. Performance & Rate Limiting

### Rate Limits

| Endpoint | Limit |
|----------|-------|
| Chat (HTTP) | 30/minute |
| Chat (Streaming) | 20/minute |
| WebSocket messages | 30/minute per user |
| WebSocket connections | 5 concurrent per user |

### Timeouts

| Component | Timeout |
|-----------|---------|
| HTTP client (LLM) | 180 seconds |
| WebSocket idle | No explicit timeout |

### Estimated Latency

| Stage | Time |
|-------|------|
| Query rewrite | 0.5-2s |
| RAG retrieval | 0.5-1s |
| LLM response (OpenRouter) | 2-10s |
| Chart hydration | 0.2-1s |
| **Total (HTTP)** | **3-15s** |
| **Streaming first token** | **2-3s** |

---

## 7. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│  Chat.jsx → useWebSocket → useChatStore → PlotlyChart          │
│  - Token streaming display                                      │
│  - Edit/rerun messages                                          │
│  - Chart auto-rendering                                         │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket / HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                         │
│  chat.py: POST /datasets/{id}/chat, WS /ws/chat                │
│  - JWT authentication                                           │
│  - Rate limiting (slowapi)                                      │
│  - Redis connection tracking                                    │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Service Orchestrator                      │
│  ai_service.py:                                                │
│  1. Sanitize input (prompt_sanitizer)                          │
│  2. Load/create conversation (MongoDB)                         │
│  3. Get RAG context (FAISS + reranker)                        │
│  4. Rewrite query (LLM call)                                   │
│  5. Build prompt (PromptFactory)                               │
│  6. Call LLM (streaming or sync)                               │
│  7. Parse response (extract_json)                              │
│  8. Validate columns (column_matcher)                          │
│  9. Hydrate chart (Polars → Plotly)                           │
│  10. Save to conversation (MongoDB)                            │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              LLM Router (OpenRouter)                            │
│  - Primary: Mistral 24B                                        │
│  - Fallback chain: Hermes 405B                                 │
│  - System prompt: CONVERSATIONAL_SYSTEM_PROMPT                 │
│  - Streaming: async generator                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Known Issues & Improvement Opportunities

### Current Limitations

| Issue | Severity | Details |
|-------|----------|---------|
| Keyword-based chart detection | Medium | Streaming uses keyword matching, not semantic understanding |
| No follow-up suggestions | Low | AI doesn't proactively suggest next questions |
| Single dataset only | Medium | Cannot query across multiple datasets |
| Full history sent | Low | No summarization — may hit token limits on long conversations |
| Query rewrite overhead | Low | Adds ~0.5-2s latency for every query |
| Silent chart failures | Medium | Malformed charts fail silently |

### Recommended Improvements

#### High Priority

1. **Chart Classification Step**
   - Add dedicated classifier before chart generation
   - Reduce false positives from keyword matching

2. **Error Transparency**
   - Surface chart generation failures to user
   - Provide actionable feedback

3. **Conversation Summarization**
   - Implement sliding window or summary for long conversations
   - Prevent token limit issues

#### Medium Priority

4. **Multi-Dataset Support**
   - Allow cross-dataset queries
   - Add dataset switching in conversation

5. **Smart Query Rewrite Skip**
   - Skip rewrite for simple queries to reduce latency
   - Use complexity analyzer already present

6. **Parallel Chart Generation**
   - Start chart inference while text is streaming
   - Reduce perceived latency

#### Low Priority

7. **Follow-up Suggestions**
   - Generate 2-3 suggested next questions
   - Improve discoverability of data

8. **Filter Context**
   - Send current dashboard filters to LLM
   - Enable filtered analysis

---

## 9. File Reference

### Backend

| File | Purpose |
|------|---------|
| `api/chat.py` | HTTP & WebSocket endpoints |
| `services/ai/ai_service.py` | Core orchestration |
| `services/ai/query_rewrite.py` | Query rewriting |
| `services/llm_router.py` | LLM routing & streaming |
| `services/conversations/conversation_service.py` | Conversation CRUD |
| `services/datasets/faiss_vector_service.py` | FAISS vector search |
| `services/rag/chunk_service.py` | RAG chunking |
| `services/rag/reranker_service.py` | Chunk reranking |
| `services/charts/column_matcher.py` | Column fuzzy matching |
| `services/charts/hydrate.py` | Chart hydration |
| `core/prompts.py` | Prompt templates |
| `core/prompt_sanitizer.py` | Input sanitization |
| `core/rate_limiter.py` | Rate limiting config |
| `core/output_validator.py` | Response validation |
| `db/schemas.py` | Pydantic models |

### Frontend

| File | Purpose |
|------|---------|
| `pages/Chat.jsx` | Main chat UI |
| `hooks/useWebSocket.js` | WebSocket connection |
| `store/chatStore.js` | Chat state management |
| `components/PlotlyChart.jsx` | Chart rendering |
| `components/ChatHistoryModal.jsx` | Conversation history |

---

## Quick Start for Developers

### Test Chat Endpoint (HTTP)

```bash
curl -X POST "http://localhost:8000/api/datasets/{dataset_id}/chat" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the top 5 products by revenue?"}'
```

### Test WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/chat?token={jwt}');
ws.onopen = () => {
  ws.send(JSON.stringify({
    message: "Show sales trend over time",
    datasetId: "dataset_id",
    streaming: true
  }));
};
ws.onmessage = (event) => console.log(JSON.parse(event.data));
```

---

*This document should be updated when significant changes are made to the chat system.*
