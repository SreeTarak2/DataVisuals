import { create } from 'zustand';

const useDashboardActionStore = create((set) => ({
  // Insights refresh state
  insightsLoading: false,
  onInsightsRefresh: null,

  // Insights setters
  setInsightsLoading: (loading) => set({ insightsLoading: loading }),
  setOnInsightsRefresh: (callback) => set({ onInsightsRefresh: callback }),

  // ── Cross-chart filtering (multi-select, multi-field) ──
  // crossFilters is the filter CONTEXT: an array of { field, value } entries.
  //   • Same field + multiple values → OR  (multi-select: West + North)
  //   • Different fields            → AND (multi-field: Region AND Product)
  // This is the Power BI / Tableau selection model — clicking a value toggles
  // it in/out of the context instead of replacing it.
  // `crossFilter` is kept as a derived convenience (the first entry) so legacy
  // readers that still read a single filter keep working.
  crossFilters: [],
  crossFilter: null,
  crossFilterSource: null,
  crossFilterActive: false,
  normalizeFilter: (filter) => {
    if (!filter) return null;
    if (typeof filter === 'string') return { field: null, value: filter };
    if (typeof filter === 'object' && filter?.value !== undefined && filter?.value !== null) {
      return { field: filter.field || null, value: String(filter.value) };
    }
    return null;
  },
  // Sync the top drill level's values when a filter on the drilled field
  // changes — the breadcrumb trail must stay truthful ("West, North").
  // Always writes back (even to empty) so stale values can never resurrect a
  // removed filter during breadcrumb navigation.
  _syncDrillLevel: (state, next) => {
    const stack = state.drillDownStack || [];
    const top = stack[stack.length - 1];
    if (!top || !top.field) return stack;
    const levelValues = (next || [])
      .filter((f) => (f.field || null) === top.field)
      .map((f) => f.value);
    return [
      ...stack.slice(0, -1),
      {
        ...top,
        values: levelValues,
        filterValue: levelValues[0] || null,
        label: levelValues.length > 1 ? levelValues.join(', ') : top.label,
      },
    ];
  },
  toggleFilter: (filter, source) => set((state) => {
    const normalized = state.normalizeFilter ? state.normalizeFilter(filter) : null;
    if (!normalized) {
      return {
        crossFilters: [],
        crossFilter: null,
        crossFilterSource: source || null,
        crossFilterActive: false,
      };
    }
    const { field, value } = normalized;
    const exists = (state.crossFilters || []).some(
      (f) => (f.field || null) === field && String(f.value) === value
    );
    const next = exists
      ? (state.crossFilters || []).filter(
          (f) => !((f.field || null) === field && String(f.value) === value)
        )
      : [...(state.crossFilters || []), { field, value }];
    const drillDownStack = state._syncDrillLevel(state, next);
    return {
      crossFilters: next,
      crossFilter: next[0] || null,
      crossFilterSource: source || null,
      crossFilterActive: next.length > 0,
      drillDownStack,
    };
  }),
  // Replace the whole filter context (URL restore, drill navigation rebuild).
  setFilters: (filters, source) => set((state) => {
    const next = (Array.isArray(filters) ? filters : [])
      .map((f) => state.normalizeFilter(f))
      .filter(Boolean);
    const drillDownStack = state._syncDrillLevel(state, next);
    return {
      crossFilters: next,
      crossFilter: next[0] || null,
      crossFilterSource: source || null,
      crossFilterActive: next.length > 0,
      drillDownStack,
    };
  }),
  // Remove every filter on a field (used by the badge's per-field ✕).
  // The badge keys legacy field-less filters as '__value__' — removing that
  // key clears every filter whose field is null.
  removeFiltersForField: (field) => set((state) => {
    const next = (state.crossFilters || []).filter((f) => {
      const fField = f.field || null;
      if (field === '__value__') return fField !== null;
      return fField !== field;
    });
    const drillDownStack = state._syncDrillLevel(state, next);
    return {
      crossFilters: next,
      crossFilter: next[0] || null,
      crossFilterSource: state.crossFilterSource,
      crossFilterActive: next.length > 0,
      drillDownStack,
    };
  }),
  clearCrossFilter: () => set((state) => {
    const drillDownStack = state._syncDrillLevel(state, []);
    return {
      crossFilters: [],
      crossFilter: null,
      crossFilterSource: null,
      crossFilterActive: false,
      drillDownStack,
    };
  }),

  // ── Validated hierarchy paths (ontology) for drill-down ──
  // [{ columns, hierarchy_type, confidence, state, source, evidence, assumption_id, description }]
  // state: 'validated' | 'provisional' — provisional paths get flagged in the UI
  // (Act-then-Validate: the system acts on every inference, the human validates).
  hierarchies: [],
  setHierarchies: (hierarchies) => set({ hierarchies: hierarchies || [] }),

  // ── Active hierarchy drill on a chart ──
  // { datasetId, componentId, chartTitle, field, currentLevel, nextLevel, hierarchy,
  //   provisional, baseChartData, baseConfig }
  // Kept so breadcrumb navigation can restore the chart's baseline granularity.
  hierarchyDrill: null,
  setHierarchyDrill: (drill) => set({ hierarchyDrill: drill }),
  clearHierarchyDrill: () => set({ hierarchyDrill: null }),

  // ── Layout snapshots (removed — no UI) ──
  // Backend API exists at /api/datasets/{id}/layout-snapshots/
  // Re-add state + methods when snapshot UI is re-implemented.

  // ── Drill-down navigation ──
  // Stack of { label, filterValue, chartTitle } — root is { label: 'All Data', filterValue: null }
  drillDownStack: [],
  pushDrillDown: (level) => set((state) => ({
    drillDownStack: [...state.drillDownStack, level],
  })),
  popDrillDown: (index) => set((state) => ({
    drillDownStack: state.drillDownStack.slice(0, index),
  })),
  clearDrillDown: () => set({ drillDownStack: [] }),
  restoreDrillDownStack: (stack) => set({ drillDownStack: stack || [] }),
}));

export default useDashboardActionStore;
