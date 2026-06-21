# Signal Backend v4.0

FastAPI-based AI analytics backend with MongoDB, vector search, multi-agent AI, and knowledge graph capabilities.

## Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (Python 3.12+) |
| Database | MongoDB (Motor async driver) |
| Vector Store | ChromaDB (belief store) + FAISS (semantic search) |
| LLM Gateway | OpenRouter (multi-model with fallbacks) |
| Embeddings | Sentence-Transformers (BAAI/bge-large-en-v1.5) |
| Query Engine | DuckDB |
| Caching | Redis (optional, in-memory fallback) |
| Auth | JWT + bcrypt + Google OAuth |
| Rate Limiting | SlowAPI (Redis-backed) |
| Data Processing | Polars, Pandas, NumPy, Scikit-learn |

## Setup

```bash
# Navigate to backend
cd version2/backend

# Install dependencies
pip install -r requirements.txt

# Required environment variables
export OPENROUTER_API_KEY="sk-or-..."
export SECRET_KEY="your-secret-key-here"
export MONGODB_URL="mongodb://localhost:27017"

# Run in development
uvicorn main:app --reload --port 8000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | LLM API key (required) |
| `SECRET_KEY` | — | JWT signing key (required) |
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection |
| `DATABASE_NAME` | `signal_ai` | MongoDB database name |
| `GOOGLE_CLIENT_ID` | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth secret |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8000/api/auth/google/callback` | OAuth callback |
| `FRONTEND_URL` | `http://localhost:5173` | CORS origin |
| `DB_ENCRYPTION_KEY` | — | Fernet key for DB credentials |
| `REDIS_URL` | — | Redis connection (optional) |
| `VECTOR_DB_PATH` | `./faiss_db` | Vector index path |
| `EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` | Embedding model name |
| `LLM_DAILY_BUDGET_CENTS` | `500` | Per-user daily budget |
| `LLM_GLOBAL_DAILY_BUDGET_CENTS` | `10000` | Global daily budget |
| `MAX_FILE_SIZE` | `524288000` | Max upload size (500MB) |
| `ALLOWED_FILE_TYPES` | `csv,xlsx,xls` | Allowed upload formats |

## Project Structure

```
backend/
├── main.py                 # FastAPI app entry point (routes, middleware)
├── core/                   # Config, rate limiting, prompts, output validation
│   ├── config.py           # Settings, env vars, OpenRouter model config
│   ├── prompt_templates.py # LLM prompt templates
│   ├── output_validator.py # Response validation with retry
│   └── rate_limiter.py     # Rate limit configuration
│
├── api/                    # API route handlers
│   ├── auth/               # Registration, login, Google OAuth
│   ├── datasets/           # Upload, CRUD, Google Sheets import
│   ├── chat/               # Conversations, WebSocket streaming
│   ├── dashboard/          # KPIs, charts, layout, insights
│   ├── charts/             # Chart rendering, recommendations
│   ├── ai/                 # AI dashboard design, KPI generation
│   ├── analysis/           # Deep analysis, advanced stats
│   ├── insights/           # Insight generation
│   ├── databases/          # External DB connections
│   ├── agentic/            # Multi-agent orchestration
│   ├── beliefs/            # Business rules, user memory
│   ├── anomalies/          # Anomaly investigation
│   ├── feedback/           # Corrections, signals
│   ├── bookmarks/          # Saved bookmarks
│   ├── notifications/      # Proactive notifications
│   ├── privacy/            # PII detection, redaction
│   ├── reports/            # PDF report generation
│   └── reflection/         # Insight quality reflection
│
├── services/               # Business logic
│   ├── ai/                 # AI services, KPI generator, agents
│   ├── pipeline/           # Dataset processing (load, clean, profile, compute)
│   ├── knowledge_graph/    # Entity extraction, Graph-RAG, relationships
│   ├── cache/              # Dashboard, insights, semantic caching
│   ├── charts/             # Chart intelligence, rendering, patterns
│   ├── datasets/           # Dataset management, FAISS, profiling
│   ├── query/              # SQL execution and repair
│   ├── feedback/           # User memory, corrections, event log
│   ├── intelligence/       # Entity detection, hierarchies, relationships
│   ├── agents/             # AI agents (chat, EDA, multi-agent)
│   ├── profiling/          # Data profiling engine
│   ├── rag/                # Hybrid search, reranking
│   ├── narrative/          # Story weaving
│   ├── thinker/            # Deep thinking agent
│   ├── memory/             # Memory and belief services
│   ├── databases/          # DB connection management
│   └── report/             # PDF generation
│
├── agents/                 # Agent system
│   ├── chat/               # Chat agent
│   ├── eda/                # Exploratory data analysis
│   ├── multi/              # Multi-agent orchestrator + tools
│   ├── quis/               # QUIS analysis pipeline
│   └── belief/             # Belief store
│
├── db/                     # Database layer
│   ├── database.py         # MongoDB connection
│   └── schemas*.py         # Pydantic/MongoEngine schemas
│
├── llm/                    # LLM routing
│   ├── router.py           # OpenRouter multi-model router
│   └── cost_tracker.py     # Budget-aware cost tracking
│
├── prompts/                # Token budgeting and prompt management
├── tests/                  # Test suites
├── Dockerfile              # Cloud Run optimized (multi-stage)
├── pyproject.toml          # Python project config
└── requirements.txt        # Dependencies
```

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| | **Authentication** | |
| `POST` | `/api/auth/register` | Register user |
| `POST` | `/api/auth/login` | Login |
| `GET` | `/api/auth/google/login` | Google OAuth login |
| `GET` | `/api/auth/google/callback` | Google OAuth callback |
| | **Datasets** | |
| `POST` | `/api/datasets/upload` | Upload CSV/XLSX file |
| `POST` | `/api/datasets/import-gsheet` | Import Google Sheet |
| `GET` | `/api/datasets` | List user datasets |
| `GET` | `/api/datasets/{id}` | Get dataset details |
| `DELETE` | `/api/datasets/{id}` | Delete dataset |
| `POST` | `/api/datasets/{id}/reprocess` | Reprocess dataset |
| | **Chat** | |
| `WS` | `/api/chat/ws` | WebSocket streaming chat |
| `GET` | `/api/chat/conversations` | List conversations |
| `GET` | `/api/chat/conversations/{id}` | Get conversation |
| `DELETE` | `/api/chat/conversations/{id}` | Delete conversation |
| | **Dashboard** | |
| `GET` | `/api/dashboard/{id}/overview` | Dashboard overview + KPIs |
| `GET` | `/api/dashboard/{id}/charts` | Chart configurations |
| `GET` | `/api/dashboard/{id}/insights` | Dashboard insights |
| `GET` | `/api/dashboard/{id}/config` | Full dashboard blueprint |
| | **Charts** | |
| `POST` | `/api/charts/recommend` | Chart recommendations |
| `POST` | `/api/charts/render` | Render chart data |
| `POST` | `/api/charts/explain` | Chart explanation |
| | **Knowledge Graph** | |
| `POST` | `/api/graph-rag/query` | Graph-RAG query |
| `POST` | `/api/entity-extraction/extract` | Extract entities |
| | **Agentic** | |
| `POST` | `/api/agentic/query` | Multi-agent query |

Full interactive docs at `http://localhost:8000/docs` (Swagger UI).

## Deployment

### Docker (Cloud Run)
```bash
docker build -t signal-backend .
docker run -p 8080:8080 -e OPENROUTER_API_KEY=... signal-backend
```

The `Dockerfile` uses multi-stage builds optimized for Cloud Run:
- Builder stage installs all dependencies
- Runtime stage uses `python:3.12-slim` with a non-root user
- Health check at `/health` on configurable `$PORT`

## Testing

```bash
cd version2/backend
python -m pytest tests/ -v
```
