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
  id:                kpi.id || kpi._id || null,
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

  // NEW: Time period context
  periodLabel: kpi.period_label || null,
  previousPeriodLabel: kpi.previous_period_label || null,
  periodType: kpi.period_type || null,

  // NEW: Baseline comparison
  baselineValue: kpi.baseline_value ?? null,
  baselineLabel: kpi.baseline_label || null,
  vsBaselinePct: kpi.vs_baseline_pct ?? null,
  baselineStd: kpi.baseline_std ?? null,
  normalRangeLow: kpi.normal_range_low ?? null,
  normalRangeHigh: kpi.normal_range_high ?? null,

  // NEW: Anomaly detection
  isAnomaly: kpi.is_anomaly || false,
  anomalyDirection: kpi.anomaly_direction || 'normal',
  zScore: kpi.z_score ?? 0,
  anomalySeverity: kpi.anomaly_severity || 'normal',

  // NEW: Trend forecast
  expectedValue: kpi.expected_value ?? null,
  trendDirection: kpi.trend_direction || 'flat',

  // NEW: Top driver
  topDriver: kpi.top_driver || null,

  // NEW: Period-over-period (secondary comparison)
  vsPreviousPct: kpi.vs_previous_pct ?? null,

  // NEW: Provenance / Trust Layer
  provenance: kpi.provenance || null,
  rootCauseChain: kpi.root_cause_chain || null,

  // NEW: Metric Relationship Graph decomposition
  metricDecomposition: kpi.metric_decomposition || null,
});

export const useIntelligentKpis = (datasetId) => {
  const [kpis,      setKpis]      = useState([]);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);
  const [source,    setSource]    = useState(null);   // 'cache' | 'generated'
  const [fetchedAt, setFetchedAt] = useState(null);

  const abortRef = useRef(null);

  // Derive a stable deterministic KPI ID that matches DashboardComponent's logic.
  // Must be identical to what DashboardComponent computes so persisted overrides
  // use the same key for both storage and lookup.
  const getStableKpiId = (kpi) =>
    kpi.id || `${kpi.title || 'kpi'}::${kpi.column || 'col'}`
      .replace(/\s+/g, '_')
      .toLowerCase()
      .replace(/[^a-z0-9_:]/g, '');

  // Apply persisted user overrides (column, aggregation, format, icon, value) to KPIs
  const applyOverrides = (kpis, overrides) => {
    if (!overrides || Object.keys(overrides).length === 0) return kpis;
    return kpis.map(kpi => {
      const stableId = getStableKpiId(kpi);
      const override = overrides[stableId];
      if (!override) return kpi;
      return { ...kpi, ...override };
    });
  };

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

      // Separate KPI cards (type='kpi') from insight cards (type='insight')
      // KPIs get normalised; insights already have the correct shape
      const normalised = raw
        .filter(item => item.type === 'kpi')
        .map(normalise)
      const insights = raw.filter(item => item.type === 'insight')

      // Fetch and merge persisted user overrides
      let merged = [...normalised];
      try {
        const overridesRes = await datasetAPI.getKpiOverrides(datasetId);
        const overrides = overridesRes?.data?.overrides || {};
        merged = applyOverrides(normalised, overrides);
      } catch (overrideErr) {
        // Overrides are non-critical — log and continue with base KPIs
        if (import.meta.env.DEV) {
          console.warn('[KPI] Failed to fetch overrides:', overrideErr);
        }
      }

      setKpis([...merged, ...insights]);
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
  // Refresh re-fetches from cache — backend handles smart migration automatically
  const refresh = useCallback(() => fetchKpis(false), [fetchKpis]);

  return { kpis, loading, error, source, isStale, refresh };
};
