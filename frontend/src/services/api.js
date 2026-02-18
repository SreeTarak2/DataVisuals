import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Helper to get auth token from Zustand persisted store
// Checks both localStorage (Remember Me ON) and sessionStorage (Remember Me OFF)
export const getAuthToken = () => {
  // Try localStorage first, then sessionStorage
  const authData = localStorage.getItem('datasage-auth') || sessionStorage.getItem('datasage-auth');
  if (authData) {
    try {
      const parsed = JSON.parse(authData);
      return parsed?.state?.token || null;
    } catch (e) {
      console.warn('Failed to parse auth data from storage');
    }
  }
  return null;
};

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
    const token = getAuthToken();
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
      // Token expired or invalid, clear auth from both storages and redirect
      localStorage.removeItem('datasage-auth');
      sessionStorage.removeItem('datasage-auth');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Dataset API calls
export const datasetAPI = {
  // Get all datasets for the user
  getDatasets: () => api.get('/datasets/'),

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

  // Trigger Deep Analysis (QUIS)
  analyzeDataset: (id, query = null, noveltyThreshold = 0.35) =>
    api.post(`/datasets/${id}/analyze`, {
      query,
      novelty_threshold: noveltyThreshold
    }),
};

// AI API calls
export const aiAPI = {
  // Process chat message
  processChat: (datasetId, message, conversationId = null) =>
    api.post(`/datasets/${datasetId}/chat`, {
      message,
      conversation_id: conversationId
    }),

  // Generate AI dashboard (legacy)
  generateDashboard: (datasetId, forceRegenerate = false) =>
    api.post(`/ai/${datasetId}/generate-dashboard?force_regenerate=${forceRegenerate}`),

  // Design intelligent dashboard (new AI Designer)
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
  // Render chart with full configuration
  renderChart: (datasetId, chartType, fields, aggregation = 'sum', options = {}) =>
    api.post('/charts/render', {
      dataset_id: datasetId,
      chart_type: chartType,
      fields: fields,
      aggregation: aggregation,
      title: options.title || `${fields[1] || 'Value'} by ${fields[0] || 'Category'}`,
      include_insights: options.includeInsights || false,
      filters: options.filters || null,
      group_by: options.groupBy || null
    }),

  // Legacy alias for backward compatibility
  generateChart: (datasetId, chartType, xAxis, yAxis, aggregation = 'sum') =>
    api.post('/charts/render', {
      dataset_id: datasetId,
      chart_type: chartType,
      fields: [xAxis, yAxis],
      aggregation: aggregation,
      title: `${yAxis} by ${xAxis}`
    }),

  // Get AI-powered chart recommendations for a dataset
  getRecommendations: (datasetId) =>
    api.get(`/charts/recommendations?dataset_id=${datasetId}`),

  // Get detailed insights for a chart
  getInsights: (chartConfig, chartData, datasetId) =>
    api.post('/charts/insights', {
      chart_config: chartConfig,
      chart_data: chartData,
      dataset_id: datasetId
    }),

  // Save chart to user's dashboard
  saveChart: (datasetId, chartConfig, title) =>
    api.post('/charts/dashboard/save', {
      dataset_id: datasetId,
      chart_config: chartConfig,
      title: title
    }),

  // List saved charts (optionally filter by dataset)
  listSavedCharts: (datasetId = null) =>
    api.get('/charts/dashboard/list' + (datasetId ? `?dataset_id=${datasetId}` : '')),

  // Render chart preview (for quick previews without full rendering)
  renderChartPreview: (chartConfig, datasetId) =>
    api.post('/charts/render-preview', {
      chart_config: chartConfig,
      dataset_id: datasetId
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

// Dashboard API calls
export const dashboardAPI = {
  // Get dashboard overview with KPIs
  getDashboardOverview: (datasetId) => api.get(`/dashboard/${datasetId}/overview`),

  // Get dashboard charts
  getDashboardCharts: (datasetId) => api.get(`/dashboard/${datasetId}/charts`),

  // Get AI dashboard layout
  getAiDashboardLayout: (datasetId) => api.get(`/dashboard/${datasetId}/ai-layout`),

  // Get dashboard insights
  getDashboardInsights: (datasetId) => api.get(`/dashboard/${datasetId}/insights`),
};

export default api;
