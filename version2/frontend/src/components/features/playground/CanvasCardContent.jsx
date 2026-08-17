import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart3, Target, FileText, Table,
  Activity, TrendingUp, TrendingDown, Minus,
  AlertCircle, Database, Loader2, Settings,
  ChevronDown, RefreshCw, ChartBar,
} from 'lucide-react';
import { chartAPI } from '../../../services/api';
import { CHART_TYPES, AGG_OPTIONS } from '../../features/charts/chartConstants';
import ChartRenderer from '../../features/charts/ChartRenderer';
import useCanvasStore from '../../../store/canvasStore';
import { cn } from '../../../lib/utils';

/* ─── Color palette for multi-series traces ─── */
const SERIES_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
  '#14b8a6', '#6366f1', '#d946ef', '#84cc16',
];

/* ─── Client-side fallback: build basic chart data from cached preview data ─── */
function buildClientSideChart(
  datasetId, chartType, xColumn, yColumns, aggregation,
  onUpdateConfig
) {
  // Only works if we have cached preview data in the store
  const state = useCanvasStore.getState();
  const rawData = state.linkedDatasetData;
  if (!Array.isArray(rawData) || rawData.length === 0) return false;

  const yColList = yColumns.length > 0 ? yColumns : [];
  if (!xColumn || yColList.length === 0) return false;

  // Verify X column exists
  const hasX = rawData.some(r => r[xColumn] !== undefined && r[xColumn] !== null);
  if (!hasX) return false;

  // Build traces for each Y column
  const traces = [];

  yColList.forEach((yCol, idx) => {
    const hasY = rawData.some(r => r[yCol] !== undefined && r[yCol] !== null);
    if (!hasY) return;

    // Group by X value
    const groupMap = new Map();
    for (const row of rawData) {
      const xVal = row[xColumn];
      const yVal = parseFloat(row[yCol]);
      if (xVal === undefined || xVal === null || isNaN(yVal)) continue;
      const key = String(xVal);
      if (!groupMap.has(key)) groupMap.set(key, { x: xVal, values: [] });
      groupMap.get(key).values.push(yVal);
    }

    // Apply aggregation
    const sortedGroups = [...groupMap.entries()]
      .sort((a, b) => String(a[0]).localeCompare(String(b[0])));
    const categories = [];
    const values = [];

    for (const [, group] of sortedGroups) {
      const vals = group.values;
      categories.push(group.x);
      let agg;
      switch (aggregation) {
        case 'sum': agg = vals.reduce((a, b) => a + b, 0); break;
        case 'mean': agg = vals.reduce((a, b) => a + b, 0) / vals.length; break;
        case 'median': {
          const sorted = [...vals].sort((a, b) => a - b);
          const mid = Math.floor(sorted.length / 2);
          agg = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
          break;
        }
        case 'count': agg = vals.length; break;
        case 'max': agg = Math.max(...vals); break;
        case 'min': agg = Math.min(...vals); break;
        default: agg = vals.reduce((a, b) => a + b, 0) / vals.length;
      }
      values.push(agg);
    }

    const color = SERIES_COLORS[idx % SERIES_COLORS.length];
    const isLineOrArea = chartType === 'line' || chartType === 'multi_line' || chartType === 'area';

    traces.push({
      x: categories,
      y: values,
      type: chartType === 'pie' || chartType === 'donut' ? 'pie' : isLineOrArea ? 'scatter' : 'bar',
      mode: isLineOrArea ? 'lines+markers' : undefined,
      fill: chartType === 'area' ? 'tozeroy' : undefined,
      line: isLineOrArea ? { color, width: 2 } : undefined,
      marker: { color },
      name: yCol,
    });
  });

  // For pie/donut, use the first Y column
  if ((chartType === 'pie' || chartType === 'donut') && traces.length > 0) {
    const first = traces[0];
    traces[0] = {
      labels: first.x,
      values: first.y,
      type: 'pie',
      hole: chartType === 'donut' ? 0.4 : undefined,
      name: yColList[0],
    };
    // Remove extra traces for pie
    traces.splice(1);
  }

  if (traces.length === 0) return false;

  const layout = {
    title: { text: `${yColList.join(' · ')} by ${xColumn}` },
    xaxis: { title: { text: xColumn } },
    yaxis: { title: { text: `${aggregation} of ${yColList.join(', ')}` } },
  };

  onUpdateConfig({
    chartData: traces,
    chartLayout: layout,
    title: `${yColList.join(' · ')} by ${xColumn} (client-side)`,
    __clientSideFallback: true,
  });

  return true;
}


/* ═══════════════════════════════════════════
   Chart Card
   ═══════════════════════════════════════════ */
function ChartCardContent({ config, cardId, isSelected, onUpdateConfig, linkedColumns, linkedDatasetId }) {
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState(null);
  const fetchRef = useRef(null);

  const xColumn = config?.xColumn || '';
  // Resolve Y columns: prefer yColumns[] (multi-select), fallback to yColumn (legacy single-select)
  const yColumns = useMemo(() => {
    if (config?.yColumns && Array.isArray(config.yColumns) && config.yColumns.length > 0) {
      return config.yColumns;
    }
    return config?.yColumn ? [config.yColumn] : [];
  }, [config?.yColumns, config?.yColumn]);

  const chartType = config?.chart_type || 'bar';
  const aggregation = config?.aggregation || 'sum';
  const groupBy = config?.groupBy || null;
  const chartData = config?.chartData || null;
  const chartLayout = config?.chartLayout || null;
  const chartTitle = config?.title || '';

  /* ─── Fetch chart when config changes ─── */
  useEffect(() => {
    if (!linkedDatasetId || !xColumn || yColumns.length === 0) return;

    // Already have chart data cached? Skip the backend call.
    if (chartData && Array.isArray(chartData) && chartData.length > 0) return;

    // Build config key from all parameters that affect the chart
    const yKey = yColumns.join(',');
    const configKey = `${linkedDatasetId}_${chartType}_${xColumn}_${yKey}_${aggregation}_${groupBy || ''}`;
    if (fetchRef.current === configKey) return;

    let cancelled = false;

    const fetchChart = async () => {
      setChartLoading(true);
      setChartError(null);
      fetchRef.current = configKey;

      // Build fields: [x, ...yColumns]
      const fields = [xColumn, ...yColumns];
      const titleText = yColumns.length > 1
        ? `${yColumns.join(' · ')} by ${xColumn}`
        : `${yColumns[0]} by ${xColumn}`;

      try {
        const response = await chartAPI.renderChart(
          linkedDatasetId,
          chartType,
          fields,
          aggregation,
          {
            include_insights: false,
            limit: 5000,
            title: titleText,
            groupBy: groupBy, // Pass groupBy to backend
          }
        );

        if (response.data) {
          const traces = response.data.traces || [];
          const layout = response.data.layout || {};
          const explanation = response.data.explanation || '';

          onUpdateConfig({
            chartData: traces,
            chartLayout: layout,
            title: explanation || titleText,
            __clientSideFallback: false,
          });
        } else {
          setChartError('No data returned from chart API');
        }
      } catch (err) {
        console.error('Chart fetch failed:', err);
        // ── Client-side fallback: build chart from cached preview data ──
        const fallbackBuilt = buildClientSideChart(
          linkedDatasetId, chartType, xColumn, yColumns, aggregation,
          onUpdateConfig
        );
        if (!fallbackBuilt) {
          setChartError(err.response?.data?.detail || err.message || 'Chart generation failed');
        }
      } finally {
        if (!cancelled) setChartLoading(false);
      }
    };

    fetchChart();

    return () => { cancelled = true; };
    // Include yColumns as dependency for proper re-fetch on multi-select changes
  }, [linkedDatasetId, xColumn, yColumns, chartType, aggregation, groupBy, chartData, onUpdateConfig]);

  const hasChart = chartData && Array.isArray(chartData) && chartData.length > 0;

  /** Has a client-side fallback been applied? */
  const isClientSide = config?.__clientSideFallback === true;

  /** Show a note when multiple Y columns are selected */
  const isMultiSeries = yColumns.length > 1;

  /* ─── Render: chart display or error fallback option ─── */
  const renderChartArea = () => {
    if (chartLoading) {
      return (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#3b82f6' }} />
            <span className="text-[11px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
              Generating chart...
            </span>
          </div>
        </div>
      );
    }

    if (chartError && !hasChart) {
      return (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
          <AlertCircle className="w-5 h-5" style={{ color: 'rgba(239,68,68,0.6)' }} />
          <p className="text-[11px]" style={{ color: 'rgba(255,255,255,0.5)' }}>
            {chartError}
          </p>
          {xColumn && yColumns.length > 0 && (
            <button
              onClick={() => {
                fetchRef.current = null;
                onUpdateConfig({ chartData: null, chartLayout: null, __clientSideFallback: false });
              }}
              className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium mt-1"
              style={{ border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}
            >
              <RefreshCw className="w-3 h-3" /> Retry
            </button>
          )}
        </div>
      );
    }

    if (hasChart) {
      return (
        <div className="absolute inset-0 p-1 flex flex-col">
          {isClientSide && (
            <div
              className="text-[9px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-t-md text-center shrink-0"
              style={{ background: 'rgba(251,191,36,0.1)', color: '#f59e0b' }}
            >
              Client-side preview · Backend unavailable
            </div>
          )}
          {isMultiSeries && !isClientSide && (
            <div
              className="text-[9px] font-medium px-2 py-0.5 rounded-t-md text-center shrink-0"
              style={{ background: 'rgba(59,130,246,0.08)', color: '#60a5fa' }}
            >
              {yColumns.length} series · {aggregation}
              {groupBy ? ` · grouped by ${groupBy}` : ''}
            </div>
          )}
          <div className="flex-1 min-h-0">
            <ChartRenderer
              data={chartData}
              layout={chartLayout || {}}
              chartType={chartType}
              chartTitle={chartTitle}
              style={{ width: '100%', height: '100%', minHeight: 0 }}
            />
          </div>
        </div>
      );
    }

    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
        <BarChart3 className="w-6 h-6" style={{ color: 'rgba(255,255,255,0.15)' }} />
        <p className="text-[11px]" style={{ color: 'rgba(255,255,255,0.3)' }}>
          {!linkedDatasetId
            ? 'Link a dataset and configure X/Y axes'
            : yColumns.length === 0
              ? 'Select at least one Y axis column'
              : 'Select X axis to generate chart'}
        </p>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      {/* ─── Chart area ─── */}
      <div className="flex-1 relative min-h-0">
        {renderChartArea()}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   KPI Card
   ═══════════════════════════════════════════ */
function KpiCardContent({ config, linkedDatasetData }) {
  const column = config?.column || '';
  const aggregation = config?.aggregation || 'sum';
  const format = config?.format || 'number';

  // Compute value from linked dataset data
  const computedValue = React.useMemo(() => {
    if (!column || !Array.isArray(linkedDatasetData) || linkedDatasetData.length === 0) return null;
    const values = linkedDatasetData
      .map(r => r[column])
      .filter(v => v !== null && v !== undefined && v !== '')
      .map(v => Number(v))
      .filter(n => !isNaN(n));
    if (values.length === 0) return null;
    switch (aggregation) {
      case 'sum': return values.reduce((a, b) => a + b, 0);
      case 'mean': return values.reduce((a, b) => a + b, 0) / values.length;
      case 'median': {
        const sorted = [...values].sort((a, b) => a - b);
        const mid = Math.floor(sorted.length / 2);
        return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
      }
      case 'count': return values.length;
      case 'max': return Math.max(...values);
      case 'min': return Math.min(...values);
      default: return values.reduce((a, b) => a + b, 0) / values.length;
    }
  }, [column, aggregation, linkedDatasetData]);

  const formatValue = (val) => {
    if (val === null || val === undefined) return '—';
    const num = typeof val === 'string' ? parseFloat(val.replace(/[^0-9.-]/g, '')) : val;
    if (isNaN(num)) return String(val);
    switch (format) {
      case 'currency':
        if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
        if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
        if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(num);
      case 'percentage':
        return `${num.toFixed(1)}%`;
      case 'integer':
        return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(num);
      default:
        if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
        if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
        if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(2)}K`;
        return new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(num);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full text-center gap-1.5 px-4">
      <div className="p-1.5 rounded-lg" style={{ background: 'rgba(16,185,129,0.1)' }}>
        <Target className="w-4 h-4" style={{ color: '#10b981' }} />
      </div>
      {computedValue != null ? (
        <motion.span
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          key={`${computedValue}-${aggregation}`}
          transition={{ type: 'spring', stiffness: 200, damping: 20 }}
          className="text-2xl font-bold tabular-nums tracking-tight"
          style={{ color: 'var(--text-primary)' }}
        >
          {formatValue(computedValue)}
        </motion.span>
      ) : (
        <span className="text-lg font-semibold" style={{ color: 'var(--text-muted)' }}>
          {column ? '—' : 'No metric set'}
        </span>
      )}
      {column && (
        <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--text-muted)' }}>
          <Activity className="w-3 h-3" />
          <span>{aggregation.toUpperCase()} · {column}</span>
        </div>
      )}
      {!linkedDatasetData?.length && (
        <p className="text-[10px] mt-1 px-2 py-0.5 rounded" style={{ background: 'rgba(251,191,36,0.1)', color: '#f59e0b' }}>
          Link a dataset
        </p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════
   Text Card
   ═══════════════════════════════════════════ */
function TextCardContent({ config }) {
  const content = config?.content || '';
  const lines = content.split('\n');

  return (
    <div className="h-full overflow-y-auto px-4 py-3">
      <div className="space-y-0.5">
        {lines.map((line, i) => {
          if (line.startsWith('## ')) {
            return <h2 key={i} className="text-sm font-bold mt-2 first:mt-0" style={{ color: 'var(--text-primary)' }}>{line.slice(3)}</h2>;
          }
          if (line.startsWith('# ')) {
            return <h1 key={i} className="text-base font-bold mt-2 first:mt-0" style={{ color: 'var(--text-primary)' }}>{line.slice(2)}</h1>;
          }
          if (line.startsWith('**') && line.endsWith('**')) {
            return <p key={i} className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{line.slice(2, -2)}</p>;
          }
          if (line.startsWith('- ')) {
            return <li key={i} className="text-xs ml-3" style={{ color: 'var(--text-secondary)' }}>{line.slice(2)}</li>;
          }
          if (line.trim() === '') {
            return <div key={i} className="h-2" />;
          }
          const parts = line.split(/(\*\*[^*]+\*\*)/g);
          return (
            <p key={i} className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {parts.map((part, j) =>
                part.startsWith('**') && part.endsWith('**')
                  ? <strong key={j} style={{ color: 'var(--text-primary)' }}>{part.slice(2, -2)}</strong>
                  : part
              )}
            </p>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   Table Card
   ═══════════════════════════════════════════ */
function TableCardContent({ config, linkedDatasetData }) {
  const columns = config?.columns || [];
  const limit = config?.limit || 50;
  const data = Array.isArray(linkedDatasetData) ? linkedDatasetData.slice(0, limit) : [];

  if (!data.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: 'rgba(139,92,246,0.1)' }}>
          <Table className="w-5 h-5" style={{ color: '#8b5cf6' }} />
        </div>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Link a dataset to view data
        </p>
      </div>
    );
  }

  const displayColumns = columns.length > 0
    ? columns
    : data.length > 0
      ? Object.keys(data[0]).filter(k => k !== '_id').slice(0, 8)
      : [];

  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            {displayColumns.map((col) => (
              <th
                key={col}
                className="text-left font-medium px-3 py-2 sticky top-0 whitespace-nowrap"
                style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)' }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={i}
              className="transition-colors"
              style={{
                borderBottom: '1px solid var(--border)',
                background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
              }}
            >
              {displayColumns.map((col) => {
                const val = row[col];
                const display = val != null ? String(val) : '—';
                return (
                  <td
                    key={col}
                    className="px-3 py-1.5 truncate max-w-[160px]"
                    style={{ color: 'var(--text-secondary)' }}
                    title={display}
                  >
                    {display}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length >= limit && (
        <div className="text-center py-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
          Showing {limit} of {data.length}+ rows
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════
   CanvasCardContent — dispatcher
   ═══════════════════════════════════════════ */
function CanvasCardContent({ card, isSelected }) {
  const linkedDatasetData = useCanvasStore((s) => s.linkedDatasetData);
  const linkedDatasetId = useCanvasStore((s) => s.linkedDatasetId);
  const getLinkedColumns = useCanvasStore((s) => s.getLinkedColumns);

  const linkedColumns = getLinkedColumns();

  const handleUpdateConfig = useCallback((patch) => {
    useCanvasStore.getState().updateCardConfig(card.id, patch);
  }, [card.id]);

  switch (card.type) {
    case 'chart':
      return (
        <ChartCardContent
          config={card.config}
          cardId={card.id}
          isSelected={isSelected}
          onUpdateConfig={handleUpdateConfig}
          linkedColumns={linkedColumns}
          linkedDatasetId={linkedDatasetId}
        />
      );
    case 'kpi':
      return <KpiCardContent config={card.config} linkedDatasetData={linkedDatasetData} />;
    case 'text':
      return <TextCardContent config={card.config} />;
    case 'table':
      return <TableCardContent config={card.config} linkedDatasetData={linkedDatasetData} />;
    default:
      return (
        <div className="flex items-center justify-center h-full text-xs" style={{ color: 'var(--text-muted)' }}>
          Unknown card type
        </div>
      );
  }
}

export default CanvasCardContent;
