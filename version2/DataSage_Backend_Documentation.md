# DataSage AI - Backend Documentation & Roadmap

**Version:** 4.0.0  
**Last Updated:** January 26, 2026  
**Platform:** AI-Powered Data Visualization & Analytics

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current System Overview](#current-system-overview)
3. [Technology Stack](#technology-stack)
4. [System Architecture](#system-architecture)
5. [Backend Modules & Services](#backend-modules--services)
6. [API Endpoints Reference](#api-endpoints-reference)
7. [Database Schema](#database-schema)
8. [AI & Machine Learning Pipeline](#ai--machine-learning-pipeline)
9. [Current Capabilities](#current-capabilities)
10. [Future Goals & Roadmap](#future-goals--roadmap)
11. [Technical Debt & Improvements](#technical-debt--improvements)

---

## Executive Summary

**DataSage AI** is a cutting-edge, production-ready data analytics and visualization platform that leverages advanced AI models to transform raw data into meaningful insights. The platform combines Large Language Models (LLMs) with robust data processing capabilities to provide intelligent, conversational analytics.

### Key Differentiators

- **Multi-Agent AI System**: 6 specialized models orchestrated for optimal results
- **QUIS Framework**: Question-Understanding-Insight-Synthesis approach for intelligent insights
- **Vector-Powered Search**: FAISS-based semantic search for datasets and queries
- **Agentic Analysis**: LangGraph-based autonomous data analysis
- **100% Free AI Models**: All OpenRouter models are completely free to use

---

## Current System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DataSage Platform                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐         ┌──────────────────────┐     │
│  │   Frontend (React)   │◄───────►│  Backend (FastAPI)   │     │
│  │                      │         │                      │     │
│  │  • Components        │   HTTP  │  • REST API          │     │
│  │  • State (Zustand)   │  /JSON  │  • Auth (JWT)        │     │
│  │  • Plotly Charts     │         │  • Services Layer    │     │
│  │  • Routing           │         │  • Background Tasks  │     │
│  └──────────────────────┘         └──────────┬───────────┘     │
│                                              │                  │
│         ┌────────────────────┐    ┌─────────▼────────┐         │
│         │   MongoDB          │    │  Celery Workers  │         │
│         │  • User Data       │    │  • Data Process  │         │
│         │  • Datasets        │    │  • Analytics     │         │
│         │  • Conversations   │    │  • Vector Index  │         │
│         └────────────────────┘    └─────────┬────────┘         │
│                                              │                  │
│         ┌────────────────────┐    ┌─────────▼────────┐         │
│         │  FAISS Vector DB   │    │  Redis           │         │
│         │  • Embeddings      │    │  • Task Queue    │         │
│         │  • Similarity      │    │  • Results       │         │
│         └────────────────────┘    └──────────────────┘         │
│                                                                 │
│         ┌────────────────────────────────────────────┐         │
│         │  AI Models (OpenRouter + Ollama)           │         │
│         │  • Qwen3-235B (Chart Recommendations)      │         │
│         │  • Hermes 3 405B (KPI Suggestions)         │         │
│         │  • Llama 3.3 70B (Natural Conversations)   │         │
│         │  • Mistral 24B (Generalist Reasoning)      │         │
│         │  • Nemotron VL (Chart Image Analysis)      │         │
│         └────────────────────────────────────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Backend Core

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Framework** | FastAPI | 0.117.1 | High-performance async Python web framework |
| **Database** | MongoDB | 5.0+ | NoSQL database for flexible schema |
| **Async Driver** | Motor | 3.7.1 | Async MongoDB operations |
| **Task Queue** | Celery | 5.5.3 | Distributed background task processing |
| **Message Broker** | Redis | 6.4.0 | Task queue and caching |
| **Validation** | Pydantic | 2.11.9 | Data validation using type hints |

### AI & Machine Learning

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **LLM Framework** | LangChain | 0.3.27 | Multi-model orchestration & prompts |
| **LLM Serving** | OpenRouter + Ollama | - | Self-hosted & cloud AI models |
| **Embeddings** | Sentence Transformers | 5.1.1 | Text embeddings (BAAI/bge-large-en-v1.5) |
| **Vector DB** | FAISS | - | Semantic similarity search |
| **ML Algorithms** | Scikit-learn | 1.7.2 | Clustering, PCA, statistics |

### Data Processing

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Primary** | Polars | 1.34.0 | Lightning-fast DataFrame library |
| **Secondary** | Pandas | 2.3.2 | Data manipulation and analysis |
| **Numerical** | NumPy | 2.3.3 | Numerical computing |
| **Scientific** | SciPy | 1.16.2 | Scientific computing and statistics |
| **Visualization** | Plotly | 6.3.0 | Interactive charts |

### Security

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Authentication** | JWT | python-jose 3.5.0 | Token-based auth |
| **Password Hashing** | bcrypt | 5.0.0 | Secure password storage |
| **Rate Limiting** | SlowAPI | - | API rate limiting |

---

## System Architecture

### Backend Services Structure

```
backend/
├── main.py                      # FastAPI application entry point (v4.0)
├── tasks.py                     # Celery background tasks
├── requirements.txt             # Python dependencies
│
├── core/                        # Core configuration & utilities
│   ├── config.py                # Application settings
│   ├── prompts.py               # AI prompt templates
│   ├── output_validator.py      # Response validation
│   ├── prompt_sanitizer.py      # Input sanitization
│   └── rate_limiter.py          # Rate limiting configuration
│
├── db/                          # Database layer
│   ├── database.py              # MongoDB connection & indexes
│   ├── schemas.py               # Base Pydantic models
│   ├── schemas_auth.py          # Authentication schemas
│   ├── schemas_charts.py        # Chart-related schemas
│   ├── schemas_chat.py          # Chat/conversation schemas
│   ├── schemas_dashboard.py     # Dashboard schemas
│   └── schemas_datasets.py      # Dataset schemas
│
├── api/                         # API route handlers
│   ├── auth.py                  # Authentication endpoints
│   ├── datasets.py              # Dataset management
│   ├── chat.py                  # AI chat & conversations
│   ├── dashboard.py             # Dashboard generation
│   ├── charts.py                # Chart rendering
│   ├── analysis.py              # Advanced analysis
│   ├── agentic.py               # Agentic AI (LangGraph)
│   └── models.py                # Model management
│
├── services/                    # Business logic layer
│   ├── auth_service.py          # Authentication logic
│   ├── cache_service.py         # Caching utilities
│   ├── llm_router.py            # Multi-model LLM routing
│   │
│   ├── ai/                      # AI services
│   │   └── ai_service.py        # Main AI orchestration
│   │
│   ├── agents/                  # Agentic services
│   │   └── [LangGraph agents]   # Autonomous analysis agents
│   │
│   ├── analysis/                # Analysis services
│   │   └── enhanced_quis.py     # QUIS framework implementation
│   │
│   ├── charts/                  # Chart services
│   │   └── [chart rendering]    # Chart generation & validation
│   │
│   ├── datasets/                # Dataset services
│   │   └── [dataset processing] # Upload, processing, storage
│   │
│   ├── conversations/           # Conversation services
│   │   └── [chat history]       # Conversation management
│   │
│   └── rag/                     # RAG services
│       └── [vector search]      # FAISS-based retrieval
│
├── faiss_db/                    # Vector database storage
│   ├── dataset_index.faiss      # Dataset embeddings
│   ├── dataset_metadata.pkl     # Dataset metadata
│   ├── query_index.faiss        # Query embeddings
│   └── query_metadata.pkl       # Query metadata
│
└── uploads/
    └── datasets/                # Uploaded dataset files
```

---

## Backend Modules & Services

### 1. Authentication Service (`services/auth_service.py`)

**Purpose:** Handles user authentication, registration, and authorization.

**Key Features:**
- JWT token generation and validation
- Password hashing with bcrypt
- User registration with duplicate detection
- Profile management
- Password change functionality

**Database Collections:**
- `users` - User accounts and profiles

---

### 2. LLM Router (`services/llm_router.py`)

**Purpose:** Intelligent routing of requests to specialized AI models.

**Multi-Model Architecture:**

| Model | Provider | Use Case |
|-------|----------|----------|
| Qwen3-235B | OpenRouter | Chart recommendations with complex reasoning |
| Hermes 3 405B | OpenRouter | KPI suggestions & structured outputs |
| Qwen3-4B | OpenRouter | Quick drafts & lightweight tasks |
| Mistral 24B | OpenRouter | Generalist reasoning & fallbacks |
| Llama 3.3 70B | OpenRouter | Natural conversations |
| Nemotron VL | OpenRouter | Chart image analysis |
| Llama 3.1 | Ollama (Local) | Primary reasoning |
| Qwen 3 (0.6B) | Ollama (Local) | Lightweight tasks |

**Pipeline Flow:**
```
User Query → Intent Classification → Model Selection → 
Response Generation → Validation → Return
```

---

### 3. AI Service (`services/ai/ai_service.py`)

**Purpose:** Main AI orchestration layer for all intelligent features.

**Capabilities:**
- Conversational analytics
- Chart recommendations
- Insight generation
- Query understanding
- Context-aware responses

---

### 4. Analysis Service (`services/analysis/`)

**Purpose:** Statistical and QUIS-based data analysis.

**Enhanced QUIS Framework:**
- **Q**uestion understanding
- **U**nderstanding data context
- **I**nsight extraction
- **S**ynthesis of findings

**Analytics Features:**
- Descriptive statistics (mean, median, mode, std dev, quartiles)
- Correlation analysis (Pearson, Spearman)
- Distribution analysis with skewness and kurtosis
- Clustering analysis (K-Means)
- Principal Component Analysis (PCA)
- Anomaly detection
- Trend analysis

---

### 5. Chart Services (`services/charts/`)

**Purpose:** Chart generation, rendering, and validation.

**Supported Chart Types (20+):**
- Bar, Line, Area, Pie, Scatter
- Heatmap, Sunburst, Treemap
- Waterfall, Sankey, Funnel
- Box Plot, Violin, Histogram
- Gauge, Indicator
- Custom composite charts

**Features:**
- Automatic chart recommendations based on data characteristics
- Data transformation for Plotly
- Configuration validation
- Dynamic drill-down paths

---

### 6. Dataset Services (`services/datasets/`)

**Purpose:** Complete dataset lifecycle management.

**Key Features:**
- Multi-format support (CSV, XLSX, XLS)
- Automatic schema inference
- Data type detection
- Content hashing for duplicate detection
- Background processing with Celery
- Vector embedding generation
- Statistical summary generation

**Processing Pipeline:**
```
Upload → Validation → Hash Check → Save File → 
Create Record → Background Processing → 
(Schema Inference + Stats + Embeddings) → Ready
```

---

### 7. RAG Services (`services/rag/`)

**Purpose:** Retrieval-Augmented Generation using FAISS.

**Components:**
- **Embedding Generation**: Uses BAAI/bge-large-en-v1.5 (1024-dimensional)
- **Index Management**: FAISS index creation and updates
- **Similarity Search**: Semantic search across datasets and queries
- **Context Enhancement**: RAG-enhanced LLM responses

---

### 8. Agentic Services (`services/agents/`)

**Purpose:** LangGraph-based autonomous analysis agents.

**Agent Capabilities:**
- Autonomous data exploration
- Multi-step analysis workflows
- Subjective novelty detection
- Self-correcting analysis loops

---

### 9. Cache Service (`services/cache_service.py`)

**Purpose:** Caching layer for performance optimization.

**Cached Items:**
- Chart configurations
- Analysis results
- Dashboard layouts
- LLM responses

---

## API Endpoints Reference

### 1. Authentication (`/api/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Register new user |
| POST | `/login` | User login |
| GET | `/me` | Get current user profile |
| PUT | `/profile` | Update user profile |
| POST | `/change-password` | Change password |

### 2. Datasets (`/api/datasets`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user datasets |
| POST | `/upload` | Upload new dataset |
| GET | `/{id}` | Get dataset details |
| DELETE | `/{id}` | Delete dataset |
| GET | `/{id}/preview` | Preview dataset data |
| GET | `/{id}/schema` | Get dataset schema |
| GET | `/{id}/status` | Get processing status |

### 3. AI Chat (`/api/chat`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query` | Send chat query |
| GET | `/history` | Get conversation history |
| GET | `/conversations` | List all conversations |
| DELETE | `/conversation/{id}` | Delete conversation |

### 4. Dashboard (`/api/dashboard`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generate` | Generate AI dashboard |
| GET | `/{id}` | Get dashboard |
| PUT | `/{id}` | Update dashboard |
| GET | `/templates` | List dashboard templates |

### 5. Charts (`/api/charts`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/render` | Render chart from config |
| POST | `/recommend` | Get chart recommendations |
| GET | `/types` | List available chart types |
| POST | `/drilldown` | Generate drill-down data |

### 6. Analysis (`/api/analysis`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/statistics` | Get statistical analysis |
| POST | `/correlations` | Calculate correlations |
| POST | `/insights` | Generate QUIS insights |
| POST | `/predict` | Predictive analytics |

### 7. Agentic AI (`/api/agentic`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/analyze` | Trigger agentic analysis |
| GET | `/status/{id}` | Get analysis status |
| GET | `/results/{id}` | Get analysis results |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

---

## Database Schema

### MongoDB Collections

#### 1. `users`
```json
{
  "_id": "ObjectId",
  "username": "string",
  "email": "string",
  "hashed_password": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "is_active": "boolean",
  "preferences": {
    "theme": "string",
    "notifications": "boolean"
  }
}
```

#### 2. `datasets`
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "name": "string",
  "filename": "string",
  "file_path": "string",
  "content_hash": "string",
  "status": "string (pending|processing|ready|failed)",
  "schema": {
    "columns": [
      {
        "name": "string",
        "type": "string",
        "nullable": "boolean"
      }
    ]
  },
  "statistics": {
    "row_count": "integer",
    "column_count": "integer",
    "summary": {}
  },
  "created_at": "datetime",
  "processed_at": "datetime"
}
```

#### 3. `conversations`
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "dataset_id": "ObjectId",
  "title": "string",
  "messages": [
    {
      "role": "string (user|assistant)",
      "content": "string",
      "timestamp": "datetime",
      "charts": [],
      "insights": []
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### 4. `cached_charts`
```json
{
  "_id": "ObjectId",
  "dataset_id": "ObjectId",
  "chart_type": "string",
  "config": {},
  "data": {},
  "created_at": "datetime",
  "expires_at": "datetime"
}
```

---

## AI & Machine Learning Pipeline

### 1. Chart Recommendation Pipeline

```
User Query + Dataset Schema
        ↓
    Intent Classification
        ↓
    Data Analysis (columns, types, distributions)
        ↓
    Chart Type Matching (using chart_definitions.py)
        ↓
    LLM Enhancement (Qwen3-235B)
        ↓
    Recommendation Ranking
        ↓
    Final Recommendations with Explanations
```

### 2. QUIS Insight Generation Pipeline

```
Dataset + Query
        ↓
    Question Understanding (intent, entities)
        ↓
    Data Context Analysis (schema, stats)
        ↓
    Pattern Recognition
        ↓
    Insight Extraction (trends, anomalies, relationships)
        ↓
    Synthesis (narrative generation)
        ↓
    Confidence Scoring
        ↓
    Final Insights
```

### 3. Agentic Analysis Pipeline

```
Dataset + Analysis Goal
        ↓
    LangGraph Agent Initialization
        ↓
    Autonomous Exploration Loop:
        → Formulate hypothesis
        → Execute analysis
        → Evaluate results
        → Refine or continue
        ↓
    Novelty Detection
        ↓
    Insight Compilation
        ↓
    Results
```

---

## Current Capabilities

### ✅ Fully Implemented

1. **User Authentication & Management**
   - JWT-based secure authentication
   - User registration, login, profile management
   - Password hashing with bcrypt

2. **Dataset Management**
   - Multi-format file upload (CSV, XLSX, XLS)
   - Automatic schema inference
   - Background processing with Celery
   - Duplicate detection via content hashing

3. **AI-Powered Chat**
   - Natural language queries
   - Context-aware responses
   - Multi-turn conversations
   - Chart generation from queries

4. **Smart Visualization**
   - 20+ chart types
   - Automatic recommendations
   - Interactive Plotly charts
   - Dynamic drill-down

5. **Analytics Suite**
   - Descriptive statistics
   - Correlation analysis
   - Distribution analysis
   - QUIS-based insights

6. **Vector Search (RAG)**
   - FAISS-powered semantic search
   - Query history analysis
   - Similar dataset discovery

7. **Multi-Model AI**
   - OpenRouter integration (6 models)
   - Ollama local models
   - Intelligent model routing

8. **Dashboard Generation**
   - AI-designed layouts
   - Multiple templates
   - KPI extraction

---

## Future Goals & Roadmap

### 🎯 Short-Term Goals (1-3 Months)

#### 1. Enhanced Agentic Capabilities
- [ ] Complete LangGraph agent implementation
- [ ] Add self-healing analysis workflows
- [ ] Implement subjective novelty scoring
- [ ] Multi-agent collaboration for complex analyses

#### 2. Real-Time Analytics
- [ ] WebSocket support for live data updates
- [ ] Streaming chart updates
- [ ] Real-time collaboration features

#### 3. Advanced Visualizations
- [ ] 3D charts and visualizations
- [ ] Geographic/map visualizations
- [ ] Custom chart builder UI
- [ ] Animated transitions

#### 4. Export & Sharing
- [ ] PDF/PNG export for charts
- [ ] Dashboard sharing links
- [ ] Scheduled report generation
- [ ] Email delivery system

### 🚀 Medium-Term Goals (3-6 Months)

#### 1. SaaS Platform Features
- [ ] Multi-tenant architecture
- [ ] Usage-based billing integration
- [ ] Organization/team management
- [ ] Role-based access control (RBAC)

#### 2. Data Connectors
- [ ] Database connections (PostgreSQL, MySQL, etc.)
- [ ] API data sources (REST, GraphQL)
- [ ] Cloud storage integration (S3, GCS)
- [ ] Real-time streaming (Kafka, WebSocket)

#### 3. Advanced ML Features
- [ ] Time series forecasting
- [ ] Anomaly detection alerts
- [ ] Predictive modeling UI
- [ ] AutoML integration

#### 4. Collaboration Features
- [ ] Shared workspaces
- [ ] Dataset versioning
- [ ] Comments and annotations
- [ ] Activity feeds

### 🌟 Long-Term Vision (6-12 Months)

#### 1. Enterprise Features
- [ ] SSO/SAML integration
- [ ] Audit logging
- [ ] Data governance policies
- [ ] Custom AI model training

#### 2. Advanced Analytics
- [ ] Natural language to SQL
- [ ] Data quality scoring
- [ ] Automated data prep
- [ ] ETL pipeline builder

#### 3. Ecosystem
- [ ] Plugin/extension system
- [ ] Public API marketplace
- [ ] Community templates
- [ ] Integration hub

---

## Technical Debt & Improvements

### 🔧 Code Quality

1. **Testing Coverage**
   - [ ] Unit tests for all services
   - [ ] Integration tests for API endpoints
   - [ ] E2E tests for critical flows
   - [ ] Performance benchmarks

2. **Documentation**
   - [ ] API documentation (OpenAPI complete)
   - [ ] Code docstrings
   - [ ] Architecture decision records (ADRs)
   - [ ] Deployment guides

3. **Error Handling**
   - [ ] Consistent error response format
   - [ ] Detailed error logging
   - [ ] User-friendly error messages
   - [ ] Error monitoring (Sentry integration)

### ⚡ Performance

1. **Optimization**
   - [ ] Query optimization for large datasets
   - [ ] Caching layer improvements
   - [ ] Connection pooling
   - [ ] Lazy loading for embeddings

2. **Scalability**
   - [ ] Horizontal scaling for Celery workers
   - [ ] Read replicas for MongoDB
   - [ ] CDN for static assets
   - [ ] Kubernetes deployment

### 🔒 Security

1. **Enhancements**
   - [ ] Rate limiting per user/IP
   - [ ] Input sanitization improvements
   - [ ] File upload security hardening
   - [ ] Regular security audits

2. **Compliance**
   - [ ] GDPR data handling
   - [ ] Data encryption at rest
   - [ ] Secure key management
   - [ ] Privacy policy enforcement

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DATABASE_NAME` | `datasage_ai` | Database name |
| `SECRET_KEY` | - | JWT secret key (required) |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `50` | Token expiration |
| `LLAMA_BASE_URL` | `http://localhost:11434/` | Ollama URL |
| `OPENROUTER_API_KEY` | - | OpenRouter API key |
| `VECTOR_DB_PATH` | `./faiss_db` | FAISS database path |
| `EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` | Embedding model |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `MAX_FILE_SIZE` | `52428800` | Max upload size (50MB) |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS origins |

---

## Quick Start Commands

```bash
# Backend Setup
cd version2/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start Services
redis-server                                    # Start Redis
celery -A tasks worker --loglevel=info          # Start Celery
uvicorn main:app --reload --port 8000           # Start FastAPI

# API Documentation
# Visit: http://localhost:8000/docs
```

---

## Contact & Support

For questions or contributions, refer to the project repository.

**DataSage AI Backend v4.0** - Built with FastAPI, MongoDB, and ❤️
