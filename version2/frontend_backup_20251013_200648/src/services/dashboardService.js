import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const dashboardService = {
  /**
   * Generate AI dashboard for a specific dataset
   * @param {string} datasetId - The dataset ID
   * @returns {Promise} Dashboard generation result
   */
  async generateAIDashboard(datasetId) {
    try {
      const response = await api.post(`/api/ai/${datasetId}/generate-dashboard`);
      return response.data;
    } catch (error) {
      console.error('Error generating AI dashboard:', error);
      throw error;
    }
  },

  /**
   * Design intelligent dashboard with specific preferences
   * @param {string} datasetId - The dataset ID
   * @param {Object} designPreference - Design preference options
   * @returns {Promise} Dashboard design result
   */
  async designIntelligentDashboard(datasetId, designPreference = {}) {
    try {
      const response = await api.post(`/api/ai/${datasetId}/design-dashboard`, {
        design_preference: designPreference
      });
      return response.data;
    } catch (error) {
      console.error('Error designing intelligent dashboard:', error);
      throw error;
    }
  },

  /**
   * Get available design patterns
   * @returns {Promise} Available design patterns
   */
  async getDesignPatterns() {
    try {
      const response = await api.get('/api/ai/design-patterns');
      return response.data;
    } catch (error) {
      console.error('Error getting design patterns:', error);
      throw error;
    }
  },

  /**
   * Generate QUIS insights for a dataset
   * @param {string} datasetId - The dataset ID
   * @returns {Promise} QUIS insights result
   */
  async generateQUISInsights(datasetId) {
    try {
      const response = await api.post('/api/ai/generate-quis-insights', {
        dataset_id: datasetId
      });
      return response.data;
    } catch (error) {
      console.error('Error generating QUIS insights:', error);
      throw error;
    }
  },

  /**
   * Render chart preview
   * @param {Object} chartConfig - Chart configuration
   * @param {string} datasetId - The dataset ID
   * @returns {Promise} Chart rendering result
   */
  async renderChartPreview(chartConfig, datasetId) {
    try {
      const response = await api.post('/api/charts/render-preview', {
        chart_config: chartConfig,
        dataset_id: datasetId
      });
      return response.data;
    } catch (error) {
      console.error('Error rendering chart preview:', error);
      throw error;
    }
  },

  /**
   * Run analysis on a dataset
   * @param {string} datasetId - The dataset ID
   * @param {string} analysisType - Type of analysis to run
   * @returns {Promise} Analysis results
   */
  async runAnalysis(datasetId, analysisType) {
    try {
      const response = await api.post('/api/analysis/run', {
        dataset_id: datasetId,
        analysis_type: analysisType
      });
      return response.data;
    } catch (error) {
      console.error('Error running analysis:', error);
      throw error;
    }
  },

  /**
   * Run QUIS analysis
   * @param {string} datasetId - The dataset ID
   * @param {number} maxDepth - Maximum depth for subspace search
   * @returns {Promise} QUIS analysis results
   */
  async runQUISAnalysis(datasetId, maxDepth = 2) {
    try {
      const response = await api.post('/api/analysis/run-quis', {
        dataset_id: datasetId,
        max_depth: maxDepth
      });
      return response.data;
    } catch (error) {
      console.error('Error running QUIS analysis:', error);
      throw error;
    }
  }
};

export default dashboardService;

