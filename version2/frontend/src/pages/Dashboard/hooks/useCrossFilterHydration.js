/**
 * useCrossFilterHydration
 * -----------------------
 * Makes the dashboard cross-filter a REAL data filter, not just a dim effect —
 * now multi-select AND multi-field.
 *
 * The filter context (crossFilters: [{ field, value }]) composes like Power BI:
 *   • same field, multiple values → OR  (multi-select: West + North)
 *   • different fields           → AND (multi-field: Region AND Product)
 *
 * For each chart we compute the fields it actually uses (group_by + columns).
 * Charts whose fields intersect the active filter context get re-aggregated
 * over the filtered rows; charts on unfiltered dimensions are untouched. A
 * chart that shows BOTH filtered dimensions (e.g. grouped by region+product)
 * gets the composed AND filter — that's "filter by two dimensions at once".
 *
 * Implementation:
 *   1. group active filters by field,
 *   2. assign every chart a signature = the sorted filtered fields it uses,
 *   3. one /api/ai/{datasetId}/hydrate-charts request PER signature, carrying
 *      [{ field, values: [...] }] payloads (OR per field, AND across fields),
 *   4. snapshot baselines once per filter context; restore instantly on clear.
 *
 * Safety:
 * - in-flight dedupe (one hydration at a time)
 * - per-signature dedupe so re-renders don't spam the backend
 * - failures degrade silently: the dim effect still shows, data stays as-is
 */

import { useEffect, useRef } from 'react';
import useDatasetStore from '../../../store/datasetStore';
import useDashboardActionStore from '../../../store/dashboardActionStore';

/**
 * Every field a chart references — its grouping dimension(s) plus columns.
 * The primary dimension (first group_by) is what a click on it belongs to.
 */
const getChartFields = (component = {}) => {
  const cfg = component.config || {};
  const fields = [];
  const gb = cfg.group_by;
  if (Array.isArray(gb)) {
    gb.forEach((f) => { if (f && !fields.includes(f)) fields.push(f); });
  } else if (typeof gb === 'string' && gb.trim()) {
    fields.push(gb);
  }
  const cols = cfg.columns || [];
  if (Array.isArray(cols)) {
    cols.forEach((c) => { if (c && !fields.includes(c)) fields.push(c); });
  }
  return fields;
};

/** [{ field, value }] → { field: [values...] } grouped (OR per field). */
const groupByField = (filters) => {
  const byField = {};
  (filters || []).forEach((f) => {
    if (!f?.field || !f.value) return;
    const field = f.field;
    if (!byField[field]) byField[field] = [];
    byField[field].push(String(f.value));
  });
  return byField;
};

export const useCrossFilterHydration = (selectedDataset, config) => {
  const { setDashboardConfig } = useDatasetStore();
  const { crossFilters, hierarchyDrill } = useDashboardActionStore();
  const datasetId = selectedDataset?.id || selectedDataset?._id;

  // Snapshot of baseline (unfiltered) chart_data keyed by component index.
  const baselineRef = useRef(null);
  const inFlightRef = useRef(false);
  const lastContextRef = useRef(null);

  useEffect(() => {
    if (!datasetId || !Array.isArray(config?.components)) return;

    const components = config.components;
    const byField = groupByField(crossFilters);
    const activeFields = Object.keys(byField);

    // ── Filter context cleared → restore the unfiltered baseline instantly ──
    if (activeFields.length === 0) {
      if (baselineRef.current) {
        const baseline = baselineRef.current;
        baselineRef.current = null;
        lastContextRef.current = null;

        const hasChanges = baseline.some(({ index, chartData }) => {
          const comp = components[index];
          return comp && comp.chart_data !== chartData;
        });
        if (!hasChanges) return;

        const patched = components.map((component, index) => {
          const entry = baseline.find((b) => b.index === index);
          if (!entry) return component;
          return { ...component, chart_data: entry.chartData };
        });
        setDashboardConfig(datasetId, { ...config, components: patched });
      }
      return;
    }

    // A field-less legacy filter can't determine which charts share a field —
    // keep the existing dim-only behavior (no data re-hydration).
    if (activeFields.some((f) => !f)) return;

    // ── Charts grouped by the filtered fields they USE ──
    // signature: sorted list of active fields the chart references. Charts on
    // unfiltered dimensions (signature []) are untouched. The hierarchy-drilled
    // chart is excluded: its granularity is owned by the drill.
    const groups = new Map(); // signature → { components, fields }
    components.forEach((component, index) => {
      if (component?.type !== 'chart') return;
      if (hierarchyDrill) {
        const isDrilled = hierarchyDrill.componentId
          ? component.id === hierarchyDrill.componentId
          : component.title === hierarchyDrill.chartTitle;
        if (isDrilled) return;
      }
      const fields = getChartFields(component).filter((f) => byField[f.field] || byField[f]);
      if (fields.length === 0) return;
      const signature = [...new Set(fields)].sort().join('|');
      if (!groups.has(signature)) groups.set(signature, { components: [], fields: [...new Set(fields)] });
      groups.get(signature).components.push({ component, index });
    });

    if (groups.size === 0) return;

    // Per-context dedupe: don't re-hydrate when the filter context is unchanged.
    const contextSignature = activeFields
      .sort()
      .map((f) => `${f}:${byField[f].slice().sort().join(',')}`)
      .join('&');
    if (lastContextRef.current === contextSignature) return;

    // Snapshot the baseline ONCE per context (before filtered data lands).
    if (!baselineRef.current) {
      baselineRef.current = [];
      groups.forEach(({ components: group }) => {
        group.forEach(({ component, index }) => {
          if (component.chart_data) {
            baselineRef.current.push({ index, chartData: component.chart_data });
          }
        });
      });
    }

    if (inFlightRef.current) return;
    inFlightRef.current = true;

    const run = async () => {
      try {
        // One request per signature; payload = [{ field, values }] per used field.
        // Patches accumulate across ALL groups and are applied in ONE store
        // write — applying per-group would clobber the previous group's
        // re-aggregation (multi-field filters need both dimensions to land).
        const accumulated = new Map(); // index → { chart_data, updated_config }
        for (const [, { components: group, fields }] of groups) {
          const filters = fields.map((field) => ({
            field,
            values: byField[field] || [],
          }));
          const res = await fetch(`/api/ai/${datasetId}/hydrate-charts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Protection': '1' },
            credentials: 'include',
            body: JSON.stringify({
              components: group.map(({ component }) => component),
              filters,
              max_rows: 10000,
            }),
          });

          if (!res.ok) {
            console.error('[useCrossFilterHydration] request failed:', res.status);
            continue;
          }

          const result = await res.json();
          const results = Array.isArray(result.results) ? result.results : [];
          results.forEach((r) => {
            if (!r?.success || !r?.chart_data) return;
            const originalIndex = group[r.index]?.index;
            if (originalIndex !== undefined) {
              accumulated.set(originalIndex, {
                chart_data: r.chart_data,
                updated_config: r.updated_config || {},
              });
            }
          });
        }

        if (accumulated.size === 0) return;

        const patched = components.map((component, index) => {
          const patch = accumulated.get(index);
          if (!patch) return component;
          return {
            ...component,
            chart_data: patch.chart_data,
            config: { ...(component.config || {}), ...patch.updated_config },
          };
        });
        setDashboardConfig(datasetId, { ...config, components: patched });
        lastContextRef.current = contextSignature;
      } catch (e) {
        console.error('[useCrossFilterHydration] network error:', e);
      } finally {
        inFlightRef.current = false;
      }
    };

    run();
  }, [datasetId, config, crossFilters, hierarchyDrill, setDashboardConfig]);

  return null;
};

export default useCrossFilterHydration;
