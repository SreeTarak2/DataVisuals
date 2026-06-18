'use client'

import React, { useMemo, useState, forwardRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  TrendingUp, TrendingDown, Minus, Pencil, Check, X,
  DollarSign, Users, FileText, BarChart3,
  Activity, Target, Zap, Database, Package,
  ShoppingCart, Percent, Hash, Calendar,
  MessageSquare, Info, Lightbulb, AlertCircle,
  RefreshCw, Clock, AlertTriangle
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from './skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider
} from './tooltip'

// ─── Icon Map ───
const ICON_MAP = {
  DollarSign, Users, FileText, BarChart3, Activity,
  Target, Zap, Database, Package, ShoppingCart,
  Percent, Hash, Calendar, TrendingUp,
  MessageSquare, Info, Lightbulb,
}

const ICON_OPTIONS = [
  { value: 'DollarSign', label: '💰 Revenue' },
  { value: 'Users', label: '👥 Users' },
  { value: 'Percent', label: '📊 Percentage' },
  { value: 'BarChart3', label: '📈 Chart' },
  { value: 'Activity', label: '📉 Activity' },
  { value: 'Target', label: '🎯 Target' },
  { value: 'ShoppingCart', label: '🛒 Sales' },
  { value: 'Package', label: '📦 Product' },
  { value: 'Hash', label: '#️⃣ Count' },
  { value: 'Calendar', label: '📅 Date' },
  { value: 'Clock', label: '⏱️ Time' },
  { value: 'Database', label: '🗄️ Data' },
]

// ─── Metric Type Classification ───
const classifyMetricType = (props) => {
  const {
    title = '',
    format,
    sparklineData,
    targetValue,
    achievementPercent,
    isAnomaly,
    anomalyDirection,
    zScore,
    businessCategory,
    deltaPercent,
    benchmarkValue,
  } = props

  const hasSparkline = Array.isArray(sparklineData)
    ? sparklineData.length > 2
    : sparklineData?.data?.length > 2

  // 1. Anomaly — z-score alert, trumps all other types
  if (isAnomaly || (zScore != null && Math.abs(zScore) > 2)) return 'anomaly'

  // 2. Goal — has explicit target with progress measurement
  const hasTarget = targetValue != null && targetValue !== ''
  const hasProgress = achievementPercent != null && achievementPercent !== undefined
  if (hasTarget || hasProgress) return 'goal'

  // 3. Health — rate/score/quality metrics
  if (format === 'percentage' && /score|rate|quality|health|uptime|sla|satisfaction|completion|accuracy|coverage/i.test(title)) return 'health'

  // 4. Snapshot — no sparkline and no significant delta
  if (!hasSparkline && (deltaPercent == null)) return 'snapshot'

  // 5. Trend — has sparkline and/or delta (default for most metrics)
  return 'trend'
}

// ─── Layout definitions per metric type ───
const METRIC_LAYOUTS = {
  trend:    ['header', 'value', 'delta', 'sparkline', 'submetrics', 'freshness', 'insight'],
  snapshot: ['header', 'value', 'sparkline', 'submetrics',              'insight'],
  health:   ['header', 'healthHero', 'sparkline', 'submetrics', 'freshness', 'insight'],
  goal:     ['header', 'value', 'progressBar', 'delta', 'sparkline', 'submetrics', 'insight'],
  anomaly:  ['header', 'value', 'anomalyBadge', 'delta', 'sparkline', 'submetrics', 'insight'],
}

// ─── Deterministic Accent Color System ───
const CATEGORY_ACCENT_MAP = {
  revenue: 'emerald',
  cost: 'rose',
  volume: 'blue',
  users: 'indigo',
  rate_metric: 'violet',
  churn_risk: 'red',
  price: 'teal',
  performance: 'amber',
  duration: 'cyan',
  quantity: 'emerald',
  growth: 'teal',
  neutral: 'neutral',
  unknown: 'neutral',
}

const ACCENT_META = {
  emerald: { hex: '#10b981' },
  teal:    { hex: '#14b8a6' },
  blue:    { hex: '#3b82f6' },
  indigo:  { hex: '#6366f1' },
  violet:  { hex: '#8b5cf6' },
  amber:   { hex: '#f59e0b' },
  orange:  { hex: '#E85002' },
  rose:    { hex: '#f43f5e' },
  cyan:    { hex: '#06b6d4' },
  red:     { hex: '#ef4444' },
  neutral: { hex: '#6b7280' },
}

const getAccentForCategory = (category) => {
  return ACCENT_META[CATEGORY_ACCENT_MAP[category] || 'neutral'] || ACCENT_META.neutral
}

// ─── Trend Colors ───
const getTrendColor = (direction) => {
  if (direction === 'up') return 'var(--kpi-success)'
  if (direction === 'down') return 'var(--kpi-critical)'
  return 'var(--kpi-text-muted)'
}

// ─── Utility Functions ───
const formatValue = (value, format = 'number') => {
  if (value === null || value === undefined || value === 'N/A') return 'N/A'

  const num = typeof value === 'string' ? parseFloat(value.replace(/[^0-9.-]/g, '')) : value
  if (isNaN(num)) return String(value)

  switch (format) {
    case 'currency':
      if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`
      if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`
      if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(2)}K`
      return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(num)
    case 'percentage':
      return `${num.toFixed(1)}%`
    case 'integer':
      if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`
      if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`
      if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`
      return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(num)
    case 'duration':
      return String(value)
    default:
      if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(2)}B`
      if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(2)}M`
      if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(2)}K`
      return new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(num)
  }
}

const humanizeComparisonLabel = (label) => {
  if (!label) return 'vs previous period'
  if (/row order|first half|time-sorted/i.test(label)) return 'vs previous period'
  return label
}

const getCoverageCount = (datasetData) => {
  if (!datasetData) return null
  if (Array.isArray(datasetData) && datasetData.length > 0 && typeof datasetData[0] === 'object' && datasetData[0] !== null) {
    return Object.keys(datasetData[0]).length
  }
  if (Array.isArray(datasetData?.columns)) return datasetData.columns.length
  if (typeof datasetData?.column_count === 'number') return datasetData.column_count
  return null
}

const getValuePrefix = (format, unitPrefix) => {
  if (unitPrefix) return unitPrefix
  return ''
}

const getValueSuffix = (format, unitSuffix) => {
  if (unitSuffix) return unitSuffix
  return ''
}

// ─── Mini Sparkline with Baseline Band & Forecast ───
const MiniSparklineWithBaseline = ({
  data,
  baselineMean,
  baselineStd,
  color = '#10b981',
  isAnomaly,
  anomalyDirection,
  forecastValue,
  height = 40,
  width = 200,
}) => {
  if (!data || data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const padding = 3

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - padding * 2) + padding
    const y = height - padding - ((v - min) / range) * (height - padding * 2)
    return { x, y, value: v }
  })

  const pathD = `M ${points.map(p => `${p.x},${p.y}`).join(' L ')}`
  const areaD = `${pathD} L ${width - padding},${height} L ${padding},${height} Z`
  const lastPt = points[points.length - 1]

  let baselineBandD = null
  let baselineLineY = null
  if (baselineMean != null && baselineStd != null && baselineStd > 0) {
    const bandTop = height - padding - ((baselineMean + baselineStd - min) / range) * (height - padding * 2)
    const bandBottom = height - padding - ((baselineMean - baselineStd - min) / range) * (height - padding * 2)
    baselineBandD = `M ${padding},${bandTop} L ${width - padding},${bandTop} L ${width - padding},${bandBottom} L ${padding},${bandBottom} Z`
    baselineLineY = height - padding - ((baselineMean - min) / range) * (height - padding * 2)
  }

  let forecastLineD = null
  if (forecastValue != null) {
    const fX = width - padding
    const fY = height - padding - ((forecastValue - min) / range) * (height - padding * 2)
    forecastLineD = `M ${lastPt.x},${lastPt.y} L ${fX},${fY}`
  }

  const anomalyDots = []
  if (isAnomaly) {
    points.forEach((p, i) => {
      anomalyDots.push(
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#ef4444" stroke="rgba(239,68,68,0.3)" strokeWidth={2} />
      )
    })
  }

  let dotColor = color
  let dotRadius = 3
  if (anomalyDirection === 'above_normal' || anomalyDirection === 'below_normal') {
    dotColor = '#ef4444'
    dotRadius = 4
  }

  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      aria-hidden="true"
    >
      {baselineBandD && <path d={baselineBandD} fill={color} fillOpacity="0.04" />}
      {baselineLineY != null && (
        <line x1={padding} y1={baselineLineY} x2={width - padding} y2={baselineLineY} stroke={color} strokeWidth="0.75" strokeDasharray="4 3" strokeOpacity="0.25" />
      )}
      <path d={areaD} fill={color} fillOpacity="0.08" />
      <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      {forecastLineD && (
        <path d={forecastLineD} fill="none" stroke={color} strokeWidth="1.25" strokeDasharray="4 4" strokeOpacity="0.5" strokeLinecap="round" />
      )}
      {isAnomaly ? anomalyDots : (
        <circle cx={lastPt.x} cy={lastPt.y} r={dotRadius} fill={dotColor} />
      )}
    </svg>
  )
}

// ─── Skeleton Card ───
const SkeletonKpiCard = ({ animationDelay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.35, delay: animationDelay, ease: [0.16, 1, 0.3, 1] }}
    className="kpi-shell"
    data-accent="neutral"
  >
    <div className="kpi-core">
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-3 w-28 rounded" />
        <Skeleton className="h-5 w-14 rounded-full" />
      </div>
      <Skeleton className="h-9 w-32 rounded mb-2" />
      <Skeleton className="h-3 w-20 rounded mb-3" />
      <Skeleton className="h-8 w-full rounded" />
      <div className="flex gap-2 mt-3">
        <Skeleton className="h-10 flex-1 rounded-lg" />
        <Skeleton className="h-10 flex-1 rounded-lg" />
      </div>
    </div>
  </motion.div>
)

// ─── Empty Card ───
const EmptyKpiCard = ({ title, reason = 'No data available', icon = 'BarChart3', animationDelay = 0 }) => {
  const IconComponent = ICON_MAP[icon] || BarChart3
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: animationDelay, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="kpi-empty">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(128,128,128,0.04)' }}>
          <IconComponent className="w-5 h-5" style={{ color: 'rgba(128,128,128,0.25)' }} />
        </div>
        <div>
          <p className="text-sm font-medium" style={{ color: 'var(--kpi-text-secondary)' }}>{title}</p>
          <p className="text-xs mt-1" style={{ color: 'var(--kpi-text-muted)' }}>{reason}</p>
        </div>
      </div>
    </motion.div>
  )
}

// ─── Error Card ───
const ErrorKpiCard = ({ title, errorMessage = 'Failed to load data', icon = 'BarChart3', animationDelay = 0, onRefresh }) => {
  const IconComponent = ICON_MAP[icon] || BarChart3
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: animationDelay, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="kpi-error">
        <div className="flex items-center gap-2 mb-3">
          <IconComponent className="w-3.5 h-3.5" style={{ color: 'var(--kpi-text-muted)' }} />
          <span className="text-xs font-medium" style={{ color: 'var(--kpi-text-muted)' }}>{title}</span>
        </div>
        <div className="flex flex-col items-center justify-center gap-3 text-center py-2">
          <AlertCircle className="w-7 h-7" style={{ color: 'rgba(239, 68, 68, 0.5)' }} />
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--kpi-text-primary)' }}>Unable to load data</p>
            <p className="text-xs mt-1" style={{ color: 'var(--kpi-text-muted)' }}>{errorMessage}</p>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors"
              style={{
                color: 'rgba(239, 68, 68, 0.8)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                background: 'rgba(239, 68, 68, 0.06)',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.12)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.06)'}
            >
              <RefreshCw className="w-3 h-3" />
              Retry
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

// ─── Driver Badge ───
const DriverBadge = ({ topDriver }) => {
  if (!topDriver || !topDriver.dimension) return null
  const segment = topDriver.segment || '—'
  const pct = topDriver.pctOfTotal != null ? `${topDriver.pctOfTotal.toFixed(0)}%` : '—'

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="block truncate text-xs font-medium" style={{ color: 'var(--kpi-text-secondary)' }}>
            {segment.length > 10 ? segment.slice(0, 10) + '…' : segment} · {pct}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{topDriver.dimension}: {segment} contributes {pct} of total</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

// ════════════════════════════════════════════════
// MAIN COMPONENT
// ════════════════════════════════════════════════

const EnterpriseKpiCard = forwardRef(({
  id,
  title,
  column: columnProp,
  aggregation: aggregationProp,
  value,
  format = 'number',
  definition,
  comparisonValue,
  comparisonLabel,
  deltaPercent,
  benchmarkText,
  isOutlier,
  aiSuggestion,
  sparklineData = [],
  recordCount,
  benchmarkValue,
  benchmarkLabel,
  icon = 'BarChart3',
  animationDelay = 0,
  onAIClick,
  onClick,
  onRefresh,
  state = 'ready',
  staleMinutes,
  errorMessage,
  emptyReason,
  ariaLabel,
  datasetData,
  unitPrefix,
  unitSuffix,
  targetValue,
  targetLabel = 'Target',
  achievementPercent,
  periodStatus = 'on-track',
  period = 'all',
  onPeriodChange,
  availablePeriods = [],
  theme = 'dark',
  accentColor,
  actionPrompt,
  businessCategory,
  periodLabel,
  previousPeriodLabel,
  periodType,
  baselineValue,
  baselineLabel,
  vsBaselinePct,
  baselineStd,
  normalRangeLow,
  normalRangeHigh,
  isAnomaly,
  anomalyDirection,
  zScore,
  anomalySeverity,
  expectedValue,
  trendDirection,
  topDriver,
  vsPreviousPct,
  provenance,
  rootCauseChain,
  metricDecomposition,
  compact = false,
}, ref) => {
  const [showDetails, setShowDetails] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editValues, setEditValues] = useState(null)

  // Available columns from datasetData
  const availableColumns = useMemo(() => {
    if (!datasetData || !Array.isArray(datasetData) || datasetData.length === 0) return []
    return Object.keys(datasetData[0] || {}).filter(k => k !== '_id')
  }, [datasetData])

  const AGG_OPTIONS = [
    { value: 'sum', label: 'Total (SUM)' },
    { value: 'mean', label: 'Average (MEAN)' },
    { value: 'median', label: 'Median' },
    { value: 'count', label: 'Count' },
    { value: 'max', label: 'Maximum' },
    { value: 'min', label: 'Minimum' },
  ]

  const FORMAT_OPTIONS = [
    { value: 'currency', label: 'Currency ($)' },
    { value: 'percentage', label: 'Percentage (%)' },
    { value: 'integer', label: 'Integer' },
    { value: 'decimal', label: 'Decimal' },
    { value: 'number', label: 'Number' },
  ]

  // Client-side KPI recalculation
  const recalculateValue = useCallback((col, agg) => {
    if (!datasetData || !Array.isArray(datasetData) || datasetData.length === 0) return null
    const raw = datasetData
      .map(r => r[col])
      .filter(v => v !== null && v !== undefined && v !== '')
      .map(v => Number(v))
      .filter(n => !isNaN(n))
    if (raw.length === 0) return null
    switch (agg) {
      case 'sum': return raw.reduce((a, b) => a + b, 0)
      case 'mean': return raw.reduce((a, b) => a + b, 0) / raw.length
      case 'median': {
        const sorted = [...raw].sort((a, b) => a - b)
        const mid = Math.floor(sorted.length / 2)
        return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
      }
      case 'count': return raw.length
      case 'max': return Math.max(...raw)
      case 'min': return Math.min(...raw)
      default: return raw.reduce((a, b) => a + b, 0) / raw.length
    }
  }, [datasetData])

  const handleStartEdit = useCallback(() => {
    setEditValues({
      column: columnProp || title,
      aggregation: aggregationProp || 'sum',
      format: format || 'number',
      icon: icon || 'BarChart3',
    })
    setIsEditing(true)
  }, [columnProp, title, aggregationProp, format, icon])

  const handleCancelEdit = useCallback(() => {
    setIsEditing(false)
    setEditValues(null)
  }, [])

  const handleSaveEdit = useCallback(() => {
    if (!editValues) return
    const newValue = recalculateValue(editValues.column, editValues.aggregation)
    window.dispatchEvent(new CustomEvent('kpi-edited', {
      detail: {
        id,
        title,
        column: editValues.column,
        aggregation: editValues.aggregation,
        format: editValues.format,
        icon: editValues.icon,
        value: newValue,
      }
    }))
    setIsEditing(false)
    setEditValues(null)
  }, [editValues, title, id, recalculateValue])

  // ── Edit Panel Component ──
  const EditPanel = () => {
    if (!editValues) return null

    const updateEdit = (field, val) => {
      setEditValues(prev => ({ ...prev, [field]: val }))
    }

    const livePreview = recalculateValue(editValues.column, editValues.aggregation)

    return (
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: 'auto' }}
        exit={{ opacity: 0, height: 0 }}
        className="kpi-edit-panel"
      >
        <div className="kpi-edit-header">
          <span className="kpi-edit-title">Configure Metric</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleSaveEdit}
              className="kpi-edit-btn kpi-edit-btn--save"
              aria-label="Save changes"
            >
              <Check className="w-3 h-3" />
              Apply
            </button>
            <button
              type="button"
              onClick={handleCancelEdit}
              className="kpi-edit-btn kpi-edit-btn--cancel"
              aria-label="Cancel"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>

        <div className="kpi-edit-grid">
          {/* Column */}
          <div className="kpi-edit-field">
            <label className="kpi-edit-label">Column</label>
            {availableColumns.length > 0 ? (
              <select
                value={editValues.column}
                onChange={e => updateEdit('column', e.target.value)}
                className="kpi-edit-select"
              >
                {availableColumns.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            ) : (
              <span className="kpi-edit-empty">No data loaded</span>
            )}
          </div>

          {/* Aggregation */}
          <div className="kpi-edit-field">
            <label className="kpi-edit-label">Aggregation</label>
            <select
              value={editValues.aggregation}
              onChange={e => updateEdit('aggregation', e.target.value)}
              className="kpi-edit-select"
            >
              {AGG_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Format */}
          <div className="kpi-edit-field">
            <label className="kpi-edit-label">Format</label>
            <select
              value={editValues.format}
              onChange={e => updateEdit('format', e.target.value)}
              className="kpi-edit-select"
            >
              {FORMAT_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Icon */}
          <div className="kpi-edit-field">
            <label className="kpi-edit-label">Icon</label>
            <select
              value={editValues.icon}
              onChange={e => updateEdit('icon', e.target.value)}
              className="kpi-edit-select"
            >
              {ICON_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {livePreview !== null && livePreview !== undefined && (
          <div className="kpi-edit-preview">
            <span className="kpi-edit-preview-label">Preview</span>
            <span className="kpi-edit-preview-value">
              {formatValue(livePreview, editValues.format)}
            </span>
          </div>
        )}
      </motion.div>
    )
  }

  // ── Metric Type Detection ──
  const metricType = useMemo(() => classifyMetricType({
    title, format, sparklineData,
    targetValue, achievementPercent,
    isAnomaly, anomalyDirection, zScore,
    businessCategory, deltaPercent,
    benchmarkValue,
  }), [title, format, sparklineData, targetValue, achievementPercent,
      isAnomaly, anomalyDirection, zScore, businessCategory, deltaPercent, benchmarkValue])

  const layout = METRIC_LAYOUTS[metricType] || METRIC_LAYOUTS.trend

  // Normalize sparklineData
  const normalizedSparkline = useMemo(() => {
    if (!sparklineData) return null
    if (Array.isArray(sparklineData)) return sparklineData.length > 2 ? sparklineData : null
    if (typeof sparklineData === 'object' && sparklineData.data) return sparklineData.data.length > 2 ? sparklineData.data : null
    return null
  }, [sparklineData])

  const isExpense = /cost|discount|churn|expense|fee|tax|loss/i.test(title)
  const higherIsBetter = !isExpense
  const coverageCount = useMemo(() => getCoverageCount(datasetData), [datasetData])
  const comparisonText = useMemo(() => humanizeComparisonLabel(comparisonLabel), [comparisonLabel])
  const valuePrefix = getValuePrefix(format, unitPrefix)
  const valueSuffix = getValueSuffix(format, unitSuffix)

  // Calculate Delta
  const delta = useMemo(() => {
    if (deltaPercent !== null && deltaPercent !== undefined) {
      return { percentChange: deltaPercent, direction: deltaPercent > 0 ? 'up' : deltaPercent < 0 ? 'down' : 'neutral', previousValue: comparisonValue }
    }
    if (comparisonValue !== null && comparisonValue !== undefined && comparisonValue !== 0) {
      const currentNum = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''))
      const prevNum = typeof comparisonValue === 'number' ? comparisonValue : parseFloat(String(comparisonValue).replace(/[^0-9.-]/g, ''))
      if (!isNaN(currentNum) && !isNaN(prevNum) && prevNum !== 0) {
        const pct = ((currentNum - prevNum) / Math.abs(prevNum)) * 100
        return { percentChange: pct, direction: pct > 0 ? 'up' : pct < 0 ? 'down' : 'neutral', previousValue: comparisonValue }
      }
    }
    return null
  }, [value, comparisonValue, deltaPercent])

  // Status computation
  const kpiStatus = useMemo(() => {
    if (baselineValue != null && baselineStd != null && baselineStd > 0) {
      const z = (value - baselineValue) / baselineStd
      if (Math.abs(z) > 3) {
        if (higherIsBetter) return z > 0 ? { status: 'success', label: 'Above Target' } : { status: 'critical', label: 'Below Target' }
        else return z > 0 ? { status: 'critical', label: 'Elevated' } : { status: 'success', label: 'Below Normal' }
      }
      if (Math.abs(z) > 2) return { status: 'warning', label: 'Watch' }
      return { status: 'neutral', label: 'Normal' }
    }
    if (!delta || delta.direction === 'neutral') return { status: 'neutral', label: 'Stable' }
    if (higherIsBetter) return delta.direction === 'up' ? { status: 'success', label: 'Improving' } : { status: 'critical', label: 'Declining' }
    else return delta.direction === 'down' ? { status: 'success', label: 'Improving' } : { status: 'critical', label: 'Elevated' }
  }, [value, baselineValue, baselineStd, higherIsBetter, delta])

  const status = kpiStatus.status
  const statusLabel = kpiStatus.label
  const insightText = aiSuggestion || benchmarkText || definition || ''
  const detailsText = actionPrompt || insightText || definition || ''

  // Deterministic accent color
  const effectiveCategory = useMemo(() => {
    if (businessCategory && businessCategory !== 'unknown') return businessCategory
    const lower = title.toLowerCase()
    for (const [key] of Object.entries(CATEGORY_ACCENT_MAP)) {
      if (key === 'neutral' || key === 'unknown') continue
      if (lower.includes(key)) return key
    }
    return 'neutral'
  }, [businessCategory, title])

  const accentName = CATEGORY_ACCENT_MAP[effectiveCategory] || 'neutral'

  const IconComponent = ICON_MAP[icon] || BarChart3
  const kpiIconColor = useMemo(() => {
    const meta = ACCENT_META[accentName]
    return meta?.hex || '#6b7280'
  }, [accentName])
  const DeltaIcon = delta?.direction === 'up' ? TrendingUp : delta?.direction === 'down' ? TrendingDown : Minus

  // Format stale minutes
  const formattedStaleTime = staleMinutes != null
    ? staleMinutes < 60 ? `${staleMinutes}m ago`
      : staleMinutes < 1440 ? `${Math.floor(staleMinutes / 60)}h ago`
      : `${Math.floor(staleMinutes / 1440)}d ago`
    : null

  // ── Provenance / Root Cause visibility ──
  const hasProvenance = provenance && (provenance.record_count > 0 || provenance.null_count > 0)
  const hasRootCause = rootCauseChain && rootCauseChain.has_root_cause
  const hasMetricDecomp = metricDecomposition && metricDecomposition.has_decomposition && metricDecomposition.components?.length > 0

  const isDrillable = !!onClick
  const metricDecompTitle = hasMetricDecomp
    ? `${title} decomposes into ${metricDecomposition.component_count} components`
    : null
  const formattedValue = formatValue(value, format)

  // ── Period Selector ──
  const PeriodSelectorComp = () => {
    if (availablePeriods.length === 0) return null
    return (
      <select
        value={period}
        onChange={(e) => onPeriodChange?.(e.target.value)}
        className="appearance-none cursor-pointer rounded-md px-2 py-1 text-[11px] font-semibold transition-colors bg-transparent border focus:outline-none"
        style={{ color: 'var(--kpi-text-muted)', borderColor: 'rgba(128,128,128,0.06)' }}
      >
        {availablePeriods.map(p => (
          <option key={p} value={p}>{p === 'day' ? 'Today' : p === 'week' ? 'This Week' : p === 'month' ? 'This Month' : p === 'quarter' ? 'This Quarter' : p === 'year' ? 'This Year' : p === 'all' ? 'All Time' : p}</option>
        ))}
      </select>
    )
  }

  // ── Sub-components ──

  const StatusPill = ({ size = 'default' }) => {
    if (!statusLabel) return null
    return (
      <span className={cn(
        'kpi-pill',
        size === 'hero' && 'kpi-pill--hero',
        status === 'critical' ? 'kpi-pill--critical' :
        status === 'success' ? 'kpi-pill--success' :
        status === 'warning' ? 'kpi-pill--warning' :
        'kpi-pill--neutral'
      )}>
        {status === 'critical' && <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--kpi-critical)' }} />}
        {status === 'success' && <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--kpi-success)' }} />}
        {status === 'warning' && <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--kpi-warning)' }} />}
        {statusLabel}
      </span>
    )
  }

  const DeltaDisplay = () => {
    if (vsBaselinePct != null) {
      return (
        <div className="kpi-delta-row">
          <span className="kpi-trend" data-direction={vsBaselinePct > 0 ? 'up' : vsBaselinePct < 0 ? 'down' : 'neutral'}>
            {vsBaselinePct > 0
              ? <TrendingUp className="kpi-trend-icon" />
              : <TrendingDown className="kpi-trend-icon" />
            }
            {Math.abs(vsBaselinePct).toFixed(1)}%
          </span>
          {baselineLabel && (
            <span className="kpi-comparison-label">vs {baselineLabel}</span>
          )}
        </div>
      )
    }
    if (delta) {
      return (
        <div className="kpi-delta-row">
          <span className="kpi-trend" data-direction={delta.direction}>
            <DeltaIcon className="kpi-trend-icon" />
            {Math.abs(delta.percentChange).toFixed(1)}%
          </span>
          <span className="kpi-comparison-label">{comparisonText}</span>
        </div>
      )
    }
    return null
  }

  const AnomalyBadge = () => {
    if (metricType !== 'anomaly') return null
    const severityColor = anomalySeverity === 'critical' ? 'var(--kpi-critical)' : 'var(--kpi-warning)'
    const severityBg = anomalySeverity === 'critical' ? 'var(--kpi-critical-bg)' : 'var(--kpi-warning-bg)'
    return (
      <div className="kpi-anomaly-badge" style={{ background: severityBg }}>
        <AlertTriangle className="w-3.5 h-3.5" style={{ color: severityColor }} />
        <span className="kpi-anomaly-severity" style={{ color: severityColor }}>
          {anomalySeverity === 'critical' ? 'Critical' : 'Warning'}
        </span>
        <span className="kpi-anomaly-zscore" style={{ color: 'var(--kpi-text-disabled)' }}>
          {zScore != null ? `${zScore > 0 ? '+' : ''}${zScore.toFixed(1)}σ` : ''}
        </span>
        {expectedValue != null && (
          <span className="kpi-anomaly-expected" style={{ color: 'var(--kpi-text-muted)' }}>
            Expected: {formatValue(expectedValue, format)}
          </span>
        )}
      </div>
    )
  }

  const ProgressBarDisplay = () => {
    if (achievementPercent === null || achievementPercent === undefined) return null
    return (
      <div className="kpi-progress">
        <span className="kpi-progress-label">{targetLabel}: {formatValue(targetValue, format)}</span>
        <div className="kpi-progress-track">
          <div
            className="kpi-progress-fill"
            data-status={periodStatus}
            style={{ width: `${Math.min(Math.max(achievementPercent, 0), 100)}%` }}
          />
        </div>
        <span className="kpi-progress-label">{achievementPercent.toFixed(0)}%</span>
      </div>
    )
  }

  const SubMetrics = () => {
    const hasMetrics = baselineValue != null || vsBaselinePct != null || topDriver
    if (!hasMetrics) return null
    return (
      <div className="kpi-metrics">
        {baselineValue != null && (
          <div className="kpi-metric-item">
            <p className="kpi-metric-label">Baseline</p>
            <p className="kpi-metric-value">{formatValue(baselineValue, format)}</p>
          </div>
        )}
        {vsBaselinePct != null && (
          <div className="kpi-metric-item">
            <p className="kpi-metric-label">vs Baseline</p>
            <p className="kpi-metric-value" style={{ color: getTrendColor(vsBaselinePct > 0 ? 'up' : 'down') }}>
              {vsBaselinePct.toFixed(1)}%
            </p>
          </div>
        )}
        {topDriver && (
          <div className="kpi-metric-item">
            <p className="kpi-metric-label">Top Driver</p>
            <DriverBadge topDriver={topDriver} />
          </div>
        )}
      </div>
    )
  }

  // ── Section Renderer ──
  const renderSection = (section) => {
    switch (section) {
      case 'header':
        return (
          <div key="header" className="kpi-header">
            <div className="flex items-center gap-2 min-w-0">
              <IconComponent className="w-4 h-4 shrink-0" style={{ color: kpiIconColor, opacity: 0.6 }} />
              <span className="kpi-title" title={title}>{title}</span>
            </div>
            <div className="kpi-header-right">
              <StatusPill />
              {!isEditing && (
                <button
                  type="button"
                  onClick={(event) => { event.stopPropagation(); handleStartEdit() }}
                  className="kpi-edit-trigger"
                  aria-label="Edit KPI"
                  title="Configure metric"
                >
                  <Pencil className="w-3 h-3" />
                </button>
              )}
              {(detailsText || hasProvenance || hasRootCause || hasMetricDecomp) && (
                <button
                  type="button"
                  onClick={(event) => { event.stopPropagation(); setShowDetails(s => !s) }}
                  className="inline-flex items-center justify-center w-5 h-5 rounded transition-colors"
                  style={{ color: showDetails ? 'rgba(128,128,128,0.7)' : 'rgba(128,128,128,0.25)' }}
                  aria-label={showDetails ? 'Hide KPI details' : 'Show KPI details'}
                >
                  <Info className="w-3 h-3" />
                </button>
              )}
              <PeriodSelectorComp />
              {isDrillable && (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'rgba(128,128,128,0.15)' }}>
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              )}
            </div>
          </div>
        )

      case 'value':
        return (
          <div key="value" className="kpi-value-row">
            {valuePrefix && <span className="kpi-prefix">{valuePrefix}</span>}
            <span className="kpi-value" role="status" aria-label={ariaLabel || `${title}: ${formattedValue}`}>
              {formattedValue}
            </span>
            {valueSuffix && <span className="kpi-suffix">{valueSuffix}</span>}
          </div>
        )

      case 'delta':
        if (!delta && vsBaselinePct == null) return null
        return <div key="delta">{DeltaDisplay()}</div>

      case 'healthHero':
        return (
          <div key="healthHero" className="kpi-health-hero">
            <div className="kpi-value-row">
              {valuePrefix && <span className="kpi-prefix">{valuePrefix}</span>}
              <span className="kpi-value" role="status">{formattedValue}</span>
              {valueSuffix && <span className="kpi-suffix">{valueSuffix}</span>}
            </div>
            <StatusPill size="hero" />
          </div>
        )

      case 'sparkline':
        if (!normalizedSparkline) return null
        return (
          <div key="sparkline" className="kpi-sparkline">
            <MiniSparklineWithBaseline
              data={normalizedSparkline}
              baselineMean={baselineValue}
              baselineStd={baselineStd}
              color={ACCENT_META[accentName]?.hex || '#6b7280'}
              isAnomaly={isAnomaly}
              anomalyDirection={anomalyDirection}
              forecastValue={expectedValue}
            />
          </div>
        )

      case 'progressBar':
        if (achievementPercent == null) return null
        return <div key="progressBar">{ProgressBarDisplay()}</div>

      case 'anomalyBadge':
        if (metricType !== 'anomaly') return null
        return <div key="anomalyBadge">{AnomalyBadge()}</div>

      case 'submetrics': {
        const hasSubMetrics = baselineValue != null || vsBaselinePct != null || topDriver
        if (!hasSubMetrics && !isEditing) return null
        return <div key="submetrics">{isEditing ? <EditPanel /> : SubMetrics()}</div>
      }

      case 'freshness':
        return (
          <div key="freshness">
            {formattedStaleTime && (
              <div className="flex items-center gap-1 mt-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: 'rgba(245, 158, 11, 0.5)' }} />
                <span className="text-[10px]" style={{ color: 'var(--kpi-text-disabled)' }}>{formattedStaleTime}</span>
              </div>
            )}
            {state === 'live' && (
              <div className="flex items-center gap-1.5 mt-2">
                <span className="kpi-live-dot" />
                <span className="text-[10px]" style={{ color: 'var(--kpi-success)' }}>Live</span>
              </div>
            )}
          </div>
        )

      case 'insight':
        if (!showDetails) return null
        if (!detailsText && !hasProvenance && !hasRootCause && !hasMetricDecomp) return null
        return (
          <div key="insight" className="kpi-insight">
            {detailsText && <p className="text-xs leading-relaxed mb-2" style={{ color: 'var(--kpi-text-secondary)' }}>{detailsText}</p>}
            {hasProvenance && (
              <div className="kpi-provenance">
                <div className="kpi-provenance-header">
                  <Database className="w-3 h-3" />
                  <span>Provenance</span>
                  {provenance.confidence_label && (
                    <span className={`kpi-confidence-badge kpi-confidence-badge--${provenance.confidence_label.toLowerCase()}`}>
                      {provenance.confidence_label}
                    </span>
                  )}
                </div>
                <div className="kpi-provenance-grid">
                  <div className="kpi-provenance-item">
                    <span className="kpi-provenance-label">Formula</span>
                    <span className="kpi-provenance-value">{provenance.formula_description || `${provenance.aggregation?.toUpperCase?.() || 'SUM'}(${provenance.column || title})`}</span>
                  </div>
                  {provenance.record_count > 0 && (
                    <div className="kpi-provenance-item">
                      <span className="kpi-provenance-label">Records</span>
                      <span className="kpi-provenance-value">{provenance.record_count.toLocaleString()}</span>
                    </div>
                  )}
                  {provenance.null_count > 0 && (
                    <div className="kpi-provenance-item">
                      <span className="kpi-provenance-label">Nulls</span>
                      <span className="kpi-provenance-value">{provenance.null_count.toLocaleString()} ({provenance.null_pct?.toFixed?.(1) || '0'}%)</span>
                    </div>
                  )}
                  {provenance.downsampled && (
                    <div className="kpi-provenance-item">
                      <span className="kpi-provenance-label">Sampled</span>
                      <span className="kpi-provenance-value">{provenance.downsample_ratio ? `${(provenance.downsample_ratio * 100).toFixed(0)}% of rows` : 'Yes'}</span>
                    </div>
                  )}
                  {provenance.total_rows > provenance.record_count && (
                    <div className="kpi-provenance-item">
                      <span className="kpi-provenance-label">Total rows</span>
                      <span className="kpi-provenance-value">{provenance.total_rows.toLocaleString()}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            {hasRootCause && (
              <div className="kpi-root-cause">
                <div className="kpi-provenance-header">
                  <Activity className="w-3 h-3" />
                  <span>Root Cause</span>
                </div>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--kpi-text-secondary)' }}>
                  {rootCauseChain.summary || rootCauseChain.links?.[0]?.headline || ''}
                </p>
                {rootCauseChain.links?.[0]?.contributors?.length > 0 && (
                  <div className="kpi-provenance-grid" style={{ marginTop: 6 }}>
                    {rootCauseChain.links[0].contributors.slice(0, 3).map((c, i) => (
                      <div key={i} className="kpi-provenance-item">
                        <span className="kpi-provenance-label">{c.dimension}</span>
                        <span className="kpi-provenance-value">{c.segment} · {c.contribution_pct > 0 ? '+' : ''}{c.contribution_pct?.toFixed?.(0) || '0'}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {hasMetricDecomp && (
              <div className="kpi-root-cause">
                <div className="kpi-provenance-header">
                  <BarChart3 className="w-3 h-3" />
                  <span>Metric Decomposition</span>
                </div>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--kpi-text-secondary)' }}>
                  {metricDecompTitle}
                </p>
                <div className="kpi-provenance-grid" style={{ marginTop: 6 }}>
                  {metricDecomposition.components.slice(0, 4).map((c, i) => (
                    <div key={i} className="kpi-provenance-item">
                      <span className="kpi-provenance-label">{c.column}</span>
                      <span className="kpi-provenance-value" style={{ color: c.change_pct > 0 ? 'var(--kpi-success)' : c.change_pct < 0 ? 'var(--kpi-critical)' : undefined }}>
                        {c.change_pct > 0 ? '+' : ''}{c.change_pct?.toFixed?.(1) || '0'}%
                        {c.contribution_pp != null && (
                          <span style={{ color: 'var(--kpi-text-disabled)', marginLeft: 4 }}>
                            · {c.contribution_pp > 0 ? '+' : ''}{c.contribution_pp.toFixed(1)}pp
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )

      default:
        return null
    }
  }

  // ── Render States ──
  if (state === 'loading') return <SkeletonKpiCard animationDelay={animationDelay} />
  if (state === 'empty') return <EmptyKpiCard title={title} reason={emptyReason} icon={icon} animationDelay={animationDelay} />
  if (state === 'error') return <ErrorKpiCard title={title} errorMessage={errorMessage} icon={icon} animationDelay={animationDelay} onRefresh={onRefresh} />

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: animationDelay, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(e) } } : undefined}
      className={cn(onClick && 'cursor-pointer')}
    >
      <div
        className="kpi-shell"
        data-accent={accentName}
        data-compact={compact ? 'true' : 'false'}
        data-metric-type={metricType}
        data-editing={isEditing ? 'true' : 'false'}
      >
        <div className="kpi-core">
          {layout.map((section) => renderSection(section))}
        </div>
      </div>
    </motion.div>
  )
})

EnterpriseKpiCard.displayName = 'EnterpriseKpiCard'

export default EnterpriseKpiCard
