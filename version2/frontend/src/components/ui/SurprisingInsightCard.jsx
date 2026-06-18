'use client'

import React, { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Lightbulb, AlertTriangle, AlertCircle,
  Activity,
  Search, Zap, GitBranch, Layers, Target,
  Share2, ChevronDown, ChevronUp, RefreshCw,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ─── Severity Config ─────────────────────────────────────────────────────────

const SEVERITY_CONFIG = {
  critical: {
    icon: AlertCircle,
    label: 'Critical',
    accent: 'border-l-red-500',
    badge: 'bg-red-100 dark:bg-red-500/15 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20',
    iconColor: 'text-red-500',
    glow: 'rgba(239, 68, 68, 0.08)',
  },
  warning: {
    icon: AlertTriangle,
    label: 'Warning',
    accent: 'border-l-amber-500',
    badge: 'bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20',
    iconColor: 'text-amber-500',
    glow: 'rgba(245, 158, 11, 0.08)',
  },
  info: {
    icon: Lightbulb,
    label: 'Insight',
    accent: 'border-l-blue-500',
    badge: 'bg-blue-100 dark:bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20',
    iconColor: 'text-blue-500',
    glow: 'rgba(59, 130, 246, 0.06)',
  },
}

// ─── Insight Type Icons ──────────────────────────────────────────────────────

const TYPE_ICONS = {
  correlation: Share2,
  ratio: GitBranch,
  simpson: Layers,
  concentration: Target,
  segment: Activity,
}

const TYPE_LABELS = {
  correlation: 'Correlation Anomaly',
  ratio: 'Hidden Ratio',
  simpson: "Simpson's Paradox",
  concentration: 'Concentration Risk',
  segment: 'Segment Decomposition',
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const truncate = (str, max = 60) =>
  str?.length > max ? str.slice(0, max) + '...' : str

// ─── Sub-Insights List ───────────────────────────────────────────────────────

const SubInsightList = ({ insights, expanded }) => {
  if (!insights?.length || !expanded) return null

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="overflow-hidden"
    >
      <div className="pt-2 space-y-1.5">
        {insights.map((item, idx) => (
          <div
            key={idx}
            className="flex items-start gap-2 px-3 py-2 rounded-lg bg-muted/30 text-xs"
          >
            <span className="text-[10px] mt-0.5 shrink-0 text-muted-foreground/50">
              {idx + 1}.
            </span>
            <span className="text-muted-foreground leading-relaxed">{item}</span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

// ─── Evidence Details ────────────────────────────────────────────────────────

const EvidenceDetails = ({ evidence, expanded }) => {
  if (!evidence || !expanded) return null

  const entries = Object.entries(evidence).filter(
    ([k]) => !['magnitude'].includes(k) && evidence[k] != null
  )
  if (!entries.length) return null

  const formatKey = (k) =>
    k.replace(/_/g, ' ')
      .replace(/\bpct\b/i, '%')
      .replace(/\bp1\b|\bp2\b/gi, (m) => m.toUpperCase())
      .replace(/\b(^| )\w/g, (c) => c.toUpperCase())

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="overflow-hidden"
    >
      <div className="mt-2 pt-2 border-t border-border/40">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground/50 mb-1.5">
          Evidence
        </p>
        <div className="grid grid-cols-2 gap-1.5">
          {entries.map(([key, val]) => (
            <div
              key={key}
              className="flex items-center justify-between px-2.5 py-1.5 rounded-md bg-muted/20 text-xs"
            >
              <span className="text-muted-foreground/70">{formatKey(key)}</span>
              <span className="font-medium tabular-nums text-foreground">
                {typeof val === 'number'
                  ? val > 1000
                    ? val.toLocaleString()
                    : val % 1 === 0
                      ? val
                      : val.toFixed(2)
                  : String(val)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

// ─── Skeleton State ──────────────────────────────────────────────────────────

const SkeletonInsightCard = ({ animationDelay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.45, delay: animationDelay, ease: [0.16, 1, 0.3, 1] }}
    className="h-full"
  >
    <div className="relative h-full flex flex-col rounded-xl bg-card overflow-hidden border border-border/50 shadow-sm">
      <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent z-20 pointer-events-none" />
      <div className="flex flex-col gap-3 p-4 flex-1 animate-pulse">
        {/* Header skeleton */}
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-muted/50" />
          <div className="w-20 h-4 rounded bg-muted/50" />
          <div className="w-14 h-4 rounded bg-muted/30" />
        </div>
        {/* Title skeleton */}
        <div className="space-y-1.5">
          <div className="w-3/4 h-4 rounded bg-muted/40" />
          <div className="w-1/2 h-4 rounded bg-muted/30" />
        </div>
        {/* Description skeleton */}
        <div className="space-y-1.5 flex-1">
          <div className="w-full h-3 rounded bg-muted/30" />
          <div className="w-full h-3 rounded bg-muted/30" />
          <div className="w-2/3 h-3 rounded bg-muted/25" />
        </div>
        {/* Metric pills skeleton */}
        <div className="flex gap-1.5 mt-auto pt-1">
          <div className="w-14 h-4 rounded bg-muted/30" />
          <div className="w-16 h-4 rounded bg-muted/25" />
        </div>
      </div>
    </div>
  </motion.div>
)

// ─── Error State ─────────────────────────────────────────────────────────────

const ErrorInsightCard = ({
  title = 'Insight unavailable',
  errorMessage = 'Failed to load insight data',
  onRetry,
  animationDelay = 0,
}) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.45, delay: animationDelay, ease: [0.16, 1, 0.3, 1] }}
    className="h-full"
  >
    <div className="relative h-full flex flex-col rounded-xl bg-card overflow-hidden border border-red-500/20 shadow-sm border-l-red-500"
         style={{ borderLeftWidth: '3px' }}
    >
      <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent z-20 pointer-events-none" />
      <div className="flex flex-col items-center justify-center gap-3 p-4 flex-1 text-center">
        <div className="p-2 rounded-lg bg-red-100 dark:bg-red-500/10">
          <AlertCircle className="w-5 h-5 text-red-500" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="text-xs text-muted-foreground">{errorMessage}</p>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/5 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-500/15 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        )}
      </div>
    </div>
  </motion.div>
)

// ─── Empty State ─────────────────────────────────────────────────────────────

const EmptyInsightCard = ({
  title = 'No insights yet',
  reason = 'The surprising patterns engine found no hidden patterns in this data',
  animationDelay = 0,
}) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.45, delay: animationDelay, ease: [0.16, 1, 0.3, 1] }}
    className="h-full"
  >
    <div className="relative h-full flex flex-col rounded-xl bg-card overflow-hidden border border-border/50 shadow-sm border-l-muted"
         style={{ borderLeftWidth: '3px' }}
    >
      <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent z-20 pointer-events-none" />
      <div className="flex flex-col items-center justify-center gap-3 p-4 flex-1 text-center">
        <div className="p-2 rounded-lg bg-muted/30">
          <Search className="w-5 h-5 text-muted-foreground/50" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="text-xs text-muted-foreground/70 max-w-[200px]">{reason}</p>
        </div>
      </div>
    </div>
  </motion.div>
)

// ─── Main Insight Card ───────────────────────────────────────────────────────

const SurprisingInsightCard = ({
  // Display props
  title,
  description,
  insightType = 'correlation',
  severity = 'info',
  impact,
  metrics = [],
  tags = [],
  evidence = {},
  plainEnglish,
  category,
  animationDelay = 0,

  // State props
  status = 'ready', // 'loading' | 'error' | 'empty' | 'ready'
  errorMessage,
  onRetry,
}) => {
  const [expanded, setExpanded] = useState(false)

  // ── State-based early returns ────────────────────────────────────────────
  if (status === 'loading') {
    return <SkeletonInsightCard animationDelay={animationDelay} />
  }

  if (status === 'error') {
    return (
      <ErrorInsightCard
        title={title || 'Insight unavailable'}
        errorMessage={errorMessage || 'Failed to load insight data'}
        onRetry={onRetry}
        animationDelay={animationDelay}
      />
    )
  }

  if (status === 'empty') {
    return (
      <EmptyInsightCard
        title={title || 'No insights yet'}
        reason={typeof description === 'string' ? description : 'The surprising patterns engine found no hidden patterns in this data'}
        animationDelay={animationDelay}
      />
    )
  }

  // ── Guard: missing content in ready state ────────────────────────────────
  if (!title && !description) {
    return (
      <EmptyInsightCard
        title="No insight data"
        reason="No insight data was returned for this card"
        animationDelay={animationDelay}
      />
    )
  }

  // ── Render ───────────────────────────────────────────────────────────────
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.info
  const SeverityIcon = config.icon
  const TypeIcon = TYPE_ICONS[insightType] || Lightbulb
  const typeLabel = TYPE_LABELS[insightType] || insightType

  const displayText = plainEnglish || description || ''
  const hasExtra = impact || Object.keys(evidence).length > 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: animationDelay, ease: [0.16, 1, 0.3, 1] }}
      className="h-full"
    >
      <div
        className={cn(
          'relative h-full flex flex-col rounded-xl bg-card overflow-hidden',
          'shadow-[0_4px_6px_-1px_rgba(0,0,0,0.1),0_2px_4px_-1px_rgba(0,0,0,0.06)]',
          'border border-border/50 transition-all duration-200',
          expanded && 'shadow-[0_8px_30px_rgba(0,0,0,0.12)]',
          config.accent,
        )}
        style={{ borderLeftWidth: '3px' }}
      >
        {/* Top glare */}
        <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent z-20 pointer-events-none" />

        {/* Content */}
        <div className="flex flex-col gap-2.5 p-4 flex-1">
          {/* Header row */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              {/* Type icon */}
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                style={{ background: config.glow }}
              >
                <TypeIcon className={cn('w-3.5 h-3.5', config.iconColor)} />
              </div>
              {/* Tags */}
              <div className="flex items-center gap-1.5 flex-wrap min-w-0">
                <span
                  className={cn(
                    'text-[10px] font-medium px-1.5 py-0.5 rounded border',
                    config.badge
                  )}
                >
                  {typeLabel}
                </span>
                {tags.slice(0, 2).map((tag, i) => (
                  <span
                    key={i}
                    className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-muted/40 text-muted-foreground border-border/50"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            {/* Expand / collapse */}
            {hasExtra && (
              <button
                type="button"
                onClick={() => setExpanded((e) => !e)}
                className="shrink-0 flex items-center justify-center w-5 h-5 rounded hover:bg-muted/60 transition-colors"
                aria-label={expanded ? 'Collapse details' : 'Expand details'}
              >
                {expanded ? (
                  <ChevronUp className="w-3.5 h-3.5 text-muted-foreground/50" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 text-muted-foreground/50" />
                )}
              </button>
            )}
          </div>

          {/* Title */}
          <h4 className="text-sm font-semibold text-foreground leading-snug">
            {title}
          </h4>

          {/* Description */}
          <p className="text-[13px] leading-relaxed text-muted-foreground flex-1">
            {expanded ? displayText : truncate(displayText, 140)}
          </p>

          {/* Impact */}
          {impact && (
            <div className="flex items-start gap-1.5">
              <Zap className="w-3 h-3 mt-0.5 shrink-0 text-muted-foreground/40" />
              <p className="text-[11px] leading-relaxed text-muted-foreground/70">
                {impact}
              </p>
            </div>
          )}

          {/* Expanded sections */}
          <EvidenceDetails evidence={evidence} expanded={expanded} />

          {/* Metrics used */}
          {metrics.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap mt-auto pt-1">
              <span className="text-[10px] text-muted-foreground/40 uppercase tracking-wider">
                Metrics:
              </span>
              {metrics.map((m, i) => (
                <span
                  key={i}
                  className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted/40 text-muted-foreground border border-border/30"
                >
                  {m.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export {
  SurprisingInsightCard,
  SkeletonInsightCard,
  ErrorInsightCard,
  EmptyInsightCard,
}
export default SurprisingInsightCard
