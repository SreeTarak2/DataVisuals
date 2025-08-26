# 📊 DataSage AI

**AI-powered data visualization and analysis platform** that transforms raw datasets into interactive dashboards, insights, and recommendations with dual persona support.

## 🌟 Features

- **Dual Persona System**: Normal (simple storytelling) vs Expert (technical depth)
- **AI-Powered Insights**: OpenAI GPT-4 driven explanations and visualization recommendations
- **Smart Dashboards**: Pre-built templates + AI-customized layouts
- **Proactive Analysis**: Anomaly detection, trend analysis, what-if simulations
- **Interactive Visualizations**: Dynamic charts that adapt to user queries

## 🚀 Quick Start

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
Create `.env` file in backend directory:
```env
MONGODB_URI=mongodb://localhost:27017
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

## 🏗️ Architecture

- **Backend**: FastAPI + MongoDB + OpenAI GPT-4 + LangChain
- **Frontend**: React + TailwindCSS + ShadCN UI + Recharts
- **AI**: OpenAI-powered insights with statistical fallbacks

## 📚 API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

## 🎯 Roadmap

- [x] Project structure & setup
- [ ] Dataset upload & profiling
- [ ] Visualization recommendations
- [ ] OpenAI integration
- [ ] Persona system
- [ ] Dashboard templates
- [ ] Advanced analytics
