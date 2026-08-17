/**
 * PlotlyAdapter
 * =============
 * Frontend adapter that converts VIS (Visualization Intent Schema) objects
 * into Plotly-compatible `{ traces, layout }` payloads.
 *
 * The existing PlotlyChart component handles all visual enhancements
 * (colors, annotations, statistical overlays, downsampling).
 * This adapter provides the raw trace/layout conversion layer.
 *
 * Usage:
 *   import { renderVis } from '../adapters/PlotlyAdapter';
 *   const { traces, layout } = renderVis(visObject);
 *   <PlotlyChart data={traces} layout={layout} chartType={vis.visualization_type} />
 */

// ── VIS type mapping to Plotly trace types ──────────────────────────
// ECharts-only types have no Plotly equivalent — they degrade gracefully.
const TRACE_TYPE_MAP = {
  bar: 'bar',
  line: 'scatter',
  area: 'scatter',
  scatter: 'scatter',
  pie: 'pie',
  donut: 'pie',                           // Plotly: pie + hole (variant_config.donut_hole)
  histogram: 'bar',
  box_plot: 'box',
  heatmap: 'heatmap',
  treemap: 'treemap',
  sunburst: 'sunburst',
  radar: 'scatterpolar',
  bubble: 'scatter',
  waterfall: 'waterfall',
  funnel: 'funnel',
  candlestick: 'candlestick',
  violin: 'violin',
  gauge: 'indicator',
  bullet: 'indicator',
  choropleth: 'choropleth',
  correlation_matrix: 'heatmap',
  multi_line: 'scatter',
  grouped_bar: 'bar',
  stacked_bar: 'bar',
  stacked_area: 'scatter',
  dual_axis: 'scatter',
  combo: 'bar',
  facet: 'scatter',
  small_multiples: 'scatter',
  // ECharts-only types — Plotly cannot render these natively.
  // They show as a visual indicator marking unsupported type.
  graph: 'scatter',
  sankey: 'scatter',
  parallel: 'scatter',
  lines: 'scatter',
  tree: 'scatter',
  theme_river: 'scatter',
  pictorial_bar: 'bar',
  effect_scatter: 'scatter',
  map: 'choropleth',                        // Plotly has choropleth; ECharts has map
};

// ── Color palettes (reused from ChartRenderer.jsx) ────────────────────
const PALETTES = {
  bar: ['#3b82f6', '#6366f1', '#8b5cf6', '#10b981', '#f59e0b', '#f43f5e', '#14b8a6', '#ec4899'],
  line: ['#3b82f6', '#6366f1', '#10b981', '#8b5cf6', '#f59e0b'],
  pie: ['#3b82f6', '#6366f1', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#14b8a6', '#ec4899'],
  scatter: ['#3b82f6', '#6366f1', '#10b981', '#f59e0b', '#f87171'],
  box: ['#3b82f6', '#6366f1', '#8b5cf6', '#10b981', '#f59e0b', '#f87171'],
  heatmap: [],
  area: ['#3b82f6', '#6366f1', '#10b981', '#f59e0b', '#ef4444'],
  default: ['#3b82f6', '#6366f1', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#14b8a6'],
};

const getPalette = (type) => {
  const normalized = (type || '').toLowerCase().replace('_chart', '').replace('_plot', '');
  return PALETTES[normalized] || PALETTES.default;
};

// ── ECharts-only types that Plotly cannot render natively ───────────
// Types NOT in this set can be rendered by Plotly (may lose some visual
// effects like ripple animation for effect_scatter or symbols for pictorial_bar).
const ECHARTS_ONLY_TYPES = new Set([
  'graph',
  'sankey',
  'parallel',
  'lines',
  'tree',
  'theme_river',
]);

// ── Main render function ────────────────────────────────────────────

/**
 * Convert a VIS object to Plotly-compatible { traces, layout }.
 * @param {Object} vis - The VIS object from the backend
 * @param {Object} [options] - Rendering options
 * @param {string} [options.theme='dark'] - 'dark' or 'light'
 * @param {number} [options.colorOffset=0] - Rotate palette start index
 * @returns {{ traces: Array, layout: Object }}
 */
export function renderVis(vis, options = {}) {
  const {
    theme = 'dark',
    colorOffset = 0,
  } = options;

  if (!vis) {
    return { traces: [], layout: {} };
  }

  const vizType = vis.visualization_type || 'bar';
  const allSeries = [...(vis.series || [])];
  if (vis.series_collection?.series) {
    allSeries.push(...vis.series_collection.series);
  }

  // Step 1: Convert each VISDataSeries to a Plotly trace
  // Degrade ECharts-only types to a visual notice instead
  let traces;
  if (ECHARTS_ONLY_TYPES.has(vizType)) {
    traces = [{
      type: 'scatter',
      mode: 'text',
      x: [0.5],
      y: [0.5],
      xaxis: 'x',
      yaxis: 'y',
      text: [`${vizType.replace(/_/g, ' ')} chart requires ECharts`],
      textfont: { size: 14, color: '#9CA3AF' },
      showlegend: false,
      hoverinfo: 'none',
    }];
  } else {
    traces = allSeries.map((series, idx) =>
      seriesToTrace(series, vizType, idx, colorOffset)
    ).filter(Boolean);
  }

  // Step 2: Apply strategy-specific layout adjustments
  const layout = buildLayout(vis, theme);

  // Step 3: Handle multi-series strategies
  if (vis.series_strategy && vis.series_strategy !== 'none') {
    applyStrategy(vis, traces, layout);
  }

  // Step 4: Apply analytics overlays as layout annotations/shapes
  if (vis.analytics) {
    applyAnalytics(vis.analytics, traces, layout, theme);
  }

  // Step 5: Build metadata payload
  const result = {
    type: 'chart',
    chart_type: vizType,
    title: vis.title || '',
    traces,
    layout,
    meta: {
      success: traces.length > 0,
      rows_used: vis.metadata?.rows_used || 0,
      warnings: [],
      render_ms: vis.metadata?.render_time_ms || 0,
    },
  };

  // Pass through point intelligence (renderer-agnostic)
  if (vis.point_intelligence) {
    result.point_intelligence = vis.point_intelligence;
  }

  // Pass through narrative
  if (vis.narrative?.headline) {
    result.explanation = vis.narrative.headline;
  }
  if (vis.narrative?.confidence) {
    result.confidence = vis.narrative.confidence;
  }
  if (vis.narrative?.badge_type) {
    result.badge_type = vis.narrative.badge_type;
  }
  if (vis.narrative?.key_numbers?.length) {
    result.key_numbers = vis.narrative.key_numbers;
  }
  if (vis.narrative?.reading_guide) {
    result.reading_guide = vis.narrative.reading_guide;
  }

  // Pass through subtitle_scope (maps VIS description → legacy subtitle)
  // ChartCanvas.jsx reads subtitle_scope from chartData payload
  if (vis.narrative?.description) {
    result.subtitle_scope = vis.narrative.description;
  } else if (vis.description) {
    result.subtitle_scope = vis.description;
  }

  // Pass through data_mapping as legacy chartConfig equivalent
  if (vis.data_mapping && Object.keys(vis.data_mapping).length > 0) {
    result.data_mapping = vis.data_mapping;
    result.aggregation = vis.aggregation;
  }

  return result;
}

// ── Series to trace conversion ──────────────────────────────────────

function seriesToTrace(series, vizType, idx, colorOffset) {
  if (!series) return null;

  const plotlyType = TRACE_TYPE_MAP[series.series_type || vizType] || 'bar';
  const palette = getPalette(vizType);
  const color = palette[(idx + (colorOffset || 0)) % palette.length];

  const trace = { type: plotlyType };

  // Name
  if (series.name) trace.name = series.name;
  if (series.group) trace.name = series.group;

  // Standard x/y
  if (series.x != null) trace.x = series.x;
  if (series.y != null) trace.y = series.y;

  // Line-specific mode
  if (plotlyType === 'scatter') {
    if (series.series_type === 'line' || series.series_type === 'multi_line') {
      trace.mode = 'lines';
      trace.line = { color, width: 2 };
    } else if (series.series_type === 'area' || series.series_type === 'stacked_area') {
      trace.mode = 'lines';
      trace.fill = series.series_type === 'stacked_area' ? 'tonexty' : 'tozeroy';
      trace.line = { color, width: 1 };
    } else {
      trace.mode = 'markers';
      trace.marker = { color, size: 8, opacity: 0.85 };
    }
  }

  // Bar
  if (plotlyType === 'bar') {
    trace.marker = { color, line: { width: 0 } };
  }

  // Pie
  if (plotlyType === 'pie') {
    if (series.labels) trace.labels = series.labels;
    if (series.values) trace.values = series.values;
    trace.hole = 0.65;
    trace.textinfo = 'none';
    trace.marker = {
      colors: getPalette('pie'),
      line: { color: 'rgba(10,13,20,0.8)', width: 2 },
    };
  }

  // Heatmap
  if (plotlyType === 'heatmap' && series.z) {
    trace.z = series.z;
    if (series.x_labels) trace.x = series.x_labels;
    if (series.y_labels) trace.y = series.y_labels;
    trace.colorscale = vizType === 'correlation_matrix' ? 'RdBu' : 'Viridis';
  }

  // Box/Violin
  if (plotlyType === 'box' || plotlyType === 'violin') {
    if (series.y_raw) trace.y = series.y_raw;
    trace.name = series.name || 'Distribution';
    if (plotlyType === 'box') {
      trace.boxpoints = 'outliers';
      trace.whiskerwidth = 0.5;
    }
    if (plotlyType === 'violin') {
      trace.box = { visible: true };
      trace.meanline = { visible: true };
      trace.points = 'all';
    }
    trace.marker = { color };
    trace.line = { color };
    trace.fillcolor = color + '20';
  }

  // Treemap / Sunburst
  if (plotlyType === 'treemap' || plotlyType === 'sunburst') {
    if (series.ids) trace.ids = series.ids;
    if (series.parents) trace.parents = series.parents;
    if (series.labels_hier) trace.labels = series.labels_hier;
    if (series.values != null) trace.values = series.values;
  }

  // Waterfall
  if (plotlyType === 'waterfall') {
    if (series.x) trace.x = series.x;
    if (series.y) trace.y = series.y;
    if (series.measure) trace.measure = series.measure;
  }

  // Funnel
  if (plotlyType === 'funnel') {
    if (series.x) trace.x = series.x;
    if (series.y) trace.y = series.y;
    trace.textinfo = 'value+percent initial';
  }

  // Candlestick
  if (plotlyType === 'candlestick') {
    if (series.x) trace.x = series.x;
    if (series.open) trace.open = series.open;
    if (series.high) trace.high = series.high;
    if (series.low) trace.low = series.low;
    if (series.close) trace.close = series.close;
    trace.increasing = { line: { color: '#34d399' } };
    trace.decreasing = { line: { color: '#f87171' } };
  }

  // Radar
  if (plotlyType === 'scatterpolar') {
    if (series.r) trace.r = series.r;
    if (series.theta) trace.theta = series.theta;
    trace.fill = 'toself';
  }

  // Indicator (Gauge/Bullet)
  if (plotlyType === 'indicator') {
    trace.value = series.value ?? 0;
    const isBullet = series.series_type === 'bullet';
    trace.mode = isBullet ? 'number+gauge+delta' : 'number+gauge';
    trace.gauge = {
      axis: { range: [0, series.gauge_max ?? (series.value * 1.5 || 100)] },
      bar: { color },
    };
    if (series.target != null) {
      trace.delta = { reference: series.target };
    }
  }

  // Choropleth
  if (plotlyType === 'choropleth') {
    if (series.locations) trace.locations = series.locations;
    if (series.z_geo) trace.z = series.z_geo;
    trace.locationmode = 'country names';
    trace.colorscale = 'Viridis';
  }

  return trace;
}

// ── Layout builder ──────────────────────────────────────────────────

function buildLayout(vis, theme) {
  const bg = theme === 'dark' ? '#111827' : 'white';
  const fg = theme === 'dark' ? '#E5E7EB' : '#1F2937';
  const grid = theme === 'dark' ? '#1F2937' : '#E5E7EB';

  const layout = {
    title: { text: vis.title || '', font: { size: 18, color: fg } },
    paper_bgcolor: bg,
    plot_bgcolor: bg,
    margin: { l: 30, r: 20, t: 40, b: 40 },
    font: { color: fg },
    legend: { font: { color: fg } },
    xaxis: { showgrid: true, gridcolor: grid, tickfont: { color: fg } },
    yaxis: { showgrid: true, gridcolor: grid, tickfont: { color: fg } },
    hovermode: 'closest',
    hoverlabel: {
      bgcolor: theme === 'dark' ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
      bordercolor: theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
      font: {
        family: 'Inter, -apple-system, sans-serif',
        size: 13,
        color: theme === 'dark' ? '#f8fafc' : '#1f2937',
      },
      align: 'left',
    },
  };

  // Axis titles from VIS axes
  if (vis.axes?.x?.title) layout.xaxis.title = { text: vis.axes.x.title };
  if (vis.axes?.y?.title) layout.yaxis.title = { text: vis.axes.y.title };

  // Date axis
  if (vis.axes?.x?.axis_type === 'date') {
    layout.xaxis.type = 'date';
  }

  // Secondary Y axis
  if (vis.axes?.y2) {
    layout.yaxis2 = {
      overlaying: 'y',
      side: 'right',
      showgrid: false,
      tickfont: { color: fg },
      title: vis.axes.y2.title ? { text: vis.axes.y2.title } : undefined,
    };
  }

  // Pie/donut adjustments
  if (vis.visualization_type === 'pie' || vis.visualization_type === 'donut') {
    layout.xaxis.showticklabels = false;
    layout.xaxis.showgrid = false;
    layout.yaxis.showticklabels = false;
    layout.yaxis.showgrid = false;
    layout.legend = {
      orientation: 'v',
      yanchor: 'middle',
      y: 0.5,
      xanchor: 'left',
      x: 1.02,
      font: { color: fg, size: 11 },
    };
    layout.margin = { l: 30, r: 20, t: 40, b: 80 };
  }

  // Heatmap adjustments
  if (vis.visualization_type === 'heatmap' || vis.visualization_type === 'correlation_matrix') {
    layout.xaxis.showgrid = false;
    layout.yaxis.showgrid = false;
  }

  return layout;
}

// ── Multi-series strategy application ───────────────────────────────

function applyStrategy(vis, traces, layout) {
  const strategy = vis.series_strategy;

  if (strategy === 'grouped') {
    layout.barmode = 'group';
  } else if (strategy === 'stacked') {
    layout.barmode = 'stack';
  } else if (strategy === 'dual_axis') {
    // Assign first half of traces to left axis, second half to right
    const mid = Math.ceil(traces.length / 2);
    traces.forEach((trace, idx) => {
      if (idx >= mid) {
        trace.yaxis = 'y2';
      }
    });
  } else if (strategy === 'combo') {
    // First trace is bar, rest are lines
    traces.forEach((trace, idx) => {
      if (idx === 0) {
        trace.type = 'bar';
        trace.yaxis = 'y';
      } else {
        trace.type = 'scatter';
        trace.mode = 'lines';
        trace.yaxis = 'y2';
      }
    });
    if (!layout.yaxis2) {
      layout.yaxis2 = { overlaying: 'y', side: 'right', showgrid: false };
    }
  }
  // facet and small_multiples are handled by the multi-series renderers
}

// ── Analytics overlays ──────────────────────────────────────────────

function applyAnalytics(analytics, traces, layout, theme) {
  const shapes = [];
  const annotations = [];
  const fg = theme === 'dark' ? '#E5E7EB' : '#1F2937';

  // Reference lines
  for (const ref of (analytics.reference_lines || [])) {
    const color = ref.color || (ref.line_type === 'mean' ? '#3b82f6' : '#f59e0b');
    shapes.push({
      type: 'line',
      xref: 'paper',
      x0: 0, x1: 1,
      y0: ref.value, y1: ref.value,
      line: { color, width: 1.5, dash: ref.dash || 'dash' },
    });
    annotations.push({
      xref: 'paper', x: 1.01,
      yref: 'y', y: ref.value,
      text: `${ref.label}: ${formatNumber(ref.value)}`,
      showarrow: false,
      font: { size: 10, color },
      xanchor: 'left',
    });
  }

  // Average and median lines are provided by backend via analytics.reference_lines.
  // flags analytics.show_average and analytics.show_median are hints only.

  if (shapes.length) layout.shapes = shapes;
  if (annotations.length) layout.annotations = annotations;
}

// ── Utility ─────────────────────────────────────────────────────────

function formatNumber(val) {
  if (typeof val !== 'number') return String(val);
  if (val >= 1e9) return (val / 1e9).toFixed(1) + 'B';
  if (val >= 1e6) return (val / 1e6).toFixed(1) + 'M';
  if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K';
  return val.toLocaleString();
}

// ── VIS → Plotly data/layout (compat format for existing consumers) ──

/**
 * Convert VIS to { data, layout } format expected by PlotlyChart.
 * This is the primary entry point for frontend consumers.
 */
export function visToChartData(vis, options = {}) {
  const result = renderVis(vis, options);
  return {
    data: result.traces,
    layout: result.layout,
    chart_type: result.chart_type,
    title: result.title,
    explanation: result.explanation || '',
    confidence: result.confidence || 0,
    badge_type: result.badge_type || null,
    point_intelligence: result.point_intelligence || null,
    metadata: result.meta || {},
  };
}

/**
 * Detect whether a payload is VIS (vs legacy Plotly JSON).
 */
export function isVIS(data) {
  return data && (
    typeof data.visualization_type === 'string' ||
    (typeof data.version === 'string' && data.version.startsWith('1.'))
  );
}

/**
 * Detect whether a payload is legacy Plotly JSON.
 */
export function isLegacyPlotly(data) {
  return data && (
    Array.isArray(data.traces) ||
    Array.isArray(data.data)
  ) && !isVIS(data);
}

export default { renderVis, visToChartData, isVIS, isLegacyPlotly };
