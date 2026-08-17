/**
 * EChartsAdapter
 * ==============
 * Frontend adapter that converts VIS (Visualization Intent Schema) objects
 * into Apache ECharts-compatible `option` objects.
 *
 * Supports ALL 22 ECharts series types and their variants:
 *   bar, line, pie, scatter, effectScatter, radar, treemap, sunburst,
 *   boxplot, candlestick, heatmap, map, parallel, lines, graph, sankey,
 *   funnel, gauge, pictorialBar, themeRiver, custom, tree
 *
 * Variant configurations (step, smooth, roseType, realtimeSort, etc.)
 * are driven by VIS.variant_config — not adapter hardcoding.
 *
 * Usage:
 *   import { renderVis } from '../adapters/EChartsAdapter';
 *   const option = renderVis(visObject);
 *   const chart = echarts.init(domElement);
 *   chart.setOption(option);
 */

// ── VIS type to ECharts series type mapping ─────────────────────────
const SERIES_TYPE_MAP = {
  bar: 'bar',
  line: 'line',
  area: 'line',
  scatter: 'scatter',
  pie: 'pie',
  donut: 'pie',
  histogram: 'bar',
  box_plot: 'boxplot',
  heatmap: 'heatmap',
  treemap: 'treemap',
  sunburst: 'sunburst',
  radar: 'radar',
  bubble: 'scatter',
  waterfall: 'bar',
  funnel: 'funnel',
  candlestick: 'candlestick',
  violin: 'custom',
  gauge: 'gauge',
  bullet: 'gauge',
  choropleth: 'map',
  correlation_matrix: 'heatmap',
  multi_line: 'line',
  grouped_bar: 'bar',
  stacked_bar: 'bar',
  stacked_area: 'line',
  dual_axis: 'line',
  combo: 'bar',
  facet: 'line',
  small_multiples: 'line',
  // ECharts-native types — direct 1:1 mapping
  graph: 'graph',
  sankey: 'sankey',
  parallel: 'parallel',
  lines: 'lines',
  tree: 'tree',
  theme_river: 'themeRiver',
  pictorial_bar: 'pictorialBar',
  effect_scatter: 'effectScatter',
  map: 'map',
};

// ── Default color palette (DataSage brand colors) ───────────────────
const DEFAULT_COLORS = [
  '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#ec4899', '#8b5cf6', '#14b8a6', '#f97316', '#84cc16',
  '#0ea5e9', '#a855f7', '#22d3ee', '#34d399', '#fbbf24',
];

// ── Main render function ────────────────────────────────────────────

/**
 * Convert a VIS object to an ECharts option object.
 * @param {Object} vis - The VIS object from the backend
 * @param {Object} [options] - Rendering options
 * @param {string} [options.theme='dark'] - 'dark' or 'light'
 * @returns {Object} ECharts option object
 */
export function renderVis(vis, options = {}) {
  const { theme = 'dark' } = options;

  if (!vis) return {};

  const vizType = vis.visualization_type || 'bar';
  const echartType = SERIES_TYPE_MAP[vizType] || 'bar';
  const allSeries = [...(vis.series || [])];
  if (vis.series_collection?.series) {
    allSeries.push(...vis.series_collection.series);
  }

  // ── Step 1: Build ECharts option skeleton ──
  const option = buildOption(vis, theme);

  // ── Step 2: Convert each VISDataSeries to ECharts series ──
  const seriesList = allSeries.map((series, idx) =>
    seriesToECharts(series, vizType, echartType, idx, vis)
  ).filter(Boolean);

  // ── Step 3: Apply multi-series strategy ──
  if (vis.series_strategy && vis.series_strategy !== 'none') {
    applyStrategy(seriesList, vizType, vis);
  }

  // ── Step 4: Apply variant config ──
  if (vis.variant_config) {
    applyVariants(seriesList, vizType, vis.variant_config, option);
  }

  // ── Step 5: Add analytics overlays ──
  if (vis.analytics) {
    applyAnalytics(vis.analytics, option, theme);
  }

  option.series = seriesList;

  return option;
}

// ── Option skeleton builder ─────────────────────────────────────────

function buildOption(vis, theme) {
  const isDark = theme === 'dark';
  const bg = isDark ? '#111827' : '#ffffff';
  const textColor = isDark ? '#E5E7EB' : '#1F2937';

  const option = {
    backgroundColor: bg,
    color: DEFAULT_COLORS,
    animation: true,
    animationDuration: 800,
    animationEasing: 'cubicOut',
    textStyle: { fontFamily: 'Inter, -apple-system, sans-serif' },
    title: {
      text: vis.title || '',
      textStyle: { color: textColor, fontSize: 18, fontWeight: 600 },
      left: 'center',
      top: 10,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
      borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
      textStyle: { color: isDark ? '#f8fafc' : '#1f2937', fontSize: 13 },
      confine: true,
    },
    grid: {
      left: 50,
      right: 20,
      top: 60,
      bottom: 40,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      axisLine: { lineStyle: { color: isDark ? '#374151' : '#D1D5DB' } },
      axisTick: { lineStyle: { color: isDark ? '#374151' : '#D1D5DB' } },
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: {
        lineStyle: { color: isDark ? '#1F2937' : '#E5E7EB', type: 'dashed' },
      },
    },
    legend: {
      textStyle: { color: textColor, fontSize: 12 },
      top: 35,
      type: 'scroll',
    },
  };

  // Apply axis titles from VIS
  if (vis.axes?.x?.title) {
    option.xAxis.name = vis.axes.x.title;
    option.xAxis.nameTextStyle = { color: textColor, fontSize: 12 };
  }
  if (vis.axes?.y?.title) {
    option.yAxis.name = vis.axes.y.title;
    option.yAxis.nameTextStyle = { color: textColor, fontSize: 12 };
  }

  // Date axis
  if (vis.axes?.x?.axis_type === 'date' || vis.axes?.x?.axis_type === 'time') {
    option.xAxis.type = 'time';
  }

  // Theme-specific backgrounds
  if (isDark) {
    option.backgroundColor = '#111827';
  }

  // Narrative in tooltip
  if (vis.narrative?.headline) {
    option.title.subtext = vis.narrative.headline;
    option.title.subtextStyle = { color: isDark ? '#9CA3AF' : '#6B7280', fontSize: 13 };
  }

  return option;
}

// ── Series conversion ───────────────────────────────────────────────

function seriesToECharts(series, vizType, echartType, idx, vis) {
  if (!series) return null;

  const base = {
    name: series.name || series.group || `Series ${idx + 1}`,
    type: echartType,
  };

  // ── Bar / Line / Scatter / Area / Pictorial Bar / Effect Scatter ──
  if (['bar', 'line', 'scatter', 'pictorialBar', 'effectScatter'].includes(echartType)) {
    if (series.x && series.y) {
      base.data = series.x.map((xv, i) => [xv, series.y[i]]);
    }

    // Stacked bar config: use stack property
    if (vizType === 'stacked_bar' || vizType === 'stacked_area') {
      base.stack = 'total';
      base.areaStyle = vizType === 'stacked_area' ? { opacity: 0.6 } : undefined;
    }

    // Bubble: map 3rd dimension to symbolSize
    if (vizType === 'bubble' && series.z?.[0]) {
      base.symbolSize = (value, params) => {
        const sizes = series.z[params.dataIndex] || 10;
        return Math.max(8, sizes / 10);
      };
    }

    // Effect scatter — ripple animation (needs data encoding from the block above)
    if (vizType === 'effect_scatter') {
      base.rippleEffect = { period: 4, scale: 2.5, brushType: 'stroke' };
    }

    // Pictorial bar — symbol icons (needs data encoding from the block above)
    if (vizType === 'pictorial_bar') {
      base.symbol = series.pictorial_symbol || 'circle';
      base.symbolRepeat = true;
      base.symbolSize = [20, 10];
    }
  }

  // ── Pie / Donut ──
  if (echartType === 'pie') {
    base.data = (series.labels || []).map((label, i) => ({
      name: label,
      value: series.values?.[i] ?? 0,
      itemStyle: { color: DEFAULT_COLORS[i % DEFAULT_COLORS.length] },
    }));

    // Rose diagram from variant_config
    if (vis.variant_config?.rose_type) {
      base.roseType = vis.variant_config.rose_type;
    }

    // Donut hole from variant_config
    const holeRatio = vis.variant_config?.donut_hole;
    if (holeRatio != null) {
      const inner = Math.round(holeRatio * 100);
      const outer = 100;
      base.radius = [`${inner}%`, `${outer}%`];
    } else if (vizType === 'donut') {
      base.radius = ['40%', '70%'];
    }

    base.avoidLabelOverlap = true;
    base.label = { show: false };
    base.emphasis = {
      label: { show: true, fontSize: 14, fontWeight: 'bold' },
    };
  }

  // ── Heatmap / Correlation Matrix ──
  if (echartType === 'heatmap') {
    if (series.z) {
      const xLabels = series.x_labels || [];
      const yLabels = series.y_labels || [];
      const heatData = [];
      for (let i = 0; i < (series.z?.length || 0); i++) {
        for (let j = 0; j < (series.z[i]?.length || 0); j++) {
          heatData.push([j, i, series.z[i][j] || 0]);
        }
      }
      base.data = heatData;
    }

    if (vizType === 'correlation_matrix') {
      base.visualMap = {
        min: -1, max: 1, inRange: { color: ['#e74c3c', '#ffffff', '#2ecc71'] },
        calculable: true,
      };
    } else {
      base.visualMap = {
        min: 0, max: null, inRange: { color: ['#f5f5f5', '#6366f1'] },
        calculable: true,
      };
    }
  }

  // ── Box Plot ──
  if (echartType === 'boxplot') {
    base.data = series.y_raw
      ? [computeBoxStats(series.y_raw)]
      : [];
  }

  // ── Candlestick ──
  if (echartType === 'candlestick') {
    base.data = (series.x || []).map((xv, i) => ({
      name: String(xv),
      value: [
        series.open?.[i] ?? 0,
        series.close?.[i] ?? 0,
        series.low?.[i] ?? 0,
        series.high?.[i] ?? 0,
      ],
    }));
    base.itemStyle = {
      color: '#34d399',
      color0: '#f87171',
      borderColor: '#34d399',
      borderColor0: '#f87171',
    };
  }

  // ── Radar ──
  if (echartType === 'radar') {
    if (series.r && series.theta) {
      base.data = [series.r.reduce((acc, v, i) => {
        acc[series.theta[i]] = v;
        return acc;
      }, {})];
    }
    base.areaStyle = { opacity: 0.2 };
    base.lineStyle = { width: 2 };
  }

  // ── Treemap / Sunburst ──
  if (echartType === 'treemap' || echartType === 'sunburst') {
    if (series.ids && series.parents) {
      base.data = buildHierarchyTree(series.ids, series.parents, series.values);
    }
    if (echartType === 'sunburst') {
      base.radius = ['0%', '90%'];
    }
  }

  // ── Funnel ──
  if (echartType === 'funnel') {
    base.data = (series.x || []).map((xv, i) => ({
      name: String(xv),
      value: series.y?.[i] ?? 0,
    }));
    base.left = '10%';
    base.right = '10%';
    base.sort = 'descending';
  }

  // ── Gauge ──
  if (echartType === 'gauge') {
    const maxVal = series.gauge_max || (series.value ? series.value * 1.5 : 100);
    base.min = 0;
    base.max = maxVal;
    base.detail = { formatter: `{value}` };
    base.data = [{ value: series.value ?? 0, name: series.name || '' }];
    base.axisLine = { lineStyle: { width: 15 } };
    base.splitLine = { length: 10 };

    // Gauge variants
    if (vis.variant_config?.gauge_progress) {
      base.progress = { show: true, width: 15 };
    }
    if (vis.variant_config?.gauge_pointer !== false) {
      base.pointer = { show: true, length: '60%', width: 4 };
    } else {
      base.pointer = { show: false };
    }

    // Bullet: gauge with fixed threshold
    if (vizType === 'bullet') {
      base.progress = { show: true, width: 15 };
      base.pointer = { show: true };
      if (series.target != null) {
        base.markLine = {
          silent: true,
          data: [{ yAxis: series.target, label: { show: true, formatter: 'Target: {c}' } }],
        };
      }
    }
  }

  // ── Graph ──
  if (echartType === 'graph') {
    base.nodes = (series.nodes || []).map(n => ({
      name: n.name,
      value: n.value,
      category: n.category,
      x: n.x,
      y: n.y,
      symbol: n.symbol,
      symbolSize: n.symbol_size || 10,
    }));
    base.links = (series.links || []).map(l => ({
      source: l.source,
      target: l.target,
      value: l.value,
      label: l.label ? { show: true, formatter: l.label } : undefined,
    }));
    base.categories = [];
    base.roam = vis.variant_config?.graph_roam ?? true;
    base.draggable = true;
    base.layout = vis.variant_config?.graph_layout || 'force';
    base.force = {
      repulsion: vis.variant_config?.graph_force_repulsion || 300,
      edgeLength: [50, 150],
    };
    base.lineStyle = { color: 'source', curveness: 0.3, width: 1, opacity: 0.5 };
    base.emphasis = { focus: 'adjacency' };
    base.label = { show: true, position: 'right', fontSize: 11 };
  }

  // ── Sankey ──
  if (echartType === 'sankey') {
    base.data = (series.nodes || []).map(n => ({ name: n.name }));
    base.links = (series.links || []).map(l => ({
      source: l.source,
      target: l.target,
      value: l.value ?? 1,
    }));
    base.nodeWidth = 20;
    base.nodeGap = 8;
    base.layoutIterations = 32;
    base.label = { show: true, fontSize: 11 };
    base.lineStyle = { color: 'gradient', curveness: 0.5 };
  }

  // ── Parallel ──
  if (echartType === 'parallel') {
    base.data = series.data_rows || [];
    base.lineStyle = { width: 1, opacity: 0.3 };
  }

  // ── Lines (flow/migration) ──
  if (echartType === 'lines') {
    base.data = (series.coords || []).map(c => ({
      coords: c,
      lineStyle: { width: 1, opacity: 0.5 },
    }));
    base.effect = {
      show: true,
      period: 6,
      trailLength: 0.2,
      symbol: 'arrow',
      symbolSize: 6,
    };
    base.polyline = true;
    base.lineStyle = { width: 1, opacity: 0.3, curveness: 0.2 };
  }

  // ── ThemeRiver ──
  if (echartType === 'themeRiver') {
    base.data = series.theme_data || [];
    base.label = { show: true, fontSize: 11 };
  }

  // ── Tree ──
  if (echartType === 'tree') {
    const rootNode = series.children?.[0] || series.nodes?.[0];
    base.data = rootNode ? [convertTreeData(rootNode)] : [];
    base.layout = 'orthogonal';
    base.orient = 'LR';
    base.roam = true;
    base.label = { show: true, position: 'right', fontSize: 11 };
    base.expandAndCollapse = true;
    base.initialTreeDepth = 2;
    base.leafDepth = 2;
  }

  // ── Map / Choropleth ──
  if (echartType === 'map') {
    base.map = vis.variant_config?.map_name || 'world';
    base.roam = vis.variant_config?.map_roam ?? true;
    base.data = (series.locations || []).map((loc, i) => ({
      name: loc,
      value: series.z_geo?.[i] ?? 0,
    }));
    base.selectedMode = 'single';
    base.label = { show: true, fontSize: 10 };
    base.emphasis = { label: { show: true } };
    base.visualMap = {
      min: 0, max: null, inRange: { color: ['#e0e7ff', '#6366f1', '#312e81'] },
      calculable: true,
    };
  }

  // ── Waterfall (via custom bar config) ──
  if (vizType === 'waterfall') {
    const yData = series.y || [];
    const measure = series.measure || [];
    let runningTotal = 0;
    base.data = yData.map((yv, i) => {
      if (measure[i] === 'total') {
        runningTotal = yv;
        return { value: yv, itemStyle: { color: '#6366f1' } };
      }
      const baseVal = runningTotal;
      runningTotal += yv;
      return {
        value: runningTotal,
        itemStyle: {
          color: yv >= 0 ? '#34d399' : '#f87171',
        },
      };
    });
    base.stack = 'waterfall';
  }

  return base;
}

// ── Multi-series strategy ───────────────────────────────────────────

function applyStrategy(seriesList, vizType, vis) {
  const strategy = vis.series_strategy;

  if (strategy === 'grouped') {
    // Default ECharts behavior — multiple bar series are grouped
    seriesList.forEach(s => { s.barGap = '20%'; });
  } else if (strategy === 'stacked') {
    seriesList.forEach(s => { s.stack = 'total'; });
  } else if (strategy === 'dual_axis') {
    const mid = Math.ceil(seriesList.length / 2);
    seriesList.forEach((s, idx) => {
      s.yAxisIndex = idx >= mid ? 1 : 0;
    });
  } else if (strategy === 'combo') {
    seriesList.forEach((s, idx) => {
      if (idx === 0) {
        s.type = 'bar';
        s.yAxisIndex = 0;
      } else {
        s.type = 'line';
        s.yAxisIndex = 1;
        s.smooth = true;
      }
    });
  }
}

// ── Variant configuration ───────────────────────────────────────────

function applyVariants(seriesList, vizType, vc, option) {
  if (!vc) return;

  // Line variants
  if (vc.step && ['line', 'multi_line', 'area'].includes(vizType)) {
    seriesList.forEach(s => { s.step = vc.step; });
  }
  if (vc.smooth && ['line', 'multi_line', 'area'].includes(vizType)) {
    seriesList.forEach(s => { s.smooth = true; });
  }
  if (vc.show_area && ['line', 'multi_line'].includes(vizType)) {
    seriesList.forEach(s => { s.areaStyle = { opacity: 0.2 }; });
  }

  // Bar variants
  if (vc.orientation === 'horizontal' && ['bar', 'grouped_bar', 'stacked_bar'].includes(vizType)) {
    // Swap xAxis/yAxis configuration in option
    const xAxis = option.xAxis;
    const yAxis = option.yAxis;
    option.xAxis = { ...yAxis, type: 'value' };
    option.yAxis = { ...xAxis, type: 'category' };
  }

  if (vc.realtime_sort && ['bar', 'grouped_bar'].includes(vizType)) {
    seriesList.forEach(s => { s.realtimeSort = true; });
  }

  if (vc.show_background && ['bar', 'grouped_bar', 'stacked_bar'].includes(vizType)) {
    seriesList.forEach(s => { s.showBackground = true; });
  }

  // Scatter variants
  if (vc.effect_ripple && vizType === 'scatter') {
    seriesList.forEach(s => {
      s.type = 'effectScatter';
      s.rippleEffect = { period: 4, scale: 2.5, brushType: 'stroke' };
    });
  }

  // Gauge variants
  if (vc.gauge_progress && vizType === 'gauge') {
    seriesList.forEach(s => { s.progress = { show: true, width: 15 }; });
  }
  if (vc.gauge_pointer === false) {
    seriesList.forEach(s => { s.pointer = { show: false }; });
  }

  // Graph variants
  if (vc.graph_layout && vizType === 'graph') {
    seriesList.forEach(s => { s.layout = vc.graph_layout; });
  }
  if (vc.graph_roam != null) {
    seriesList.forEach(s => { s.roam = vc.graph_roam; });
  }

  // Map variants
  if (vc.map_name && vizType === 'map') {
    seriesList.forEach(s => { s.map = vc.map_name; });
  }
  if (vc.map_roam != null) {
    seriesList.forEach(s => { s.roam = vc.map_roam; });
  }
}

// ── Analytics overlays ──────────────────────────────────────────────

function applyAnalytics(analytics, option, theme) {
  const markLines = [];

  // Reference lines -> ECharts markLine
  for (const ref of (analytics.reference_lines || [])) {
    markLines.push({
      yAxis: ref.value,
      label: { formatter: `${ref.label}: ${formatNumber(ref.value)}` },
      lineStyle: {
        color: ref.color || '#3b82f6',
        type: ref.dash === 'dash' ? 'dashed' : ref.dash === 'dot' ? 'dotted' : 'solid',
        width: 1.5,
      },
    });
  }

  // Show average/median via markLine on first series
  if (analytics.show_average || analytics.show_median) {
    const label = analytics.show_average ? 'Avg' : 'Median';
    // markLine will be added per-series by the frontend consumer
  }

  if (markLines.length > 0) {
    option.markLine = { silent: true, data: markLines };
  }

  // Anomaly points -> emphasis style
  if (analytics.show_anomalies && analytics.outlier_indices?.length > 0) {
    option.outlier_indices = analytics.outlier_indices;
  }
}

// ── Helper: Box plot statistics ─────────────────────────────────────

function computeBoxStats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  const q1 = sorted[Math.floor(n * 0.25)];
  const median = sorted[Math.floor(n * 0.5)];
  const q3 = sorted[Math.floor(n * 0.75)];
  const iqr = q3 - q1;
  const min = Math.max(sorted[0], q1 - 1.5 * iqr);
  const max = Math.min(sorted[n - 1], q3 + 1.5 * iqr);
  return [min, q1, median, q3, max];
}

// ── Helper: Build tree hierarchy from flat ids/parents ──────────────

function buildHierarchyTree(ids, parents, values) {
  const nodeMap = {};
  const tree = [];

  // Create all nodes
  ids.forEach((id, i) => {
    nodeMap[id] = { name: String(id), children: [], value: values?.[i] ?? 0 };
  });

  // Build parent-child relationships
  ids.forEach((id, i) => {
    const parent = parents[i];
    if (parent && nodeMap[parent]) {
      nodeMap[parent].children.push(nodeMap[id]);
    } else if (!parent) {
      tree.push(nodeMap[id]);
    }
  });

  return tree.length === 1 ? tree[0] : tree;
}

// ── Helper: Convert VISNode to tree data ────────────────────────────

function convertTreeData(node) {
  const result = {
    name: node.name,
    value: node.value,
  };
  if (node.children?.length) {
    result.children = node.children.map(convertTreeData);
  }
  return result;
}

// ── Utility ─────────────────────────────────────────────────────────

function formatNumber(val) {
  if (typeof val !== 'number') return String(val);
  if (val >= 1e9) return (val / 1e9).toFixed(1) + 'B';
  if (val >= 1e6) return (val / 1e6).toFixed(1) + 'M';
  if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K';
  return val.toLocaleString();
}

// ── Vis → ECharts option (compat entry point) ───────────────────────

/**
 * Convert VIS to ECharts option object.
 * This is the primary entry point for frontend consumers.
 */
export function visToOption(vis, options = {}) {
  return renderVis(vis, options);
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

export default { renderVis, visToOption, isVIS };
