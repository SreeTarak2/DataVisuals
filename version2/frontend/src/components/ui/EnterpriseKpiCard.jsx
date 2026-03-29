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

// ─── Mini Sparkline Component ───
const MiniSparkline = ({ data, color = '#10b981', height = 48, width = 120 }) => {
  if (!data || data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const padding = 4

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - padding * 2) + padding
    const y = height - padding - ((v - min) / range) * (height - padding * 2)
    return `${x},${y}`
  })

  const pathD = `M ${points.join(' L ')}`
  const areaD = `${pathD} L ${width - padding},${height} L ${padding},${height} Z`
  const gradId = `sparkGrad-${color.replace('#', '')}-${Math.random().toString(36).substr(2, 5)}`

  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden="true">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
        <filter id={`glow-${gradId}`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <path d={areaD} fill={`url(#${gradId})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="drop-shadow-sm" />
      <circle cx={width - padding} cy={height - padding - ((data[data.length - 1] - min) / range) * (height - padding * 2)} r="3" fill={color} filter={`url(#glow-${gradId})`} />
      <circle cx={padding} cy={height - padding - ((data[0] - min) / range) * (height - padding * 2)} r="2" fill={color} opacity="0.4" />
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
    <div className="relative h-full flex flex-col p-6 rounded-xl border border-border/60 bg-card overflow-hidden">
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-slate-400/40 rounded-l-xl" />
      <div className="flex items-center gap-3 mb-4">
        <Skeleton className="w-9 h-9 rounded-lg" />
        <Skeleton className="h-3 w-24 rounded" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-10 w-40 rounded" />
        <Skeleton className="h-3 w-16 rounded" />
      </div>
      <div className="absolute bottom-4 right-4">
        <Skeleton className="w-[100px] h-[40px] rounded" />
      </div>
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
      <div className="relative h-full flex flex-col items-center justify-center p-6 rounded-xl border border-dashed border-border/40 bg-muted/20">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="w-12 h-12 rounded-lg bg-slate-200/50 dark:bg-slate-700/50 flex items-center justify-center">
            <IconComponent className="w-6 h-6 text-muted-foreground/40" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{title}</p>
            <p className="text-xs text-muted-foreground/70 mt-1">{reason}</p>
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
      <div className="relative h-full flex flex-col p-6 rounded-xl border border-red-200/50 dark:border-red-500/25 bg-red-50/30 dark:bg-red-500/5">
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-500/60 rounded-l-xl" />
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg bg-red-100/80 dark:bg-red-500/15 flex items-center justify-center">
            <IconComponent className="w-4 h-4 text-red-600 dark:text-red-400" />
          </div>
          <span className="text-xs font-semibold text-red-700 dark:text-red-400 uppercase tracking-wider">
            {title}
          </span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-red-100/60 dark:bg-red-500/10 flex items-center justify-center">
            <AlertCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-red-700 dark:text-red-300">Unable to Load Data</p>
            <p className="text-xs text-red-600/70 dark:text-red-400/60 mt-1">{errorMessage}</p>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="mt-3 inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-red-700 dark:text-red-400 bg-red-100/80 dark:bg-red-500/15 border border-red-200/50 dark:border-red-500/25 rounded-lg hover:bg-red-200/80 dark:hover:bg-red-500/25 transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" />
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
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400 rounded text-xs font-bold uppercase tracking-wider">
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
  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 rounded text-xs font-bold uppercase tracking-wider">
    <span className="relative flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
    </span>
    Live
  </span>
)

// ─── Status Badge Component ───
const StatusBadge = ({ status = 'on-track', theme = 'dark' }) => {
  const isDark = theme === 'dark';

  const statusConfig = {
    'on-track': {
      bg: isDark ? 'bg-emerald-500/15' : 'bg-emerald-100',
      border: isDark ? 'border-emerald-500/30' : 'border-emerald-300/50',
      text: isDark ? 'text-emerald-400' : 'text-emerald-700',
      label: '✓ On Track'
    },
    'at-risk': {
      bg: isDark ? 'bg-amber-500/15' : 'bg-amber-100',
      border: isDark ? 'border-amber-500/30' : 'border-amber-300/50',
      text: isDark ? 'text-amber-400' : 'text-amber-700',
      label: '⚠ At Risk'
    },
    'critical': {
      bg: isDark ? 'bg-rose-500/15' : 'bg-red-100',
      border: isDark ? 'border-rose-500/30' : 'border-red-300/50',
      text: isDark ? 'text-rose-400' : 'text-red-700',
      label: '✕ Critical'
    }
  };

  const config = statusConfig[status] || statusConfig['on-track'];

  return (
    <span className={cn(
      "px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border",
      config.bg, config.text, config.border
    )}>
      {config.label}
    </span>
  );
};

// ─── Progress Bar Component ───
const ProgressBar = ({ percent, status = 'on-track', theme = 'dark' }) => {
  const isDark = theme === 'dark';

  const statusColors = {
    'on-track': isDark ? 'bg-emerald-500' : 'bg-emerald-600',
    'at-risk': isDark ? 'bg-amber-500' : 'bg-amber-600',
    'critical': isDark ? 'bg-rose-500' : 'bg-red-600'
  };

  return (
    <div className={cn(
      "h-1.5 rounded-full overflow-hidden w-full",
      isDark ? "bg-slate-700/40" : "bg-slate-200"
    )}>
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500 shadow-lg shadow-transparent",
          statusColors[status] || statusColors['on-track']
        )}
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
        "relative h-full flex flex-col p-6 rounded-xl border bg-card overflow-hidden transition-all duration-300",
        "hover:shadow-xl hover:-translate-y-1",
        "border-border/60 hover:border-border/100",
        onClick && "cursor-pointer",
        "before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/5 before:to-transparent before:pointer-events-none"
      )}>
        {/* Left accent line */}
        <div className={cn(
          "absolute left-0 top-0 bottom-0 w-1 rounded-l-xl transition-all duration-300",
          style.border.replace('border-l-', 'bg-')
        )} />

        {/* Zone 1: Header (40px) */}
        <div className="flex items-center justify-between mb-4 relative z-10">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className={cn(
              "w-9 h-9 rounded-lg flex items-center justify-center shrink-0 transition-all duration-200",
              "shadow-sm",
              style.bg
            )}>
              <IconComponent className={cn("w-4 h-4", style.text)} />
            </div>
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <span className="text-xs font-semibold text-pearl-muted uppercase tracking-wider truncate">
                {title}
              </span>
              {definition && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button className="text-muted-foreground/60 hover:text-muted-foreground transition-colors focus:outline-none shrink-0">
                        <Info className="w-3.5 h-3.5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs">
                      <p className="text-xs">{definition}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
          </div>

          {/* Status indicators */}
          <div className="flex items-center gap-2 ml-2">
            {state === 'stale' && staleMinutes && staleMinutes > 5 && (
              <StaleIndicator minutes={staleMinutes} />
            )}
            {state === 'live' && <LiveIndicator />}
            {isOutlier && (
              <span className="px-2 py-0.5 bg-amber-100/80 dark:bg-amber-500/15 border border-amber-200/50 dark:border-amber-500/25 text-amber-700 dark:text-amber-400 rounded text-xs font-bold uppercase tracking-wider whitespace-nowrap">
                Anomaly
              </span>
            )}
            {/* Period Selector */}
            <PeriodSelectorComp />
          </div>
        </div>

        {/* Zone 2: Primary Metric (60px) */}
        <div className="flex flex-col gap-1 mb-5 relative z-10" role="status" aria-label={ariaLabel || `${title}: ${formatValue(value, format)}`}>
          <div className="flex items-baseline gap-2">
            <div className="text-4xl font-bold text-foreground tracking-tight tabular-nums leading-tight">
              {formatValue(value, format)}
            </div>

            {/* Delta Badge - New Design */}
            {delta && (
              <div className="flex items-center">
                <div className={cn(
                  "inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold transition-all duration-200",
                  "backdrop-blur-sm border",
                  delta.direction === 'up' && !higherIsBetter
                    ? "bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400"
                    : delta.direction === 'up' && higherIsBetter
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                      : delta.direction === 'down' && !higherIsBetter
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
                        : delta.direction === 'down' && higherIsBetter
                          ? "bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400"
                          : "bg-slate-500/10 border-slate-500/30 text-slate-600 dark:text-slate-400"
                )}>
                  <DeltaIcon className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>{Math.abs(delta.percentChange).toFixed(1)}%</span>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground/70 font-medium mt-1">
            <span className="font-mono bg-muted/40 px-1.5 py-0.5 rounded text-[11px]">{formatFullPrecision(value, format)}</span>
            {recordCount != null && (
              <>
                <span className="opacity-50">•</span>
                <span>{recordCount.toLocaleString()} records</span>
              </>
            )}
          </div>
        </div>

        {/* Zone 3: Comparison Label */}
        {delta && (
          <div className="text-xs text-muted-foreground/70 mb-3 relative z-10">
            {comparisonLabel || "vs last period"}
          </div>
        )}

        {/* Progress Bar (NEW) */}
        {achievementPercent !== undefined && achievementPercent !== null && (
          <div className="mb-4 relative z-10">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-muted-foreground/70">{achievementPercent.toFixed(0)}% of target</span>
              <StatusBadge status={periodStatus} theme={theme} />
            </div>
            <ProgressBar percent={achievementPercent} status={periodStatus} theme={theme} />
          </div>
        )}

        {/* Zone 4: Secondary Content */}
        <div className="flex-grow flex flex-col justify-end gap-3 relative z-10">
          {benchmarkText && (
            <div className="text-xs text-muted-foreground/70 py-2 px-3 bg-muted/30 rounded-lg border border-border/50">
              {benchmarkText}
            </div>
          )}

          {targetValue && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground/70">{targetLabel}</span>
              <span className="font-semibold text-foreground">{targetValue}</span>
            </div>
          )}

          {aiSuggestion && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onAIClick?.()
              }}
              className="text-xs flex items-start text-left gap-2 p-2 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-500/10 rounded-lg transition-all focus:outline-none focus:ring-1 focus:ring-cyan-500/50 group"
            >
              <Lightbulb className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 opacity-60 group-hover:opacity-100" />
              <span className="leading-snug line-clamp-2">{aiSuggestion}</span>
            </button>
          )}

          {/* Enterprise Action Prompt - "Ask DataSage ↗" chip */}
          {actionPrompt && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onAIClick?.()
              }}
              className="text-xs flex items-center gap-1.5 px-3 py-1.5 text-teal-600 dark:text-teal-400 bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/30 rounded-lg transition-all focus:outline-none focus:ring-1 focus:ring-teal-500/50"
            >
              <span className="leading-snug line-clamp-1">{actionPrompt}</span>
              <span className="text-[10px] font-bold ml-1">↗</span>
            </button>
          )}
        </div>

        {/* Footer with Target and Status (NEW) */}
        {!achievementPercent && (targetValue || periodStatus) && (
          <div className={cn(
            "flex justify-between items-center pt-4 mt-auto border-t",
            isDark ? "border-pearl/5" : "border-slate-100/50"
          )}>
            {targetValue && !achievementPercent && (
              <div className={isDark ? "text-pearl-muted" : "text-slate-400"}>
                <span className="text-xs">{targetLabel}: </span>
                <span className={cn("text-xs font-semibold", isDark ? "text-pearl" : "text-slate-600")}>
                  {targetValue}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Sparkline (absolute positioned) */}
        {normalizedSparkline && normalizedSparkline.length > 2 && (
          <div className="absolute bottom-4 right-4 opacity-50 hover:opacity-100 transition-all duration-200 pointer-events-none">
            <MiniSparkline data={normalizedSparkline} color={style.hex} width={100} height={40} />
          </div>
        )}
      </div>
    </motion.div>
  )
})

EnterpriseKpiCard.displayName = 'EnterpriseKpiCard'

export { StatusBadge, ProgressBar };
export default EnterpriseKpiCard
