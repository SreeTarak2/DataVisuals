import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('datasage-token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid, redirect to login
      localStorage.removeItem('datasage-token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Dataset API calls
export const datasetAPI = {
  // Get all datasets for the user
  getDatasets: () => api.get('/datasets'),
  
  // Get specific dataset
  getDataset: (id) => api.get(`/datasets/${id}`),
  
  // Upload new dataset
  uploadDataset: (formData) => api.post('/datasets/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  }),
  
  // Delete dataset
  deleteDataset: (id) => {
    if (!id) {
      return Promise.reject(new Error('Dataset ID is required'));
    }
    console.log('API: Deleting dataset with ID:', id);
    return api.delete(`/datasets/${id}`);
  },
  
  // Get dataset data with pagination
  getDatasetData: (id, page = 1, pageSize = 100) => 
    api.get(`/datasets/${id}/data?page=${page}&page_size=${pageSize}`),
  
  // Get dataset summary
  getDatasetSummary: (id) => api.get(`/datasets/${id}/summary`),
  
  // Get dataset columns with types
  getDatasetColumns: (id) => api.get(`/datasets/${id}/columns`),
  
  // Reprocess dataset
  reprocessDataset: (id) => {
    if (!id) {
      return Promise.reject(new Error('Dataset ID is required'));
    }
    console.log('API: Reprocessing dataset with ID:', id);
    return api.post(`/datasets/${id}/reprocess`);
  },
};

// AI API calls
export const aiAPI = {
  // Process chat message
  processChat: (datasetId, message, conversationId = null) => 
    api.post(`/datasets/${datasetId}/chat`, {
      message,
      conversation_id: conversationId
    }),
  
  // Generate AI dashboard
  generateDashboard: (datasetId, forceRegenerate = false) => 
    api.post(`/ai/${datasetId}/generate-dashboard?force_regenerate=${forceRegenerate}`),
  
  // Design intelligent dashboard
  designDashboard: (datasetId, designPreference) => 
    api.post(`/ai/${datasetId}/design-dashboard`, { design_preference: designPreference }),
  
  // Get design patterns
  getDesignPatterns: () => api.get('/ai/design-patterns'),
  
  // Generate QUIS insights
  generateQuisInsights: (datasetMetadata, datasetName) => 
    api.post('/ai/generate-quis-insights', {
      dataset_metadata: datasetMetadata,
      dataset_name: datasetName
    }),
};

// Chat API calls
export const chatAPI = {
  // Get all conversations
  getConversations: () => api.get('/chat/conversations'),
  
  // Get specific conversation
  getConversation: (conversationId) => api.get(`/chat/conversations/${conversationId}`),
  
  // Delete conversation
  deleteConversation: (conversationId) => api.delete(`/chat/conversations/${conversationId}`),
};

// Chart Insights API calls
export const chartInsightsAPI = {
  // Get cached charts for a dataset
  getCachedCharts: (datasetId) => api.get(`/datasets/${datasetId}/cached-charts`),
  
  // Generate insights for a specific chart
  generateChartInsight: (datasetId, chartConfig, chartData) => 
    api.post(`/datasets/${datasetId}/generate-chart-insight`, {
      chart_config: chartConfig,
      chart_data: chartData
    }),
};

// Chart API calls
export const chartAPI = {
  // Render chart preview
  renderChartPreview: (chartConfig, datasetId) => 
    api.post('/charts/render-preview', {
      chart_config: chartConfig,
      dataset_id: datasetId
    }),
  
  // Generate analytics chart with aggregation
  generateChart: (datasetId, chartType, xAxis, yAxis, aggregation = 'sum') => 
    api.post('/analytics/generate-chart', {
      dataset_id: datasetId,
      chart_type: chartType,
      x_axis: xAxis,
      y_axis: yAxis,
      aggregation: aggregation
    }),
};

// Analysis API calls
export const analysisAPI = {
  // Run analysis
  runAnalysis: (datasetId, analysisType) => 
    api.post('/analysis/run', {
      dataset_id: datasetId,
      analysis_type: analysisType
    }),
  
  // Run QUIS analysis
  runQuisAnalysis: (datasetId, maxDepth = 2) => 
    api.post('/analysis/run-quis', {
      dataset_id: datasetId,
      max_depth: maxDepth
    }),
};

// Drill-down API calls
export const drilldownAPI = {
  // Get hierarchies
  getHierarchies: (datasetId) => api.get(`/datasets/${datasetId}/hierarchies`),
  
  // Execute drill-down
  executeDrillDown: (datasetId, hierarchy, currentLevel, filters = null) => 
    api.post(`/datasets/${datasetId}/drill-down`, {
      hierarchy,
      current_level: currentLevel,
      filters
    }),
};

// Vector database API calls
export const vectorAPI = {
  // Index dataset to vector DB
  indexDataset: (datasetId) => api.post(`/vector/datasets/${datasetId}/index`),
  
  // Search similar datasets
  searchSimilarDatasets: (query, limit = 5) => 
    api.post('/vector/search/datasets', { query, limit }),
  
  // Enhanced RAG search
  enhancedRagSearch: (datasetId, query) => 
    api.post(`/vector/rag/${datasetId}/enhanced`, { query }),
  
  // Get vector DB stats
  getVectorStats: () => api.get('/vector/stats'),
  
  // Reset vector DB
  resetVectorDb: () => api.delete('/vector/reset'),
};

// Background task API calls
export const taskAPI = {
  // Get task status
  getTaskStatus: (taskId) => api.get(`/tasks/${taskId}/status`),
};

export default api;
