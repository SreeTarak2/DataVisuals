import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Create axios instance with default config.
// `withCredentials: true` ensures the HttpOnly auth cookie is sent on every
// request, including cross-origin calls when frontend and backend are on
// different origins (Phase 1+ cookie-based auth).
const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include CSRF protection header.
// Auth is handled by the HttpOnly cookie (auto-sent by browser).
// The X-CSRF-Protection header is defense-in-depth against CSRF attacks.
// X-Device-Name lets the backend label this device in the session list.
let deviceNameCache = null;
const getDeviceName = () => {
  if (deviceNameCache) return deviceNameCache;
  try {
    const ua = navigator.userAgent || '';
    const browser = /Edg\//.test(ua) ? 'Edge'
      : /Chrome\//.test(ua) ? 'Chrome'
      : /Firefox\//.test(ua) ? 'Firefox'
      : /Safari\//.test(ua) ? 'Safari'
      : 'Browser';
    const os = /Windows/.test(ua) ? 'Windows'
      : /Mac OS X/.test(ua) ? 'macOS'
      : /Android/.test(ua) ? 'Android'
      : /iPhone|iPad/.test(ua) ? 'iOS'
      : /Linux/.test(ua) ? 'Linux'
      : 'Device';
    deviceNameCache = `${browser} on ${os}`;
  } catch (e) {
    deviceNameCache = 'Web browser';
  }
  return deviceNameCache;
};

api.interceptors.request.use(
  (config) => {
    config.headers['X-CSRF-Protection'] = '1';
    config.headers['X-Device-Name'] = getDeviceName();
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Single-flight refresh: concurrent 401s share one /auth/refresh call.
// The refresh token lives in an HttpOnly cookie (path-scoped to /api/auth),
// so the browser sends it automatically — no JS access needed.
let refreshPromise = null;
const refreshAccessToken = () => {
  if (!refreshPromise) {
    refreshPromise = api
      .post('/auth/refresh')
      .then((res) => res.data.access_token)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
};

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

    // ── 401: try refresh-token rotation once, then retry the request ──────
    // Short-lived access tokens mean 401s are routine (not just logouts).
    // With a valid refresh cookie this is invisible to the user; without
    // one, we fall through to the auto-logout handling below.
    if (status === 401 && config.url && !config.url.includes('/auth/refresh') && !config._authRetried) {
      try {
        await refreshAccessToken();
        config._authRetried = true;
        return api(config);
      } catch (refreshError) {
        // Session is truly dead — fall through to logout handling
      }
    }

    // ── 401: Session expired or invalid → auto-logout mid-session ──────────
    // Uses lazy store access (not module-level import) to avoid circular
    // dependency: authStore imports api.js → api.js must NOT import authStore
    // at module level.
    //
    // The redirect is handled by ProtectedRoute (React Router <Navigate>):
    //   logout() sets user=null → ProtectedRoute detects !isAuthenticated
    //   → <Navigate to="/login" replace /> (no full page reload)
    //
    // Skip auth endpoints to prevent recursion:
    //   - /auth/me   → handled by verifyToken() in authStore (sets user=null)
    //   - /auth/logout → logout() already handles failure gracefully
    if (status === 401 && config.url && !config.url.includes("/auth/me") && !config.url.includes("/auth/logout")) {
      try {
        const { default: useAuthStore } = await import("../store/authStore.jsx");
        const store = useAuthStore.getState();
        if (store.user) {
          console.warn(`API 401 on ${config.url} — session expired, logging out`);
          store.logout();
        }
      } catch (importErr) {
        console.error("Failed to auto-logout on 401:", importErr);
      }
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

  // Upload new dataset (onProgress optional — real upload % via axios onUploadProgress)
  uploadDataset: (formData, onProgress) => api.post('/datasets/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...(typeof onProgress === 'function' ? {
      onUploadProgress: (e) => {
        if (e.total) onProgress(Math.min(Math.round((e.loaded / e.total) * 100), 100));
      },
    } : {}),
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

  // Get dataset preview (small row sample for fast table preview)
  getDatasetPreview: (id, params = {}) => {
    const query = new URLSearchParams();
    if (params.limit) query.set('limit', String(params.limit));
    const qs = query.toString();
    return api.get(`/datasets/${id}/preview${qs ? `?${qs}` : ''}`);
  },

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

  // Intelligent KPI cards — data-science-grade, pre-computed during upload.
  // refresh=true forces regeneration even when cached.
  // persona (explorer|ceo|analyst|marketing|ops) re-generates the KPI
  // selection for that audience (regenerates server-side).
  getKpis: (id, refresh = false, persona = null) => {
    const params = new URLSearchParams();
    if (refresh) params.set('refresh', 'true');
    if (persona) params.set('persona', persona);
    const qs = params.toString();
    return api.get(`/datasets/${id}/kpis${qs ? `?${qs}` : ''}`);
  },



  // Import Google Sheets by URL
  importGoogleSheets: (sheetUrl) => api.post('/datasets/import-gsheet', { url: sheetUrl }),

  // Re-import / refresh a Google Sheets dataset in-place
  reimportGoogleSheets: (datasetId) => api.post(`/datasets/${datasetId}/reimport-gsheet`),

  // ── Column Cleaning Manifest (Stage 1.5 Normalization) ──

  // Get the column name cleaning manifest for review
  getCleaningManifest: (id) => api.get(`/datasets/${id}/cleaning-manifest`),

  // Approve or reject a single cleaning action
  approveCleaningAction: (id, actionIndex, approved) =>
    api.post(`/datasets/${id}/cleaning-action`, {
      action_index: actionIndex,
      approved: approved,
    }),

  // Bulk approve or reject all pending cleaning actions
  applyAllCleaning: (id, approved, actionIndices = null) =>
    api.post(`/datasets/${id}/apply-cleaning`, {
      approved: approved,
      action_indices: actionIndices,
    }),
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

  // Design intelligent dashboard with column selection and user intent
  designDashboardWithBriefing: (datasetId, { selectedColumns, userIntent, forceRegenerate = true }) =>
    api.post(`/ai/${datasetId}/design-dashboard`, {
      selected_columns: selectedColumns,
      user_intent: userIntent,
      force_regenerate: forceRegenerate,
      redesign_mode: 'full',
    }),

  // LLM-powered column suggestion from user intent
  suggestColumns: (datasetId, userIntent, maxColumns = 20) =>
    api.post(`/ai/${datasetId}/suggest-columns`, {
      user_intent: userIntent,
      max_columns: maxColumns,
    }),

  // Get design patterns
  getDesignPatterns: () => api.get('/ai/design-patterns'),

  // Generate QUIS insights
  generateQuisInsights: (datasetMetadata, datasetName) =>
    api.post('/ai/generate-quis-insights', {
      dataset_metadata: datasetMetadata,
      dataset_name: datasetName
    }),
};

// Auth API calls (session management & refresh)
export const authAPI = {
  // Rotate the refresh cookie + mint a fresh access token
  refresh: () => api.post('/auth/refresh'),

  // Revoke every other device's session (keeps this device logged in)
  logoutAll: () => api.post('/auth/logout-all'),

  // List active sessions (devices) for the Settings UI
  listSessions: () => api.get('/auth/sessions'),

  // Revoke a specific device session
  revokeSession: (sessionId) => api.delete(`/auth/sessions/${sessionId}`),
};

// Notification API calls (in-app job notification inbox)
export const notificationAPI = {
  // List notifications, newest first
  getNotifications: (limit = 30) => api.get('/notifications', { params: { limit, include_read: true } }),

  // Unread count for the bell badge
  getUnreadCount: () => api.get('/notifications/unread-count'),

  // Mark a single notification as read
  markRead: (id) => api.post(`/notifications/${id}/read`),

  // Mark all notifications as read
  markAllRead: () => api.post('/notifications/read-all'),
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

// ──────────────────────────────────────────────
// SQL Editor API calls — Async Execution with Polling
// ──────────────────────────────────────────────
export const sqlAPI = {
  // Execute arbitrary SQL against a dataset (async with polling)
  // Accepts optional AbortSignal to cancel in-flight requests on unmount / navigate
  executeSql: async (datasetId, sql, limit = 1000, signal = null) => {
    // Helper: return cancelled result if signal was aborted
    const cancelled = (queryId = null) => ({
      data: {
        success: false,
        error: 'Query cancelled',
        query_id: queryId,
      },
    });

    // Bail immediately if already aborted before first request
    if (signal?.aborted) {
      return cancelled();
    }

    // Pass signal to axios when provided (lets axios throw CanceledError on abort)
    const req = signal ? { signal } : {};

    // 1. Submit the query — returns query_id immediately
    let submitRes;
    try {
      submitRes = await api.post('/v2/query/execute', {
        dataset_id: datasetId,
        sql,
        limit,
      }, req);
    } catch (submitErr) {
      if (signal?.aborted) return cancelled();
      throw submitErr;
    }

    const { query_id, status: initialStatus } = submitRes.data;

    // 2. Fast-path: query already completed (trivial SQL)
    if (initialStatus === 'completed' || initialStatus === 'failed') {
      return submitRes;
    }

    // 3. Poll with exponential backoff — check signal.aborted after each await
    const delays = [200, 500, 1000, 2000, 3000, 5000, 8000, 10000];
    for (const delay of delays) {
      if (signal?.aborted) return cancelled(query_id);

      await new Promise((r) => setTimeout(r, delay));

      if (signal?.aborted) return cancelled(query_id);

      try {
        const statusRes = await api.get(`/v2/query/${query_id}/status`, req);
        const s = statusRes.data.status;

        if (s === 'completed') {
          // Fetch the actual results
          const resultsRes = await api.get(`/v2/query/${query_id}/results`, req);
          // Rewrap to match the original response shape
          return {
            ...submitRes,
            data: {
              success: true,
              columns: resultsRes.data.columns || [],
              data: resultsRes.data.rows || [],
              row_count: resultsRes.data.total_rows || 0,
              execution_time_ms: resultsRes.data.execution_time_ms || 0,
              query_id,
            },
          };
        }

        if (s === 'failed') {
          return {
            ...submitRes,
            data: {
              success: false,
              error: statusRes.data.error || 'Query failed',
              query_id,
            },
          };
        }

        if (s === 'cancelled') {
          return {
            ...submitRes,
            data: {
              success: false,
              error: 'Query was cancelled',
              query_id,
            },
          };
        }

        // Still "queued" or "running" — keep polling
      } catch (pollErr) {
        // Aborted requests throw CanceledError from axios — handle gracefully
        if (signal?.aborted) return cancelled(query_id);
        console.warn('Poll error (non-fatal):', pollErr);
        // Continue polling unless it's a 404 or 403
        if (pollErr?.response?.status === 404 || pollErr?.response?.status === 403) {
          throw pollErr;
        }
      }
    }

    // 4. Final fallback: try a blocking fetch with longer timeout
    try {
      const resultsRes = await api.get(`/v2/query/${query_id}/results`, {
        ...req,
        timeout: 60000,
      });
      return {
        ...submitRes,
        data: {
          success: true,
          columns: resultsRes.data.columns || [],
          data: resultsRes.data.rows || [],
          row_count: resultsRes.data.total_rows || 0,
          execution_time_ms: resultsRes.data.execution_time_ms || 0,
          query_id,
        },
      };
    } catch {
      if (signal?.aborted) return cancelled(query_id);
      return {
        ...submitRes,
        data: {
          success: false,
          error: 'Query timed out after maximum polling duration',
          query_id,
        },
      };
    }
  },

  // Check query status (for manual polling)
  getQueryStatus: (queryId) =>
    api.get(`/v2/query/${queryId}/status`),

  // Get paginated query results
  getQueryResults: (queryId, offset = 0, limit = 100) =>
    api.get(`/v2/query/${queryId}/results?offset=${offset}&limit=${limit}`),

  // Cancel a running query
  cancelQuery: (queryId) =>
    api.post(`/v2/query/${queryId}/cancel`),

  // Get query history for the current user
  getQueryHistory: (datasetId = null, limit = 50, offset = 0) => {
    const params = new URLSearchParams();
    if (datasetId) params.set('dataset_id', datasetId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    return api.get(`/v2/query/history?${params.toString()}`);
  },

  // Delete a query log entry
  deleteQuery: (queryId) =>
    api.delete(`/v2/query/${queryId}`),

  // Generate SQL from natural language description (via semantic layer)
  generateSql: (datasetId, query, returnRaw = true) =>
    api.post('/v2/semantic/query', {
      query,
      dataset_id: datasetId,
      return_raw: returnRaw,
    }),

  // Explain SQL in plain English
  explainSql: (datasetId, sql) =>
    api.post('/v2/sql/explain', { dataset_id: datasetId, sql }),

  // Fix SQL using AI (provide original SQL + error message)
  fixSql: (datasetId, sql, error) =>
    api.post('/v2/sql/fix', { dataset_id: datasetId, sql, error }),

  // Save SQL as a governed metric definition
  saveAsMetric: (datasetId, name, sql, description) =>
    api.post('/v2/metrics', { dataset_id: datasetId, name, sql, description }),
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

  // ── Layout Snapshots ──
  listSnapshots: (datasetId) => api.get(`/datasets/${datasetId}/layout-snapshots/`),
  createSnapshot: (datasetId, name, layout = {}, isAuto = false) =>
    api.post(`/datasets/${datasetId}/layout-snapshots/`, { name, layout, is_auto: isAuto }),
  restoreSnapshot: (datasetId, snapshotId) =>
    api.post(`/datasets/${datasetId}/layout-snapshots/${snapshotId}/restore`),
  deleteSnapshot: (datasetId, snapshotId) =>
    api.delete(`/datasets/${datasetId}/layout-snapshots/${snapshotId}`),
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
  // Auth is handled by the HttpOnly cookie (auto-sent by browser).
  streamAnalysis: (datasetId, question = 'Give me a full exploratory analysis of this dataset') => {
    return fetch(`${API_URL}/agentic/analyze`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Protection': '1',
      },
      body: JSON.stringify({ dataset_id: datasetId, question }),
    });
  },

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

// Insight feedback API — wires to the SND Belief Store
// POST /api/insights/accept  — thumbs up (stores as useful, no alpha change)
// POST /api/insights/{id}/dismiss — "already knew" (stores + updates alpha)
export const insightAPI = {
  // Thumbs up — mark as useful
  accept: ({ insightText, datasetId = null }) =>
    api.post('/insights/accept', {
      insight_text: insightText,
      dataset_id: datasetId,
    }),

  // Thumbs down — log negative feedback with a reason
  reject: ({ insightText, datasetId = null, reason = null }) =>
    api.post('/insights/reject', {
      insight_text: insightText,
      dataset_id: datasetId,
      reason: reason,
    }),

  // "Already knew" — dismiss + update alpha (SND personalization)
  dismiss: ({ insightId, insightText, datasetId = null, metricName = null, metricValue = null }) =>
    api.post(`/insights/${insightId}/dismiss`, {
      insight_text: insightText,
      dataset_id: datasetId,
      metric_name: metricName,
      metric_value: metricValue,
    }),
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

// ──────────────────────────────────────────────
// Workspace API (Roles, Members, Workspace CRUD)
// ──────────────────────────────────────────────
export const workspaceAPI = {
  // ── Workspace CRUD ──
  createWorkspace: (data) => api.post('/workspaces', data),
  listWorkspaces: () => api.get('/workspaces'),
  getWorkspace: (id) => api.get(`/workspaces/${id}`),
  updateWorkspace: (id, data) => api.put(`/workspaces/${id}`, data),
  deleteWorkspace: (id) => api.delete(`/workspaces/${id}`),

  // ── Membership ──
  listMembers: (workspaceId) => api.get(`/workspaces/${workspaceId}/members`),
  addMember: (workspaceId, data) => api.post(`/workspaces/${workspaceId}/members`, data),
  updateMemberRole: (workspaceId, userId, role) =>
    api.put(`/workspaces/${workspaceId}/members/${userId}/role`, { role }),
  removeMember: (workspaceId, userId) =>
    api.delete(`/workspaces/${workspaceId}/members/${userId}`),

  // ── Resolve current workspace ──
  resolveWorkspace: () => api.get('/auth/me'),  // Returns current_user + workspace context
};

// ──────────────────────────────────────────────
// BYOK API Key Management
// ──────────────────────────────────────────────
export const keysAPI = {
  // Discover models for a key (test + list models, no save)
  discoverModels: (provider, apiKey) =>
    api.post('/v1/keys/discover', { provider, api_key: apiKey }),

  // Register a new API key (validates + encrypts + stores)
  createKey: (data) => api.post('/v1/keys', data),

  // List user's active keys
  listKeys: () => api.get('/v1/keys'),

  // Get a single key's metadata
  getKey: (keyId) => api.get(`/v1/keys/${keyId}`),

  // Update a key (label, selected_models, is_active, or key rotation)
  updateKey: (keyId, data) => api.patch(`/v1/keys/${keyId}`, data),

  // Delete a key permanently
  deleteKey: (keyId) => api.delete(`/v1/keys/${keyId}`),

  // Re-validate an existing stored key
  validateKey: (keyId) => api.post(`/v1/keys/${keyId}/validate`),
};

// ──────────────────────────────────────────────
// Project Workspace API (analysis containers)
// ──────────────────────────────────────────────
export const projectAPI = {
  // ── Project CRUD ──
  create: (data) => api.post('/projects', data),
  list: () => api.get('/projects'),
  get: (id) => api.get(`/projects/${id}`),
  update: (id, data) => api.put(`/projects/${id}`, data),
  remove: (id) => api.delete(`/projects/${id}`),

  // ── Sources (context binder) ──
  bindSource: (projectId, data) => api.post(`/projects/${projectId}/sources`, data),
  listSources: (projectId) => api.get(`/projects/${projectId}/sources`),
  syncSource: (projectId, sourceId) => api.post(`/projects/${projectId}/sources/${sourceId}/sync`),

  // ── Cells (journey) ──
  addCell: (projectId, data) => api.post(`/projects/${projectId}/cells`, data),
  listCells: (projectId) => api.get(`/projects/${projectId}/cells`),
  updateCell: (projectId, cellId, data) => api.put(`/projects/${projectId}/cells/${cellId}`, data),

  // ── Journey ──
  nextQuestion: (projectId, problemStatement = null) =>
    api.post(`/projects/${projectId}/journey/next-question`, problemStatement ? { problem_statement: problemStatement } : {}),

  // ── Context rules ──
  addContextRule: (projectId, ruleText) =>
    api.post(`/projects/${projectId}/context/rules`, { rule_text: ruleText }),
};

// ──────────────────────────────────────────────
// dlt Data Connector API calls
// ──────────────────────────────────────────────
export const dltAPI = {
  // List available source types (Salesforce, HubSpot, etc.)
  listSources: () => api.get('/dlt/sources'),

  // List saved dlt connections
  listConnections: () => api.get('/dlt/connections'),

  // Setup a new dlt connection (encrypts + saves)
  setupConnection: (data) => api.post('/dlt/setup', data),

  // Trigger a sync on a saved connection
  syncConnection: (data) => api.post('/dlt/sync', data),

  // Get connection sync status
  getConnectionStatus: (connId) => api.get(`/dlt/${connId}/status`),

  // Delete a dlt connection
  deleteConnection: (connId) => api.delete(`/dlt/${connId}`),

  // Reset incremental state (force full re-sync on next run)
  resetConnectionState: (connId) => api.post(`/dlt/${connId}/reset`),
};

export default api;
