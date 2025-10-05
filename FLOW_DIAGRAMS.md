# DataSage Flow Diagrams

## 🔄 Individual Flow Diagrams

### 1. User Authentication Flow

```mermaid
graph TD
    A[User Opens App] --> B{Already Logged In?}
    B -->|Yes| C[Redirect to Dashboard]
    B -->|No| D[Show Login Page]
    D --> E[User Enters Credentials]
    E --> F[POST /api/auth/login]
    F --> G{Valid Credentials?}
    G -->|No| H[Show Error Message]
    H --> D
    G -->|Yes| I[Generate JWT Token]
    I --> J[Store Token in Context]
    J --> K[Redirect to Dashboard]
    K --> L[Load User Data]
    L --> M[Show Dashboard]
```

### 2. Dataset Upload Flow

```mermaid
graph TD
    A[User Clicks Upload] --> B[Open Upload Modal]
    B --> C[User Selects File]
    C --> D{File Valid?}
    D -->|No| E[Show Error Message]
    E --> C
    D -->|Yes| F[Show File Preview]
    F --> G[User Enters Dataset Name]
    G --> H[User Clicks Upload]
    H --> I[POST /api/datasets/upload]
    I --> J[Save File to Storage]
    J --> K[Generate File Metadata]
    K --> L[Store in MongoDB]
    L --> M[AI Analysis]
    M --> N[Return Success Response]
    N --> O[Update UI with New Dataset]
    O --> P[Close Upload Modal]
```

### 3. AI Visualization Flow

```mermaid
graph TD
    A[User Clicks AI Builder] --> B[Show Dataset Selection]
    B --> C[User Selects Dataset]
    C --> D[Load Dataset Metadata]
    D --> E[POST /api/ai/recommend-fields]
    E --> F[AI Analyzes Data Structure]
    F --> G[Generate Field Recommendations]
    G --> H[POST /api/ai/generate-insights]
    H --> I[Generate Data Insights]
    I --> J[Display AI Recommendations]
    J --> K[User Selects Recommendation]
    K --> L[Generate Chart Data]
    L --> M[Create Plotly Chart]
    M --> N[Display Interactive Chart]
    N --> O[User Can Drill Down]
    O --> P[Save Chart Configuration]
```

### 4. Natural Language Query Flow

```mermaid
graph TD
    A[User Types Query] --> B[POST /api/ai/natural-query]
    B --> C[Parse Query Intent]
    C --> D{Query Type?}
    D -->|Trend| E[Suggest Line Charts]
    D -->|Correlation| F[Suggest Scatter Plots]
    D -->|Distribution| G[Suggest Bar/Pie Charts]
    D -->|Ranking| H[Suggest Bar Charts]
    D -->|General| I[Provide General Guidance]
    E --> J[Generate Response]
    F --> J
    G --> J
    H --> J
    I --> J
    J --> K[Display AI Response]
    K --> L[Show Follow-up Questions]
    L --> M[User Can Ask More]
```

### 5. Chart Generation Flow

```mermaid
graph TD
    A[User Selects Chart Type] --> B[Choose Fields]
    B --> C[Validate Field Selection]
    C --> D{Valid Selection?}
    D -->|No| E[Show Validation Error]
    E --> B
    D -->|Yes| F[Generate Chart Configuration]
    F --> G[Create Plotly Data Object]
    G --> H[Set Chart Layout]
    H --> I[Configure Chart Options]
    I --> J[Render Interactive Chart]
    J --> K[Enable Drill-down]
    K --> L[Handle User Interactions]
    L --> M[Update Chart on Interaction]
    M --> N[Save Chart State]
```

### 6. Data Processing Flow

```mermaid
graph TD
    A[File Upload] --> B[Validate File Type]
    B --> C{Supported Format?}
    C -->|No| D[Return Error]
    C -->|Yes| E[Read File Content]
    E --> F[Detect Data Types]
    F --> G[Generate Column Metadata]
    G --> H[Calculate Basic Statistics]
    H --> I[Detect Missing Values]
    I --> J[Identify Data Patterns]
    J --> K[Generate AI Recommendations]
    K --> L[Store Metadata in MongoDB]
    L --> M[Save File to Disk]
    M --> N[Return Success Response]
```

## 🎯 Complete System Flow Chart

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[User Interface] --> B[Authentication]
        B --> C[Dashboard]
        C --> D[Dataset Management]
        C --> E[AI Visualization Builder]
        C --> F[Charts & Analytics]
        
        D --> D1[Upload Modal]
        D --> D2[Dataset List]
        D --> D3[Dataset Details]
        
        E --> E1[Dataset Selection]
        E --> E2[AI Recommendations]
        E --> E3[Natural Language Query]
        E --> E4[Chart Preview]
        
        F --> F1[Interactive Charts]
        F --> F2[Drill-down Support]
        F --> F3[Export Options]
    end
    
    subgraph "Backend Layer"
        G[FastAPI Application] --> H[Authentication Service]
        G --> I[Dataset Service]
        G --> J[AI Visualization Service]
        G --> K[File Storage Service]
        
        H --> H1[JWT Token Management]
        H --> H2[User Validation]
        
        I --> I1[File Upload Handler]
        I --> I2[Metadata Generation]
        I --> I3[Data Processing]
        
        J --> J1[Field Recommendations]
        J --> J2[Insight Generation]
        J --> J3[Natural Language Processing]
        
        K --> K1[File Storage]
        K --> K2[Metadata Management]
    end
    
    subgraph "Data Layer"
        L[MongoDB Database] --> M[User Collection]
        L --> N[Dataset Collection]
        L --> O[Metadata Storage]
        
        P[File System] --> Q[Dataset Files]
        P --> R[Chunked Data]
    end
    
    subgraph "AI Processing"
        S[Pattern Recognition] --> T[Statistical Analysis]
        T --> U[Recommendation Engine]
        U --> V[Natural Language Understanding]
    end
    
    %% Frontend to Backend Connections
    B --> H
    D1 --> I1
    E2 --> J1
    E3 --> J3
    F1 --> I2
    
    %% Backend to Data Connections
    H2 --> M
    I2 --> N
    I3 --> O
    K1 --> Q
    K2 --> R
    
    %% AI Processing Connections
    I3 --> S
    J1 --> U
    J2 --> T
    J3 --> V
    
    %% Data Flow
    M --> H1
    N --> I2
    O --> J1
    Q --> I3
    R --> I3
    
    %% AI Flow
    S --> J1
    T --> J2
    U --> E2
    V --> E3
```

## 🖼️ Visual Flow Diagrams

### 1. User Journey Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Landing Page  │───▶│   Login/Register│───▶│    Dashboard    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Builder    │◀───│   Datasets      │───▶│     Charts      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2. Data Processing Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ File Upload │───▶│ Validation  │───▶│ Processing  │───▶│ AI Analysis │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ File Storage│    │ Type Detect │    │ Metadata    │    │ Insights    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 3. AI Recommendation Engine

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Data Input  │───▶│ Pattern     │───▶│ Statistical │───▶│ Chart       │
│             │    │ Recognition │    │ Analysis    │    │ Suggestions │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Column      │    │ Data Type   │    │ Correlation │    │ Confidence  │
│ Analysis    │    │ Detection   │    │ Detection   │    │ Scoring     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 🔄 Complete System Architecture Flow

```mermaid
graph TB
    subgraph "User Interface Layer"
        UI1[Login Page]
        UI2[Registration Page]
        UI3[Dashboard]
        UI4[Dataset Management]
        UI5[AI Visualization Builder]
        UI6[Charts & Analytics]
        UI7[Settings]
    end
    
    subgraph "Application Layer"
        APP1[React Router]
        APP2[State Management]
        APP3[HTTP Client]
        APP4[Chart Components]
        APP5[Modal Components]
    end
    
    subgraph "API Gateway Layer"
        API1[FastAPI Router]
        API2[CORS Middleware]
        API3[Authentication Middleware]
        API4[Error Handling]
        API5[Request Validation]
    end
    
    subgraph "Business Logic Layer"
        BL1[Auth Service]
        BL2[Dataset Service]
        BL3[AI Visualization Service]
        BL4[File Storage Service]
        BL5[Metadata Service]
    end
    
    subgraph "Data Access Layer"
        DAL1[MongoDB Driver]
        DAL2[File System Access]
        DAL3[Data Processing]
        DAL4[Query Optimization]
    end
    
    subgraph "Data Storage Layer"
        DS1[MongoDB Database]
        DS2[File System]
        DS3[Cache Layer]
        DS4[Backup Storage]
    end
    
    subgraph "AI Processing Layer"
        AI1[Pattern Recognition]
        AI2[Statistical Analysis]
        AI3[Natural Language Processing]
        AI4[Recommendation Engine]
        AI5[Insight Generation]
    end
    
    %% User Interface to Application
    UI1 --> APP1
    UI2 --> APP1
    UI3 --> APP2
    UI4 --> APP3
    UI5 --> APP4
    UI6 --> APP4
    UI7 --> APP2
    
    %% Application to API Gateway
    APP1 --> API1
    APP2 --> API1
    APP3 --> API1
    APP4 --> API1
    APP5 --> API1
    
    %% API Gateway to Business Logic
    API1 --> BL1
    API1 --> BL2
    API1 --> BL3
    API1 --> BL4
    API1 --> BL5
    
    %% Business Logic to Data Access
    BL1 --> DAL1
    BL2 --> DAL1
    BL2 --> DAL2
    BL3 --> DAL3
    BL4 --> DAL2
    BL5 --> DAL1
    
    %% Data Access to Storage
    DAL1 --> DS1
    DAL2 --> DS2
    DAL3 --> DS1
    DAL4 --> DS1
    
    %% AI Processing Connections
    BL3 --> AI1
    BL3 --> AI2
    BL3 --> AI3
    BL3 --> AI4
    BL3 --> AI5
    
    %% AI to Data Access
    AI1 --> DAL3
    AI2 --> DAL3
    AI3 --> DAL3
    AI4 --> DAL3
    AI5 --> DAL3
    
    %% Cache Layer
    DS3 --> DAL1
    DS3 --> DAL2
    
    %% Backup
    DS1 --> DS4
    DS2 --> DS4
```

## 📊 Key Process Flows

### 1. End-to-End User Experience

```
User Registration → Email Verification → Login → Dashboard → 
Dataset Upload → AI Analysis → Chart Generation → 
Interactive Visualization → Export/Share
```

### 2. Data Processing Pipeline

```
File Upload → Validation → Type Detection → 
Metadata Generation → AI Analysis → Storage → 
API Response → Frontend Update
```

### 3. AI Recommendation Process

```
Data Input → Pattern Analysis → Statistical Processing → 
Recommendation Generation → Confidence Scoring → 
UI Presentation → User Selection → Chart Creation
```

### 4. Security Flow

```
Request → Authentication Check → Authorization → 
Rate Limiting → Input Validation → 
Business Logic → Response → Audit Logging
```

## 🎯 Performance Optimization Flows

### 1. Caching Strategy

```
Request → Cache Check → Cache Hit? → 
Yes: Return Cached Data → No: Process Request → 
Store in Cache → Return Response
```

### 2. File Processing

```
Large File → Chunked Reading → Parallel Processing → 
Metadata Generation → Background Storage → 
Progress Updates → Completion Notification
```

### 3. Database Optimization

```
Query → Index Check → Query Optimization → 
Execution Plan → Result Caching → 
Response → Cache Update
```

This comprehensive flow diagram documentation provides a complete view of how DataSage operates, from user interactions to data processing and AI analysis. Each flow is designed to be efficient, secure, and user-friendly while maintaining high performance and scalability.
