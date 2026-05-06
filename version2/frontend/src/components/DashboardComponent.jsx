import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart3, Layers, AlertCircle, RefreshCw, Loader2, HelpCircle, ChevronDown, ChevronUp
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import PlotlyChart from './features/charts/PlotlyChart';
import EnterpriseKpiCard from './ui/EnterpriseKpiCard';
import useDatasetStore from '../store/datasetStore';
import { getAuthToken, chartAPI } from '../services/api';
import { useChartTheme } from '../hooks/useChartTheme';
import useDashboardActionStore from '../store/dashboardActionStore';
import CorrelationMatrix from './features/analysis/CorrelationMatrix';
import DistributionComparison from './features/analysis/DistributionComparison';

const MotionDiv = motion.div;

const getChartHeight = (type, variant) => {
  // Fixed height per variant eliminates gaps and ensures aligned grid
  // No dynamic multipliers or bonuses — consistent alignment
  const fixedHeights = {
    hero: 420,
    featured: 380,
    standard: 380,
    compact: 360,
  };
  return fixedHeights[variant] || 380;
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
  const autoRetryAttemptedRef = useRef(false);
  const clickTimeout = useRef(null);
  const { colors } = useChartTheme();
  const { crossFilter, setCrossFilter } = useDashboardActionStore();

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

  const chartData = useMemo(() => normalizePlotlyChartData(component), [component]);
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
        font: { size: 11, color: colors.primary, family: 'IBM Plex Sans, sans-serif' },
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
        font: { size: 10, color: colors.warning, family: 'IBM Plex Sans, sans-serif' },
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

  const { selectedDataset } = useDatasetStore();

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
        if (!silent) toast.error(err.detail || 'Failed to load chart', { duration: 3000 });
      }
    } catch (e) {
      console.error('Retry chart failed:', e);
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
        <EnterpriseKpiCard
          title={component.title}
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
          sparklineData={component.sparklineData || component.sparkline_data || []}
          topValues={component.topValues || null}
          recordCount={component.recordCount ?? component.record_count ?? null}
          datasetData={datasetData}
          unitPrefix={component.unitPrefix || component.unit_prefix || null}
          unitSuffix={component.unitSuffix || component.unit_suffix || null}
          status={component.status}
          icon={component.icon || 'BarChart3'}
          animationDelay={0}
          accentColor={component.accentColor || component.accent_color || null}
          actionPrompt={component.actionPrompt || component.action_prompt || null}
        />
      );

    case 'chart': {
      return (
        <MotionDiv
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-xl border flex flex-col transition-all duration-300"
          style={{
            background: colors.cardBg,
            borderColor: colors.border,
          }}
        >
          {/* Card header */}
          <div
            className="px-4 pt-3 pb-2.5 flex items-center justify-between gap-3 shrink-0"
            style={{ borderBottom: `1px solid ${colors.border}` }}
          >
            <div className="flex items-center gap-2 min-w-0">
              <BarChart3
                className="w-3.5 h-3.5 shrink-0"
                style={{ color: colors.primary, opacity: 0.7 }}
              />
              <h3
                className="font-semibold text-sm truncate"
                style={{ fontFamily: 'Manrope, sans-serif', color: colors.text }}
              >
                {component.title || 'Chart'}
              </h3>
            </div>
            <button
              onClick={handleExplainChart}
              disabled={explanationLoading || !hasData}
              className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-all duration-200 shrink-0"
              style={{
                background: explanationExpanded ? `${colors.primary}15` : `${colors.primary}08`,
                border: `1px solid ${explanationExpanded ? colors.primary : colors.border}`,
                color: explanationExpanded ? colors.primary : colors.textMuted,
                opacity: !hasData ? 0.5 : 1,
              }}
              title="Get AI explanation for this chart"
            >
              {explanationLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <HelpCircle className="w-3.5 h-3.5" />
              )}
              <span className="hidden sm:inline">Explain</span>
            </button>
          </div>

          {/* Explanation panel */}
          <AnimatePresence>
            {explanationExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden shrink-0"
              >
                <div className="px-4 py-3">
                  <div
                    className="rounded-lg p-3 text-xs leading-relaxed border"
                    style={{
                      background: `${colors.primary}08`,
                      borderColor: `${colors.primary}20`,
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
                      <div className="flex items-center justify-between">
                        <p>Unable to generate explanation. Please try again.</p>
                        <button
                          onClick={handleExplainChart}
                          className="px-2 py-1 text-[10px] font-medium rounded bg-accent-primary/10 text-accent-primary hover:bg-accent-primary/20 transition-colors"
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

          {/* Chart body — explicit height so Plotly's height:100% resolves correctly */}
          <div className="px-3 py-2" style={{ height: `${chartHeight}px` }}>
            {hasData ? (
              isAnalyticsComponent ? (
                <div className="h-full">
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
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    font: { color: colors.textMuted, family: 'IBM Plex Sans, sans-serif', size: 11 },
                    autosize: true,
                    margin: { t: computedAnnotations.length > 0 ? 40 : 8, b: 30, l: 50, r: 16, pad: 4 },
                    xaxis: {
                      ...chartData.layout?.xaxis,
                      tickangle: (chartType === 'line' || chartType === 'line_chart') ? 0 : -40,
                      automargin: true,
                      gridcolor: colors.gridColor,
                      showgrid: chartType === 'line' || chartType === 'line_chart',
                      linecolor: colors.axisLine,
                      tickfont: { size: 10 },
                    },
                    yaxis: {
                      ...chartData.layout?.yaxis,
                      automargin: true,
                      gridcolor: colors.gridColor,
                      showgrid: true,
                      griddash: 'dot',
                      zerolinecolor: colors.border,
                      linecolor: colors.axisLine,
                      tickfont: { size: 10 },
                    },
                    hoverlabel: {
                      bgcolor: colors.hoverBg,
                      bordercolor: colors.hoverBorder,
                      font: { color: colors.text, family: 'IBM Plex Sans, sans-serif', size: 12 },
                    },
                    annotations: [...computedAnnotations, ...(chartData.layout?.annotations || [])],
                  }}
                  chartType={chartType}
                  colorOffset={colorOffset}
                  config={{
                    responsive: true,
                    displayModeBar: 'hover',
                    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'sendDataToCloud', 'autoScale2d'],
                    displaylogo: false,
                    toImageButtonOptions: {
                      format: 'png',
                      filename: component.title?.replace(/\s+/g, '_') || 'chart',
                      scale: 2,
                    },
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
                <div className="text-center space-y-1.5">
                  <p className="text-xs" style={{ color: colors.text }}>Chart unavailable</p>
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
      const tableData = component.table_data || [];
      const columns = tableData.length > 0 ? Object.keys(tableData[0]) : [];

      return (
        <MotionDiv
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-xl border col-span-1 lg:col-span-12 transition-all duration-300"
          style={{
            background: colors.cardBg,
            borderColor: colors.border,
          }}
        >
          <div className="px-5 pt-4 pb-3" style={{ borderBottom: `1px solid ${colors.border}` }}>
            <h3
              className="font-semibold text-sm"
              style={{ fontFamily: 'Manrope, sans-serif', color: colors.text }}
            >
              {component.title}
            </h3>
          </div>
          <div className="overflow-x-auto p-4">
            {tableData.length > 0 ? (
              <table className="w-full text-sm text-left">
                <thead className="text-[11px] uppercase tracking-wider" style={{ color: colors.textMuted }}>
                  <tr style={{ background: `${colors.text}05` }}>
                    {columns.map(col => (
                      <th key={col} className="px-4 py-3 font-medium" scope="col">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.map((row, i) => (
                    <tr key={i} className="transition-colors duration-150" style={{ borderBottom: `1px solid ${colors.border}` }}>
                      {columns.map(col => (
                        <td key={col} className="px-4 py-3 truncate max-w-50 tabular-nums" style={{ color: colors.textMuted }}>{String(row[col])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-center py-10" style={{ color: colors.textMuted }} role="status">No data available</div>
            )}
          </div>
        </MotionDiv>
      );
    }

    default:
      return null;
  }
};

export default DashboardComponent;
