import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { datasetAPI } from '../services/api';
import { toast } from 'react-hot-toast';

const DATASET_STORAGE_KEY = 'dataset-storage';

const getInitialState = () => ({
  datasets: [],
  selectedDataset: null,
  ownerUserId: null,
  uploadProgress: 0,
  isUploading: false,
  loading: false,
  error: null,
});

const getDatasetId = (dataset) => dataset?.id || dataset?._id || null;
const hasSameDatasetSnapshot = (a, b) => {
  if (!a || !b) return false;
  return (
    getDatasetId(a) === getDatasetId(b) &&
    a?.is_processed === b?.is_processed &&
    (a?.processing_status || '') === (b?.processing_status || '') &&
    Number(a?.row_count || 0) === Number(b?.row_count || 0) &&
    Number(a?.column_count || 0) === Number(b?.column_count || 0) &&
    (a?.name || '') === (b?.name || '') &&
    (a?.updated_at || a?.created_at || a?.upload_date || '') ===
      (b?.updated_at || b?.created_at || b?.upload_date || '')
  );
};

const parsePersistedAuth = (storage) => {
  try {
    const raw = storage.getItem('datasage-auth');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state || null;
  } catch (error) {
    console.warn('Failed to parse persisted auth state:', error);
    return null;
  }
};

const getCurrentAuthUserId = () => {
  if (typeof window === 'undefined') return null;

  const sessionState = parsePersistedAuth(window.sessionStorage);
  const localState = parsePersistedAuth(window.localStorage);

  const activeAuthState = sessionState?.token
    ? sessionState
    : localState?.token
      ? localState
      : sessionState || localState;

  return activeAuthState?.user?.id || null;
};

const useDatasetStore = create(
  persist(
    (set, get) => ({
      ...getInitialState(),

      // Actions
      setDatasets: (datasets) => {
        const currentSelected = get().selectedDataset;
        const selectedId = getDatasetId(currentSelected);
        const selectedFromList = datasets.find((dataset) => getDatasetId(dataset) === selectedId) || null;
        const nextSelected = selectedFromList
          ? (hasSameDatasetSnapshot(currentSelected, selectedFromList) ? currentSelected : selectedFromList)
          : datasets[0] || null;
        set({
          datasets,
          selectedDataset: nextSelected,
          ownerUserId: getCurrentAuthUserId(),
        });
      },
      setSelectedDataset: (dataset) => {
        const datasetId = getDatasetId(dataset);
        if (!datasetId) {
          set({ selectedDataset: null });
          return;
        }
        const matched = get().datasets.find((item) => getDatasetId(item) === datasetId);
        set({ selectedDataset: matched || dataset });
      },
      setUploadProgress: (progress) => set({ uploadProgress: progress }),
      setIsUploading: (isUploading) => set({ isUploading }),
      setLoading: (loading) => set({ loading }),
      resetState: () => set(getInitialState()),
      setError: (error) => {
        set({ error });
        if (error) toast.error(error);
      },
      clearError: () => set({ error: null }),

      // Enhanced fetch: Auto-call on init if empty
      fetchDatasets: async (force = false) => {
        const { loading } = get();
        const currentUserId = getCurrentAuthUserId();

        // No authenticated user means no dataset access
        if (!currentUserId) {
          set({
            datasets: [],
            selectedDataset: null,
            ownerUserId: null,
            loading: false,
            error: null,
          });
          return [];
        }

        // Prevent concurrent fetches (race condition fix)
        if (loading) return get().datasets;

        const { ownerUserId } = get();
        if (ownerUserId && ownerUserId !== currentUserId) {
          set({
            datasets: [],
            selectedDataset: null,
            ownerUserId: currentUserId,
            error: null,
          });
        }

        const scopedState = get();
        if (
          !force &&
          scopedState.ownerUserId === currentUserId &&
          scopedState.datasets.length > 0
        ) {
          return scopedState.datasets;
        }

        set({ loading: true, error: null });
        try {
          const response = await datasetAPI.getDatasets();
          const fetched = response.data.datasets || [];
          const currentSelected = get().selectedDataset;
          const selectedDatasetId = getDatasetId(currentSelected);
          const selectedFromFetched = fetched.find(
            (dataset) => getDatasetId(dataset) === selectedDatasetId
          ) || null;
          const nextSelectedDataset = selectedFromFetched
            ? (hasSameDatasetSnapshot(currentSelected, selectedFromFetched) ? currentSelected : selectedFromFetched)
            : fetched[0] || null;

          set({
            datasets: fetched,
            selectedDataset: nextSelectedDataset,
            ownerUserId: currentUserId,
            loading: false,
          });

          // Only show success toast for manual refreshes, not automatic polling
          if (force) {
            toast.success(`Refreshed ${fetched.length} datasets`, {
              id: 'datasets-refreshed', // Prevent duplicate toasts
              duration: 2000,
            });
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
            selectedDataset: newDataset,
            ownerUserId: getCurrentAuthUserId(),
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
          set({
            selectedDataset: dataset,
            ownerUserId: getCurrentAuthUserId(),
            loading: false,
          });
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
        set((state) => ({
          datasets: [dataset, ...state.datasets],
          selectedDataset: dataset,
          ownerUserId: getCurrentAuthUserId(),
        }));
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
      name: DATASET_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        datasets: state.datasets,
        selectedDataset: state.selectedDataset,
        ownerUserId: state.ownerUserId,
      }),
      onRehydrateStorage: () => (state) => {
        if (!state) return;

        const currentUserId = getCurrentAuthUserId();
        const hasDifferentOwner =
          !!state.ownerUserId && !!currentUserId && state.ownerUserId !== currentUserId;

        if (!currentUserId || hasDifferentOwner) {
          state.resetState?.();
          if (typeof window !== 'undefined') {
            window.localStorage.removeItem(DATASET_STORAGE_KEY);
            window.sessionStorage.removeItem(DATASET_STORAGE_KEY);
          }
          return;
        }

        const selectedDatasetId = getDatasetId(state.selectedDataset);
        const isSelectedValid = state.datasets.some(
          (dataset) => getDatasetId(dataset) === selectedDatasetId
        );

        if (state.datasets.length === 0) {
          state.fetchDatasets?.(true);
          return;
        }

        if (!isSelectedValid) {
          state.setSelectedDataset?.(state.datasets[0] || null);
        }
      },
    }
  )
);

export default useDatasetStore;
