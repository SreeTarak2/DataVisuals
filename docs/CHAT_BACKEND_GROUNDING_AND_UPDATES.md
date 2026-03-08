# Chat Backend: Actual & Relevant Information — Gaps and Updates

This doc answers: **"Is the backend providing actual and relevant information for user queries like most other tools?"** and what to update if not.

---

## 1. Short Answer

- **HTTP chat path**: **Yes.** For data questions (totals, counts, filters, trends, etc.) the backend runs **real SQL** on the dataset via `query_executor` and returns **actual numbers** and optional charts. No hallucination for those.
- **WebSocket (streaming) path**: **No.** It never runs SQL. It only gives the LLM **RAG context** (schema + chunks or `create_context_string`: row count, column names/types, a few sample rows). So for questions like "What is total sales?" or "How many orders by region?" the **streamed text can be made up** — not grounded in real query results.

Because the frontend prefers WebSocket when connected, **most users get ungrounded answers for data questions** unless they hit the HTTP fallback.

---

## 2. How It Works Today

### HTTP path (`process_chat_message_enhanced` → `process_query_with_execution` / `process_chat_message`)

1. **Classification**: `query_classifier.needs_sql_execution(query)` decides:
   - **True** (e.g. "total", "how many", "show me", "by region", "top 10") → **SQL path**
   - **False** (e.g. "describe the dataset", "what columns") → **Metadata path**

2. **SQL path** (grounded):
   - Load dataset → `query_executor.execute_query(query, df, ...)`:
     - LLM generates SQL from NL
     - SQL validated (safety)
     - **DuckDB runs SQL on real data**
     - LLM interprets **actual results** into natural language
   - Response = real numbers + optional SQL + optional chart from real data. **Relevant and actual.**

3. **Metadata path** (weaker but OK for schema/help):
   - `_get_rag_context(...)` → vector chunks or `create_context_string(metadata)` (row count, column list, 3 sample rows)
   - LLM answers from that context only. Fine for "what columns exist?"; not for "what is the sum of X?"

### Streaming path (`process_chat_message_streaming`)

1. **No classification**, no `query_executor`.
2. RAG context → query rewrite → **CONVERSATIONAL** prompt → LLM stream.
3. Chart is inferred from LLM output, then **hydrated from real data** (so the chart is real; the **text** is not necessarily grounded).
4. So: **streamed narrative and numbers are not guaranteed to be actual** for data questions.

### What the LLM sees when it doesn’t run SQL

- **RAG hit**: Chunks from vector search (dataset-derived text), reranked. Quality depends on what’s in the index.
- **RAG miss**: `create_context_string(metadata)` only:
  - `Dataset Overview: N rows, M columns.`
  - `Columns: - col1 (type), - col2 (type), ...` (first 10)
  - Optionally 3 sample rows.

So for "What is total revenue?" the model has **no** aggregate or real totals — it can only guess. That’s why streaming can give wrong or irrelevant numbers.

---

## 3. What to Update (Prioritized)

### 3.1 Critical: Ground streaming with real execution (recommended)

**Goal**: For queries that need data, streaming should still use **executed SQL** and real results; only the **delivery** is streamed (e.g. narrate the pre-computed answer token-by-token).

**Option A — Run SQL first, then stream the answer (simplest)**

In `process_chat_message_streaming` (in `ai_service.py`), after guardrails and conversation load:

1. **Classify**: `needs_sql = query_classifier.needs_sql_execution(query)`.
2. **If `needs_sql`**:
   - Load dataset and call `query_executor.execute_query(query, df, dataset_id, ...)` (same as HTTP).
   - Get back `result["response"]`, `result["sql"]`, `result.get("data")`, etc.
   - **Stream** the pre-computed `result["response"]` token-by-token (e.g. word-by-word) so the UI still shows typing.
   - Emit `response_complete`, then if you have a chart from results, emit `chart` and in `done` pass `conversation_id`, `chart_config`, and **include `result["sql"]`** so the frontend can show it (e.g. in the existing SQL `<details>`).
   - Save the same AI message (text + sql + chart_config) to the conversation and yield `done`.
3. **If not `needs_sql`**: Keep current behavior (RAG + CONVERSATIONAL stream).

Effects:

- Data questions over WebSocket become **actual and relevant** (same as HTTP).
- UX stays streaming (tokens appear over time).
- One code path for “truth”: `query_executor.execute_query`.

**Option B — Stream an interpretation of real results**

If you want the wording to feel more “streaming from the model”:

- Run SQL and get `result` as above.
- Build a small prompt that includes the **actual result** (e.g. "The user asked: ... The query returned: [table or summary]. Write a short, natural language answer that uses only these numbers.").
- Stream the **LLM output** of that prompt (so the model is only paraphrasing/formatting real data, not inventing numbers).

Option A is simpler and avoids any chance of the model drifting from the result.

**Concrete place to change**

- **File**: `version2/backend/services/ai/ai_service.py`
- **Function**: `process_chat_message_streaming` (around the block after QUIS routing and before “RAG context retrieval”).
- **Steps**:
  1. After loading `dataset_doc` and `metadata`, add:
     - `needs_sql = query_classifier.needs_sql_execution(query)`
  2. If `needs_sql`, load the dataset (you already have `dataset_doc`, get `file_path` and `load_dataset`), then:
     - `result = await query_executor.execute_query(query=query, df=df, dataset_id=dataset_id, return_raw=False)`
  3. If `result["success"]`:
     - Build `ai_text` from `result["response"]` and optionally append a small “Query Results” section from `result.get("data")` (reuse the same formatting as in `process_query_with_execution`).
     - Optionally build chart from results (reuse `_generate_chart_for_results` or equivalent).
     - Stream `ai_text` token-by-token (e.g. `for word in ai_text.split(): yield {"type": "token", "content": word + " "}`), then `response_complete`, then `chart` if any, then save conversation and `done` with `conversation_id`, `chart_config`, and SQL for the frontend.
  4. If not `result["success"]`, fall through to the existing RAG + LLM stream (so failed SQL doesn’t block the user).

This way the backend **always** uses actual, relevant information for data queries on both HTTP and WebSocket.

---

### 3.2 High: Make “metadata” context richer (when you don’t run SQL)

**Goal**: When the answer is metadata-only (e.g. “what columns?”, “describe the data”), the LLM still gets a bit more than row count + column names so answers stay relevant.

**Updates**:

- **`create_context_string`** (e.g. in `dataset_loader.py` or wherever it’s defined): Extend with:
  - Numeric columns: min/max/mean or distinct count when cheap.
  - Categoricals: distinct count and a few example values.
  - Optionally 1–2 sentence “dataset summary” if you have it in metadata (e.g. from ingestion).
- **RAG**: Prefer indexing not only raw chunks but also:
  - Schema + column descriptions.
  - Small summary stats per column if you precompute them at ingest.

This doesn’t replace SQL for “what is the total X?” but makes descriptive answers better and more consistent with the real data.

---

### 3.3 Medium: Consistent SQL and chart in streaming

- When you run SQL in the streaming path, attach **`sql`** to the saved message and to the payload the frontend expects (e.g. in `done` or in the message object), so the UI can show “View SQL” as it does for HTTP.
- Reuse the same chart-from-results logic as HTTP so streaming and HTTP both show charts from **real** result data when appropriate.

---

### 3.4 Optional: Broaden SQL classification slightly

- **`QueryClassifier.needs_sql_execution`**: Today it’s pattern-based. If you see data questions wrongly treated as “metadata only”, add patterns or a tiny classifier so more clearly analytical questions go to the SQL path on both HTTP and (after 3.1) streaming.
- You can also add a “when in doubt, run SQL” rule for short questions that look like they’re about the data (e.g. contain column-like words and a question mark).

---

## 4. Summary Table

| Path              | Data questions (totals, counts, filters, etc.) | Metadata/help questions      |
|-------------------|-------------------------------------------------|------------------------------|
| HTTP              | ✅ Real SQL → actual numbers                     | ✅ RAG / context             |
| WebSocket (today) | ❌ LLM from RAG only → can hallucinate          | ✅ RAG / context             |
| WebSocket (after 3.1) | ✅ Same as HTTP (run SQL, stream answer)   | ✅ RAG / context             |

**Bottom line**: The backend can provide actual and relevant information, but only the HTTP path does it for data queries today. **Implement Section 3.1 (ground streaming with real execution)** so both paths use real data for the same queries; then optionally do 3.2–3.4 for richer context and consistency.
