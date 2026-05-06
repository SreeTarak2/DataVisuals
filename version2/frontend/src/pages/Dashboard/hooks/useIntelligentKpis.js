/**
 * useIntelligentKpis
 *
 * Fetches data-science-grade KPI cards from GET /api/datasets/{id}/kpis.
 * Normalises snake_case backend fields → camelCase frontend props so
 * DashboardComponent / EnterpriseKpiCard receive everything they need.
 *
 * Returned kpis array can be used as `visibleKpis` in Dashboard.jsx —
 * each item is already shaped as a `type: 'kpi'` component.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { datasetAPI } from '@/services/api';

const STALE_THRESHOLD_MS = 10 * 60 * 1000; // 10 minutes

// Normalise one KPI dict from the backend into EnterpriseKpiCard props
const normalise = (kpi) => ({
  // Required by DashboardComponent switch
  type: 'kpi',

  // Identity / metadata
  column:            kpi.column,
  aggregation:       kpi.aggregation,
  importance:        kpi.importance || 'medium',
  businessCategory:  kpi.business_category,

  // Display
  title:        kpi.title,
  subtitle:     kpi.subtitle || '',
  value:        kpi.value ?? 0,
  format:       kpi.format || 'number',
  icon:         kpi.icon || 'BarChart3',
  recordCount:  kpi.record_count ?? null,
  definition:   kpi.subtitle || null,
  unitPrefix:   kpi.unit_prefix || null,
  unitSuffix:   kpi.unit_suffix || null,

  // Comparison (backend sends snake_case)
  comparisonValue:  kpi.comparison_value ?? null,
  comparisonLabel:  kpi.comparison_label || null,
  deltaPercent:     kpi.delta_percent    ?? null,
  deltaDirection:   kpi.delta_direction  || null,
  isDeltaPositive:  kpi.is_delta_positive ?? true,

  // Accent color (pre-computed by backend, drives the left border stripe)
  accentColor: kpi.accent_color || null,

  // Sparkline
  sparklineData: kpi.sparkline_data || [],

  // Benchmark / target
  benchmarkText:  kpi.benchmark_text  || null,
  benchmarkValue: kpi.benchmark_value ?? null,
  benchmarkLabel: kpi.benchmark_label || null,

  // AI narrative
  aiSuggestion: kpi.ai_suggestion || null,
  actionPrompt: kpi.action_prompt  || null,

  // Dashboard-level story (only on hero card)
  dashboardStory: kpi.dashboard_story || null,
  archetype:      kpi.archetype       || null,
});

export const useIntelligentKpis = (datasetId) => {
  const [kpis,      setKpis]      = useState([]);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);
  const [source,    setSource]    = useState(null);   // 'cache' | 'generated'
  const [fetchedAt, setFetchedAt] = useState(null);

  const abortRef = useRef(null);

  const fetchKpis = useCallback(async (refresh = false) => {
    if (!datasetId) return;

    // Cancel any in-flight request
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const res = await datasetAPI.getKpis(datasetId, refresh);
      const data = res?.data || {};
      const raw  = data.kpis || [];

      setKpis(raw.map(normalise));
      setSource(data.source || 'generated');
      setFetchedAt(Date.now());
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.name === 'AbortError') return;
      const msg = err?.response?.data?.detail || err?.message || 'Failed to load KPIs';
      setError(msg);
      setKpis([]);
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  // Auto-fetch when datasetId changes
  useEffect(() => {
    if (!datasetId) {
      setKpis([]);
      setLoading(false);
      setError(null);
      setSource(null);
      return;
    }
    fetchKpis(false);

    return () => {
      abortRef.current?.abort();
    };
  }, [datasetId, fetchKpis]);

  const isStale = fetchedAt ? (Date.now() - fetchedAt) > STALE_THRESHOLD_MS : false;
  const refresh = useCallback(() => fetchKpis(true), [fetchKpis]);

  return { kpis, loading, error, source, isStale, refresh };
};
