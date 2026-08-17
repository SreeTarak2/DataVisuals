# Async Query Execution Architecture

> DataSage SQL Engine — Design v1

## Overview

Production-grade async SQL execution pipeline with cancellation, resource governance, pagination, and persistence. Replaces the current synchronous `POST /api/v2/query/execute` (which blocks the HTTP response until DuckDB finishes) with an async pattern: submit → poll → fetch results.

---

## 1. State Machine

Every query execution transitions through these states:

```
          ┌──────────┐
          │  QUEUED   │
          └────┬─────┘
               │ (acquires concurrency slot)
               ▼
          ┌──────────┐       ┌──────────┐
          │ RUNNING   │──────▶│ CANCELLED│  ← POST /cancel
          └────┬─────┘       └──────────┘
               │ (completes or fails)
               ▼
     ┌─────────────────┐
     │  COMPLETED       │  ← results available at GET /results
     │  or  FAILED      │
     └─────────────────┘
          │ (TTL expires)
          ▼
     ┌──────────┐
     │  EXPIRED  │  ← garbage collected after TTL
     └──────────┘
```

No `PENDING` / `SUBMITTED` distinction — the execute endpoint either queues or runs immediately depending on concurrency capacity. The client sees a unified `query_id` from submission.

---

## 2. Endpoint Contracts

All routes live under `/api/v2/query` to match the existing semantic layer prefix.

### `POST /api/v2/query/execute`

Submit SQL for async execution. Returns immediately with a `query_id`.

**Request:**

```json
{
  "dataset_id": "uuid-string",
  "sql": "SELECT category, SUM(revenue) FROM data GROUP BY category",
  "limit": 1000,
  "workspace_id": "optional-workspace-uuid"
}
```

**Response (202 Accepted) — queued or running:**

```json
{
  "query_id": "qry_a1b2c3d4e5f6",
  "status": "queued",
  "position": 0,
  "created_at": "2026-07-11T14:30:00Z"
}
```

**Response (200 OK) — immediate result for fast queries:**

```json
{
  "query_id": "qry_a1b2c3d4e5f6",
  "status": "completed",
  "execution_time_ms": 42,
  "row_count": 5,
  "result": {
    "columns": ["category", "revenue"],
    "rows": [["Electronics", 52000], ["Clothing", 34000]]
  }
}
```

**Backend processing:**

```
POST /api/v2/query/execute
  │
  ├─ 1. Validate SQL (SQLValidator.validate — eventual sqlglot replacement)
  │
  ├─ 2. Generate query_id: f"qry_{uuid4().hex[:12]}"
  │
  ├─ 3. Save to MongoDB: query_log collection
  │     { query_id, dataset_id, user_id, sql, limit,
  │       status: "queued", created_at, ttl_index }
  │
  ├─ 4. Acquire concurrency slot
  │     ├─ slot available → asyncio.create_task(run_query(query_id))
  │     └─ at capacity   → status stays "queued"
  │                        (future slot release triggers dequeue)
  │
  └─ 5. Return 202 { query_id, status }
```

Resource governance applied inside `run_query()`:

```python
async def run_query(query_id: str):
    # Step 1: Load dataset (async — Polars from disk/S3)
    df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)

    # Step 2: Apply DuckDB safety guards
    conn = duckdb.connect(":memory:", read_only=True)
    conn.execute("SET memory_limit = '2GB'")
    conn.execute("SET statement_timeout = '60s'")

    # Step 3: Move sync execution to thread pool
    loop = asyncio.get_running_loop()
    result_df, error = await loop.run_in_executor(
        _thread_pool,  # shared ThreadPoolExecutor(max_workers=4)
        _execute_in_duckdb,
        conn, sql, df, limit
    )
```

This is the core fix — `run_in_executor` moves the blocking `conn.execute()` call off the event loop, and `asyncio.wait_for` wraps it for timeout:

```python
try:
    result_df, error = await asyncio.wait_for(
        loop.run_in_executor(_thread_pool, _execute_in_duckdb, conn, sql, df, limit),
        timeout=settings.QUERY_TIMEOUT or 120
    )
except asyncio.TimeoutError:
    conn.close()
    await _update_status(query_id, "failed", error="Query timed out")
```

---

### `GET /api/v2/query/{query_id}/status`

Poll for query completion. Lightweight — reads MongoDB document only.

**Response:**

```json
{
  "query_id": "qry_a1b2c3d4e5f6",
  "status": "running",
  "created_at": "2026-07-11T14:30:00Z",
  "started_at": "2026-07-11T14:30:01Z",
  "execution_time_ms": null,
  "row_count": null
}
```

**Status transitions during polling:**

| Status | Next States |
|---|---|
| `queued` | `running` |
| `running` | `completed` / `failed` |
| `cancelled` | terminal (no further changes) |
| `completed` | terminal |
| `failed` | terminal |

**Client-side polling strategy:**

```
submit → POST /execute → get query_id
  │
  ├─ optimistic: GET /status after 500ms
  │     if "completed" → GET /results immediately
  │
  ├─ if "running":
  │     poll /status with exponential backoff:
  │       200ms → 500ms → 1s → 2s → 5s → 10s (capped)
  │
  └─ if "failed" or "cancelled":
        show error state in SqlResultTable
```

---

### `GET /api/v2/query/{query_id}/results`

Fetch paginated query results (available only when `status: "completed"`).

**Query params:** `?offset=0&limit=100`

**Response:**

```json
{
  "query_id": "qry_a1b2c3d4e5f6",
  "status": "completed",
  "columns": ["category", "revenue"],
  "rows": [
    ["Electronics", 52000],
    ["Clothing", 34000]
  ],
  "row_count": 5,
  "total_rows": 5,
  "offset": 0,
  "limit": 100,
  "execution_time_ms": 42,
  "truncated": false
}
```

**Design decisions for results:**

- **Small results (≤10K rows):** stored inline in the MongoDB `query_log` document.
- **Large results (>10K rows or >1MB):** stored as newline-delimited JSON on disk at `data/query_results/{query_id}.ndjson`. The `/results` endpoint reads from disk with pagination.
- **Truncation:** If result exceeds `limit`, `truncated: true` is returned. Client shows "Results truncated. Download full CSV." link.

---

### `POST /api/v2/query/{query_id}/cancel`

Cancel a running query.

**Response:**

```json
{
  "query_id": "qry_a1b2c3d4e5f6",
  "status": "cancelled",
  "cancelled_at": "2026-07-11T14:30:05Z"
}
```

**Backend cancellation mechanism:**

```python
_query_tasks: dict[str, asyncio.Task] = {}  # module-level registry

async def run_query(query_id: str, ...):
    task = asyncio.current_task()
    _query_tasks[query_id] = task
    try:
        ...  # execute
    finally:
        _query_tasks.pop(query_id, None)

async def cancel_query(query_id: str):
    task = _query_tasks.get(query_id)
    if task and not task.done():
        task.cancel()  # raises CancelledError inside run_query
        # cleanup handler closes DuckDB connection
    await _update_status(query_id, "cancelled")
```

`task.cancel()` raises `asyncio.CancelledError` inside the coroutine. The `finally` block in `run_query()` closes the DuckDB connection (which terminates the stuck query on the C++ side).

---

## 3. Thread Pool Architecture

```
                  asyncio event loop
                ┌──────────────────────┐
                │  FastAPI endpoints   │
                │  MongoDB reads/writes│
                │  Dataset loading     │
                └─────────┬────────────┘
                          │
                run_in_executor()
                          │
                          ▼
      ┌────────────────────────────────────┐
      │   ThreadPoolExecutor(max_workers=4)│
      │────────────────────────────────────│
      │  Thread 1: conn.execute(SELECT ...)│
      │  Thread 2: conn.execute(SELECT ...)│
      │  Thread 3: (idle)                  │
      │  Thread 4: (idle)                  │
      └────────────────────────────────────┘
                │
                ▼
       duckdb.connect(":memory:")
       SET memory_limit = '2GB'
       SET statement_timeout = '60s'
       conn.register("data", pandas_df)
       conn.execute(f"SELECT * FROM ({sql}) LIMIT {limit}")
```

**Why 4 workers?**

- Each worker gets its own DuckDB connection (isolated, read-only)
- Each connection has its own `memory_limit` guard
- The 5th+ query is queued, not rejected — it waits for a slot
- 4 workers × 2GB = 8GB max concurrent DuckDB memory (safe for most hosts)

---

## 4. Query Persistence (MongoDB)

**Collection:** `query_log`

```javascript
{
  _id: "qry_a1b2c3d4e5f6",
  dataset_id: "ds-uuid",
  user_id: "user-uuid",
  workspace_id: "ws-uuid",                // optional
  sql: "SELECT category, SUM(revenue) FROM data GROUP BY category",
  limit: 1000,
  status: "completed",                     // queued | running | completed | failed | cancelled
  created_at: ISODate("2026-07-11T14:30:00Z"),
  started_at: ISODate("2026-07-11T14:30:01Z"),
  completed_at: ISODate("2026-07-11T14:30:02Z"),
  execution_time_ms: 1200,
  row_count: 5,
  total_rows: 5,
  columns: ["category", "revenue"],
  error: null,
  result_stored: "inline",                // inline | file
  result_file_path: null,                 // for file-stored results
  ttl_expire_at: ISODate("2026-07-12T14:30:00Z")  // TTL index: 24h
}
```

**Indexes:**

| Index | Purpose |
|---|---|
| `{ _id: 1 }` | Primary lookup |
| `{ user_id: 1, created_at: -1 }` | User query history |
| `{ dataset_id: 1, created_at: -1 }` | Per-dataset history |
| `{ status: 1 }` | Status polling queries |
| `{ ttl_expire_at: 1 }` | TTL index (expire after 24h) |

---

## 5. Concurrency & Queuing

```
         ┌─────────────────┐
         │  Concurrency    │
         │  Controller     │
         │  max_workers=4  │
         └────────┬────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
┌────────┐               ┌──────────────┐
│ SLOT   │               │ WAIT QUEUE   │
│ ACQUIRED│              │ FIFO, max 20 │
└────────┘               └──────────────┘
```

**Implementation:**

```python
class QueryConcurrencyController:
    def __init__(self, max_workers: int = 4):
        self._semaphore = asyncio.Semaphore(max_workers)
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=20)

    async def acquire(self) -> Optional[bool]:
        """Try to acquire a slot."""
        if self._semaphore.locked():
            try:
                self._queue.put_nowait("placeholder")
                return False  # queued
            except asyncio.QueueFull:
                return None  # rejected → 429
        await self._semaphore.acquire()
        return True  # slot acquired

    def release(self):
        self._semaphore.release()
        try:
            self._queue.get_nowait()
            # signal dequeue (via Future or event)
        except asyncio.QueueEmpty:
            pass
```

When a slot opens, the controller checks the wait queue and schedules the next queued query.

---

## 6. DuckDB Safety Configuration

Every `duckdb.connect()` call applies:

```python
conn = duckdb.connect(":memory:", read_only=True)
conn.execute("SET memory_limit = '2GB'")        # Prevent OOM
conn.execute("SET statement_timeout = '60000'") # 60s query timeout
conn.execute("SET threads = 2")                 # Limit CPU usage
conn.execute("SET max_expression_depth = 50")   # Prevent deep recursion
```

These are reset per-connection so runaway queries cannot leak between sessions.

---

## 7. Frontend Integration

The existing `sqlAPI.executeSql()` in `api.js` needs three changes:

```javascript
// NEW — async with polling:
executeSql: async (datasetId, sql, limit = 1000) => {
  const submitRes = await api.post('/api/v2/query/execute', {
    dataset_id: datasetId, sql, limit
  });
  const { query_id, status } = submitRes.data;

  if (status === 'completed') return submitRes;

  const delays = [200, 500, 1000, 2000, 5000, 10000];
  for (const delay of delays) {
    await new Promise(r => setTimeout(r, delay));
    const statusRes = await api.get(`/api/v2/query/${query_id}/status`);
    const s = statusRes.data.status;
    if (s === 'completed') return api.get(`/api/v2/query/${query_id}/results`);
    if (s === 'failed' || s === 'cancelled')
      throw new Error(statusRes.data.error || 'Query failed');
  }
  return api.get(`/api/v2/query/${query_id}/results?timeout=60000`);
},
```

Additionally, `SqlEditorPanel.jsx` needs:
- **Cancel button** in the toolbar (when query is running)
- **Status indicator** (spinner during "running", elapsed time counter)
- **History panel** toggle to show recent queries from `/api/v2/query/history`

---

## 8. File Layout

```
version2/backend/
  api/
    v2/                              ← new directory
      __init__.py
      query_routes.py                ← POST /execute, GET /{id}/status, etc.
  services/
    query/
      executor.py                    ← existing (add async wrapper)
      async_executor.py              ← NEW: run_in_executor + cancellation
      concurrency.py                 ← NEW: QueryConcurrencyController
      query_store.py                 ← NEW: MongoDB CRUD for query_log
      thread_pool.py                 ← NEW: shared ThreadPoolExecutor
```

---

## 9. Configuration

In `core/config.py`, add:

```python
# Async Query Execution
QUERY_TIMEOUT: int = int(os.getenv("QUERY_TIMEOUT", "120"))          # seconds
QUERY_MAX_WORKERS: int = int(os.getenv("QUERY_MAX_WORKERS", "4"))   # DuckDB threads
QUERY_MAX_QUEUE: int = int(os.getenv("QUERY_MAX_QUEUE", "20"))      # wait queue depth
QUERY_MEMORY_LIMIT: str = os.getenv("QUERY_MEMORY_LIMIT", "2GB")    # per-connection
QUERY_RESULT_TTL_HOURS: int = int(os.getenv("QUERY_RESULT_TTL_HOURS", "24"))
```

---

## 10. Implementation Priority

| Step | What | Why |
|------|------|-----|
| 1 | `query_routes.py` — POST /execute with `run_in_executor` + `asyncio.wait_for` | Fixes timeout + non-blocking HTTP |
| 2 | `query_store.py` — MongoDB CRUD + TTL index | Enables polling + persistence |
| 3 | `async_executor.py` — Cancellation via `task.cancel()` + DuckDB cleanup | Enables cancellation |
| 4 | `concurrency.py` — Semaphore + queue | Resource governance |
| 5 | Frontend: polling in `sqlAPI.executeSql` + cancel button | Makes it usable |
| 6 | Large-result file storage (NDJSON on disk) | Pagination for big results |
| 7 | Query history UI — recent queries panel | Persistence UX |
