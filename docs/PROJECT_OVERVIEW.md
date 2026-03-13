# DataSage AI - Project Overview & Technical Assessment

**Document Generated:** February 8, 2026  
**Version:** 4.0.0

---

## 1. Project Overview & Purpose

### Main Goal
Transform uploaded datasets into AI-powered interactive dashboards with natural language analytics, automated chart recommendations, and intelligent insights — all using 100% free AI models.

### Primary User
- **Data Analysts** who want quick insights without manual chart creation
- **Business Users** who need self-service analytics without technical expertise
- **Data Scientists** who want AI-assisted EDA and visualization

### Core Value Proposition
> "Upload any CSV/Excel file and get an AI-generated interactive dashboard with smart KPIs, auto-recommended charts, and conversational analytics — powered by 6 free AI models working together."

### Product Type
**Web Application** — Full-stack platform with:
- React 19 SPA frontend
- FastAPI async backend
- Celery background processing
- MongoDB + Redis + FAISS infrastructure

---

## 2. Current Features / Modules

### ✅ Polished & Stable Features

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | **Dataset Upload & Processing** | ✅ Stable | CSV, XLSX, XLS with Celery background processing, duplicate detection |
| 2 | **Auto Schema Inference** | ✅ Stable | Automatic data type detection, domain classification |
| 3 | **Data Profiling** | ✅ Stable | Cardinality, patterns, quality metrics, missing data analysis |
| 4 | **JWT Authentication** | ✅ Stable | Secure login/register, token refresh |
| 5 | **20+ Chart Types** | ✅ Stable | Bar, Line, Pie, Scatter, Heatmap, Treemap, Sankey, Sunburst, Waterfall, etc. |
| 6 | **Interactive Plotly Charts** | ✅ Stable | Zoom, pan, hover, drill-down |
| 7 | **Multi-Model LLM Router** | ✅ Stable | 6 OpenRouter free models with intelligent routing |
| 8 | **Conversational Chat** | ✅ Stable | Natural language queries with context-aware responses |
| 9 | **FAISS Vector Search** | ✅ Stable | Semantic search for datasets and query history |
| 10 | **Rate Limiting** | ✅ Stable | SlowAPI-based per-user/endpoint limits |

### ⚠️ Working but Fragile/Incomplete

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | **AI Chart Recommendations** | ⚠️ Works | Sometimes suggests suboptimal charts for edge cases |
| 2 | **Dashboard Layout Generator** | ⚠️ Works | AI-generated layouts can be inconsistent |
| 3 | **Intelligent KPI Generator** | ⚠️ Works | Context-aware but occasionally picks wrong columns |
| 4 | **QUIS Insight Framework** | ⚠️ Works | Question-Understanding-Insight-Synthesis is functional but verbose |
| 5 | **Agentic Analysis (LangGraph)** | ⚠️ Partial | Cyclic graph implemented but not fully production-tested |
| 6 | **RAG Chunking** | ⚠️ Works | Chunking works but reranking could be improved |
| 7 | **Chart Insights/Explanations** | ⚠️ Works | LLM-generated but sometimes too generic |

### 🎯 Killer Feature
**Multi-Agent AI Pipeline with Free Models** — The orchestration of 6 specialized free OpenRouter models (Qwen3-235B, Hermes 405B, Llama 3.3 70B, Mistral 24B, etc.) working together for different tasks is genuinely unique. This provides GPT-4-class quality at zero cost.

---

## 3. Data Flow & Core Interactions

### Typical User Journey (Happy Path)

```
1. USER UPLOADS FILE
   └─→ POST /api/datasets/upload
       └─→ File validation → Save to disk → Return dataset_id
       └─→ Celery task triggered (background)

2. BACKGROUND PROCESSING (Celery)
   └─→ Load & clean data (Polars)
   └─→ Domain detection (LLM + rules)
   └─→ Data profiling (cardinality, quality)
   └─→ Statistical analysis (correlations, distributions)
   └─→ Chart recommendations (AI-powered)
   └─→ FAISS vector indexing
   └─→ Update MongoDB with metadata

3. USER VIEWS DASHBOARD
   └─→ GET /api/dashboard/{dataset_id}/overview
       └─→ Intelligent KPI generation
       └─→ Return formatted metrics

4. USER GETS CHART RECOMMENDATIONS
   └─→ GET /api/charts/smart-recommendations/{dataset_id}
       └─→ AI selects best charts based on data profile
       └─→ Hydrate with actual data
       └─→ Return Plotly-ready chart configs

5. USER ASKS NATURAL LANGUAGE QUESTION
   └─→ POST /api/chat/{dataset_id}
       └─→ Query complexity analysis
       └─→ RAG retrieval (relevant chunks)
       └─→ LLM call with context
       └─→ Optional chart generation
       └─→ Return response + chart (if applicable)

6. USER DRILLS DOWN INTO DATA
   └─→ POST /api/datasets/{id}/drill-down
       └─→ Hierarchy detection
       └─→ Filtered aggregation
       └─→ Return child-level data
```

### Supported Data Formats

| Format | Support Level | Max Tested |
|--------|---------------|------------|
| **CSV** | ✅ Full | 500MB, 5M rows |
| **XLSX** | ✅ Full | 100MB |
| **XLS** | ✅ Full | 50MB |
| **Parquet** | ✅ Internal | N/A (converted from CSV) |
| **JSON** | ❌ Not yet | — |
| **Database** | ❌ Roadmap | — |
| **API** | ❌ Roadmap | — |

### Current Limits
- **Max file size:** 50MB (configurable)
- **Reasonable row count:** ~500K-1M rows work well
- **Large datasets (>1M rows):** Work but slower processing

---

## 4. Architecture & Tech Choices

### Backend Stack

| Component | Technology | Version |
|-----------|------------|---------|
| **Framework** | FastAPI | 0.117.1 |
| **Database** | MongoDB | 5.0+ |
| **Async Driver** | Motor | 3.7.1 |
| **Task Queue** | Celery | 5.5.3 |
| **Message Broker** | Redis | 6.4.0 |
| **Data Processing** | Polars (primary), Pandas | 1.34.0 |
| **Vector DB** | FAISS | — |
| **Embeddings** | Sentence Transformers | 5.1.1 |
| **Validation** | Pydantic | 2.11.9 |

### Frontend Stack

| Component | Technology | Version |
|-----------|------------|---------|
| **Framework** | React | 19.1.1 |
| **Build Tool** | Vite | 7.1.7 |
| **State Management** | Zustand | 5.0.8 |
| **Styling** | Tailwind CSS | 3.4.17 |
| **Charts** | Plotly.js + react-plotly.js | 3.1.1 |
| **HTTP Client** | Axios | 1.12.2 |
| **Routing** | React Router DOM | 7.9.4 |
| **Animations** | Framer Motion | 12.23.24 |

### State & Persistence

| Data Type | Storage |
|-----------|---------|
| User accounts | MongoDB `users` collection |
| Dataset metadata | MongoDB `datasets` collection |
| Uploaded files | Local disk (`uploads/datasets/`) |
| Chat history | MongoDB `conversations` collection |
| Vector embeddings | FAISS on disk (`faiss_db/`) |
| Task queue | Redis |
| Task results | Redis |

### Background Tasks
**Celery** with Redis broker — used for:
- Dataset processing pipeline
- Heavy analytics computations
- Vector index updates
- Chart generation (batched)

### LLM Providers

#### Primary: OpenRouter (Free Tier)
| Model | Role | Use Case |
|-------|------|----------|
| `qwen/qwen3-235b` | Chart Recommendations | Complex reasoning for viz |
| `nousresearch/hermes-3-llama-3.1-405b:free` | KPI/Insights | Structured output, JSON |
| `mistralai/mistral-small-3.1-24b-instruct:free` | Chat Engine | Conversational, reasoning |
| `mistralai/devstral-2512:free` | Layout Design | Long context, planning |
| `qwen/qwen3-4b:free` | Quick Tasks | Fast drafts, rewrites |
| `qwen/qwen3-vl-8b-instruct` | Vision | Chart image analysis |

#### Secondary: Ollama (Local)
- Llama 3.1 for offline/fallback
- Qwen 3 for lightweight local tasks

### Agent Framework
**LangGraph** — Used for agentic QUIS orchestrator with cyclic state graph:
```
START → planner → analyst → critic → [conditional]
                                ↓
                    REJECT → analyst (retry)
                    APPROVE → novelty → synthesizer → END
                    BORING → planner (new question)
```

### Code Execution / Sandbox
**No Python sandbox currently** — The system generates chart configs and queries but doesn't execute arbitrary user code.

---

## 5. AI-Related Parts

### AI-Powered Features

| Feature | AI Type | Model Used |
|---------|---------|------------|
| Chart Recommendations | LLM + Rules | Mistral 24B |
| Dashboard Layout | LLM | Devstral 2 |
| KPI Suggestions | LLM | Hermes 405B |
| Natural Language Chat | LLM | Mistral 24B |
| Insight Generation | LLM | Hermes 405B |
| Query Rewriting | LLM | Qwen 4B |
| Domain Detection | LLM + Rules | Hybrid |
| Chart Explanations | LLM | Mistral 24B |
| Semantic Search | Embeddings | BAAI/bge-large-en-v1.5 |

### Most Useful AI Feature
**Conversational Analytics** — Users can ask questions like "What's the correlation between price and mileage?" and get instant, contextual answers with auto-generated charts.

### Most Unreliable AI Part
**AI Dashboard Layout Generator** — The LLM sometimes produces inconsistent JSON layouts, requires post-processing/validation, and can fail on edge cases.

### Conversation Memory
**Yes** — Full chat history per dataset/user stored in MongoDB `conversations` collection with:
- Message threading
- Context carryover
- Conversation summarization (for long chats)

### RAG Implementation
**Yes** — RAG over:
1. **Dataset metadata chunks** (schema, column stats, sample rows)
2. **Query history** (similar past questions)
3. **Relationship chunks** (correlations, patterns)

Uses FAISS for vector storage with `BAAI/bge-large-en-v1.5` embeddings (1024 dimensions).

---

## 6. Pain Points & Next Priorities

### Top 3 Annoyances

| # | Pain Point | Category | Severity |
|---|------------|----------|----------|
| 1 | **LLM JSON parsing failures** | AI Quality | High |
| | Sometimes models return malformed JSON for chart configs, requiring retry/fallback | | |
| 2 | **Slow initial dataset processing** | Performance | Medium |
| | Large datasets (>500K rows) can take 30-60+ seconds to fully process | | |
| 3 | **Inconsistent chart recommendations** | AI Quality | Medium |
| | Edge cases (sparse data, unusual distributions) get suboptimal chart types | | |

### Next 3 Priority Features/Improvements

| # | Feature | Priority | Effort |
|---|---------|----------|--------|
| 1 | **Robust output validation/repair** | High | Medium |
| | Add JSON repair layer + structured output enforcement for LLM calls | | |
| 2 | **Streaming responses** | High | Medium |
| | WebSocket streaming for chat to improve perceived latency | | |
| 3 | **Database connectors** | Medium | High |
| | Support PostgreSQL, MySQL, BigQuery direct connections | | |

### Considering Removal/Replacement
- **Legacy QUIS linear pipeline** — Being replaced by LangGraph agentic version
- **Old dashboard templates** — Moving to fully AI-generated layouts

### Known Performance Bottlenecks
1. **FAISS index updates** — Synchronous, blocks on large datasets
2. **Sentence Transformer embedding** — Cold start is slow (~5s first call)
3. **OpenRouter API latency** — 2-5 seconds per call (network dependent)
4. **Large file parsing** — Memory-intensive for 500MB+ files

---

## 7. Scale & Environment

### Project Stage
```
[ ] Personal / side project
[x] Startup / early product ← Current stage
[ ] Internal company tool
[ ] Already has real users
```

### Team Size
**Solo developer** (with AI assistance)

### Current Deployment

| Aspect | Current State |
|--------|---------------|
| **Environment** | Local development primarily |
| **Backend** | Uvicorn + Celery (manual start) |
| **Frontend** | Vite dev server |
| **Database** | Local MongoDB + Redis |
| **Docker** | Dockerfile exists, not in active use |
| **CI/CD** | Not configured |
| **Production** | Not yet deployed |

### Recommended Next Steps for Deployment
1. Docker Compose for full stack (FastAPI + Celery + Redis + MongoDB)
2. Environment variable management (`.env` files properly configured)
3. Nginx reverse proxy for production
4. Cloud VM (DigitalOcean, AWS EC2, or Railway)

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Backend Lines of Code | ~15,000+ |
| Frontend Lines of Code | ~8,000+ |
| API Endpoints | 25+ |
| AI Models Used | 6 (OpenRouter) + 2 (Ollama) |
| Chart Types Supported | 20+ |
| Background Task Types | 8 |
| Database Collections | 5 |

---

## File Structure Summary

```
datasage/
├── version2/
│   ├── backend/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── tasks.py             # Celery background tasks
│   │   ├── api/                 # Route handlers (8 modules)
│   │   ├── core/                # Config, prompts, validators
│   │   ├── db/                  # Database schemas (6 modules)
│   │   ├── services/            # Business logic
│   │   │   ├── ai/              # AI orchestration
│   │   │   ├── agents/          # LangGraph agents
│   │   │   ├── analysis/        # QUIS, statistics
│   │   │   ├── charts/          # Chart generation
│   │   │   ├── datasets/        # Data processing
│   │   │   ├── rag/             # Vector search
│   │   │   └── conversations/   # Chat history
│   │   └── faiss_db/            # Vector indices
│   └── frontend/
│       └── src/
│           ├── pages/           # Route components
│           ├── components/      # UI components
│           ├── store/           # Zustand state
│           ├── services/        # API client
│           └── hooks/           # Custom hooks
└── README.md                    # Main documentation
```

---

*Generated by DataSage AI Analysis*
