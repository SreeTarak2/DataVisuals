import React, { useState, useCallback, useEffect, useMemo, useRef, Component } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart3, Layers, AlertCircle, RefreshCw, Loader2, HelpCircle,
  ChevronDown, ChevronUp, Sparkles, Lightbulb, Filter, ShieldAlert
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import ChartRenderer from './features/charts/ChartRenderer';
import { MetricCard } from './kpi';
import SurprisingInsightCard from './ui/SurprisingInsightCard';
import useDatasetStore from '../store/datasetStore';
import { chartAPI } from '../services/api';
import { useChartTheme } from '../hooks/useChartTheme';
import useDashboardActionStore from '../store/dashboardActionStore';
import CorrelationMatrix from './features/analysis/CorrelationMatrix';
import DistributionComparison from './features/analysis/DistributionComparison';
import PivotTable from './features/analysis/PivotTable';
import AnomalyFeed from './features/analysis/AnomalyFeed';
import DataPreviewTable from '../pages/Dashboard/components/DataPreviewTable';
import DrillDownBreadcrumbs from './features/charts/DrillDownBreadcrumbs';
import { drillChartAlongHierarchy, restoreDrilledCharts, findHierarchyForField } from '../utils/hierarchyDrill';

// ── KPI Card Error Boundary (isolates one bad card so it doesn't collapse the grid) ──
class KpiCardErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error) {
    if (import.meta.env.DEV) {
      console.error('KpiCardErrorBoundary caught:', error);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-5 rounded-xl border border-dashed border-red-500/20 bg-card min-h-[120px]">
          <AlertCircle className="w-5 h-5 text-red-500/60 mb-2" />
          <p className="text-xs text-red-400/80 text-center">
            {this.props.title || 'KPI card'}{' '}
            <span className="text-white/30">encountered an error</span>
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

const MotionDiv = motion.div;

const getChartHeight = (type, variant) => {
  // Height tuned for modern SaaS aesthetics, allowing more breathing room
  const fixedHeights = {
    hero: 480,
    featured: 420,
    standard: 400,
    compact: 360,
  };
  return fixedHeights[variant] || 400;
};

const normalizePlotlyChartData = (component = {}) => {
  const raw = component.chart_data || component.chartData || component.plotly || component;
  const nested = raw?.chart_data || raw?.chartData;

  if (nested && nested !== raw) {
    return normalizePlotlyChartData({ chart_data: nested });
  }

  const meta = raw?.metadata || component.metadata || {};

  if (Array.isArray(raw?.data)) {
    return { data: raw.data, layout: raw.layout || {}, metadata: meta };
  }

  if (Array.isArray(raw?.traces)) {
    return { data: raw.traces, layout: raw.layout || {}, metadata: meta };
  }

  if (Array.isArray(component.data)) {
    return { data: component.data, layout: component.layout || {}, metadata: meta };
  }

  if (Array.isArray(component.traces)) {
    return { data: component.traces, layout: component.layout || {}, metadata: meta };
  }

  return { data: [], layout: {}, metadata: {} };
};

const chartHasRenderableData = (chartData = {}) => {
  if (!Array.isArray(chartData.data)) return false;

  return chartData.data.some((trace) => {
    if (!trace || trace.error) return false;
    const traceType = (trace.type || '').toLowerCase();
    if (traceType === 'heatmap') {
      return Array.isArray(trace.z) && trace.z.length > 0 && Array.isArray(trace.z[0]) && trace.z[0].length > 0;
    }
    if (traceType === 'pie') {
      return Array.isArray(trace.values) && trace.values.length > 0;
    }
    if (traceType === 'box' || traceType === 'violin') {
      return Array.isArray(trace.y) && trace.y.length > 0;
    }
    return (Array.isArray(trace.x) && trace.x.length > 0) || (Array.isArray(trace.y) && trace.y.length > 0);
  });
};



const DashboardComponent = ({ component: initialComponent, variant, datasetData = [], bulkHydrating = false }) => {
  const [component, setComponent] = useState(initialComponent);
  const [retrying, setRetrying] = useState(false);
  const [explanationExpanded, setExplanationExpanded] = useState(false);
  const [chartExplanation, setChartExplanation] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [retryError, setRetryError] = useState(null);
  const clickTimeout = useRef(null);
  const { colors } = useChartTheme();
  const { crossFilters, crossFilter, toggleFilter, setFilters, clearCrossFilter,
    drillDownStack, pushDrillDown, popDrillDown, clearDrillDown,
    hierarchies, hierarchyDrill } = useDashboardActionStore();
  const { selectedDataset } = useDatasetStore();

  // Generate a stable unique ID for this KPI card instance.
  // Uses component.id if provided (from backend or intelligentKpis), otherwise
  // falls back to a deterministic ID derived from title + column.
  // This MUST be deterministic across page loads so persisted overrides can be found.
  const kpiId = useMemo(() =>
    initialComponent.id || initialComponent._id ||
    `${initialComponent.title || 'kpi'}::${initialComponent.column || 'col'}`
      .replace(/\s+/g, '_')
      .toLowerCase()
      .replace(/[^a-z0-9_:]/g, ''),
  [initialComponent.title, initialComponent.column]);

  // KPI drill-down event listener
  useEffect(() => {
    const handleKpiDrillDown = (e) => {
      const { kpiId: targetId } = e.detail || {};
      if (targetId === kpiId) {
        toast(`Explore: ${component.title}`, {
          duration: 2000,
          style: {
            background: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            fontSize: '13px',
          },
        });
      }
    };

    window.addEventListener('kpi-drilldown', handleKpiDrillDown);
    return () => window.removeEventListener('kpi-drilldown', handleKpiDrillDown);
  }, [kpiId, component.title]);

  useEffect(() => {
    setComponent(initialComponent);
    setChartExplanation(null);
    setExplanationExpanded(false);
  }, [initialComponent]);

  const chartType = component.config?.chart_type?.toLowerCase() || '';

  // The dimension this chart is grouped by — the field a cross-filter click
  // on this chart belongs to (config.group_by takes priority, else the x column).
  const chartFilterField = useMemo(() => {
    const cfg = component.config || {};
    const gb = cfg.group_by;
    if (Array.isArray(gb) && gb.length) return gb[0];
    if (typeof gb === 'string' && gb.trim()) return gb;
    const cols = cfg.columns || [];
    return cols[0] || null;
  }, [component.config]);

  const isAnalyticsComponent = useMemo(() => {
    return ['distribution_comparison', 'ridge_plot'].includes(chartType);
  }, [chartType]);

  const chartData = useMemo(() => {
    return normalizePlotlyChartData(component);
  }, [component]);
  const chartHeight = getChartHeight(chartType, variant);

  const hasData = useMemo(() => {
    if (isAnalyticsComponent) return true;
    return chartHasRenderableData(chartData);
  }, [chartData, isAnalyticsComponent]);

  // True when the active cross-filter excluded every row for this chart
  // (backend signals via metadata.empty_filtered).
  const emptyUnderFilter = useMemo(() => {
    const meta = chartData?.metadata || component?.metadata || {};
    return Boolean(meta.empty_filtered) && !hasData;
  }, [chartData, component, hasData]);

  // ── Honesty badge: how many points are actually shown vs the source data ──
  // Backend attaches metadata.sampling = {shown, original_count, method} when
  // LTTB / category-caps downsampled the traces. Show it instead of silently
  // truncating.
  const samplingInfo = useMemo(() => {
    const s = chartData?.metadata?.sampling;
    if (!s || typeof s.shown !== 'number' || typeof s.original_count !== 'number') return null;
    if (s.shown <= 0 || s.original_count <= s.shown) return null;
    return s;
  }, [chartData]);

  const formatCompact = (n) => {
    if (n >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`;
    if (n >= 1e3) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}K`;
    return `${n}`;
  };

  // Chart intelligence — simplified for ECharts (tooltips handle annotations natively)
  const handleExplainChart = useCallback(async () => {
    const datasetId = selectedDataset?.id || selectedDataset?._id;
    if (!datasetId || explanationLoading) return;

    if (chartExplanation) {
      setExplanationExpanded(!explanationExpanded);
      return;
    }

    setExplanationLoading(true);
    setExplanationExpanded(true);

    try {
      const chartKey = component.id || component.config?.id || `${chartType}_${component.title || 'chart'}`;
      const res = await chartAPI.explainChart(
        datasetId,
        chartKey,
        {
          chart_type: chartType,
          columns: component.config?.columns || [],
          x: component.config?.x || component.config?.columns?.[0],
          y: component.config?.y || component.config?.columns?.[1],
          title: component.title,
          data: chartData.data || [],
        }
      );

      if (res.data) {
        setChartExplanation({
          explanation: res.data.explanation || '',
          keyInsights: res.data.key_insights || [],
          readingGuide: res.data.reading_guide || '',
          anomalyFlag: res.data.anomaly_flag || null,
          cached: res.data.cached || false,
        });
      } else {
        throw new Error('No explanation data returned');
      }
    } catch (err) {
      console.error('Failed to load chart explanation:', err);
      toast.error('Unable to generate explanation — click Retry in the panel');
      // Keep the panel open so the user can see and click the Retry button
    } finally {
      setExplanationLoading(false);
    }
  }, [selectedDataset, component, chartType, chartData, chartExplanation, explanationLoading, explanationExpanded]);

  const handleRetryChart = useCallback(async ({ silent = false } = {}) => {
    const datasetId = selectedDataset?.id || selectedDataset?._id;
    if (!datasetId || retrying) return;
    setRetrying(true);
    setRetryError(null);
    try {
      const res = await fetch(`/api/ai/${datasetId}/retry-chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Protection': '1' },
        credentials: 'include',
        body: JSON.stringify({ component }),
      });

      if (res.ok) {
        const result = await res.json();
        const regeneratedChartData = normalizePlotlyChartData({ chart_data: result.chart_data });

        const hasValidChartData = chartHasRenderableData(regeneratedChartData);

        if (hasValidChartData) {
          const updatedComponent = {
            ...component,
            chart_data: regeneratedChartData,
            config: {
              ...component.config,
              ...result.updated_config
            }
          };

          setComponent(prev => ({
            ...prev,
            chart_data: updatedComponent.chart_data,
            config: {
              ...prev.config,
              ...result.updated_config
            }
          }));

          const { dashboardConfigs, setDashboardConfig } = useDatasetStore.getState();
          const dashboardConfig = dashboardConfigs?.[datasetId];
          if (dashboardConfig?.components) {
            const patchedComponents = dashboardConfig.components.map((item) => {
              if (item === initialComponent) return updatedComponent;
              if (component.id && item.id === component.id) return updatedComponent;
              if (component.title && item.title === component.title) return updatedComponent;
              return item;
            });
            setDashboardConfig(datasetId, {
              ...dashboardConfig,
              components: patchedComponents,
            });
          }

          if (!silent) {
            toast.success('Chart regenerated successfully!', {
              duration: 2500,
              style: {
                background: '#1e293b',
                color: '#e2e8f0',
                border: '1px solid rgba(52, 211, 153, 0.3)',
                fontSize: '13px'
              }
            });
          }
        } else {
          if (!silent) toast.error('Chart data generation failed - empty result', { duration: 3000 });
        }
      } else {
        const err = await res.json().catch(() => ({ detail: 'Failed to retry chart' }));
        const errorDetail = err.detail;
        const errorMessage = typeof errorDetail === 'object' ? errorDetail.message : errorDetail;
        const errorCategory = typeof errorDetail === 'object' ? errorDetail.category : 'unknown';
        const errorSuggestion = typeof errorDetail === 'object' ? errorDetail.suggestion : null;

        setRetryError({
          message: errorMessage || 'Failed to load chart',
          category: errorCategory,
          suggestion: errorSuggestion,
        });

        if (!silent) {
          toast.error(errorMessage || 'Failed to load chart', { duration: 4000 });
        }
      }
    } catch (e) {
      console.error('Retry chart failed:', e);
      setRetryError({
        message: 'Network error — could not retry',
        category: 'network_error',
        suggestion: 'Check your connection and try again.',
      });
      if (!silent) toast.error('Network error — could not retry', { duration: 3000 });
    } finally {
      setRetrying(false);
    }
  }, [selectedDataset, component, retrying, initialComponent]);

  // Note: automatic per-chart hydration now happens via the page-level
  // useBulkChartHydration hook (ONE /hydrate-charts request for all config-only
  // charts). This component only handles the manual Retry button below.

  // ── Cross-filter: listen for brush events from ECharts ──
  // Brush-select is multi-select: every brushed value toggles into the filter
  // context on this chart's field (OR), so a brush across West+North keeps both.
  useEffect(() => {
    const handleBrush = (e) => {
      const { values } = e.detail || {};
      if (values && values.length > 0) {
        values.slice(0, 50).forEach((v) => {
          toggleFilter({ field: chartFilterField, value: String(v) }, component.title);
        });
      }
    };
    const handleBrushClear = () => {
      clearCrossFilter();
    };

    window.addEventListener('chart-brush', handleBrush);
    window.addEventListener('chart-brush-clear', handleBrushClear);
    return () => {
      window.removeEventListener('chart-brush', handleBrush);
      window.removeEventListener('chart-brush-clear', handleBrushClear);
    };
  }, [toggleFilter, clearCrossFilter, chartFilterField, component.title]);

  const handleDrillDownNavigate = useCallback((index) => {
    // Any navigation away from the drilled state invalidates the hierarchy
    // drill — restore the drilled chart(s) to their baseline granularity.
    restoreDrilledCharts();
    if (index === 0) {
      // Clicked root breadcrumb — clear everything
      clearCrossFilter();
      clearDrillDown();
    } else {
      // Clicked intermediate breadcrumb — pop stack and rebuild the filter
      // context from the remaining drill levels ONLY (each level's values are
      // that field's active multi-select selections). Independent filters on
      // other fields are dropped — navigation means "back to this drill point".
      const remaining = drillDownStack.slice(0, index + 1);
      popDrillDown(index + 1);
      const nextFilters = remaining
        .filter((l) => l && l.field && Array.isArray(l.values) && l.values.length > 0)
        .flatMap((l) => l.values.map((v) => ({ field: l.field, value: String(v) })));
      if (nextFilters.length > 0) {
        setFilters(nextFilters, drillDownStack[index]?.chartTitle || null);
      } else {
        clearCrossFilter();
      }
    }
  }, [drillDownStack, clearCrossFilter, clearDrillDown, popDrillDown, setFilters]);

  const handlePointClick = useCallback((clickData) => {
    if (clickTimeout.current) {
      clearTimeout(clickTimeout.current);
      clickTimeout.current = null;

      // Double-click → drill-down: push level, set cross-filter, and follow
      // the validated hierarchy if this chart's field is a hierarchy level
      // (e.g. US → states). Falls back to the plain filter drill otherwise.
      const clickedValue = clickData.x !== null && clickData.x !== undefined ? String(clickData.x) : null;
      const chartTitle = component.title || 'Data';

      if (clickedValue) {
        // Is this chart's grouping field part of a drillable hierarchy?
        const found = findHierarchyForField(hierarchies, chartFilterField);

        // Push root level if this is the first drill-down
        if (drillDownStack.length === 0) {
          pushDrillDown({ label: 'All Data', values: [], filterValue: null, field: null, chartTitle });
        }
        // Push the clicked level (multi-select values + field + hierarchy so
        // restore is field-aware and provisional paths get flagged in the trail)
        pushDrillDown({
          label: clickedValue,
          values: [clickedValue],
          filterValue: clickedValue,
          field: chartFilterField,
          chartTitle,
          hierarchy: found?.hierarchy || null,
          provisional: found ? found.hierarchy.state === 'provisional' : false,
        });
        // Ensure the clicked value is part of the filter context — toggle in,
        // never toggle out (a double-click is always a drill, not a deselect).
        const alreadyActive = crossFilters.some(
          (f) => f.field === chartFilterField && String(f.value) === String(clickedValue)
        );
        if (!alreadyActive) {
          toggleFilter({ field: chartFilterField, value: clickedValue }, chartTitle);
        }

        drillChartAlongHierarchy({
          datasetId: selectedDataset?.id || selectedDataset?._id,
          component,
          clickedValue,
          chartFilterField,
          chartTitle,
        })
          .then((outcome) => {
            if (outcome?.drilled) {
              toast(
                `Drilled: ${clickedValue} → by ${outcome.nextLevel}${outcome.provisional ? ' (assumed)' : ''}`,
                {
                  duration: 2200,
                  style: {
                    background: '#1e293b',
                    color: '#e2e8f0',
                    border: `1px solid ${outcome.provisional ? 'rgba(245, 158, 11, 0.4)' : 'rgba(99, 102, 241, 0.3)'}`,
                    fontSize: '13px',
                  },
                  icon: <Layers size={16} />,
                }
              );
            } else {
              toast(`Drilling into ${clickedValue}`, {
                duration: 2000,
                style: {
                  background: '#1e293b',
                  color: '#e2e8f0',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                  fontSize: '13px',
                },
                icon: <BarChart3 size={16} />,
              });
            }
          })
          .catch(() => {
            toast(`Drilling into ${clickedValue}`, {
              duration: 2000,
              style: {
                background: '#1e293b',
                color: '#e2e8f0',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                fontSize: '13px',
              },
              icon: <BarChart3 size={16} />,
            });
          });
      }
      return;
    }

    clickTimeout.current = setTimeout(() => {
      clickTimeout.current = null;
      // Single-click → toggle this value in/out of the filter context on this
      // chart's field (multi-select: clicking West then North keeps both; a
      // chart on another field adds a second AND dimension).
      if (clickData.x !== null && clickData.x !== undefined) {
        toggleFilter({ field: chartFilterField, value: String(clickData.x) }, component.title);
      }
    }, 250);
  }, [component, component.title, toggleFilter, chartFilterField, drillDownStack, crossFilters, hierarchies, selectedDataset]);

  switch (component.type) {
    case 'kpi':
      return (
        <KpiCardErrorBoundary title={component.title}>
          <MetricCard
            id={kpiId}
            title={component.title}
            value={component.value}
            format={component.format || 'number'}
            previousValue={component.comparisonValue ?? component.comparison_value ?? null}
            deltaPct={component.deltaPercent ?? component.delta_percent ?? null}
            deltaDirection={
              component.delta_direction || component.trendDirection || component.trend_direction || null
            }
            comparisonLabel={component.comparisonLabel || component.comparison_label || null}
            sparklineData={component.sparklineData || component.sparkline_data || null}
            businessCategory={
              component.businessCategory || component.business_category || component.archetype || null
            }
            iconName={component.icon || null}
            accentColor={component.accentColor || component.accent_color || null}
            loading={component.state === 'loading'}
            error={component.state === 'error' ? (component.aiSuggestion || component.ai_suggestion || 'Failed to load') : null}
            onDrillDown={() => {
              window.dispatchEvent(new CustomEvent('kpi-drilldown', {
                detail: { kpiId, title: component.title, value: component.value },
              }));
            }}
          />
        </KpiCardErrorBoundary>
      );

    case 'insight':
      return (
        <SurprisingInsightCard
          title={component.title}
          description={component.description || component.plain_english || ''}
          insightType={component.insight_type || 'correlation'}
          severity={component.severity || 'info'}
          impact={component.impact}
          metrics={component.metrics || []}
          tags={component.tags || []}
          evidence={component.evidence || {}}
          plainEnglish={component.plain_english}
          category={component.category}
          animationDelay={0}
        />
      );

    case 'pivot_table':
    case 'anomaly_feed': {
      return (
        <MotionDiv
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-2xl flex flex-col transition-all duration-500 group"
          style={{
            background: colors.cardBg,
            border: `1px solid ${colors.border}`,
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06), inset 0 1px 0 0 rgba(255, 255, 255, 0.05)',
            gridColumn: `span ${component.span || 2}`
          }}
        >
          {/* Subtle top glare effect */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent z-20 pointer-events-none" />

          {/* Card header */}
          <div className="px-5 pt-4 pb-3 flex items-center justify-between gap-4 shrink-0 relative z-10">
            <div className="flex items-center gap-3 min-w-0">
              <div className="p-1.5 rounded-lg flex items-center justify-center shadow-sm" style={{ background: `${colors.primary}15`, border: `1px solid ${colors.primary}20` }}>
                {component.type === 'pivot_table' ? (
                  <Grid className="w-3.5 h-3.5 shrink-0" style={{ color: colors.primary }} />
                ) : (
                  <Activity className="w-3.5 h-3.5 shrink-0" style={{ color: colors.primary }} />
                )}
              </div>
              <h3 className="font-semibold text-[15px] tracking-tight truncate" style={{ fontFamily: 'Inter, system-ui, sans-serif', color: colors.text }}>
                {component.title || (component.type === 'pivot_table' ? 'Pivot Analysis' : 'Anomaly Feed')}
              </h3>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 min-h-[350px] relative">
            {component.type === 'pivot_table' ? (
              <PivotTable component={component} datasetData={datasetData} />
            ) : (
              <AnomalyFeed component={component} />
            )}
          </div>
        </MotionDiv>
      );
    }

    case 'chart': {
      return (
        <MotionDiv
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-2xl flex flex-col transition-all duration-500 group"
          style={{
            background: colors.cardBg,
            border: `1px solid ${colors.border}`,
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06), inset 0 1px 0 0 rgba(255, 255, 255, 0.05)'
          }}
        >
          {/* Subtle top glare effect for glassmorphism feel */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent z-20 pointer-events-none" />

          {/* Card header */}
          <div className="px-5 pt-4 pb-3 flex items-center justify-between gap-4 shrink-0 relative z-10">
            <div className="flex items-center gap-3 min-w-0">
              <div className="p-1.5 rounded-lg flex items-center justify-center shadow-sm" style={{ background: `${colors.primary}15`, border: `1px solid ${colors.primary}20` }}>
                <BarChart3 className="w-3.5 h-3.5 shrink-0" style={{ color: colors.primary }} />
              </div>
              <h3 className="font-semibold text-[15px] tracking-tight truncate" style={{ fontFamily: 'Inter, system-ui, sans-serif', color: colors.text }}>
                {component.title || 'Data Visualization'}
              </h3>
              {samplingInfo && (
                <span
                  className="px-2 py-0.5 rounded-full text-[10px] font-medium whitespace-nowrap border shrink-0"
                  style={{
                    background: `${colors.text}08`,
                    borderColor: colors.border,
                    color: colors.textMuted,
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                  }}
                  title={`Showing ${samplingInfo.shown.toLocaleString()} of ${samplingInfo.original_count.toLocaleString()} data points (${samplingInfo.method || 'downsampled'})`}
                >
                  {formatCompact(samplingInfo.shown)} of {formatCompact(samplingInfo.original_count)} pts
                </span>
              )}

              {/* Hierarchy drill indicator — this chart is showing the next level down */}
              {hierarchyDrill && (
                hierarchyDrill.componentId === component.id ||
                (!hierarchyDrill.componentId && hierarchyDrill.chartTitle === component.title)
              ) && (
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border shrink-0 whitespace-nowrap"
                  style={{
                    background: hierarchyDrill.provisional ? 'rgba(245, 158, 11, 0.1)' : `${colors.primary}08`,
                    borderColor: hierarchyDrill.provisional ? 'rgba(245, 158, 11, 0.3)' : `${colors.primary}25`,
                    color: hierarchyDrill.provisional ? '#f59e0b' : colors.primary,
                  }}
                  title={hierarchyDrill.provisional
                    ? `Assumed hierarchy: ${(hierarchyDrill.hierarchy?.columns || []).join(' → ')} (${Math.round((hierarchyDrill.hierarchy?.confidence || 0) * 100)}% confidence) — validate it in the assumptions review`
                    : `Drilled along ${(hierarchyDrill.hierarchy?.columns || []).join(' → ')}`}
                >
                  {hierarchyDrill.provisional
                    ? <ShieldAlert size={10} className="shrink-0" />
                    : <Layers size={10} className="shrink-0" />}
                  by {hierarchyDrill.nextLevel}
                </span>
              )}
            </div>
            
            <button
              onClick={handleExplainChart}
              disabled={explanationLoading || !hasData}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-300 shrink-0 border"
              style={{
                background: explanationExpanded ? `${colors.primary}15` : 'transparent',
                borderColor: explanationExpanded ? `${colors.primary}40` : colors.border,
                color: explanationExpanded ? colors.primary : colors.textMuted,
                opacity: !hasData ? 0.4 : 1,
                boxShadow: explanationExpanded ? `0 0 12px ${colors.primary}20` : 'none'
              }}
              onMouseEnter={(e) => { if(!explanationExpanded && hasData) e.currentTarget.style.background = `${colors.text}08`; }}
              onMouseLeave={(e) => { if(!explanationExpanded && hasData) e.currentTarget.style.background = 'transparent'; }}
              title="Get AI insights for this visualization"
            >
              {explanationLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <HelpCircle className="w-3.5 h-3.5" />
              )}
              <span className="hidden sm:inline">AI Explain</span>
            </button>
          </div>

          {/* Explanation panel */}
          <AnimatePresence>
            {explanationExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="overflow-hidden shrink-0 relative z-10 px-5"
              >
                <div className="pb-4 pt-1">
                  <div className="rounded-xl p-4 text-xs leading-relaxed border backdrop-blur-md shadow-inner"
                    style={{
                      background: chartExplanation ? `${colors.primary}08` : `rgba(239, 68, 68, 0.05)`,
                      borderColor: chartExplanation ? `${colors.primary}20` : `rgba(239, 68, 68, 0.2)`,
                      color: colors.textMuted,
                    }}
                  >
                    {explanationLoading ? (
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Analyzing chart...</span>
                      </div>
                    ) : chartExplanation ? (
                      <div className="space-y-2">
                        {chartExplanation.explanation && (
                          <p className="font-medium" style={{ color: colors.text }}>{chartExplanation.explanation}</p>
                        )}
                        {chartExplanation.keyInsights?.filter(i => typeof i === 'string' && !i.trim().startsWith('{') && !i.trim().startsWith('['))?.length > 0 && (
                          <div className="pt-2 border-t" style={{ borderColor: `${colors.primary}15` }}>
                            <p className="font-semibold mb-1.5" style={{ color: colors.primary }}>Key Insights</p>
                            <ul className="space-y-1">
                              {chartExplanation.keyInsights
                                .filter(i => typeof i === 'string' && !i.trim().startsWith('{') && !i.trim().startsWith('['))
                                .map((insight, idx) => (
                                <li key={idx} className="flex items-start gap-1.5">
                                  <span className="text-[10px] mt-0.5" style={{ color: colors.primary }}>•</span>
                                  <span>{insight}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {chartExplanation.readingGuide && (
                          <div className="pt-2 border-t" style={{ borderColor: `${colors.primary}15` }}>
                            <p className="font-medium flex items-center gap-1.5" style={{ color: colors.text }}><Lightbulb size={14} className="shrink-0" />{chartExplanation.readingGuide}</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2 text-red-400/90">
                          <AlertCircle className="w-4 h-4" />
                          <p>Unable to generate AI explanation at this time.</p>
                        </div>
                        <button
                          onClick={handleExplainChart}
                          className="px-3 py-1.5 text-[11px] font-semibold rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors border border-red-500/20"
                        >
                          Retry
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Drill-down breadcrumbs */}
          {drillDownStack.length > 1 && (
            <DrillDownBreadcrumbs
              stack={drillDownStack}
              onNavigate={handleDrillDownNavigate}
              colors={colors}
            />
          )}

          {/* Chart body */}
          <div className="px-2 pb-3 w-full flex-grow relative z-0" style={{ height: `${chartHeight}px` }}>
            {hasData ? (
              isAnalyticsComponent ? (
                <div className="h-full px-2">
                  {['correlation_matrix', 'heatmap'].includes(chartType) ? (
                    <CorrelationMatrix datasetId={selectedDataset?.id} title={component.title} />
                  ) : (
                    <DistributionComparison
                      datasetId={selectedDataset?.id}
                      numericCol={component.config?.x_axis || component.columns?.[0]}
                      groupCol={component.config?.group_by || component.columns?.[1]}
                      title={component.title}
                    />
                  )}
                </div>
              ) : (
                <ChartRenderer
                  data={chartData.data || chartData.traces || []}
                  layout={{
                    ...chartData.layout,
                  }}
                  chartType={chartType}
                  style={{ width: '100%', height: '100%' }}
                  onPointClick={handlePointClick}
                  chartTitle={component.title}
                  crossFilters={crossFilters}
                  crossFilter={crossFilter}
                  chartFilterField={chartFilterField}
                />
              )
            ) : emptyUnderFilter ? (
              <div className="flex flex-col items-center justify-center h-full space-y-2" role="status">
                <div className="p-2 rounded-xl border" style={{ background: `${colors.text}08`, borderColor: colors.border }}>
                  <Filter className="w-5 h-5" style={{ color: colors.textMuted }} />
                </div>
                <p className="text-xs font-medium" style={{ color: colors.textMuted }}>
                  No data matches the active filter
                </p>
                {crossFilter && (
                  <p className="text-[11px]" style={{ color: colors.textMuted }}>
                    {crossFilters.length > 1
                      ? `${crossFilters.length} active filters excluded everything here`
                      : `${crossFilter.field ? `${crossFilter.field}: ` : ''}"${crossFilter.value}" excluded everything here`}
                  </p>
                )}
              </div>
            ) : bulkHydrating ? (
              <div className="flex flex-col items-center justify-center h-full space-y-3" role="status">
                <div className="p-3 rounded-xl border" style={{ background: `${colors.categorical[0]}10`, borderColor: `${colors.categorical[0]}20` }}>
                  <Loader2 className="w-5 h-5 animate-spin" style={{ color: colors.categorical[0] }} />
                </div>
                <p className="text-xs font-medium" style={{ color: colors.textMuted }}>
                  Preparing chart…
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full space-y-3" role="status">
                <div className="p-3 rounded-xl border" style={{ background: `${colors.categorical[0]}10`, borderColor: `${colors.categorical[0]}20` }}>
                  <AlertCircle className="w-6 h-6" style={{ color: colors.categorical[0] }} />
                </div>
                <div className="text-center space-y-1.5 max-w-xs">
                  <p className="text-xs font-medium" style={{ color: colors.text }}>
                    {retryError?.message || 'Chart unavailable'}
                  </p>
                  {retryError?.suggestion && (
                    <p className="text-[11px] leading-relaxed" style={{ color: colors.textMuted }}>
                      {retryError.suggestion}
                    </p>
                  )}
                  <button
                    onClick={handleRetryChart}
                    disabled={retrying}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all duration-200"
                    style={{
                      background: retrying ? colors.border : `${colors.categorical[0]}10`,
                      borderColor: `${colors.categorical[0]}30`,
                      color: colors.categorical[0],
                    }}
                  >
                    {retrying ? (
                      <><Loader2 className="w-3 h-3 animate-spin" /> Retrying…</>
                    ) : (
                      <><RefreshCw className="w-3 h-3" /> Retry</>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </MotionDiv>
      );
    }

    case 'table': {
      return (
        <div className="col-span-1 lg:col-span-12">
          <DataPreviewTable 
            dataPreview={component.table_data || []} 
            totalRows={component.record_count}
            loading={retrying}
            onReload={handleRetryChart}
          />
        </div>
      );
    }

    default:
      return null;
  }
};

export default DashboardComponent;
