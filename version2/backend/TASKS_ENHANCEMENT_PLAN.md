# 🔧 tasks.py - Celery Worker Analysis & Enhancement Plan

## 📋 Current State Assessment

### ✅ **What's Working Well:**

1. **Proper Worker Initialization**
   - Fork-safe MongoDB connection per worker process
   - `@worker_process_init` signal for database setup

2. **Robust Data Cleaning Pipeline**
   - String normalization (whitespace stripping, null handling)
   - Duplicate column renaming
   - Numeric cleaning (inf/nan removal)
   - Duplicate row removal

3. **Comprehensive Metadata Generation**
   - Dataset overview (rows, columns)
   - Column metadata (types, null counts)
   - Statistical analysis integration
   - Data quality metrics

4. **Progress Tracking**
   - Celery state updates at each stage
   - Clear progress percentages (10% → 100%)

5. **Error Handling**
   - Try-catch with database failure updates
   - Truncated error messages for Celery
   - Proper exception propagation

6. **Vector Database Integration**
   - FAISS indexing after metadata generation
   - Separate task for query history

---

## 🚨 **Critical Issues & Gaps**

### **1. Missing Schema Validation**
❌ No validation that cleaned data matches expected schema  
❌ No type coercion for mismatched columns  
❌ No handling of mixed-type columns  

### **2. No Data Profiling**
❌ Missing cardinality analysis (unique values per column)  
❌ No domain detection (email, phone, date patterns)  
❌ No column relationship inference  

### **3. Incomplete Statistical Analysis**
❌ No correlation matrix generation  
❌ Missing outlier detection summary  
❌ No distribution analysis (skewness, kurtosis)  

### **4. No Intelligent Domain Detection**
❌ Not inferring dataset domain (automotive, healthcare, sales)  
❌ Missing key metric identification  
❌ No suggested aggregations  

### **5. Vector Indexing Is Fire-and-Forget**
❌ No retry mechanism on FAISS failure  
❌ No fallback if vector service unavailable  
❌ Warning logged but task succeeds anyway  

### **6. Missing Data Sampling**
❌ Not storing sample rows for AI context  
❌ Frontend can't preview data without full dataset load  

### **7. No Chart Recommendations**
❌ Not generating suggested visualizations  
❌ AI Designer has no pre-computed chart hints  

### **8. Limited Progress Granularity**
❌ Large gaps in progress updates (30% → 60%)  
❌ No sub-task progress for long operations  

---

## 🎯 **Enhancement Plan: Production-Grade Pipeline**

### **Phase 1: Data Intelligence Layer** 🧠

Add these steps to make your pipeline truly intelligent:

```python
# After data cleaning, before metadata:

[NEW] Step 3.5: DATA PROFILING (progress: 35%)
    - Cardinality analysis (unique value counts)
    - Domain pattern detection (email, phone, URL, date)
    - Column name normalization (snake_case)
    - Suggested data types (categorical vs numeric)
    
[NEW] Step 4: DOMAIN DETECTION (progress: 40%)
    - Infer dataset domain (sales, healthcare, automotive, etc.)
    - Identify key metrics (revenue, quantity, price, etc.)
    - Detect time columns (for trend analysis)
    - Classify columns: dimension vs measure
    
[NEW] Step 5: RELATIONSHIP INFERENCE (progress: 45%)
    - Detect foreign key relationships
    - Find hierarchies (country → state → city)
    - Identify aggregation paths
    
[NEW] Step 6: STATISTICAL DEEP DIVE (progress: 55%)
    - Correlation matrix (Pearson + Spearman)
    - Distribution analysis (skewness, kurtosis)
    - Outlier detection with severity scores
    - Trend detection for time series
    
[NEW] Step 7: CHART RECOMMENDATIONS (progress: 65%)
    - Generate 5-10 recommended charts
    - Match column types to chart types
    - Calculate chart relevance scores
    - Prepare chart configs for AI Designer
    
[NEW] Step 8: DATA SAMPLING (progress: 70%)
    - Store first 100 rows for AI context
    - Store representative samples (stratified)
    - Create column value examples
```

### **Phase 2: Validation & Safety** 🛡️

```python
[NEW] SCHEMA VALIDATION (after cleaning)
    - Validate all columns have consistent types
    - Coerce mismatched types with warnings
    - Flag mixed-type columns for review
    - Generate schema fingerprint (hash)
    
[NEW] DATA QUALITY GATES
    - Minimum row count (e.g., 10 rows)
    - Maximum null percentage (e.g., 50%)
    - Minimum unique columns (e.g., 2)
    - Flag low-quality datasets
```

### **Phase 3: Enhanced Vector Indexing** 🔍

```python
[NEW] RETRY LOGIC FOR FAISS
    - Retry up to 3 times on failure
    - Exponential backoff (1s, 2s, 4s)
    - Mark dataset as "partial_success" if vector fails
    - Queue separate retry task
    
[NEW] FALLBACK HANDLING
    - If FAISS unavailable, continue processing
    - Store "vector_indexed: false" flag
    - Background job retries later
```

### **Phase 4: Progress & Observability** 📊

```python
[NEW] DETAILED PROGRESS TRACKING
    - Emit progress every 5% instead of 30%
    - Sub-task progress for long operations
    - Estimated time remaining
    - Current operation name
    
[NEW] METRICS COLLECTION
    - Processing time per dataset
    - Average rows/second processed
    - Error rates by file type
    - Cache hit rates
```

---

## 🔥 **Proposed Enhanced Pipeline**

```python
@celery_app.task(bind=True)
def process_dataset_task(self, dataset_id: str, file_path: str):
    """
    ENHANCED: Full Data Intelligence Pipeline
    
    Pipeline Stages:
    [10%] Load dataset
    [20%] Clean data
    [25%] Validate schema
    [30%] Generate metadata
    [35%] Profile data (NEW)
    [40%] Detect domain (NEW)
    [45%] Infer relationships (NEW)
    [50%] Run statistical analysis
    [55%] Generate correlation matrix (NEW)
    [60%] Detect outliers (NEW)
    [65%] Generate chart recommendations (NEW)
    [70%] Sample data for AI context (NEW)
    [75%] Calculate data quality scores
    [80%] Prepare metadata
    [85%] Save to database
    [90%] Index to FAISS (with retry)
    [95%] Generate cache keys
    [100%] Complete
    """
    
    pipeline = DataProcessingPipeline(self, dataset_id, file_path)
    return pipeline.execute()
```

---

## 📦 **New Service Classes Needed**

### **1. DataProfiler Service**
```python
# services/datasets/data_profiler.py

class DataProfiler:
    def profile_dataset(self, df: pl.DataFrame) -> Dict:
        """
        Returns:
        {
            "cardinality": {column: unique_count},
            "domains": {column: "email|phone|url|date|text"},
            "suggested_types": {column: "categorical|numeric|temporal"},
            "value_distributions": {column: [top_10_values]}
        }
        """
```

### **2. DomainDetector Service**
```python
# services/datasets/domain_detector.py

class DomainDetector:
    def detect_domain(self, df: pl.DataFrame, columns: List[str]) -> Dict:
        """
        Returns:
        {
            "domain": "automotive|healthcare|sales|finance|general",
            "key_metrics": ["revenue", "price", "quantity"],
            "time_columns": ["date", "timestamp"],
            "dimensions": ["region", "category", "product"],
            "measures": ["sales", "profit", "cost"]
        }
        """
```

### **3. RelationshipInference Service**
```python
# services/datasets/relationship_inference.py

class RelationshipInference:
    def infer_relationships(self, df: pl.DataFrame) -> Dict:
        """
        Returns:
        {
            "hierarchies": [
                {"path": ["country", "state", "city"], "type": "geographic"}
            ],
            "foreign_keys": [
                {"from": "product_id", "to": "products.id"}
            ],
            "aggregation_paths": [
                {"group_by": "category", "measure": "sales", "agg": "sum"}
            ]
        }
        """
```

### **4. ChartRecommender Service**
```python
# services/datasets/chart_recommender.py

class ChartRecommender:
    def recommend_charts(self, df: pl.DataFrame, metadata: Dict) -> List[Dict]:
        """
        Returns:
        [
            {
                "chart_type": "bar",
                "columns": ["category", "sales"],
                "aggregation": "sum",
                "title": "Sales by Category",
                "relevance_score": 0.95,
                "reason": "Categorical vs Numeric comparison"
            },
            ...
        ]
        """
```

---

## 🎯 **Implementation Priority**

### **Week 1: Core Enhancements**
1. ✅ Add data profiling (cardinality, domains)
2. ✅ Add domain detection (automotive, sales, etc.)
3. ✅ Generate chart recommendations
4. ✅ Store data samples (first 100 rows)

### **Week 2: Intelligence**
5. ✅ Add correlation matrix generation
6. ✅ Enhance outlier detection
7. ✅ Add relationship inference
8. ✅ Improve progress tracking

### **Week 3: Reliability**
9. ✅ Add FAISS retry logic
10. ✅ Add schema validation
11. ✅ Add data quality gates
12. ✅ Add error recovery

---

## 💡 **Key Benefits After Enhancement**

### **For AI Designer:**
✅ Knows dataset domain → selects correct pattern  
✅ Has pre-computed chart recommendations → faster generation  
✅ Has column relationships → better dashboard layouts  

### **For Chat System:**
✅ Has data samples → better AI context  
✅ Has cardinality info → knows when to aggregate  
✅ Has correlation matrix → suggests relationships  

### **For Users:**
✅ Faster dashboard generation (pre-computed recommendations)  
✅ Higher quality insights (domain-aware analysis)  
✅ Better error messages (validation feedback)  

### **For System:**
✅ Reduced LLM calls (more metadata available)  
✅ Better caching (chart recommendations stored)  
✅ Higher reliability (retry mechanisms)  

---

## 🚀 **Next Steps**

Would you like me to:

1. **Implement Phase 1** (Data Profiling + Domain Detection)
2. **Create new service classes** (DataProfiler, DomainDetector, ChartRecommender)
3. **Enhance existing tasks.py** with new pipeline stages
4. **Add comprehensive error handling** with retry logic
5. **All of the above** (complete overhaul)

**Which approach do you prefer?** 🎯
