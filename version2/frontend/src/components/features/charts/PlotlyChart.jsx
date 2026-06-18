import React, { useEffect, useRef, memo, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';

const MotionDiv = motion.div;

const resolvePointColor = (point) => {
  if (!point || !point.fullData) return '#8FA6D8';

  const marker = point.fullData.marker;
  const line = point.fullData.line;

  if (Array.isArray(marker?.colors)) {
    const pointIndex = typeof point.pointNumber === 'number' ? point.pointNumber : 0;
    return marker.colors[pointIndex] || marker.colors[0] || '#8FA6D8';
  }

  if (Array.isArray(marker?.color)) {
    const pointIndex = typeof point.pointNumber === 'number' ? point.pointNumber : 0;
    return marker.color[pointIndex] || marker.color[0] || '#8FA6D8';
  }

  return marker?.color || line?.color || point.color || '#8FA6D8';
};

// ── Smart Downsampling: Largest-Triangle-Three-Buckets (LTTB) ──
// Preserves visual shape while reducing points. Keeps peaks/troughs intact.
const downsampleLTTB = (xArr, yArr, targetPoints) => {
  const len = xArr.length;
  if (len <= targetPoints) return { x: xArr, y: yArr };

  const sampledX = [xArr[0]];
  const sampledY = [yArr[0]];
  const bucketSize = (len - 2) / (targetPoints - 2);

  let prevIndex = 0;
  for (let i = 1; i < targetPoints - 1; i++) {
    const bucketStart = Math.floor((i - 1) * bucketSize) + 1;
    const bucketEnd = Math.min(Math.floor(i * bucketSize) + 1, len);
    const nextBucketStart = Math.floor(i * bucketSize) + 1;
    const nextBucketEnd = Math.min(Math.floor((i + 1) * bucketSize) + 1, len);

    // Average of next bucket for reference
    let avgY = 0, count = 0;
    for (let j = nextBucketStart; j < nextBucketEnd; j++) {
      avgY += (typeof yArr[j] === 'number' ? yArr[j] : 0);
      count++;
    }
    avgY = count > 0 ? avgY / count : 0;

    // Find point in current bucket with max triangle area
    let maxArea = -1, maxIndex = bucketStart;
    const prevY = typeof yArr[prevIndex] === 'number' ? yArr[prevIndex] : 0;
    for (let j = bucketStart; j < bucketEnd; j++) {
      const curY = typeof yArr[j] === 'number' ? yArr[j] : 0;
      const area = Math.abs((prevIndex - nextBucketStart) * (curY - prevY) - (prevIndex - j) * (avgY - prevY));
      if (area > maxArea) { maxArea = area; maxIndex = j; }
    }
    sampledX.push(xArr[maxIndex]);
    sampledY.push(yArr[maxIndex]);
    prevIndex = maxIndex;
  }
  sampledX.push(xArr[len - 1]);
  sampledY.push(yArr[len - 1]);
  return { x: sampledX, y: sampledY };
};

// ── Gradient Color Generator ──
// Creates a per-point color array that transitions from startColor to endColor
const generateGradientColors = (values, startHue = 195, endHue = 260) => {
  if (!values || values.length === 0) return [];
  const numericVals = values.map(v => (typeof v === 'number' ? v : 0));
  const min = Math.min(...numericVals);
  const max = Math.max(...numericVals);
  const range = max - min || 1;
  return numericVals.map(v => {
    const t = (v - min) / range;
    const hue = startHue + t * (endHue - startHue);
    const lightness = 55 + t * 15; // brighter for higher values
    return `hsl(${hue}, 85%, ${lightness}%)`;
  });
};

// ── Find Min/Max Annotations ──
const findMinMaxAnnotations = (xArr, yArr) => {
  if (!yArr || yArr.length < 5) return [];
  const numericY = yArr.map(v => (typeof v === 'number' ? v : 0));
  let minIdx = 0, maxIdx = 0;
  for (let i = 1; i < numericY.length; i++) {
    if (numericY[i] < numericY[minIdx]) minIdx = i;
    if (numericY[i] > numericY[maxIdx]) maxIdx = i;
  }
  const formatAnnotationVal = (v) => {
    if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
    return typeof v === 'number' ? v.toFixed(1) : v;
  };
  const annotations = [];
  if (Math.abs(maxIdx - minIdx) > yArr.length * 0.05) {
    annotations.push({
      x: xArr[maxIdx], y: numericY[maxIdx],
      xref: 'x', yref: 'y',
      text: `▲ ${formatAnnotationVal(numericY[maxIdx])}`,
      showarrow: true, arrowhead: 0, arrowcolor: '#34d399',
      ax: 0, ay: -30,
      font: { color: '#34d399', size: 11, family: 'Inter, sans-serif' },
      bgcolor: 'rgba(16,185,129,0.12)', bordercolor: 'rgba(16,185,129,0.3)',
      borderwidth: 1, borderpad: 4,
    });
    annotations.push({
      x: xArr[minIdx], y: numericY[minIdx],
      xref: 'x', yref: 'y',
      text: `▼ ${formatAnnotationVal(numericY[minIdx])}`,
      showarrow: true, arrowhead: 0, arrowcolor: '#f87171',
      ax: 0, ay: 28,
      font: { color: '#f87171', size: 11, family: 'Inter, sans-serif' },
      bgcolor: 'rgba(248,113,113,0.12)', bordercolor: 'rgba(248,113,113,0.3)',
      borderwidth: 1, borderpad: 4,
    });
  }
  return annotations;
};

// ── Data Density Thresholds ──
const DENSITY = {
  SHOW_MARKERS: 80,       // Show individual markers below this
  DOWNSAMPLE_AT: 300,     // Start downsampling above this
  TARGET_POINTS: 200,     // Downsample to this many points
  DISABLE_SPLINE: 500,    // Use linear interpolation above this
};

const toFiniteNumber = (value) => {
  const num = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(num) ? num : null;
};

const toTimeMs = (value) => {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value.getTime();
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
};

const detectTemporal = (xArr = []) => {
  const sample = xArr.filter(v => v !== null && v !== undefined).slice(0, 40);
  if (sample.length < 3) return false;
  const parseable = sample.filter(v => toTimeMs(v) !== null).length;
  return parseable / sample.length >= 0.8;
};

const pickBucketMs = (spanMs, pointCount, targetPoints) => {
  if (!Number.isFinite(spanMs) || spanMs <= 0 || pointCount <= targetPoints) return null;

  const ideal = spanMs / targetPoints;
  const candidates = [
    60 * 60 * 1000,       // 1h
    3 * 60 * 60 * 1000,   // 3h
    6 * 60 * 60 * 1000,   // 6h
    12 * 60 * 60 * 1000,  // 12h
    24 * 60 * 60 * 1000,  // 1d
    2 * 24 * 60 * 60 * 1000,
    7 * 24 * 60 * 60 * 1000,   // 1w
    14 * 24 * 60 * 60 * 1000,
    30 * 24 * 60 * 60 * 1000,  // ~1mo
    90 * 24 * 60 * 60 * 1000,  // ~1q
  ];

  for (const candidate of candidates) {
    if (candidate >= ideal) return candidate;
  }
  return candidates[candidates.length - 1];
};

const formatTemporalBucket = (bucketStartMs, bucketMs) => {
  const date = new Date(bucketStartMs);
  if (bucketMs >= 24 * 60 * 60 * 1000) {
    return date.toISOString().slice(0, 10);
  }
  return date.toISOString();
};

const normalizeLineSeries = (xArr = [], yArr = [], targetPoints = DENSITY.TARGET_POINTS) => {
  const rows = [];
  const len = Math.min(xArr.length, yArr.length);
  for (let i = 0; i < len; i += 1) {
    const x = xArr[i];
    const y = toFiniteNumber(yArr[i]);
    if (x === null || x === undefined || y === null) continue;
    rows.push({ x, y, i, t: toTimeMs(x) });
  }
  if (rows.length === 0) return { x: [], y: [], meta: { originalPoints: 0, displayedPoints: 0 } };

  const temporal = detectTemporal(rows.map(r => r.x));
  let ordered = rows;

  if (temporal) {
    ordered = [...rows].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
  } else {
    const numericX = rows.map(r => toFiniteNumber(r.x));
    const hasNumericX = numericX.every(v => v !== null);
    if (hasNumericX) {
      ordered = [...rows].sort((a, b) => Number(a.x) - Number(b.x));
    }
  }

  let reduced = ordered;
  let bucketMsUsed = null;

  if (temporal) {
    const minT = ordered[0].t ?? 0;
    const maxT = ordered[ordered.length - 1].t ?? minT;
    const spanMs = maxT - minT;
    const bucketMs = pickBucketMs(spanMs, ordered.length, targetPoints);

    if (bucketMs) {
      const bucketMap = new Map();
      for (const row of ordered) {
        const t = row.t ?? minT;
        const bucketStart = Math.floor(t / bucketMs) * bucketMs;
        const existing = bucketMap.get(bucketStart);
        if (existing) {
          existing.y += row.y;
          existing.count += 1;
        } else {
          bucketMap.set(bucketStart, { t: bucketStart, y: row.y, count: 1 });
        }
      }
      reduced = [...bucketMap.values()]
        .sort((a, b) => a.t - b.t)
        .map(row => ({
          x: formatTemporalBucket(row.t, bucketMs),
          y: row.y,
          i: 0,
          t: row.t,
        }));
      bucketMsUsed = bucketMs;
    } else {
      // Collapse duplicate timestamps while preserving trend semantics.
      const tsMap = new Map();
      for (const row of ordered) {
        const key = row.t ?? 0;
        const existing = tsMap.get(key);
        if (existing) {
          existing.y += row.y;
          existing.count += 1;
        } else {
          tsMap.set(key, { t: key, y: row.y, count: 1 });
        }
      }
      reduced = [...tsMap.values()]
        .sort((a, b) => a.t - b.t)
        .map(row => ({
          x: formatTemporalBucket(row.t, 24 * 60 * 60 * 1000),
          y: row.y,
          i: 0,
          t: row.t,
        }));
    }
  } else {
    const dupMap = new Map();
    for (const row of reduced) {
      const key = String(row.x);
      const existing = dupMap.get(key);
      if (existing) {
        existing.y += row.y;
        existing.count += 1;
      } else {
        dupMap.set(key, { x: row.x, y: row.y, count: 1 });
      }
    }
    reduced = [...dupMap.values()].map(row => ({ x: row.x, y: row.y, i: 0, t: null }));
  }

  let finalX = reduced.map(r => r.x);
  let finalY = reduced.map(r => r.y);
  const needsDownsample = finalX.length > targetPoints;
  if (needsDownsample) {
    const sampled = downsampleLTTB(finalX, finalY, targetPoints);
    finalX = sampled.x;
    finalY = sampled.y;
  }

  return {
    x: finalX,
    y: finalY,
    meta: {
      originalPoints: rows.length,
      preDownsamplePoints: reduced.length,
      displayedPoints: finalX.length,
      temporal,
      bucketMs: bucketMsUsed,
      downsampled: needsDownsample,
    },
  };
};

// ── Rich Color Palettes — Chart-Type Specific ──
// Each chart type gets a visually distinct palette that conveys meaning
const PALETTES = {
  // Bar charts: warm, bold, high-contrast categorical colors
  bar: ['#6366f1', '#E85002', '#E85002', '#c084fc', '#e879f9', '#f472b6', '#fb7185', '#f97316'],
  // Line charts: cool gradient progression (low→high energy)
  line: ['#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc'],
  // Pie/donut: maximally distinct, perceptually balanced (no adjacent similar hues)
  pie: ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#E85002', '#14b8a6', '#f97316', '#84cc16'],
  // Scatter: distinguishable point colors
  scatter: ['#06b6d4', '#E85002', '#34d399', '#fbbf24', '#f87171', '#fb923c'],
  // Box/violin: soft, distinguishable per-group colors
  box: ['#818cf8', '#34d399', '#fbbf24', '#f87171', '#22d3ee', '#E85002', '#fb923c', '#84cc16', '#e879f9', '#2dd4bf',
         '#f472b6', '#a3e635', '#38bdf8', '#c084fc', '#facc15', '#4ade80', '#f43f5e', '#06b6d4', '#d946ef', '#fca5a5'],
  // Heatmap: sequential (handled by colorscale, not palette)
  heatmap: [],
  // Area: layered translucent fills
  area: ['#06b6d4', '#E85002', '#10b981', '#f59e0b', '#ef4444'],
  // Default fallback
  default: ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#E85002', '#14b8a6'],
};

// Get palette for a chart type
const getPalette = (type) => {
  const normalized = (type || '').toLowerCase().replace('_chart', '').replace('_plot', '');
  return PALETTES[normalized] || PALETTES.default;
};

// Apply colors to pre-built Plotly traces that have no color set
// colorOffset rotates the palette starting color so each chart card on the dashboard
// gets a visually distinct primary color even when it has only one trace.
const applyTraceColors = (traces, chartType, colorOffset = 0) => {
  const palette = getPalette(chartType);
  return traces.map((trace, idx) => {
    const color = palette[(idx + colorOffset) % palette.length];
    const traceType = (trace.type || '').toLowerCase();
    const enhanced = { ...trace };

    // Skip if trace already has custom colors set
    const hasCustomColor = trace.marker?.color || trace.marker?.colors || trace.line?.color;
    if (hasCustomColor) return enhanced;

    if (traceType === 'bar') {
      // Bar: each trace gets a solid color with subtle gradient via opacity
      enhanced.marker = {
        ...(trace.marker || {}),
        color: color,
        line: { width: 0 },
      };
    } else if (traceType === 'scatter' && (trace.mode || '').includes('markers')) {
      // Scatter: colored dots with glow border
      enhanced.marker = {
        ...(trace.marker || {}),
        color: color,
        size: trace.marker?.size || 8,
        line: { color: 'rgba(10,13,20,0.6)', width: 1 },
        opacity: 0.85,
      };
    } else if (traceType === 'scatter') {
      // Line: colored line
      enhanced.line = { ...(trace.line || {}), color: color };
    } else if (traceType === 'pie') {
      // Pie: full palette rotation + enforce modern donut styling
      enhanced.hole = trace.hole ?? 0.65;
      enhanced.textinfo = 'none';
      enhanced.marker = {
        ...(trace.marker || {}),
        colors: palette,
        line: { color: 'rgba(10,13,20,0.8)', width: 2 },
      };
    } else if (traceType === 'box' || traceType === 'violin') {
      // Box/violin: each group gets a distinct color
      enhanced.marker = { ...(trace.marker || {}), color: color };
      enhanced.line = { ...(trace.line || {}), color: color };
      enhanced.fillcolor = color + '20'; // 12% opacity fill
    } else if (traceType === 'heatmap') {
      // Heatmap: use a premium colorscale if none set
      if (!trace.colorscale) {
        enhanced.colorscale = [
          [0, '#0c1445'], [0.2, '#1e3a8a'], [0.4, '#3b82f6'],
          [0.6, '#06b6d4'], [0.8, '#34d399'], [1, '#a3e635']
        ];
      }
    }
    else if (traceType === 'indicator') {
      // Bullet/Indicator: use primary color for the bar
      enhanced.number = { font: { color: color, size: 40 } };
      if (enhanced.gauge) {
        enhanced.gauge.bar = { color: color };
      }
    } else if (traceType === 'choropleth') {
      // Choropleth: premium color scale
      if (!enhanced.colorscale) {
        enhanced.colorscale = 'Viridis';
      }
    }

    return enhanced;
  });
};

// Removed CustomTooltip definition per user request.

const PlotlyChart = memo(({ data, layout = {}, style = {}, config = {}, chartType = 'bar', onPointClick, pointIntelligence, chartTitle, colorOffset = 0 }) => {
  const plotRef = useRef(null);
  const resizeObserverRef = useRef(null);
  const resizeFrameRef = useRef(null);
  const dataHashRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Helper to format numbers
  const formatValue = (val) => {
    if (typeof val === 'number') {
      if (val >= 1000000000) return (val / 1000000000).toFixed(1) + 'B';
      if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
      if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
      return val.toLocaleString(); // Add commas
    }
    return val;
  };

  useEffect(() => {
    // Create a simple hash of the data to avoid unnecessary re-renders
    const dataHash = JSON.stringify(data);
    if (dataHash === dataHashRef.current) {
      return; // Data hasn't changed, skip re-render
    }
    dataHashRef.current = dataHash;

    const loadPlotly = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const Plotly = (await import('plotly.js-dist-min')).default;
        if (!plotRef.current || !data) {
          setIsLoading(false);
          return;
        }
        
        if (data && data.length === 0) {
          setError('No data available for chart');
          setIsLoading(false);
          return;
        }
        
        if (plotRef.current && data) {
          let processedData = data;
          let xKey = 'x', yKey = 'y';
          let xLabel = '', yLabel = '';

          // Check if data is already in Plotly format
          // Supports: bar/scatter (x+y), pie (labels+values), box/violin (y only), heatmap (z)
          const isPlotlyFormat = Array.isArray(data) && data.length > 0 &&
            data[0].type !== undefined &&
            (data[0].x !== undefined || data[0].labels !== undefined || data[0].y !== undefined || data[0].z !== undefined);

          if (isPlotlyFormat) {
            // Data is already in Plotly format — enhance line/scatter traces
            processedData = data.map(trace => {
              const enhanced = { ...trace };
              const traceType = (trace.type || '').toLowerCase();

              // Enforce modern donut styling for pie traces regardless of stored state
              if (traceType === 'pie') {
                enhanced.hole = trace.hole ?? 0.65;
                enhanced.textinfo = 'none';
              }

              const isScatterLine = traceType === 'scatter' &&
                (trace.mode === 'lines' || trace.mode === 'lines+markers' || trace.mode === 'lines+text');
              
              if (isScatterLine && Array.isArray(trace.x) && Array.isArray(trace.y)) {
                const normalized = normalizeLineSeries(trace.x, trace.y, DENSITY.TARGET_POINTS);
                enhanced.x = normalized.x;
                enhanced.y = normalized.y;
                enhanced.meta = {
                  ...(trace.meta || {}),
                  totalPoints: normalized.meta.originalPoints,
                  displayedPoints: normalized.meta.displayedPoints,
                  preDownsamplePoints: normalized.meta.preDownsamplePoints,
                  temporal: normalized.meta.temporal,
                  bucketMs: normalized.meta.bucketMs,
                  downsampled: normalized.meta.downsampled,
                };

                const isDense = normalized.meta.displayedPoints > DENSITY.DOWNSAMPLE_AT;
                const displayPts = enhanced.x.length;
                
                // Smart markers: only show when data is sparse enough
                if (displayPts > DENSITY.SHOW_MARKERS) {
                  enhanced.mode = 'lines';
                } else {
                  enhanced.mode = 'lines+markers';
                  const colors = generateGradientColors(enhanced.y, 185, 270);
                  enhanced.marker = {
                    ...(trace.marker || {}),
                    color: colors,
                    size: Math.max(4, Math.min(8, 200 / displayPts)),
                    line: { color: 'rgba(10,13,20,0.8)', width: 1.5 },
                  };
                }
                
                // Line styling: disable spline on dense data
                enhanced.line = {
                  ...(trace.line || {}),
                  width: isDense ? 2.5 : (trace.line?.width || 3),
                  shape: displayPts > DENSITY.DISABLE_SPLINE ? 'linear' : (trace.line?.shape || 'spline'),
                };
              }
              return enhanced;
            });
            
            // Add area fill trace for single-series line charts
            const lineTraces = processedData.filter(t => 
              t.type === 'scatter' && (t.mode === 'lines' || t.mode === 'lines+markers')
            );
            if (lineTraces.length === 1 && lineTraces[0].x?.length > 0) {
              const lt = lineTraces[0];
              const fillColor = lt.line?.color || '#06b6d4';
              processedData.unshift({
                x: lt.x,
                y: lt.y,
                type: 'scatter',
                mode: 'lines',
                line: { color: 'transparent', width: 0 },
                fill: 'tozeroy',
                fillcolor: fillColor.startsWith('#') 
                  ? fillColor + '14'   // ~8% opacity hex
                  : 'rgba(6,182,212,0.08)',
                showlegend: false,
                hoverinfo: 'skip',
              });
            }

            // Apply chart-type-specific colors to all traces that lack colors
            processedData = applyTraceColors(processedData, chartType, colorOffset);
          }
          // Handle histogram data (bin/count format)
          else if (chartType === 'histogram' && Array.isArray(data) && data.length > 0) {
            const first = data[0];
            const keys = Object.keys(first);

            // Histogram usually has 'bin' and 'count' fields
            if (keys.includes('bin') && keys.includes('count')) {
              const binValues = data.map(row => parseFloat(row.bin) || row.bin);
              const countValues = data.map(row => row.count);
              xLabel = 'Bin Range';
              yLabel = 'Frequency';
              const histPalette = getPalette('bar');

              processedData = [{
                x: binValues,
                y: countValues,
                type: 'bar',
                marker: {
                  color: countValues.map((_, i) => histPalette[i % histPalette.length]),
                  line: { width: 0 }
                },
                name: 'Frequency'
              }];
            } else {
              // Fallback to first two keys
              xKey = keys[0];
              yKey = keys[1];
              xLabel = xKey;
              yLabel = yKey;
              const histPalette = getPalette('bar');
              const yVals = data.map(row => row[yKey]);

              processedData = [{
                x: data.map(row => row[xKey]),
                y: yVals,
                type: 'bar',
                marker: {
                  color: yVals.map((_, i) => histPalette[i % histPalette.length]),
                  line: { width: 0 }
                },
                name: yKey
              }];
            }
          }
          // Use config.columns if available (for raw data arrays)
          else if ((chartType === 'line' || chartType === 'line_chart' || chartType === 'bar' || chartType === 'bar_chart') && Array.isArray(data) && data.length > 0) {
            if (config && Array.isArray(config.columns) && config.columns.length >= 2) {
              xKey = config.columns[0];
              yKey = config.columns[1];
              xLabel = config.columns[0];
              yLabel = config.columns[1];
            } else {
              const first = data[0];
              const keys = Object.keys(first);
              if (keys.includes('x') && keys.includes('y')) {
                xKey = 'x';
                yKey = 'y';
                xLabel = 'x';
                yLabel = 'y';
              } else if (keys.length >= 2) {
                xKey = keys[0];
                yKey = keys[1];
                xLabel = keys[0];
                yLabel = keys[1];
              }
            }

            const isLine = chartType === 'line' || chartType === 'line_chart';

            if (isLine) {
              // ── Smart Line Chart Rendering ──
              let rawX = data.map(row => row[xKey]);
              let rawY = data.map(row => row[yKey]);
              const normalized = normalizeLineSeries(rawX, rawY, DENSITY.TARGET_POINTS);
              let plotX = normalized.x;
              let plotY = normalized.y;
              const totalPoints = normalized.meta.originalPoints;
              const isDense = normalized.meta.displayedPoints > DENSITY.DOWNSAMPLE_AT;

              // Gradient colors per point (value-based: cyan→violet)
              const gradientColors = generateGradientColors(plotY, 185, 270);

              // Main line trace
              processedData = [{
                x: plotX,
                y: plotY,
                type: 'scatter',
                mode: totalPoints <= DENSITY.SHOW_MARKERS ? 'lines+markers' : 'lines',
                line: {
                  color: '#06b6d4',
                  width: isDense ? 2.5 : 3,
                  shape: totalPoints > DENSITY.DISABLE_SPLINE ? 'linear' : 'spline',
                  smoothing: 1.0,
                },
                marker: totalPoints <= DENSITY.SHOW_MARKERS ? {
                  color: gradientColors,
                  size: Math.max(4, Math.min(8, 200 / totalPoints)),
                  line: { color: 'rgba(10,13,20,0.8)', width: 1.5 },
                  symbol: 'circle',
                } : undefined,
                name: yLabel,
                // Show number of displayed points vs total
                meta: {
                  totalPoints,
                  displayedPoints: plotX.length,
                  preDownsamplePoints: normalized.meta.preDownsamplePoints,
                  temporal: normalized.meta.temporal,
                  bucketMs: normalized.meta.bucketMs,
                  downsampled: normalized.meta.downsampled,
                },
              }];

              // Area fill trace (gradient underneath the line)
              processedData.unshift({
                x: plotX,
                y: plotY,
                type: 'scatter',
                mode: 'lines',
                line: { color: 'transparent', width: 0 },
                fill: 'tozeroy',
                fillcolor: 'rgba(6,182,212,0.08)',
                fillgradient: {
                  type: 'vertical',
                  colorscale: [
                    [0, 'rgba(6,182,212,0)'],
                    [0.5, 'rgba(6,182,212,0.06)'],
                    [1, 'rgba(6,182,212,0.15)'],
                  ]
                },
                showlegend: false,
                hoverinfo: 'skip',
              });

            } else {
              // ── Bar chart — per-bar gradient coloring ──
              const barData = data.map(row => row[yKey]);
              const barPalette = getPalette('bar');
              const barColors = barData.map((_, i) => barPalette[i % barPalette.length]);
              processedData = [{
                x: data.map(row => row[xKey]),
                y: barData,
                type: 'bar',
                marker: {
                  color: barColors,
                  line: { width: 0 },
                },
                name: yLabel
              }];
            }
          } else if ((chartType === 'pie' || chartType === 'pie_chart') && Array.isArray(data) && data.length > 0) {
            // Check if data is in Plotly format with labels/values
            if (data[0].labels && data[0].values) {
              processedData = [{
                labels: data[0].labels,
                values: data[0].values,
                type: 'pie',
                textinfo: 'label+percent',
                textposition: 'outside',
                textfont: {
                  color: '#e6edf3',
                  size: 13
                },
                marker: {
                  colors: PALETTES.pie,
                  line: {
                    color: 'rgba(10,13,20,0.8)',
                    width: 2
                  }
                },
                hoverinfo: 'none'
              }];
            } else {
              // Data is in array format with name/value or similar keys
              const first = data[0];
              const keys = Object.keys(first);
              const nameKey = keys.includes('name') ? 'name' : keys[0];
              const valueKey = keys.includes('value') ? 'value' : keys[1];

              processedData = [{
                labels: data.map(row => row[nameKey]),
                values: data.map(row => row[valueKey]),
                type: 'pie',
                textinfo: 'label+percent',
                textposition: 'outside',
                textfont: {
                  color: '#e6edf3',
                  size: 13
                },
                marker: {
                  colors: PALETTES.pie,
                  line: {
                    color: 'rgba(10,13,20,0.8)',
                    width: 2
                  }
                },
                hoverinfo: 'none'
              }];
            }
          } else if (chartType === 'donut' && data.length > 0 && data[0].labels && data[0].values) {
            processedData = [{
              labels: data[0].labels,
              values: data[0].values,
              type: 'pie',
              hole: 0.4,
              textinfo: 'label+percent',
              textposition: 'outside',
              textfont: {
                color: '#e6edf3',
                size: 13
              },
              marker: {
                colors: PALETTES.pie,
                line: {
                  color: 'rgba(10,13,20,0.8)',
                  width: 2
                }
              }
            }];
          } else if (Array.isArray(data) && data.length > 0) {
            // Generic fallback for any unhandled chart types
            const first = data[0];
            const keys = Object.keys(first);

            // Try to intelligently pick x and y keys
            xKey = keys.includes('x') ? 'x' : keys[0];
            yKey = keys.includes('y') ? 'y' : (keys.includes('value') ? 'value' : (keys.includes('count') ? 'count' : keys[1]));
            xLabel = xKey;
            yLabel = yKey;

            const plotType = chartType === 'scatter' || chartType === 'scatter_plot' ? 'scatter' : 'bar';
            const fallbackPalette = getPalette(plotType);

            processedData = [{
              x: data.map(row => row[xKey]),
              y: data.map(row => row[yKey]),
              type: plotType,
              mode: plotType === 'scatter' ? 'markers' : undefined,
              marker: {
                color: plotType === 'scatter' ? fallbackPalette[0] : data.map((_, i) => fallbackPalette[i % fallbackPalette.length]),
                size: plotType === 'scatter' ? 10 : undefined,
                line: { width: 0 },
                opacity: plotType === 'scatter' ? 0.85 : 1,
              },
              name: yLabel
            }];
          }

          // ── Detect data density for layout decisions ──
          const isLineType = chartType === 'line' || chartType === 'line_chart';
          const traceLen = processedData?.[0]?.x?.length || (Array.isArray(data) ? data.length : 0);
          const rawDataLen = Array.isArray(data) ? data.length : traceLen;
          const primaryLineTrace = isLineType
            ? processedData.find(trace => trace.type === 'scatter' && trace.fill !== 'tozeroy')
            : null;
          const metaTotal = primaryLineTrace?.meta?.totalPoints || rawDataLen;
          const metaPreDownsample = primaryLineTrace?.meta?.preDownsamplePoints || traceLen;
          const isDenseData = metaTotal > DENSITY.DOWNSAMPLE_AT || metaPreDownsample > DENSITY.DOWNSAMPLE_AT;
          const wasDownsampled = isLineType && isDenseData;

          // ── Build min/max annotations for line charts ──
          let autoAnnotations = [];
          if (isLineType && processedData.length > 0) {
            const mainTrace = processedData.find(t => t.mode !== 'lines' || t.fill !== 'tozeroy') || processedData[processedData.length - 1];
            if (mainTrace?.x && mainTrace?.y) {
              autoAnnotations = findMinMaxAnnotations(mainTrace.x, mainTrace.y);
            }
          }

          // ── Add statistical reference lines for distribution charts ──
          let statisticalShapes = [];
          let statisticalAnnotations = [];
          const isDistributionType = ['box_plot', 'violin', 'histogram', 'scatter'].includes(chartType);
          if (isDistributionType && processedData.length > 0) {
            const firstTrace = processedData[0];
            const yValues = (firstTrace.y || []).filter(v => typeof v === 'number' && Number.isFinite(v));
            if (yValues.length > 0) {
              const sorted = [...yValues].sort((a, b) => a - b);
              const n = sorted.length;
              const mean = yValues.reduce((a, b) => a + b, 0) / n;
              const median = n % 2 === 0 ? (sorted[n / 2 - 1] + sorted[n / 2]) / 2 : sorted[Math.floor(n / 2)];
              const q1 = sorted[Math.floor(n * 0.25)];
              const q3 = sorted[Math.floor(n * 0.75)];

              // Median reference line
              statisticalShapes.push({
                type: 'line',
                xref: 'paper',
                x0: 0, x1: 1,
                y0: median, y1: median,
                line: { color: 'rgba(251, 146, 60, 0.6)', width: 1.5, dash: 'dot' },
              });
              statisticalAnnotations.push({
                xref: 'paper', x: 1.01,
                yref: 'y', y: median,
                text: `Median: ${formatValue(median)}`,
                showarrow: false,
                font: { size: 10, color: 'rgba(251, 146, 60, 0.8)' },
                xanchor: 'left',
                bgcolor: 'rgba(251, 146, 60, 0.1)',
                borderpad: 2,
              });

              // Mean reference line (if different from median)
              if (Math.abs(mean - median) / (Math.abs(median) || 1) > 0.05) {
                statisticalShapes.push({
                  type: 'line',
                  xref: 'paper',
                  x0: 0, x1: 1,
                  y0: mean, y1: mean,
                  line: { color: 'rgba(56, 189, 248, 0.5)', width: 1, dash: 'dash' },
                });
                statisticalAnnotations.push({
                  xref: 'paper', x: 1.01,
                  yref: 'y', y: mean,
                  text: `Mean: ${formatValue(mean)}`,
                  showarrow: false,
                  font: { size: 10, color: 'rgba(56, 189, 248, 0.7)' },
                  xanchor: 'left',
                  bgcolor: 'rgba(56, 189, 248, 0.1)',
                  borderpad: 2,
                });
              }

              // IQR shaded region
              if (chartType === 'histogram' || chartType === 'box_plot') {
                statisticalShapes.push({
                  type: 'rect',
                  xref: 'paper',
                  x0: 0, x1: 1,
                  y0: q1, y1: q3,
                  fillcolor: 'rgba(16, 185, 129, 0.06)',
                  line: { width: 0 },
                  layer: 'below',
                });
              }
            }
          }

          const isChoropleth = processedData.some(t => (t.type || '').toLowerCase() === 'choropleth');
          const isIndicator = processedData.some(t => (t.type || '').toLowerCase() === 'indicator');

          const defaultLayout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {
              color: '#8b949e',
              family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              size: 13
            },
            xaxis: isIndicator ? { visible: false } : {
              color: '#8b949e',
              gridcolor: isLineType ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0)',
              showgrid: isLineType,
              showline: false,
              zeroline: false,
              tickfont: { size: 12, color: '#8b949e' },
              title: { text: xLabel, font: { color: '#6b7280', size: 12 } },
              tickmode: chartType === 'histogram' ? 'linear' : 'auto',
              tickangle: chartType === 'histogram' ? 0 : (isLineType ? 0 : -45),
              automargin: true,
              // Range slider for dense line charts — lets users zoom/pan interactively
              ...(wasDownsampled ? {
                rangeslider: {
                  visible: true,
                  bgcolor: 'rgba(15,23,42,0.8)',
                  bordercolor: 'rgba(255,255,255,0.06)',
                  borderwidth: 1,
                  thickness: 0.08,
                },
              } : {}),
            },
            yaxis: isIndicator ? { visible: false } : {
              color: '#8b949e',
              // Subtle grid lines on Y axis — lets users estimate values
              gridcolor: 'rgba(255,255,255,0.06)',
              showgrid: true,
              gridwidth: 1,
              griddash: isLineType ? 'dot' : 'solid',
              showline: false,
              zeroline: false,
              zerolinecolor: 'rgba(255,255,255,0.08)',
              tickfont: { size: 11, color: '#8b949e' },
              title: { text: yLabel, font: { color: '#6b7280', size: 12 } },
            },
            margin: {
              l: 55,
              r: 25,
              t: autoAnnotations.length > 0 ? 50 : 30,
              b: wasDownsampled ? 80 : 55,
            },
            hovermode: 'closest', // Changed from 'x unified' to 'closest' to prevent misaligned vertical crosshair lines
            hoverlabel: {
              bgcolor: 'rgba(15, 23, 42, 0.95)', // dark slate
              bordercolor: 'rgba(255, 255, 255, 0.1)',
              font: {
                family: 'Inter, -apple-system, sans-serif',
                size: 13,
                color: '#f8fafc'
              },
              align: 'left',
              namelength: -1
            },
            showlegend: chartType !== 'pie' && chartType !== 'donut' && !isIndicator,
            ...(isChoropleth ? {
              geo: {
                bgcolor: 'transparent',
                showframe: false,
                showcoastlines: true,
                coastlinecolor: 'rgba(255,255,255,0.2)',
                projection: { type: 'equirectangular' },
                lakecolor: 'rgba(59, 130, 246, 0.1)',
                showlakes: true,
                landcolor: 'rgba(255,255,255,0.03)'
              }
            } : {}),
            legend: {
              orientation: 'h',
              yanchor: 'bottom',
              y: 1.02,
              xanchor: 'right',
              x: 1,
              bgcolor: 'rgba(0,0,0,0)',
              bordercolor: 'rgba(0,0,0,0)',
              font: { color: '#8b949e', size: 12 },
            },
            // Auto-annotate min/max peaks
            annotations: autoAnnotations,
            // Statistical reference lines for distribution charts
            shapes: statisticalShapes,
          };

          // Merge layout: default ← parent layout, but keep our annotations
          const mergedAnnotations = [
            ...(autoAnnotations || []),
            ...(statisticalAnnotations || []),
            ...(layout?.annotations || []),
          ];

          const mergedShapes = [
            ...(statisticalShapes || []),
            ...(layout?.shapes || []),
          ];

          await Plotly.newPlot(plotRef.current, processedData, {
            ...defaultLayout,
            ...layout,
            annotations: mergedAnnotations,
            shapes: mergedShapes,
            autosize: true,
            useResizeHandler: true,
          }, {
            responsive: true,
            displayModeBar: 'hover',    // Show toolbar only on hover — cleaner
            modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'sendDataToCloud'],
            modeBarButtonsToAdd: wasDownsampled ? ['resetScale2d'] : [],
            displaylogo: false,
            dragmode: wasDownsampled ? 'zoom' : 'pan',  // Zoom for dense data so users can explore
            toImageButtonOptions: {
              format: 'png',
              filename: 'chart',
              height: 1080,
              width: 1920,
              scale: 2
            },
            ...config
          });

          // Removed CustomTooltip hover/unhover logic to rely purely on native Plotly tooltips

          // Attach click event for drill-down
          plotRef.current.on('plotly_click', (eventData) => {
            if (!eventData || !eventData.points || eventData.points.length === 0) return;
            if (!onPointClick) return;

            const pt = eventData.points[0];
            const clickData = {
              x: pt.x ?? pt.label ?? null,
              y: pt.y ?? pt.value ?? null,
              seriesName: pt.data?.name || pt.fullData?.name || '',
              pointIndex: pt.pointNumber,
              chartType,
            };
            onPointClick(clickData);
          });

          const scheduleResize = () => {
            if (!plotRef.current || !window.Plotly) return;
            if (resizeFrameRef.current) cancelAnimationFrame(resizeFrameRef.current);
            resizeFrameRef.current = requestAnimationFrame(() => {
              try {
                window.Plotly.Plots.resize(plotRef.current);
              } catch (err) {
                console.debug('Plotly resize skipped:', err);
              }
            });
          };

          // Observe the chart container itself so chart cards respond to grid/flex changes,
          // not just browser window resizes.
          resizeObserverRef.current?.disconnect();
          resizeObserverRef.current = new ResizeObserver(() => {
            scheduleResize();
          });
          resizeObserverRef.current.observe(plotRef.current.parentElement || plotRef.current);
          scheduleResize();

        }
      } catch (error) {
        console.error("Plotly load error:", error);
        setError(error.message || 'Failed to render chart');
      }
      setIsLoading(false);
    };
    loadPlotly();
    const cleanupPlotElement = plotRef.current;
    return () => {
      if (resizeFrameRef.current) {
        cancelAnimationFrame(resizeFrameRef.current);
        resizeFrameRef.current = null;
      }
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
        resizeObserverRef.current = null;
      }
      if (cleanupPlotElement && window.Plotly) {
        try {
          window.Plotly.purge(cleanupPlotElement);
        } catch (err) {
          console.error('Failed to purge Plotly:', err);
        }
      }
    };
  }, [data, layout, config, chartType, pointIntelligence]);

  // Single stable container — plotRef never gets React children so Plotly owns its DOM freely.
  // Loading and error states are sibling overlays, not replacements for the plotRef div.
  return (
    <>
      <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '200px', ...style }}>
        {/* Plotly renders here exclusively — React never adds JSX children to this div */}
        <div
          ref={plotRef}
          style={{ width: '100%', height: '100%', minHeight: '200px', visibility: isLoading ? 'hidden' : 'visible' }}
        />

        {isLoading && (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#6C6E79', pointerEvents: 'none',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ marginBottom: '8px', fontSize: '24px' }}>📊</div>
              <div style={{ fontSize: '14px', opacity: 0.7 }}>Loading chart...</div>
            </div>
          </div>
        )}

        {error && !isLoading && (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#ef4444',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ marginBottom: '8px', fontSize: '24px' }}>⚠️</div>
              <div style={{ fontSize: '14px', marginBottom: '4px' }}>Chart Error</div>
              <div style={{ fontSize: '12px', opacity: 0.7 }}>{error}</div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}, (prevProps, nextProps) => {
  // Custom comparison - only re-render if data or layout actually changed
  return (
    JSON.stringify(prevProps.data) === JSON.stringify(nextProps.data) &&
    JSON.stringify(prevProps.layout) === JSON.stringify(nextProps.layout) &&
    prevProps.chartType === nextProps.chartType &&
    prevProps.onPointClick === nextProps.onPointClick
  );
});

export default PlotlyChart;
