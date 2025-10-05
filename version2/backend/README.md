# DataSage AI Backend v2.0

A FastAPI-based backend with MongoDB integration and JWT authentication for the DataSage AI platform.

## 🚀 Features

- **MongoDB Integration**: Full MongoDB support with async operations
- **JWT Authentication**: Secure user authentication and authorization
- **User Management**: Registration, login, profile management
- **Dataset Management**: Upload, process, and manage datasets
- **AI Services**: LLM integration for data analysis and insights
- **RESTful API**: Clean, documented API endpoints

## 📋 Prerequisites

- Python 3.8+
- MongoDB (local or cloud)
- Virtual environment (recommended)

## 🛠️ Installation

1. **Clone and navigate to the backend directory:**
   ```bash
   cd version2/backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   # Create .env file (optional, defaults will be used)
   cp .env.example .env
   # Edit .env with your configuration
   ```

## 🗄️ MongoDB Setup

### Option 1: Local MongoDB
1. **Install MongoDB:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install mongodb
   
   # macOS
   brew install mongodb-community
   
   # Windows
   # Download from https://www.mongodb.com/try/download/community
   ```

2. **Start MongoDB:**
   ```bash
   # Ubuntu/Debian
   sudo systemctl start mongod
   
   # macOS
   brew services start mongodb-community
   
   # Windows
   # Start MongoDB service from Services
   ```

### Option 2: MongoDB Atlas (Cloud)
1. Create a free account at [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Create a cluster
3. Get your connection string
4. Set `MONGODB_URL` in your environment

### Test MongoDB Connection
```bash
python test_mongodb.py
```

## 🚀 Running the Backend

### Development Mode
```bash
python start.py
```

### Production Mode
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`

## 📚 API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🔐 Authentication

### Register a new user:
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'
```

### Login:
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

### Use the token in subsequent requests:
```bash
curl -X GET "http://localhost:8000/api/datasets" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 📊 Dataset Management

### Upload a dataset:
```bash
curl -X POST "http://localhost:8000/api/datasets/upload" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@your_dataset.csv"
```

### Get user datasets:
```bash
curl -X GET "http://localhost:8000/api/datasets" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 🏗️ Project Structure

```
backend/
├── main.py                 # FastAPI application
├── database.py             # MongoDB connection and configuration
├── config.py              # Application settings
├── start.py               # Startup script
├── test_mongodb.py        # MongoDB connection test
├── requirements.txt       # Python dependencies
├── models/
│   └── schemas.py         # Pydantic models
└── services/
    ├── auth_service.py    # Authentication service
    ├── dataset_service.py # Dataset management service
    ├── enhanced_llm_service.py
    ├── metadata_service.py
    ├── rag_service.py
    ├── dynamic_drilldown_service.py
    └── chart_validation_service.py
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DATABASE_NAME` | `datasage_ai` | Database name |
| `SECRET_KEY` | `your-secret-key-change-in-production` | JWT secret key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token expiration time |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |

## 🧪 Testing

### Test MongoDB Connection:
```bash
python test_mongodb.py
```

### Test API Endpoints:
```bash
# Health check
curl http://localhost:8000/api/health

# Get API docs
curl http://localhost:8000/docs
```

## 🐛 Troubleshooting

### MongoDB Connection Issues
1. Ensure MongoDB is running
2. Check connection string
3. Verify network connectivity
4. Run `python test_mongodb.py`

### Authentication Issues
1. Check JWT secret key
2. Verify token expiration
3. Ensure proper Authorization header format

### File Upload Issues
1. Check file size limits
2. Verify file type restrictions
3. Ensure proper multipart/form-data encoding

## 📝 API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login user
- `GET /auth/me` - Get current user
- `PUT /auth/profile` - Update user profile
- `POST /auth/change-password` - Change password

### Datasets
- `GET /api/datasets` - List user datasets
- `POST /api/datasets/upload` - Upload dataset
- `GET /api/datasets/{id}` - Get dataset details
- `DELETE /api/datasets/{id}` - Delete dataset

### System
- `GET /api/health` - Health check
- `GET /docs` - API documentation

## 🔒 Security Features

- JWT-based authentication
- Password hashing with bcrypt
- CORS protection
- Input validation with Pydantic
- SQL injection protection (MongoDB)
- File type validation

## 🚀 Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "start.py"]
```

### Manual Deployment
1. Install dependencies
2. Set environment variables
3. Start MongoDB
4. Run the application
5. Configure reverse proxy (nginx)

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation
3. Check logs for error details
4. Test MongoDB connection

---

**DataSage AI Backend v2.0** - Built with FastAPI, MongoDB, and ❤️



