import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { datasetAPI } from '../services/api';
import { toast } from 'react-hot-toast';

const DATASET_STORAGE_KEY = 'dataset-storage';
let datasetsFetchPromise = null;

const getInitialState = () => ({
  datasets: [],
  selectedDataset: null,
  selectedDatasetId: null,
  ownerUserId: null,
  uploadProgress: 0,
  isUploading: false,
  loading: false,
  error: null,
  processingDatasetId: null,
  isProcessingComplete: false,
  lastFetchedAt: 0,
  isBackendOffline: false,
  dashboardConfigs: {}, // Map of datasetId -> dashboardConfig
  activeUpload: { fileName: null, progress: 0, isComplete: false, error: null },
});

const getDatasetId = (dataset) => dataset?.id || dataset?._id || null;
const getDatasetLifecycleStatus = (dataset) =>
  (dataset?.processing_status || dataset?.status || '').toLowerCase();
const hasSameDatasetSnapshot = (a, b) => {
  if (!a || !b) return false;
  return (
    getDatasetId(a) === getDatasetId(b) &&
    a?.is_processed === b?.is_processed &&
    getDatasetLifecycleStatus(a) === getDatasetLifecycleStatus(b) &&
    (a?.artifact_status?.dashboard_design || null) === (b?.artifact_status?.dashboard_design || null) &&
    (a?.artifact_status?.insights_report || null) === (b?.artifact_status?.insights_report || null) &&
    (a?.artifact_status?.dashboard_error || '') === (b?.artifact_status?.dashboard_error || '') &&
    (a?.artifact_status?.insights_error || '') === (b?.artifact_status?.insights_error || '') &&
    Number(a?.processing_progress || 0) === Number(b?.processing_progress || 0) &&
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
          selectedDatasetId: getDatasetId(nextSelected),
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
        set({
          selectedDataset: matched || dataset,
          selectedDatasetId: datasetId
        });
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

      // Processing modal state
      setProcessingDataset: (datasetId) => set({
        processingDatasetId: datasetId,
        isProcessingComplete: false
      }),
      setProcessingComplete: (isComplete) => set({ isProcessingComplete: isComplete }),
      clearProcessingState: () => set({
        processingDatasetId: null,
        isProcessingComplete: false
      }),

      // Enhanced fetch: Auto-call on init if empty
      fetchDatasets: async (force = false, manual = false) => {
        const currentUserId = getCurrentAuthUserId();
        const now = Date.now();
        const { lastFetchedAt, datasets, ownerUserId } = get();

        // No authenticated user means no dataset access
        if (!currentUserId) {
          set({
            datasets: [],
            selectedDataset: null,
            ownerUserId: null,
            loading: false,
            error: null,
            lastFetchedAt: 0,
          });
          return [];
        }

        // Reuse the in-flight request instead of returning stale datasets.
        if (datasetsFetchPromise) {
          return datasetsFetchPromise;
        }

        // Optimization: Throttling forced refreshes
        // If not a manual refresh, ignore 'force' if fetched within the last 15 seconds
        const isFresh = (now - lastFetchedAt) < 15000;
        if (force && isFresh && !manual && datasets.length > 0) {
          console.debug('Optimizing: Skipping forced dataset refresh (fetched < 5s ago)');
          return datasets;
        }

        if (ownerUserId && ownerUserId !== currentUserId) {
          set({
            datasets: [],
            selectedDataset: null,
            ownerUserId: currentUserId,
            error: null,
            lastFetchedAt: 0,
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
        datasetsFetchPromise = (async () => {
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
              selectedDatasetId: getDatasetId(nextSelectedDataset),
              ownerUserId: currentUserId,
              loading: false,
              lastFetchedAt: Date.now(),
              isBackendOffline: false,
            });

            if (force && manual) {
              toast.success(`Refreshed ${fetched.length} datasets`, {
                id: 'datasets-refreshed',
                duration: 2000,
              });
            }

            return fetched;
          } catch (error) {
            const isNetworkError = !error.response && (error.code === 'ERR_NETWORK' || error.message?.includes('Network Error') || error.name === 'TypeError');
            const errMsg = error.response?.data?.detail || (isNetworkError ? 'Backend server is unreachable' : 'Failed to fetch datasets');

            set({
              error: errMsg,
              loading: false,
              isBackendOffline: isNetworkError
            });

            if (force) {
              toast.error(errMsg);
            }
            return [];
          } finally {
            datasetsFetchPromise = null;
          }
        })();

        return datasetsFetchPromise;
      },

      // Enhanced upload with duplicate detection
      uploadDataset: async (file, name = '', description = '') => {
        const uploadToast = toast.loading('Uploading...');
        set({
          isUploading: true,
          uploadProgress: 0,
          error: null,
          activeUpload: { fileName: name || file.name, progress: 0, isComplete: false, error: null }
        });
        get().clearActiveUpload(); // Reset previous if any
        set({
          activeUpload: { fileName: name || file.name, progress: 0, isComplete: false, error: null }
        });
        try {
          const formData = new FormData();
          formData.append('file', file);
          if (name) formData.append('name', name);
          if (description) formData.append('description', description);

          const response = await datasetAPI.uploadDataset(formData, (progress) => {
            set((state) => ({
              uploadProgress: progress,
              activeUpload: { ...state.activeUpload, progress }
            }));
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
            selectedDatasetId: getDatasetId(newDataset),
            ownerUserId: getCurrentAuthUserId(),
            isUploading: false,
            uploadProgress: 100,
            activeUpload: { ...state.activeUpload, progress: 100, isComplete: true }
          }));

          toast.success('Dataset uploaded successfully!', { id: uploadToast });
          return { success: true, dataset: newDataset };

        } catch (error) {
          const errMsg = error.response?.data?.detail || 'Upload failed';
          set({
            error: errMsg,
            isUploading: false,
            uploadProgress: 0,
            activeUpload: { fileName: null, progress: 0, isComplete: false, error: errMsg }
          });
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
            selectedDatasetId: getDatasetId(dataset),
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
          selectedDatasetId: getDatasetId(dataset),
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
      setActiveUpload: (fileName, progress = 0) => set({
        activeUpload: { fileName, progress, isComplete: false, error: null }
      }),
      updateUploadProgress: (progress) => set((state) => ({
        activeUpload: { ...state.activeUpload, progress }
      })),
      clearActiveUpload: () => set({
        activeUpload: { fileName: null, progress: 0, isComplete: false, error: null }
      }),
      setDashboardConfig: (datasetId, config) => {
        if (!datasetId) return;
        set((state) => ({
          dashboardConfigs: {
            ...state.dashboardConfigs,
            [datasetId]: config,
          },
        }));
      },
      clearDashboardConfigs: () => set({ dashboardConfigs: {} }),
    }),
    {
      name: DATASET_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        selectedDatasetId: state.selectedDatasetId || getDatasetId(state.selectedDataset),
        ownerUserId: state.ownerUserId,
        dashboardConfigs: state.dashboardConfigs,
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
          }
          return;
        }

        // Auto-fetch datasets and restore selection by ID
        const rehydrateData = async () => {
          try {
            const datasets = await state.fetchDatasets(true);
            const targetId = state.selectedDatasetId;

            if (targetId) {
              const matched = datasets.find(d => getDatasetId(d) === targetId);
              if (matched) {
                state.setSelectedDataset(matched);
              } else if (datasets.length > 0) {
                state.setSelectedDataset(datasets[0]);
              }
            } else if (datasets.length > 0) {
              state.setSelectedDataset(datasets[0]);
            }
          } catch (e) {
            console.error('Failed to rehydrate dataset selection:', e);
          }
        };

        rehydrateData();
      },
    }
  )
);

export default useDatasetStore;
