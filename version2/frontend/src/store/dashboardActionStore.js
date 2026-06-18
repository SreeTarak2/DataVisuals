import { create } from 'zustand';

const useDashboardActionStore = create((set, get) => ({
  // Dashboard redesign state
  isRedesigning: false,
  redesignAttempts: 0,
  onRegenerate: null,
  MAX_REDESIGNS: 5,

  // Insights refresh state
  insightsLoading: false,
  onInsightsRefresh: null,

  // Dashboard setters
  setRedesigning: (isRedesigning) => set({ isRedesigning }),
  setRedesignAttempts: (attempts) => set({ redesignAttempts: attempts }),
  setOnRegenerate: (callback) => set({ onRegenerate: callback }),
  setMaxRedesigns: (max) => set({ MAX_REDESIGNS: max }),
  resetRedesignState: () => set({ isRedesigning: false, redesignAttempts: 0 }),

  // Insights setters
  setInsightsLoading: (loading) => set({ insightsLoading: loading }),
  setOnInsightsRefresh: (callback) => set({ onInsightsRefresh: callback }),

  // Cross-chart filtering
  crossFilter: null,
  setCrossFilter: (filter) => set({ crossFilter: filter }),

  // ─── Layout persistence (drag-and-drop) ───
  kpiLayout: null,
  chartLayout: null,
  layoutSaving: false,

  // ─── Compact mode ───
  compactType: 'vertical',

  // ─── Removed components (for undo/restore) ───
  removedComponents: [],

  // ─── Snapshot state ───
  snapshots: [],
  snapshotsLoading: false,
  showSnapshots: false,

  setKpiLayout: (layout) => set({ kpiLayout: layout }),
  setChartLayout: (layout) => set({ chartLayout: layout }),
  setCompactType: (compactType) => set({ compactType }),
  setShowSnapshots: (showSnapshots) => set({ showSnapshots }),

  // ─── Compact layout (re-pack items greedily) ───
  compactLayout: (type) => {
    const { kpiLayout, chartLayout } = get();
    const layout = type === 'kpi' ? [...(kpiLayout || [])] : [...(chartLayout || [])];
    if (!layout || layout.length === 0) return;

    const sorted = [...layout].sort((a, b) => (a.y || 0) - (b.y || 0) || (a.x || 0) - (b.x || 0));
    let currentY = 0;
    let currentRowHeight = 0;
    let currentRowX = 0;
    const cols = type === 'kpi' ? 4 : 12;

    const compacted = sorted.map((item) => {
      const w = Math.min(item.w || 1, cols);
      if (currentRowX + w > cols) {
        currentY += currentRowHeight;
        currentRowX = 0;
        currentRowHeight = 0;
      }
      const result = { ...item, x: currentRowX, y: currentY };
      currentRowX += w;
      currentRowHeight = Math.max(currentRowHeight, item.h || 1);
      return result;
    });

    if (type === 'kpi') {
      set({ kpiLayout: compacted });
    } else {
      set({ chartLayout: compacted });
    }
  },

  // ─── Remove a grid item ───
  removeGridItem: (type, id, componentData = null) => {
    const { kpiLayout, chartLayout, removedComponents } = get();
    const layout = type === 'kpi' ? [...(kpiLayout || [])] : [...(chartLayout || [])];
    const removed = layout.find((item) => item.i === id);

    const filtered = layout.filter((item) => item.i !== id);

    if (type === 'kpi') {
      set({ kpiLayout: filtered });
    } else {
      set({ chartLayout: filtered });
    }

    // Store removed item for possible undo
    if (removed) {
      set({
        removedComponents: [
          ...removedComponents,
          { type, item: removed, componentData },
        ],
      });
    }

    // Compact after remove
    get().compactLayout(type);
  },

  // ─── Undo last removal ───
  undoRemove: () => {
    const { removedComponents, kpiLayout, chartLayout } = get();
    if (removedComponents.length === 0) return;

    const last = removedComponents[removedComponents.length - 1];
    const layout = last.type === 'kpi' ? [...(kpiLayout || [])] : [...(chartLayout || [])];
    layout.push(last.item);

    if (last.type === 'kpi') {
      set({ kpiLayout: layout });
    } else {
      set({ chartLayout: layout });
    }

    set({ removedComponents: removedComponents.slice(0, -1) });
  },

  // ─── Priority management ───
  setComponentPriority: async (datasetId, componentId, priority, reason = '') => {
    if (!datasetId || !componentId || !priority) return;
    try {
      const token = localStorage.getItem('token');
      await fetch(`/api/datasets/${datasetId}/layout/priority`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ component_id: componentId, priority, reason }),
      });
    } catch (e) {
      console.warn('[Priority] Save failed:', e);
    }
  },

  promoteComponent: (type, id, datasetId) => {
    const { kpiLayout, chartLayout } = get();
    const layout = type === 'kpi' ? [...(kpiLayout || [])] : [...(chartLayout || [])];
    const item = layout.find((it) => it.i === id);
    if (!item) return;

    const currentPriority = item.priority || 'P3';
    const priorityOrder = { P4: 'P3', P3: 'P2', P2: 'P1' };
    const newPriority = priorityOrder[currentPriority];
    if (!newPriority) return; // already P1

    item.priority = newPriority;

    if (type === 'kpi') {
      set({ kpiLayout: layout });
    } else {
      set({ chartLayout: layout });
    }

    // Persist to backend
    get().setComponentPriority(datasetId, id, newPriority, 'User promoted');

    // Re-compact to reflow based on new priority
    get().compactLayout(type);

    return newPriority;
  },

  demoteComponent: (type, id, datasetId) => {
    const { kpiLayout, chartLayout } = get();
    const layout = type === 'kpi' ? [...(kpiLayout || [])] : [...(chartLayout || [])];
    const item = layout.find((it) => it.i === id);
    if (!item) return;

    const currentPriority = item.priority || 'P3';
    const priorityOrder = { P1: 'P2', P2: 'P3', P3: 'P4' };
    const newPriority = priorityOrder[currentPriority];
    if (!newPriority) return; // already P4

    item.priority = newPriority;

    if (type === 'kpi') {
      set({ kpiLayout: layout });
    } else {
      set({ chartLayout: layout });
    }

    get().setComponentPriority(datasetId, id, newPriority, 'User demoted');
    get().compactLayout(type);

    return newPriority;
  },

  // ─── Snapshots ───
  loadSnapshots: async (datasetId) => {
    if (!datasetId) return;
    set({ snapshotsLoading: true });
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`/api/datasets/${datasetId}/layout-snapshots/`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ snapshots: data.snapshots || [] });
      }
    } catch (e) {
      console.warn('[Snapshots] Load failed:', e);
    } finally {
      set({ snapshotsLoading: false });
    }
  },

  saveSnapshot: async (datasetId, name, layout = {}) => {
    if (!datasetId || !name.trim()) return false;
    try {
      const token = localStorage.getItem('token');
      const { kpiLayout, chartLayout } = get();
      const res = await fetch(`/api/datasets/${datasetId}/layout-snapshots/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          layout: layout.kpis || layout.charts
            ? layout
            : { kpis: kpiLayout || [], charts: chartLayout || [] },
          is_auto: false,
        }),
      });
      if (res.ok) {
        // Refresh snapshot list
        get().loadSnapshots(datasetId);
        return true;
      }
    } catch (e) {
      console.warn('[Snapshots] Save failed:', e);
    }
    return false;
  },

  restoreSnapshot: async (datasetId, snapshotId) => {
    if (!datasetId || !snapshotId) return null;
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(
        `/api/datasets/${datasetId}/layout-snapshots/${snapshotId}/restore`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );
      if (res.ok) {
        const data = await res.json();
        // Update local layout state
        if (data.layout) {
          set({
            kpiLayout: data.layout.kpis || [],
            chartLayout: data.layout.charts || [],
          });
        }
        return data.layout;
      }
    } catch (e) {
      console.warn('[Snapshots] Restore failed:', e);
    }
    return null;
  },

  deleteSnapshot: async (datasetId, snapshotId) => {
    if (!datasetId || !snapshotId) return false;
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(
        `/api/datasets/${datasetId}/layout-snapshots/${snapshotId}`,
        {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );
      if (res.ok) {
        get().loadSnapshots(datasetId);
        return true;
      }
    } catch (e) {
      console.warn('[Snapshots] Delete failed:', e);
    }
    return false;
  },

  // ─── Layout persistence (drag-and-drop) ───
  saveLayoutToBackend: async (datasetId, layoutSnapshot = {}) => {
    const { kpiLayout, chartLayout } = get();
    if (!datasetId) return;
    set({ layoutSaving: true });
    try {
      const token = localStorage.getItem('token');
      const payload = {
        kpis: layoutSnapshot.kpis ?? kpiLayout ?? [],
        charts: layoutSnapshot.charts ?? chartLayout ?? [],
      };
      await fetch(`/api/datasets/${datasetId}/layout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      console.warn('[Layout] Save failed:', e);
    } finally {
      set({ layoutSaving: false });
    }
  },

  loadLayoutFromBackend: async (datasetId) => {
    if (!datasetId) return { kpis: [], charts: [] };
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`/api/datasets/${datasetId}/layout`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ kpiLayout: data.kpis || [], chartLayout: data.charts || [] });
        return data;
      }
    } catch (e) {
      console.warn('[Layout] Load failed:', e);
    }
    return { kpis: [], charts: [] };
  },

  resetLayout: async (datasetId) => {
    if (!datasetId) return;
    try {
      const token = localStorage.getItem('token');
      await fetch(`/api/datasets/${datasetId}/layout/reset`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      set({ kpiLayout: null, chartLayout: null });
    } catch (e) {
      console.warn('[Layout] Reset failed:', e);
    }
  },
}));

export default useDashboardActionStore;
