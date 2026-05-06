'use client'

import React, { useMemo, useState, forwardRef } from 'react'
import { motion } from 'framer-motion'
import {
  TrendingUp, TrendingDown, Minus,
  DollarSign, Users, FileText, BarChart3,
  Activity, Target, Zap, Database, Package,
  ShoppingCart, Percent, Hash, Calendar,
  MessageSquare, Info, Lightbulb, AlertCircle,
  RefreshCw, Clock
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
  MessageSquare, Info, Lightbulb
}

// ─── Status Colors ───
const STATUS_COLORS = {
  success: {
    border: 'border-l-emerald-500',
    text: 'text-emerald-600 dark:text-emerald-400',
    hex: '#10b981',
    bg: 'bg-emerald-500/10',
    badge: 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300'
  },
  critical: {
    border: 'border-l-red-500',
    text: 'text-red-600 dark:text-red-400',
    hex: '#ef4444',
    bg: 'bg-red-500/10',
    badge: 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-300'
  },
  neutral: {
    border: 'border-l-slate-400 dark:border-l-slate-500',
    text: 'text-slate-600 dark:text-slate-400',
    hex: '#64748b',
    bg: 'bg-slate-500/10',
    badge: 'bg-slate-100 dark:bg-slate-500/20 text-slate-700 dark:text-slate-300'
  }
}

// Enterprise accent colors from backend semantic_color calculation
const ACCENT_COLORS = {
  green: {
    border: 'border-l-emerald-500',
    text: 'text-emerald-600 dark:text-emerald-400',
    hex: '#10b981',
    bg: 'bg-emerald-500/10',
  },
  red: {
    border: 'border-l-red-500',
    text: 'text-red-600 dark:text-red-400',
    hex: '#ef4444',
    bg: 'bg-red-500/10',
  },
  amber: {
    border: 'border-l-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
    hex: '#f59e0b',
    bg: 'bg-amber-500/10',
  },
  teal: {
    border: 'border-l-teal-500',
    text: 'text-teal-600 dark:text-teal-400',
    hex: '#14b8a6',
    bg: 'bg-teal-500/10',
  },
  neutral: {
    border: 'border-l-slate-400 dark:border-l-slate-500',
    text: 'text-slate-600 dark:text-slate-400',
    hex: '#64748b',
    bg: 'bg-slate-500/10',
  },
}

const NEUTRAL_ACCENTS = [
  { border: 'border-l-cyan-500', text: 'text-cyan-600 dark:text-cyan-400', hex: '#06b6d4', bg: 'bg-cyan-500/10' },
  { border: 'border-l-violet-500', text: 'text-violet-600 dark:text-violet-400', hex: '#8b5cf6', bg: 'bg-violet-500/10' },
  { border: 'border-l-amber-500', text: 'text-amber-600 dark:text-amber-400', hex: '#f59e0b', bg: 'bg-amber-500/10' },
  { border: 'border-l-rose-500', text: 'text-rose-600 dark:text-rose-400', hex: '#f43f5e', bg: 'bg-rose-500/10' },
  { border: 'border-l-teal-500', text: 'text-teal-600 dark:text-teal-400', hex: '#14b8a6', bg: 'bg-teal-500/10' },
]

// ─── Utility Functions ───
const hashString = (value = '') => {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

const formatValue = (value, format = 'number') => {
  if (value === null || value === undefined || value === 'N/A') return 'N/A'

  const num = typeof value === 'string' ? parseFloat(value.replace(/[^0-9.-]/g, '')) : value
  if (isNaN(num)) return String(value)

  switch (format) {
    case 'currency':
      if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`
      if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`
      if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(2)}K`
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
      }).format(num)
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

const formatFullPrecision = (value, format = 'number') => {
  if (value === null || value === undefined || value === 'N/A') return 'N/A'

  const num = typeof value === 'string' ? parseFloat(value.replace(/[^0-9.-]/g, '')) : value
  if (isNaN(num)) return String(value)

  switch (format) {
    case 'currency':
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }).format(num)
    case 'percentage':
      return `${num.toFixed(2)}%`
    default:
      return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
      }).format(num)
  }
}

const humanizeComparisonLabel = (label) => {
  if (!label) return 'vs previous period'
  if (/row order|first half|time-sorted/i.test(label)) return 'vs previous period'
  return label
}

const getStatusLabel = (status, deltaDirection, higherIsBetter) => {
  if (status === 'success') return higherIsBetter ? 'Improving' : 'Improving'
  if (status === 'critical') return 'Elevated'
  if (deltaDirection === 'up') return 'Elevated'
  if (deltaDirection === 'down') return 'Lower'
  return 'Stable'
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
  if (format === 'currency') return '$'
  return ''
}

const getValueSuffix = (format, unitSuffix) => {
  if (unitSuffix) return unitSuffix
  if (format === 'percentage') return '%'
  return ''
}

// ─── Mini Sparkline Component ───
const MiniSparkline = ({ data, color = '#10b981', height = 48, width = 240 }) => {
  if (!data || data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const padding = 3

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - padding * 2) + padding
    const y = height - padding - ((v - min) / range) * (height - padding * 2)
    return `${x},${y}`
  })

  const pathD = `M ${points.join(' L ')}`
  const areaD = `${pathD} L ${width - padding},${height} L ${padding},${height} Z`
  const lastPt = points[points.length - 1].split(',')

  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      aria-hidden="true"
    >
      <path d={areaD} fill={color} fillOpacity="0.08" />
      <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastPt[0]} cy={lastPt[1]} r="3" fill={color} />
    </svg>
  )
}

// ─── Skeleton Card ───
const SkeletonKpiCard = ({ animationDelay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.4, delay: animationDelay }}
    className="h-full"
  >
    <div className="h-full flex flex-col gap-4 p-5 rounded-xl border border-border/50 bg-card overflow-hidden">
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-32 rounded" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-9 w-36 rounded" />
        <Skeleton className="h-3 w-20 rounded" />
      </div>
      <Skeleton className="h-10 w-full rounded" />
      <div className="grid grid-cols-3 gap-2">
        <Skeleton className="h-12 rounded-lg" />
        <Skeleton className="h-12 rounded-lg" />
        <Skeleton className="h-12 rounded-lg" />
      </div>
      <Skeleton className="h-16 w-full rounded-lg" />
    </div>
  </motion.div>
)

// ─── Empty Card ───
const EmptyKpiCard = ({ title, reason = 'No data available', icon = 'BarChart3', animationDelay = 0 }) => {
  const IconComponent = ICON_MAP[icon] || BarChart3

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: animationDelay }}
      className="h-full"
    >
      <div className="h-full flex flex-col items-center justify-center p-6 rounded-xl border border-dashed border-border/50 bg-card">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
            <IconComponent className="w-5 h-5 text-muted-foreground/50" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="text-xs text-muted-foreground mt-1">{reason}</p>
          </div>
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
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: animationDelay }}
      className="h-full"
    >
      <div className="h-full flex flex-col p-5 rounded-xl border border-red-200 dark:border-red-500/20 bg-card overflow-hidden">
        <div className="flex items-center gap-2 mb-4">
          <IconComponent className="w-4 h-4 text-muted-foreground/60" />
          <span className="text-xs font-medium text-muted-foreground">{title}</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
          <AlertCircle className="w-8 h-8 text-red-500/70" />
          <div>
            <p className="text-sm font-medium text-foreground">Unable to load data</p>
            <p className="text-xs text-muted-foreground mt-1">{errorMessage}</p>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 border border-red-200 dark:border-red-500/25 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
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

// ─── Stale Indicator ───
const StaleIndicator = ({ minutes }) => {
  const formatStaleTime = (mins) => {
    if (mins < 60) return `${mins}m ago`
    if (mins < 1440) return `${Math.floor(mins / 60)}h ago`
    return `${Math.floor(mins / 1440)}d ago`
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20">
            <Clock className="w-2.5 h-2.5" />
            Stale
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p>Data last updated {formatStaleTime(minutes)}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

// ─── Live Indicator ───
const LiveIndicator = () => (
  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
    <span className="relative flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
    </span>
    Live
  </span>
)

// ─── Status Badge Component ───
const StatusBadge = ({ status = 'on-track' }) => {
  const statusConfig = {
    'on-track': {
      cls: 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20',
      label: 'On track'
    },
    'at-risk': {
      cls: 'bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20',
      label: 'At risk'
    },
    'critical': {
      cls: 'bg-red-100 dark:bg-red-500/15 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20',
      label: 'Critical'
    }
  };

  const config = statusConfig[status] || statusConfig['on-track'];

  return (
    <span className={cn('px-2 py-0.5 rounded text-[11px] font-medium border', config.cls)}>
      {config.label}
    </span>
  );
};

// ─── Progress Bar Component ───
const ProgressBar = ({ percent, status = 'on-track' }) => {
  const statusColors = {
    'on-track': 'bg-emerald-500',
    'at-risk': 'bg-amber-500',
    'critical': 'bg-red-500',
  };

  return (
    <div className="h-1 rounded-full overflow-hidden w-full bg-border/50">
      <div
        className={cn('h-full rounded-full transition-all duration-500', statusColors[status] || statusColors['on-track'])}
        style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
      />
    </div>
  );
};

// ─── Main Enterprise KPI Card ───
const EnterpriseKpiCard = forwardRef(({
  title,
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
  // NEW props for period-based KPIs
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
}, ref) => {
  const isDark = theme === 'dark';
  const [showDetails, setShowDetails] = useState(false);

  // Normalize sparklineData - backend returns {data: [], type: "time_series"} or just array
  const normalizedSparkline = useMemo(() => {
    if (!sparklineData) return null
    if (Array.isArray(sparklineData)) {
      return sparklineData.length > 2 ? sparklineData : null
    }
    if (typeof sparklineData === 'object' && sparklineData.data) {
      return sparklineData.data.length > 2 ? sparklineData.data : null
    }
    return null
  }, [sparklineData])

  // Period Selector Component
  const PeriodSelectorComp = () => {
    if (availablePeriods.length === 0) return null;

    return (
      <select
        value={period}
        onChange={(e) => onPeriodChange?.(e.target.value)}
        className={cn(
          "appearance-none cursor-pointer rounded-lg px-3 py-1.5 text-xs font-semibold",
          "transition-all duration-200 bg-transparent border",
          "focus:outline-none focus:ring-1 focus:ring-ocean/50",
          isDark
            ? "text-pearl-muted hover:text-pearl border-pearl/10 hover:border-pearl/20"
            : "text-slate-500 hover:text-slate-700 border-slate-200 hover:border-slate-300"
        )}
      >
        {availablePeriods.map(p => (
          <option key={p} value={p} className={isDark ? "bg-midnight-light" : "bg-white"}>
            {p === 'day' ? 'Today' :
              p === 'week' ? 'This Week' :
                p === 'month' ? 'This Month' :
                  p === 'quarter' ? 'This Quarter' :
                    p === 'year' ? 'This Year' :
                      p === 'all' ? 'All Time' : p}
          </option>
        ))}
      </select>
    );
  };

  const isExpense = /cost|discount|churn|expense|fee|tax|loss/i.test(title)
  const higherIsBetter = !isExpense
  const coverageCount = useMemo(() => getCoverageCount(datasetData), [datasetData])
  const comparisonText = useMemo(() => humanizeComparisonLabel(comparisonLabel), [comparisonLabel])
  const valuePrefix = getValuePrefix(format, unitPrefix)
  const valueSuffix = getValueSuffix(format, unitSuffix)

  // Calculate Delta
  const delta = useMemo(() => {
    if (deltaPercent !== null && deltaPercent !== undefined) {
      return {
        percentChange: deltaPercent,
        direction: deltaPercent > 0 ? 'up' : deltaPercent < 0 ? 'down' : 'neutral',
        previousValue: comparisonValue
      }
    }
    if (comparisonValue !== null && comparisonValue !== undefined && comparisonValue !== 0) {
      const currentNum = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''))
      const prevNum = typeof comparisonValue === 'number' ? comparisonValue : parseFloat(String(comparisonValue).replace(/[^0-9.-]/g, ''))
      if (!isNaN(currentNum) && !isNaN(prevNum) && prevNum !== 0) {
        const pct = ((currentNum - prevNum) / Math.abs(prevNum)) * 100
        return {
          percentChange: pct,
          direction: pct > 0 ? 'up' : pct < 0 ? 'down' : 'neutral',
          previousValue: comparisonValue
        }
      }
    }
    return null
  }, [value, comparisonValue, deltaPercent])

  // Apply Business Status
  const status = useMemo(() => {
    if (!delta || delta.direction === 'neutral') return 'neutral'
    if (higherIsBetter) {
      return delta.direction === 'up' ? 'success' : 'critical'
    } else {
      return delta.direction === 'down' ? 'success' : 'critical'
    }
  }, [delta, higherIsBetter])
  const statusLabel = getStatusLabel(status, delta?.direction, higherIsBetter)
  const insightText = aiSuggestion || benchmarkText || definition || ''
  const detailsText = actionPrompt || insightText || definition || ''

  // Get color style - prefer accent_color from backend when available
  const neutralAccent = useMemo(() => {
    const idx = hashString(`${title}:${icon}`) % NEUTRAL_ACCENTS.length
    return NEUTRAL_ACCENTS[idx]
  }, [title, icon])

  const style = useMemo(() => {
    // If accent_color is provided from backend, use it
    if (accentColor && ACCENT_COLORS[accentColor]) {
      return ACCENT_COLORS[accentColor]
    }
    // Fall back to calculated status
    return status === 'neutral' ? neutralAccent : STATUS_COLORS[status]
  }, [accentColor, status, neutralAccent])
  const IconComponent = ICON_MAP[icon] || BarChart3
  const DeltaIcon = delta?.direction === 'up' ? TrendingUp : delta?.direction === 'down' ? TrendingDown : Minus

  // Render States
  if (state === 'loading') {
    return <SkeletonKpiCard animationDelay={animationDelay} />
  }

  if (state === 'empty') {
    return <EmptyKpiCard title={title} reason={emptyReason} icon={icon} animationDelay={animationDelay} />
  }

  if (state === 'error') {
    return <ErrorKpiCard title={title} errorMessage={errorMessage} icon={icon} animationDelay={animationDelay} onRefresh={onRefresh} />
  }

  // Main Card Render
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: animationDelay }}
      className="h-full"
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className={cn(
        "relative h-full flex flex-col gap-4 p-5 rounded-xl bg-card overflow-hidden transition-colors duration-200 shadow-[0_18px_45px_rgba(0,0,0,0.22)]",
        onClick && "cursor-pointer"
      )}>

        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex flex-col gap-0.5">
            <p className="text-[13px] text-muted-foreground font-normal truncate">{title}</p>
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground/60">
              <span>{comparisonText}</span>
              {state === 'stale' && staleMinutes && staleMinutes > 5 && <StaleIndicator minutes={staleMinutes} />}
              {state === 'live' && <LiveIndicator />}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {isOutlier && (
              <span className="inline-flex items-center gap-1 rounded text-[11px] font-medium border px-2 py-0.5 bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20">
                <AlertCircle className="w-3 h-3" />
                Outlier
              </span>
            )}
            {detailsText && (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  setShowDetails((current) => !current);
                }}
                className={cn(
                  "inline-flex items-center justify-center rounded px-2 py-1 transition-colors",
                  showDetails
                    ? "bg-primary/10 text-primary"
                    : "bg-muted/40 text-muted-foreground hover:text-foreground hover:bg-muted"
                )}
                aria-label={showDetails ? 'Hide KPI details' : 'Show KPI details'}
                title={showDetails ? 'Hide details' : 'Show details'}
              >
                <Info className="w-3.5 h-3.5" />
              </button>
            )}
            <span className={cn(
              "inline-flex items-center gap-1 rounded text-[11px] font-medium border px-2 py-0.5",
              status === 'critical'
                ? "bg-red-100 dark:bg-red-500/15 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20"
                : status === 'success'
                  ? "bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20"
                  : "bg-muted text-muted-foreground border-border/50"
            )}>
              {status === 'critical' && <span className="w-1.5 h-1.5 rounded-full bg-red-500 dark:bg-red-400" />}
              {status === 'success' && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400" />}
              {statusLabel}
            </span>
            <PeriodSelectorComp />
          </div>
        </div>

        <div role="status" aria-label={ariaLabel || `${title}: ${formatValue(value, format)}`}>
          <div className="flex items-baseline gap-1.5 flex-wrap mb-1.5">
            {valuePrefix && <span className="text-xl font-medium text-foreground/70">{valuePrefix}</span>}
            <span className="text-4xl font-semibold text-foreground tracking-tight tabular-nums leading-none">
              {formatValue(value, format)}
            </span>
            {valueSuffix && <span className="text-base font-normal text-muted-foreground">{valueSuffix}</span>}
          </div>
          {delta && (
            <div className="flex items-center gap-1.5 text-[13px]">
              <span className={cn(
                "font-medium flex items-center gap-0.5",
                delta.direction === 'down' && higherIsBetter ? "text-emerald-600 dark:text-emerald-400" :
                delta.direction === 'up' && !higherIsBetter ? "text-red-600 dark:text-red-400" :
                delta.direction === 'up' ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"
              )}>
                <DeltaIcon className="w-3.5 h-3.5" />
                {Math.abs(delta.percentChange).toFixed(1)}%
              </span>
              <span className="text-muted-foreground/70">{comparisonText}</span>
            </div>
          )}
        </div>

        {normalizedSparkline && (
          <div className="h-10">
            <MiniSparkline data={normalizedSparkline} color={style.hex} width={240} height={40} />
          </div>
        )}

        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'Records', value: recordCount != null ? recordCount.toLocaleString() : '—' },
            { label: benchmarkLabel || 'Top 25% avg', value: benchmarkValue != null ? formatFullPrecision(benchmarkValue, format) : (benchmarkText || '—') },
            { label: 'Coverage', value: coverageCount != null ? `${coverageCount} cols` : '—' },
          ].map(({ label, value: val }) => (
            <div key={label} className="bg-muted/50 rounded-lg px-3 py-2.5">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 mb-1">{label}</p>
              <p className="text-[15px] font-medium text-foreground tabular-nums">{val}</p>
            </div>
          ))}
        </div>

        {showDetails && detailsText && (
          <div className="rounded-lg bg-muted/40 px-3.5 py-3">
            <p className="text-[13px] leading-relaxed text-muted-foreground">{detailsText}</p>
          </div>
        )}

        {achievementPercent !== undefined && achievementPercent !== null && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-muted-foreground">{achievementPercent.toFixed(0)}% of target</span>
              <StatusBadge status={periodStatus} />
            </div>
            <ProgressBar percent={achievementPercent} status={periodStatus} />
          </div>
        )}
      </div>
    </motion.div>
  )
})

EnterpriseKpiCard.displayName = 'EnterpriseKpiCard'

export { StatusBadge, ProgressBar };
export default EnterpriseKpiCard
