/**
 * PlotlyRenderer
 * ==============
 * ⚠️ DEPRECATED — The dashboard now uses ECharts for all chart rendering.
 * This file is kept as a fallback/reference and may be removed in a future cleanup.
 *
 * Plotly-specific visualization engine.
 * Contains LTTB downsampling, gradient colors, temporal binning, etc.
 *
 * Usage (legacy):
 *   <PlotlyRenderer
 *     data={traces}
 *     layout={layout}
 *     chartType="line"
 *     onPointClick={handler}
 *     colorOffset={0}
 *   />
 */

// @deprecated Use EChartsRenderer via ChartRenderer from './index' instead.

import React, { useEffect, useRef, memo, useState } from 'react';
import { BarChart3, AlertTriangle } from 'lucide-react';

// ── Constants ───────────────────────────────────────────────────────

const DENSITY = {
  SHOW_MARKERS: 80,
  DOWNSAMPLE_AT: 300,
  TARGET_POINTS: 200,
  DISABLE_SPLINE: 500,
};

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

// ── Helpers ─────────────────────────────────────────────────────────

const isCyanColor = (col) => {
  if (typeof col !== 'string') return false;
  const lower = col.toLowerCase().trim();
  return lower === 'cyan' || lower === '#00f0ff' || lower === '#00d4d4' || lower === '#00ffff' || lower === '#06b6d4';
};

const getPalette = (type) => {
  const normalized = (type || '').toLowerCase().replace('_chart', '').replace('_plot', '');
  return PALETTES[normalized] || PALETTES.default;
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
    60 * 60 * 1000, 3 * 60 * 60 * 1000, 6 * 60 * 60 * 1000, 12 * 60 * 60 * 1000,
    24 * 60 * 60 * 1000, 2 * 24 * 60 * 60 * 1000, 7 * 24 * 60 * 60 * 1000,
    14 * 24 * 60 * 60 * 1000, 30 * 24 * 60 * 60 * 1000, 90 * 24 * 60 * 60 * 1000,
  ];
  for (const candidate of candidates) {
    if (candidate >= ideal) return candidate;
  }
  return candidates[candidates.length - 1];
};

const formatTemporalBucket = (bucketStartMs, bucketMs) => {
  const date = new Date(bucketStartMs);
  if (bucketMs >= 24 * 60 * 60 * 1000) return date.toISOString().slice(0, 10);
  return date.toISOString();
};

// ── LTTB Downsampling ───────────────────────────────────────────────

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

    let avgY = 0, count = 0;
    for (let j = nextBucketStart; j < nextBucketEnd; j++) {
      avgY += (typeof yArr[j] === 'number' ? yArr[j] : 0);
      count++;
    }
    avgY = count > 0 ? avgY / count : 0;

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

// ── Gradient Color Generator ────────────────────────────────────────

const generateGradientColors = (values, startHue = 195, endHue = 260) => {
  if (!values || values.length === 0) return [];
  const numericVals = values.map(v => (typeof v === 'number' ? v : 0));
  const min = Math.min(...numericVals);
  const max = Math.max(...numericVals);
  const range = max - min || 1;
  return numericVals.map(v => {
    const t = (v - min) / range;
    const hue = startHue + t * (endHue - startHue);
    return `hsl(${hue}, 85%, ${55 + t * 15}%)`;
  });
};

// ── Min/Max Annotations ─────────────────────────────────────────────

const findMinMaxAnnotations = (xArr, yArr) => {
  if (!yArr || yArr.length < 5) return [];
  const numericY = yArr.map(v => (typeof v === 'number' ? v : 0));
  let minIdx = 0, maxIdx = 0;
  for (let i = 1; i < numericY.length; i++) {
    if (numericY[i] < numericY[minIdx]) minIdx = i;
    if (numericY[i] > numericY[maxIdx]) maxIdx = i;
  }
  const fmt = (v) => {
    if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
    return typeof v === 'number' ? v.toFixed(1) : v;
  };
  const annotations = [];
  if (Math.abs(maxIdx - minIdx) > yArr.length * 0.05) {
    annotations.push({
      x: xArr[maxIdx], y: numericY[maxIdx],
      xref: 'x', yref: 'y', text: `▲ ${fmt(numericY[maxIdx])}`,
      showarrow: true, arrowhead: 0, arrowcolor: '#34d399',
      ax: 0, ay: -30, font: { color: '#34d399', size: 11, family: 'Inter, sans-serif' },
      bgcolor: 'rgba(16,185,129,0.12)', bordercolor: 'rgba(16,185,129,0.3)',
      borderwidth: 1, borderpad: 4,
    });
    annotations.push({
      x: xArr[minIdx], y: numericY[minIdx],
      xref: 'x', yref: 'y', text: `▼ ${fmt(numericY[minIdx])}`,
      showarrow: true, arrowhead: 0, arrowcolor: '#f87171',
      ax: 0, ay: 28, font: { color: '#f87171', size: 11, family: 'Inter, sans-serif' },
      bgcolor: 'rgba(248,113,113,0.12)', bordercolor: 'rgba(248,113,113,0.3)',
      borderwidth: 1, borderpad: 4,
    });
  }
  return annotations;
};

// ── Line Series Normalization ───────────────────────────────────────

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
    if (numericX.every(v => v !== null)) {
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
        if (existing) { existing.y += row.y; existing.count += 1; }
        else { bucketMap.set(bucketStart, { t: bucketStart, y: row.y, count: 1 }); }
      }
      reduced = [...bucketMap.values()].sort((a, b) => a.t - b.t).map(row => ({
        x: formatTemporalBucket(row.t, bucketMs), y: row.y, i: 0, t: row.t,
      }));
      bucketMsUsed = bucketMs;
    } else {
      const tsMap = new Map();
      for (const row of ordered) {
        const key = row.t ?? 0;
        const existing = tsMap.get(key);
        if (existing) { existing.y += row.y; existing.count += 1; }
        else { tsMap.set(key, { t: key, y: row.y, count: 1 }); }
      }
      reduced = [...tsMap.values()].sort((a, b) => a.t - b.t).map(row => ({
        x: formatTemporalBucket(row.t, 24 * 60 * 60 * 1000), y: row.y, i: 0, t: row.t,
      }));
    }
  } else {
    const dupMap = new Map();
    for (const row of reduced) {
      const key = String(row.x);
      const existing = dupMap.get(key);
      if (existing) { existing.y += row.y; existing.count += 1; }
      else { dupMap.set(key, { x: row.x, y: row.y, count: 1 }); }
    }
    reduced = [...dupMap.values()].map(row => ({ x: row.x, y: row.y, i: 0, t: null }));
  }

  let finalX = reduced.map(r => r.x);
  let finalY = reduced.map(r => r.y);
  if (finalX.length > targetPoints) {
    const sampled = downsampleLTTB(finalX, finalY, targetPoints);
    finalX = sampled.x;
    finalY = sampled.y;
  }

  return {
    x: finalX, y: finalY,
    meta: {
      originalPoints: rows.length, preDownsamplePoints: reduced.length,
      displayedPoints: finalX.length, temporal, bucketMs: bucketMsUsed,
      downsampled: finalX.length < rows.length,
    },
  };
};

// ── Color Application ───────────────────────────────────────────────

const applyTraceColors = (traces, chartType, colorOffset = 0) => {
  const palette = getPalette(chartType);
  return traces.map((trace, idx) => {
    const color = palette[(idx + colorOffset) % palette.length];
    const traceType = (trace.type || '').toLowerCase();
    const enhanced = { ...trace };

    // Override harsh flat cyan if passed from API
    if (trace.marker?.color && isCyanColor(trace.marker.color)) {
      enhanced.marker = { ...trace.marker, color };
    }
    if (trace.line?.color && isCyanColor(trace.line.color)) {
      enhanced.line = { ...trace.line, color };
    }

    if (enhanced.marker?.color || enhanced.marker?.colors || enhanced.line?.color) return enhanced;

    if (traceType === 'bar') {
      enhanced.marker = { ...(trace.marker || {}), color, line: { width: 0 } };
    } else if (traceType === 'scatter' && (trace.mode || '').includes('markers')) {
      enhanced.marker = { ...(trace.marker || {}), color, size: trace.marker?.size || 8, line: { color: 'rgba(10,13,20,0.6)', width: 1 }, opacity: 0.85 };
    } else if (traceType === 'scatter') {
      enhanced.line = { ...(trace.line || {}), color };
    } else if (traceType === 'pie') {
      enhanced.hole = trace.hole ?? 0.65;
      enhanced.textinfo = 'none';
      enhanced.marker = { ...(trace.marker || {}), colors: palette, line: { color: 'rgba(10,13,20,0.8)', width: 2 } };
    } else if (traceType === 'box' || traceType === 'violin') {
      enhanced.marker = { ...(trace.marker || {}), color };
      enhanced.line = { ...(trace.line || {}), color };
      enhanced.fillcolor = color + '20';
    } else if (traceType === 'heatmap' && !trace.colorscale) {
      enhanced.colorscale = [[0, '#0c1445'], [0.2, '#1e3a8a'], [0.4, '#3b82f6'], [0.6, '#06b6d4'], [0.8, '#34d399'], [1, '#a3e635']];
    } else if (traceType === 'indicator') {
      enhanced.number = { font: { color, size: 40 } };
      if (enhanced.gauge) enhanced.gauge.bar = { color };
    } else if (traceType === 'choropleth' && !enhanced.colorscale) {
      enhanced.colorscale = 'Viridis';
    }
    return enhanced;
  });
};

// ── PlotlyRenderer Component ────────────────────────────────────────

const PlotlyRenderer = memo(({ data, layout = {}, style = {}, config = {}, chartType = 'bar', onPointClick, colorOffset = 0 }) => {
  const plotRef = useRef(null);
  const resizeObserverRef = useRef(null);
  const resizeFrameRef = useRef(null);
  const dataHashRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const formatValue = (val) => {
    if (typeof val !== 'number') return val;
    if (val >= 1e9) return (val / 1e9).toFixed(1) + 'B';
    if (val >= 1e6) return (val / 1e6).toFixed(1) + 'M';
    if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K';
    return val.toLocaleString();
  };

  useEffect(() => {
    const dataHash = JSON.stringify(data);
    if (dataHash === dataHashRef.current) return;
    dataHashRef.current = dataHash;

    const loadPlotly = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const Plotly = (await import('plotly.js-dist-min')).default;
        if (!plotRef.current || !data) { setIsLoading(false); return; }
        if (data.length === 0) { setError('No data available for chart'); setIsLoading(false); return; }

        if (plotRef.current && data) {
          let processedData = data;
          let xKey = 'x', yKey = 'y';
          let xLabel = '', yLabel = '';

          const isPlotlyFormat = Array.isArray(data) && data.length > 0 &&
            data[0].type !== undefined &&
            (data[0].x !== undefined || data[0].labels !== undefined || data[0].y !== undefined || data[0].z !== undefined);

          if (isPlotlyFormat) {
            processedData = data.map(trace => {
              const enhanced = { ...trace };
              const traceType = (trace.type || '').toLowerCase();
              if (traceType === 'pie') {
                enhanced.hole = trace.hole ?? 0.65;
                enhanced.textinfo = 'none';
              }
              const isScatterLine = traceType === 'scatter' && (trace.mode === 'lines' || trace.mode === 'lines+markers' || trace.mode === 'lines+text');
              if (isScatterLine && Array.isArray(trace.x) && Array.isArray(trace.y)) {
                const normalized = normalizeLineSeries(trace.x, trace.y, DENSITY.TARGET_POINTS);
                enhanced.x = normalized.x;
                enhanced.y = normalized.y;
                enhanced.meta = { ...(trace.meta || {}), totalPoints: normalized.meta.originalPoints, displayedPoints: normalized.meta.displayedPoints, preDownsamplePoints: normalized.meta.preDownsamplePoints, temporal: normalized.meta.temporal, bucketMs: normalized.meta.bucketMs, downsampled: normalized.meta.downsampled };
                const isDense = normalized.meta.displayedPoints > DENSITY.DOWNSAMPLE_AT;
                const displayPts = enhanced.x.length;
                if (displayPts > DENSITY.SHOW_MARKERS) enhanced.mode = 'lines';
                else {
                  enhanced.mode = 'lines+markers';
                  enhanced.marker = { ...(trace.marker || {}), color: generateGradientColors(enhanced.y, 185, 270), size: Math.max(4, Math.min(8, 200 / displayPts)), line: { color: 'rgba(10,13,20,0.8)', width: 1.5 } };
                }
                enhanced.line = { ...(trace.line || {}), width: isDense ? 2.5 : (trace.line?.width || 3), shape: displayPts > DENSITY.DISABLE_SPLINE ? 'linear' : (trace.line?.shape || 'spline') };
              }
              return enhanced;
            });

            const lineTraces = processedData.filter(t => t.type === 'scatter' && (t.mode === 'lines' || t.mode === 'lines+markers'));
            if (lineTraces.length === 1 && lineTraces[0].x?.length > 0) {
              const lt = lineTraces[0];
              const fc = lt.line?.color || '#06b6d4';
              processedData.unshift({ x: lt.x, y: lt.y, type: 'scatter', mode: 'lines', line: { color: 'transparent', width: 0 }, fill: 'tozeroy', fillcolor: fc.startsWith('#') ? fc + '14' : 'rgba(6,182,212,0.08)', showlegend: false, hoverinfo: 'skip' });
            }
            processedData = applyTraceColors(processedData, chartType, colorOffset);
          } else if (chartType === 'histogram' && Array.isArray(data) && data.length > 0) {
            const first = data[0];
            const keys = Object.keys(first);
            if (keys.includes('bin') && keys.includes('count')) {
              xLabel = 'Bin Range'; yLabel = 'Frequency';
              const hp = getPalette('bar');
              processedData = [{ x: data.map(r => parseFloat(r.bin) || r.bin), y: data.map(r => r.count), type: 'bar', marker: { color: data.map((_, i) => hp[i % hp.length]), line: { width: 0 } }, name: 'Frequency' }];
            } else {
              xKey = keys[0]; yKey = keys[1]; xLabel = xKey; yLabel = yKey;
              const hp = getPalette('bar');
              processedData = [{ x: data.map(r => r[xKey]), y: data.map(r => r[yKey]), type: 'bar', marker: { color: data.map((_, i) => hp[i % hp.length]), line: { width: 0 } }, name: yKey }];
            }
          } else if ((chartType === 'line' || chartType === 'bar') && Array.isArray(data) && data.length > 0) {
            if (config && Array.isArray(config.columns) && config.columns.length >= 2) {
              xKey = config.columns[0]; yKey = config.columns[1]; xLabel = config.columns[0]; yLabel = config.columns[1];
            } else {
              const first = data[0];
              const keys = Object.keys(first);
              xKey = keys.includes('x') ? 'x' : keys[0];
              yKey = keys.includes('y') ? 'y' : (keys.includes('value') ? 'value' : (keys.includes('count') ? 'count' : keys[1]));
              xLabel = xKey; yLabel = yKey;
            }
            if (chartType === 'line') {
              const normalized = normalizeLineSeries(data.map(r => r[xKey]), data.map(r => r[yKey]), DENSITY.TARGET_POINTS);
              const totalPoints = normalized.meta.originalPoints;
              const isDense = normalized.meta.displayedPoints > DENSITY.DOWNSAMPLE_AT;
              const gcolors = generateGradientColors(normalized.y, 185, 270);
              processedData = [{
                x: normalized.x, y: normalized.y, type: 'scatter',
                mode: totalPoints <= DENSITY.SHOW_MARKERS ? 'lines+markers' : 'lines',
                line: { color: '#06b6d4', width: isDense ? 2.5 : 3, shape: totalPoints > DENSITY.DISABLE_SPLINE ? 'linear' : 'spline', smoothing: 1.0 },
                marker: totalPoints <= DENSITY.SHOW_MARKERS ? { color: gcolors, size: Math.max(4, Math.min(8, 200 / totalPoints)), line: { color: 'rgba(10,13,20,0.8)', width: 1.5 } } : undefined,
                name: yLabel,
                meta: { totalPoints, displayedPoints: normalized.x.length, temporal: normalized.meta.temporal, downsampled: normalized.meta.downsampled },
              }];
              processedData.unshift({ x: normalized.x, y: normalized.y, type: 'scatter', mode: 'lines', line: { color: 'transparent', width: 0 }, fill: 'tozeroy', fillcolor: 'rgba(6,182,212,0.08)', showlegend: false, hoverinfo: 'skip' });
            } else {
              const bp = getPalette('bar');
              processedData = [{ x: data.map(r => r[xKey]), y: data.map(r => r[yKey]), type: 'bar', marker: { color: data.map((_, i) => bp[i % bp.length]), line: { width: 0 } }, name: yLabel }];
            }
          } else if ((chartType === 'pie' || chartType === 'donut') && Array.isArray(data) && data.length > 0) {
            const first = data[0];
            const labels = first.labels ? data[0].labels : data.map(r => r[Object.keys(first).find(k => k !== 'value' && k !== 'count') || Object.keys(first)[0]]);
            const values = first.values ? data[0].values : data.map(r => r.value || r.count || r[Object.keys(first)[1]]);
            processedData = [{
              labels, values, type: 'pie',
              textinfo: 'label+percent', textposition: 'outside',
              textfont: { color: '#e6edf3', size: 13 },
              marker: { colors: PALETTES.pie, line: { color: 'rgba(10,13,20,0.8)', width: 2 } },
              ...(chartType === 'donut' ? { hole: 0.4 } : { hole: 0.65 }),
            }];
          } else if (Array.isArray(data) && data.length > 0) {
            const first = data[0];
            const keys = Object.keys(first);
            xKey = keys.includes('x') ? 'x' : keys[0];
            yKey = keys.includes('y') ? 'y' : (keys.includes('value') ? 'value' : (keys.includes('count') ? 'count' : keys[1]));
            xLabel = xKey; yLabel = yKey;
            const plotType = chartType === 'scatter' ? 'scatter' : 'bar';
            const fp = getPalette(plotType);
            processedData = [{ x: data.map(r => r[xKey]), y: data.map(r => r[yKey]), type: plotType, mode: plotType === 'scatter' ? 'markers' : undefined, marker: { color: plotType === 'scatter' ? fp[0] : data.map((_, i) => fp[i % fp.length]), size: plotType === 'scatter' ? 10 : undefined, line: { width: 0 }, opacity: plotType === 'scatter' ? 0.85 : 1 }, name: yLabel }];
          }

          const isLineType = chartType === 'line';
          const primaryLineTrace = isLineType ? processedData.find(t => t.type === 'scatter' && t.fill !== 'tozeroy') : null;
          const metaTotal = primaryLineTrace?.meta?.totalPoints || (Array.isArray(data) ? data.length : 0);
          const isDenseData = metaTotal > DENSITY.DOWNSAMPLE_AT;
          const wasDownsampled = isLineType && isDenseData;

          let autoAnnotations = [];
          if (isLineType && processedData.length > 0) {
            const mt = processedData.find(t => t.mode !== 'lines' || t.fill !== 'tozeroy') || processedData[processedData.length - 1];
            if (mt?.x && mt?.y) autoAnnotations = findMinMaxAnnotations(mt.x, mt.y);
          }

          let statisticalShapes = [], statisticalAnnotations = [];
          if (['box_plot', 'violin', 'histogram', 'scatter'].includes(chartType) && processedData.length > 0) {
            const yValues = (processedData[0].y || []).filter(v => typeof v === 'number' && Number.isFinite(v));
            if (yValues.length > 0) {
              const sorted = [...yValues].sort((a, b) => a - b);
              const n = sorted.length;
              const mean = yValues.reduce((a, b) => a + b, 0) / n;
              const median = n % 2 === 0 ? (sorted[n / 2 - 1] + sorted[n / 2]) / 2 : sorted[Math.floor(n / 2)];
              const q1 = sorted[Math.floor(n * 0.25)];
              const q3 = sorted[Math.floor(n * 0.75)];

              statisticalShapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: median, y1: median, line: { color: 'rgba(251, 146, 60, 0.6)', width: 1.5, dash: 'dot' } });
              statisticalAnnotations.push({ xref: 'paper', x: 1.01, yref: 'y', y: median, text: `Median: ${formatValue(median)}`, showarrow: false, font: { size: 10, color: 'rgba(251, 146, 60, 0.8)' }, xanchor: 'left', bgcolor: 'rgba(251, 146, 60, 0.1)', borderpad: 2 });

              if (Math.abs(mean - median) / (Math.abs(median) || 1) > 0.05) {
                statisticalShapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: mean, y1: mean, line: { color: 'rgba(56, 189, 248, 0.5)', width: 1, dash: 'dash' } });
                statisticalAnnotations.push({ xref: 'paper', x: 1.01, yref: 'y', y: mean, text: `Mean: ${formatValue(mean)}`, showarrow: false, font: { size: 10, color: 'rgba(56, 189, 248, 0.7)' }, xanchor: 'left', bgcolor: 'rgba(56, 189, 248, 0.1)', borderpad: 2 });
              }
              if (chartType === 'histogram' || chartType === 'box_plot') {
                statisticalShapes.push({ type: 'rect', xref: 'paper', x0: 0, x1: 1, y0: q1, y1: q3, fillcolor: 'rgba(16, 185, 129, 0.06)', line: { width: 0 }, layer: 'below' });
              }
            }
          }

          const isChoropleth = processedData.some(t => (t.type || '').toLowerCase() === 'choropleth');
          const isIndicator = processedData.some(t => (t.type || '').toLowerCase() === 'indicator');

          const defaultLayout = {
            paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#8b949e', family: 'Inter, -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif', size: 13 },
            xaxis: isIndicator ? { visible: false } : {
              color: '#8b949e', gridcolor: isLineType ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0)', showgrid: isLineType,
              showline: false, zeroline: false, tickfont: { size: 12, color: '#8b949e' },
              title: { text: xLabel, font: { color: '#6b7280', size: 12 } },
              tickmode: 'auto', tickangle: isLineType ? 0 : -45, automargin: true,
              ...(wasDownsampled ? { rangeslider: { visible: true, bgcolor: 'rgba(15,23,42,0.8)', bordercolor: 'rgba(255,255,255,0.06)', borderwidth: 1, thickness: 0.08 } } : {}),
            },
            yaxis: isIndicator ? { visible: false } : {
              color: '#8b949e', gridcolor: 'rgba(255,255,255,0.06)', showgrid: true, gridwidth: 1,
              griddash: isLineType ? 'dot' : 'solid', showline: false, zeroline: false,
              tickfont: { size: 11, color: '#8b949e' }, title: { text: yLabel, font: { color: '#6b7280', size: 12 } },
            },
            margin: { l: 55, r: 25, t: autoAnnotations.length > 0 ? 50 : 30, b: wasDownsampled ? 80 : 55 },
            hovermode: 'closest',
            hoverlabel: { bgcolor: 'rgba(15, 23, 42, 0.95)', bordercolor: 'rgba(255, 255, 255, 0.1)', font: { family: 'Inter, -apple-system, sans-serif', size: 13, color: '#f8fafc' }, align: 'left', namelength: -1 },
            showlegend: !['pie', 'donut'].includes(chartType) && !isIndicator,
            ...(isChoropleth ? { geo: { bgcolor: 'transparent', showframe: false, showcoastlines: true, coastlinecolor: 'rgba(255,255,255,0.2)', projection: { type: 'equirectangular' }, lakecolor: 'rgba(59, 130, 246, 0.1)', showlakes: true, landcolor: 'rgba(255,255,255,0.03)' } } : {}),
            legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1, bgcolor: 'rgba(0,0,0,0)', bordercolor: 'rgba(0,0,0,0)', font: { color: '#8b949e', size: 12 } },
            annotations: autoAnnotations,
            shapes: statisticalShapes,
          };

          await Plotly.newPlot(plotRef.current, processedData, {
            ...defaultLayout, ...layout,
            annotations: [...autoAnnotations, ...statisticalAnnotations, ...(layout?.annotations || [])],
            shapes: [...statisticalShapes, ...(layout?.shapes || [])],
            autosize: true, useResizeHandler: true,
          }, {
            responsive: true, displayModeBar: 'hover',
            modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'sendDataToCloud'],
            modeBarButtonsToAdd: wasDownsampled ? ['resetScale2d'] : [],
            displaylogo: false, dragmode: wasDownsampled ? 'zoom' : 'pan',
            toImageButtonOptions: { format: 'png', filename: 'chart', height: 1080, width: 1920, scale: 2 },
            ...config,
          });

          plotRef.current.on('plotly_click', (eventData) => {
            if (!eventData?.points?.length || !onPointClick) return;
            const pt = eventData.points[0];
            onPointClick({ x: pt.x ?? pt.label ?? null, y: pt.y ?? pt.value ?? null, seriesName: pt.data?.name || pt.fullData?.name || '', pointIndex: pt.pointNumber, chartType });
          });

          const scheduleResize = () => {
            if (!plotRef.current || !window.Plotly) return;
            if (resizeFrameRef.current) cancelAnimationFrame(resizeFrameRef.current);
            resizeFrameRef.current = requestAnimationFrame(() => { try { window.Plotly.Plots.resize(plotRef.current); } catch (err) { console.debug('Plotly resize skipped:', err); } });
          };

          resizeObserverRef.current?.disconnect();
          resizeObserverRef.current = new ResizeObserver(() => scheduleResize());
          resizeObserverRef.current.observe(plotRef.current.parentElement || plotRef.current);
          scheduleResize();
        }
      } catch (error) {
        console.error('Plotly load error:', error);
        setError(error.message || 'Failed to render chart');
      }
      setIsLoading(false);
    };
    loadPlotly();
    const cleanupElement = plotRef.current;
    return () => {
      if (resizeFrameRef.current) { cancelAnimationFrame(resizeFrameRef.current); resizeFrameRef.current = null; }
      if (resizeObserverRef.current) { resizeObserverRef.current.disconnect(); resizeObserverRef.current = null; }
      if (cleanupElement && window.Plotly) { try { window.Plotly.purge(cleanupElement); } catch (err) { console.error('Failed to purge Plotly:', err); } }
    };
  }, [data, layout, config, chartType, onPointClick, colorOffset]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '200px', ...style }}>
      <div ref={plotRef} style={{ width: '100%', height: '100%', minHeight: '200px', visibility: isLoading ? 'hidden' : 'visible' }} />
      {isLoading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6C6E79', pointerEvents: 'none' }}>
          <div style={{ textAlign: 'center' }}><BarChart3 size={24} style={{ marginBottom: '8px', opacity: 0.5, display: 'inline-block' }} /><div style={{ fontSize: '14px', opacity: 0.7 }}>Loading chart...</div></div>
        </div>
      )}
      {error && !isLoading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444' }}>
          <div style={{ textAlign: 'center' }}><AlertTriangle size={24} style={{ marginBottom: '8px', opacity: 0.7, display: 'inline-block' }} /><div style={{ fontSize: '14px', marginBottom: '4px' }}>Chart Error</div><div style={{ fontSize: '12px', opacity: 0.7 }}>{error}</div></div>
        </div>
      )}
    </div>
  );
}, (prevProps, nextProps) => (
  JSON.stringify(prevProps.data) === JSON.stringify(nextProps.data) &&
  JSON.stringify(prevProps.layout) === JSON.stringify(nextProps.layout) &&
  prevProps.chartType === nextProps.chartType &&
  prevProps.onPointClick === nextProps.onPointClick
));

export default PlotlyRenderer;
export { PlotlyRenderer };
