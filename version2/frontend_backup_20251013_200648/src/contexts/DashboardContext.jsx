import React, { createContext, useContext, useReducer, useCallback } from 'react';
import dashboardService from '../services/dashboardService';
import toast from 'react-hot-toast';

const DashboardContext = createContext();

// Action types
const DASHBOARD_ACTIONS = {
  SET_LOADING: 'SET_LOADING',
  SET_DASHBOARDS: 'SET_DASHBOARDS',
  SET_ACTIVE_DASHBOARD: 'SET_ACTIVE_DASHBOARD',
  SET_DESIGN_PATTERNS: 'SET_DESIGN_PATTERNS',
  ADD_DASHBOARD: 'ADD_DASHBOARD',
  UPDATE_DASHBOARD: 'UPDATE_DASHBOARD',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR'
};

// Initial state
const initialState = {
  loading: false,
  dashboards: [],
  activeDashboard: null,
  designPatterns: [],
  error: null
};

// Reducer
function dashboardReducer(state, action) {
  switch (action.type) {
    case DASHBOARD_ACTIONS.SET_LOADING:
      return { ...state, loading: action.payload };
    
    case DASHBOARD_ACTIONS.SET_DASHBOARDS:
      return { ...state, dashboards: action.payload };
    
    case DASHBOARD_ACTIONS.SET_ACTIVE_DASHBOARD:
      return { ...state, activeDashboard: action.payload };
    
    case DASHBOARD_ACTIONS.SET_DESIGN_PATTERNS:
      return { ...state, designPatterns: action.payload };
    
    case DASHBOARD_ACTIONS.ADD_DASHBOARD:
      return { ...state, dashboards: [...state.dashboards, action.payload] };
    
    case DASHBOARD_ACTIONS.UPDATE_DASHBOARD:
      return {
        ...state,
        dashboards: state.dashboards.map(dashboard =>
          dashboard.id === action.payload.id ? action.payload : dashboard
        )
      };
    
    case DASHBOARD_ACTIONS.SET_ERROR:
      return { ...state, error: action.payload };
    
    case DASHBOARD_ACTIONS.CLEAR_ERROR:
      return { ...state, error: null };
    
    default:
      return state;
  }
}

export const DashboardProvider = ({ children }) => {
  const [state, dispatch] = useReducer(dashboardReducer, initialState);

  // Actions
  const generateAIDashboard = useCallback(async (datasetId) => {
    try {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: true });
      dispatch({ type: DASHBOARD_ACTIONS.CLEAR_ERROR });

      const result = await dashboardService.generateAIDashboard(datasetId);
      
      dispatch({ type: DASHBOARD_ACTIONS.ADD_DASHBOARD, payload: result });
      dispatch({ type: DASHBOARD_ACTIONS.SET_ACTIVE_DASHBOARD, payload: result });
      
      toast.success('AI Dashboard generated successfully!');
      return result;
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to generate AI dashboard';
      dispatch({ type: DASHBOARD_ACTIONS.SET_ERROR, payload: errorMessage });
      toast.error(errorMessage);
      throw error;
    } finally {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: false });
    }
  }, []);

  const designIntelligentDashboard = useCallback(async (datasetId, designPreference = {}) => {
    try {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: true });
      dispatch({ type: DASHBOARD_ACTIONS.CLEAR_ERROR });

      const result = await dashboardService.designIntelligentDashboard(datasetId, designPreference);
      
      dispatch({ type: DASHBOARD_ACTIONS.ADD_DASHBOARD, payload: result });
      dispatch({ type: DASHBOARD_ACTIONS.SET_ACTIVE_DASHBOARD, payload: result });
      
      toast.success('Intelligent dashboard designed successfully!');
      return result;
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to design intelligent dashboard';
      dispatch({ type: DASHBOARD_ACTIONS.SET_ERROR, payload: errorMessage });
      toast.error(errorMessage);
      throw error;
    } finally {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: false });
    }
  }, []);

  const getDesignPatterns = useCallback(async () => {
    try {
      const patterns = await dashboardService.getDesignPatterns();
      dispatch({ type: DASHBOARD_ACTIONS.SET_DESIGN_PATTERNS, payload: patterns });
      return patterns;
    } catch (error) {
      console.error('Error fetching design patterns:', error);
      return [];
    }
  }, []);

  const generateQUISInsights = useCallback(async (datasetId) => {
    try {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: true });
      const result = await dashboardService.generateQUISInsights(datasetId);
      toast.success('QUIS insights generated successfully!');
      return result;
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to generate QUIS insights';
      toast.error(errorMessage);
      throw error;
    } finally {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: false });
    }
  }, []);

  const runAnalysis = useCallback(async (datasetId, analysisType) => {
    try {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: true });
      const result = await dashboardService.runAnalysis(datasetId, analysisType);
      return result;
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to run analysis';
      toast.error(errorMessage);
      throw error;
    } finally {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: false });
    }
  }, []);

  const runQUISAnalysis = useCallback(async (datasetId, maxDepth = 2) => {
    try {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: true });
      const result = await dashboardService.runQUISAnalysis(datasetId, maxDepth);
      toast.success('QUIS analysis completed successfully!');
      return result;
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to run QUIS analysis';
      toast.error(errorMessage);
      throw error;
    } finally {
      dispatch({ type: DASHBOARD_ACTIONS.SET_LOADING, payload: false });
    }
  }, []);

  const renderChartPreview = useCallback(async (chartConfig, datasetId) => {
    try {
      const result = await dashboardService.renderChartPreview(chartConfig, datasetId);
      return result;
    } catch (error) {
      console.error('Error rendering chart preview:', error);
      throw error;
    }
  }, []);

  const setActiveDashboard = useCallback((dashboard) => {
    dispatch({ type: DASHBOARD_ACTIONS.SET_ACTIVE_DASHBOARD, payload: dashboard });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: DASHBOARD_ACTIONS.CLEAR_ERROR });
  }, []);

  const value = {
    ...state,
    generateAIDashboard,
    designIntelligentDashboard,
    getDesignPatterns,
    generateQUISInsights,
    runAnalysis,
    runQUISAnalysis,
    renderChartPreview,
    setActiveDashboard,
    clearError
  };

  return (
    <DashboardContext.Provider value={value}>
      {children}
    </DashboardContext.Provider>
  );
};

export const useDashboard = () => {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
};

export default DashboardContext;

