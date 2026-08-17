import React from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, Target } from 'lucide-react';
import MetricCard from './MetricCard';

/**
 * MetricStrip — responsive grid of MetricCard components.
 *
 * Handles the collective states:
 *  - loading with skeleton fallback
 *  - empty (no metrics)
 *  - error banner
 *  - healthy metric grid
 *
 * Props:
 *  - metrics : Array<MetricCardProps>
 *  - loading : boolean
 *  - error   : string | null
 *  - onRefresh : function — called when user clicks Refresh
 *  - onMetricClick : function(metric, index) — drill-down handler
 *  - maxCards : number (default 6)
 *  - title   : string (default "Key Metrics")
 */
const MetricStrip = ({
  metrics = [],
  loading = false,
  error = null,
  onRefresh,
  onMetricClick,
  maxCards = 6,
  title = 'Key Metrics',
}) => {
  // Loading state — show skeleton grid
  if (loading && metrics.length === 0) {
    return (
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
              <Target className="w-3.5 h-3.5 text-white/40" />
            </div>
            <span className="text-sm font-semibold text-white/80">{title}</span>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-4">
          {Array.from({ length: Math.min(maxCards, 6) }).map((_, i) => (
            <MetricCard key={`skel-${i}`} title="" value={null} loading />
          ))}
        </div>
      </section>
    );
  }

  // Error state with no data
  if (error && metrics.length === 0) {
    return (
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
              <Target className="w-3.5 h-3.5 text-white/40" />
            </div>
            <span className="text-sm font-semibold text-white/80">{title}</span>
          </div>
        </div>
        <div className="p-6 rounded-2xl bg-red-500/5 border border-red-500/20 text-center">
          <p className="text-sm text-red-400/70">{error}</p>
          {onRefresh && (
            <button onClick={onRefresh} className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-400/70 border border-red-500/20 hover:bg-red-500/10 transition-colors">
              <RefreshCw className="w-3 h-3" />
              Retry
            </button>
          )}
        </div>
      </section>
    );
  }

  // Empty state
  if (!loading && metrics.length === 0) {
    return (
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
              <Target className="w-3.5 h-3.5 text-white/40" />
            </div>
            <span className="text-sm font-semibold text-white/80">{title}</span>
          </div>
        </div>
        <div className="p-8 rounded-2xl bg-white/[0.02] border border-white/[0.06] text-center">
          <Target className="w-8 h-8 mx-auto mb-3 text-white/15" />
          <p className="text-sm text-white/40">No metrics available</p>
          <p className="text-xs text-white/20 mt-1">KPIs will appear here once generated</p>
        </div>
      </section>
    );
  }

  // Live data
  const visibleMetrics = metrics.slice(0, maxCards);

  return (
    <section className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/15">
            <Target className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <span className="text-sm font-semibold text-white/80">{title}</span>
          <span className="px-1.5 py-0.5 rounded-md text-xs font-medium tabular-nums bg-white/5 text-white/40 border border-white/[0.06]">
            {visibleMetrics.length}
          </span>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-white/40 border border-white/[0.06] hover:bg-white/5 hover:text-white/60 transition-all disabled:opacity-30"
            title="Refresh metrics"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        )}
      </div>

      {/* Card grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {visibleMetrics.map((metric, index) => (
          <motion.div
            key={metric.id || metric.title || index}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          >
            <MetricCard
              {...metric}
              onClick={onMetricClick ? () => onMetricClick(metric, index) : undefined}
            />
          </motion.div>
        ))}
      </div>
    </section>
  );
};

export default MetricStrip;
