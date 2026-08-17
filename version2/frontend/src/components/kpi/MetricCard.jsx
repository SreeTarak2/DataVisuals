import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react';
import { resolveMetricIcon, trendIcon } from './MetricIcon';
import { cn } from '../../lib/utils';

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Compact number formatting: 1_234_567 → "1.2M" */
function compactNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '−' : '';
  if (abs >= 1e9)  return `${sign}${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6)  return `${sign}${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3)  return `${sign}${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${Number.isInteger(value) ? value.toLocaleString() : value.toFixed(1)}`;
}

function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '−' : '';
  if (abs >= 1e9)  return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6)  return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3)  return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2)}`;
}

function formatPercentage(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function formatValue(value, fmt) {
  if (fmt === 'currency')   return formatCurrency(value);
  if (fmt === 'percentage') return formatPercentage(value);
  if (fmt === 'integer')    return compactNumber(value);
  return compactNumber(value);
}

/** Compute delta from previous → current value */
function computeDelta(current, previous) {
  if (current == null || previous == null || previous === 0) return null;
  const pct = ((current - previous) / Math.abs(previous)) * 100;
  return {
    pct: Math.abs(pct),
    direction: pct > 0 ? 'up' : pct < 0 ? 'down' : 'neutral',
    isPositive: pct >= 0,
    absPct: Math.abs(pct),
  };
}

// ─── Sparkline ────────────────────────────────────────────────────────────────

const MiniSparkline = ({ data, color = '#10b981', height = 36, width = 160 }) => {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - pad * 2) + pad;
    const y = height - pad - ((v - min) / range) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="block w-full" aria-hidden="true">
      <path d={`M ${pts.join(' L ')}`} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
      <path d={`M ${pts[pts.length - 1].split(',')[0]} ${height} L ${pts.join(' L ')} L ${pad} ${height} Z`} fill={color} fillOpacity="0.04" />
    </svg>
  );
};

// ─── Skeleton ────────────────────────────────────────────────────────────────

const Skeleton = ({ className }) => (
  <div className={cn('animate-pulse rounded bg-white/10', className)} />
);

// ─── Card ────────────────────────────────────────────────────────────────────

/**
 * MetricCard — a single KPI/metric card.
 *
 * Props:
 *  - title         : string                — metric label
 *  - value         : number                — current value
 *  - format        : 'currency' | 'percentage' | 'integer' | 'number'
 *  - previousValue : number | null         — comparison period value
 *  - deltaPct      : number | null         — pre-computed delta %
 *  - deltaDirection: 'up' | 'down' | 'neutral' | null
 *  - comparisonLabel : string | null       — e.g. "vs last month"
 *  - sparklineData : number[] | null       — time-series data points
 *  - businessCategory : string | null      — drives icon & accent color
 *  - iconName      : string | null         — overrides businessCategory icon
 *  - loading       : boolean
 *  - error         : string | null
 *  - onClick       : function              — drill-down handler
 *  - accentColor   : string | null         — hex color override
 */
const MetricCard = React.forwardRef(({
  title,
  value,
  format = 'number',
  previousValue,
  deltaPct,
  deltaDirection,
  comparisonLabel,
  sparklineData,
  businessCategory,
  iconName,
  loading = false,
  error = null,
  onClick,
  accentColor,
}, ref) => {
  // Resolve icon
  const Icon = useMemo(() => resolveMetricIcon(businessCategory, iconName), [businessCategory, iconName]);

  // Compute delta if not pre-computed
  const delta = useMemo(() => {
    if (deltaPct != null && deltaDirection) return { pct: Math.abs(deltaPct), direction: deltaDirection, isPositive: deltaDirection === 'up' };
    if (previousValue != null) return computeDelta(value, previousValue);
    return null;
  }, [value, previousValue, deltaPct, deltaDirection]);

  // Accent color
  const accent = accentColor || '#3b82f6';

  // Determine if "up is good"
  const isExpense = /cost|churn|expense|fee|tax|loss|defect|error|latency|spend/i.test(title);
  const higherIsBetter = !isExpense;
  const isGood = delta ? (higherIsBetter ? delta.direction === 'up' : delta.direction === 'down') : null;

  // ── Loading state ──
  if (loading) {
    return (
      <div className="flex flex-col gap-3 p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] min-h-[140px]">
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-4 w-4 rounded-full" />
        </div>
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  // ── Error state ──
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 p-5 rounded-2xl bg-white/[0.03] border border-red-500/20 min-h-[140px]">
        <AlertCircle className="w-5 h-5 text-red-400/60" />
        <p className="text-xs text-red-400/50 text-center">{error}</p>
      </div>
    );
  }

  // ── Empty / no-data state ──
  if (value === null || value === undefined) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 p-5 rounded-2xl bg-white/[0.03] border border-white/[0.06] min-h-[140px]">
        <Icon className="w-5 h-5 text-white/20" />
        <p className="text-xs text-white/30">{title}</p>
        <p className="text-[10px] text-white/20">No data</p>
      </div>
    );
  }

  const dt = delta;
  const DeltaIcon = dt ? trendIcon(dt.direction) : null;
  const trendColor = dt
    ? isGood ? '#34d399' : dt.direction === 'neutral' ? '#6b7280' : '#f87171'
    : '#6b7280';

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(e); } } : undefined}
      className={cn(
        'group relative flex flex-col gap-2 p-5 rounded-2xl border transition-all duration-300',
        'bg-white/[0.03] border-white/[0.06]',
        'hover:bg-white/[0.05] hover:border-white/[0.12]',
        onClick && 'cursor-pointer hover:shadow-lg hover:shadow-black/10',
        'active:scale-[0.99]',
      )}
    >
      {/* Header: icon + title */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className="w-4 h-4 shrink-0" style={{ color: accent, opacity: 0.7 }} aria-hidden="true" />
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-white/50 truncate" title={title}>
            {title}
          </span>
        </div>
        {dt && (
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold"
            style={{
              color: isGood ? '#34d399' : dt.direction === 'neutral' ? '#6b7280' : '#f87171',
              background: isGood ? 'rgba(52,211,153,0.1)' : dt.direction === 'neutral' ? 'rgba(107,114,128,0.1)' : 'rgba(248,113,113,0.1)',
            }}
          >
            <DeltaIcon className="w-3 h-3" />
            {dt.pct.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold tracking-tight text-white/90 tabular-nums">
          {formatValue(value, format)}
        </span>
      </div>

      {/* Comparison context */}
      {dt && (
        <div className="flex items-center gap-1.5">
          <span className="text-[11px]" style={{ color: trendColor }}>
            {dt.direction === 'up' ? '↑' : dt.direction === 'down' ? '↓' : '→'}
            {' '}{formatValue(dt.pct, 'percentage')}
          </span>
          {comparisonLabel && (
            <span className="text-[11px] text-white/30">{comparisonLabel}</span>
          )}
        </div>
      )}

      {/* Sparkline */}
      {sparklineData && sparklineData.length >= 2 && (
        <div className="mt-1 opacity-60 group-hover:opacity-90 transition-opacity duration-300">
          <MiniSparkline data={sparklineData} color={accent} />
        </div>
      )}

      {/* Hover hint (only if clickable) */}
      {onClick && (
        <div className="absolute inset-0 rounded-2xl ring-1 ring-inset ring-white/0 group-hover:ring-white/[0.04] transition-all duration-300 pointer-events-none" />
      )}
    </motion.div>
  );
});

MetricCard.displayName = 'MetricCard';
export default MetricCard;
