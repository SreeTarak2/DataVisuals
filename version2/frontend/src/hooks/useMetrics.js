import { useState, useEffect, useCallback, useRef } from 'react';
import { datasetAPI } from '../services/api';
import usePersonaStore from '../store/personaStore';

/**
 * Normalise one KPI dict from the backend into MetricCard props.
 *
 * Backend returns snake_case; we keep camelCase internally and map
 * directly to MetricCard's prop interface.
 */
function normalise(kpi) {
  return {
    id:                kpi.id || kpi._id || null,
    title:             kpi.title || kpi.column || 'Metric',
    value:             kpi.value ?? null,
    format:            kpi.format || 'number',
    previousValue:     kpi.comparison_value ?? null,
    deltaPct:          kpi.delta_percent ?? null,
    deltaDirection:    kpi.delta_direction || null,
    comparisonLabel:   kpi.comparison_label || null,
    sparklineData:     Array.isArray(kpi.sparkline_data) ? kpi.sparkline_data
                       : Array.isArray(kpi.sparklineData) ? kpi.sparklineData
                       : null,
    businessCategory:  kpi.business_category || kpi.businessCategory || null,
    iconName:          kpi.icon || null,
    accentColor:       kpi.accent_color || kpi.accentColor || null,
    // Preserve raw for downstream consumers
    _raw: kpi,
  };
}

/**
 * useMetrics — fetch, cache, and normalise KPI data from the backend.
 *
 * @param {string} datasetId
 * @returns {{ metrics, loading, error, refresh, isStale }}
 *
 * `metrics` is an array of MetricCard-ready props objects.
 */
export function useMetrics(datasetId) {
  const persona = usePersonaStore((s) => s.personas[datasetId] || null);
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fetchedAt, setFetchedAt] = useState(null);
  const abortRef = useRef(null);

  const fetchMetrics = useCallback(async (refresh = false) => {
    if (!datasetId) {
      setMetrics([]);
      setLoading(false);
      return;
    }

    // Cancel in-flight
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const res = await datasetAPI.getKpis(datasetId, refresh, persona);
      const data = res?.data || {};
      const raw = Array.isArray(data) ? data : (data.kpis || []);

      const normalised = raw
        .filter(item => item.type === 'kpi' || !item.type)
        .map(normalise);

      setMetrics(normalised);
      setFetchedAt(Date.now());
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.name === 'AbortError') return;
      const msg = err?.response?.data?.detail || err?.message || 'Failed to load metrics';
      setError(msg);
      setMetrics([]);
    } finally {
      setLoading(false);
    }
  }, [datasetId, persona]);

  // Auto-fetch on datasetId or persona change. The persona param alone forces
  // regeneration server-side, so a persona switch refetches automatically.
  useEffect(() => {
    if (!datasetId) {
      setMetrics([]);
      setLoading(false);
      setError(null);
      return;
    }
    fetchMetrics(false);

    return () => {
      abortRef.current?.abort();
    };
  }, [datasetId, persona, fetchMetrics]);

  // Auto-refresh if stale (> 10 min)
  const isStale = fetchedAt ? (Date.now() - fetchedAt) > 10 * 60 * 1000 : false;

  return {
    metrics,
    loading,
    error,
    refresh: () => fetchMetrics(false),
    isStale,
  };
}

export default useMetrics;
