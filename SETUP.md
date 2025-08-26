# 🚀 DataSage AI - Quick Setup Guide

## 📋 Prerequisites

Before starting, ensure you have the following installed:

- **Python 3.8+** with pip
- **Node.js 16+** with npm
- **MongoDB** (local or cloud instance)
- **OpenAI API Key** (for AI-powered insights)

## 🔧 Installation Steps

### 1. Clone and Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd datasage

# Make startup script executable
chmod +x start.sh
```

### 2. Backend Setup
```bash
cd backend

# Copy environment file
cp env.example .env

# Edit .env with your configuration
nano .env

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd ../frontend

# Install dependencies
npm install
```

### 4. Environment Configuration

Edit `backend/.env`:
```env
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=datasage

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true
```

**Important**: Replace `your_openai_api_key_here` with your actual OpenAI API key.

## 🚀 Starting the Application

### Option 1: Use Startup Script (Recommended)
```bash
./start.sh
```

### Option 2: Manual Start
```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## 🌐 Access Points

- **Frontend Application**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📊 Testing the Application

### 1. Health Check
Visit `http://localhost:8000/health` to verify all services are running.

### 2. Upload a Dataset
- Go to http://localhost:3000/datasets
- Upload a CSV or Excel file
- Check the auto-profiling results

### 3. Try AI Analysis
- Go to http://localhost:3000/analysis
- Ask questions about your data
- Switch between Normal and Expert personas

### 4. Explore Templates
- Go to http://localhost:3000/templates
- Browse available dashboard templates
- See persona-specific features

## 🔍 Troubleshooting

### Common Issues

#### MongoDB Connection Failed
```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Start MongoDB if needed
sudo systemctl start mongod
```

#### OpenAI API Key Issues
```bash
# Check if API key is set
echo $OPENAI_API_KEY

# Or check .env file
cat backend/.env | grep OPENAI_API_KEY

# Make sure your API key is valid and has credits
```

#### Port Already in Use
```bash
# Check what's using the port
lsof -i :8000
lsof -i :3000

# Kill the process or change ports in .env
```

#### Python Dependencies Issues
```bash
cd backend
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

#### Node Dependencies Issues
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## 🧪 Sample Data

For testing, you can use these sample datasets:

### Sales Data (CSV)
```csv
date,product,category,sales_amount,customer_region
2024-01-01,Laptop,Electronics,1200,North
2024-01-02,Desk,Furniture,450,South
2024-01-03,Phone,Electronics,800,East
```

### Customer Data (CSV)
```csv
customer_id,name,age,city,subscription_type
1,John Doe,30,New York,Premium
2,Jane Smith,25,Los Angeles,Basic
3,Bob Johnson,35,Chicago,Premium
```

## 📚 Next Steps

1. **Explore the API**: Visit `/docs` for interactive API documentation
2. **Customize Personas**: Modify the OpenAI prompts in `backend/services/llm_service.py`
3. **Add Visualizations**: Integrate with Recharts/Plotly for custom charts
4. **Extend Analysis**: Add more statistical methods in `backend/services/data_profiler.py`
5. **Create Templates**: Build new dashboard templates in the frontend

## 🆘 Getting Help

- Check the logs in your terminal for error messages
- Verify MongoDB is running
- Ensure your OpenAI API key is valid and has credits
- Ensure ports 3000 and 8000 are available
- Check the browser console for frontend errors
- Review the API documentation at `/docs`

## 🎯 Development Tips

- **Hot Reload**: Both frontend and backend support hot reloading
- **Type Safety**: Full TypeScript support in frontend
- **API Testing**: Use the interactive docs at `/docs`
- **State Management**: Persona context is available throughout the app
- **Responsive Design**: Mobile-first approach with Tailwind CSS
- **OpenAI Integration**: Structured JSON responses for better parsing
