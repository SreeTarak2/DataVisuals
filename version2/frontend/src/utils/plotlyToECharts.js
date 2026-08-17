/**
 * plotlyToECharts.js
 * ===================
 * Converts backend Plotly-format chart data (traces + layout) into
 * Apache ECharts option objects.
 *
 * Every chart type supported by backend hydrate.py:
 *   bar, line, area, scatter, pie, heatmap, box_plot, treemap, sunburst,
 *   grouped_bar, stacked_bar, multi_line, stacked_area, radar, bubble,
 *   waterfall, funnel, candlestick, violin, gauge, bullet, choropleth,
 *   indicator, scatterpolar, correlation_matrix
 *
 * Usage:
 *   import { plotlyToECharts } from '../../utils/plotlyToECharts';
 *   const option = plotlyToECharts(traces, chartType, layout, { theme: 'dark' });
 */

const DEFAULT_COLORS = [
  '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#ec4899', '#8b5cf6', '#14b8a6', '#f97316', '#84cc16',
  '#0ea5e9', '#a855f7', '#22d3ee', '#34d399', '#fbbf24',
];

const MULTI_SERIES_COLORS = [
  '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#ec4899', '#8b5cf6', '#14b8a6', '#f97316', '#84cc16',
];

/**
 * Determines whether a chart type supports axis-based interactions
 * (dataZoom, brush, crosshair tooltip).
 */
function supportsAxisInteraction(chartType) {
  const nonAxis = new Set([
    'pie', 'donut', 'treemap', 'sunburst', 'radar', 'gauge', 'bullet',
    'graph', 'sankey', 'parallel', 'theme_river', 'map', 'choropleth',
    'scatterpolar', 'funnel', 'indicator',
  ]);
  return !nonAxis.has(chartType);
}

/**
 * Map Plotly trace types to ECharts series types.
 */
function mapTraceType(plotlyType, plotlyMode, chartType) {
  const t = (plotlyType || chartType || '').toLowerCase();

  if (t === 'scatter' && plotlyMode === 'lines') return 'line';
  if (t === 'scatter' && plotlyMode === 'lines+markers') return 'line';
  if (t === 'scatter' && plotlyMode === 'markers') return 'scatter';
  if (t === 'scatter') return 'line';
  if (t === 'scatterpolar') return 'radar';
  if (t === 'indicator') return 'gauge';
  if (t === 'box') return 'boxplot';
  if (t === 'choropleth') return 'map';

  const map = {
    bar: 'bar',
    line: 'line',
    area: 'line',
    pie: 'pie',
    donut: 'pie',
    scatter: 'scatter',
    heatmap: 'heatmap',
    histogram: 'bar',
    box_plot: 'boxplot',
    treemap: 'treemap',
    sunburst: 'sunburst',
    radar: 'radar',
    funnel: 'funnel',
    waterfall: 'bar',
    candlestick: 'candlestick',
    violin: 'boxplot',
    gauge: 'gauge',
    bullet: 'gauge',
    indicator: 'gauge',
    scatterpolar: 'radar',
    correlation_matrix: 'heatmap',
    multi_line: 'line',
    grouped_bar: 'bar',
    stacked_bar: 'bar',
    stacked_area: 'line',
    dual_axis: 'line',
    combo: 'bar',
    facet: 'line',
    small_multiples: 'line',
    graph: 'graph',
    sankey: 'sankey',
    parallel: 'parallel',
    lines: 'lines',
    tree: 'tree',
    theme_river: 'themeRiver',
    pictorial_bar: 'pictorialBar',
    effect_scatter: 'effectScatter',
    map: 'map',
    bubble: 'scatter',
  };
  return map[t] || 'bar';
}

function getFormatHint(trace, role) {
  const meta = trace._axis_metadata || {};
  return (role === 'x' ? meta.x : meta.y) || {};
}

/**
 * Build a value formatter from a backend semantic format hint.
 *
 * The backend attaches `_axis_metadata.y = { format, semantic_type }` on
 * traces (e.g. "currency", "percentage", "duration", "rank"). This turns
 * those hints into real axis-label + tooltip formatting so charts respect
 * the semantics of the data without the LLM writing format strings.
 */
function buildValueFormatter(hint = {}) {
  const type = hint.semantic_type || hint.format || '';
  return (value) => {
    if (value == null || value === '') return '—';
    // Pass through non-numeric labels untouched (categorical names, ISO
    // dates, etc.) — never mangle them into "—". Trim whitespace-only
    // strings first so they don't coerce to 0 via isNaN.
    if (typeof value === 'string') {
      if (value.trim() === '') return value;
      if (isNaN(value)) return value;
    }
    const num = Number(value);
    if (!Number.isFinite(num)) return String(value);
    switch (type) {
      case 'currency':
        if (Math.abs(num) >= 1e9) return '$' + (num / 1e9).toFixed(1) + 'B';
        if (Math.abs(num) >= 1e6) return '$' + (num / 1e6).toFixed(1) + 'M';
        if (Math.abs(num) >= 1e3) return '$' + (num / 1e3).toFixed(1) + 'K';
        return '$' + num.toLocaleString();
      case 'percentage':
        return num.toFixed(1) + '%';
      case 'ratio':
        return (num * 100).toFixed(1) + '%';
      case 'temperature':
        return num.toFixed(0) + '°';
      case 'duration': {
        const s = num / 1000;
        if (s >= 3600) return (s / 3600).toFixed(1) + 'h';
        if (s >= 60) return (s / 60).toFixed(1) + 'm';
        return s.toFixed(1) + 's';
      }
      case 'rank':
      case 'integer':
        return Math.round(num).toLocaleString();
      // Non-numeric semantic types must pass the raw label through —
      // even when it *looks* numeric (e.g. year "2024", zip code "007").
      case 'categorical':
      case 'dimension':
      case 'identifier':
      case 'boolean':
      case 'date':
      case 'datetime':
      case 'year_month':
        return value;
      default:
        // Legacy traces without metadata: never compact string labels
        // (year "2024" must stay "2024", not "2K").
        if (typeof value === 'string') return value;
        return fmtNum(num);
    }
  };
}

function isDarkTheme(theme) {
  return theme === 'dark' || theme !== 'light';
}

/**
 * Format a number for display.
 */
function fmtNum(v) {
  if (v == null || isNaN(v)) return '—';
  if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(1) + 'B';
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2);
}

/**
 * Main converter: Plotly traces + layout → ECharts option.
 */
export function plotlyToECharts(traces, chartType, layout = {}, options = {}) {
  const { theme = 'dark', title: overrideTitle, onPointClick, chartTitle } = options;
  const isDark = isDarkTheme(theme);
  const bg = isDark ? '#000000' : '#ffffff';
  const textColor = isDark ? '#f0f2f5' : '#1F2937';
  const gridColor = isDark ? '#2a2a2a' : '#E5E7EB';
  const mutedColor = isDark ? '#9ca3af' : '#9ca3af';

  const actualChartType = (chartType || 'bar').toLowerCase();
  const isLineType = actualChartType === 'line' || actualChartType === 'multi_line' ||
    actualChartType === 'area' || actualChartType === 'stacked_area';
  const isPie = actualChartType === 'pie' || actualChartType === 'donut';
  const isScatter = actualChartType === 'scatter' || actualChartType === 'bubble';
  const isHeatmap = actualChartType === 'heatmap' || actualChartType === 'correlation_matrix';
  const isRadar = actualChartType === 'radar' || actualChartType === 'scatterpolar';
  const isBar = actualChartType === 'bar' || actualChartType === 'grouped_bar' ||
    actualChartType === 'stacked_bar' || actualChartType === 'histogram';

  const traceArray = Array.isArray(traces) ? traces : (traces ? [traces] : []);
  const isStacked = traceArray.some(t => t._stacked);

  // ── Semantic formatting hints from backend `_axis_metadata` ──
  const yFormatter = buildValueFormatter(traceArray[0] ? getFormatHint(traceArray[0], 'y') : {});
  const xFormatter = buildValueFormatter(traceArray[0] ? getFormatHint(traceArray[0], 'x') : {});
  const axisTitles = {
    x: layout?.xaxis?.title?.text || '',
    y: layout?.yaxis?.title?.text || '',
  };

  // ── Build ECharts series from traces ──
  const series = traceArray.map((trace, idx) => {
    if (!trace || trace.error) return null;

    const plotlyType = (trace.type || actualChartType).toLowerCase();
    const echartType = mapTraceType(plotlyType, trace.mode, actualChartType);
    const color = trace.marker?.color || trace.line?.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length];
    const name = trace.name || `Series ${idx + 1}`;

    // ── BAR ──
    if (echartType === 'bar') {
      const x = trace.x || [];
      const y = trace.y || [];
      const isHorizontal = trace.orientation === 'h';
      const itemStyle = {};
      if (trace.marker?.color) {
        itemStyle.color = trace.marker.color;
      }
      if (trace._stacked) {
        itemStyle.stack = 'total';
      }
      return {
        type: 'bar',
        name,
        data: x.map((xv, i) => (isHorizontal ? [y[i], xv] : [xv, y[i] != null ? y[i] : 0])),
        itemStyle: { color: trace.marker?.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length], ...itemStyle },
        barGap: isStacked ? '-100%' : '20%',
        barCategoryGap: isStacked ? '0%' : '20%',
        emphasis: { focus: 'series' },
      };
    }

    // ── LINE / AREA ──
    if (echartType === 'line') {
      const x = trace.x || [];
      const y = trace.y || [];
      const isArea = trace.fill === 'tozeroy' || trace.fill === 'tonexty' || actualChartType === 'area' || actualChartType === 'stacked_area';
      const hasMarkers = trace.mode !== 'lines' || (x.length <= 80);

      const lineColor = trace.line?.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length];
      const fillColor = trace.fillcolor || (lineColor + '18');

      const seriesItem = {
        type: 'line',
        name,
        data: x.map((xv, i) => [xv, y[i] != null ? y[i] : null]),
        lineStyle: { color: lineColor, width: trace.line?.width || 2.5 },
        itemStyle: { color: lineColor },
        smooth: trace.line?.shape === 'spline' || trace.line?.smoothing > 0,
        showSymbol: hasMarkers,
        symbolSize: 6,
        connectNulls: false,
        emphasis: { focus: 'series' },
      };

      if (isArea) {
        seriesItem.areaStyle = {
          color: fillColor,
          opacity: 0.3,
        };
        if (trace._stacked || actualChartType === 'stacked_area') {
          seriesItem.stack = 'total';
          seriesItem.areaStyle.opacity = 0.6;
        }
      }

      return seriesItem;
    }

    // ── SCATTER ──
    if (echartType === 'scatter') {
      const x = trace.x || [];
      const y = trace.y || [];

      // Bubble: check for size data
      let symbolSize = (val, params) => 8;
      const markerSize = trace.marker?.size;
      const hasSizes = Array.isArray(markerSize) && markerSize.length > 0;

      if (hasSizes) {
        const sizes = markerSize;
        const minSize = Math.min(...sizes);
        const maxSize = Math.max(...sizes);
        const range = maxSize - minSize || 1;
        symbolSize = (val, params) => {
          const s = sizes[params.dataIndex] || minSize;
          return 6 + 24 * ((s - minSize) / range);
        };
      }

      const markerColor = trace.marker?.color || DEFAULT_COLORS[0];
      const colorArray = Array.isArray(markerColor) ? markerColor : undefined;

      return {
        type: 'scatter',
        name,
        data: x.map((xv, i) => ({
          value: [xv, y[i] != null ? y[i] : 0],
          itemStyle: colorArray ? { color: colorArray[i % colorArray.length] } : undefined,
        })),
        symbolSize,
        itemStyle: {
          color: !colorArray ? markerColor : undefined,
          borderColor: isDark ? '#1e293b' : '#ffffff',
          borderWidth: 1.5,
        },
        emphasis: { focus: 'series', itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      };
    }

    // ── PIE ──
    if (echartType === 'pie') {
      const labels = trace.labels || [];
      const values = trace.values || [];
      const isDonut = actualChartType === 'donut' || trace.hole > 0;
      const holeRatio = trace.hole || (isDonut ? 0.4 : 0);

      return {
        type: 'pie',
        name,
        data: labels.map((label, i) => ({
          name: String(label),
          value: values[i] != null ? values[i] : 0,
          itemStyle: { color: DEFAULT_COLORS[i % DEFAULT_COLORS.length] },
        })),
        radius: holeRatio ? [`${Math.round(holeRatio * 100)}%`, '70%'] : ['0%', '65%'],
        center: ['50%', '55%'],
        avoidLabelOverlap: true,
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold' },
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' },
        },
        itemStyle: {
          borderColor: isDark ? '#1e293b' : '#ffffff',
          borderWidth: 2,
        },
      };
    }

    // ── HEATMAP ──
    if (echartType === 'heatmap') {
      const z = trace.z || [];
      const xLabels = trace.x || [];
      const yLabels = trace.y || [];
      const data = [];
      for (let i = 0; i < z.length; i++) {
        if (Array.isArray(z[i])) {
          for (let j = 0; j < z[i].length; j++) {
            data.push([j, i, z[i][j] || 0]);
          }
        }
      }
      const isCorrelation = actualChartType === 'correlation_matrix' || trace.colorscale === 'RdBu';

      return {
        type: 'heatmap',
        name,
        data,
        xAxisIndex: 0,
        yAxisIndex: 0,
        label: {
          show: data.length <= 100,
          fontSize: 10,
          color: isDark ? '#d1d5db' : '#374151',
        },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' },
        },
        visualMap: isCorrelation
          ? { min: -1, max: 1, inRange: { color: ['#d73027', '#ffffff', '#1a9850'] }, calculable: true, orient: 'horizontal', left: 'center', bottom: 0 }
          : { min: 0, max: null, inRange: { color: ['#f5f5f5', '#6366f1'] }, calculable: true, orient: 'horizontal', left: 'center', bottom: 0 },
      };
    }

    // ── BOXPLOT ──
    if (echartType === 'boxplot') {
      return {
        type: 'boxplot',
        name,
        data: trace.y ? [trace.y] : [],
        itemStyle: { color: DEFAULT_COLORS[idx % DEFAULT_COLORS.length] },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      };
    }

    // ── TREEMAP ──
    if (echartType === 'treemap') {
      const ids = trace.ids || [];
      const parents = trace.parents || [];
      const labels = trace.labels || [];
      const values = trace.values || [];
      // Build tree structure from flat ids/parents
      const nodeMap = {};
      ids.forEach((id, i) => {
        nodeMap[id] = { name: String(labels[i] || id), value: values[i] || 0, children: [] };
      });
      const roots = [];
      ids.forEach((id, i) => {
        const parent = parents[i];
        if (parent && nodeMap[parent]) {
          nodeMap[parent].children.push(nodeMap[id]);
        } else if (!parent || parent === 'root' || parent === '') {
          roots.push(nodeMap[id]);
        }
      });
      return {
        type: 'treemap',
        name,
        data: roots.length === 1 ? roots[0].children : roots,
        roam: true,
        drillDownIcon: '▶',
        label: { show: true, fontSize: 12, color: '#fff' },
        itemStyle: { borderColor: isDark ? '#1e293b' : '#fff', borderWidth: 2 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      };
    }

    // ── SUNBURST ──
    if (echartType === 'sunburst') {
      const ids = trace.ids || [];
      const parents = trace.parents || [];
      const labels = trace.labels || [];
      const values = trace.values || [];
      const nodeMap = {};
      ids.forEach((id, i) => {
        nodeMap[id] = { name: String(labels[i] || id), value: values[i] || 0, children: [] };
      });
      const roots = [];
      ids.forEach((id, i) => {
        const parent = parents[i];
        if (parent && nodeMap[parent]) {
          nodeMap[parent].children.push(nodeMap[id]);
        } else if (!parent || parent === '') {
          roots.push(nodeMap[id]);
        }
      });
      return {
        type: 'sunburst',
        name,
        data: roots.length === 1 ? roots[0].children : roots,
        radius: ['0%', '90%'],
        label: { fontSize: 11, color: isDark ? '#e5e7eb' : '#374151' },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      };
    }

    // ── RADAR ──
    if (echartType === 'radar') {
      const r = trace.r || [];
      const theta = trace.theta || [];
      return {
        type: 'radar',
        name,
        data: [{ value: r, name }],
        areaStyle: { opacity: 0.15, color: DEFAULT_COLORS[idx % DEFAULT_COLORS.length] },
        lineStyle: { color: DEFAULT_COLORS[idx % DEFAULT_COLORS.length], width: 2 },
        itemStyle: { color: DEFAULT_COLORS[idx % DEFAULT_COLORS.length] },
        emphasis: { lineStyle: { width: 3 } },
      };
    }

    // ── FUNNEL ──
    if (echartType === 'funnel') {
      const x = trace.x || [];
      const y = trace.y || [];
      const items = (x.length ? x : (trace.labels || [])).map((label, i) => ({
        name: String(label),
        value: (trace.values || y || [])[i] || 0,
      }));
      return {
        type: 'funnel',
        name,
        data: items,
        left: '10%',
        right: '10%',
        sort: 'descending',
        label: { show: true, position: 'inside', fontSize: 12, color: '#fff' },
        emphasis: { label: { fontSize: 14 } },
      };
    }

    // ── CANDLESTICK ──
    if (echartType === 'candlestick') {
      const x = trace.x || [];
      const open = trace.open || [];
      const high = trace.high || [];
      const low = trace.low || [];
      const close = trace.close || [];
      return {
        type: 'candlestick',
        name,
        data: x.map((xv, i) => [open[i], close[i], low[i], high[i]]),
        itemStyle: {
          color: '#34d399',
          color0: '#f87171',
          borderColor: '#34d399',
          borderColor0: '#f87171',
        },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      };
    }

    // ── GAUGE ──
    if (echartType === 'gauge') {
      const val = trace.value || 0;
      const maxVal = trace.gauge?.axis?.range?.[1] || val * 1.5 || 100;
      return {
        type: 'gauge',
        name,
        data: [{ value: val, name }],
        min: 0,
        max: maxVal,
        axisLine: { lineStyle: { width: 15, color: [[0.5, '#34d399'], [0.8, '#fbbf24'], [1, '#f87171']] } },
        pointer: { show: true, length: '60%', width: 4 },
        detail: { formatter: `{value}`, fontSize: 16, color: textColor },
        title: { fontSize: 12, color: mutedColor },
      };
    }

    // ── GRAPH ──
    if (echartType === 'graph') {
      return {
        type: 'graph',
        name,
        nodes: (trace.nodes || []).map(n => ({
          name: n.name || n.id || '',
          value: n.value,
          symbolSize: (n.symbol_size || n.value || 10) / 5 + 5,
          category: n.category,
        })),
        links: (trace.links || []).map(l => ({
          source: l.source,
          target: l.target,
          value: l.value,
        })),
        roam: true,
        draggable: true,
        layout: 'force',
        force: { repulsion: 300, edgeLength: [50, 150] },
        lineStyle: { color: 'source', curveness: 0.3, width: 1, opacity: 0.5 },
        emphasis: { focus: 'adjacency' },
        label: { show: true, position: 'right', fontSize: 10, color: textColor },
      };
    }

    // ── SANKEY ──
    if (echartType === 'sankey') {
      return {
        type: 'sankey',
        name,
        data: (trace.nodes || []).map(n => ({ name: n.name || n.id || '' })),
        links: (trace.links || []).map(l => ({
          source: l.source,
          target: l.target,
          value: l.value || 1,
        })),
        nodeWidth: 20,
        nodeGap: 8,
        layoutIterations: 32,
        label: { fontSize: 11, color: textColor },
        lineStyle: { color: 'gradient', curveness: 0.5 },
        emphasis: { focus: 'adjacency' },
      };
    }

    // ── MAP ──
    if (echartType === 'map') {
      const locations = trace.locations || [];
      const z = trace.z || [];
      return {
        type: 'map',
        name,
        map: 'world',
        roam: true,
        data: locations.map((loc, i) => ({ name: loc, value: z[i] || 0 })),
        label: { show: true, fontSize: 10, color: textColor },
        emphasis: { label: { show: true, fontSize: 14 } },
      };
    }

    // ── PARALLEL ──
    if (echartType === 'parallel') {
      return {
        type: 'parallel',
        name,
        data: trace.data_rows || [],
        lineStyle: { width: 1, opacity: 0.3 },
      };
    }

    // ── THEME_RIVER ──
    if (echartType === 'themeRiver') {
      return {
        type: 'themeRiver',
        name,
        data: trace.theme_data || [],
        label: { fontSize: 11, color: textColor },
      };
    }

    // ── LINES (flow) ──
    if (echartType === 'lines') {
      return {
        type: 'lines',
        name,
        data: (trace.coords || []).map(c => ({ coords: c })),
        polyline: true,
        effect: { show: true, period: 6, trailLength: 0.2, symbol: 'arrow', symbolSize: 6 },
        lineStyle: { width: 1, opacity: 0.3, curveness: 0.2 },
      };
    }

    // ── PICTORIAL BAR ──
    if (echartType === 'pictorialBar') {
      const x = trace.x || [];
      const y = trace.y || [];
      return {
        type: 'pictorialBar',
        name,
        data: x.map((xv, i) => ({ value: [xv, y[i] || 0] })),
        symbol: trace._pictorial_symbol || 'circle',
        symbolRepeat: true,
        symbolSize: [20, 10],
      };
    }

    // ── EFFECT SCATTER ──
    if (echartType === 'effectScatter') {
      const x = trace.x || [];
      const y = trace.y || [];
      return {
        type: 'effectScatter',
        name,
        data: x.map((xv, i) => ({ value: [xv, y[i] || 0] })),
        rippleEffect: { period: 4, scale: 2.5, brushType: 'stroke' },
        itemStyle: { color: DEFAULT_COLORS[idx % DEFAULT_COLORS.length] },
      };
    }

    // Fallback: treat as bar
    const fallbackX = trace.x || [];
    const fallbackY = trace.y || [];
    return {
      type: 'bar',
      name,
      data: fallbackX.map((xv, i) => [xv, fallbackY[i] != null ? fallbackY[i] : 0]),
      itemStyle: { color: DEFAULT_COLORS[idx % DEFAULT_COLORS.length] },
    };
  }).filter(Boolean);

  // ── dataZoom: Range slider + inside zoom for interactive exploration ──
  const hasAxis = supportsAxisInteraction(actualChartType);
  const showZoom = hasAxis && !isHeatmap && !isScatter && series.length > 0;
  const dataZoomConfig = showZoom ? [
    {
      type: 'inside',
      start: 0,
      end: 100,
      zoomOnMouseWheel: true,
      moveOnMouseMove: true,
    },
    {
      type: 'slider',
      start: 0,
      end: 100,
      height: 18,
      bottom: 0,
      borderColor: isDark ? '#374151' : '#D1D5DB',
      fillerColor: isDark ? 'rgba(99,102,241,0.15)' : 'rgba(99,102,241,0.2)',
      handleStyle: { color: isDark ? '#6366f1' : '#6366f1' },
      textStyle: { color: textColor, fontSize: 10 },
      backgroundColor: isDark ? '#1F2937' : '#F3F4F6',
    },
  ] : undefined;

  // ── Brush: Area selection for cross-filtering ──
  const showBrush = hasAxis && !isPie && !isHeatmap && !isScatter;
  const brushConfig = showBrush ? {
    toolbox: ['rect', 'polygon', 'keep', 'clear'],
    brushStyle: { borderWidth: 1, color: 'rgba(99,102,241,0.1)', borderColor: 'rgba(99,102,241,0.5)' },
    throttleType: 'debounce',
    throttleDelay: 300,
  } : undefined;

  // Adjust grid bottom to accommodate dataZoom slider
  const gridBottom = showZoom ? 52 : 35;

  // ── Build ECharts grid option ──
  const titleText = overrideTitle || chartTitle || '';
  const hasSingleSeries = series.length === 1;
  const showLegend = !isPie && hasSingleSeries ? false : series.length > 0;

  // Radar needs special indicator config
  const radarIndicator = isRadar && series[0]?.data?.[0]?.value
    ? series[0].data[0].value.map((v, i) => ({
        name: series[0].name ? `${series[0].name} ${i + 1}` : `Indicator ${i + 1}`,
        max: Math.max(...series.map(s => Math.max(...(s.data?.[0]?.value || [0])))),
      }))
    : undefined;

  // Heatmap axis labels
  const heatmapX = isHeatmap && traceArray[0]?.x ? traceArray[0].x : undefined;
  const heatmapY = isHeatmap && traceArray[0]?.y ? traceArray[0].y : undefined;

  const option = {
    backgroundColor: bg,
    color: DEFAULT_COLORS,
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut',
    textStyle: { fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif' },
    title: titleText ? {
      text: titleText,
      textStyle: { color: textColor, fontSize: 15, fontWeight: 600 },
      left: 'center',
      top: 8,
    } : undefined,
    tooltip: {
      trigger: isPie ? 'item' : 'axis',
      backgroundColor: isDark ? 'rgba(30, 32, 42, 0.96)' : 'rgba(255, 255, 255, 0.95)',
      borderColor: isDark ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)',
      textStyle: { color: isDark ? '#ffffff' : '#1f2937', fontSize: 12 },
      confine: true,
      formatter: function(params) {
        if (!params) return '';
        if (Array.isArray(params)) {
          const lines = params.map(p => {
            const name = p.seriesName || '';
            const val = p.value;
            if (Array.isArray(val)) return `${name}: ${yFormatter(val[1])}`;
            if (typeof val === 'object') return `${name}: ${yFormatter(val.value)}`;
            return `${name}: ${yFormatter(val)}`;
          });
          return `<div style="font-size:12px">${lines.join('<br/>')}</div>`;
        }
        return `<div style="font-size:12px">${params.name}: ${yFormatter(params.value)}</div>`;
      },
    },
    grid: isPie || isRadar || isHeatmap ? undefined : {
      left: 50,
      right: 20,
      top: titleText ? 50 : 30,
      bottom: gridBottom,
      containLabel: true,
    },
    xAxis: isPie || isRadar || isHeatmap ? undefined : {
      type: 'category',
      name: axisTitles.x || undefined,
      nameTextStyle: axisTitles.x ? { color: mutedColor, fontSize: 11, padding: [0, 0, 4, 0] } : undefined,
      axisLine: { lineStyle: { color: isDark ? '#4B5563' : '#D1D5DB' } },
      axisTick: { lineStyle: { color: isDark ? '#4B5563' : '#D1D5DB' } },
      axisLabel: {
        color: textColor,
        fontSize: 11,
        rotate: isBar ? 0 : (isLineType ? 0 : -30),
        formatter: (val) => xFormatter(val),
      },
      splitLine: { show: false },
    },
    yAxis: isPie || isRadar || isHeatmap ? undefined : {
      type: 'value',
      name: axisTitles.y || undefined,
      nameTextStyle: axisTitles.y ? { color: mutedColor, fontSize: 11, padding: [0, 0, 0, 4] } : undefined,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: textColor, fontSize: 11, formatter: (val) => yFormatter(val) },
      splitLine: { lineStyle: { color: gridColor, type: 'dashed' } },
    },
    ...(radarIndicator ? {
      radar: {
        indicator: radarIndicator.map(ind => ({ name: ind.name, max: ind.max })),
        radius: '65%',
        center: ['50%', '55%'],
        splitArea: { areaStyle: { color: [isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)', isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'] } },
      axisLine: { lineStyle: { color: isDark ? '#4B5563' : '#D1D5DB' } },
      splitLine: { lineStyle: { color: isDark ? '#4B5563' : '#D1D5DB' } },
      },
    } : {}),
    ...(isHeatmap ? {
      xAxis: heatmapX ? {
        type: 'category',
        data: heatmapX,
        axisLabel: { color: textColor, fontSize: 10, rotate: 45 },
        splitArea: { show: true },
      } : undefined,
      yAxis: heatmapY ? {
        type: 'category',
        data: heatmapY,
        axisLabel: { color: textColor, fontSize: 10 },
        splitArea: { show: true },
      } : undefined,
    } : {}),
    legend: showLegend && !isHeatmap ? {
      textStyle: { color: textColor, fontSize: 11 },
      top: titleText ? 32 : 8,
      type: 'scroll',
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 8,
    } : undefined,
    dataZoom: dataZoomConfig,
    brush: brushConfig,
    series,
  };

  return option;
}

/**
 * Convert full Plotly chart data (from backend API response) to ECharts option.
 * Handles both {data: [...], layout: {}} and {traces: [...], layout: {}} formats.
 */
export function chartDataToECharts(chartData, chartType, options = {}) {
  if (!chartData) return null;

  const traces = chartData.data || chartData.traces || [];
  const layout = chartData.layout || {};
  const title = chartData.title || chartData.explanation || chartData.chart_type || '';

  return plotlyToECharts(traces, chartType || chartData.chart_type, layout, {
    ...options,
    title: options.title || title,
  });
}

/**
 * Apply a dim effect to an ECharts option for cross-filtering.
 * Matching data points stay at full opacity; non-matching points
 * are dimmed to ~15% opacity so the user can still see the full
 * context of the chart.
 *
 * Mutates the option in-place (safe because the option is created
 * fresh by plotlyToECharts on every render).
 *
 * Handles multiple ECharts data formats:
 *   Array format (bar/line): [[x, y], [x, y], ...]
 *   Object format (scatter): [{value: [x, y], ...}, ...]
 *   Pie format:             [{name: 'label', value: n}, ...]
 *
 * @param {Object} option       — Full ECharts option object (mutated in-place)
 * @param {string|string[]} filterValues — value(s) to KEEP lit (OR semantics;
 *                  a single string is accepted for backward compatibility)
 * @returns {Object}            — Same option reference with dimming applied
 */
export function applyDimEffect(option, filterValues) {
  if (!filterValues || !option?.series) return option;

  const keepSet = new Set(
    (Array.isArray(filterValues) ? filterValues : [filterValues])
      .map((v) => String(v))
  );
  if (keepSet.size === 0) return option;

  // Chart types that don't support x-axis dimming
  const skipTypes = new Set([
    'pie', 'treemap', 'sunburst', 'radar', 'gauge', 'funnel',
    'graph', 'sankey', 'parallel', 'themeRiver', 'map',
    'boxplot', 'heatmap', 'candlestick',
  ]);

  for (let s = 0; s < option.series.length; s++) {
    const series = option.series[s];
    if (!series?.data || !Array.isArray(series.data)) continue;

    const type = (series.type || '').toLowerCase();
    if (skipTypes.has(type)) continue;

    for (let d = 0; d < series.data.length; d++) {
      const item = series.data[d];
      if (item == null) continue;

      let itemX;

      if (Array.isArray(item)) {
        itemX = item[0];
      } else if (typeof item === 'object' && item !== null) {
        if (type === 'pie') {
          itemX = item.name;
        } else if (item.value != null) {
          itemX = Array.isArray(item.value) ? item.value[0] : item.value;
        } else {
          itemX = item.name;
        }
      } else {
        itemX = item;
      }

      const matches = keepSet.has(String(itemX ?? ''));
      if (matches) continue;

      // Dim non-matching item
      if (Array.isArray(item)) {
        // Convert array to object format with dimmed style
        series.data[d] = {
          value: [...item],
          itemStyle: { opacity: 0.15 },
        };
      } else if (typeof item === 'object' && item !== null) {
        series.data[d] = {
          ...item,
          itemStyle: {
            ...(item.itemStyle || {}),
            opacity: 0.15,
          },
        };
      }
    }
  }

  return option;
}

export default { plotlyToECharts, chartDataToECharts, applyDimEffect };
