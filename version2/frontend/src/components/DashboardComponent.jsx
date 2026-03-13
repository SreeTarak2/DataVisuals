import React, { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp, TrendingDown, Database, Users, FileText, BarChart3,
  PieChart, LineChart, Activity, DollarSign, Target, Zap,
  Lightbulb, Eye, Sparkles, ChevronRight, Layers, AlertCircle,
  RefreshCw, Loader2
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import PlotlyChart from './features/charts/PlotlyChart';
import EnterpriseKpiCard from './ui/EnterpriseKpiCard';
import useDatasetStore from '../store/datasetStore';
import { getAuthToken } from '../services/api';

const COLORS = ['#06b6d4', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#fb923c', '#84cc16', '#ec4899'];

// Exported for external consumers (e.g. other dashboards)
export const getGridClass = (type, data) => {
  switch (type) {
    case 'line':
    case 'line_chart':
    case 'area':
    case 'multi_bar':
      return 'col-span-1 lg:col-span-12';
    case 'scatter':
    case 'scatter_plot':
    case 'heatmap':
      return 'col-span-1 lg:col-span-8';
    case 'pie':
    case 'pie_chart':
    case 'donut':
      return 'col-span-1 lg:col-span-4';
    case 'bar':
    case 'bar_chart':
    case 'histogram':
    case 'box':
    case 'box_plot':
    case 'violin':
      const rowCount = data?.length || 0;
      return rowCount > 10 ? 'col-span-1 lg:col-span-8' : 'col-span-1 lg:col-span-6';
    default:
      return 'col-span-1 lg:col-span-6';
  }
};

// Height classes — bento variant takes priority, then chart type fallback
const getChartHeightClass = (type, variant) => {
  // Variant from bento layout engine
  if (variant === 'hero') return 'h-[380px] sm:h-[440px] md:h-[520px]';
  if (variant === 'compact') return 'h-[220px] sm:h-[260px] md:h-[300px]';
  if (variant === 'featured') return 'h-[300px] sm:h-[360px] md:h-[420px]';

  // Fallback: chart-type based
  switch (type) {
    case 'line':
    case 'line_chart':
    case 'area':
    case 'multi_bar':
      return 'h-[320px] sm:h-[380px] md:h-[440px]';
    case 'pie':
    case 'pie_chart':
    case 'donut':
      return 'h-[240px] sm:h-[280px] md:h-[320px]';
    default:
      return 'h-[280px] sm:h-[340px] md:h-[400px]';
  }
};

// Chart type accent colors — gives each chart a visual identity
const getChartAccent = (type) => {
  switch (type) {
    case 'line':
    case 'line_chart':
    case 'area':
      return { border: 'border-t-cyan-500', bg: 'bg-cyan-500/10', text: 'text-cyan-400', dot: 'bg-cyan-400' };
    case 'bar':
    case 'bar_chart':
    case 'histogram':
    case 'grouped_bar':
      return { border: 'border-t-violet-500', bg: 'bg-violet-500/10', text: 'text-violet-400', dot: 'bg-violet-400' };
    case 'pie':
    case 'pie_chart':
    case 'donut':
      return { border: 'border-t-emerald-500', bg: 'bg-emerald-500/10', text: 'text-emerald-400', dot: 'bg-emerald-400' };
    case 'scatter':
    case 'scatter_plot':
      return { border: 'border-t-amber-500', bg: 'bg-amber-500/10', text: 'text-amber-400', dot: 'bg-amber-400' };
    case 'box_plot':
    case 'box':
    case 'violin':
      return { border: 'border-t-rose-500', bg: 'bg-rose-500/10', text: 'text-rose-400', dot: 'bg-rose-400' };
    case 'heatmap':
      return { border: 'border-t-orange-500', bg: 'bg-orange-500/10', text: 'text-orange-400', dot: 'bg-orange-400' };
    default:
      return { border: 'border-t-slate-500', bg: 'bg-slate-500/10', text: 'text-slate-400', dot: 'bg-slate-400' };
  }
};

// Friendly chart type display names
const getChartTypeLabel = (type) => {
  const labels = {
    'bar': 'Bar Chart', 'bar_chart': 'Bar Chart',
    'line': 'Line Chart', 'line_chart': 'Line Chart',
    'pie': 'Pie Chart', 'pie_chart': 'Pie Chart',
    'scatter': 'Scatter Plot', 'scatter_plot': 'Scatter Plot',
    'histogram': 'Histogram', 'box_plot': 'Box Plot', 'box': 'Box Plot',
    'violin': 'Violin Plot', 'heatmap': 'Heatmap',
    'area': 'Area Chart', 'donut': 'Donut Chart',
    'grouped_bar': 'Grouped Bar', 'treemap': 'Treemap',
  };
  return labels[type] || 'Chart';
};

const DashboardComponent = ({ component: initialComponent, datasetData, variant }) => {
  const [component, setComponent] = useState(initialComponent);
  const [retrying, setRetrying] = useState(false);

  // Sync with parent when the initial component changes (e.g. dashboard regeneration)
  useEffect(() => {
    setComponent(initialComponent);
  }, [initialComponent]);

  const chartType = component.config?.chart_type?.toLowerCase() || '';
  const chartHeightClass = getChartHeightClass(chartType, variant);
  const accent = getChartAccent(chartType);

  const [showExplanation, setShowExplanation] = useState(false);
  const { selectedDataset } = useDatasetStore();

  // Per-chart retry handler — re-hydrates only this chart
  const handleRetryChart = useCallback(async () => {
    if (!selectedDataset?.id || retrying) return;
    setRetrying(true);
    try {
      const token = getAuthToken();
      const res = await fetch(`/api/ai/${selectedDataset.id}/retry-chart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ component }),
      });
      if (res.ok) {
        const result = await res.json();
        if (result.success && result.chart_data) {
          setComponent(prev => ({ ...prev, chart_data: result.chart_data }));
          // Save chart to dashboard after retry
          try {
            const { chartAPI } = await import('../services/api');
            await chartAPI.saveChart(selectedDataset.id, component.config, component.title);
            toast.success('Chart loaded and saved!', { duration: 2000, style: { background: '#1e293b', color: '#e2e8f0', border: '1px solid rgba(52, 211, 153, 0.3)', fontSize: '13px' } });
          } catch (saveErr) {
            toast.error('Chart loaded, but failed to save.', { duration: 3000 });
          }
        } else {
          toast.error('Chart data still unavailable', { duration: 3000 });
        }
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Failed to load chart', { duration: 3000 });
      }
    } catch (e) {
      console.error('Retry chart failed:', e);
      toast.error('Network error — could not retry', { duration: 3000 });
    } finally {
      setRetrying(false);
    }
  }, [selectedDataset, component, retrying]);

  // Chart drill-down handler
  const handlePointClick = useCallback((clickData) => {
    const xLabel = clickData.x !== null ? String(clickData.x) : '';
    const yLabel = clickData.y !== null ? (typeof clickData.y === 'number' ? clickData.y.toLocaleString() : String(clickData.y)) : '';
    const series = clickData.seriesName ? ` (${clickData.seriesName})` : '';

    toast(
      `📊 ${xLabel}: ${yLabel}${series}`,
      {
        duration: 3000,
        style: {
          background: '#1e293b',
          color: '#e2e8f0',
          border: '1px solid rgba(6, 182, 212, 0.3)',
          fontSize: '13px',
        },
        icon: '🔍',
      }
    );
  }, []);

  switch (component.type) {
    case 'kpi':
      return (
        <EnterpriseKpiCard
          title={component.title}
          value={component.value ?? 0}
          format={component.format || 'number'}
          comparisonValue={component.comparisonValue ?? null}
          comparisonLabel={component.comparisonLabel || null}
          deltaPercent={component.deltaPercent ?? null}
          targetValue={component.targetValue}
          targetLabel={component.targetLabel}
          sparklineData={component.sparklineData || []}
          topValues={component.topValues || null}
          recordCount={component.recordCount ?? null}
          status={component.status}
          icon={component.icon || 'BarChart3'}
          animationDelay={0}
        />
      );

    case 'chart': {
      const chartData = component.chart_data || { data: [], layout: {} };
      const hasData = Array.isArray(chartData.data) && chartData.data.some((trace) => {
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
      const noveltyScore = component.config?.novelty_score;
      const explanation = component.metadata?.explanation;
      const keyInsights = component.metadata?.key_insights || [];
      const readingGuide = component.metadata?.reading_guide;
      const reasoning = component.metadata?.reasoning;
      const hasAIContent = explanation || keyInsights.length > 0 || readingGuide;

      const getInsightText = (insight) =>
        typeof insight === 'string' ? insight : insight?.text || insight?.label || '';

      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`relative overflow-hidden bg-[#0f172a] border border-slate-800/80 ${variant === 'hero' ? 'border-t-[3px]' : 'border-t-2'} ${accent.border} rounded-xl h-full group
            ${variant === 'hero'
              ? 'shadow-[0_8px_40px_rgba(0,0,0,0.3)] ring-1 ring-white/[0.04]'
              : 'shadow-[0_4px_24px_rgba(0,0,0,0.15)]'
            } hover:shadow-[0_12px_48px_rgba(0,0,0,0.3)] hover:border-slate-700/80 hover:-translate-y-0.5
            transition-all duration-300`}
          aria-labelledby={`chart-title-${component.title?.replace(/\s+/g, '-')}`}
        >
          {/* ── Card Header ── */}
          <div className="px-5 pt-4 pb-3 flex justify-between items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2.5 mb-1">
                <h3
                  id={`chart-title-${component.title?.replace(/\s+/g, '-')}`}
                  className={`font-semibold text-slate-100 leading-snug truncate ${variant === 'hero' ? 'text-base sm:text-lg' : 'text-[15px]'}`}
                >
                  {component.title}
                </h3>
                {noveltyScore > 0.6 && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider bg-purple-500/15 text-purple-400 border border-purple-500/20 flex items-center gap-1 shrink-0">
                    <Sparkles className="w-2.5 h-2.5" aria-hidden="true" /> Novel
                  </span>
                )}
              </div>
              {/* Chart type badge + rows pill in one line */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium ${accent.bg} ${accent.text} border border-current/10`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${accent.dot}`} />
                  {getChartTypeLabel(chartType)}
                </span>
                {hasData && chartData.rows_used > 0 && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-800/60 text-slate-400 border border-slate-700/40">
                    <Layers className="w-2.5 h-2.5" aria-hidden="true" />
                    {chartData.rows_used?.toLocaleString()} rows
                  </span>
                )}
              </div>
            </div>

            {/* AI Insights toggle */}
            {hasAIContent && (
              <button
                onClick={() => setShowExplanation(!showExplanation)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/50 shrink-0
                  ${showExplanation
                    ? 'bg-amber-500/20 border border-amber-500/40 text-amber-300'
                    : 'bg-slate-800/60 border border-slate-700/50 text-slate-400 hover:bg-amber-500/10 hover:text-amber-400 hover:border-amber-500/30'
                  }`}
                aria-label="Toggle AI Insights"
                aria-expanded={showExplanation}
                aria-controls={`explanation-${component.title?.replace(/\s+/g, '-')}`}
              >
                <Lightbulb className="w-3 h-3" aria-hidden="true" />
                <span className="hidden sm:inline">Insights</span>
              </button>
            )}
          </div>

          {/* ── Inline AI Insight (always visible when collapsed) ── */}
          {hasAIContent && keyInsights.length > 0 && !showExplanation && (
            <div className="mx-5 mb-2 px-3 py-2 rounded-lg bg-slate-800/40 border border-slate-700/30">
              <div className="flex items-start gap-2">
                <Lightbulb className="w-3.5 h-3.5 text-amber-500/80 shrink-0 mt-0.5" aria-hidden="true" />
                <p className="text-[13px] text-slate-300 leading-relaxed line-clamp-2">
                  {getInsightText(keyInsights[0])}
                  {keyInsights.length > 1 && (
                    <button
                      onClick={() => setShowExplanation(true)}
                      className="text-amber-400/80 hover:text-amber-300 ml-1.5 font-medium inline-flex items-center gap-0.5 transition-colors"
                    >
                      +{keyInsights.length - 1} more <ChevronRight className="w-3 h-3" />
                    </button>
                  )}
                </p>
              </div>
            </div>
          )}

          {/* ── Chart Area ── */}
          <div className={`${chartHeightClass} w-full px-2 pb-2 sm:px-4 sm:pb-4`}>
            {hasData ? (
              <PlotlyChart
                data={chartData.data}
                layout={{
                  ...chartData.layout,
                  paper_bgcolor: 'rgba(0,0,0,0)',
                  plot_bgcolor: 'rgba(0,0,0,0)',
                  font: { color: '#94a3b8', family: 'Inter, sans-serif', size: 12 },
                  autosize: true,
                  margin: { t: 10, b: 60, l: 50, r: 20, pad: 4 },
                  xaxis: {
                    ...chartData.layout?.xaxis,
                    tickangle: (chartType === 'line' || chartType === 'line_chart') ? 0 : -45,
                    automargin: true,
                    gridcolor: 'rgba(255,255,255,0.05)',
                    showgrid: chartType === 'line' || chartType === 'line_chart',
                    linecolor: 'rgba(255,255,255,0.06)',
                  },
                  yaxis: {
                    ...chartData.layout?.yaxis,
                    automargin: true,
                    gridcolor: 'rgba(255,255,255,0.06)',
                    showgrid: true,
                    griddash: 'dot',
                    zerolinecolor: 'rgba(255,255,255,0.08)',
                    linecolor: 'rgba(255,255,255,0.06)',
                  },
                  hoverlabel: {
                    bgcolor: '#1e293b',
                    bordercolor: '#334155',
                    font: { color: '#f8fafc', family: 'Inter, sans-serif', size: 12 }
                  }
                }}
                chartType={chartType}
                config={{
                  responsive: true,
                  displayModeBar: 'hover',
                  modeBarButtonsToRemove: ['lasso2d', 'select2d', 'sendDataToCloud', 'autoScale2d'],
                  displaylogo: false,
                  toImageButtonOptions: {
                    format: 'png',
                    filename: component.title?.replace(/\s+/g, '_') || 'chart',
                    scale: 2
                  }
                }}
                style={{ width: '100%', height: '100%' }}
                onPointClick={handlePointClick}
              />
            ) : (
              /* ── Friendly Empty State with Retry ── */
              <div className="flex flex-col items-center justify-center h-full space-y-3 px-4" role="status">
                <div className={`p-4 rounded-2xl ${accent.bg} border border-current/10`}>
                  <AlertCircle className={`w-7 h-7 ${accent.text} opacity-60`} />
                </div>
                <div className="text-center space-y-1.5">
                  <p className="text-sm font-medium text-slate-300">Chart data unavailable</p>
                  <p className="text-xs text-slate-500 max-w-[240px] leading-relaxed">
                    This visualization couldn't load on the first attempt.
                  </p>
                  <button
                    onClick={handleRetryChart}
                    disabled={retrying}
                    className={`
                      inline-flex items-center gap-1.5 px-3.5 py-1.5 mt-2 rounded-lg text-xs font-medium
                      border transition-all duration-200
                      ${retrying
                        ? 'bg-slate-800/60 border-slate-700/40 text-slate-500 cursor-wait'
                        : `${accent.bg} border-current/20 ${accent.text} hover:brightness-125 hover:scale-[1.02] active:scale-[0.98]`
                      }
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500
                    `}
                  >
                    {retrying ? (
                      <><Loader2 className="w-3 h-3 animate-spin" /> Retrying…</>
                    ) : (
                      <><RefreshCw className="w-3 h-3" /> Retry this chart</>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ── Expanded AI Insights Panel ── */}
          {hasAIContent && (
            <AnimatePresence>
              {showExplanation && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25, ease: 'easeInOut' }}
                  className="overflow-hidden"
                >
                  <div
                    id={`explanation-${component.title?.replace(/\s+/g, '-')}`}
                    className="border-t border-slate-800/60 bg-gradient-to-b from-slate-800/30 to-transparent p-5 space-y-4"
                  >
                    {/* Explanation */}
                    {explanation && (
                      <div className="flex gap-3 items-start">
                        <div className="p-1.5 rounded-lg bg-amber-500/15 shrink-0 mt-0.5">
                          <Lightbulb className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
                        </div>
                        <p className="text-[15px] text-slate-300 font-semibold leading-relaxed">{explanation}</p>
                      </div>
                    )}

                    {/* Key Insights as mini-cards */}
                    {keyInsights.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-[13px] font-bold text-slate-500 uppercase tracking-wider">Key Findings</h4>
                        <div className="grid gap-2">
                          {keyInsights.map((insight, idx) => (
                            <div
                              key={idx}
                              className="flex items-start gap-2.5 px-3 py-2.5 rounded-lg bg-slate-800/40 border border-slate-700/30"
                            >
                              <span className={`w-1.5 h-1.5 rounded-full ${accent.dot} mt-1.5 shrink-0`} />
                              <p className="text-[14px] text-slate-300 leading-relaxed">
                                {getInsightText(insight)}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Reading Guide */}
                    {readingGuide && (
                      <div className="flex items-start gap-2.5 px-3 py-2.5 rounded-lg bg-cyan-500/5 border border-cyan-500/15">
                        <Eye className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" aria-hidden="true" />
                        <p className="text-[12px] text-slate-300 leading-relaxed">
                          <span className="font-semibold text-cyan-300">How to read: </span>
                          {readingGuide}
                        </p>
                      </div>
                    )}

                    {reasoning && !explanation && (
                      <p className="text-[11px] text-slate-500 italic">{reasoning}</p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          )}
        </motion.div>
      );
    }

    case 'table': {
      const tableData = component.table_data || [];
      const columns = tableData.length > 0 ? Object.keys(tableData[0]) : [];

      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden bg-[#0f172a] border border-slate-800/80 border-t-2 border-t-slate-600 rounded-xl col-span-1 lg:col-span-12
            shadow-[0_4px_24px_rgba(0,0,0,0.15)] hover:shadow-[0_8px_40px_rgba(0,0,0,0.25)] hover:border-slate-700/80
            transition-all duration-300"
          aria-labelledby={`table-title-${component.title?.replace(/\s+/g, '-')}`}
        >
          <div className="px-5 pt-4 pb-3 border-b border-slate-800/60">
            <h3
              id={`table-title-${component.title?.replace(/\s+/g, '-')}`}
              className="font-semibold text-slate-100 text-[15px]"
            >
              {component.title}
            </h3>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-800/60 text-slate-400 border border-slate-700/40 mt-1.5">
              <Layers className="w-2.5 h-2.5" aria-hidden="true" />
              {tableData.length} rows
            </span>
          </div>
          <div className="overflow-x-auto p-4">
            {tableData.length > 0 ? (
              <table className="w-full text-sm text-left text-slate-400">
                <thead className="text-[11px] text-slate-500 uppercase tracking-wider bg-slate-800/30">
                  <tr>
                    {columns.map(col => (
                      <th key={col} className="px-4 py-3 font-medium" scope="col">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.map((row, i) => (
                    <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/20 transition-colors duration-150">
                      {columns.map(col => (
                        <td key={col} className="px-4 py-3 truncate max-w-[200px] tabular-nums">{String(row[col])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-center py-10 text-slate-500" role="status">No data available</div>
            )}
          </div>
        </motion.div>
      );
    }

    default:
      return null;
  }
};

export default DashboardComponent;
