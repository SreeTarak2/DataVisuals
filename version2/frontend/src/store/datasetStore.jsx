import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { datasetAPI } from '../services/api';
import { toast } from 'react-hot-toast';

const useDatasetStore = create(
  persist(
    (set, get) => ({
      datasets: [],
      selectedDataset: null,
      uploadProgress: 0,
      isUploading: false,
      loading: false,
      error: null,
      
      // Actions
      setDatasets: (datasets) => set({ datasets }),
      setSelectedDataset: (dataset) => set({ selectedDataset: dataset }),
      setUploadProgress: (progress) => set({ uploadProgress: progress }),
      setIsUploading: (isUploading) => set({ isUploading }),
      setLoading: (loading) => set({ loading }),
      setError: (error) => {
        set({ error });
        if (error) toast.error(error);
      },
      clearError: () => set({ error: null }),
      
      // Enhanced fetch: Auto-call on init if empty
      fetchDatasets: async (force = false) => {
        const { datasets } = get();
        if (!force && datasets.length > 0) return datasets;
        set({ loading: true, error: null });
        try {
          const response = await datasetAPI.getDatasets();
          const fetched = response.data.datasets || [];
          set({ datasets: fetched, loading: false });
          
          // Only show success toast for manual refreshes, not automatic polling
          if (force) {
            toast.success(`Refreshed ${fetched.length} datasets`);
          }
          
          // Auto-select first if none
          if (fetched.length > 0 && !get().selectedDataset) {
            set({ selectedDataset: fetched[0] });
          }
          return fetched;
        } catch (error) {
          const errMsg = error.response?.data?.detail || 'Failed to fetch datasets';
          set({ error: errMsg, loading: false });
          // Only show error toast for manual refreshes, not automatic polling
          if (force) {
            toast.error(errMsg);
          }
          return [];
        }
      },
      
      // Enhanced upload with duplicate detection
      uploadDataset: async (file, name = '', description = '') => {
        const uploadToast = toast.loading('Uploading...');
        set({ isUploading: true, uploadProgress: 0, error: null });
        try {
          const formData = new FormData();
          formData.append('file', file);
          if (name) formData.append('name', name);
          if (description) formData.append('description', description);
          
          const response = await datasetAPI.uploadDataset(formData, (progress) => {
            set({ uploadProgress: progress });
            toast.loading(`Uploading: ${progress}%`, { id: uploadToast });
          });
          
          const responseData = response.data;
          
          // Check if it's a duplicate
          if (responseData.is_duplicate) {
            toast.dismiss(uploadToast);
            toast.error('Dataset already exists! This file has been uploaded before.', {
              duration: 5000,
              style: {
                background: '#fef2f2',
                color: '#dc2626',
                border: '1px solid #fecaca'
              }
            });
            set({ isUploading: false, uploadProgress: 0 });
            return { 
              success: false, 
              isDuplicate: true, 
              existingDataset: responseData.existing_dataset 
            };
          }
          
          // New dataset uploaded successfully
          const { dataset_id } = responseData;
          
          // Fetch the full dataset data
          const datasetResponse = await datasetAPI.getDataset(dataset_id);
          const newDataset = datasetResponse.data;
          
          set((state) => ({
            datasets: [newDataset, ...state.datasets],
            isUploading: false,
            uploadProgress: 100,
          }));
          
          toast.success('Dataset uploaded successfully!', { id: uploadToast });
          return { success: true, dataset: newDataset };
          
        } catch (error) {
          const errMsg = error.response?.data?.detail || 'Upload failed';
          set({ error: errMsg, isUploading: false, uploadProgress: 0 });
          toast.error(errMsg, { id: uploadToast });
          return { success: false, error: errMsg };
        }
      },
      
      deleteDataset: async (datasetId) => {
        // Validate dataset ID
        if (!datasetId) {
          const errMsg = 'Dataset ID is required for deletion';
          set({ error: errMsg });
          toast.error(errMsg);
          return { success: false, error: errMsg };
        }

        const deleteToast = toast.loading('Deleting...');
        try {
          console.log('Store: Deleting dataset with ID:', datasetId);
          await datasetAPI.deleteDataset(datasetId);
          set((state) => ({
            datasets: state.datasets.filter(d => d.id !== datasetId && d._id !== datasetId),
            selectedDataset: (state.selectedDataset?.id === datasetId || state.selectedDataset?._id === datasetId) ? null : state.selectedDataset,
          }));
          toast.success('Dataset deleted', { id: deleteToast });
          return { success: true };
        } catch (error) {
          console.error('Store delete error:', error);
          const errMsg = error.response?.data?.detail || 'Delete failed';
          set({ error: errMsg });
          toast.error(errMsg, { id: deleteToast });
          return { success: false, error: errMsg };
        }
      },
      
      getDataset: async (datasetId) => {
        set({ loading: true, error: null });
        try {
          const response = await datasetAPI.getDataset(datasetId);
          const dataset = response.data;
          set({ selectedDataset: dataset, loading: false });
          toast.success('Dataset loaded');
          return { success: true, dataset };
        } catch (error) {
          const errMsg = error.response?.data?.detail || 'Failed to fetch dataset';
          set({ error: errMsg, loading: false });
          toast.error(errMsg);
          return { success: false, error: errMsg };
        }
      },
      
      addDataset: (dataset) => {
        set((state) => ({ datasets: [dataset, ...state.datasets] }));
        toast.success('Dataset added');
      },
      removeDataset: (datasetId) => {
        set((state) => ({ datasets: state.datasets.filter(d => d.id !== datasetId) }));
        toast.success('Dataset removed');
      },
      
      reprocessDataset: async (datasetId) => {
        if (!datasetId) {
          const errMsg = 'Dataset ID is required for reprocessing';
          toast.error(errMsg);
          return { success: false, error: errMsg };
        }
        
        const reprocessToast = toast.loading('Reprocessing dataset...');
        try {
          console.log('Store: Reprocessing dataset with ID:', datasetId);
          const response = await datasetAPI.reprocessDataset(datasetId);
          toast.success('Dataset reprocessing started', { id: reprocessToast });
          // Refresh datasets after a short delay
          setTimeout(() => {
            get().fetchDatasets(true);
          }, 2000);
          return { success: true, taskId: response.data.task_id };
        } catch (error) {
          console.error('Store reprocess error:', error);
          const errMsg = error.response?.data?.detail || 'Reprocessing failed';
          toast.error(errMsg, { id: reprocessToast });
          return { success: false, error: errMsg };
        }
      },
    }),
    {
      name: 'dataset-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ datasets: state.datasets, selectedDataset: state.selectedDataset }),
      onRehydrateStorage: () => (state) => {
        // Auto-fetch on rehydrate if empty
        if (!state || state.datasets.length === 0) {
          get().fetchDatasets(true);
        }
      },
    }
  )
);

export default useDatasetStore;