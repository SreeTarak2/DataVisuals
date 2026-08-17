/**
 * hierarchyDrill.js
 * =================
 * Drill-down along VALIDATED hierarchy paths (the ontology layer).
 *
 * The mechanics of drill-down are deterministic (a click passes a field+value
 * to a re-aggregation) — the only intelligence is WHICH hierarchy exists and
 * how confident we are. That comes from the backend ontology
 * (`GET /datasets/{id}/hierarchies`): validated chains first, then provisional.
 *
 * Flow (double-click a chart grouped by a hierarchy level):
 *   1. find the hierarchy whose columns include the chart's grouping field,
 *   2. re-render the chart grouped by the NEXT level, filtered to the clicked
 *      value (AND-composed with every active drill level), via
 *      `POST /ai/{id}/hydrate-charts` (which skips blueprint persistence when
 *      filters are active — drilled views are transient, never persisted),
 *   3. remember the baseline so breadcrumb navigation restores it,
 *   4. if the hierarchy is provisional, the caller flags it in the UI.
 */

import useDatasetStore from '../store/datasetStore';
import useDashboardActionStore from '../store/dashboardActionStore';

/**
 * Find the first hierarchy whose columns contain `field` with a deeper level
 * to drill into. Returns null when the field isn't part of a drillable path.
 */
export const findHierarchyForField = (hierarchies, field) => {
  if (!field || !Array.isArray(hierarchies) || hierarchies.length === 0) return null;
  for (const hierarchy of hierarchies) {
    const columns = hierarchy.columns || [];
    const fieldIndex = columns.indexOf(field);
    if (fieldIndex >= 0 && fieldIndex < columns.length - 1) {
      return { hierarchy, fieldIndex, nextLevel: columns[fieldIndex + 1] };
    }
  }
  return null;
};

/**
 * Build the composed filter payload for a drill from the live filter context
 * (crossFilters — the source of truth). Same field values OR together, fields
 * AND together, so drilling US → California while Product=A is also selected
 * filters by all three at once (multi-field drill).
 */
export const buildDrillFilters = (crossFilters) => {
  const byField = {};
  (crossFilters || []).forEach((f) => {
    if (!f?.field || !f.value) return;
    if (!byField[f.field]) byField[f.field] = [];
    byField[f.field].push(String(f.value));
  });
  return Object.entries(byField).map(([field, values]) => ({ field, values }));
};

/**
 * Restore every hierarchy-drilled chart to its baseline (called when the drill
 * stack is popped or cleared). Returns true if something was restored.
 */
export const restoreDrilledCharts = () => {
  const store = useDashboardActionStore.getState();
  const drill = store.hierarchyDrill;
  if (!drill) return false;

  const datasetStore = useDatasetStore.getState();
  const { dashboardConfigs, setDashboardConfig } = datasetStore;
  const config = drill.datasetId ? dashboardConfigs?.[drill.datasetId] : null;

  if (config && Array.isArray(config.components)) {
    const patched = config.components.map((item) => {
      const isDrilled =
        item?.type === 'chart' &&
        (drill.componentId ? item.id === drill.componentId : item.title === drill.chartTitle);
      if (!isDrilled) return item;
      // Restore baseline data + config (drop the group_by override).
      return {
        ...item,
        chart_data: drill.baseChartData,
        config: drill.baseConfig || item.config,
      };
    });
    setDashboardConfig(drill.datasetId, { ...config, components: patched });
  }

  store.clearHierarchyDrill();
  return true;
};

/**
 * Drill a chart one level deeper along its hierarchy.
 *
 * Returns { drilled, nextLevel, provisional } — `drilled: false` when the
 * field isn't a drillable hierarchy level (caller keeps the plain filter
 * drill) or when the backend returns nothing renderable (e.g. leaf level).
 */
export const drillChartAlongHierarchy = async ({
  datasetId,
  component,
  clickedValue,
  chartFilterField,
  chartTitle,
}) => {
  if (!datasetId) return { drilled: false };

  const store = useDashboardActionStore.getState();
  const hierarchies = store.hierarchies;
  const found = findHierarchyForField(hierarchies, chartFilterField);
  if (!found) return { drilled: false };
  const { hierarchy, nextLevel } = found;
  const provisional = hierarchy.state === 'provisional';

  // Re-render the chart grouped by the NEXT level over the filtered rows.
  const cfg = component.config || {};
  const columns = [
    nextLevel,
    ...(Array.isArray(cfg.columns) ? cfg.columns : [])
      .filter((c) => c && c !== chartFilterField && c !== nextLevel),
  ];
  const drilledComponent = {
    ...component,
    config: { ...cfg, group_by: nextLevel, columns },
  };

  // The live filter context (multi-field composed) drives the re-aggregation.
  const filters = buildDrillFilters(store.crossFilters);

  let result;
  try {
    const res = await fetch(`/api/ai/${datasetId}/hydrate-charts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Protection': '1' },
      credentials: 'include',
      body: JSON.stringify({ components: [drilledComponent], filters, max_rows: 10000 }),
    });
    if (!res.ok) {
      console.error('[hierarchyDrill] hydrate-charts failed:', res.status);
      return { drilled: false, error: `HTTP ${res.status}` };
    }
    result = await res.json();
  } catch (e) {
    console.error('[hierarchyDrill] network error:', e);
    return { drilled: false, error: e.message };
  }

  const r = result?.results?.[0];
  if (!r?.success || !r?.chart_data || !Array.isArray(r.chart_data?.data) || r.chart_data.data.length === 0) {
    // Leaf level or nothing matches the filters — fall back to filter-only drill.
    return { drilled: false, error: 'empty drilled result' };
  }

  // Patch the drilled chart's data + config in the store config.
  const datasetStore = useDatasetStore.getState();
  const { dashboardConfigs, setDashboardConfig } = datasetStore;
  const config = dashboardConfigs?.[datasetId];
  if (config && Array.isArray(config.components)) {
    const patched = config.components.map((item) => {
      const match =
        item?.type === 'chart' &&
        ((component.id && item.id === component.id) ||
          (component.title && item.title === component.title) ||
          item === component);
      if (!match) return item;
      return {
        ...item,
        chart_data: r.chart_data,
        config: {
          ...(item.config || {}),
          ...(r.updated_config || {}),
          group_by: nextLevel,
          columns,
        },
      };
    });
    setDashboardConfig(datasetId, { ...config, components: patched });
  }

  // Remember the baseline so breadcrumb navigation restores it.
  store.setHierarchyDrill({
    datasetId,
    componentId: component.id || null,
    chartTitle,
    field: chartFilterField,
    currentLevel: chartFilterField,
    nextLevel,
    hierarchy,
    provisional,
    baseChartData: component.chart_data,
    baseConfig: component.config,
  });

  return { drilled: true, nextLevel, provisional, hierarchy };
};
