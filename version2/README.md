# DataSage AI v2.0 🚀

A modern, AI-powered data visualization and analysis platform built with React, TypeScript, and FastAPI.

## ✨ Features

### 🎨 **Modern Dark Theme UI**
- Beautiful dark theme interface inspired by Shadcn UI
- Responsive design for all screen sizes
- Smooth animations and transitions
- Professional data visualization aesthetics

### 🤖 **AI-Powered Analytics**
- Intelligent chart recommendations
- Natural language query processing
- Automated data insights generation
- Smart data quality assessment

### 📊 **Advanced Chart System**
- 10+ chart types (Bar, Line, Pie, Scatter, Histogram, etc.)
- Interactive drill-down functionality
- Real-time chart generation
- Google AI Studio-style loading animations

### 🔍 **Universal Drill-Down**
- Works with ANY dataset (not hardcoded)
- Automatic hierarchy detection
- Temporal, geographic, and categorical drill-downs
- Breadcrumb navigation

### 🚀 **Performance Optimized**
- Frontend chart generation (no server load)
- Metadata-only LLM processing
- Smart caching and data chunking
- Fast API with async processing

## 🏗️ Architecture

### Backend (FastAPI + Python)
```
backend/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── models/
│   └── schemas.py         # Pydantic models
└── services/
    ├── enhanced_llm_service.py      # AI orchestration
    ├── metadata_service.py          # LLM-safe metadata
    ├── rag_service.py              # Retrieval-augmented generation
    ├── dynamic_drilldown_service.py # Universal drill-down
    └── chart_validation_service.py  # Chart validation
```

### Frontend (React + TypeScript)
```
frontend/
├── src/
│   ├── components/        # Reusable UI components
│   ├── pages/            # Application pages
│   ├── hooks/            # Custom React hooks
│   ├── contexts/         # React contexts
│   └── main.tsx          # Application entry point
├── package.json          # Node.js dependencies
└── tailwind.config.js    # Tailwind CSS configuration
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Installation

1. **Clone and navigate to version2:**
```bash
cd /home/vamsi/nothing/datasage/version2
```

2. **Start the application:**
```bash
./start.sh
```

This will:
- Install Python dependencies
- Install Node.js dependencies
- Start the backend server (port 8000)
- Start the frontend server (port 3000)

### Manual Setup

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 📱 Usage

1. **Upload Dataset**: Click "Upload Dataset" to add your CSV files
2. **Generate Dashboard**: Automatically creates AI-recommended charts
3. **Explore Data**: Use natural language queries to analyze your data
4. **Drill Down**: Click on charts to explore data hierarchies
5. **Create Charts**: Generate custom visualizations

## 🎯 Key Improvements from v1

### ✅ **What's New**
- **Dark Theme**: Modern, professional dark UI
- **KPI Dashboard**: Key performance indicators at a glance
- **Enhanced UX**: Google AI Studio-style loading animations
- **Better Architecture**: Cleaner separation of concerns
- **TypeScript**: Full type safety in frontend
- **Responsive Design**: Works on all devices

### 🔧 **Technical Enhancements**
- Simplified service architecture
- Better error handling
- Improved loading states
- Enhanced chart skeleton animations
- Modern React patterns (hooks, contexts)

## 🛠️ API Endpoints

### Core Dataset Management
- `GET /api/datasets` - List all datasets
- `POST /api/datasets/upload` - Upload new dataset
- `GET /api/datasets/{id}` - Get dataset details
- `DELETE /api/datasets/{id}` - Delete dataset

### Chart Generation
- `POST /api/datasets/{id}/generate-dashboard` - Generate dashboard charts
- `POST /api/datasets/{id}/create-chart` - Create specific chart
- `GET /api/datasets/{id}/chart-recommendations` - Get AI recommendations

### AI Features
- `POST /api/datasets/{id}/chat` - Process natural language queries
- `GET /api/datasets/{id}/hierarchies` - Get drill-down hierarchies
- `POST /api/datasets/{id}/drill-down` - Execute drill-down operations

## 🎨 UI Components

### Core Components
- **KPICard**: Key performance indicator cards
- **ChartGrid**: Responsive chart display grid
- **ChartSkeleton**: Loading animations for charts
- **UploadModal**: Drag-and-drop file upload
- **Sidebar**: Navigation sidebar
- **Header**: Top navigation bar

### Pages
- **Dashboard**: Main overview with KPIs and charts
- **Datasets**: Dataset management and listing
- **Analysis**: AI-powered data analysis
- **Charts**: Chart creation and management
- **Insights**: AI-generated insights
- **Settings**: User preferences

## 🔮 Future Enhancements

- [ ] Real-time collaboration
- [ ] Advanced AI models integration
- [ ] Custom chart builder
- [ ] Data export features
- [ ] User authentication
- [ ] Team workspaces
- [ ] Advanced drill-down visualizations
- [ ] Real-time data streaming

## 📄 License

This project is part of the DataSage AI platform.

---

**DataSage AI v2.0** - AI-Powered Data Visualization Platform 🚀

