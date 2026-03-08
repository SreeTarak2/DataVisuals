import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Search,
  Bell,
  Share2,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  Plus,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Bar,
  Line,
  ReferenceLine,
  ReferenceDot,
} from 'recharts';
import useDatasetStore from '../../store/datasetStore';
import { cn } from '../../lib/utils';
import './ChartsStudioNextPage.css';

const MotionArticle = motion.article;

const STACK_META = {
  completed: { label: 'Completed', color: '#0E6E6C' },
  processing: { label: 'Processing', color: '#23A29B' },
  pending: { label: 'Pending', color: '#7AD5C4' },
  returned: { label: 'Returns', color: '#E57C6F' },
};

const TYPE_META = {
  number: { label: 'Number', className: 'studio-next-pill-number' },
  date: { label: 'Date', className: 'studio-next-pill-date' },
  text: { label: 'Text', className: 'studio-next-pill-text' },
  calculated: { label: 'Calc', className: 'studio-next-pill-calculated' },
};

const MONTHLY_SERIES = [
  { month: 'Jan', completed: 168, processing: 42, pending: 33, returned: 16, priorYearTotal: 212, revenue: 410000, priorRevenue: 368000 },
  { month: 'Feb', completed: 174, processing: 48, pending: 30, returned: 17, priorYearTotal: 220, revenue: 426000, priorRevenue: 381000 },
  { month: 'Mar', completed: 182, processing: 50, pending: 35, returned: 24, priorYearTotal: 228, revenue: 439000, priorRevenue: 395000 },
  { month: 'Apr', completed: 196, processing: 47, pending: 29, returned: 18, priorYearTotal: 234, revenue: 462000, priorRevenue: 412000 },
  { month: 'May', completed: 204, processing: 54, pending: 27, returned: 16, priorYearTotal: 246, revenue: 475000, priorRevenue: 426000 },
  { month: 'Jun', completed: 216, processing: 53, pending: 25, returned: 15, priorYearTotal: 252, revenue: 498000, priorRevenue: 442000 },
  { month: 'Jul', completed: 224, processing: 55, pending: 24, returned: 14, priorYearTotal: 261, revenue: 516000, priorRevenue: 460000 },
  { month: 'Aug', completed: 232, processing: 58, pending: 23, returned: 13, priorYearTotal: 270, revenue: 538000, priorRevenue: 474000 },
  { month: 'Sep', completed: 241, processing: 61, pending: 26, returned: 15, priorYearTotal: 278, revenue: 554000, priorRevenue: 491000 },
  { month: 'Oct', completed: 258, processing: 66, pending: 30, returned: 18, priorYearTotal: 294, revenue: 592000, priorRevenue: 526000 },
  { month: 'Nov', completed: 304, processing: 72, pending: 34, returned: 20, priorYearTotal: 326, revenue: 684000, priorRevenue: 589000 },
  { month: 'Dec', completed: 286, processing: 64, pending: 29, returned: 17, priorYearTotal: 306, revenue: 639000, priorRevenue: 557000 },
];

const FALLBACK_FIELDS = [
  { name: 'order_month', type: 'date' },
  { name: 'order_status', type: 'text' },
  { name: 'region', type: 'text' },
  { name: 'segment', type: 'text' },
  { name: 'sales_channel', type: 'text' },
  { name: 'total_revenue', type: 'number' },
  { name: 'avg_order_value', type: 'number' },
  { name: 'completed_orders', type: 'number' },
  { name: 'return_rate', type: 'calculated' },
  { name: 'growth_vs_prior', type: 'calculated' },
];

const VIEW_TABS = [
  { id: 'exec', label: 'Executive Summary', preview: [42, 58, 72, 84, 95, 88], description: 'KPI strip + monthly stack + AI narrative' },
  { id: 'returns', label: 'Returns Drill', preview: [22, 31, 54, 28, 26, 20], description: 'Highlights return anomalies and key cohorts' },
  { id: 'segments', label: 'Segment Mix', preview: [34, 48, 57, 63, 67, 74], description: 'Compares segment-level revenue contribution' },
];

const SUGGESTED_QUESTIONS = [
  'Which segment drove the November spike?',
  'Why did returns peak in March?',
  'What explains order softness in early Q2?',
  'Forecast next quarter with current run rate',
];

const formatCompactCurrency = (value) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);

const formatCompactNumber = (value) =>
  new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);

const formatDelta = (value) => `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;

const parseFieldType = (rawType, name) => {
  const fieldName = String(name || '').toLowerCase();
  const normalized = String(rawType || '').toLowerCase();

  if (fieldName.includes('rate') || fieldName.includes('ratio') || fieldName.includes('growth')) {
    return 'calculated';
  }

  if (
    normalized.includes('int') ||
    normalized.includes('float') ||
    normalized.includes('double') ||
    normalized.includes('decimal') ||
    normalized.includes('number') ||
    normalized.includes('measure')
  ) {
    return 'number';
  }

  if (
    normalized.includes('date') ||
    normalized.includes('time') ||
    fieldName.includes('date') ||
    fieldName.includes('month') ||
    fieldName.includes('year')
  ) {
    return 'date';
  }

  if (normalized.includes('calc') || normalized.includes('derived') || normalized.includes('formula')) {
    return 'calculated';
  }

  return 'text';
};

const normalizeColumnMetadata = (metadata) => {
  if (!metadata) return FALLBACK_FIELDS;

  if (Array.isArray(metadata) && metadata.length > 0) {
    return metadata.map((column, index) => {
      const name = typeof column === 'string'
        ? column
        : column?.name || column?.column_name || column?.field || `field_${index + 1}`;
      const rawType = typeof column === 'string'
        ? ''
        : column?.type || column?.data_type || column?.dtype || column?.semantic_type;
      return { name, type: parseFieldType(rawType, name) };
    });
  }

  if (typeof metadata === 'object') {
    const entries = Object.entries(metadata);
    if (entries.length === 0) return FALLBACK_FIELDS;
    return entries.map(([name, value]) => {
      const rawType = typeof value === 'string' ? value : value?.type || value?.data_type || value?.dtype;
      return { name, type: parseFieldType(rawType, name) };
    });
  }

  return FALLBACK_FIELDS;
};

const Sparkline = ({ values, positive = true }) => {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = 28 - ((value - min) / range) * 24;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg className="h-8 w-full" viewBox="0 0 100 30" preserveAspectRatio="none" role="img" aria-label="Metric sparkline">
      <polyline
        fill="none"
        stroke={positive ? '#1E948E' : '#D96B5D'}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
};

const SchemaMiniMap = () => (
  <div className="studio-next-schema">
    <svg viewBox="0 0 220 120" className="h-[120px] w-full" role="img" aria-label="Table relationships">
      <line x1="42" y1="34" x2="112" y2="60" stroke="#99B0E8" strokeWidth="2" strokeDasharray="3 3" />
      <line x1="112" y1="60" x2="184" y2="32" stroke="#99B0E8" strokeWidth="2" strokeDasharray="3 3" />
      <rect x="10" y="16" width="64" height="36" rx="10" fill="#DCE6FF" />
      <rect x="82" y="42" width="74" height="36" rx="10" fill="#D4F4EE" />
      <rect x="158" y="14" width="58" height="36" rx="10" fill="#E4DCF8" />
      <text x="42" y="39" textAnchor="middle" className="studio-next-schema-label">Orders</text>
      <text x="119" y="65" textAnchor="middle" className="studio-next-schema-label">Line Items</text>
      <text x="187" y="37" textAnchor="middle" className="studio-next-schema-label">Customers</text>
    </svg>
  </div>
);

const buildConicGradient = (items, total) => {
  let cursor = 0;
  return items
    .map((item) => {
      const start = cursor;
      cursor += (item.value / Math.max(total, 1)) * 360;
      return `${item.color} ${start}deg ${cursor}deg`;
    })
    .join(', ');
};

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;

  const items = payload
    .filter((entry) => STACK_META[entry.dataKey] && Number(entry.value) > 0)
    .map((entry) => ({
      key: entry.dataKey,
      label: STACK_META[entry.dataKey].label,
      color: STACK_META[entry.dataKey].color,
      value: Number(entry.value),
    }));

  if (!items.length) return null;

  const total = items.reduce((sum, item) => sum + item.value, 0);
  const conicGradient = buildConicGradient(items, total);

  return (
    <div className="studio-next-tooltip">
      <div className="studio-next-tooltip-header">{label} breakdown</div>
      <div className="studio-next-tooltip-body">
        <div className="studio-next-ring-wrap">
          <div className="studio-next-ring" style={{ background: `conic-gradient(${conicGradient})` }}>
            <div className="studio-next-ring-center">{Math.round(total)}</div>
          </div>
        </div>
        <div className="studio-next-tooltip-list">
          {items.map((item) => (
            <div key={item.key} className="studio-next-tooltip-row">
              <span className="studio-next-tooltip-dot" style={{ backgroundColor: item.color }} />
              <span className="studio-next-tooltip-label">{item.label}</span>
              <span className="studio-next-tooltip-value">{item.value.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const TabPreview = ({ bars }) => (
  <div className="studio-next-tab-preview-chart">
    {bars.map((value, index) => (
      <span
        key={`${value}-${index}`}
        className="studio-next-tab-preview-bar"
        style={{ height: `${Math.max(value, 10)}%` }}
      />
    ))}
  </div>
);

const ChartsStudioNextPage = () => {
  const { selectedDataset } = useDatasetStore();

  const [searchValue, setSearchValue] = useState('');
  const [showComparison, setShowComparison] = useState(true);
  const [showInsights, setShowInsights] = useState(true);
  const [activeFields, setActiveFields] = useState(['order_month', 'total_revenue', 'return_rate']);
  const [activeView, setActiveView] = useState(VIEW_TABS[0].id);
  const [hoveredView, setHoveredView] = useState(null);
  const [activeQuestion, setActiveQuestion] = useState(SUGGESTED_QUESTIONS[0]);
  const [collapsed, setCollapsed] = useState({
    dimensions: false,
    measures: false,
    dates: false,
    calculated: false,
  });

  const fields = useMemo(() => {
    const metadata = selectedDataset?.metadata?.column_metadata;
    return normalizeColumnMetadata(metadata).slice(0, 24);
  }, [selectedDataset]);

  const groupedFields = useMemo(
    () => ({
      dimensions: fields.filter((field) => field.type === 'text'),
      measures: fields.filter((field) => field.type === 'number'),
      dates: fields.filter((field) => field.type === 'date'),
      calculated: fields.filter((field) => field.type === 'calculated'),
    }),
    [fields]
  );

  const chartSeries = useMemo(
    () =>
      MONTHLY_SERIES.map((point) => ({
        ...point,
        total: point.completed + point.processing + point.pending + point.returned,
      })),
    []
  );

  const totals = useMemo(() => {
    const aggregate = chartSeries.reduce(
      (acc, point) => {
        acc.revenue += point.revenue;
        acc.priorRevenue += point.priorRevenue;
        acc.completed += point.completed;
        acc.returned += point.returned;
        acc.orders += point.total;
        return acc;
      },
      { revenue: 0, priorRevenue: 0, completed: 0, returned: 0, orders: 0 }
    );

    const avgOrderValue = aggregate.revenue / Math.max(aggregate.orders, 1);
    const returnRate = aggregate.returned / Math.max(aggregate.orders, 1);
    const completionRate = aggregate.completed / Math.max(aggregate.orders, 1);

    const deltaRevenue = ((aggregate.revenue - aggregate.priorRevenue) / Math.max(aggregate.priorRevenue, 1)) * 100;
    const deltaCompleted = 8.4;
    const deltaReturnRate = -2.8;
    const deltaAov = 5.6;
    const deltaCompletion = 3.2;

    return {
      ...aggregate,
      avgOrderValue,
      returnRate,
      completionRate,
      deltaRevenue,
      deltaCompleted,
      deltaReturnRate,
      deltaAov,
      deltaCompletion,
    };
  }, [chartSeries]);

  const strongestMonth = useMemo(
    () => chartSeries.reduce((current, point) => (point.revenue > current.revenue ? point : current), chartSeries[0]),
    [chartSeries]
  );

  const highestReturnMonth = useMemo(
    () =>
      chartSeries.reduce((current, point) => {
        const currentRate = current.returned / Math.max(current.total, 1);
        const pointRate = point.returned / Math.max(point.total, 1);
        return pointRate > currentRate ? point : current;
      }, chartSeries[0]),
    [chartSeries]
  );

  const kpiCards = useMemo(
    () => [
      {
        id: 'revenue',
        label: 'Total Revenue',
        value: formatCompactCurrency(totals.revenue),
        delta: totals.deltaRevenue,
        positive: totals.deltaRevenue >= 0,
        trend: chartSeries.map((point) => point.revenue),
      },
      {
        id: 'completed',
        label: 'Completed Orders',
        value: formatCompactNumber(totals.completed),
        delta: totals.deltaCompleted,
        positive: true,
        trend: chartSeries.map((point) => point.completed),
      },
      {
        id: 'returns',
        label: 'Return Rate',
        value: `${(totals.returnRate * 100).toFixed(1)}%`,
        delta: totals.deltaReturnRate,
        positive: totals.deltaReturnRate <= 0,
        trend: chartSeries.map((point) => (point.returned / Math.max(point.total, 1)) * 100),
      },
      {
        id: 'aov',
        label: 'Avg Order Value',
        value: formatCompactCurrency(totals.avgOrderValue),
        delta: totals.deltaAov,
        positive: totals.deltaAov >= 0,
        trend: chartSeries.map((point) => point.revenue / Math.max(point.total, 1)),
      },
      {
        id: 'fulfillment',
        label: 'Fulfillment Rate',
        value: `${(totals.completionRate * 100).toFixed(1)}%`,
        delta: totals.deltaCompletion,
        positive: totals.deltaCompletion >= 0,
        trend: chartSeries.map((point) => (point.completed / Math.max(point.total, 1)) * 100),
      },
    ],
    [chartSeries, totals]
  );

  const insights = useMemo(
    () => [
      `Revenue grew ${totals.deltaRevenue.toFixed(1)}% YoY with ${formatCompactCurrency(totals.revenue)} booked across the current period.`,
      `${strongestMonth.month} is the strongest month, primarily driven by completed orders and lower pending volume.`,
      `Return rates are trending down overall; the temporary peak in ${highestReturnMonth.month} normalized by Q4.`,
    ],
    [highestReturnMonth.month, strongestMonth.month, totals.deltaRevenue, totals.revenue]
  );

  const annotations = useMemo(
    () => [
      { month: strongestMonth.month, label: 'Revenue spike likely holiday season', color: '#3B6FE8', position: 'insideTopLeft' },
      { month: highestReturnMonth.month, label: 'Return rate peaks here', color: '#D96B5D', position: 'insideTopRight' },
    ],
    [highestReturnMonth.month, strongestMonth.month]
  );

  const currentView = useMemo(() => VIEW_TABS.find((view) => view.id === activeView) || VIEW_TABS[0], [activeView]);

  const toggleSection = (section) => {
    setCollapsed((previous) => ({ ...previous, [section]: !previous[section] }));
  };

  const toggleField = (name) => {
    setActiveFields((previous) =>
      previous.includes(name) ? previous.filter((field) => field !== name) : [...previous, name]
    );
  };

  const renderFieldGroup = (title, key, list) => (
    <div className="studio-next-section">
      <button
        type="button"
        onClick={() => toggleSection(key)}
        className="studio-next-section-header"
      >
        <span>{title}</span>
        {collapsed[key] ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
      </button>
      {!collapsed[key] && (
        <div className="studio-next-fields">
          {list.length === 0 ? (
            <div className="studio-next-empty">No fields detected</div>
          ) : (
            list.map((field) => (
              <button
                key={field.name}
                type="button"
                onClick={() => toggleField(field.name)}
                className={cn('studio-next-field-item', activeFields.includes(field.name) && 'is-active')}
              >
                <span className="studio-next-field-name">{field.name}</span>
                <span className={cn('studio-next-pill', TYPE_META[field.type]?.className || TYPE_META.text.className)}>
                  {TYPE_META[field.type]?.label || TYPE_META.text.label}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );

  const workspaceClass = cn(
    'mx-auto w-full max-w-[1800px] flex flex-col gap-6 lg:grid lg:grid-cols-[260px_minmax(0,1fr)]',
    showInsights ? 'xl:grid-cols-[260px_minmax(0,1fr)_280px]' : 'xl:grid-cols-[260px_minmax(0,1fr)]'
  );

  return (
    <div className="studio-next-page h-full min-h-screen flex flex-col">
      <header className="studio-next-command-bar">
        <div className="grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)_220px] lg:items-center">
          <div className="flex items-center gap-2">
            <div className="studio-next-logo">
              <Sparkles size={14} />
            </div>
            <div>
              <p className="studio-next-label">Workbook</p>
              <p className="studio-next-workbook-name">
                {selectedDataset?.name || 'Revenue Performance Studio'}
              </p>
            </div>
          </div>

          <div className="studio-next-search-wrap">
            <Search size={15} className="text-[#9CB1DA]" />
            <input
              value={searchValue}
              onChange={(event) => setSearchValue(event.target.value)}
              className="studio-next-search-input"
              placeholder="Ask your data anything..."
              aria-label="Natural language query"
            />
          </div>

          <div className="flex items-center justify-start gap-2 lg:justify-end">
            <button type="button" className="studio-next-icon-btn" aria-label="Share workbook">
              <Share2 size={15} />
            </button>
            <button type="button" className="studio-next-icon-btn" aria-label="Notifications">
              <Bell size={15} />
            </button>
            <div className="studio-next-avatar">VS</div>
          </div>
        </div>
      </header>

      <div className="flex-1 min-h-0 overflow-auto px-4 py-4 md:px-6 md:py-6">
        <div className={workspaceClass}>
          <aside className="studio-next-sidebar">
            <div className="studio-next-sidebar-scroll">
              <div>
                <p className="studio-next-label">Schema Map</p>
                <SchemaMiniMap />
              </div>

              <div className="space-y-3">
                {renderFieldGroup('Dimensions', 'dimensions', groupedFields.dimensions)}
                {renderFieldGroup('Measures', 'measures', groupedFields.measures)}
                {renderFieldGroup('Dates', 'dates', groupedFields.dates)}
                {renderFieldGroup('Calculated', 'calculated', groupedFields.calculated)}
              </div>
            </div>

            <div className="studio-next-sidebar-sticky">
              <p className="studio-next-label">Recent Fields</p>
              <div className="studio-next-chip-wrap">
                {activeFields.slice(0, 4).map((field) => (
                  <span key={field} className="studio-next-chip">{field}</span>
                ))}
              </div>
              <p className="studio-next-label mt-3">Saved Sets</p>
              <div className="studio-next-chip-wrap">
                <span className="studio-next-chip studio-next-chip-emphasis">Exec Summary</span>
                <span className="studio-next-chip">Returns Monitor</span>
              </div>
            </div>
          </aside>

          <section className="min-w-0 flex flex-col gap-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-5">
              {kpiCards.map((card, index) => (
                <MotionArticle
                  key={card.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: index * 0.04 }}
                  className={cn('studio-next-kpi-card', card.positive ? 'positive' : 'negative')}
                >
                  <p className="studio-next-kpi-label">{card.label}</p>
                  <div className="mt-1 flex items-end justify-between gap-2">
                    <p className="studio-next-kpi-value">{card.value}</p>
                    <span className={cn('studio-next-kpi-delta', card.positive ? 'positive' : 'negative')}>
                      {card.positive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                      {formatDelta(card.delta)}
                    </span>
                  </div>
                  <Sparkline values={card.trend} positive={card.positive} />
                </MotionArticle>
              ))}
            </div>

            <MotionArticle
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.15 }}
              className="studio-next-chart-shell"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="studio-next-panel-title">Monthly Orders and Completion Health</p>
                  <p className="studio-next-panel-subtitle">
                    Refined stacked bars with semantic palette and AI-generated anomaly callouts.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <label className="studio-next-switch-wrap">
                    <span>Compare prior year</span>
                    <button
                      type="button"
                      className={cn('studio-next-switch', showComparison && 'on')}
                      onClick={() => setShowComparison((value) => !value)}
                      aria-pressed={showComparison}
                    >
                      <span className="studio-next-switch-thumb" />
                    </button>
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowInsights((value) => !value)}
                    className="studio-next-secondary-btn"
                  >
                    {showInsights ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
                    {showInsights ? 'Hide Insights' : 'Show Insights'}
                  </button>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                {Object.entries(STACK_META).map(([key, meta]) => (
                  <div key={key} className="studio-next-legend-item">
                    <span className="studio-next-legend-dot" style={{ backgroundColor: meta.color }} />
                    {meta.label}
                  </div>
                ))}
              </div>

              <div className="mt-4 h-[430px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartSeries} margin={{ top: 18, right: 16, left: 0, bottom: 4 }}>
                    <defs>
                      <filter id="studio-next-shadow" x="-10%" y="-10%" width="130%" height="140%">
                        <feDropShadow dx="0" dy="5" stdDeviation="4" floodColor="#AFC2E6" floodOpacity="0.22" />
                      </filter>
                    </defs>
                    <CartesianGrid stroke="#E4E8F4" strokeDasharray="3 6" vertical={false} />
                    <XAxis
                      dataKey="month"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#6D7791', fontSize: 12, fontWeight: 600 }}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#8490AB', fontSize: 12 }}
                      tickFormatter={(value) => formatCompactNumber(value)}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(59, 111, 232, 0.08)' }}
                      content={<ChartTooltip />}
                    />

                    {annotations.map((annotation) => {
                      const point = chartSeries.find((item) => item.month === annotation.month);
                      if (!point) return null;

                      return (
                        <React.Fragment key={annotation.month}>
                          <ReferenceLine
                            x={annotation.month}
                            stroke={annotation.color}
                            strokeOpacity={0.45}
                            strokeDasharray="4 6"
                            label={{
                              value: annotation.label,
                              position: annotation.position,
                              fill: annotation.color,
                              fontSize: 11,
                            }}
                          />
                          <ReferenceDot
                            x={annotation.month}
                            y={point.total}
                            r={5}
                            fill={annotation.color}
                            stroke="#FFFFFF"
                            strokeWidth={2}
                          />
                        </React.Fragment>
                      );
                    })}

                    <Bar
                      stackId="orders"
                      dataKey="completed"
                      fill={STACK_META.completed.color}
                      radius={[0, 0, 0, 0]}
                      style={{ filter: 'url(#studio-next-shadow)' }}
                    />
                    <Bar
                      stackId="orders"
                      dataKey="processing"
                      fill={STACK_META.processing.color}
                      radius={[0, 0, 0, 0]}
                      style={{ filter: 'url(#studio-next-shadow)' }}
                    />
                    <Bar
                      stackId="orders"
                      dataKey="pending"
                      fill={STACK_META.pending.color}
                      radius={[0, 0, 0, 0]}
                      style={{ filter: 'url(#studio-next-shadow)' }}
                    />
                    <Bar
                      stackId="orders"
                      dataKey="returned"
                      fill={STACK_META.returned.color}
                      radius={[10, 10, 0, 0]}
                      style={{ filter: 'url(#studio-next-shadow)' }}
                    />

                    {showComparison && (
                      <Line
                        type="monotone"
                        dataKey="priorYearTotal"
                        stroke="#355EA8"
                        strokeWidth={2.3}
                        strokeDasharray="6 4"
                        dot={false}
                        activeDot={{ r: 5, fill: '#355EA8', stroke: '#FFFFFF', strokeWidth: 2 }}
                        name="Prior Year"
                      />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </MotionArticle>

            <div className="studio-next-tabs">
              <div className="flex flex-1 flex-wrap items-center gap-2">
                {VIEW_TABS.map((view) => (
                  <div
                    key={view.id}
                    className="relative"
                    onMouseEnter={() => setHoveredView(view.id)}
                    onMouseLeave={() => setHoveredView(null)}
                  >
                    <button
                      type="button"
                      onClick={() => setActiveView(view.id)}
                      className={cn('studio-next-tab-btn', activeView === view.id && 'active')}
                    >
                      {view.label}
                    </button>
                    {hoveredView === view.id && (
                      <div className="studio-next-tab-preview">
                        <TabPreview bars={view.preview} />
                        <p>{view.description}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <button type="button" className="studio-next-new-view-btn">
                <Plus size={15} />
                New View
              </button>
            </div>

            <div className="studio-next-view-note">
              Active view: <strong>{currentView.label}</strong>. {currentView.description}.
            </div>
          </section>

          {showInsights && (
            <aside className="studio-next-insights lg:col-span-2 xl:col-span-1">
              <div className="flex items-center justify-between">
                <p className="studio-next-panel-title">AI Insight Panel</p>
                <span className="studio-next-badge">Live Narrative</span>
              </div>

              <div className="mt-4 space-y-3">
                {insights.map((line) => (
                  <p key={line} className="studio-next-insight-line">{line}</p>
                ))}
              </div>

              <div className="mt-5">
                <p className="studio-next-label">Suggested follow-up questions</p>
                <div className="studio-next-question-wrap">
                  {SUGGESTED_QUESTIONS.map((question) => (
                    <button
                      key={question}
                      type="button"
                      className={cn('studio-next-question-chip', activeQuestion === question && 'active')}
                      onClick={() => {
                        setActiveQuestion(question);
                        setSearchValue(question);
                      }}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-6 rounded-xl bg-[#F4F6FD] p-3 text-sm text-[#5B6785]">
                Next action: run <strong>{activeQuestion}</strong> to validate the signal with segment-level drill down.
              </div>

              <Link to="/app/charts" className="studio-next-secondary-link">
                Back to classic studio
              </Link>
            </aside>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChartsStudioNextPage;
