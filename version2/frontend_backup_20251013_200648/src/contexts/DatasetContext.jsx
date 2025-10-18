import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';

const DatasetContext = createContext();

export const useDataset = () => {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error('useDataset must be used within a DatasetProvider');
  }
  return context;
};

export const DatasetProvider = ({ children }) => {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const { api, isAuthenticated } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      fetchDatasets();
    }
  }, [isAuthenticated]);

  const fetchDatasets = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get('/api/datasets');
      setDatasets(response.data.datasets || []);
    } catch (error) {
      console.error('Failed to fetch datasets:', error);
      setError('Failed to fetch datasets');
    } finally {
      setLoading(false);
    }
  };

  const uploadDataset = async (file) => {
    try {
      setLoading(true);
      setError(null);
      
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post('/api/datasets/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      // Refresh datasets list
      await fetchDatasets();
      return { success: true, data: response.data };
    } catch (error) {
      console.error('Dataset upload failed:', error);
      const errorMessage = error.response?.data?.detail || 'Upload failed';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const deleteDataset = async (datasetId) => {
    try {
      setLoading(true);
      setError(null);
      
      await api.delete(`/api/datasets/${datasetId}`);
      
      // Remove from local state
      setDatasets(prev => prev.filter(dataset => dataset.id !== datasetId));
      
      // Clear selection if it was the deleted dataset
      if (selectedDataset?.id === datasetId) {
        setSelectedDataset(null);
      }
      
      return { success: true };
    } catch (error) {
      console.error('Dataset deletion failed:', error);
      const errorMessage = error.response?.data?.detail || 'Deletion failed';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const getDataset = async (datasetId) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await api.get(`/api/datasets/${datasetId}`);
      setSelectedDataset(response.data);
      return { success: true, data: response.data };
    } catch (error) {
      console.error('Failed to fetch dataset:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to fetch dataset';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const getDatasetData = async (datasetId, page = 1, pageSize = 100) => {
    try {
      const response = await api.get(`/api/datasets/${datasetId}/data`, {
        params: { page, page_size: pageSize }
      });
      return { success: true, data: response.data };
    } catch (error) {
      console.error('Failed to fetch dataset data:', error);
      return { success: false, error: error.response?.data?.detail || 'Failed to fetch data' };
    }
  };

  const generateDashboard = async (datasetId) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await api.post(`/api/ai/${datasetId}/generate-dashboard`);
      return { success: true, data: response.data };
    } catch (error) {
      console.error('Dashboard generation failed:', error);
      const errorMessage = error.response?.data?.detail || 'Dashboard generation failed';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const designDashboard = async (datasetId, designPreference) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await api.post(`/api/ai/${datasetId}/design-dashboard`, {
        design_preference: designPreference
      });
      return { success: true, data: response.data };
    } catch (error) {
      console.error('Dashboard design failed:', error);
      const errorMessage = error.response?.data?.detail || 'Dashboard design failed';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  const chatWithDataset = async (datasetId, message, conversationId = null) => {
    try {
      const response = await api.post(`/api/datasets/${datasetId}/chat`, {
        message,
        conversation_id: conversationId
      });
      return { success: true, data: response.data };
    } catch (error) {
      console.error('Chat failed:', error);
      return { success: false, error: error.response?.data?.detail || 'Chat failed' };
    }
  };

  const value = {
    datasets,
    loading,
    error,
    selectedDataset,
    setSelectedDataset,
    fetchDatasets,
    uploadDataset,
    deleteDataset,
    getDataset,
    getDatasetData,
    generateDashboard,
    designDashboard,
    chatWithDataset,
  };

  return (
    <DatasetContext.Provider value={value}>
      {children}
    </DatasetContext.Provider>
  );
};

export default DatasetContext;

