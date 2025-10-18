# QUIS Analysis & FAISS Vector Database Implementation

This document describes the enhanced QUIS (Question-driven Insight Search) analysis capabilities and FAISS vector database implementation in DataSage AI.

## 🚀 QUIS Subspace Search Analysis

### Overview

The QUIS methodology implements automated Exploratory Data Analysis (EDA) with a focus on discovering **hidden patterns** through subspace search. Unlike traditional analysis that looks at the entire dataset, QUIS finds insights that become much stronger in specific data segments.

### Key Features

#### 1. **Subspace Search**
- Finds correlations that are weak overall but strong in specific segments
- Discovers patterns like "While overall correlation is 0.5, in North Electronics it's 0.9"
- Supports single-level and two-level subspace filtering

#### 2. **Multi-Dimensional Analysis**
- **Correlation Subspaces**: Finds segments where correlations are significantly stronger
- **Category-Specific Patterns**: Identifies categories with unusual statistical properties  
- **Temporal Subspace Patterns**: Discovers time-based trends in specific segments

#### 3. **Configurable Search Depth**
- `max_depth=1`: Single-level filtering (e.g., Region=North)
- `max_depth=2`: Two-level filtering (e.g., Region=North AND Category=Electronics)

### API Endpoints

#### Run QUIS Analysis
```http
POST /api/analysis/run-quis
Content-Type: application/json

{
  "dataset_id": "your-dataset-id",
  "max_depth": 2
}
```

**Response:**
```json
{
  "quis_analysis": {
    "basic_insights": [...],
    "deep_insights": [
      {
        "type": "subspace_correlation",
        "base_insight": {"columns": ["sales", "profit"], "value": 0.5},
        "subspace": {"region": "North", "category": "Electronics"},
        "subspace_correlation": 0.92,
        "improvement": 0.42,
        "subspace_size": 150,
        "significance": "very_high"
      }
    ],
    "summary": {
      "total_basic_insights": 15,
      "total_deep_insights": 8,
      "high_significance_insights": 5,
      "very_high_significance_insights": 2
    }
  }
}
```

### Example Insights

#### Subspace Correlation
```json
{
  "type": "subspace_correlation",
  "base_insight": {"columns": ["price", "sales"], "value": 0.3},
  "subspace": {"region": "North"},
  "subspace_correlation": 0.85,
  "improvement": 0.55,
  "significance": "very_high"
}
```
**Interpretation**: While price and sales have a weak correlation (0.3) overall, in the North region the correlation is very strong (0.85).

#### Category-Specific Pattern
```json
{
  "type": "category_specific_pattern",
  "category_column": "age_group",
  "category_value": "18-25",
  "numeric_column": "spending",
  "overall_mean": 500.0,
  "subspace_mean": 750.0,
  "deviation": 2.1,
  "significance": "high"
}
```
**Interpretation**: The 18-25 age group spends significantly more (750 vs 500 average) than the overall population.

## 🔍 FAISS Vector Database

### Overview

FAISS (Facebook AI Similarity Search) provides high-performance vector operations for semantic search and RAG (Retrieval-Augmented Generation). It replaces ChromaDB for better scalability and performance.

### Key Features

#### 1. **Billion-Scale Performance**
- Handles millions of vectors efficiently
- GPU acceleration support (when using `faiss-gpu`)
- Persistent storage with automatic indexing

#### 2. **Multi-tenant Support**
- User isolation for datasets and queries
- Efficient filtering by user ID
- Automatic cleanup and reset capabilities

#### 3. **Advanced Search Capabilities**
- Cosine similarity search with normalized embeddings
- Semantic dataset search
- Query history tracking for RAG enhancement

### API Endpoints

#### Index Dataset
```http
POST /api/vector/datasets/{dataset_id}/index
```

#### Search Similar Datasets
```http
POST /api/vector/search/datasets
Content-Type: application/json

{
  "query": "sales data with customer demographics",
  "limit": 5
}
```

#### Enhanced RAG Search
```http
POST /api/vector/rag/{dataset_id}/enhanced
Content-Type: application/json

{
  "query": "show me trends in customer spending"
}
```

#### Vector Database Stats
```http
GET /api/vector/stats
```

**Response:**
```json
{
  "status": "enabled",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "embedding_dimension": 384,
  "indices": {
    "datasets": {
      "total_vectors": 25,
      "user_vectors": 12
    },
    "query_history": {
      "total_vectors": 156,
      "user_vectors": 89
    }
  }
}
```

### Configuration

Update your `.env` file:
```bash
# Vector Database Settings
VECTOR_DB_PATH=./vector_db
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENABLE_VECTOR_SEARCH=true
```

### Performance Comparison

| Feature | ChromaDB | FAISS |
|---------|----------|-------|
| **Scalability** | Good for prototyping | Billion-scale production |
| **Performance** | Moderate | Very fast |
| **Memory Usage** | Higher | Optimized |
| **GPU Support** | Limited | Full support |
| **Persistence** | Built-in | Custom implementation |
| **Multi-tenancy** | Basic | Advanced |

## 🧪 Testing

### Run QUIS Analysis Test
```bash
cd backend
python test_quis_analysis.py
```

This test script:
1. Creates sample datasets with hidden patterns
2. Demonstrates subspace search capabilities
3. Shows how QUIS finds insights that traditional analysis misses

### Expected Output
```
🚀 Testing QUIS Subspace Search Analysis
============================================================

📊 Testing with Sales Dataset...
Dataset shape: (1000, 7)
Columns: ['region', 'category', 'month', 'sales', 'profit', 'customer_count', 'avg_order_value']

📈 QUIS Analysis Results:
Basic insights found: 15
Deep insights found: 8
High significance insights: 5
Very high significance insights: 2

🔍 Deep Insights (Subspace Search Results):

1. subspace_correlation
   Subspace: {'region': 'North', 'category': 'Electronics'}
   Improvement: 0.42
   Significance: very_high
   Subspace size: 150 records
```

## 🔧 Implementation Details

### QUIS Analysis Service

**File**: `services/analysis_service.py`

**Key Methods**:
- `run_quis_analysis()`: Master function for comprehensive QUIS analysis
- `find_deep_insights()`: Core subspace search implementation
- `_search_correlation_subspaces()`: Finds correlations in filtered segments
- `_find_category_specific_patterns()`: Identifies unusual category behaviors
- `_find_temporal_subspace_patterns()`: Discovers time-based patterns in segments

### FAISS Vector Service

**File**: `services/faiss_vector_service.py`

**Key Methods**:
- `add_dataset_to_vector_db()`: Index dataset metadata for semantic search
- `search_similar_datasets()`: Find similar datasets using embeddings
- `enhanced_rag_search()`: Combine vector search with dataset context
- `_normalize_embeddings()`: Prepare vectors for cosine similarity

### Integration Points

1. **Dataset Processing**: Automatic vector indexing after metadata generation
2. **Chat Interface**: Enhanced RAG context for better AI responses
3. **Analysis Pipeline**: QUIS insights feed into AI summarization

## 🚀 Next Steps

### Planned Enhancements

1. **True QUGEN**: Replace static question templates with AI-generated questions
2. **Iterative Learning**: Store successful patterns for future few-shot learning
3. **Advanced Subspace Search**: Three-level filtering and more sophisticated algorithms
4. **Real-time Analysis**: Streaming analysis for live data sources

### Performance Optimizations

1. **GPU Acceleration**: Enable FAISS GPU support for large-scale deployments
2. **Parallel Processing**: Multi-threaded subspace search for large datasets
3. **Caching**: Cache frequent subspace patterns and embeddings
4. **Index Optimization**: Use FAISS IVF indexes for billion-scale operations

## 📚 References

- **QUIS Paper**: "Question-driven Insight Search for Automated Exploratory Data Analysis" (2024)
- **FAISS Documentation**: https://github.com/facebookresearch/faiss
- **Sentence Transformers**: https://www.sbert.net/

## 🤝 Contributing

When adding new analysis methods or vector operations:

1. Follow the existing pattern in `analysis_service.py`
2. Add comprehensive tests in `test_quis_analysis.py`
3. Update API documentation
4. Consider performance implications for large datasets

---

*This implementation transforms DataSage AI from a basic analytics tool into a sophisticated AI-powered insight discovery platform, capable of finding hidden patterns that traditional analysis would miss.*



