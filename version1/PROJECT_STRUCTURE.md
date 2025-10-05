# 📁 DataSage AI - Project Structure

## 🏗️ Overall Architecture

```
datasage/
├── backend/                 # FastAPI Backend
│   ├── services/           # Business Logic Services
│   ├── config.py           # Configuration & Environment
│   ├── database.py         # MongoDB Connection
│   ├── main.py            # FastAPI App & Endpoints
│   ├── models.py           # Pydantic Models
│   └── requirements.txt    # Python Dependencies
├── frontend/               # React Frontend
│   ├── src/
│   │   ├── components/     # Reusable UI Components
│   │   ├── contexts/       # React Contexts
│   │   ├── pages/          # Page Components
│   │   ├── App.tsx         # Main App Component
│   │   └── main.tsx        # Entry Point
│   ├── package.json        # Node Dependencies
│   ├── tailwind.config.js  # Tailwind Configuration
│   └── vite.config.ts      # Vite Configuration
├── start.sh                # Startup Script
├── README.md               # Project Overview
└── PROJECT_STRUCTURE.md    # This File
```

## 🔧 Backend Structure

### Core Files
- **`main.py`** - FastAPI application with all endpoints
- **`config.py`** - Environment configuration and settings
- **`database.py`** - MongoDB connection management
- **`models.py`** - Pydantic data models and schemas

### Services (`backend/services/`)
- **`data_profiler.py`** - Dataset analysis and profiling
- **`visualization_recommender.py`** - Chart type recommendations
- **`llm_service.py`** - Ollama LLM integration

### API Endpoints
- **`/datasets/*`** - Dataset management (upload, list, delete)
- **`/visualization/*`** - Chart recommendations and field info
- **`/llm/*`** - AI-powered insights and explanations
- **`/dashboard/templates/*`** - Pre-built dashboard layouts
- **`/health`** - System health monitoring

## 🎨 Frontend Structure

### Core Components (`frontend/src/components/`)
- **`Layout.tsx`** - Main application layout with navigation
- **`PersonaSwitcher.tsx`** - Toggle between Normal/Expert modes

### Pages (`frontend/src/pages/`)
- **`Dashboard.tsx`** - Main dashboard with overview and quick actions
- **`Datasets.tsx`** - Dataset upload and management
- **`Analysis.tsx`** - AI-powered analysis and insights
- **`Templates.tsx`** - Dashboard template selection
- **`NotFound.tsx`** - 404 error page

### Contexts (`frontend/src/contexts/`)
- **`PersonaContext.tsx`** - Global persona state management

## 🚀 Key Features

### 1. Dual Persona System
- **Normal Persona**: Business-friendly explanations, simple insights
- **Expert Persona**: Technical analysis, statistical depth, confidence intervals

### 2. AI-Powered Analysis
- **Data Profiling**: Automatic dataset analysis and quality assessment
- **Visualization Recommendations**: Smart chart suggestions based on data types
- **Natural Language Queries**: Ask questions about your data in plain English

### 3. Smart Dashboards
- **Pre-built Templates**: KPI, Exploration, and Forecasting dashboards
- **Persona Adaptations**: Different insights and features per persona
- **Interactive Components**: Dynamic charts and real-time updates

### 4. Data Management
- **File Upload**: Support for CSV and Excel files
- **Auto-profiling**: Instant data analysis and statistics
- **Quality Assessment**: Data completeness and validation

## 🔌 Integration Points

### Backend Dependencies
- **FastAPI**: Modern Python web framework
- **MongoDB (Motor)**: Async database operations
- **Pandas/NumPy**: Data processing and analysis
- **LangChain + Ollama**: LLM integration for AI insights
- **Uvicorn**: ASGI server

### Frontend Dependencies
- **React 18**: Modern React with hooks
- **TailwindCSS**: Utility-first CSS framework
- **Recharts/Plotly**: Data visualization libraries
- **React Router**: Client-side routing
- **Lucide React**: Icon library

## 🛠️ Development Workflow

### 1. Setup Environment
```bash
# Install MongoDB and Ollama
# Copy env.example to .env and configure
cp backend/env.example backend/.env
```

### 2. Start Development
```bash
# Use the startup script
./start.sh

# Or start manually:
# Backend: cd backend && uvicorn main:app --reload
# Frontend: cd frontend && npm run dev
```

### 3. Access Points
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 📊 Data Flow

1. **Upload**: User uploads CSV/Excel file
2. **Profiling**: Backend analyzes data structure and quality
3. **Storage**: Dataset metadata stored in MongoDB
4. **Analysis**: LLM generates insights based on persona
5. **Visualization**: AI recommends appropriate chart types
6. **Dashboard**: User creates interactive dashboards

## 🔒 Security & Performance

- **File Validation**: Type and size restrictions
- **Async Processing**: Non-blocking operations
- **Error Handling**: Graceful fallbacks and user feedback
- **CORS Configuration**: Secure cross-origin requests
- **Health Monitoring**: System status endpoints

## 🚧 Future Enhancements

- **Real-time Updates**: WebSocket connections for live data
- **Advanced Analytics**: Machine learning models and predictions
- **User Authentication**: Multi-user support and permissions
- **Data Export**: Multiple format support
- **Mobile App**: React Native companion app
- **API Rate Limiting**: Request throttling and quotas
- **Background Jobs**: Celery integration for heavy processing
- **Caching**: Redis integration for performance
- **Monitoring**: Prometheus metrics and Grafana dashboards

## 📝 Development Notes

- **TypeScript**: Full type safety in frontend
- **Responsive Design**: Mobile-first approach with Tailwind
- **Component Reusability**: Modular architecture for maintainability
- **Error Boundaries**: Graceful error handling throughout
- **Loading States**: User feedback during async operations
- **Accessibility**: ARIA labels and keyboard navigation
