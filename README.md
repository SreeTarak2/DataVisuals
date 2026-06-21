# DataSage — Context-Aware AI Analytics Platform

> **Status:** In Production | v4.0.0
> **Stack:** FastAPI + React + MongoDB + ChromaDB/FAISS + OpenRouter

DataSage is an AI-powered analytics platform that turns raw data into actionable insights. It captures business context automatically, surfaces intelligent KPIs, generates dashboards, and provides natural-language chat over your datasets.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React + Vite)                    │
│  Landing · Dashboard · Chat · Charts Studio · Insights · Connectors│
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTP / WebSocket
┌────────────────────────────────┴────────────────────────────────────┐
│                        BACKEND (FastAPI)                            │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     API ROUTES (30+)                         │   │
│  │  Auth · Datasets · Chat · Dashboard · Charts · Insights     │   │
│  │  Analysis · Agentic · Beliefs · Connectors · Feedback       │   │
│  │  Knowledge Graph · Anomalies · Reports · Privacy            │   │
│  └───────────────────────┬─────────────────────────────────────┘   │
│                          │                                          │
│  ┌───────────────────────┴─────────────────────────────────────┐   │
│  │                     SERVICES LAYER                          │   │
│  │                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ AI & Agents  │  │  Analytics   │  │  Knowledge Graph │   │   │
│  │  │ · LLM Router │  │ · Profiling  │  │ · Entity Extract │   │   │
│  │  │ · Multi-     │  │ · QUIS       │  │ · Graph RAG      │   │   │
│  │  │   Agent      │  │   Analysis   │  │ · Relation Detec │   │   │
│  │  │ · KPI Engine │  │ · EDA Pipe   │  │ · Confidence     │   │   │
│  │  │ · Chart Gen  │  │ · Pattern    │  │   Scoring        │   │   │
│  │  │ · Memory     │  │   Detection  │  └──────────────────┘   │   │
│  │  └──────────────┘  └──────────────┘                         │   │
│  │                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │  Pipeline    │  │   Feedback   │  │  Infrastructure  │   │   │
│  │  │ · Process    │  │ · Corrections│  │ · Rate Limiting  │   │   │
│  │  │ · Compute    │  │ · User Memory│  │ · Caching (Redis)│   │   │
│  │  │ · Classify   │  │ · Event Log  │  │ · Cost Tracking  │   │   │
│  │  │ · Narrate    │  │ · Signal     │  │ · Audit Trail    │   │   │
│  │  │ · Profiler   │  │   Classifier │  │ · Security       │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │   │
│  └───────────────────────┬─────────────────────────────────────┘   │
└──────────────────────────┼─────────────────────────────────────────┘
                           │
┌──────────────────────────┴─────────────────────────────────────────┐
│                        DATA LAYER                                  │
│  MongoDB  ·  ChromaDB (Belief Store)  ·  FAISS (Vector Index)      │
│  DuckDB (Query Engine)  ·  Redis (Cache)  ·  File Storage          │
└─────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (Python 3.12) |
| Database | MongoDB (Motor async driver) |
| Vector Store | ChromaDB (belief/knowledge) + FAISS (search) |
| LLM Gateway | OpenRouter (multi-model routing) |
| Query Engine | DuckDB (SQL execution) |
| Caching | Redis (optional, in-memory fallback) |
| Auth | JWT + bcrypt + Google OAuth |
| Rate Limiting | SlowAPI (Redis-backed) |
| Embeddings | Sentence-Transformers (BAAI/bge-large-en-v1.5) |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 19 + Vite |
| Styling | Tailwind CSS 4 + CSS Modules |
| State | Zustand |
| Routing | React Router v7 |
| Charts | Plotly.js + react-plotly.js |
| Animations | Framer Motion |
| HTTP | Axios |
| WebSocket | Native WebSocket API |

### Supported Models (OpenRouter)
- **Gemini 2.5 Flash Lite** — Chat & streaming (primary)
- **DeepSeek V3.2** — Complex analysis & SQL generation
- **DeepSeek V4 Flash** — JSON/structured outputs, dashboard design
- **Mistral Small 3.2** — Validation & lightweight tasks
- **Qwen 2.5 72B** — Narrative/storytelling & plain-English explanations
- **MiniMax M2.5** — System design & planning
- **DeepSeek R1T2 Chimera** — Deep reasoning & insight generation
- **Mistral Nemo 12B** — Conversation naming & fast classification

---

## Key Features

### 🤖 AI Chat with Streaming
Natural-language querying over datasets with real-time token streaming, follow-up suggestions, and chart generation.

### 📊 Intelligent KPIs
Auto-generated KPI cards with anomaly detection, trend analysis, period-over-period comparison, and driver identification.

### 📈 Dashboard Designer
AI-generated dashboard layouts with drag-and-drop customization, KPI overrides, and component priority management.

### 🔍 Dataset Understanding
Entity discovery, primary object identification, relationship detection, and reference signal analysis — all deterministic, no LLM calls.

### 🔗 Knowledge Graph
Graph-RAG for cross-dataset context, entity extraction, and relationship discovery with confidence scoring.

### 🧠 Multi-Agent System
Specialized agents (Analyst, KPI, Chart, Profile, EDA) coordinated by an orchestrator for complex analysis workflows.

### 📝 Feedback Loop
Correction capture, user memory, signal classification, and belief store — the system learns from every interaction.

### 🛡️ Privacy & Security
PII detection/redaction, encrypted database credentials, rate limiting, security headers (CSP, HSTS), audit logging.

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+
- MongoDB (local or Atlas)
- OpenRouter API key

### Backend Setup

```bash
cd version2/backend
pip install -r requirements.txt

# Set up environment
cp .env.example .env  # Edit with your keys
# Required: OPENROUTER_API_KEY, SECRET_KEY, MONGODB_URL

uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd version2/frontend
pnpm install
pnpm dev
```

The app runs at `http://localhost:3000` with API proxied to `http://localhost:8000`.

### Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `OPENROUTER_API_KEY` | — | ✅ | LLM API key |
| `SECRET_KEY` | — | ✅ | JWT signing key |
| `MONGODB_URL` | `mongodb://localhost:27017` | — | MongoDB connection |
| `DATABASE_NAME` | `signal_ai` | — | Database name |
| `GOOGLE_CLIENT_ID` | — | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | — | — | Google OAuth secret |
| `DB_ENCRYPTION_KEY` | — | — | Fernet key for DB credentials |
| `REDIS_URL` | — | — | Redis connection (optional) |
| `LLM_DAILY_BUDGET_CENTS` | `500` | — | Per-user daily LLM budget |
| `LLM_GLOBAL_DAILY_BUDGET_CENTS` | `10000` | — | Global daily LLM budget |

### Docker Deployment

```bash
cd version2/backend
docker build -t signal-backend .
docker run -p 8080:8080 -e OPENROUTER_API_KEY=... -e SECRET_KEY=... signal-backend
```

---

## Project Structure

```
version2/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── core/                   # Config, rate limiting, prompts, exceptions
│   ├── api/                    # Route handlers (auth, datasets, chat, etc.)
│   ├── services/               # Business logic (AI, pipeline, KG, cache, etc.)
│   ├── agents/                 # AI agents (chat, EDA, multi-agent orchestrator)
│   ├── db/                     # MongoDB schemas and connection
│   ├── llm/                    # LLM router and cost tracking
│   ├── prompts/                # Token budgeting and prompt templates
│   ├── pipeline/               # Dataset processing pipeline
│   ├── migrations/             # Database migrations
│   ├── scripts/                # CLI tools and benchmarks
│   └── tests/                  # Test suites
│
└── frontend/
    ├── src/
    │   ├── App.jsx             # Root with routing
    │   ├── pages/              # Route pages (Dashboard, Chat, Insights, etc.)
    │   ├── components/         # Reusable UI components
    │   ├── store/              # Zustand state stores
    │   ├── services/           # API client
    │   ├── hooks/              # Custom React hooks
    │   └── assets/             # Styles and static assets
    ├── index.html
    └── vite.config.js
```

---

## API Overview

The backend exposes **30+ route modules** across the following domains:

| Prefix | Module | Description |
|--------|--------|-------------|
| `/api/auth` | Auth | Registration, login, Google OAuth |
| `/api/datasets` | Datasets | Upload, CRUD, import Google Sheets |
| `/api/chat` | Chat | Conversation management, WebSocket streaming |
| `/api/dashboard` | Dashboard | KPI cards, chart configs, insights, layout |
| `/api/charts` | Charts | Chart rendering, recommendations, overlays |
| `/api/ai` | AI | Dashboard design, KPI generation, analysis |
| `/api/insights` | Insights | Deep analysis, executive summaries |
| `/api/databases` | Databases | Connect external DBs (Postgres, MySQL, MongoDB) |
| `/api/agentic` | Agentic | Multi-agent orchestration |
| `/api/beliefs` | Beliefs | Business rules, user memory |
| `/api/anomalies` | Anomalies | Anomaly investigation |
| `/api/feedback` | Feedback | Corrections, signals, event log |
| `/api/privacy` | Privacy | PII detection, redaction, audit |
| `/api/reports` | Reports | PDF report generation |

Full API docs available at `http://localhost:8000/docs` (Swagger).

---

## License

Proprietary — All rights reserved.
