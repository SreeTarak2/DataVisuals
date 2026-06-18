import React, { useState, useCallback, useEffect, useMemo, useRef, Component } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart3, Layers, AlertCircle, RefreshCw, Loader2, HelpCircle, ChevronDown, ChevronUp
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import PlotlyChart from './features/charts/PlotlyChart';
import EnterpriseKpiCard from './ui/EnterpriseKpiCard';
import SurprisingInsightCard from './ui/SurprisingInsightCard';
import useDatasetStore from '../store/datasetStore';
import { getAuthToken, chartAPI, datasetAPI } from '../services/api';
import { useChartTheme } from '../hooks/useChartTheme';
import useDashboardActionStore from '../store/dashboardActionStore';
import CorrelationMatrix from './features/analysis/CorrelationMatrix';
import DistributionComparison from './features/analysis/DistributionComparison';
import PivotTable from './features/analysis/PivotTable';
import AnomalyFeed from './features/analysis/AnomalyFeed';
import DataPreviewTable from '../pages/Dashboard/components/DataPreviewTable';

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

  if (Array.isArray(raw?.data)) {
    return { data: raw.data, layout: raw.layout || {} };
  }

  if (Array.isArray(raw?.traces)) {
    return { data: raw.traces, layout: raw.layout || {} };
  }

  if (Array.isArray(component.data)) {
    return { data: component.data, layout: component.layout || {} };
  }

  if (Array.isArray(component.traces)) {
    return { data: component.traces, layout: component.layout || {} };
  }

  return { data: [], layout: {} };
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

const DashboardComponent = ({ component: initialComponent, variant, chartIntelligence, colorOffset = 0, datasetData = [] }) => {
  const [component, setComponent] = useState(initialComponent);
  const [retrying, setRetrying] = useState(false);
  const [explanationExpanded, setExplanationExpanded] = useState(false);
  const [chartExplanation, setChartExplanation] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [retryError, setRetryError] = useState(null);
  const autoRetryAttemptedRef = useRef(false);
  const clickTimeout = useRef(null);
  const { colors } = useChartTheme();
  const { crossFilter, setCrossFilter } = useDashboardActionStore();
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

  // Listen for KPI edit events from EnterpriseKpiCard
  useEffect(() => {
    const handleKpiEdit = async (e) => {
      const { id, column, aggregation, format, icon, value } = e.detail;
      if (id !== kpiId) return;

      // Update local state immediately
      setComponent(prev => ({
        ...prev,
        column,
        aggregation,
        format,
        icon,
        value,
      }));

      // Persist to backend (fire-and-forget — don't block the UI)
      const datasetId = selectedDataset?.id || selectedDataset?._id;
      if (!datasetId) return;

      try {
        await datasetAPI.updateKpi(datasetId, kpiId, {
          column,
          aggregation,
          format,
          icon,
          value,
        });
      } catch (err) {
        console.warn('[KPI] Failed to persist edit:', err);
        toast.error('Failed to save KPI changes — will retry on next edit', {
          duration: 3000,
          style: { background: '#1e293b', color: '#e2e8f0', border: '1px solid rgba(239,68,68,0.3)' },
        });
      }
    };

    window.addEventListener('kpi-edited', handleKpiEdit);
    return () => window.removeEventListener('kpi-edited', handleKpiEdit);
  }, [kpiId, selectedDataset]);

  useEffect(() => {
    setComponent(initialComponent);
    setChartExplanation(null);
    setExplanationExpanded(false);
    autoRetryAttemptedRef.current = false;
  }, [initialComponent]);

  const chartType = component.config?.chart_type?.toLowerCase() || '';

  const isAnalyticsComponent = useMemo(() => {
    return ['distribution_comparison', 'ridge_plot'].includes(chartType);
  }, [chartType]);

  const chartData = useMemo(() => {
    const normalized = normalizePlotlyChartData(component);
    if (!normalized || !Array.isArray(normalized.data)) return normalized;

    // Enforce SaaS-tier styling on traces
    const styledData = normalized.data.map((trace) => {
      const isLine = chartType === 'line' || chartType === 'line_chart' || chartType === 'area';
      const isBar = chartType === 'bar' || chartType === 'bar_chart' || chartType === 'grouped_bar';
      const isScatter = chartType === 'scatter' || chartType === 'scatter_plot';
      const isPie = chartType === 'pie' || chartType === 'pie_chart' || chartType === 'donut';

      let newTrace = { ...trace };

      if (isLine) {
        newTrace.type = 'scatter';
        // Force lines, smooth them out, hide markers until hover
        newTrace.mode = 'lines+markers';
        newTrace.line = { ...trace.line, shape: 'spline', smoothing: 1.3, width: 3 };
        // Hide markers by default, they will appear on hover
        newTrace.marker = { ...trace.marker, size: 6, opacity: 0 }; 
        if (chartType === 'area') {
            newTrace.fill = 'tozeroy';
        }
      } else if (isBar) {
        newTrace.type = 'bar';
        // Remove default bar borders for a cleaner look
        newTrace.marker = { 
            ...trace.marker, 
            line: { width: 0 } 
        };
      } else if (isScatter) {
        newTrace.type = 'scatter';
        newTrace.mode = 'markers';
        newTrace.marker = { 
            ...trace.marker, 
            size: 8, 
            opacity: 0.75, 
            line: { width: 1, color: colors?.cardBg || '#fff' } 
        };
      } else if (isPie) {
        newTrace.type = 'pie';
        newTrace.hole = 0.65; // Convert all pies to sleek donuts
        newTrace.hoverinfo = 'label+percent';
        newTrace.textinfo = 'none'; // Don't clutter the donut with text
        newTrace.marker = {
            ...trace.marker,
            line: { width: 2, color: colors?.cardBg || 'transparent' } // Gap between slices
        };
      }

      return newTrace;
    });

    return { ...normalized, data: styledData };
  }, [component, chartType, colors]);
  const chartHeight = getChartHeight(chartType, variant);

  const hasData = useMemo(() => {
    if (isAnalyticsComponent) return true;
    return chartHasRenderableData(chartData);
  }, [chartData, isAnalyticsComponent]);

  // Compute AI annotations from chart intelligence
  const computedAnnotations = useMemo(() => {
    if (!chartIntelligence?.intelligence) return [];

    const annotations = [];
    const { insight_annotation, anomaly_flag } = chartIntelligence.intelligence;

    if (insight_annotation) {
      annotations.push({
        x: 0.02,
        y: 1.08,
        xref: 'paper',
        yref: 'paper',
        text: insight_annotation,
        showarrow: false,
        font: { size: 11, color: colors.primary, family: 'Inter, sans-serif' },
        bgcolor: `${colors.primary}10`,
        bordercolor: `${colors.primary}30`,
        borderwidth: 1,
        borderpad: 4,
        textangle: 0,
        xanchor: 'left',
        align: 'left',
      });
    }

    if (anomaly_flag) {
      annotations.push({
        x: 0.98,
        y: 1.08,
        xref: 'paper',
        yref: 'paper',
        text: `! ${anomaly_flag}`,
        showarrow: false,
        font: { size: 10, color: colors.warning, family: 'Inter, sans-serif' },
        bgcolor: `${colors.warning}10`,
        bordercolor: `${colors.warning}30`,
        borderwidth: 1,
        borderpad: 3,
        xanchor: 'right',
        align: 'right',
      });
    }

    return annotations;
  }, [chartIntelligence, colors.primary, colors.warning]);

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
      const token = getAuthToken();
      const res = await fetch(`/api/ai/${datasetId}/retry-chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
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

  useEffect(() => {
    if (component.type !== 'chart' || isAnalyticsComponent || hasData || retrying || autoRetryAttemptedRef.current) {
      return;
    }

    const datasetId = selectedDataset?.id || selectedDataset?._id;
    if (!datasetId || !component.config) return;

    autoRetryAttemptedRef.current = true;
    handleRetryChart({ silent: true });
  }, [component, handleRetryChart, hasData, isAnalyticsComponent, retrying, selectedDataset]);

  const handlePointClick = useCallback((clickData) => {
    if (clickTimeout.current) {
      clearTimeout(clickTimeout.current);
      clickTimeout.current = null;

      const xLabel = clickData.x !== null ? String(clickData.x) : '';
      const yLabel = clickData.y !== null ? (typeof clickData.y === 'number' ? clickData.y.toLocaleString() : String(clickData.y)) : '';
      const series = clickData.seriesName ? ` (${clickData.seriesName})` : '';
      const chartTitle = component.title || 'the chart';

      const query = `I clicked on a specific data point in "${chartTitle}" where ${xLabel} = ${yLabel}${series}. Can you tell me more about what might be driving this specific point or if it represents an anomaly?`;

      window.dispatchEvent(new CustomEvent('open-chat-with-query', { detail: { query } }));

      toast(
        `🎯 Context sent to AI: ${xLabel}: ${yLabel}`,
        {
          duration: 2500,
          style: {
            background: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            fontSize: '13px',
          },
          icon: '✨',
        }
      );
      return;
    }

    clickTimeout.current = setTimeout(() => {
      clickTimeout.current = null;
      // Set cross-chart visual filter
      if (clickData.x !== null && clickData.x !== undefined) {
        setCrossFilter(String(clickData.x));
      }
    }, 250);
  }, [component.title, setCrossFilter]);

  switch (component.type) {
    case 'kpi':
      return (
        <KpiCardErrorBoundary title={component.title}>
          <EnterpriseKpiCard
            id={kpiId}
            title={component.title}
            column={component.column || component.title}
            aggregation={component.aggregation || 'sum'}
            value={component.value ?? 0}
            format={component.format || 'number'}
            definition={component.definition || component.subtitle || null}
            comparisonValue={component.comparisonValue ?? component.comparison_value ?? null}
            comparisonLabel={component.comparisonLabel || component.comparison_label || null}
            deltaPercent={component.deltaPercent ?? component.delta_percent ?? null}
            benchmarkValue={component.benchmarkValue ?? component.benchmark_value ?? null}
            benchmarkLabel={component.benchmarkLabel ?? component.benchmark_label ?? null}
            benchmarkText={component.benchmarkText || component.benchmark_text || null}
            isOutlier={component.isOutlier || false}
            aiSuggestion={component.aiSuggestion || component.ai_suggestion || null}
            targetValue={component.targetValue}
            targetLabel={component.targetLabel}
            achievementPercent={component.achievementPercent ?? component.achievement_pct ?? null}
            periodStatus={component.periodStatus || component.period_status || 'on-track'}
            sparklineData={component.sparklineData || component.sparkline_data || []}
            topValues={component.topValues || null}
            recordCount={component.recordCount ?? component.record_count ?? null}
            datasetData={datasetData}
            unitPrefix={component.unitPrefix || component.unit_prefix || null}
            unitSuffix={component.unitSuffix || component.unit_suffix || null}
            state={component.state || 'ready'}
            staleMinutes={component.staleMinutes ?? component.cache_age_min ?? null}
            icon={component.icon || 'BarChart3'}
            animationDelay={0}
            accentColor={component.accentColor || component.accent_color || null}
            actionPrompt={component.actionPrompt || component.action_prompt || null}
            businessCategory={component.businessCategory || component.business_category || component.archetype || null}
            periodLabel={component.periodLabel || component.period_label || null}
            previousPeriodLabel={component.previousPeriodLabel || component.previous_period_label || null}
            periodType={component.periodType || component.period_type || null}
            baselineValue={component.baselineValue ?? component.baseline_value ?? null}
            baselineLabel={component.baselineLabel || component.baseline_label || null}
            vsBaselinePct={component.vsBaselinePct ?? component.vs_baseline_pct ?? null}
            baselineStd={component.baselineStd ?? component.baseline_std ?? null}
            normalRangeLow={component.normalRangeLow ?? component.normal_range_low ?? null}
            normalRangeHigh={component.normalRangeHigh ?? component.normal_range_high ?? null}
            isAnomaly={component.isAnomaly || false}
            anomalyDirection={component.anomalyDirection || component.anomaly_direction || null}
            zScore={component.zScore ?? component.z_score ?? null}
            anomalySeverity={component.anomalySeverity || component.anomaly_severity || null}
            expectedValue={component.expectedValue ?? component.expected_value ?? null}
            trendDirection={component.trendDirection || component.trend_direction || null}
            topDriver={component.topDriver || component.top_driver || null}
            vsPreviousPct={component.vsPreviousPct ?? component.vs_previous_pct ?? null}
            compact={variant === 'compact'}
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
                            <p className="font-medium" style={{ color: colors.text }}>💡 {chartExplanation.readingGuide}</p>
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
                <PlotlyChart
                  data={chartData.data}
                  layout={{
                    ...chartData.layout,
                    title: null, // REMOVED: redundant internal Plotly title
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: colors.textMuted, family: 'Inter, system-ui, sans-serif', size: 12 },
                    autosize: true,
                    margin: { t: computedAnnotations.length > 0 ? 30 : 15, b: 40, l: 45, r: 20, pad: 0 },
                    xaxis: {
                      ...chartData.layout?.xaxis,
                      title: null, // Often redundant if clear from chart title, but left to backend preference
                      tickangle: (chartType === 'line' || chartType === 'line_chart') ? 0 : -40,
                      automargin: true,
                      gridcolor: `${colors.border}80`,
                      showgrid: chartType === 'line' || chartType === 'line_chart' || chartType === 'scatter',
                      zeroline: false,
                      linecolor: 'transparent',
                      tickfont: { size: 11, color: colors.textMuted },
                    },
                    yaxis: {
                      ...chartData.layout?.yaxis,
                      automargin: true,
                      gridcolor: `${colors.border}80`,
                      showgrid: true,
                      griddash: 'dash',
                      zeroline: false,
                      linecolor: 'transparent',
                      tickfont: { size: 11, color: colors.textMuted },
                    },
                    hoverlabel: {
                      bgcolor: colors.cardBg,
                      bordercolor: colors.border,
                      font: { color: colors.text, family: 'Inter, system-ui, sans-serif', size: 13 },
                      align: 'left',
                    },
                    annotations: [...computedAnnotations, ...(chartData.layout?.annotations || [])],
                  }}
                  chartType={chartType}
                  colorOffset={colorOffset}
                  config={{
                    responsive: true,
                    displayModeBar: false, // Completely hide Plotly controls for SaaS feel
                    displaylogo: false,
                  }}
                  style={{ width: '100%', height: '100%' }}
                  onPointClick={handlePointClick}
                  chartTitle={component.title}
                  crossFilter={crossFilter}
                />
              )
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
