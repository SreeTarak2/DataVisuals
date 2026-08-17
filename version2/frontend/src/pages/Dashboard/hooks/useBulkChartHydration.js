/**
 * useBulkChartHydration
 * ---------------------
 * Replaces the N-per-chart `retry-chart` auto-fires with ONE `hydrate-charts`
 * request that renders every config-only chart component in parallel.
 *
 * Fires when the dashboard config gains chart components that have a renderable
 * config but no `chart_data` yet (initial blueprint load, chat-driven additions).
 * On success, merges the returned `chart_data` back into the store config so the
 * chart cards re-render without individual round-trips.
 *
 * Safe guards:
 * - in-flight dedupe (one request at a time)
 * - auto-fires once per (dataset, config signature) — manual per-chart Retry
 *   buttons in DashboardComponent remain as the fallback for failed charts.
 */

import { useEffect, useRef, useState } from 'react';
import useDatasetStore from '../../../store/datasetStore';

const hasRenderableChartData = (component = {}) => {
  const raw = component?.chart_data || component?.chartData || null;
  const data = Array.isArray(raw?.data)
    ? raw.data
    : Array.isArray(raw?.traces)
      ? raw.traces
      : null;
  if (!data || data.length === 0) return false;

  return data.some((trace) => {
    if (!trace || trace.error) return false;
    const t = (trace.type || '').toLowerCase();
    if (t === 'heatmap') {
      return Array.isArray(trace.z) && trace.z.length > 0 && Array.isArray(trace.z[0]) && trace.z[0].length > 0;
    }
    if (t === 'pie' || t === 'donut') {
      return Array.isArray(trace.values) && trace.values.length > 0;
    }
    return (Array.isArray(trace.x) && trace.x.length > 0) || (Array.isArray(trace.y) && trace.y.length > 0);
  });
};

export const useBulkChartHydration = (selectedDataset, config) => {
  const { setDashboardConfig } = useDatasetStore();
  const inFlightRef = useRef(false);
  const firedSignaturesRef = useRef(new Set());
  const [bulkHydrating, setBulkHydrating] = useState(false);

  const datasetId = selectedDataset?.id || selectedDataset?._id;

  // Clear the auto-fire guard ONLY when the dataset actually changes, so charts
  // that failed hydration for one dataset can retry when another is opened.
  // (Keeping this in the main effect would wipe the guard on every config
  // identity change and cause repeated bulk requests for still-unhydrated charts.)
  useEffect(() => {
    firedSignaturesRef.current = new Set();
  }, [datasetId]);

  useEffect(() => {
    if (!datasetId) return;

    const components = Array.isArray(config?.components) ? config.components : [];

    // Only chart components that still lack rendered data qualify for hydration.
    const configOnly = components
      .map((component, index) => ({ component, index }))
      .filter(
        ({ component }) =>
          component?.type === 'chart' &&
          !hasRenderableChartData(component) &&
          (component?.config?.chart_type || component?.config?.columns?.length)
      );

    if (configOnly.length === 0) return;

    // Auto-fire once per dataset+config signature so React StrictMode / re-renders
    // don't spam the backend. Manual Retry buttons handle per-chart failures.
    const signature = `${datasetId}:${components.length}:${configOnly.length}`;
    if (firedSignaturesRef.current.has(signature)) return;
    firedSignaturesRef.current.add(signature);

    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setBulkHydrating(true);

    const run = async () => {
      try {
        const res = await fetch(`/api/ai/${datasetId}/hydrate-charts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Protection': '1' },
          credentials: 'include',
          body: JSON.stringify({
            components: configOnly.map(({ component }) => component),
            max_rows: 10000,
          }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          console.error('[useBulkChartHydration] request failed:', err.detail || res.status);
          return;
        }

        const result = await res.json();
        const results = Array.isArray(result.results) ? result.results : [];
        if (results.length === 0) return;

        // Backend indexes results by position in the SENT (configOnly) array.
        // Map those back to the original components array index before merging.
        const hydratedByIndex = new Map();
        results.forEach((r) => {
          if (!r?.success || !r?.chart_data) return;
          const originalIndex = configOnly[r.index]?.index;
          if (originalIndex !== undefined) hydratedByIndex.set(originalIndex, r);
        });

        if (hydratedByIndex.size === 0) return;

        const patchedComponents = components.map((component, index) => {
          const r = hydratedByIndex.get(index);
          if (!r) return component;
          return {
            ...component,
            chart_data: r.chart_data,
            config: {
              ...(component.config || {}),
              ...(r.updated_config || {}),
            },
          };
        });

        setDashboardConfig(datasetId, {
          ...config,
          components: patchedComponents,
        });
      } catch (e) {
        console.error('[useBulkChartHydration] network error:', e);
      } finally {
        inFlightRef.current = false;
        setBulkHydrating(false);
      }
    };

    run();
  }, [datasetId, config, setDashboardConfig]);

  return { bulkHydrating };
};

export default useBulkChartHydration;
