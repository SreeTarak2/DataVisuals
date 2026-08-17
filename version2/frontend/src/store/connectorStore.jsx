import { create } from 'zustand';
import { databaseAPI } from '../services/api';

/**
 * useConnectorStore — Centralized Zustand store for database connector state.
 *
 * Consolidates connector CRUD, connection listing, form state, and table browsing
 * so that Sidebar, ConnectorsPage, and ConnectorSetupPage always share the same
 * authoritative state instead of each managing their own local useState.
 *
 * Key improvements over the previous pattern (local useState + custom events):
 *   1. Single source of truth for connections list across all components.
 *   2. No fragile window event listeners ('db-connection-saved') for cross-component refresh.
 *   3. Loading / error states are consistently available everywhere.
 *   4. Connection form state can be restored if the user navigates away and back.
 */

const useConnectorStore = create((set, get) => ({
  // ─── Connection list ───
  connections: [],
  connectionsLoading: false,
  connectionsError: null,

  // ─── Active connection detail (for ConnectorSetupPage) ───
  activeConnection: null,
  activeConnectionLoading: false,
  activeConnectionError: null,

  // ─── Table browsing ───
  tables: [],
  tablesLoading: false,

  // ─── Connection form state (preserved across navigation) ───
  form: {
    name: '',
    host: '',
    port: '',
    database: '',
    username: '',
    password: '',
    connection_url: '',
  },

  // ─── Test / save state ───
  testResult: null,        // 'success' | 'error' | null
  testMessage: '',
  isTesting: false,
  isSaving: false,
  savedConnId: null,
  error: null,

  // ══════════════════════════════════════════════
  //  ACTIONS
  // ══════════════════════════════════════════════

  // ─── Fetch all saved connections ───
  fetchConnections: async () => {
    set({ connectionsLoading: true, connectionsError: null });
    try {
      const res = await databaseAPI.listConnections();
      const data = res.data || [];
      set({ connections: Array.isArray(data) ? data : [], connectionsLoading: false });
      return data;
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to load connections';
      set({ connectionsError: msg, connectionsLoading: false });
      return [];
    }
  },

  // ─── Load a single connection (for Manage mode) ───
  loadConnection: async (connId) => {
    if (!connId) {
      set({ activeConnection: null, activeConnectionLoading: false });
      return null;
    }
    set({ activeConnectionLoading: true, activeConnectionError: null });
    try {
      const res = await databaseAPI.listConnections();
      const conns = res.data || [];
      const found = conns.find((c) => c.connection_id === connId);
      if (found) {
        set({
          activeConnection: found,
          activeConnectionLoading: false,
          form: {
            name: found.name || '',
            host: found.host || '',
            port: found.port?.toString() || '',
            database: found.database || '',
            username: found.username || '',
            password: '',
            connection_url: '',
          },
          savedConnId: connId,
        });
        return found;
      } else {
        set({ activeConnection: null, activeConnectionLoading: false, activeConnectionError: 'Connection not found' });
        return null;
      }
    } catch (err) {
      set({
        activeConnection: null,
        activeConnectionLoading: false,
        activeConnectionError: err.response?.data?.detail || err.message || 'Failed to load connection',
      });
      return null;
    }
  },

  // ─── Fetch tables for a saved connection ───
  fetchTables: async (connId) => {
    if (!connId) return;
    set({ tablesLoading: true });
    try {
      const res = await databaseAPI.getTables(connId);
      const tables = res.data?.tables || [];
      set({ tables, tablesLoading: false });
      return tables;
    } catch (err) {
      set({ tables: [], tablesLoading: false });
      return [];
    }
  },

  // ─── Update a single form field ───
  setFormField: (key, value) => {
    set((state) => ({
      form: { ...state.form, [key]: value },
    }));
    // Reset test/save state when important fields change (except name)
    if (key !== 'name') {
      set({ testResult: null, testMessage: '', error: null });
    }
  },

  // ─── Reset form to defaults ───
  resetForm: (defaultPort = '') => {
    set({
      form: { name: '', host: '', port: defaultPort, database: '', username: '', password: '', connection_url: '' },
      testResult: null,
      testMessage: '',
      error: null,
      savedConnId: null,
      activeConnection: null,
      tables: [],
    });
  },

  // ─── Test a connection ───
  testConnection: async (config) => {
    set({ isTesting: true, testResult: null, testMessage: '', error: null });
    try {
      const res = await databaseAPI.testConnection(config);
      const data = res.data;
      if (data.success) {
        set({
          testResult: 'success',
          testMessage: data.tables_count !== undefined
            ? `Connected successfully. Found ${data.tables_count} tables/collections.`
            : 'Connection successful. Credentials are valid.',
          isTesting: false,
        });
      } else {
        set({
          testResult: 'error',
          testMessage: data.message || 'Connection failed. Check your credentials.',
          isTesting: false,
        });
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Connection failed. Check your credentials and network.';
      set({
        testResult: 'error',
        testMessage: typeof detail === 'string' ? detail : 'Connection failed. Please verify your credentials.',
        isTesting: false,
      });
    }
  },

  // ─── Save a verified connection ───
  saveConnection: async (data) => {
    set({ isSaving: true, error: null });
    try {
      const res = await databaseAPI.saveConnection(data);
      const result = res.data;
      set({ savedConnId: result.connection_id, isSaving: false });
      // Refresh the connections list
      get().fetchConnections();
      return { success: true, connection_id: result.connection_id };
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Failed to save connection.';
      set({
        error: typeof detail === 'string' ? detail : 'Failed to save connection. Please try again.',
        isSaving: false,
      });
      return { success: false, error: detail };
    }
  },

  // ─── Delete a saved connection ───
  deleteConnection: async (connId) => {
    try {
      await databaseAPI.deleteConnection(connId);
      // Refresh the connections list
      await get().fetchConnections();
      return { success: true };
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to delete connection.';
      return { success: false, error: msg };
    }
  },

  // ─── Extract table → dataset ───
  extractTable: async (connId, config) => {
    try {
      const res = await databaseAPI.extractTable(connId, config);
      return { success: true, dataset_id: res.data.dataset_id };
    } catch (err) {
      const msg = err.response?.data?.detail || 'Extraction failed';
      return { success: false, error: msg };
    }
  },

  // ─── Reset all state (e.g. on unmount) ───
  resetState: () => {
    set({
      activeConnection: null,
      activeConnectionLoading: false,
      activeConnectionError: null,
      tables: [],
      tablesLoading: false,
      testResult: null,
      testMessage: '',
      isTesting: false,
      isSaving: false,
      savedConnId: null,
      error: null,
    });
  },
}));

export default useConnectorStore;
