# 🚀 DataSage AI - Intelligent Data Visualization & Analytics Platform

<div align="center">

![DataSage AI](https://img.shields.io/badge/DataSage-AI%20Powered-blue?style=for-the-badge)
![Version](https://img.shields.io/badge/version-3.0.0-green?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-orange?style=for-the-badge)

**Transform Your Data into Actionable Insights with AI-Powered Analytics**

[Features](#-key-features) • [Tech Stack](#-technology-stack) • [Architecture](#-system-architecture) • [Installation](#-installation) • [Usage](#-usage) • [API Documentation](#-api-documentation)

</div>

---

## � Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Technology Stack](#-technology-stack)
- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [AI Models & Services](#-ai-models--services)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

**DataSage AI** is a cutting-edge, production-ready data analytics and visualization platform that leverages advanced AI models to transform raw data into meaningful insights. Built with modern technologies and best practices, DataSage combines the power of Large Language Models (LLMs) with robust data processing capabilities to provide intelligent, conversational analytics.

### 🆕 NEW: Multi-Agent OpenRouter Integration! ⚡

**DataSage now uses 6 specialized FREE AI models working together!**

- 🎯 **Qwen3-235B** - Chart recommendations with complex reasoning
- 🏗️ **Hermes 3 405B** - KPI suggestions & structured outputs
- ⚡ **Qwen3-4B** - Quick drafts & lightweight tasks
- 🔮 **Mistral 24B** - Generalist reasoning & fallbacks
- 💬 **Llama 3.3 70B** - Natural conversations
- 👁️ **Nemotron VL** - Chart image analysis

**Pipeline:** Chart Recommendation + KPI Suggestion (parallel) → Chart Explanation → Insight Generation = **Better Quality, Faster Results!**

📖 **[Quick Start Guide](QUICK_START_OPENROUTER.md)** | 📚 **[Full Documentation](OPENROUTER_MULTI_AGENT_IMPLEMENTATION.md)**

---

### What Makes DataSage Unique?

- 🤖 **Multi-Agent AI System**: 6 specialized models orchestrated for optimal results (NEW!)
- 📊 **Intelligent Visualization**: Automatic chart recommendations based on data characteristics and user intent
- 💬 **Conversational Analytics**: Natural language interface for data exploration and analysis
- 🎨 **AI-Powered Dashboard Design**: Context-aware, story-driven dashboard layouts with multi-agent pipeline
- 🔍 **Advanced Analytics**: Statistical analysis, correlations, anomaly detection, and predictive insights
- 🚀 **Vector-Based Search**: FAISS-powered semantic search for datasets and queries
- ⚡ **Async Processing**: Celery-based background task processing for heavy computations
- 🔐 **Enterprise-Ready**: JWT authentication, role-based access, and secure file handling
- 💰 **100% Free AI**: All 6 OpenRouter models are completely free to use!

---

## ✨ Key Features

### 🎯 Core Features

#### 1. **Intelligent Data Upload & Processing**
- Support for multiple file formats (CSV, XLSX, XLS)
- Automatic data type detection and schema inference
- Duplicate detection using content hashing
- Background processing with Celery for large datasets
- Real-time processing status tracking

#### 2. **AI-Powered Conversational Analytics**
- Natural language queries for data exploration
- Context-aware responses with pedagogical approach
- Multi-turn conversations with conversation history
- Automatic chart generation from text queries
- Technical and non-technical explanation modes

#### 3. **Smart Visualization Engine**
- **20+ Chart Types**: Bar, Line, Area, Pie, Scatter, Heatmap, Sunburst, Treemap, Waterfall, Sankey, and more
- **Automatic Chart Recommendations**: AI suggests the best visualization based on:
  - Data types (numeric, categorical, temporal)
  - Data distribution and cardinality
  - User query intent
  - Statistical characteristics
- **Interactive Charts**: Built with Plotly.js for rich interactivity
- **Dynamic Drill-Down**: Automatic hierarchy detection and drill-down paths

#### 4. **Advanced Analytics Suite**

##### Statistical Analysis
- Descriptive statistics (mean, median, mode, std dev, quartiles)
- Correlation analysis (Pearson, Spearman)
- Distribution analysis with skewness and kurtosis
- Missing data analysis and quality metrics

##### Intelligent Insights (QUIS Framework)
- **Q**uestion-**U**nderstanding-**I**nsight-**S**ynthesis approach
- Pattern recognition and trend analysis
- Performance analysis across categories
- Relationship discovery between variables
- Anomaly detection and outlier identification

##### Predictive Analytics
- Time series forecasting
- Clustering analysis (K-Means)
- Principal Component Analysis (PCA)
- Confidence scoring for predictions

#### 5. **AI Dashboard Designer**
- Context-aware dashboard layouts
- Multiple design patterns:
  - Executive KPI & Trend Dashboard
  - Analytical Deep-Dive Dashboard
  - Operational Monitoring Dashboard
  - Customer Journey Dashboard
- Story-driven component arrangement
- Automatic KPI extraction and calculation

#### 6. **Vector-Powered Features**

##### FAISS Vector Database
- Semantic search across datasets
- Query history analysis
- Similar dataset discovery
- RAG-enhanced responses

##### Embedding Model
- Uses `BAAI/bge-large-en-v1.5` for high-quality embeddings
- 1024-dimensional vectors
- Normalized embeddings for cosine similarity

#### 7. **Dynamic Drill-Down System**
- Automatic hierarchy detection:
  - Temporal hierarchies (Year → Quarter → Month → Day)
  - Geographic hierarchies (Country → State → City)
  - Categorical hierarchies (Category → Subcategory → Item)
- Universal drill-down for any dataset structure
- Maintains context across drill-down levels

#### 8. **Chart Insights & Explanations**
- AI-generated chart explanations
- Visual evidence panels
- Key metrics extraction
- Actionable recommendations
- Executive summaries

---

## 🛠️ Technology Stack

### Backend Stack

#### Core Framework
- **FastAPI 0.117.1** - Modern, high-performance Python web framework
  - Async/await support for concurrent operations
  - Automatic OpenAPI documentation
  - Type hints and Pydantic validation

#### AI & Machine Learning
- **LangChain 0.3.27** - LLM application framework
  - Multi-model orchestration
  - Prompt management and templating
  - RAG (Retrieval-Augmented Generation) support
- **Ollama Integration** - Self-hosted LLM serving
  - Primary: Llama 3.1 for complex reasoning
  - Secondary: Qwen 3 (0.6B) for lightweight tasks
- **Sentence Transformers 5.1.1** - State-of-the-art text embeddings
- **Scikit-learn 1.7.2** - Machine learning algorithms
  - Clustering (K-Means)
  - Dimensionality reduction (PCA)
  - Statistical analysis

#### Data Processing
- **Polars 1.34.0** - Lightning-fast DataFrame library
  - 10-100x faster than Pandas for large datasets
  - Lazy evaluation for query optimization
  - Memory-efficient columnar storage
- **Pandas 2.3.2** - Data manipulation and analysis
- **NumPy 2.3.3** - Numerical computing
- **SciPy 1.16.2** - Scientific computing and statistics

#### Vector Database
- **FAISS (Facebook AI Similarity Search)** - Efficient similarity search
  - GPU/CPU acceleration support
  - Billion-scale vector indexing
  - Multiple index types (Flat, IVF, HNSW)
- **LangChain-HuggingFace 0.3.1** - HuggingFace integration

#### Database
- **MongoDB** - NoSQL database for flexible schema
  - **Motor 3.7.1** - Async MongoDB driver
  - **PyMongo 4.15.1** - MongoDB Python driver
- Collections:
  - `users` - User accounts and profiles
  - `datasets` - Dataset metadata
  - `conversations` - Chat history
  - `cached_charts` - Chart cache for performance

#### Task Queue
- **Celery 5.5.3** - Distributed task queue
  - Redis backend for message brokering
  - Async task processing
  - Task result tracking
  - Worker process pooling

#### Security & Authentication
- **JWT (JSON Web Tokens)** - Secure authentication
  - **python-jose 3.5.0** - JWT implementation
  - **passlib 1.7.4** - Password hashing with bcrypt
  - **bcrypt 5.0.0** - Secure password hashing
- Token-based authentication with configurable expiration

#### Visualization & Charts
- **Plotly 6.3.0** - Interactive plotting library
  - 40+ chart types
  - Rich interactivity (zoom, pan, hover)
  - Export capabilities (PNG, SVG, JSON)

#### File Processing
- **FastExcel 0.16.0** - Fast Excel file reading
- **OpenPyXL 3.1.2** - Excel file manipulation
- **python-magic 0.4.27** - File type detection

#### HTTP & Networking
- **HTTPx 0.28.1** - Modern async HTTP client
  - Connection pooling
  - HTTP/2 support
  - Timeout management

#### Utilities
- **Pydantic 2.11.9** - Data validation using Python type hints
- **python-dotenv 1.1.1** - Environment variable management
- **aiofiles 24.1.0** - Async file operations

### Frontend Stack

#### Core Framework
- **React 19.1.1** - Modern UI library with latest features
  - Hooks and Functional Components
  - Context API for state management
  - Suspense and Concurrent Features
- **React DOM 19.1.1** - React rendering for web

#### Build Tools
- **Vite 7.1.7** - Next-generation frontend tooling
  - Lightning-fast HMR (Hot Module Replacement)
  - Optimized production builds
  - ES modules native support
- **@vitejs/plugin-react 5.0.4** - React plugin for Vite

#### Routing
- **React Router DOM 7.9.4** - Declarative routing
  - Protected routes
  - Dynamic routing
  - Navigation guards

#### State Management
- **Zustand 5.0.8** - Lightweight state management
  - Minimal boilerplate
  - No providers needed
  - DevTools integration
- Stores:
  - `datasetStore` - Dataset management
  - `chatStore` - Conversation state
  - `chatHistoryStore` - Chat history

#### UI & Styling
- **Tailwind CSS 3.4.17** - Utility-first CSS framework
  - Custom design system
  - Responsive design utilities
  - Dark mode support
- **Framer Motion 12.23.24** - Production-ready animation library
  - Declarative animations
  - Gesture recognition
  - Layout animations
- **Lucide React 0.545.0** - Beautiful icon library
  - 1000+ icons
  - Tree-shakeable
  - Customizable

#### Data Visualization
- **Plotly.js 3.1.1** - Interactive charting library
- **react-plotly.js 2.6.0** - React wrapper for Plotly
- **Recharts 3.2.1** - Composable charting library for React

#### HTTP Client
- **Axios 1.12.2** - Promise-based HTTP client
  - Request/response interceptors
  - Automatic JSON transformation
  - CSRF protection

#### UI Components
- **React Dropzone 14.3.8** - File upload with drag-and-drop
- **React Hot Toast 2.6.0** - Beautiful notifications
- **clsx 2.1.1** - Conditional className utility
- **tailwind-merge 3.3.1** - Merge Tailwind classes

#### Development Tools
- **ESLint 9.36.0** - Code linting
- **PostCSS 8.5.6** - CSS transformations
- **Autoprefixer 10.4.21** - CSS vendor prefixing

### Infrastructure & DevOps

#### Message Broker
- **Redis 6.4.0** - In-memory data structure store
  - Celery message broker
  - Task result backend
  - Caching layer

#### Development Tools
- **Docker** (optional) - Containerization
- **Git** - Version control
- **Ngrok** - Tunnel for Ollama access (development)


---

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DataSage Platform                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐         ┌──────────────────────┐    │
│  │   Frontend (React)   │◄───────►│  Backend (FastAPI)   │    │
│  │                      │         │                      │    │
│  │  • Components        │   HTTP  │  • REST API          │    │
│  │  • State (Zustand)   │  /JSON  │  • Auth (JWT)        │    │
│  │  • Plotly Charts     │         │  • Services Layer    │    │
│  │  • Routing           │         │  • Background Tasks  │    │
│  └──────────────────────┘         └──────────┬───────────┘    │
│                                              │                 │
│                    ┌─────────────────────────┼────────────────┐│
│                    │                         │                ││
│         ┌──────────▼─────────┐    ┌─────────▼────────┐       ││
│         │   MongoDB          │    │  Celery Workers  │       ││
│         │                    │    │                  │       ││
│         │  • User Data       │    │  • Data Process  │       ││
│         │  • Datasets        │    │  • Analytics     │       ││
│         │  • Conversations   │    │  • Vector Index  │       ││
│         │  • Cache           │    │                  │       ││
│         └────────────────────┘    └─────────┬────────┘       ││
│                                              │                ││
│         ┌────────────────────┐    ┌─────────▼────────┐       ││
│         │  FAISS Vector DB   │    │  Redis           │       ││
│         │                    │    │                  │       ││
│         │  • Embeddings      │    │  • Task Queue    │       ││
│         │  • Similarity      │    │  • Results       │       ││
│         │  • RAG Support     │    │  • Cache         │       ││
│         └────────────────────┘    └──────────────────┘       ││
│                                                               ││
│         ┌────────────────────────────────────────────┐       ││
│         │  AI Models (Ollama)                        │       ││
│         │                                            │       ││
│         │  • Llama 3.1 (Primary)                     │       ││
│         │  • Qwen 3 (Lightweight)                    │       ││
│         │  • Specialized Engines:                    │       ││
│         │    - Chat Engine                           │       ││
│         │    - Visualization Engine                  │       ││
│         │    - Layout Designer                       │       ││
│         │    - Insight Generator                     │       ││
│         │    - Chart Recommender                     │       ││
│         └────────────────────────────────────────────┘       ││
│                                                               ││
└───────────────────────────────────────────────────────────────┘│
```

### Service Architecture

```
Backend Services Layer
├── AI Service
│   ├── Multi-Model Router
│   ├── Conversational Engine
│   ├── Visualization Engine
│   ├── Insight Synthesizer
│   └── QUIS Framework
├── Dataset Service
│   ├── Upload Handler
│   ├── Schema Inference
│   ├── Duplicate Detection
│   └── Background Processing
├── Analysis Service
│   ├── Statistical Analysis
│   ├── Correlation Analysis
│   ├── Distribution Analysis
│   └── Clustering & PCA
├── Chart Render Service
│   ├── Chart Type Mapping
│   ├── Data Transformation
│   ├── Plotly Config Generation
│   └── Validation & Sanitization
├── AI Designer Service
│   ├── Design Pattern Library
│   ├── Layout Generator
│   ├── KPI Extractor
│   └── Story Builder
├── Dynamic Drilldown Service
│   ├── Hierarchy Detection
│   ├── Drill Path Generation
│   └── Context Management
├── FAISS Vector Service
│   ├── Embedding Generation
│   ├── Index Management
│   ├── Similarity Search
│   └── RAG Enhancement
├── Auth Service
│   ├── User Registration
│   ├── JWT Token Generation
│   └── Password Hashing
└── File Storage Service
    ├── File Upload
    ├── Content Hashing
    └── Cleanup Management
```

### Data Flow

#### 1. Dataset Upload Flow
```
User → Upload File → FastAPI Endpoint
  ↓
Validation & Content Hash
  ↓
Save to File System
  ↓
Create Dataset Record (MongoDB)
  ↓
Trigger Celery Task
  ↓
Background Processing:
  - Schema Inference
  - Statistical Analysis
  - Vector Embedding
  - Cache Generation
  ↓
Update Dataset Status
  ↓
Notify Frontend (Status Poll)
```

#### 2. Conversational Analytics Flow
```
User Query → Chat Endpoint
  ↓
FAISS Vector Search (RAG)
  ↓
Retrieve Similar Queries & Context
  ↓
AI Service (Multi-Model Router)
  ↓
LLM Processing:
  - Intent Classification
  - Chart Recommendation
  - Data Analysis
  - Response Generation
  ↓
Chart Render Service (if needed)
  ↓
Response to Frontend:
  - Text Response
  - Chart Config
  - Insights
  - Confidence Score
```

#### 3. Dashboard Generation Flow
```
User Request → Design Dashboard Endpoint
  ↓
Load Dataset & Metadata
  ↓
Analysis Service:
  - Column Analysis
  - Statistical Summary
  - Pattern Detection
  ↓
AI Designer Service:
  - Select Design Pattern
  - Generate Layout
  - Create KPI Cards
  - Arrange Components
  ↓
Chart Render Service:
  - Generate Chart Configs
  - Prepare Data
  ↓
Cache Dashboard Config
  ↓
Return to Frontend
```


---

## 📁 Project Structure

```
datasage/
├── version2/
│   ├── backend/
│   │   ├── main.py                          # FastAPI application entry point
│   │   ├── config.py                        # Configuration management
│   │   ├── database.py                      # MongoDB connection & indexes
│   │   ├── tasks.py                         # Celery background tasks
│   │   ├── requirements.txt                 # Python dependencies
│   │   │
│   │   ├── core/
│   │   │   ├── chart_definitions.py         # Chart type definitions & rules
│   │   │   └── prompts.py                   # AI prompt templates & factory
│   │   │
│   │   ├── models/
│   │   │   └── schemas.py                   # Pydantic models & validation
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ai_service.py                # Multi-model AI orchestration
│   │   │   ├── ai_designer_service.py       # Dashboard design AI
│   │   │   ├── analysis_service.py          # Statistical analysis engine
│   │   │   ├── auth_service.py              # Authentication & authorization
│   │   │   ├── chart_insights_service.py    # Chart explanation generator
│   │   │   ├── chart_render_service.py      # Chart data preparation
│   │   │   ├── dynamic_drilldown_service.py # Drill-down logic
│   │   │   ├── enhanced_dataset_service.py  # Dataset lifecycle management
│   │   │   ├── faiss_vector_service.py      # Vector DB operations
│   │   │   └── file_storage_service.py      # File handling
│   │   │
│   │   ├── faiss_db/                        # Vector database storage
│   │   │   ├── dataset_index.faiss          # Dataset embeddings
│   │   │   ├── dataset_metadata.pkl         # Dataset metadata
│   │   │   ├── query_index.faiss            # Query embeddings
│   │   │   └── query_metadata.pkl           # Query metadata
│   │   │
│   │   └── uploads/
│   │       └── datasets/                    # Uploaded dataset files
│   │
│   └── frontend/
│       ├── index.html                       # HTML entry point
│       ├── vite.config.js                   # Vite configuration
│       ├── tailwind.config.js               # Tailwind CSS config
│       ├── package.json                     # Node dependencies
│       │
│       └── src/
│           ├── main.jsx                     # React application entry
│           ├── App.jsx                      # Main app component
│           │
│           ├── pages/
│           │   ├── Landing.jsx              # Landing page
│           │   ├── Login.jsx                # Login page
│           │   ├── Register.jsx             # Registration page
│           │   ├── Dashboard.jsx            # Main dashboard
│           │   ├── Datasets.jsx             # Dataset management
│           │   ├── Chat.jsx                 # Conversational interface
│           │   ├── Charts.jsx               # Chart gallery
│           │   └── Settings.jsx             # User settings
│           │
│           ├── components/
│           │   ├── Button.jsx               # Reusable button component
│           │   ├── PlotlyChart.jsx          # Plotly chart wrapper
│           │   ├── DashboardComponent.jsx   # Dashboard renderer
│           │   ├── DashboardSkeleton.jsx    # Loading skeleton
│           │   ├── ExecutiveSummary.jsx     # Summary component
│           │   ├── InsightsPanel.jsx        # Insights display
│           │   ├── IntelligentChartExplanation.jsx
│           │   ├── VisualEvidencePanel.jsx
│           │   ├── ChatHistoryModal.jsx
│           │   ├── UploadModal.jsx
│           │   ├── ProtectedRoute.jsx       # Route guard
│           │   │
│           │   ├── common/
│           │   │   └── GlassCard.jsx        # Glassmorphism card
│           │   │
│           │   └── layout/
│           │       └── DashboardLayout.jsx  # App layout
│           │
│           ├── contexts/
│           │   ├── AuthContext.jsx          # Authentication context
│           │   └── ThemeContext.jsx         # Theme management
│           │
│           ├── store/
│           │   ├── datasetStore.jsx         # Dataset state (Zustand)
│           │   ├── chatStore.jsx            # Chat state
│           │   └── chatHistoryStore.jsx     # Chat history
│           │
│           ├── services/
│           │   └── api.js                   # API client
│           │
│           └── utils/
│               └── dashboardUtils.js        # Dashboard utilities
│
├── ARCHITECTURE.md                          # Architecture documentation
├── FLOW_DIAGRAMS.md                         # Flow diagrams
└── README.md                                # This file
```

---

## 🚀 Installation

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and **pnpm** (or npm/yarn)
- **MongoDB 5.0+**
- **Redis 6.0+**
- **Ollama** (for AI models)

### Backend Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/datasage.git
cd datasage/version2/backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=datasage_ai

# JWT
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=50

# Ollama URLs (use ngrok tunnels or local URLs)
LLAMA_BASE_URL=http://localhost:11434/
QWEN_BASE_URL=http://localhost:11434/

# Vector Database
VECTOR_DB_PATH=./faiss_db
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
ENABLE_VECTOR_SEARCH=true

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# File Upload
MAX_FILE_SIZE=52428800  # 50MB
ALLOWED_FILE_TYPES=csv,xlsx,xls

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

5. **Install and pull Ollama models**
```bash
# Install Ollama from https://ollama.ai
ollama pull llama3.1
ollama pull qwen3:0.6b
```

6. **Start Redis**
```bash
redis-server
```

7. **Start MongoDB**
```bash
mongod --dbpath /path/to/your/data
```

8. **Start Celery worker**
```bash
celery -A tasks worker --loglevel=info
```

9. **Run the FastAPI server**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**
```bash
cd ../frontend
```

2. **Install dependencies**
```bash
pnpm install
# or: npm install
```

3. **Set up environment variables**
```bash
cp .env.example .env
```

Edit `.env`:
```env
VITE_API_URL=http://localhost:8000/api
```

4. **Start development server**
```bash
pnpm dev
# or: npm run dev
```

The frontend will be available at `http://localhost:3000`

### Docker Setup (Optional)

```bash
# Build and run with Docker Compose
docker-compose up -d
```

---

## ⚙️ Configuration

### Backend Configuration (`config.py`)

```python
class Settings:
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "datasage_ai"
    
    # JWT Authentication
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 50
    
    # AI Models Configuration
    MODELS = {
        "chat_engine": {
            "primary": {"model": "llama3.1", "base_url": LLAMA_BASE_URL}
        },
        "layout_designer": {
            "primary": {"model": "llama3.1", "base_url": LLAMA_BASE_URL}
        },
        "visualization_engine": {
            "primary": {"model": "qwen3:0.6b", "base_url": QWEN_BASE_URL}
        },
        # ... more engines
    }
    
    # Vector Database
    VECTOR_DB_PATH: str = "./faiss_db"
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    ENABLE_VECTOR_SEARCH: bool = True
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]
    
    # File Upload
    MAX_FILE_SIZE: int = 52428800  # 50MB
    ALLOWED_FILE_TYPES: List[str] = ["csv", "xlsx", "xls"]
```

### Frontend Configuration

**Vite Configuration (`vite.config.js`)**
```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
```

---

## 💡 Usage

### 1. Register & Login

1. Navigate to `http://localhost:3000`
2. Click "Get Started" or "Sign Up"
3. Create an account with email and password
4. Log in with your credentials

### 2. Upload a Dataset

1. Click the "Upload Dataset" button in the top right
2. Drag and drop a CSV or Excel file
3. Wait for processing to complete
4. Your dataset will appear in the datasets list

### 3. Explore with Conversational AI

1. Navigate to the "Chat" page
2. Select your dataset
3. Ask questions in natural language:
   - "Show me sales trends over time"
   - "What are the top 10 customers by revenue?"
   - "Create a pie chart of revenue by region"
   - "Analyze the correlation between price and quantity"

### 4. Generate AI-Powered Dashboards

1. Navigate to the "Dashboard" page
2. Select your dataset
3. Click "Generate AI Dashboard"
4. The AI will:
   - Analyze your data
   - Select an appropriate design pattern
   - Create KPI cards
   - Generate visualizations
   - Arrange components in a story-driven layout

### 5. Drill Down into Data

1. Click on any chart in your dashboard
2. Select a data point
3. The system will automatically:
   - Detect hierarchies
   - Generate drill-down paths
   - Show more granular data

### 6. View Insights & Analytics

1. Navigate to the "Dashboard" page
2. Select your dataset
3. View automatically generated:
   - Statistical summaries
   - Correlations
   - Anomalies
   - Trends
   - Recommendations


---

## 📚 API Documentation

### Authentication Endpoints

#### Register User
```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "john@example.com",
  "password": "secure_password"
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "...",
    "username": "john_doe",
    "email": "john@example.com"
  }
}
```

### Dataset Endpoints

#### Upload Dataset
```http
POST /api/datasets/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: <binary data>
```

#### Get User Datasets
```http
GET /api/datasets
Authorization: Bearer {token}
```

#### Get Dataset Details
```http
GET /api/datasets/{dataset_id}
Authorization: Bearer {token}
```

#### Get Dataset Preview
```http
GET /api/datasets/{dataset_id}/preview?limit=100
Authorization: Bearer {token}
```

### AI & Analytics Endpoints

#### Chat with Dataset
```http
POST /api/datasets/{dataset_id}/chat
Authorization: Bearer {token}
Content-Type: application/json

{
  "message": "Show me sales trends",
  "conversation_id": "optional-conversation-id"
}
```

#### Generate Dashboard
```http
POST /api/ai/{dataset_id}/design-dashboard
Authorization: Bearer {token}
Content-Type: application/json

{
  "design_requirements": {
    "focus": "sales_analysis",
    "kpis": ["revenue", "profit", "growth"]
  }
}
```

#### Generate QUIS Insights
```http
POST /api/ai/generate-quis-insights
Authorization: Bearer {token}
Content-Type: application/json

{
  "dataset_id": "...",
  "focus_areas": ["trends", "correlations", "anomalies"]
}
```

#### Render Chart
```http
POST /api/charts/render-preview
Authorization: Bearer {token}
Content-Type: application/json

{
  "dataset_id": "...",
  "chart_config": {
    "chart_type": "bar",
    "x": "category",
    "y": "sales",
    "aggregation": "sum"
  }
}
```

### Vector Search Endpoints

#### Search Similar Datasets
```http
POST /api/vector/search/datasets
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "sales data with customer information",
  "top_k": 5
}
```

#### RAG-Enhanced Query
```http
POST /api/vector/rag/{dataset_id}/enhanced
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "analyze customer behavior",
  "use_history": true
}
```

### Drilldown Endpoints

#### Analyze Drilldown Possibilities
```http
POST /api/drilldown/{dataset_id}/analyze
Authorization: Bearer {token}
```

#### Execute Drilldown
```http
POST /api/drilldown/{dataset_id}/execute
Authorization: Bearer {token}
Content-Type: application/json

{
  "hierarchy_type": "temporal",
  "current_level": "month",
  "filter_value": "2024-01"
}
```

### Background Task Endpoints

#### Get Task Status
```http
GET /api/tasks/{task_id}/status
Authorization: Bearer {token}
```

---

## 🤖 AI Models & Services

### Multi-Model Architecture

DataSage uses a **specialized multi-model approach** where different AI models handle different tasks:

#### 1. Chat Engine (Llama 3.1)
- **Purpose**: Conversational analytics, query understanding
- **Capabilities**:
  - Natural language understanding
  - Intent classification
  - Context-aware responses
  - Multi-turn conversations

#### 2. Visualization Engine (Qwen 3 0.6B)
- **Purpose**: Fast chart generation and recommendations
- **Capabilities**:
  - Quick chart type suggestions
  - Data transformation logic
  - Configuration generation

#### 3. Layout Designer (Llama 3.1)
- **Purpose**: Dashboard design and component arrangement
- **Capabilities**:
  - Design pattern selection
  - Layout optimization
  - Story-driven arrangement
  - KPI prioritization

#### 4. Insight Engine (Llama 3.1)
- **Purpose**: Statistical analysis and insight generation
- **Capabilities**:
  - Pattern recognition
  - Anomaly detection
  - Correlation analysis
  - Predictive insights

#### 5. Chart Recommender (Llama 3.1)
- **Purpose**: Intelligent chart type selection
- **Capabilities**:
  - Data type analysis
  - Cardinality checking
  - Best practice recommendations
  - Use case matching

### QUIS Framework

**Q**uestion-**U**nderstanding-**I**nsight-**S**ynthesis

```python
QUIS Process:
1. Question Generation
   - Identify key questions based on data characteristics
   - Pattern analysis: "What are the trends?"
   - Performance analysis: "Which categories perform best?"
   - Correlation analysis: "What relationships exist?"

2. Understanding Phase
   - Statistical analysis
   - Data quality assessment
   - Context gathering
   - Hypothesis formation

3. Insight Extraction
   - Run analytics
   - Detect patterns
   - Identify outliers
   - Calculate metrics

4. Synthesis
   - Combine findings
   - Generate narrative
   - Provide recommendations
   - Create actionable items
```

### Prompt Engineering

DataSage uses **advanced prompt templates** with:

- **Few-shot learning**: Examples in prompts for better results
- **Context injection**: Dynamic data context
- **Schema awareness**: Data type and structure information
- **Pedagogical approach**: Teaching-style explanations
- **JSON output**: Structured, parseable responses

---

## 🎨 Features in Detail

### Automatic Chart Recommendations

The system analyzes:
1. **Data Types**: Numeric, categorical, temporal
2. **Cardinality**: Number of unique values
3. **Distribution**: Skewness, outliers
4. **User Intent**: Keywords in query
5. **Best Practices**: Chart definition rules

### Dynamic Drill-Down

Automatic hierarchy detection:
```python
Temporal: Year → Quarter → Month → Week → Day
Geographic: Country → State → City → Postal Code
Categorical: Category → Subcategory → Product → SKU
```

### Dashboard Design Patterns

**Executive KPI & Trend**
```
┌─────┬─────┬─────┬─────┐
│ KPI │ KPI │ KPI │ KPI │
├─────┴─────┴─────┼─────┤
│                 │     │
│   Main Trend    │ Pie │
│                 │     │
├─────────────────┴─────┤
│      Data Table       │
└───────────────────────┘
```

---

## 🔒 Security Features

- **JWT Authentication**: Secure token-based auth
- **Password Hashing**: Bcrypt with salt
- **CORS Protection**: Configurable origins
- **SQL Injection Prevention**: Parameterized queries
- **File Upload Validation**:
  - Type checking
  - Size limits
  - Content verification
- **Rate Limiting**: (Recommended for production)
- **Input Sanitization**: Pydantic validation

---

## 🚢 Deployment

### Production Checklist

- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set `DEBUG=False`
- [ ] Configure production database
- [ ] Set up Redis cluster
- [ ] Configure Celery workers with supervisor
- [ ] Set up reverse proxy (Nginx)
- [ ] Enable HTTPS with SSL certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Configure log aggregation
- [ ] Set up automated backups
- [ ] Enable rate limiting
- [ ] Configure CDN for frontend assets

### Docker Deployment

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Run containers
docker-compose -f docker-compose.prod.yml up -d

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=4
```

---

## 📈 Performance Optimization

### Backend
- **Polars** instead of Pandas (10-100x faster)
- **Async operations** for I/O
- **Connection pooling** for MongoDB
- **Celery** for background tasks
- **Redis caching** for frequent queries
- **FAISS** for fast vector search

### Frontend
- **Code splitting** with React.lazy
- **Vite** for fast builds
- **Lazy loading** for charts
- **Memoization** with React.memo
- **Virtual scrolling** for large lists

---

## 🐛 Troubleshooting

### Common Issues

**1. Ollama models not responding**
```bash
# Check Ollama status
ollama list
ollama ps

# Restart Ollama
ollama serve
```

**2. Celery workers not processing**
```bash
# Check Redis connection
redis-cli ping

# Restart workers
celery -A tasks worker --loglevel=info
```

**3. MongoDB connection failed**
```bash
# Check MongoDB status
mongosh

# Restart MongoDB
sudo systemctl restart mongod
```

**4. Frontend not connecting to backend**
- Check CORS configuration in `config.py`
- Verify `VITE_API_URL` in frontend `.env`
- Check browser console for errors

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use ESLint rules for JavaScript
- Write unit tests for new features
- Update documentation
- Keep commits atomic and meaningful

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **FastAPI** - Modern Python web framework
- **React** - UI library
- **Plotly** - Visualization library
- **LangChain** - LLM framework
- **Ollama** - Local LLM serving
- **FAISS** - Similarity search
- **MongoDB** - Database
- **Polars** - Fast DataFrames

---

## 📞 Contact & Support

- **GitHub Repository**: [SreeTarak2/DataSageAIV2](https://github.com/SreeTarak2/DataSageAIV2)
- **GitHub Issues**: [Create an issue](https://github.com/SreeTarak2/DataSageAIV2/issues)

---

<div align="center">

**Made with ❤️ by the DataSage Team**

⭐ Star us on GitHub if you find this project useful!

[Report Bug](https://github.com/SreeTarak2/DataSageAIV2/issues) • [Request Feature](https://github.com/SreeTarak2/DataSageAIV2/issues)

</div>
- **Role-based Access Control**: Granular permissions and user roles
- **API Rate Limiting**: Advanced API protection and monitoring
- **Audit Logging**: Comprehensive activity tracking and compliance

### Phase 4: Advanced Analytics
- **Real-time Streaming**: Support for real-time data streams
- **Advanced Statistical Analysis**: More sophisticated statistical methods
- **Custom Visualizations**: User-defined chart types and templates
- **Collaboration Features**: Team sharing and collaboration tools

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Plotly.js** for excellent data visualization capabilities
- **FastAPI** for the modern, fast web framework
- **React** for the powerful UI library
- **MongoDB** for flexible data storage
- **Tailwind CSS** for rapid UI development

## 📞 Support

For support, email support@datasage.ai or join our Slack community.

---

**DataSage** - Empowering data-driven decisions with AI-powered insights 🚀
