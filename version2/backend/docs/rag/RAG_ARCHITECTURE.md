# DataSage AI — RAG Architecture

> Last updated: July 29, 2026
>
> Covers the Retrieval-Augmented Generation system: per-dataset vector indices,
> hybrid search, cross-encoder reranking, query enrichment, and MongoDB-backed recovery.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [MongoDB Schema & Indexes](#2-mongodb-schema--indexes)
3. [FAISS Index Management](#3-faiss-index-management)
4. [Hybrid Search (BM25 + FAISS)](#4-hybrid-search-bm25--faiss)
5. [Cross-Encoder Reranker](#5-cross-encoder-reranker)
6. [Query Enrichment for RAG](#6-query-enrichment-for-rag)
7. [Data Flow](#7-data-flow)
8. [Configuration](#8-configuration)
9. [File Map](#9-file-map)
10. [Key Design Decisions](#10-key-design-decisions)

---

## 1. Architecture Overview

### The Problem

Before the redesign, all datasets shared a **single flat FAISS index** (`chunk_index.faiss`):

```
All Datasets ──► Single FAISS Index ──► search() ──► post-filter by dataset_id
                                                        │
                                                     ⚠️ Cross-tenant touching
                                                     ⚠️ Results from wrong datasets
                                                     ⚠️ O(N) deletion via lazy rebuild
```

This is a **SaaS anti-pattern** — User A's chunks were physically interleaved with User B's
chunks in the same FAISS index. The post-filter provided logical isolation but violated
tenant separation at the storage level.

### The Solution: Per-Dataset Indices

Each dataset gets its own FAISS index file. MongoDB is the source of truth.

```
                    ┌─────────────────────────────────────┐
                    │         MongoDB "chunks"              │
                    │         (source of truth)             │
                    │   - Chunk content + metadata          │
                    │   - TTL index on expire_at            │
                    │   - Unique constraint on chunk_id     │
                    └─────────────┬───────────────────────┘
                                  │
                                  ▼ (recovery path)
            ┌─────────────────────────────────────────┐
            │         FAISS on Disk (cache)            │
            │                                          │
            │  faiss_db/chunks/                        │
            │    ├── {dataset_id}.faiss   (vectors)    │
            │    └── {dataset_id}.pkl     (metadata)   │
            └─────────────┬───────────────────────────┘
                          │
                          ▼ (LRU cache, max 100)
            ┌─────────────────────────────────────────┐
            │      In-Memory LRU Cache                │
            │  - _chunk_indices: LRUDict              │
            │  - _chunk_metadata: LRUDict             │
            └─────────────────────────────────────────┘
```

### Key Properties

| Property | Implementation |
|----------|---------------|
| **Tenant isolation** | Each dataset has its own `.faiss` file — no cross-tenant touching |
| **Source of truth** | MongoDB `chunks` collection — FAISS is a cache |
| **O(1) deletion** | Delete MongoDB records + delete FAISS file — no index rebuild |
| **Disaster recovery** | If FAISS file is corrupt/missing, rebuild from MongoDB |
| **Bounded memory** | LRU cache with configurable max size (default 100 datasets) |
| **Atomic writes** | All FAISS files written via temp-file-then-rename |

---

## 2. MongoDB Schema & Indexes

### Chunk Document Structure

```json
{
  "_id": ObjectId,
  "chunk_id": "a1b2c3d4e5f6a7b8",
  "dataset_id": "abc-123-def",
  "user_id": "user-456",
  "chunk_type": "schema | column | sample | relationship | statistics",
  "content": "Dataset: Sales 2024\nRows: 10,000\nColumns: 12\n...",
  "metadata": {
    "total_rows": 10000,
    "total_columns": 12
  },
  "created_at": ISODate("2026-07-29T12:00:00Z"),
  "expire_at": null
}
```

### Indexes (created on startup in `db/database.py`)

| Field | Type | Purpose |
|-------|------|---------|
| `expire_at` | TTL (`expireAfterSeconds: 0`) | Auto-cleanup of orphaned chunks |
| `dataset_id` | Regular (ascending) | Fast lookup by dataset |
| `chunk_id` | **Unique** (ascending) | Prevent duplicate chunks |

**Why `expire_at` TTL instead of `created_at` TTL?**

- `created_at` TTL would delete **active** chunks after a fixed duration — wrong.
- `expire_at: null` means **never expire** (MongoDB TTL indexes ignore null values).
- `expire_at: <datetime>` means **delete when that time is reached**.
- The safety-net in `delete_dataset_chunks()` sets `expire_at: now()` on any chunks
  that survive the primary `delete_many()` — MongoDB cleans them up within ~60 seconds.

---

## 3. FAISS Index Management

### File Layout

```
faiss_db/
├── dataset_index.faiss       (dataset-level metadata, shared)
├── dataset_metadata.pkl
├── query_index.faiss         (query history, shared)
├── query_metadata.pkl
└── chunks/
    ├── abc-123-def.faiss     (per-dataset chunk vectors)
    ├── abc-123-def.pkl       (per-dataset chunk metadata)
    ├── xyz-789-ghi.faiss
    └── xyz-789-ghi.pkl
```

### LRU Cache (`LRUDict`)

```python
class LRUDict(OrderedDict):
    """OrderedDict with max size — drops LRU item on overflow."""
    maxsize = settings.CHUNK_INDEX_CACHE_MAX  # default: 100

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)     # Mark as most recently used
        return value

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            self.popitem(last=False)  # Evict oldest
```

Two parallel `LRUDict` instances are maintained:
- `_chunk_indices: map<dataset_id → faiss.Index>`
- `_chunk_metadata: map<dataset_id → map<idx → chunk_metadata>>`

Initialized in `__init__()` for robustness (not in `_initialize_faiss_indices()`).

### Atomic Writes

All FAISS files and pickle metadata are written via `_atomic_write()`:

```python
@staticmethod
def _atomic_write(data, path, is_faiss=False):
    tmp_path = path + ".tmp"
    try:
        if is_faiss:
            faiss.write_index(data, tmp_path)
        else:
            with open(tmp_path, "wb") as f:
                pickle.dump(data, f)
        os.replace(tmp_path, path)  # Atomic on POSIX same-filesystem
    except Exception:
        try: os.remove(tmp_path)
        except Exception: pass
        raise
```

This prevents file corruption from crashes during write.

### Load Path (Lazy, with MongoDB fallback)

```
search_relevant_chunks(query, dataset_id)
         │
         ▼
  _chunk_indices.get(dataset_id)  ← LRU cache hit?
         │                           (also updates LRU order)
         ▼ no
  _load_chunk_index(dataset_id)
         │
         ├── disk hit ──► faiss.read_index() + pickle.load()
         │
         └── disk miss ──► _rebuild_chunk_index_from_mongodb(dataset_id)
                              │
                              ├── find({dataset_id}) from MongoDB
                              ├── embed_documents(texts)
                              ├── build FAISS index
                              ├── _atomic_write() to disk
                              └── update LRU cache
```

---

## 4. Hybrid Search (BM25 + FAISS)

### Flow

```
User Query
    │
    ▼
FAISS Dense Search ──► chunks with similarity scores
    │
    ▼
BM25 Sparse Search ──► chunks with bm25_scores
    │
    ▼
RRF Fusion (Reciprocal Rank Fusion, k=60)
    │  score = Σ 1/(k + rank) across both rankings
    ▼
Cross-Encoder Rerank (optional, if loaded)
    │
    ▼
Diversity Rerank (interleave chunk types)
    │
    ▼
Top-K Results
```

### Implementation (`services/rag/hybrid_search.py`)

- **BM25 index**: Built in `enhanced_dataset_service.auto_index_dataset_to_vector_db()`
  during dataset processing, alongside the FAISS index.
- **Fusion methods**: RRF (default) and Linear Combination.
- **Granularity**: Per-dataset (`bm25_indices[dataset_id]`).
- **Fallback**: If BM25 returns no results for a dataset, falls back to dense-only.

### Wire-up point (`services/chat/context_loader.py:get_rag_context()`)

```python
chunks = await faiss_vector_service.search_relevant_chunks(...)
if chunks:
    try:
        from services.rag.hybrid_search import hybrid_search_service
        if hybrid_search_service.bm25_available:
            chunks = hybrid_search_service.hybrid_search(
                query=query, dense_results=chunks,
                dataset_id=dataset_id, k=10, fusion_method="rrf"
            )
    except ImportError:
        pass  # rank_bm25 not installed
```

---

## 5. Cross-Encoder Reranker

### Lazy Initialization

The BGE-reranker-v2-m3 model (`BAAI/bge-reranker-v2-m3`) is loaded lazily on
the **first RAG call**:

```python
# In get_rag_context():
if not reranker_service.use_cross_encoder:
    asyncio.create_task(
        _lazy_init_cross_encoder(reranker_service)
    )
```

The model takes ~5-10 seconds to load (free, CPU, ~2GB RAM). The first query
uses score-threshold + diversity reranking only. Subsequent queries benefit
from cross-encoder scoring.

### Fallback Chain

1. **Cross-encoder scores**: Query-chunk pairs re-scored by the cross-encoder
2. **Score threshold**: Filter below `score_threshold` (default: 0.5)
3. **Diversity rerank**: Interleave chunk types to prevent over-representation

### Graceful Degradation

If the cross-encoder model fails to load (e.g., no internet for first download,
OOM on low-memory machines), the `enable_cross_encoder()` method sets
`use_cross_encoder = False` and the system falls back to the diversity-only path.

---

## 6. Query Enrichment for RAG

### The Insight

Raw user queries are often poor RAG queries:
```
User: "Show me revenue"            ← too short for semantic search
User: "What about last month?"     ← pronoun-dependent, no context
```

The query understanding step (`understand_query()`) produces an `enriched_query`
that adds domain context, expands abbreviations, and clarifies intent.

### Integration (`services/chat/pipeline.py`)

Step 4 runs query understanding → Step 4b re-runs RAG with the enriched query:

```python
# After query understanding (Step 4):
if query_ctx.was_enriched:
    await self._upgrade_rag_with_enriched_query(
        query_ctx, context_pkg, dataset_id, user_id
    )
```

This replaces `context_pkg.dataset_context_str` and `context_pkg.rag_context`
with results from the enriched query. The agent then receives better context.

### Cost

The enriched RAG call is ~20-50ms (one extra embedding + FAISS search).
Negligible compared to the agent's seconds-long LLM calls.

---

## 7. Data Flow

### Upload → Index

```
User uploads CSV
    │
    ▼
enhanced_dataset_service.upload_dataset()
    │
    ▼ (background task)
pipeline.process_dataset(dataset_id, ...)
    │
    ▼
chunk_service.create_chunks_from_metadata()
    │  Creates 5 chunk types:
    │    - schema (1)
    │    - column (1 per column)
    │    - statistics (1)
    │    - sample (1)
    │    - relationship (1 if correlations exist)
    ▼
faiss_vector_service.index_dataset_chunks(dataset_id, chunks, user_id)
    │
    ├── Step 1: MongoDB — delete existing chunks, insert_many(new)
    │              Document: {chunk_id, dataset_id, user_id, chunk_type,
    │                         content, metadata, created_at, expire_at: null}
    │
    ├── Step 2: FAISS — build per-dataset index from embeddings
    │
    ├── Step 3: Disk — _atomic_write() to chunks/{dataset_id}.faiss + .pkl
    │
    └── Step 4: Cache — self._chunk_indices[dataset_id] = index
                        self._chunk_metadata[dataset_id] = metadata
```

### Query → Retrieve

```
User asks a question
    │
    ▼
ChatPipeline.process() or .process_streaming()
    │
    ├── Step 1: Off-topic guard
    ├── Step 2: Load context ──► get_rag_context()
    │              │
    │              ├── search_relevant_chunks(raw_query, dataset_id)
    │              │     ├── Load per-dataset index (LRU → disk → MongoDB)
    │              │     ├── FAISS search
    │              │     ├── BM25 hybrid fusion (if available)
    │              │     └── Cross-encoder + diversity rerank
    │              │
    │              └── apply_privacy_controls()
    │
    ├── Step 3: Scope guard
    ├── Step 4: Query understanding ──► enriched_query
    ├── Step 4b: _upgrade_rag_with_enriched_query()
    │              └── Re-run get_rag_context(enriched_query, ...)
    │
    ├── Step 5: Routing
    ├── Step 6: ReAct agent
    ├── Step 7: Synthesis
    └── Step 8: Persist
```

### Delete

```
User deletes dataset
    │
    ▼
enhanced_dataset_service.delete_dataset(dataset_id, user_id)
    │
    └── faiss_vector_service.delete_dataset_chunks(dataset_id, user_id)
           │
           ├── MongoDB: delete_many({dataset_id})
           ├── Safety-net: update_many(expire_at: now()) ← catches orphans
           ├── Disk: os.remove(chunks/{dataset_id}.faiss)
           │        os.remove(chunks/{dataset_id}.pkl)
           └── Cache: _chunk_indices.pop(dataset_id)
                      _chunk_metadata.pop(dataset_id)
```

---

## 8. Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `ENABLE_VECTOR_SEARCH` | `true` | Master toggle for all vector search |
| `VECTOR_DB_PATH` | `./faiss_db` | Directory for FAISS index files |
| `EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` | Sentence-transformer model for embeddings |
| `CHUNK_INDEX_CACHE_MAX` | `100` | Max per-dataset FAISS indices in LRU cache |

### Key Constants (hardcoded, not configurable — deliberate)

| Constant | Value | Location |
|----------|-------|----------|
| Embedding dimension | 1024 | `FAISSVectorService.__init__` |
| FAISS index type | `IndexFlatIP` | (inner product = cosine similarity) |
| FAISS search multiplier | `k * 3` | `search_relevant_chunks()` — search extra, then filter |
| RAG score threshold | `0.3` | `get_rag_context()` — minimum similarity |
| Reranker score threshold | `0.4` | `reranker_service.rerank()` |
| Reranker top_k | `5` | `get_rag_context()` — final chunks to return |
| Context max tokens | `2000` | `assemble_context_from_chunks()` |
| Cross-encoder model | `BAAI/bge-reranker-v2-m3` | `_lazy_init_cross_encoder()` |
| BM25 RRF k | `60` | `hybrid_search_service.rrf_k` |

---

## 9. File Map

### Core Vector Service

| File | Purpose |
|------|---------|
| `services/datasets/faiss_vector_service.py` | Core FAISS operations — `LRUDict`, `_atomic_write`, `index_dataset_chunks`, `search_relevant_chunks`, `delete_dataset_chunks`, `_load_chunk_index`, `_rebuild_chunk_index_from_mongodb` |

### Context Assembly

| File | Purpose |
|------|---------|
| `services/chat/context_loader.py` | `get_rag_context()` — orchestrates FAISS search → BM25 hybrid → reranker → context assembly |
| `services/chat/pipeline.py` | `_upgrade_rag_with_enriched_query()` — re-runs RAG with enriched query |

### RAG Services

| File | Purpose |
|------|---------|
| `services/rag/chunk_service.py` | `ChunkService` — creates 5 chunk types from dataset metadata |
| `services/rag/hybrid_search.py` | `HybridSearchService` — BM25 index + RRF fusion |
| `services/rag/reranker_service.py` | `RerankerService` — cross-encoder + diversity reranking |

### Dataset Processing

| File | Purpose |
|------|---------|
| `services/datasets/enhanced_dataset_service.py` | `auto_index_dataset_to_vector_db()` — orchestrates chunk creation + FAISS indexing + BM25 indexing |
| `services/pipeline/process.py` | Dataset processing pipeline (triggers auto-index) |

### Database

| File | Purpose |
|------|---------|
| `db/database.py` | `create_indexes()` — creates MongoDB indexes for `chunks` collection |
| `db/schemas.py` | Dataset schemas (chunk documents use ad-hoc structure, no Pydantic schema) |

---

## 10. Key Design Decisions

### Why MongoDB as source of truth instead of FAISS?

FAISS is a vector index, not a database. It doesn't support:
- Atomic transactions
- Per-document querying (by chunk_id, by chunk_type)
- Schema enforcement
- Replication/backup

MongoDB provides all of these. The FAISS index is a **cache** that can be rebuilt
from MongoDB at any time via `_rebuild_chunk_index_from_mongodb()`.

### Why per-dataset indices instead of per-user?

- A user can have multiple datasets with unrelated schemas.
- Searching "revenue" against a "Customer Surveys" dataset is wasted effort.
- Per-dataset indices ensure: `O(chunks_per_dataset)` search time, not `O(total_chunks)`.
- If cross-dataset search is needed, multiple per-dataset indices can be searched
  and fused (same RRF pattern as BM25 fusion).

### Why LRU eviction instead of always loading from disk?

- FAISS `read_index()` is fast (~5ms for a small index) but not free.
- The embedding model call to `embed_query()` dominates search time (~20-50ms).
- Caching the loaded index saves the `read_index()` cost on subsequent searches.
- LRU with max 100 datasets means ~20MB memory for 100 indices (50 chunks × 1024-dim each).

### Why both `delete_many()` and `update_many(expire_at)` in delete?

- `delete_many({dataset_id})` is the primary fast path.
- The `update_many(expire_at: now())` safety-net catches chunks that survive
  the `delete_many()` due to transient MongoDB errors.
- The TTL index cleans them up within ~60 seconds.
- This is a belt-and-suspenders approach for production robustness.

### Why not use `expire_at` TTL on `created_at` instead?

A TTL on `created_at` would delete **all** chunks older than N days,
including chunks for actively used datasets. Our chunks persist for the lifetime
of the dataset. The `expire_at: null` pattern (null = never expire, date = delete)
only targets orphaned chunks.

### Why lazy cross-encoder init?

The BGE-reranker-v2-m3 model is ~2GB and takes ~5-10 seconds to load on CPU.
Loading it eagerly on startup would add 10 seconds to server startup.
Lazy loading means:
- First RAG query pays the load cost (with diversity fallback)
- Subsequent queries don't wait
- If the model fails to load (OOM, no network), the system falls back gracefully

---

*End of RAG Architecture Document*
