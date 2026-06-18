import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const USER_SCOPED_STORAGE_KEYS = ['dataset-storage', 'signal-chat-store', 'chat-history-storage'];

// Helper to get auth token from Zustand persisted store
// Checks both localStorage (Remember Me ON) and sessionStorage (Remember Me OFF)
export const getAuthToken = () => {
  // Try localStorage first, then sessionStorage
  const authData = localStorage.getItem('signal-auth') || sessionStorage.getItem('signal-auth');
  if (authData) {
    try {
      const parsed = JSON.parse(authData);
      return parsed?.state?.token || null;
    } catch {
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

// Track retries per request config to avoid infinite retry loops
const RETRYABLE_STATUSES = [503, 429, 502, 504];
const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 1000; // 1 second

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    const status = error.response?.status;

    // Retry on transient server errors (503 Service Unavailable, 429 Too Many Requests, etc.)
    if (status && RETRYABLE_STATUSES.includes(status) && !config._retryCount) {
      config._retryCount = 0;
    }

    if (status && RETRYABLE_STATUSES.includes(status) && config._retryCount < MAX_RETRIES) {
      config._retryCount = (config._retryCount || 0) + 1;
      const delay = BASE_RETRY_DELAY * Math.pow(2, config._retryCount - 1); // 1s, 2s, 4s
      console.warn(
        `API ${status} on ${config.url} — retrying (${config._retryCount}/${MAX_RETRIES}) after ${delay}ms`
      );
      await new Promise((resolve) => setTimeout(resolve, delay));
      return api(config);
    }

    if (status === 401) {
      // Token expired or invalid, clear auth from both storages and redirect
      localStorage.removeItem('signal-auth');
      sessionStorage.removeItem('signal-auth');
      USER_SCOPED_STORAGE_KEYS.forEach((key) => {
        localStorage.removeItem(key);
        sessionStorage.removeItem(key);
      });
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

  // Update KPI configuration (persists edited column/aggregation/format/icon)
  updateKpi: (id, kpiId, updates) =>
    api.put(`/datasets/${id}/kpis/${kpiId}`, updates),

  // Get persisted KPI overrides for the current user
  getKpiOverrides: (id) =>
    api.get(`/datasets/${id}/kpis/overrides`),

  // Get per-stage pipeline execution history
  getDatasetStages: (id) => api.get(`/datasets/${id}/stages`),

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

  // Intelligent KPI cards — data-science-grade, pre-computed during upload
  // refresh=true forces regeneration even when cached
  getKpis: (id, refresh = false) =>
    api.get(`/datasets/${id}/kpis${refresh ? '?refresh=true' : ''}`),

  // Get unified profile + intelligence data for the Data Profile page
  getProfile: (id) => api.get(`/datasets/${id}/profile`),

  // Get Dataset Understanding Report — primary object, participants, evidence traces, ambiguity
  getUnderstanding: (id) => api.get(`/datasets/${id}/understanding`),

  // Import Google Sheets by URL
  importGoogleSheets: (sheetUrl) => api.post('/datasets/import-gsheet', { url: sheetUrl }),

  // Re-import / refresh a Google Sheets dataset in-place
  reimportGoogleSheets: (datasetId) => api.post(`/datasets/${datasetId}/reimport-gsheet`),
};

// Database Connection API calls
export const databaseAPI = {
  // Test credentials without saving
  testConnection: (config) => api.post('/databases/test', config),

  // Save a verified connection (encrypts password server-side)
  saveConnection: (data) => api.post('/databases/', data),

  // List all saved connections for current user
  listConnections: () => api.get('/databases/'),

  // List tables inside a saved connection (cached 5 min server-side)
  getTables: (connId) => api.get(`/databases/${connId}/tables`),

  // Get foreign key constraints from a saved connection
  getForeignKeys: (connId, refresh = false) =>
    api.get(`/databases/${connId}/foreign-keys${refresh ? '?refresh=true' : ''}`),

  // Extract a table → creates a dataset + fires Celery pipeline
  extractTable: (connId, body) => api.post(`/databases/${connId}/extract`, body),

  // Remove a saved connection
  deleteConnection: (connId) => api.delete(`/databases/${connId}`),
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

  // Upload an image for embedding in chat messages
  uploadChatImage: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/chat/attachments', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
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
      include_insights: options.include_insights !== undefined ? options.include_insights : true,
      filters: options.filters || null,
      group_by: options.groupBy || null,
      from: options.from || null,
      to: options.to || null,
      granularity: options.granularity || 'day',
      limit: options.limit || 10000,
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

  // Explain a chart (lazy load explanation)
  explainChart: (datasetId, chartKey, chartConfig) =>
    api.post('/charts/explain', {
      dataset_id: datasetId,
      chart_key: chartKey,
      chart_config: chartConfig
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

// Insights API calls (dedicated insights page)
export const insightsAPI = {
  // Get comprehensive insights for a dataset
  getComprehensiveInsights: (datasetId, forceRefresh = false, config = {}, filters = null) => {
    const params = new URLSearchParams();
    if (forceRefresh) params.set('force_refresh', 'true');
    if (filters) params.set('filters', filters);
    const qs = params.toString();
    return api.get(`/insights/${datasetId}${qs ? `?${qs}` : ''}`, config);
  },
};

// Reports API calls (PDF generation)
export const reportsAPI = {
  // Get PDF report for a dataset
  downloadPDF: (datasetId, includeCharts = true) => {
    const params = new URLSearchParams();
    if (!includeCharts) params.set('include_charts', 'false');
    const qs = params.toString();
    return `${API_URL}/reports/${datasetId}/pdf${qs ? `?${qs}` : ''}`;
  },

  // Preview report as HTML
  previewReport: (datasetId, includeCharts = true) => {
    const params = new URLSearchParams();
    params.set('preview', 'true');
    if (!includeCharts) params.set('include_charts', 'false');
    const qs = params.toString();
    return `${API_URL}/reports/${datasetId}/pdf?${qs}`;
  },

  // Get report metadata/info
  getReportInfo: (datasetId) => api.get(`/reports/${datasetId}/report-info`),
};

// Agentic AI & Belief Store API calls
export const agenticAPI = {
  // Stream EDA pipeline via Server-Sent Events (fetch + ReadableStream)
  // Returns a native fetch Response — caller reads body with getReader()
  streamAnalysis: (datasetId, question = 'Give me a full exploratory analysis of this dataset') => {
    const token = getAuthToken();
    return fetch(`${API_URL}/agentic/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ dataset_id: datasetId, question }),
    });
  },

  // Submit feedback on an insight (feeds the Belief Store)
  submitFeedback: ({ insight_text, feedback_type, dataset_id = null }) =>
    api.post('/agentic/feedback', { insight_text, feedback_type, dataset_id }),

  // List user beliefs
  listBeliefs: (limit = 50) =>
    api.get(`/agentic/beliefs?limit=${limit}`),

  // Delete a specific belief
  deleteBelief: (beliefId) =>
    api.delete(`/agentic/beliefs/${beliefId}`),

  // Clear all beliefs (reset personalization)
  clearBeliefs: () =>
    api.delete('/agentic/beliefs'),
};

// Belief/Business Rules API
export const beliefAPI = {
  list: (datasetId) => api.get(`/beliefs/${datasetId}`),
  create: (data) => api.post('/beliefs/', data),
  update: (beliefId, data) => api.patch(`/beliefs/${beliefId}`, data),
  delete: (beliefId) => api.delete(`/beliefs/${beliefId}`),
};

// Privacy API
export const privacyAPI = {
  // Get global privacy settings
  getGlobalSettings: () => api.get('/privacy/settings'),

  // Update global privacy settings
  updateGlobalSettings: (updates) => api.put('/privacy/settings', updates),

  // Get dataset-specific privacy settings
  getDatasetSettings: (datasetId) => api.get(`/privacy/settings/${datasetId}`),

  // Update dataset-specific privacy settings
  updateDatasetSettings: (datasetId, updates) => api.put(`/privacy/settings/${datasetId}`, updates),

  // Scan dataset for PII
  scanForPII: (datasetId) => api.post(`/privacy/detect-pii/${datasetId}`),

  // Generate privacy preview (dry-run)
  generatePreview: (datasetId) => api.post(`/privacy/preview/${datasetId}`),

  // Manage private columns
  managePrivateColumn: (datasetId, action, columnName) =>
    api.post(`/privacy/settings/${datasetId}/columns`, { action, column_name: columnName }),

  // Get audit log
  getAuditLog: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return api.get(`/privacy/audit-log${query ? `?${query}` : ''}`);
  },

  // Get audit stats
  getAuditStats: (days = 30) => api.get(`/privacy/audit-log/stats?days=${days}`),

  // Export privacy data (GDPR)
  exportPrivacyData: () => api.get('/privacy/export'),

  // Dismiss privacy notice
  dismissNotice: (dismissed = true) => api.post('/privacy/notice-dismissal', { dismissed }),
};

export default api;
