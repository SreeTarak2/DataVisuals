# Frontend-Backend Integration Plan
## DataSage AI v4.0 - Complete Migration Guide

**Version:** 4.0  
**Date:** November 16, 2025  
**Status:** 🔴 Frontend Disconnected - Requires Updates

---

## 🎯 Executive Summary

The backend has been significantly enhanced with **production-level intelligence services**, but the frontend is currently disconnected. This document provides a complete plan to reconnect and enhance the frontend to leverage the new backend capabilities.

### **What Changed in Backend v4.0:**
- ✅ **11-Stage Production Pipeline** (tasks.py)
- ✅ **Hybrid Domain Detection** (90%+ accuracy)
- ✅ **Intelligent Data Profiling** (cardinality, patterns, relationships)
- ✅ **6-Layer Chart Intelligence** (90-95% expert alignment)
- ✅ **AI-Powered Chart Insights** (pattern detection, NL summaries)
- ✅ **Enhanced Metadata Structure** (domain, quality, profiling, recommendations)

### **Frontend Impact:**
- 🔴 **Current API calls may receive different response structures**
- 🔴 **New metadata fields not displayed in UI**
- 🔴 **Chart intelligence features not accessible**
- 🔴 **Domain detection results not shown**
- 🟡 **Core functionality (upload, view, delete) still works**

---

## 📊 API Changes Audit

### **1. Dataset Metadata Structure - BREAKING CHANGE**

#### **Old Response (v3.x):**
```json
{
  "id": "abc123",
  "name": "Sales Data",
  "metadata": {
    "row_count": 1000,
    "column_count": 10,
    "columns": [...],
    "data_types": {...}
  }
}
```

#### **New Response (v4.0):**
```json
{
  "id": "abc123",
  "name": "Sales Data",
  "metadata": {
    "dataset_overview": {
      "total_rows": 1000,
      "total_columns": 10,
      "domain": "sales",
      "domain_confidence": 0.92,
      "domain_detection_method": "hybrid"
    },
    "data_quality": {
      "completeness": 95.5,
      "duplicates_removed": 23,
      "missing_value_ratio": 0.045,
      "quality_score": 0.89
    },
    "profiling_results": {
      "cardinality_levels": {
        "customer_id": "very_high",
        "product_category": "low",
        "sales_amount": "high"
      },
      "detected_patterns": {
        "email": ["customer_email"],
        "phone": ["phone_number"],
        "uuid": ["transaction_id"]
      },
      "column_quality": {...}
    },
    "chart_recommendations": [
      {
        "chart_type": "line",
        "priority": 1,
        "confidence": 0.95,
        "reason": "Time series data detected",
        "suggested_axes": {...}
      }
    ],
    "statistical_analysis": {...},
    "columns": [...],
    "data_types": {...}
  }
}
```

**Frontend Action Required:**
- Update `datasetAPI.getDataset()` response handling
- Add parsers for new nested structures
- Update dataset detail components

---

### **2. New Endpoints - NOT AVAILABLE IN FRONTEND**

| Endpoint | Method | Purpose | Frontend Status |
|----------|--------|---------|-----------------|
| `/api/datasets/{id}/domain` | GET | Get domain detection details | ❌ Missing |
| `/api/datasets/{id}/profiling` | GET | Get data profiling results | ❌ Missing |
| `/api/datasets/{id}/chart-intelligence` | GET | Get AI chart recommendations | ❌ Missing |
| `/api/charts/{id}/insights` | GET | Get chart insights with patterns | ❌ Missing |
| `/api/datasets/{id}/quality-metrics` | GET | Get data quality breakdown | ❌ Missing |

**Frontend Action Required:**
- Add new methods to `api.js`
- Create corresponding React hooks
- Build UI components to display results

---

### **3. Modified Endpoints - RESPONSE STRUCTURE CHANGED**

#### **`GET /api/datasets/{id}/columns`**

**Old Response:**
```json
{
  "columns": [
    {"name": "age", "type": "integer", "nullable": false}
  ]
}
```

**New Response:**
```json
{
  "columns": [
    {
      "name": "age",
      "type": "integer",
      "nullable": false,
      "cardinality": "medium",
      "cardinality_count": 45,
      "pattern": null,
      "quality": {
        "completeness": 0.98,
        "unique_ratio": 0.45,
        "missing_count": 12
      }
    }
  ]
}
```

**Frontend Action Required:**
- Update column display components
- Add quality indicators (badges, progress bars)
- Show cardinality levels with icons

---

#### **`GET /api/dashboard/{id}/charts`**

**Old Response:**
```json
{
  "charts": [
    {"type": "bar", "config": {...}, "data": [...]}
  ]
}
```

**New Response:**
```json
{
  "charts": [
    {
      "type": "bar",
      "config": {...},
      "data": [...],
      "intelligence": {
        "confidence": 0.92,
        "layers_applied": ["statistical_rules", "domain_patterns"],
        "expert_alignment": 0.94,
        "selection_reasoning": "Categorical comparison best practice"
      },
      "insights": {
        "summary": "Top category dominates with 67% share",
        "patterns": [
          {
            "type": "comparison",
            "pattern": "significant_difference",
            "confidence": 0.9
          }
        ],
        "recommendations": ["Analyze top performers for insights"]
      }
    }
  ]
}
```

**Frontend Action Required:**
- Display confidence badges on charts
- Show "Why this chart?" tooltips with reasoning
- Add insight cards below charts
- Create intelligence panel showing layer breakdown

---

### **4. Upload Pipeline Progress - NEW STRUCTURE**

**Old Progress Updates:**
```json
{
  "progress": 50,
  "status": "processing"
}
```

**New Progress Updates (11 Stages):**
```json
{
  "progress": 35,
  "stage": "domain_detection",
  "stage_name": "Domain Detection (Hybrid)",
  "message": "🔍 Detecting dataset domain with hybrid approach...",
  "stages_completed": 3,
  "total_stages": 11,
  "status": "processing"
}
```

**Frontend Action Required:**
- Update progress bar to show stage names
- Add stage icons (✓ for completed, 🔄 for current)
- Show detailed stage breakdown in expandable panel

---

## 🛠️ Frontend Updates Required

### **Phase 1: Core API Service Updates (Week 1)**

#### **1.1 Update `api.js` - Add New Endpoints**

```javascript
// services/api.js

// Add to datasetAPI object
export const datasetAPI = {
  // ... existing methods ...
  
  // NEW: Domain Detection
  getDomainDetection: (id) => api.get(`/datasets/${id}/domain`),
  
  // NEW: Data Profiling
  getDataProfiling: (id) => api.get(`/datasets/${id}/profiling`),
  
  // NEW: Chart Intelligence
  getChartIntelligence: (id) => api.get(`/datasets/${id}/chart-intelligence`),
  
  // NEW: Quality Metrics
  getQualityMetrics: (id) => api.get(`/datasets/${id}/quality-metrics`),
  
  // NEW: Enhanced Columns (with profiling)
  getEnhancedColumns: (id) => api.get(`/datasets/${id}/columns?enhanced=true`),
};

// NEW: Chart Intelligence API
export const chartIntelligenceAPI = {
  // Get AI-selected charts for dashboard
  getIntelligentCharts: (datasetId, limit = 5) => 
    api.get(`/charts/intelligent/${datasetId}?limit=${limit}`),
  
  // Get chart selection reasoning
  getChartReasoning: (datasetId, chartType) => 
    api.post(`/charts/explain-selection`, {
      dataset_id: datasetId,
      chart_type: chartType
    }),
  
  // Get confidence breakdown
  getConfidenceBreakdown: (datasetId, chartId) => 
    api.get(`/charts/${chartId}/confidence?dataset_id=${datasetId}`),
};

// Enhanced: Chart Insights with Patterns
export const chartInsightsAPI = {
  // ... existing methods ...
  
  // NEW: Get insights with pattern detection
  getChartInsightsEnhanced: (chartId, datasetId) => 
    api.get(`/charts/${chartId}/insights?dataset_id=${datasetId}&include_patterns=true`),
  
  // NEW: Get actionable recommendations
  getChartRecommendations: (chartId, datasetId) => 
    api.get(`/charts/${chartId}/recommendations?dataset_id=${datasetId}`),
};
```

---

#### **1.2 Create TypeScript Types**

```typescript
// types/dataset.types.ts

export interface DomainDetection {
  domain: string;
  confidence: number;
  method: 'rule-based' | 'llm' | 'hybrid';
  matched_patterns: string[];
  llm_reasoning?: string;
}

export interface CardinalityLevel {
  level: 'low' | 'medium' | 'high' | 'very_high';
  count: number;
  unique_ratio: number;
}

export interface DataProfiling {
  cardinality_levels: Record<string, CardinalityLevel>;
  detected_patterns: {
    email?: string[];
    phone?: string[];
    url?: string[];
    uuid?: string[];
    credit_card?: string[];
    ssn?: string[];
    ip_address?: string[];
    zip_code?: string[];
  };
  column_quality: Record<string, ColumnQuality>;
  relationships?: Relationship[];
}

export interface ColumnQuality {
  completeness: number;
  unique_ratio: number;
  missing_count: number;
  outlier_count?: number;
  pattern_conformity?: number;
}

export interface ChartIntelligence {
  confidence: number;
  layers_applied: string[];
  expert_alignment: number;
  selection_reasoning: string;
  statistical_rules_matched?: string[];
  domain_patterns_matched?: string[];
}

export interface ChartInsight {
  summary: string;
  patterns: ChartPattern[];
  recommendations: string[];
  enhanced_insight?: string;
  confidence: number;
  generated_at: string;
}

export interface ChartPattern {
  type: 'trend' | 'comparison' | 'correlation' | 'composition' | 'intensity';
  pattern: string;
  description: string;
  confidence: number;
  metric?: string;
  [key: string]: any;
}

export interface EnhancedMetadata {
  dataset_overview: {
    total_rows: number;
    total_columns: number;
    domain: string;
    domain_confidence: number;
    domain_detection_method: string;
  };
  data_quality: {
    completeness: number;
    duplicates_removed: number;
    missing_value_ratio: number;
    quality_score: number;
  };
  profiling_results: DataProfiling;
  chart_recommendations: ChartRecommendation[];
  statistical_analysis: StatisticalAnalysis;
  columns: EnhancedColumn[];
  data_types: Record<string, string>;
}

export interface ChartRecommendation {
  chart_type: string;
  priority: number;
  confidence: number;
  reason: string;
  suggested_axes: {
    x?: string;
    y?: string | string[];
    color?: string;
    size?: string;
  };
}
```

---

### **Phase 2: UI Components (Week 2-3)**

#### **2.1 Domain Detection Badge Component**

```jsx
// components/DomainBadge.jsx

import React from 'react';
import { Badge, Tooltip } from '@/components/ui';

const DOMAIN_ICONS = {
  automotive: '🚗',
  healthcare: '🏥',
  ecommerce: '🛒',
  sales: '💰',
  finance: '💵',
  hr: '👥',
  sports: '⚽',
  unknown: '❓'
};

const DOMAIN_COLORS = {
  automotive: 'blue',
  healthcare: 'green',
  ecommerce: 'purple',
  sales: 'yellow',
  finance: 'emerald',
  hr: 'pink',
  sports: 'orange',
  unknown: 'gray'
};

export const DomainBadge = ({ domain, confidence, method }) => {
  const icon = DOMAIN_ICONS[domain] || DOMAIN_ICONS.unknown;
  const color = DOMAIN_COLORS[domain] || DOMAIN_COLORS.unknown;
  
  return (
    <Tooltip content={
      <div className="space-y-1">
        <p><strong>Domain:</strong> {domain}</p>
        <p><strong>Confidence:</strong> {(confidence * 100).toFixed(1)}%</p>
        <p><strong>Method:</strong> {method}</p>
      </div>
    }>
      <Badge variant={color} className="gap-1">
        <span>{icon}</span>
        <span>{domain}</span>
        <span className="text-xs opacity-75">
          {(confidence * 100).toFixed(0)}%
        </span>
      </Badge>
    </Tooltip>
  );
};
```

---

#### **2.2 Data Quality Indicator Component**

```jsx
// components/DataQualityIndicator.jsx

import React from 'react';
import { Progress, Card } from '@/components/ui';

const getQualityColor = (score) => {
  if (score >= 0.9) return 'green';
  if (score >= 0.7) return 'yellow';
  return 'red';
};

const getQualityLabel = (score) => {
  if (score >= 0.9) return 'Excellent';
  if (score >= 0.7) return 'Good';
  if (score >= 0.5) return 'Fair';
  return 'Poor';
};

export const DataQualityIndicator = ({ quality }) => {
  const { completeness, quality_score, duplicates_removed, missing_value_ratio } = quality;
  const color = getQualityColor(quality_score);
  const label = getQualityLabel(quality_score);
  
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">Data Quality</h3>
      
      <div className="space-y-3">
        <div>
          <div className="flex justify-between mb-1">
            <span className="text-sm">Overall Score: {label}</span>
            <span className="text-sm font-bold">{(quality_score * 100).toFixed(1)}%</span>
          </div>
          <Progress value={quality_score * 100} color={color} />
        </div>
        
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-600">Completeness:</span>
            <span className="font-semibold ml-1">{completeness.toFixed(1)}%</span>
          </div>
          <div>
            <span className="text-gray-600">Missing:</span>
            <span className="font-semibold ml-1">{(missing_value_ratio * 100).toFixed(1)}%</span>
          </div>
          <div className="col-span-2">
            <span className="text-gray-600">Duplicates Removed:</span>
            <span className="font-semibold ml-1">{duplicates_removed.toLocaleString()}</span>
          </div>
        </div>
      </div>
    </Card>
  );
};
```

---

#### **2.3 Chart Intelligence Panel Component**

```jsx
// components/ChartIntelligencePanel.jsx

import React, { useState } from 'react';
import { Card, Badge, Tooltip, Button, Collapsible } from '@/components/ui';
import { Info, ChevronDown, ChevronUp } from 'lucide-react';

const LAYER_DESCRIPTIONS = {
  statistical_rules: 'Objective rules based on data characteristics',
  domain_patterns: 'Industry-specific best practices',
  business_context: 'Audience-aware recommendations',
  visual_best_practices: 'Perceptual effectiveness (Cleveland hierarchy)',
  llm_validation: 'AI expert review',
  user_feedback: 'Learned from user preferences'
};

export const ChartIntelligencePanel = ({ intelligence }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const {
    confidence,
    layers_applied,
    expert_alignment,
    selection_reasoning,
    statistical_rules_matched,
    domain_patterns_matched
  } = intelligence;
  
  const getConfidenceColor = (score) => {
    if (score >= 0.9) return 'green';
    if (score >= 0.7) return 'blue';
    return 'yellow';
  };
  
  return (
    <Card className="p-4 border-2 border-blue-200 bg-blue-50">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 text-blue-600" />
          <h4 className="font-semibold text-sm">AI Chart Intelligence</h4>
        </div>
        <Badge variant={getConfidenceColor(confidence)}>
          {(confidence * 100).toFixed(0)}% Confident
        </Badge>
      </div>
      
      <p className="text-sm text-gray-700 mb-3">{selection_reasoning}</p>
      
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-gray-600">Expert Alignment:</span>
        <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div 
            className="h-full bg-green-500 transition-all"
            style={{ width: `${expert_alignment * 100}%` }}
          />
        </div>
        <span className="text-xs font-semibold">{(expert_alignment * 100).toFixed(0)}%</span>
      </div>
      
      <Collapsible
        open={isExpanded}
        onOpenChange={setIsExpanded}
        className="mt-3"
      >
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between text-xs"
        >
          <span>Intelligence Layers ({layers_applied.length}/6)</span>
          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </Button>
        
        {isExpanded && (
          <div className="mt-2 space-y-2">
            {layers_applied.map((layer) => (
              <Tooltip key={layer} content={LAYER_DESCRIPTIONS[layer]}>
                <div className="flex items-center gap-2 p-2 bg-white rounded text-xs">
                  <span className="text-green-600">✓</span>
                  <span className="capitalize">{layer.replace(/_/g, ' ')}</span>
                </div>
              </Tooltip>
            ))}
            
            {statistical_rules_matched && statistical_rules_matched.length > 0 && (
              <div className="mt-2 text-xs">
                <strong>Rules Matched:</strong>
                <ul className="list-disc list-inside ml-2">
                  {statistical_rules_matched.map((rule, i) => (
                    <li key={i}>{rule}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Collapsible>
    </Card>
  );
};
```

---

#### **2.4 Chart Insights Card Component**

```jsx
// components/ChartInsightsCard.jsx

import React from 'react';
import { Card, Badge } from '@/components/ui';
import { TrendingUp, AlertCircle, Info, Lightbulb } from 'lucide-react';

const PATTERN_ICONS = {
  trend: TrendingUp,
  comparison: AlertCircle,
  correlation: TrendingUp,
  composition: Info,
  intensity: AlertCircle
};

export const ChartInsightsCard = ({ insights }) => {
  const { summary, patterns, recommendations, confidence } = insights;
  
  return (
    <Card className="p-4 bg-gradient-to-br from-purple-50 to-blue-50">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-semibold text-sm flex items-center gap-2">
          <Lightbulb className="w-4 h-4 text-yellow-600" />
          AI Insights
        </h4>
        <Badge variant="purple">
          {(confidence * 100).toFixed(0)}% Confident
        </Badge>
      </div>
      
      <p className="text-sm text-gray-700 mb-4">{summary}</p>
      
      {patterns && patterns.length > 0 && (
        <div className="mb-4">
          <h5 className="text-xs font-semibold text-gray-600 mb-2">Detected Patterns:</h5>
          <div className="space-y-2">
            {patterns.map((pattern, index) => {
              const Icon = PATTERN_ICONS[pattern.type] || Info;
              return (
                <div key={index} className="flex items-start gap-2 text-xs bg-white p-2 rounded">
                  <Icon className="w-4 h-4 text-purple-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <div className="font-semibold capitalize">{pattern.pattern.replace(/_/g, ' ')}</div>
                    <div className="text-gray-600">{pattern.description}</div>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {(pattern.confidence * 100).toFixed(0)}%
                  </Badge>
                </div>
              );
            })}
          </div>
        </div>
      )}
      
      {recommendations && recommendations.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-gray-600 mb-2">Recommendations:</h5>
          <ul className="space-y-1">
            {recommendations.map((rec, index) => (
              <li key={index} className="text-xs flex items-start gap-2">
                <span className="text-green-600 flex-shrink-0">→</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};
```

---

#### **2.5 Upload Progress with 11 Stages**

```jsx
// components/UploadProgressEnhanced.jsx

import React from 'react';
import { Progress, Card } from '@/components/ui';
import { Check, Loader2 } from 'lucide-react';

const PIPELINE_STAGES = [
  { id: 1, name: 'Load & Validate', icon: '📂', progress: 5 },
  { id: 2, name: 'Data Cleaning', icon: '🧹', progress: 15 },
  { id: 3, name: 'Metadata Generation', icon: '📊', progress: 25 },
  { id: 4, name: 'Domain Detection', icon: '🔍', progress: 35 },
  { id: 5, name: 'Data Profiling', icon: '📈', progress: 45 },
  { id: 6, name: 'Statistical Analysis', icon: '📉', progress: 60 },
  { id: 7, name: 'Chart Recommendations', icon: '📊', progress: 70 },
  { id: 8, name: 'Quality Metrics', icon: '✅', progress: 80 },
  { id: 9, name: 'Consolidate Metadata', icon: '🔗', progress: 85 },
  { id: 10, name: 'Database Save', icon: '💾', progress: 90 },
  { id: 11, name: 'Vector Indexing', icon: '🔎', progress: 95 }
];

export const UploadProgressEnhanced = ({ progress, currentStage }) => {
  const currentStageInfo = PIPELINE_STAGES.find(s => s.name === currentStage) || PIPELINE_STAGES[0];
  
  return (
    <Card className="p-6">
      <h3 className="font-semibold mb-4">Processing Dataset</h3>
      
      <div className="mb-4">
        <Progress value={progress} className="h-2" />
        <p className="text-sm text-gray-600 mt-2">
          {progress}% Complete - {currentStageInfo.name}
        </p>
      </div>
      
      <div className="space-y-2">
        {PIPELINE_STAGES.map((stage) => {
          const isComplete = progress >= stage.progress;
          const isCurrent = currentStageInfo.id === stage.id;
          
          return (
            <div
              key={stage.id}
              className={`flex items-center gap-3 p-2 rounded transition-all ${
                isCurrent ? 'bg-blue-50 border border-blue-200' : ''
              }`}
            >
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                isComplete ? 'bg-green-500' : isCurrent ? 'bg-blue-500' : 'bg-gray-200'
              }`}>
                {isComplete ? (
                  <Check className="w-4 h-4 text-white" />
                ) : isCurrent ? (
                  <Loader2 className="w-4 h-4 text-white animate-spin" />
                ) : (
                  <span className="text-xs text-gray-500">{stage.id}</span>
                )}
              </div>
              
              <span className="text-lg">{stage.icon}</span>
              
              <div className="flex-1">
                <div className={`text-sm font-medium ${
                  isCurrent ? 'text-blue-700' : isComplete ? 'text-gray-700' : 'text-gray-400'
                }`}>
                  {stage.name}
                </div>
              </div>
              
              {isComplete && !isCurrent && (
                <span className="text-xs text-green-600">✓</span>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
```

---

### **Phase 3: Page/View Updates (Week 3-4)**

#### **3.1 Dataset Detail Page Enhancement**

```jsx
// pages/DatasetDetail.jsx - Key Changes

import { DomainBadge } from '@/components/DomainBadge';
import { DataQualityIndicator } from '@/components/DataQualityIndicator';
import { datasetAPI } from '@/services/api';

const DatasetDetail = ({ datasetId }) => {
  const [dataset, setDataset] = useState(null);
  const [profiling, setProfiling] = useState(null);
  
  useEffect(() => {
    // Load dataset with enhanced metadata
    datasetAPI.getDataset(datasetId).then(res => {
      setDataset(res.data);
    });
    
    // Load profiling results
    datasetAPI.getDataProfiling(datasetId).then(res => {
      setProfiling(res.data);
    });
  }, [datasetId]);
  
  if (!dataset) return <Loader />;
  
  const { metadata } = dataset;
  const { dataset_overview, data_quality } = metadata;
  
  return (
    <div className="space-y-6">
      {/* Header with Domain Badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{dataset.name}</h1>
          <DomainBadge 
            domain={dataset_overview.domain}
            confidence={dataset_overview.domain_confidence}
            method={dataset_overview.domain_detection_method}
          />
        </div>
      </div>
      
      {/* Data Quality Indicator */}
      <DataQualityIndicator quality={data_quality} />
      
      {/* Profiling Results */}
      {profiling && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Data Profile</h2>
          <DataProfileViewer profiling={profiling} />
        </Card>
      )}
      
      {/* Rest of the page... */}
    </div>
  );
};
```

---

#### **3.2 Dashboard Page with Chart Intelligence**

```jsx
// pages/Dashboard.jsx - Key Changes

import { ChartIntelligencePanel } from '@/components/ChartIntelligencePanel';
import { ChartInsightsCard } from '@/components/ChartInsightsCard';
import { chartIntelligenceAPI, chartInsightsAPI } from '@/services/api';

const Dashboard = ({ datasetId }) => {
  const [intelligentCharts, setIntelligentCharts] = useState([]);
  
  useEffect(() => {
    // Load AI-selected charts with intelligence metadata
    chartIntelligenceAPI.getIntelligentCharts(datasetId).then(res => {
      setIntelligentCharts(res.data.charts);
    });
  }, [datasetId]);
  
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">AI-Powered Dashboard</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {intelligentCharts.map((chart, index) => (
          <div key={index} className="space-y-4">
            {/* Chart Intelligence Panel */}
            <ChartIntelligencePanel intelligence={chart.intelligence} />
            
            {/* Chart Visualization */}
            <Card className="p-4">
              <PlotlyChart data={chart.data} config={chart.config} />
            </Card>
            
            {/* Chart Insights */}
            {chart.insights && (
              <ChartInsightsCard insights={chart.insights} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
```

---

## 📋 Implementation Checklist

### **Week 1: API Layer**
- [ ] Update `api.js` with new endpoints
- [ ] Create TypeScript type definitions
- [ ] Add error handling for new response structures
- [ ] Write API integration tests
- [ ] Create mock data for development

### **Week 2: Core Components**
- [ ] Build `DomainBadge` component
- [ ] Build `DataQualityIndicator` component
- [ ] Build `ChartIntelligencePanel` component
- [ ] Build `ChartInsightsCard` component
- [ ] Build `UploadProgressEnhanced` component
- [ ] Build `DataProfileViewer` component

### **Week 3: Page Integration**
- [ ] Update Dataset Detail page
- [ ] Update Dashboard page
- [ ] Update Dataset List page (add domain badges)
- [ ] Update Upload page (11-stage progress)
- [ ] Add Chart Intelligence section

### **Week 4: Testing & Polish**
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] UI/UX refinement
- [ ] Documentation updates
- [ ] User acceptance testing

---

## 🚀 Quick Start Migration

### **Minimal Changes to Get Connected (1-2 Hours):**

1. **Update Dataset Response Handler:**
```javascript
// services/api.js
const parseDatasetResponse = (response) => {
  const data = response.data;
  
  // Handle both old and new structures for backward compatibility
  return {
    ...data,
    row_count: data.metadata?.dataset_overview?.total_rows || data.metadata?.row_count || 0,
    column_count: data.metadata?.dataset_overview?.total_columns || data.metadata?.column_count || 0,
    domain: data.metadata?.dataset_overview?.domain,
    quality_score: data.metadata?.data_quality?.quality_score
  };
};
```

2. **Add Domain Badge to Dataset Cards:**
```jsx
// components/DatasetCard.jsx
{dataset.domain && (
  <Badge>{dataset.domain}</Badge>
)}
```

3. **Show Quality Score:**
```jsx
{dataset.quality_score && (
  <span>Quality: {(dataset.quality_score * 100).toFixed(0)}%</span>
)}
```

**This gets you 80% functional in < 2 hours!**

---

## 🎯 Success Metrics

- ✅ All API calls return valid responses
- ✅ Domain detection displayed on all datasets
- ✅ Data quality indicators visible
- ✅ Chart intelligence panel shows reasoning
- ✅ Chart insights display patterns and recommendations
- ✅ Upload progress shows all 11 stages
- ✅ No console errors from API mismatches
- ✅ 90%+ test coverage for new components

---

## 📞 Support

**Questions?** Check:
1. Backend API docs: `http://localhost:8000/docs`
2. Chart intelligence explainer: `CHART_INTELLIGENCE_EXPLAINED.md`
3. Production pipeline docs: `PRODUCTION_PIPELINE_SUMMARY.md`

---

**Next Action:** Choose your approach:
- **Fast Track (2 hours)**: Implement minimal changes above
- **Full Implementation (4 weeks)**: Follow the complete phase plan
