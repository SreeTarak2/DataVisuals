import React, { useState, useCallback, useRef } from 'react';
import {
    BarChart3, TrendingUp, AlertTriangle, Activity, Link2, PieChart,
    GitCompare, Target, Sparkles, RefreshCw, Info, ChevronDown
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../../lib/utils';
import PlotlyChart from './PlotlyChart';

const BADGE_ICONS = {
    'KEY FINDING': Target,
    'ANOMALY DETECTED': AlertTriangle,
    'STRONG TREND': TrendingUp,
    'RELATIONSHIP': Link2,
    'DISTRIBUTION': Activity,
    'COMPOSITION': PieChart,
    'COMPARISON': GitCompare,
};

const BADGE_COLORS = {
    'KEY FINDING': 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    'ANOMALY DETECTED': 'bg-red-500/20 text-red-400 border-red-500/30',
    'STRONG TREND': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    'RELATIONSHIP': 'bg-violet-500/20 text-violet-400 border-violet-500/30',
    'DISTRIBUTION': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    'COMPOSITION': 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    'COMPARISON': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
};

function deriveDisplayData(chartData, chartConfig) {
    if (!chartData) return null;

    const explanation = chartData.explanation || '';
    const confidence = chartData.confidence || 0;
    const meta = chartData.metadata || {};
    const pi = chartData.point_intelligence || {};
    const xField = chartConfig?.encoding?.x?.field || pi.x_label || 'x';
    const yField = chartConfig?.encoding?.y?.field || pi.y_label || 'y';
    const chartType = chartConfig?.chartType || chartData.type || 'bar';
    const piStats = pi.stats || {};

    const titleInsight = explanation || `${yField} by ${xField}`;

    let badgeType = 'KEY FINDING';
    if (chartData.badge_type) badgeType = chartData.badge_type;
    else if (['line', 'area'].includes(chartType)) badgeType = 'STRONG TREND';
    else if (['scatter', 'bubble'].includes(chartType)) badgeType = 'RELATIONSHIP';
    else if (['pie', 'donut', 'treemap', 'sunburst', 'funnel'].includes(chartType)) badgeType = 'COMPOSITION';
    else if (['bar', 'grouped_bar', 'waterfall'].includes(chartType)) badgeType = 'COMPARISON';
    else if (piStats.std && piStats.mean && piStats.std / piStats.mean > 0.5) badgeType = 'DISTRIBUTION';

    const rowCount = meta.rows_used || meta.row_count;
    const subtitleScope = chartData.subtitle_scope
        || (rowCount ? `${rowCount.toLocaleString()} records` : null);

    const fmt = (n) => typeof n === 'number'
        ? n.toLocaleString(undefined, { maximumFractionDigits: 2 })
        : String(n);

    const keyNumbers = chartData.key_numbers?.length
        ? chartData.key_numbers
        : piStats.mean !== undefined
            ? [
                { label: 'Mean', value: fmt(piStats.mean) },
                { label: 'Peak', value: fmt(piStats.max) },
                { label: 'Floor', value: fmt(piStats.min) },
                { label: 'Std Dev', value: fmt(piStats.std) },
            ].filter(k => k.value !== 'undefined')
            : [];

    return { titleInsight, subtitleScope, badgeType, keyNumbers, confidence, meta, chartType };
}

/* ────────────────────────────────────────────────────────────────────────── */

const ChartCanvas = ({ chartData, chartConfig, loading, onAskAI, onReset }) => {
    const [showStats, setShowStats] = useState(false);
    const clickTimeout = useRef(null);

    const handlePointClick = useCallback((clickData) => {
        if (clickTimeout.current) {
            clearTimeout(clickTimeout.current);
            clickTimeout.current = null;

            const xLabel = clickData.x !== null ? String(clickData.x) : '';
            const yLabel = clickData.y !== null ? (typeof clickData.y === 'number' ? clickData.y.toLocaleString() : String(clickData.y)) : '';
            const series = clickData.seriesName ? ` (${clickData.seriesName})` : '';
            const chartTitle = chartData?.title || 'the chart';

            const query = `I clicked on a specific data point in "${chartTitle}" where ${xLabel} = ${yLabel}${series}. Can you tell me more about what might be driving this specific point or if it represents an anomaly?`;

            window.dispatchEvent(new CustomEvent('open-chat-with-query', { detail: { query } }));
            return;
        }

        clickTimeout.current = setTimeout(() => {
            clickTimeout.current = null;
            // Native tooltips handle single clicks
        }, 250);
    }, [chartData?.title]);

    /* ── Empty State ──────────────────────────────────────────────────── */
    if (!chartConfig.encoding?.x?.field && !chartData) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="text-center max-w-xs px-10 py-12 rounded-2xl bg-surface border border-border">
                    <div className="w-14 h-14 mx-auto mb-6 rounded-xl bg-accent-primary-light flex items-center justify-center">
                        <BarChart3 size={24} className="text-accent-primary" strokeWidth={2.5} />
                    </div>
                    <h3 className="text-base font-black mb-2 text-header">Select axes to begin</h3>
                    <p className="text-[12px] text-secondary leading-relaxed">
                        Pick a Dimension (X) and Value (Y) from the toolbar below.
                    </p>
                </div>
            </div>
        );
    }

    /* ── Loading State ────────────────────────────────────────────────── */
    if (loading) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                    <div className="relative w-16 h-16 mx-auto mb-4">
                        <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }}
                            className="absolute inset-0 rounded-xl border-2 border-accent-primary/10 border-t-accent-primary"
                        />
                        <Sparkles size={20} className="absolute inset-0 m-auto text-accent-primary" />
                    </div>
                    {/* skeleton bars */}
                    <div className="flex items-end gap-1.5 justify-center h-12 mt-3">
                        {[55, 80, 40, 95, 68, 50, 85, 72].map((h, i) => (
                            <div
                                key={i}
                                className="w-5 rounded-t chart-skeleton"
                                style={{ height: `${h}%`, animationDelay: `${i * 0.08}s` }}
                            />
                        ))}
                    </div>
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-accent-primary mt-3">
                        Rendering
                    </p>
                </div>
            </div>
        );
    }

    /* ── Error / No data ──────────────────────────────────────────────── */
    if (!chartData || !chartData.traces) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="text-center max-w-xs p-8 rounded-2xl bg-surface border border-border">
                    <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-red-500/10 flex items-center justify-center">
                        <AlertTriangle size={22} className="text-red-400" />
                    </div>
                    <h3 className="text-sm font-black mb-2 text-header">No data returned</h3>
                    <p className="text-[12px] text-secondary mb-5 leading-relaxed">
                        This axis pairing produced no results. Try a different field or aggregation.
                    </p>
                    <button
                        onClick={onReset}
                        className="px-5 py-2 rounded-lg bg-accent-primary text-white text-[11px] font-black uppercase tracking-widest hover:bg-accent-primary-hover transition-all flex items-center gap-2 mx-auto"
                    >
                        <RefreshCw size={12} />
                        Reset Axes
                    </button>
                </div>
            </div>
        );
    }

    const display = deriveDisplayData(chartData, chartConfig);
    if (!display) return null;

    const { titleInsight, subtitleScope, badgeType, keyNumbers, confidence, meta } = display;
    const BadgeIcon = BADGE_ICONS[badgeType] || Target;
    const badgeColorClass = BADGE_COLORS[badgeType] || BADGE_COLORS['KEY FINDING'];

    /* ── Rendered: chart-first layout ────────────────────────────────── */
    return (
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">

            {/* ── Compact header strip ─────────────────────────────── */}
            <div className="shrink-0 flex items-center gap-3 px-4 pt-3 pb-2 border-b border-border/40 flex-wrap">
                {/* Badge */}
                <span className={cn(
                    'inline-flex items-center gap-1.5 px-2 py-1 rounded text-[9px] font-black uppercase tracking-[0.15em] border shrink-0',
                    badgeColorClass
                )}>
                    <BadgeIcon size={9} strokeWidth={3} />
                    {badgeType}
                </span>

                {/* Title — single line, truncated */}
                <p
                    className="flex-1 min-w-0 text-[13px] font-bold text-header truncate"
                    title={titleInsight}
                >
                    {titleInsight}
                </p>

                {/* Subtitle chips */}
                {subtitleScope && (
                    <span className="text-[11px] text-muted shrink-0 hidden sm:block">{subtitleScope}</span>
                )}
                {confidence > 0 && (
                    <span className="text-[10px] font-bold text-muted shrink-0 hidden sm:block">
                        {Math.round(confidence * 100)}% conf.
                    </span>
                )}

                {/* Stats toggle */}
                {keyNumbers.length > 0 && (
                    <button
                        onClick={() => setShowStats(v => !v)}
                        className={cn(
                            'shrink-0 flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold transition-colors',
                            showStats
                                ? 'bg-accent-primary/15 text-accent-primary'
                                : 'text-muted hover:text-header'
                        )}
                        title="Toggle stats"
                    >
                        <Info size={11} />
                        Stats
                        <ChevronDown size={10} className={`transition-transform ${showStats ? 'rotate-180' : ''}`} />
                    </button>
                )}

                {/* Deep Analysis */}
                <button
                    onClick={() => onAskAI?.()}
                    className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-primary/10 text-accent-primary text-[10px] font-black uppercase tracking-widest hover:bg-accent-primary hover:text-white transition-all"
                >
                    <Sparkles size={11} />
                    Analyze
                </button>
            </div>

            {/* ── Collapsible stats bar ─────────────────────────────── */}
            <AnimatePresence>
                {showStats && keyNumbers.length > 0 && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        className="shrink-0 overflow-hidden border-b border-border/40"
                    >
                        <div className="flex items-center gap-px bg-secondary/30">
                            {keyNumbers.slice(0, 6).map((item, idx) => (
                                <div
                                    key={idx}
                                    className="flex-1 px-3 py-2 border-r border-border/40 last:border-r-0"
                                >
                                    <div className="text-[9px] font-black text-muted uppercase tracking-widest mb-0.5">
                                        {item.label}
                                    </div>
                                    <div className="text-[14px] font-black text-header tabular-nums leading-none">
                                        {item.value}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── THE CHART — takes all remaining space ─────────────── */}
            {/* Use relative+absolute so Plotly gets a concrete pixel height */}
            <div className="flex-1 min-h-0 relative">
                <div className="absolute inset-0 p-2">
                    <PlotlyChart
                        data={chartData.traces}
                        chartType={chartConfig?.chartType || chartData.type || 'bar'}
                        layout={{
                            ...chartData.layout,
                            title: '',
                            height: undefined,
                            autosize: true,
                            paper_bgcolor: 'rgba(0,0,0,0)',
                            plot_bgcolor: 'rgba(0,0,0,0)',
                        }}
                        style={{ width: '100%', height: '100%' }}
                        onPointClick={handlePointClick}
                        pointIntelligence={chartData.point_intelligence}
                        chartTitle={chartData.title || ''}
                    />
                </div>
            </div>
        </div>
    );
};

export default ChartCanvas;
