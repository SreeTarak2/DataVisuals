# DataSage API Documentation

## 🔗 Base URL
- **Development**: `http://localhost:8000`
- **Production**: `https://api.datasage.ai`

## 🔐 Authentication

All API endpoints (except auth endpoints) require authentication via JWT token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## 📚 API Endpoints

### Authentication Endpoints

#### Register User
```http
POST /api/auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "id": "user_id",
    "email": "user@example.com",
    "full_name": "John Doe"
  },
  "message": "Account created successfully!"
}
```

#### Login User
```http
POST /api/auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "user": {
    "id": "user_id",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

#### Get Current User
```http
GET /api/auth/me
```

**Headers:**
```
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "id": "user_id",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Dataset Endpoints

#### Upload Dataset
```http
POST /api/datasets/upload
```

**Headers:**
```
Authorization: Bearer <jwt-token>
Content-Type: multipart/form-data
```

**Request Body (Form Data):**
- `file`: File to upload (CSV, Excel, or JSON)
- `name`: Dataset name (optional)
- `description`: Dataset description (optional)

**Response:**
```json
{
  "dataset_id": "dataset_uuid",
  "message": "Dataset uploaded successfully",
  "metadata": {
    "dataset_overview": {
      "total_rows": 1000,
      "total_columns": 5,
      "numeric_columns": 3,
      "categorical_columns": 2,
      "missing_values": 10,
      "duplicate_rows": 0
    },
    "column_metadata": [
      {
        "name": "column1",
        "type": "int64",
        "null_count": 0,
        "null_percentage": 0.0,
        "unique_count": 100
      }
    ],
    "statistical_summaries": {},
    "data_quality": {
      "completeness": 99.0,
      "uniqueness": 100.0,
      "consistency": 85.0,
      "accuracy": 90.0
    },
    "chart_recommendations": [],
    "hierarchies": []
  }
}
```

#### List Datasets
```http
GET /api/datasets?skip=0&limit=100
```

**Headers:**
```
Authorization: Bearer <jwt-token>
```

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: 100)

**Response:**
```json
{
  "datasets": [
    {
      "id": "dataset_id",
      "name": "Sales Data",
      "description": "Monthly sales data",
      "file_size": 1024000,
      "row_count": 1000,
      "column_count": 5,
      "uploaded_at": "2024-01-01T00:00:00Z",
      "is_processed": true,
      "columns": ["date", "sales", "region", "product", "quantity"]
    }
  ]
}
```

#### Get Dataset Details
```http
GET /api/datasets/{dataset_id}
```

**Headers:**
```
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "id": "dataset_id",
  "name": "Sales Data",
  "description": "Monthly sales data",
  "original_filename": "sales_data.csv",
  "file_size": 1024000,
  "mime_type": "text/csv",
  "file_extension": ".csv",
  "uploaded_at": "2024-01-01T00:00:00Z",
  "last_accessed": "2024-01-01T00:00:00Z",
  "is_active": true,
  "is_processed": true,
  "columns": ["date", "sales", "region", "product", "quantity"],
  "row_count": 1000,
  "column_count": 5,
  "preview_data": [
    {
      "date": "2024-01-01",
      "sales": 1500.00,
      "region": "North",
      "product": "Widget A",
      "quantity": 10
    }
  ],
  "metadata": {
    "dataset_overview": {},
    "column_metadata": [],
    "statistical_summaries": {},
    "data_quality": {},
    "chart_recommendations": [],
    "hierarchies": []
  }
}
```

#### Get Dataset Data
```http
GET /api/datasets/{dataset_id}/data?page=1&page_size=100
```

**Headers:**
```
Authorization: Bearer <jwt-token>
```

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Number of records per page (default: 100)

**Response:**
```json
{
  "data": [
    {
      "date": "2024-01-01",
      "sales": 1500.00,
      "region": "North",
      "product": "Widget A",
      "quantity": 10
    }
  ],
  "total_rows": 1000,
  "current_page": 1,
  "page_size": 100,
  "has_more": true
}
```

#### Get Dataset Summary
```http
GET /api/datasets/{dataset_id}/summary
```

**Headers:**
```
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "total_rows": 1000,
  "total_columns": 5,
  "numeric_columns": ["sales", "quantity"],
  "categorical_columns": ["region", "product"],
  "missing_values": {
    "date": 0,
    "sales": 5,
    "region": 0,
    "product": 0,
    "quantity": 0
  },
  "data_types": {
    "date": "object",
    "sales": "float64",
    "region": "object",
    "product": "object",
    "quantity": "int64"
  },
  "basic_stats": {
    "numeric_summary": {
      "sales": {
        "count": 995.0,
        "mean": 1250.50,
        "std": 300.25,
        "min": 500.00,
        "25%": 1000.00,
        "50%": 1200.00,
        "75%": 1500.00,
        "max": 2000.00
      }
    }
  }
}
```

#### Delete Dataset
```http
DELETE /api/datasets/{dataset_id}
```

**Headers:**
```
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "message": "Dataset deleted successfully"
}
```

### AI Endpoints

#### Get AI Field Recommendations
```http
POST /api/ai/recommend-fields
```

**Headers:**
```
Authorization: Bearer <jwt-token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "columns": [
    {
      "name": "sales",
      "type": "float64",
      "unique_count": 100,
      "null_count": 0
    },
    {
      "name": "region",
      "type": "object",
      "unique_count": 5,
      "null_count": 0
    }
  ],
  "dataset_name": "Sales Data"
}
```

**Response:**
```json
{
  "recommendations": [
    {
      "chartType": "bar",
      "fields": ["region", "sales"],
      "confidence": 0.9,
      "reasoning": "Categorical vs numeric data - ideal for comparison analysis",
      "insight": "Compare sales across region categories",
      "ai_analysis": "Potential correlation analysis between region and sales. Look for significant differences between groups."
    },
    {
      "chartType": "scatter",
      "fields": ["sales", "quantity"],
      "confidence": 0.85,
      "reasoning": "Two numeric variables detected - perfect for correlation analysis",
      "insight": "Explore relationship between sales and quantity",
      "ai_analysis": "Potential correlation analysis between sales and quantity. Look for linear or non-linear relationships."
    }
  ],
  "dataset_analysis": {
    "total_columns": 5,
    "numeric_columns": 2,
    "categorical_columns": 2,
    "datetime_columns": 1,
    "analysis_confidence": 0.85
  }
}
```

#### Generate AI Insights
```http
POST /api/ai/generate-insights
```

**Headers:**
```
Authorization: Bearer <jwt-token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "dataset_metadata": {
    "dataset_overview": {
      "total_rows": 1000,
      "total_columns": 5,
      "missing_values": 10
    },
    "column_metadata": [],
    "data_quality": {
      "completeness": 99.0
    }
  },
  "dataset_name": "Sales Data"
}
```

**Response:**
```json
{
  "insights": [
    {
      "type": "success",
      "title": "Excellent Data Quality",
      "content": "Your dataset has 99.0% completeness - great for analysis!",
      "confidence": 0.9,
      "action": "Ready for advanced analytics"
    },
    {
      "type": "pattern",
      "title": "Correlation Analysis Opportunity",
      "content": "You have 2 numeric columns - perfect for correlation analysis and scatter plots.",
      "confidence": 0.85,
      "action": "Try scatter plots to discover relationships"
    }
  ],
  "summary": {
    "total_insights": 2,
    "warnings": 0,
    "recommendations": 1,
    "generated_at": "2024-01-01T00:00:00Z"
  }
}
```

#### Process Natural Language Query
```http
POST /api/ai/natural-query
```

**Headers:**
```
Authorization: Bearer <jwt-token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "Show me sales trends over time",
  "dataset_metadata": {
    "dataset_overview": {},
    "column_metadata": []
  },
  "dataset_name": "Sales Data"
}
```

**Response:**
```json
{
  "response": "I can help you analyze trends in your data. Based on your dataset, I recommend using line charts to track changes over time. Would you like me to create a trend visualization?",
  "suggested_chart": "line",
  "confidence": 0.8,
  "follow_up_questions": [
    "What time period are you interested in?",
    "Which metric should we track over time?",
    "Do you want to see seasonal patterns?"
  ]
}
```

## 📊 Error Responses

### Standard Error Format
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

- **200 OK**: Request successful
- **201 Created**: Resource created successfully
- **400 Bad Request**: Invalid request data
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Access denied
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation error
- **500 Internal Server Error**: Server error

### Example Error Responses

#### Validation Error (422)
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

#### Authentication Error (401)
```json
{
  "detail": "Could not validate credentials"
}
```

#### Not Found Error (404)
```json
{
  "detail": "Dataset not found"
}
```

## 🔧 Rate Limiting

- **Authentication endpoints**: 5 requests per minute per IP
- **Dataset upload**: 10 requests per hour per user
- **AI endpoints**: 20 requests per minute per user
- **Other endpoints**: 100 requests per minute per user

## 📝 Request/Response Examples

### Complete Dataset Upload Flow

1. **Upload Dataset**
```bash
curl -X POST "http://localhost:8000/api/datasets/upload" \
  -H "Authorization: Bearer your-jwt-token" \
  -F "file=@sales_data.csv" \
  -F "name=Sales Data" \
  -F "description=Monthly sales data for 2024"
```

2. **Get AI Recommendations**
```bash
curl -X POST "http://localhost:8000/api/ai/recommend-fields" \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{
    "columns": [
      {"name": "date", "type": "object", "unique_count": 365, "null_count": 0},
      {"name": "sales", "type": "float64", "unique_count": 1000, "null_count": 0},
      {"name": "region", "type": "object", "unique_count": 5, "null_count": 0}
    ],
    "dataset_name": "Sales Data"
  }'
```

3. **Generate Chart Data**
```bash
curl -X GET "http://localhost:8000/api/datasets/dataset_id/data?page=1&page_size=100" \
  -H "Authorization: Bearer your-jwt-token"
```

## 🔍 Testing the API

### Using Postman
1. Import the API collection
2. Set up environment variables for base URL and auth token
3. Run the authentication flow first
4. Use the returned token for subsequent requests

### Using curl
```bash
# Login and get token
TOKEN=$(curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}' \
  | jq -r '.access_token')

# Use token for authenticated requests
curl -X GET "http://localhost:8000/api/datasets" \
  -H "Authorization: Bearer $TOKEN"
```

## 📚 SDK Examples

### JavaScript/TypeScript
```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Upload dataset
const uploadDataset = async (file: File, name: string) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name);
  
  const response = await api.post('/api/datasets/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  
  return response.data;
};

// Get AI recommendations
const getAIRecommendations = async (columns: any[], datasetName: string) => {
  const response = await api.post('/api/ai/recommend-fields', {
    columns,
    dataset_name: datasetName
  });
  
  return response.data;
};
```

### Python
```python
import requests
import json

class DataSageAPI:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None
    
    def login(self, email, password):
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            json={"email": email, "password": password}
        )
        data = response.json()
        self.token = data["access_token"]
        return data
    
    def upload_dataset(self, file_path, name=None, description=None):
        headers = {"Authorization": f"Bearer {self.token}"}
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'name': name, 'description': description}
            
            response = requests.post(
                f"{self.base_url}/api/datasets/upload",
                headers=headers,
                files=files,
                data=data
            )
        
        return response.json()
    
    def get_ai_recommendations(self, columns, dataset_name):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{self.base_url}/api/ai/recommend-fields",
            headers=headers,
            json={"columns": columns, "dataset_name": dataset_name}
        )
        
        return response.json()

# Usage
api = DataSageAPI()
api.login("user@example.com", "password")
result = api.upload_dataset("data.csv", "My Dataset")
```

This comprehensive API documentation provides all the information needed to integrate with DataSage's backend services.
