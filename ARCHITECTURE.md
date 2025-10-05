# DataSage Architecture Documentation

## 🏗️ System Architecture Overview

DataSage follows a modern microservices-inspired architecture with clear separation of concerns between the frontend, backend, and data layers.

## 📊 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                DataSage Platform                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────┐    ┌─────────────────────────────────────┐  │
│  │         Frontend Layer          │    │         Backend Layer               │  │
│  │                                 │    │                                     │  │
│  │  ┌─────────────────────────────┐│    │  ┌─────────────────────────────────┐│  │
│  │  │     Presentation Layer      ││    │  │      API Gateway Layer          ││  │
│  │  │  ┌─────────────────────────┐││    │  │  ┌─────────────────────────────┐││  │
│  │  │  │   React Components      │││    │  │  │   FastAPI Application       │││  │
│  │  │  │   - Dashboard           │││    │  │  │   - CORS Middleware         │││  │
│  │  │  │   - Dataset Management  │││    │  │  │   - Authentication          │││  │
│  │  │  │   - AI Visualization    │││    │  │  │   - Error Handling          │││  │
│  │  │  │   - Charts & Analytics  │││    │  │  │   - Request Validation      │││  │
│  │  │  └─────────────────────────┘││    │  │  └─────────────────────────────┘││  │
│  │  └─────────────────────────────┘│    │  └─────────────────────────────────┘│  │
│  │                                 │    │                                     │  │
│  │  ┌─────────────────────────────┐│    │  ┌─────────────────────────────────┐│  │
│  │  │     State Management        ││    │  │      Business Logic Layer       ││  │
│  │  │  ┌─────────────────────────┐││    │  │  ┌─────────────────────────────┐││  │
│  │  │  │   React Context         │││    │  │  │   Service Layer              │││  │
│  │  │  │   - AuthContext         │││    │  │  │   - AuthService              │││  │
│  │  │  │   - State Management    │││    │  │  │   - DatasetService           │││  │
│  │  │  │   - HTTP Client         │││    │  │  │   - AIVisualizationService  │││  │
│  │  │  └─────────────────────────┘││    │  │  │   - FileStorageService       │││  │
│  │  └─────────────────────────────┘│    │  │  └─────────────────────────────┘││  │
│  │                                 │    │  └─────────────────────────────────┘│  │
│  │  ┌─────────────────────────────┐│    │                                     │  │
│  │  │     Visualization Layer     ││    │  ┌─────────────────────────────────┐│  │
│  │  │  ┌─────────────────────────┐││    │  │      Data Access Layer          ││  │
│  │  │  │   Plotly.js             │││    │  │  ┌─────────────────────────────┐││  │
│  │  │  │   - Interactive Charts  │││    │  │  │   Database Layer             │││  │
│  │  │  │   - Drill-down Support  │││    │  │  │   - MongoDB Connection       │││  │
│  │  │  │   - Export Capabilities │││    │  │  │   - Data Models              │││  │
│  │  │  └─────────────────────────┘││    │  │  │   - Query Optimization       │││  │
│  │  └─────────────────────────────┘│    │  │  └─────────────────────────────┘││  │
│  └─────────────────────────────────┘    │  │  ┌─────────────────────────────┐││  │
│                                         │  │  │   File Storage Layer        │││  │
│                                         │  │  │   - Local File System       │││  │
│                                         │  │  │   - File Metadata           │││  │
│                                         │  │  │   - Chunked Processing      │││  │
│                                         │  │  └─────────────────────────────┘││  │
│                                         │  └─────────────────────────────────┘│  │
│                                         └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🔄 Data Flow Diagrams

### 1. User Authentication Flow

```
User → Frontend → Backend → Database
 │        │         │         │
 │        │         │         │
 │  1. Login Form   │         │
 │  ──────────────→ │         │
 │        │         │         │
 │        │  2. POST /auth/login
 │        │  ──────────────────→
 │        │         │         │
 │        │         │  3. Validate Credentials
 │        │         │  ──────────────────────→
 │        │         │         │
 │        │         │  4. User Data
 │        │         │  ←──────────────────────
 │        │         │         │
 │        │  5. JWT Token + User Info
 │        │  ←─────────────────
 │        │         │         │
 │  6. Store Token & Redirect
 │  ←─────────────── │         │
 │        │         │         │
```

### 2. Dataset Upload Flow

```
User → Frontend → Backend → File Storage → Database
 │        │         │         │            │
 │        │         │         │            │
 │  1. Select File  │         │            │
 │  ──────────────→ │         │            │
 │        │         │         │            │
 │        │  2. POST /datasets/upload
 │        │  ──────────────────→
 │        │         │         │            │
 │        │         │  3. Save File
 │        │         │  ──────────────────→
 │        │         │         │            │
 │        │         │  4. File Metadata
 │        │         │  ←──────────────────
 │        │         │         │            │
 │        │         │  5. Generate Metadata
 │        │         │  ───────────────────
 │        │         │         │            │
 │        │         │  6. Store Dataset Info
 │        │         │  ──────────────────────→
 │        │         │         │            │
 │        │         │  7. Dataset ID
 │        │         │  ←──────────────────────
 │        │         │         │            │
 │        │  8. Upload Success + Metadata
 │        │  ←─────────────────
 │        │         │         │            │
 │  9. Show Success Message
 │  ←─────────────── │         │            │
```

### 3. AI Visualization Flow

```
User → Frontend → Backend → AI Service → Database
 │        │         │         │           │
 │        │         │         │           │
 │  1. Open AI Builder
 │  ──────────────→ │         │           │
 │        │         │         │           │
 │        │  2. GET /datasets
 │        │  ──────────────────→
 │        │         │         │           │
 │        │         │  3. Query Datasets
 │        │         │  ──────────────────→
 │        │         │         │           │
 │        │         │  4. Dataset List
 │        │         │  ←──────────────────
 │        │         │         │           │
 │        │  5. Available Datasets
 │        │  ←─────────────────
 │        │         │         │           │
 │  6. Select Dataset
 │  ──────────────→ │         │           │
 │        │         │         │           │
 │        │  7. POST /ai/recommend-fields
 │        │  ──────────────────→
 │        │         │         │           │
 │        │         │  8. Analyze Dataset
 │        │         │  ──────────────────→
 │        │         │         │           │
 │        │         │  9. Field Recommendations
 │        │         │  ←──────────────────
 │        │         │         │           │
 │        │  10. AI Recommendations
 │        │  ←─────────────────
 │        │         │         │           │
 │  11. Select Recommendation
 │  ──────────────→ │         │           │
 │        │         │         │           │
 │        │  12. Generate Chart
 │        │  ──────────────────→
 │        │         │         │           │
 │        │  13. Chart Configuration
 │        │  ←─────────────────
 │        │         │         │           │
 │  14. Display Interactive Chart
 │  ←─────────────── │         │           │
```

## 🗄️ Database Schema

### MongoDB Collections

#### Users Collection
```json
{
  "_id": "ObjectId",
  "email": "string",
  "hashed_password": "string",
  "full_name": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "is_active": "boolean"
}
```

#### Datasets Collection
```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "name": "string",
  "description": "string",
  "original_filename": "string",
  "file_path": "string",
  "file_size": "number",
  "mime_type": "string",
  "file_extension": "string",
  "uploaded_at": "datetime",
  "last_accessed": "datetime",
  "is_active": "boolean",
  "is_processed": "boolean",
  "columns": ["string"],
  "row_count": "number",
  "column_count": "number",
  "preview_data": [{}],
  "sample_data": [{}],
  "metadata": {
    "dataset_overview": {},
    "column_metadata": [{}],
    "statistical_summaries": {},
    "data_quality": {},
    "chart_recommendations": [{}],
    "hierarchies": [{}]
  }
}
```

## 🔧 Component Architecture

### Frontend Components Hierarchy

```
App
├── AuthContext
├── Router
│   ├── Login
│   ├── Register
│   └── Dashboard
│       ├── Sidebar
│       ├── Header
│       └── Main Content
│           ├── Datasets
│           │   ├── UploadModal
│           │   └── ConfirmationModal
│           ├── Charts
│           │   ├── PlotlyChart
│           │   └── AIVisualizationBuilder
│           └── Dashboard
│               └── KPICard
```

### Backend Service Architecture

```
main.py (FastAPI App)
├── Middleware
│   ├── CORS
│   └── Authentication
├── Routes
│   ├── /api/auth/*
│   ├── /api/datasets/*
│   └── /api/ai/*
└── Services
    ├── auth_service.py
    ├── enhanced_dataset_service.py
    ├── ai_visualization_service.py
    └── file_storage_service.py
```

## 🚀 Deployment Architecture

### Development Environment
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (Vite Dev)    │◄──►│   (FastAPI)     │◄──►│   (MongoDB)     │
│   Port: 5173    │    │   Port: 8000    │    │   Port: 27017   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Production Environment
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx         │    │   Backend       │    │   Database      │
│   (Reverse      │◄──►│   (FastAPI +    │◄──►│   (MongoDB      │
│   Proxy)        │    │   Gunicorn)     │    │   Cluster)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔒 Security Architecture

### Authentication Flow
1. User submits credentials
2. Backend validates against database
3. JWT token generated with user info
4. Token stored in frontend context
5. All subsequent requests include token
6. Backend validates token on each request

### Data Security
- **Encryption**: Passwords hashed with bcrypt
- **Transport**: HTTPS in production
- **Storage**: User data isolated by user_id
- **Validation**: Input validation on all endpoints
- **CORS**: Configured for specific origins

## 📈 Performance Optimizations

### Frontend Optimizations
- **Code Splitting**: Lazy loading of components
- **Bundle Optimization**: Vite's built-in optimizations
- **Caching**: HTTP response caching
- **Virtual Scrolling**: For large datasets

### Backend Optimizations
- **Async Operations**: Non-blocking I/O operations
- **Database Indexing**: Optimized queries
- **Chunked Processing**: Large file handling
- **Connection Pooling**: Database connection management

### Data Layer Optimizations
- **Hybrid Storage**: Metadata in DB, files on disk
- **Compression**: File compression for storage
- **Caching**: Frequently accessed data caching
- **Pagination**: Large dataset pagination

## 🔄 Error Handling Strategy

### Frontend Error Handling
- **Global Error Boundary**: Catches React errors
- **HTTP Error Interceptors**: Axios error handling
- **User Notifications**: Toast notifications for errors
- **Fallback UI**: Graceful degradation

### Backend Error Handling
- **HTTP Exceptions**: Proper HTTP status codes
- **Validation Errors**: Pydantic validation
- **Database Errors**: Connection and query errors
- **Logging**: Comprehensive error logging

## 📊 Monitoring and Logging

### Application Metrics
- **Request/Response Times**: API performance
- **Error Rates**: Application stability
- **User Activity**: Usage patterns
- **Resource Usage**: Memory and CPU

### Logging Strategy
- **Structured Logging**: JSON format logs
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Log Aggregation**: Centralized log collection
- **Alerting**: Error threshold alerts

## 🚀 Scalability Considerations

### Horizontal Scaling
- **Load Balancing**: Multiple backend instances
- **Database Sharding**: Data distribution
- **CDN**: Static asset delivery
- **Microservices**: Service decomposition

### Vertical Scaling
- **Resource Optimization**: CPU and memory tuning
- **Database Optimization**: Query and index optimization
- **Caching Strategy**: Multi-level caching
- **Connection Pooling**: Database connection management

This architecture provides a solid foundation for DataSage's current features while maintaining flexibility for future enhancements and scaling requirements.
