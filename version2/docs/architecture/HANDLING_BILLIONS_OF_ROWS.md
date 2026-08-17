# Datasage: Handling Billions of Rows — Architecture & Strategy

> **Purpose**: This document explains how Datasage handles large datasets (100K to 1B+ rows) across all features — SQL execution, AI chat, RAG, profiling, and schema context. Use this as a reference during frontend design, backend refactoring, and infrastructure decisions.
>
> **Status**: Living document. Updated as bottlenecks are identified and fixed.

---

## Table of Contents

1. [Current Architecture — The Bottlenecks](#1-current-architecture--the-bottlenecks)
2. [Why Polars → Pandas → DuckDB?](#2-why-polars--pandas--duckdb)
3. [Data Flow: How a Query Travels Through the System](#3-data-flow-how-a-query-travels-through-the-system)
4. [Bottleneck Analysis by Scale](#4-bottleneck-analysis-by-scale)
5. [Proposed Fixes (Priority Order)](#5-proposed-fixes-priority-order)
6. [Competitor Analysis: How Looker/Tableau/Sigma Handle Big Data](#6-competitor-analysis-how-lookertableausigma-handle-big-data)
7. [Cloudflare Workers & KV — Are They Useful?](#7-cloudflare-workers--kv--are-they-useful)
8. [Frontend Design Implications](#8-frontend-design-implications)
9. [Glossary](#9-glossary)
10. [Change Log](#10-change-log)

---

## 1. Current Architecture — The Bottlenecks

### 1.1 Data Loading (🔴 Critical)

```
User uploads CSV (100MB–5GB)
    ↓
enhanced_dataset_service.upload_dataset()
    ↓
file_storage_service.save_file()          ✅ Streams to disk, fine
    ↓
process_dataset()                          🔴 Loads full file into Polars
    ↓
load_dataset(file_path)                    🔴 pl.read_csv() → ALL rows in memory
    ↓
get_dataset_metadata()                     🔴 Iterates ALL rows for stats
    ↓
faiss_vector_service.index_dataset()       🟡 Indexes from metadata (fine)
```

### 1.2 AI Chat / SQL Execution (🔴 Critical)

```
User asks "Show revenue by category"
    ↓
ensure_dataframe_for_agent(dataset_id)     🔴 Loads FULL dataset
    ↓
query_executor.generate_sql(query, df)     🟡 LLM call (no data needed)
    ↓
query_executor.execute_sql(sql, df)        🔴 Polars → Pandas → DuckDB
    ↓
  df.to_pandas()                           🔴 COPY 1: Full dataset → Pandas
  conn.register("data", pandas_df)          🔴 COPY 2: Pandas → DuckDB
  conn.execute("SELECT ...")               🟢 DuckDB runs query (fast)
```

### 1.3 Schema Context for AI Prompts (🟡 Moderate)

```
_generate_sql() → _get_column_schema(df)   🟡 Iterates ALL rows for sample values
                → _get_sample_data(df)      🟡 Gets first 5 rows (fine)
                → _get_data_stats(df)       🟡 Computes n_unique, min/max on ALL rows
```

**Note**: The schema context string sent to the LLM is SMALL (column names + types + 5 sample rows = ~500 chars). But computing it requires iterating the full DataFrame. This work can be cached.

### 1.4 Data Profiling (🔴 Critical at scale)

```
process_dataset_pipeline()
    ↓
load_dataset(file_path)                     🔴 Full load
    ↓
DataProfiler.profile(df)                    🔴 Iterates ALL rows for every column
    ↓
  n_unique() on each column                 🔴 Minutes per column at 1B rows
  min/max/mean/std on numeric columns       🔴 Full scan per metric
  value_counts() on categorical columns     🔴 Full GROUP BY scan
```

### 1.5 RAG / Vector Search (🟡 Moderate)

```
auto_index_dataset_to_vector_db()
    ↓
faiss_vector_service.add_dataset_to_vector_db()   ✅ From metadata (fine)
    ↓
chunk_service.create_chunks_from_metadata(df)      🟡 Depends on df size
    ↓
faiss_vector_service.index_dataset_chunks()        🟡 Depends on chunk count
```

---

## 2. Why Polars → Pandas → DuckDB?

### 2.1 The Exact Code Path

```python
# In services/query/executor.py :: execute_sql()

# Step 1: Polars loads the full dataset (happens BEFORE execute_sql)
df = pl.read_csv("1billion_rows.csv")     # Memory: ~8GB for 1B rows

# Step 2: Polars → Pandas conversion (inside execute_sql)
try:
    pandas_df = df.to_pandas()            # Memory: ~8GB AGAIN = 16GB total
except ModuleNotFoundError:
    pandas_df = pd.DataFrame(df.to_dicts())  # Fallback: even slower

# Step 3: Pandas → DuckDB registration
conn.register("data", pandas_df)          # Memory: ~8GB AGAIN = 24GB total

# Step 4: DuckDB executes the query (finally!)
cursor = conn.execute("SELECT category, SUM(revenue) FROM data GROUP BY category")
```

### 2.2 Why This Exists

The historical reason: DuckDB's Python API `register()` method natively accepts:
- Pandas DataFrames ✅ (native C++ bridge)
- Arrow tables ✅ (native C++ bridge)
- Polars DataFrames ❌ (no direct bridge — Polars must be converted to Arrow or Pandas first)

At the time this code was written (earlier version of DuckDB), the Polars→DuckDB path was not well-supported, so the developer used Pandas as the bridge.

### 2.3 Memory Impact at Scale

| Rows | Data Size | Polars Memory | Pandas Memory | DuckDB Memory | Total (Polar+Pandas+DuckDB) |
|------|-----------|--------------|--------------|--------------|----------------------------|
| 100K | ~10MB | ~20MB | ~20MB | ~20MB | **~60MB** ✅ Fine |
| 1M | ~100MB | ~200MB | ~200MB | ~200MB | **~600MB** 🟡 Manageable |
| 10M | ~1GB | ~2GB | ~2GB | ~2GB | **~6GB** 🔴 Expensive |
| 100M | ~10GB | ~20GB | ~20GB | ~20GB | **~60GB** 🔴 Likely OOM |
| 1B | ~100GB | ~200GB | ~200GB | ~200GB | **~600GB** 🔴 Impossible |

### 2.4 The Fix: DuckDB Reads Files Directly

DuckDB can read CSV and Parquet files **directly without any Python bridge**:

```python
# ✅ CORRECT — No Polars, No Pandas, DuckDB streams from disk
def execute_sql_from_file(sql: str, file_path: str) -> pl.DataFrame:
    conn = duckdb.connect(":memory:")
    
    # Tell DuckDB to read the file directly — uses streaming, columnar I/O
    # DuckDB reads only the columns needed by the SQL query
    result_sql = f"""
        SELECT * FROM (
            {sql.replace('FROM data', 'FROM read_csv_auto(:file_path)')}
        ) AS subquery LIMIT 1000
    """
    
    cursor = conn.execute(result_sql, {"file_path": file_path})
    # ... fetch results into Polars (result is small, this is fine)
```

**This single change eliminates all three memory copies.** Memory goes from:
```
❌ Before:  200GB (Polars) + 200GB (Pandas) + 200GB (DuckDB) = 600GB
✅ After:   <200MB (DuckDB streaming) — never loads full dataset
```

---

## 3. Data Flow: How a Query Travels Through the System

### 3.1 Current Flow (at 100K rows)

```
User: "Show me revenue by category"
    │
    ▼
WebSocket (api/chat/routes.py)
    │
    ▼
copilot_service.process_streaming()
    │
    ▼
CopilotOrchestrator.process()
    │
    ├─ Stage 1: IntentClassifier.classify()
    │     Uses query text only — NO DATA LOADED
    │
    ├─ Stage 2: SqlExecutor.execute()
    │     ├─ ensure_dataframe_for_agent()     ← 🔴 LOADS FULL DATASET
    │     └─ query_executor.execute_query()
    │           ├─ generate_sql()              ← LLM call (needs schema)
    │           ├─ _estimate_row_count()       ← runs COUNT(*)
    │           └─ execute_sql()               ← 🔴 Polars→Pandas→DuckDB
    │
    ├─ Stage 3: ReasoningEngine.synthesize()
    │     Uses query results — NO DATA RE-LOADED
    │
    ├─ Stage 4: ResponseVerifier.verify()
    │     Validates response text
    │
    └─ Stage 5: Stream response
          Yields tokens, chart config, done chunk
```

### 3.2 Fixed Flow (at 1B rows)

```
User: "Show me revenue by category"
    │
    ▼
WebSocket (api/chat/routes.py)
    │
    ▼
copilot_service.process_streaming()
    │
    ▼
CopilotOrchestrator.process()
    │
    ├─ Stage 1: IntentClassifier.classify()
    │     Uses query text only — NO DATA LOADED
    │
    ├─ Stage 2: SqlExecutor.execute()
    │     ├─ build_compact_schema_context()   ← ✅ From CACHE (no data load)
    │     └─ query_executor.execute_query()
    │           ├─ generate_sql()              ← LLM (schema from cache)
    │           ├─ _estimate_row_count()       ← ✅ DuckDB counts on file directly
    │           └─ execute_sql()               ← ✅ DuckDB reads file DIRECTLY
    │                                            No Polars, No Pandas.
    │
    ├─ Stage 3: ReasoningEngine.synthesize()
    │     Uses query results — always small (<1000 rows)
    │
    ├─ Stage 4: ResponseVerifier.verify()
    │
    └─ Stage 5: Stream response
```

---

## 4. Bottleneck Analysis by Scale

### 4.1 At 100K Rows (Current Testing Size)

| Feature | Status | Memory | Time |
|---------|--------|--------|------|
| Data loading | ✅ Fine | ~20MB | ~1s |
| SQL execution | ✅ Fine | ~60MB (3 copies) | <100ms |
| Schema context | ✅ Fine | ~20MB | ~10ms |
| Data profiling | ✅ Fine | ~20MB | ~5s |
| RAG indexing | ✅ Fine | ~20MB | ~3s |

### 4.2 At 1M Rows

| Feature | Status | Memory | Time |
|---------|--------|--------|------|
| Data loading | ✅ Fine | ~200MB | ~5s |
| SQL execution | 🟡 OK | ~600MB (3 copies) | <500ms |
| Schema context | 🟡 OK | ~200MB | ~50ms |
| Data profiling | 🟡 OK | ~200MB | ~30s |
| RAG indexing | 🟡 OK | ~200MB | ~15s |

### 4.3 At 10M Rows

| Feature | Status | Memory | Time |
|---------|--------|--------|------|
| Data loading | 🔴 Slow | ~2GB | ~30s |
| SQL execution | 🔴 High memory | ~6GB (3 copies) | ~2s |
| Schema context | 🔴 Slow | ~2GB | ~500ms |
| Data profiling | 🔴 Slow | ~2GB | ~5min |
| RAG indexing | 🔴 Slow | ~2GB | ~2min |

### 4.4 At 100M Rows

| Feature | Status | Memory | Time |
|---------|--------|--------|------|
| Data loading | 🔴 Crash | OOM (>20GB) | N/A |
| SQL execution | 🔴 Crash | OOM | N/A |
| Schema context | 🔴 Crash | OOM | N/A |
| Data profiling | 🔴 Crash | OOM | N/A |
| RAG indexing | 🔴 Crash | OOM | N/A |

### 4.5 At 1B Rows

| Feature | Status |
|---------|--------|
| Everything | 🔴 **Cannot run. System crashes during data load.** |
| AQP approximate mode | ✅ **Would work** — but only after the data loading fix |
| DuckDB direct read | ✅ **Would work** — DuckDB handles 1B rows easily |

---

## 5. Proposed Fixes (Priority Order)

### Fix #1: DuckDB Reads Files Directly (🔴 Critical)

**Impact**: Enables all features at 1B rows.
**Effort**: ~15 lines of code in `executor.py` and `sql_executor.py`.

**What changes**:
- `execute_sql()` receives a `file_path` instead of (or in addition to) a DataFrame
- DuckDB uses `read_csv_auto(file_path)` or `read_parquet(file_path)` instead of `register("data", pandas_df)`
- Eliminates ALL three memory copies (Polars → Pandas → DuckDB)

```python
# Before
pandas_df = df.to_pandas()
conn.register("data", pandas_df)

# After
conn.execute(f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{file_path}')")
```

### Fix #2: Default Agent Data to Sampling (🔴 Critical)

**Impact**: Prevents OOM when agents load datasets.
**Effort**: ~5 lines in `enhanced_dataset_service.py`.

**What changes**:
- `ensure_dataframe_for_agent()` defaults `sample=True`
- Only loads 10K rows by default
- Full load only when explicitly requested (e.g., user clicks "Export All")

### Fix #3: Profiling Uses DuckDB Streaming (🟡 Important)

**Impact**: Profiling pipeline completes at scale.
**Effort**: ~30 lines in `data_profiler.py` and `dataset_loader.py`.

**What changes**:
- Replace `df.n_unique()`, `df.min()`, `df.max()` etc. with DuckDB SQL queries
- SQL queries stream from file — never load full dataset into memory

### Fix #4: Schema Context from Cache (🟡 Important)

**Impact**: Eliminates slow startup time for AI chat.
**Effort**: ~10 lines in `executor.py`.

**What changes**:
- Schema context (column names + types + sample values) is computed once at upload time
- Stored in MongoDB metadata
- AI chat reads from cache instead of iterating the loaded DataFrame

### Fix #5: Parquet Conversion at Upload Time (🟢 Nice to have)

**Impact**: 5-10x faster reads, 2-3x compression.
**Effort**: ~10 lines in `process.py`.

**What changes**:
- After upload, convert CSV → Parquet using DuckDB
- All subsequent reads use Parquet instead of CSV
- Parquet is columnar + compressed + has embedded statistics

---

## 6. Competitor Analysis: How Looker/Tableau/Sigma Handle Big Data

### 6.1 Looker (Google Cloud)

| Aspect | Detail |
|--------|--------|
| **Architecture** | **Never loads data into memory.** Every query is sent as SQL to BigQuery/Snowflake. Looker is a thin translation layer (LookML → SQL). |
| **Billion-row strategy** | The **warehouse** does the heavy lifting. BigQuery's distributed MPP engine scans 1B rows in 15-45s. |
| **Cold start** | 2-5s — BigQuery must compile the query, allocate slots, then execute. |
| **Cost** | ~$5/TB scanned. A full scan of 1B rows (~100GB) = ~$0.50. Repeated queries add up fast. |
| **Caching** | Looker's node-based cache with configurable TTL. Must be explicitly configured. |
| **Weakness** | Network latency, warehouse cold starts, expensive at scale, no approximate mode. |

### 6.2 Tableau

| Aspect | Detail |
|--------|--------|
| **Architecture** | Hybrid: either **live connection** (queries pass through to warehouse) or **extracts** (proprietary .hyper file with pre-computed data). |
| **Billion-row strategy** | Extracts pre-compute and compress data into columnar .hyper format. Live queries go to warehouse. |
| **Cold start** | Extracts: instant (loaded into memory). Live: same as warehouse (2-30s). |
| **Cost** | License: $70-$150/user/month + warehouse compute. |
| **Weakness** | Extracts are stale (need manual refresh). Live queries are slow. No approximate mode. |

### 6.3 Sigma Computing

| Aspect | Detail |
|--------|--------|
| **Architecture** | **Live SQL only.** Every spreadsheet formula translates to SQL that runs on Snowflake/Databricks. Never loads data into browser or middleware. |
| **Billion-row strategy** | Warehouse does the heavy lifting (same as Looker). Sigma is a pure UI layer. |
| **Weakness** | 100% dependent on warehouse performance and budget. |

### 6.4 Metabase

| Aspect | Detail |
|--------|--------|
| **Architecture** | **Loads data into embedded database** (H2 for apps, PostgreSQL for production). Uses row-oriented storage. |
| **Billion-row strategy** | **Cannot handle billion rows.** Row-oriented queries on large data cause OOM or timeouts. |
| **Weakness** | **Same fundamental problem as our current approach.** Row-oriented, loads everything. |

### 6.5 MotherDuck

| Aspect | Detail |
|--------|--------|
| **Architecture** | **Hybrid local/cloud.** Uses DuckDB locally (in-browser WASM or Python embedded) for zero-latency queries. Cloud backend for heavy multi-user JOINs. |
| **Billion-row strategy** | DuckDB reads Parquet files directly — never loads full dataset into memory. Uses streaming, vectorized execution. |
| **Cold start** | Local: 0ms (in-process). Cloud: ~100ms ("Duckling" per-tenant isolated instances). |
| **Cost** | Free tier + paid cloud. Per-second billing. Scale-to-zero. |
| **Weakness** | Requires their managed cloud for multi-user. Closed-source extensions. |

### 6.6 Key Takeaways

| What they do | What we should do |
|-------------|-------------------|
| **Looker/Sigma**: Push queries to warehouse, never load data | We don't have a warehouse — **DuckDB reads files directly** instead |
| **Tableau**: Pre-compute extracts | **Parquet conversion** at upload time serves the same purpose |
| **MotherDuck**: DuckDB reads Parquet directly | **Same** — we already use DuckDB, just need to bypass Polars/Pandas |
| **Metabase**: Loads everything (fails at scale) | **Do NOT follow** — this is our current approach and it's wrong |

**Our advantage**: Unlike Looker/Tableau/Sigma, we don't need a separate warehouse. DuckDB + direct file reads gives us **faster queries at zero infrastructure cost**.

---

## 7. Cloudflare Workers & KV — Are They Useful?

### 7.1 Cloudflare Services Evaluation

| Service | What it does | Could we use it? | Why/Why not |
|---------|-------------|------------------|-------------|
| **Workers** | Edge JS/WASM functions, 128MB memory, 30s CPU | ❌ **Not for data** | Too constrained for DuckDB or billion-row processing |
| **KV** | Global key-value store, 25MB max value | ❌ **Too small** | Datasets are 100MB-5GB+ |
| **D1** | Serverless SQLite, row-based | ❌ **Slow for analytics** | SQLite is 1000x slower than DuckDB for GROUP BY queries |
| **R2** | S3-compatible object store, zero egress | ✅ **Maybe** | Could replace Supabase S3 for parquet storage |
| **Vectorize** | Vector database for similarity search | ✅ **Maybe** | Alternative to FAISS, but not needed |
| **Workers AI** | Serverless GPU inference | ❌ **Limited** | Fewer models, no fine-tuning — OpenRouter is better |

### 7.2 Where Cloudflare COULD Help

The ONE scenario where Cloudflare makes sense:

> **Edge caching for dashboard queries.** If a dashboard is viewed by 1000 users in Asia, Cloudflare Workers on edge nodes could cache the pre-computed aggregation results near those users, reducing latency.

But this requires:
- Pre-computed results (which we don't have yet)
- Global distribution (which we don't need yet)
- A caching layer (which is simple to add with Redis)

### 7.3 Verdict

| Question | Answer |
|----------|--------|
| Is Cloudflare relevant for our core data problem? | **No.** The fix is simpler: make DuckDB read files directly. |
| Would Cloudflare Workers help with query execution? | **No.** Workers have 128MB memory limit and 30s CPU limit. DuckDB needs 2GB+ for 1B rows. |
| Would KV help with dataset caching? | **No.** KV max value size is 25MB. Our datasets are 100MB-5GB+. |
| Would R2 help for storage? | **Maybe.** Zero egress is nice, but Supabase S3 already works. |
| When should we reconsider Cloudflare? | When we need global edge caching of dashboard results (not raw data). That's a future Phase 2 or 3 concern. |

**Bottom line**: Fixing the data loading pipeline gives us **100x more performance improvement than adding Cloudflare**, at zero infrastructure cost.

---

## 8. Frontend Design Implications

### 8.1 What the Frontend Should Expect

After the fixes, the backend will:

| Operation | Behavior | Frontend UX |
|-----------|----------|-------------|
| **Schema query** | Returns instantly (<10ms) from cache | Show columns immediately |
| **SQL execution (exact)** | Returns in 1-5s for 1B rows (DuckDB direct) | Show loading state, result appears |
| **SQL execution (approximate)** | Returns in <100ms with ±1% accuracy | Show "⚡ Approximate (±1%)" badge |
| **Large result sets** | DuckDB's LIMIT 1000 caps automatically | Always expect ≤1000 rows |
| **Row-count warning** | Pre-checks before execution | Show warning if >10K rows expected |
| **Data profiling** | Runs in background | Show "Processing..." until complete |

### 8.2 What the Frontend Should NOT Assume

| Old assumption | New reality |
|---------------|-------------|
| "Backend can return all data" | Backend limits to 1000 rows by default |
| "Schema is fast because data is small" | Schema is fast because it's CACHED, not because data is small |
| "Full dataset can be loaded for analysis" | Only 10K sample is loaded by default |
| "COUNT(DISTINCT) is always exact" | In approximate mode, it returns ±1% accuracy |

### 8.3 Recommended UX Patterns

```
┌────────────────────────────────────────────────────┐
│  APPROXIMATE MODE TOGGLE                            │
│                                                    │
│  [🎯 Exact] ─── [⚡ Approximate (±1%)]              │
│                                                    │
│  When approximate is ON:                           │
│  • Results appear 200x faster                      │
│  • A badge shows: "⚡ Approximate answer (±1%)"    │
│  • User can click "Run exact" to get precise result │
│                                                    │
├────────────────────────────────────────────────────┤
│  ROW COUNT WARNING                                  │
│                                                    │
│  ⚠️ This query would return 50,000 rows             │
│                                                    │
│  [Add Filter] [Run in Approximate Mode] [Run Anyway]│
│                                                    │
├────────────────────────────────────────────────────┤
│  PROGRESSIVE LOADING                                │
│                                                    │
│  Results (first 100 of 1,523 rows):               │
│  ┌─────────────────────────────────────┐           │
│  │ region    │ revenue                 │           │
│  │ North     │ $52,000                 │ ← visible │
│  │ South     │ $41,000                 │   in <1s  │
│  │ ...       │ ...                     │           │
│  └─────────────────────────────────────┘           │
│  ⏳ Loading 1,423 more rows...                     │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 9. Glossary

| Term | Definition |
|------|------------|
| **DuckDB** | In-process, vectorized, columnar SQL OLAP engine. Reads CSV/Parquet directly. |
| **Polars** | Rust-based DataFrame library for Python. Fast for ETL, not designed for billion-row in-memory queries. |
| **DuckDB direct read** | DuckDB reads CSV/Parquet files from disk using streaming columnar I/O. Never loads full file into memory. |
| **AQP (Approximate Query Processing)** | Replaces `COUNT(DISTINCT x)` with `APPROX_COUNT_DISTINCT(x)` for ~200x faster results at ±1% accuracy. |
| **Row-count pre-check** | Runs `SELECT COUNT(*)` before the main query to warn if result would exceed threshold. |
| **Vectorized execution** | DuckDB processes data in cache-friendly batches of 2048 values using SIMD CPU instructions. |
| **Predicate pushdown** | DuckDB skips irrelevant row groups/columns during file read based on WHERE clause. |
| **OOM (Out Of Memory)** | What happens when you try to load a 100GB dataset into 8GB of RAM. |

---

## 10. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-28 | Initial document created. Covers all architecture, bottlenecks, competitor analysis, and Cloudflare evaluation. | Buffy (AI) |
| | | |

---

## Appendix: Key Files Referenced

| File | Purpose | Status |
|------|---------|--------|
| `services/query/executor.py` | SQL execution — contains Polars→Pandas→DuckDB bottleneck | 🔴 Needs fix #1 |
| `services/query/approximate_engine.py` | AQP rewriter — replaces COUNT DISTINCT with APPROX_COUNT_DISTINCT | ✅ Done |
| `services/datasets/enhanced_dataset_service.py` | Data loading for agents — defaults to full load | 🔴 Needs fix #2 |
| `services/datasets/dataset_loader.py` | File loading logic — has sampling but unused by default | 🟡 Needs fix #3 |
| `services/datasets/data_profiler.py` | Profiling — loads everything, crashes at scale | 🔴 Needs fix #3 |
| `core/config.py` | Settings — has AQP_ENABLED but no direct-file-read flag | 🟡 Needs update |
