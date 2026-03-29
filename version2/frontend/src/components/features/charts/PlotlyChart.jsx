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
  bar: ['#6366f1', '#8b5cf6', '#a78bfa', '#c084fc', '#e879f9', '#f472b6', '#fb7185', '#f97316'],
  // Line charts: cool gradient progression (low→high energy)
  line: ['#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc'],
  // Pie/donut: maximally distinct, perceptually balanced (no adjacent similar hues)
  pie: ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316', '#84cc16'],
  // Scatter: distinguishable point colors
  scatter: ['#06b6d4', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#fb923c'],
  // Box/violin: soft, distinguishable per-group colors
  box: ['#818cf8', '#34d399', '#fbbf24', '#f87171', '#22d3ee', '#a78bfa', '#fb923c', '#84cc16', '#e879f9', '#2dd4bf',
         '#f472b6', '#a3e635', '#38bdf8', '#c084fc', '#facc15', '#4ade80', '#f43f5e', '#06b6d4', '#d946ef', '#fca5a5'],
  // Heatmap: sequential (handled by colorscale, not palette)
  heatmap: [],
  // Area: layered translucent fills
  area: ['#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'],
  // Default fallback
  default: ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6'],
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
      enhanced.hovertemplate = '<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>';
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
    return enhanced;
  });
};

const CustomTooltip = ({ visible, x, y, data }) => {
  if (!visible || !data || !Array.isArray(data.items) || data.items.length === 0) return null;

  const { xLabel, xValue, items, grandTotal, yLabel, avg, rank, totalCategories, totalRecords, backendInsight, isOutlier, zScore, percentile } = data;
  const isSingle = items.length === 1;
  const primaryItem = items[0];
  const pct = grandTotal > 0 ? ((primaryItem.rawValue / grandTotal) * 100) : 0;
  const vsAvg = avg > 0 ? (((primaryItem.rawValue - avg) / avg) * 100) : null;

  // Use backend-computed insight if available, otherwise fall back to client heuristic
  const generateInsight = () => {
    if (backendInsight) return backendInsight;
    if (!primaryItem) return null;
    if (rank === 1) return 'Highest value across all categories';
    if (rank === totalCategories) return 'Lowest value across all categories';
    if (vsAvg !== null) {
      if (vsAvg > 50) return 'Significantly above the average for this dataset';
      if (vsAvg > 15) return 'Moderately above average — a strong performer';
      if (vsAvg > 0) return 'Slightly above average';
      if (vsAvg > -15) return 'Slightly below average';
      if (vsAvg > -50) return 'Moderately below average';
      return 'Significantly below the average for this dataset';
    }
    if (pct > 30) return 'Dominant share — contributes a major portion';
    if (pct < 5) return 'Minor share — relatively small contribution';
    return null;
  };

  const insight = generateInsight();

  // Position: default top-right of cursor, flip near edges
  const tooltipStyle = { left: x + 16, top: y - 16 };
  if (x > window.innerWidth - 320) tooltipStyle.left = x - 300;
  if (y > window.innerHeight - 320) tooltipStyle.top = y - 280;

  return createPortal(
    <AnimatePresence>
      <MotionDiv
        initial={{ opacity: 0, y: 6, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 6, scale: 0.96 }}
        transition={{ duration: 0.12, ease: 'easeOut' }}
        style={{
          position: 'fixed',
          ...tooltipStyle,
          zIndex: 9999,
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            width: isSingle ? 260 : 280,
            borderRadius: 12,
            overflow: 'hidden',
            background: 'rgba(26,25,28,0.97)',
            backdropFilter: 'blur(24px)',
            border: '1px solid rgba(202,210,253,0.10)',
            boxShadow: '0 12px 40px rgba(0,0,0,0.6), 0 0 0 1px rgba(202,210,253,0.04)',
            fontFamily: 'Inter, -apple-system, system-ui, sans-serif',
          }}
        >
          {/* ── Header: Category identification ── */}
          <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid rgba(202,210,253,0.07)' }}>
            <div style={{ fontSize: 9, fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>
              {xLabel || 'Category'}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#CAD2FD', letterSpacing: '-0.01em' }}>
              {xValue ?? '—'}
            </div>
          </div>

          {/* ── Primary metric rows ── */}
          <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {items.map((item, index) => {
              const itemPct = grandTotal > 0 ? ((item.rawValue / grandTotal) * 100) : 0;
              return (
                <div key={`${item.name}-${index}`}>
                  {/* Hero value row */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                      <span style={{
                        width: 8, height: 8, borderRadius: '50%',
                        backgroundColor: item.color, flexShrink: 0,
                        boxShadow: `0 0 10px ${item.color}40`,
                      }} />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{
                          fontSize: 10, color: '#9CA3AF', marginBottom: 2,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {yLabel || item.name || 'Value'}
                        </div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: '#CAD2FD', fontVariantNumeric: 'tabular-nums', lineHeight: 1, letterSpacing: '-0.02em' }}>
                          {item.value}
                        </div>
                      </div>
                    </div>
                    {/* Percentage badge */}
                    <div style={{ textAlign: 'right', flexShrink: 0, paddingTop: 2 }}>
                      <div style={{
                        fontSize: 13, fontWeight: 700, color: item.color,
                        fontVariantNumeric: 'tabular-nums', lineHeight: 1,
                      }}>
                        {itemPct.toFixed(1)}%
                      </div>
                      <div style={{ fontSize: 9, color: '#6B7280', marginTop: 2 }}>
                        of total
                      </div>
                    </div>
                  </div>

                  {/* Proportion bar */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{
                      flex: 1, height: 4, borderRadius: 3,
                      background: 'rgba(202,210,253,0.06)', overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%', borderRadius: 3,
                        width: `${Math.min(itemPct, 100)}%`,
                        background: `linear-gradient(90deg, ${item.color}CC, ${item.color})`,
                        transition: 'width 0.2s ease',
                      }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* ── Benchmarking row ── */}
          {(vsAvg !== null || rank || isOutlier) && (
            <div style={{
              padding: '8px 14px',
              borderTop: '1px solid rgba(202,210,253,0.06)',
              display: 'flex', gap: 6, flexWrap: 'wrap',
            }}>
              {isOutlier && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', borderRadius: 6,
                  background: 'rgba(245,158,11,0.12)',
                  border: '1px solid rgba(245,158,11,0.25)',
                }}>
                  <span style={{ fontSize: 10 }}>⚠</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#f59e0b', letterSpacing: '0.04em' }}>
                    OUTLIER
                  </span>
                </div>
              )}
              {vsAvg !== null && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', borderRadius: 6,
                  background: vsAvg >= 0 ? 'rgba(16,185,129,0.10)' : 'rgba(239,68,68,0.10)',
                  border: `1px solid ${vsAvg >= 0 ? 'rgba(16,185,129,0.20)' : 'rgba(239,68,68,0.20)'}`,
                }}>
                  <span style={{ fontSize: 10, color: vsAvg >= 0 ? '#34d399' : '#f87171' }}>
                    {vsAvg >= 0 ? '▲' : '▼'}
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: vsAvg >= 0 ? '#34d399' : '#f87171', fontVariantNumeric: 'tabular-nums' }}>
                    {Math.abs(vsAvg).toFixed(1)}% vs avg
                  </span>
                </div>
              )}
              {rank && totalCategories && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', borderRadius: 6,
                  background: rank <= 3 ? 'rgba(251,191,36,0.10)' : 'rgba(202,210,253,0.06)',
                  border: `1px solid ${rank <= 3 ? 'rgba(251,191,36,0.22)' : 'rgba(202,210,253,0.08)'}`,
                }}>
                  <span style={{ fontSize: 10, fontWeight: 600, color: rank <= 3 ? '#fbbf24' : '#9CA3AF', fontVariantNumeric: 'tabular-nums' }}>
                    {rank <= 3 ? ['🥇','🥈','🥉'][rank - 1] + ' ' : ''}#{rank} of {totalCategories}
                  </span>
                </div>
              )}
              {typeof percentile === 'number' && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', borderRadius: 6,
                  background: percentile >= 75 ? 'rgba(16,185,129,0.10)' : percentile <= 25 ? 'rgba(239,68,68,0.08)' : 'rgba(202,210,253,0.06)',
                  border: `1px solid ${percentile >= 75 ? 'rgba(16,185,129,0.20)' : percentile <= 25 ? 'rgba(239,68,68,0.15)' : 'rgba(202,210,253,0.08)'}`,
                }}>
                  <span style={{ fontSize: 10, fontWeight: 600, color: percentile >= 75 ? '#34d399' : percentile <= 25 ? '#f87171' : '#9CA3AF', fontVariantNumeric: 'tabular-nums' }}>
                    P{Math.round(percentile)}
                  </span>
                </div>
              )}
              {typeof totalRecords === 'number' && totalRecords > 0 && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', borderRadius: 6,
                  background: 'rgba(202,210,253,0.06)',
                  border: '1px solid rgba(202,210,253,0.08)',
                }}>
                  <span style={{ fontSize: 10, fontWeight: 500, color: '#6B7280' }}>
                    {totalRecords.toLocaleString()} records
                  </span>
                </div>
              )}
            </div>
          )}

          {/* ── Intelligence insight ── */}
          {insight && (
            <div style={{
              padding: '8px 14px 10px',
              borderTop: '1px dashed rgba(202,210,253,0.08)',
              display: 'flex', alignItems: 'flex-start', gap: 6,
            }}>
              <span style={{ fontSize: 11, flexShrink: 0, marginTop: 1 }}>{backendInsight ? '🔬' : '💡'}</span>
              <span style={{ fontSize: 10, fontStyle: 'italic', color: backendInsight ? '#CAD2FD' : '#B0B8C4', lineHeight: 1.4 }}>
                {insight}
              </span>
            </div>
          )}
        </div>
      </MotionDiv>
    </AnimatePresence>,
    document.body
  );
};

const PlotlyChart = memo(({ data, layout = {}, style = {}, config = {}, chartType = 'bar', onPointClick, pointIntelligence, chartTitle, colorOffset = 0 }) => {
  const plotRef = useRef(null);
  const dataHashRef = useRef(null);
  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, data: null });
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
              const enhanced = { ...trace, hoverinfo: 'none' };
              const traceType = (trace.type || '').toLowerCase();

              // Enforce modern donut styling for pie traces regardless of stored state
              if (traceType === 'pie') {
                enhanced.hole = trace.hole ?? 0.65;
                enhanced.textinfo = 'none';
                enhanced.hovertemplate = '<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>';
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
                name: 'Frequency',
                hoverinfo: 'none'
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
                name: yKey,
                hoverinfo: 'none'
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
                hoverinfo: 'none',
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
                name: yLabel,
                hoverinfo: 'none'
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
              },
              hoverinfo: 'none'
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
              name: yLabel,
              hoverinfo: 'none'
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

          const defaultLayout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {
              color: '#8b949e',
              family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              size: 13
            },
            xaxis: {
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
            yaxis: {
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
            hovermode: 'x unified',
            showlegend: chartType !== 'pie' && chartType !== 'donut',
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
          };

          // Merge layout: default ← parent layout, but keep our annotations
          const mergedAnnotations = [
            ...(autoAnnotations || []),
            ...(layout?.annotations || []),
          ];

          await Plotly.newPlot(plotRef.current, processedData, {
            ...defaultLayout,
            ...layout,
            annotations: mergedAnnotations,
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

          // Extract axis labels from layout for enriched tooltips
          const mergedLayout = { ...layout };
          const xAxisLabel = mergedLayout?.xaxis?.title?.text || mergedLayout?.xaxis?.title || '';
          const yAxisLabel = mergedLayout?.yaxis?.title?.text || mergedLayout?.yaxis?.title || '';

          // Attach hover event
          plotRef.current.on('plotly_hover', (eventData) => {
            if (!eventData || !eventData.points || eventData.points.length === 0) return;

            const points = eventData.points;
            const xVal = points[0].x;

            // Compute grand total (sum across ALL bars/points in the trace)
            const firstTrace = points[0]?.data;
            const allYValues = firstTrace?.y || firstTrace?.values || [];
            const grandTotal = allYValues.reduce((s, v) => s + (Number(v) || 0), 0);

            // Compute average across all data points in the trace
            const numericYValues = allYValues.map(v => Number(v) || 0).filter(v => v > 0);
            const avg = numericYValues.length > 0 ? numericYValues.reduce((s, v) => s + v, 0) / numericYValues.length : 0;

            // Compute total categories/data points
            const totalCategories = numericYValues.length;

            // Total records from dataset metadata if available
            const totalRecords = firstTrace?.meta?.totalRecords || null;

            let total = 0;
            const items = points.map(pt => {
              const rawValue = Number(pt.y ?? pt.value ?? 0) || 0;
              total += rawValue;
              // Use yAxisLabel as item name for single-series, trace name for multi-series
              const traceName = pt.data.name || pt.fullData.name || '';
              // Prefer axis label, then chart title, then trace name — avoids "Chart" as metric label
              const metricLabel = yAxisLabel || (chartTitle && chartTitle !== 'Chart' ? chartTitle : null) || traceName || 'Value';
              return {
                name: metricLabel,
                value: formatValue(rawValue),
                rawValue,
                color: resolvePointColor(pt)
              };
            });

            // Compute rank of the current value (1 = highest)
            const currentValue = items[0]?.rawValue || 0;
            const sortedValues = [...numericYValues].sort((a, b) => b - a);
            const rank = sortedValues.indexOf(currentValue) + 1;

            // For Pie charts
            if (chartType === 'pie' || chartType === 'donut') {
               const pt = points[0];
               const pieValues = Array.isArray(pt?.data?.values) ? pt.data.values : [];
               const pieTotal = pieValues.reduce((sum, value) => sum + (Number(value) || 0), 0);
               const pieNumericValues = pieValues.map(v => Number(v) || 0).filter(v => v > 0);
               const pieAvg = pieNumericValues.length > 0 ? pieNumericValues.reduce((s, v) => s + v, 0) / pieNumericValues.length : 0;
               const pieSorted = [...pieNumericValues].sort((a, b) => b - a);
               const pieVal = Number(pt.value) || 0;
               const pieRank = pieSorted.indexOf(pieVal) + 1;

               // Look up pre-computed intelligence from backend
               const ptIntel = pointIntelligence?.points?.[String(pt.label)] || null;

               setTooltip({
                 visible: true,
                 x: eventData.event.clientX,
                 y: eventData.event.clientY,
                 data: {
                   xLabel: pointIntelligence?.x_label || xAxisLabel || 'Slice',
                   xValue: pt.label,
                   yLabel: pointIntelligence?.y_label || yAxisLabel || 'Value',
                   items: [{
                     name: pt.label,
                     value: formatValue(pieVal),
                     rawValue: pieVal,
                     color: resolvePointColor(pt)
                   }],
                   grandTotal: pieTotal,
                   avg: ptIntel ? pointIntelligence.stats.mean : pieAvg,
                   rank: ptIntel?.rank || pieRank,
                   totalCategories: ptIntel ? Object.keys(pointIntelligence.points).length : pieNumericValues.length,
                   totalRecords: ptIntel?.record_count || pointIntelligence?.total_records || null,
                   backendInsight: ptIntel?.insight || null,
                   isOutlier: ptIntel?.is_outlier || false,
                   zScore: ptIntel?.z_score || null,
                   percentile: ptIntel?.percentile || null,
                 }
               });
            } else {
              // For multi-series, keep individual trace names
              const enrichedItems = points.length > 1
                ? points.filter(pt => (Number(pt.y ?? 0) || 0) > 0).map(pt => ({
                    name: pt.data.name || pt.fullData.name || 'Series',
                    value: formatValue(Number(pt.y ?? 0) || 0),
                    rawValue: Number(pt.y ?? 0) || 0,
                    color: resolvePointColor(pt)
                  }))
                : items.filter(item => item.rawValue > 0);

              // Look up pre-computed intelligence from backend
              const ptIntel = pointIntelligence?.points?.[String(xVal)] || null;

              setTooltip({
                visible: true,
                x: eventData.event.clientX,
                y: eventData.event.clientY,
                data: {
                  xLabel: pointIntelligence?.x_label || xAxisLabel,
                  xValue: xVal,
                  yLabel: pointIntelligence?.y_label || yAxisLabel || '',
                  items: enrichedItems.length > 0 ? enrichedItems : items,
                  grandTotal,
                  avg: ptIntel ? pointIntelligence.stats.mean : avg,
                  rank: ptIntel?.rank || (rank > 0 ? rank : null),
                  totalCategories: ptIntel ? Object.keys(pointIntelligence.points).length : totalCategories,
                  totalRecords: ptIntel?.record_count || pointIntelligence?.total_records || null,
                  backendInsight: ptIntel?.insight || null,
                  isOutlier: ptIntel?.is_outlier || false,
                  zScore: ptIntel?.z_score || null,
                  percentile: ptIntel?.percentile || null,
                }
              });
            }
          });

          // Attach unhover event
          plotRef.current.on('plotly_unhover', () => {
             setTooltip(prev => ({ ...prev, visible: false }));
          });

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
      {!isLoading && !error && <CustomTooltip {...tooltip} />}
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
