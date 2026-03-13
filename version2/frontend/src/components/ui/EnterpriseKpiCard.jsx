import React, { useMemo, useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import {
    TrendingUp, TrendingDown, Minus,
    DollarSign, Users, FileText, BarChart3,
    Activity, Target, Zap, Database, Package,
    ShoppingCart, Percent, Hash, Calendar,
    MoreHorizontal, MessageSquare, Copy, Info, Lightbulb
} from 'lucide-react';
import { cn } from '../../lib/utils';
const ICON_MAP = {
    DollarSign, Users, FileText, BarChart3, Activity,
    Target, Zap, Database, Package, ShoppingCart,
    Percent, Hash, Calendar, TrendingUp,
    MoreHorizontal, MessageSquare, Copy, Info, Lightbulb
};

const NEUTRAL_ACCENTS = [
    { border: 'border-l-cyan-500', text: 'text-cyan-400', hex: '#06b6d4', bg: 'bg-cyan-500/10' },
    { border: 'border-l-violet-500', text: 'text-violet-400', hex: '#8b5cf6', bg: 'bg-violet-500/10' },
    { border: 'border-l-emerald-500', text: 'text-emerald-400', hex: '#10b981', bg: 'bg-emerald-500/10' },
    { border: 'border-l-amber-500', text: 'text-amber-400', hex: '#f59e0b', bg: 'bg-amber-500/10' },
    { border: 'border-l-rose-500', text: 'text-rose-400', hex: '#f43f5e', bg: 'bg-rose-500/10' },
];

const hashString = (value = '') => {
    let hash = 0;
    for (let i = 0; i < value.length; i += 1) {
        hash = (hash << 5) - hash + value.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash);
};

// ─── Shared Tooltip Component ───
const InfoTooltip = ({ content }) => {
    const [show, setShow] = useState(false);
    return (
        <div
            className="relative inline-flex items-center"
            onPointerEnter={() => setShow(true)}
            onPointerLeave={() => setShow(false)}
        >
            <button
                className="text-slate-500 hover:text-slate-400 focus:outline-none"
                aria-label="More information"
            >
                <Info className="w-3.5 h-3.5" />
            </button>
            <AnimatePresence>
                {show && (
                    <motion.div
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                        transition={{ duration: 0.15 }}
                        className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 bg-slate-800 border border-slate-700 text-white text-[11px] rounded shadow-xl whitespace-nowrap max-w-xs"
                    >
                        {content}
                        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

// ─── Value Formatter ───
const formatValue = (value, format = 'number') => {
    if (value === null || value === undefined || value === 'N/A') return 'N/A';

    const num = typeof value === 'string' ? parseFloat(value.replace(/[^0-9.-]/g, '')) : value;
    if (isNaN(num)) return String(value);

    switch (format) {
        case 'currency':
            if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
            if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
            if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(1)}K`;
            return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(num);
        case 'percentage':
            return `${num.toFixed(1)}%`;
        case 'integer':
            if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
            if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
            if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
            return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(num);
        default:
            if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
            if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
            if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
            return new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(num);
    }
};

// ─── Subtle SVG Sparkline (Stripe Style) ───
const MiniSparkline = ({ data, color = '#10b981', height = 48, width = 120 }) => {
    if (!data || data.length < 2) return null;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padding = 4;

    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * (width - padding * 2) + padding;
        const y = height - padding - ((v - min) / range) * (height - padding * 2);
        return `${x},${y}`;
    });

    const pathD = `M ${points.join(' L ')}`;
    const areaD = `${pathD} L ${width - padding},${height} L ${padding},${height} Z`;
    const gradId = `sparkGrad-${color.replace('#', '')}-${Math.random().toString(36).substr(2, 5)}`;

    return (
        <svg width={width} height={height} className="overflow-visible drop-shadow-sm">
            <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.2" />
                    <stop offset="100%" stopColor={color} stopOpacity="0.0" />
                </linearGradient>
            </defs>
            <path d={areaD} fill={`url(#${gradId})`} />
            <path d={pathD} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx={width - padding} cy={height - padding - ((data[data.length - 1] - min) / range) * (height - padding * 2)} r="3" fill={color} className="shadow-sm" />
        </svg>
    );
};

// ─── Main Component ───
const EnterpriseKpiCard = ({
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
    fallbackReason
}) => {

    // 1. AUTO-DETECT: Is higher better? (Revenue = True, Costs = False)
    const isExpense = /cost|discount|churn|expense|fee|tax|loss/i.test(title);
    const higherIsBetter = !isExpense;

    // 2. Calculate Math Delta
    const delta = useMemo(() => {
        if (deltaPercent !== null && deltaPercent !== undefined) {
            return { percentChange: deltaPercent, direction: deltaPercent > 0 ? 'up' : deltaPercent < 0 ? 'down' : 'neutral' };
        }
        if (comparisonValue && comparisonValue !== 0) {
            const currentNum = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''));
            const prevNum = typeof comparisonValue === 'number' ? comparisonValue : parseFloat(String(comparisonValue).replace(/[^0-9.-]/g, ''));
            if (!isNaN(currentNum) && !isNaN(prevNum)) {
                const pct = ((currentNum - prevNum) / Math.abs(prevNum)) * 100;
                return { percentChange: pct, direction: pct > 0 ? 'up' : pct < 0 ? 'down' : 'neutral' };
            }
        }
        return null;
    }, [value, comparisonValue, deltaPercent]);

    // 3. Apply Business Status (The Secret Sauce)
    const status = useMemo(() => {
        if (!delta || delta.direction === 'neutral') return 'neutral';

        if (higherIsBetter) {
            return delta.direction === 'up' ? 'success' : 'critical';
        } else {
            return delta.direction === 'down' ? 'success' : 'critical'; // Costs going down = success!
        }
    }, [delta, higherIsBetter]);

    const STATUS_COLORS = {
        success: { border: 'border-l-emerald-500', text: 'text-emerald-400', hex: '#10b981', bg: 'bg-emerald-500/10' },
        critical: { border: 'border-l-red-500', text: 'text-red-400', hex: '#ef4444', bg: 'bg-red-500/10' },
        neutral: { border: 'border-l-slate-600', text: 'text-slate-400', hex: '#94a3b8', bg: 'bg-slate-500/10' }
    };

    const neutralAccent = useMemo(() => {
        const idx = hashString(`${title}:${icon}`) % NEUTRAL_ACCENTS.length;
        return NEUTRAL_ACCENTS[idx];
    }, [title, icon]);

    const style = status === 'neutral' ? neutralAccent : STATUS_COLORS[status];
    const IconComponent = ICON_MAP[icon] || BarChart3;
    const DeltaIcon = delta?.direction === 'up' ? TrendingUp : delta?.direction === 'down' ? TrendingDown : Minus;

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: animationDelay }}
            className="h-full"
        >
            <div className={cn(
                "relative h-full flex flex-col justify-between p-5 rounded-2xl border-l-4 bg-[var(--surface-1)] border-[var(--surface-border)] overflow-hidden transition-all duration-300",
                "hover:shadow-lg hover:border-[var(--surface-border-hover)] hover:-translate-y-1",
                style.border
            )}>
                {/* Header Row */}
                <div className="flex items-center justify-between mb-4 relative z-10">
                    <div className="flex items-center gap-2.5">
                        <div className={cn("w-8 h-8 rounded-xl flex items-center justify-center", style.bg)}>
                            <IconComponent className={cn("w-4 h-4", style.text)} />
                        </div>
                        <div className="flex items-center gap-1.5">
                            <span className="text-sm font-semibold text-[var(--page-muted)] uppercase tracking-wider">{title}</span>
                            {definition && <InfoTooltip content={definition} />}
                            {fallbackReason && (
                                <div className="p-0.5 rounded-full bg-amber-500/10 text-amber-500">
                                    <InfoTooltip content={`AI Fallback: ${fallbackReason}`} />
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Data Row */}
                <div className="relative z-10 flex items-end justify-between">
                    <div>
                        <div className="text-3xl font-extrabold text-[var(--page-text)] tracking-tight tabular-nums leading-none">
                            {formatValue(value, format)}
                        </div>

                        {delta ? (
                            <div className="flex items-center gap-2 mt-3">
                                <span className={cn("flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-md bg-opacity-10", style.bg, style.text)}>
                                    <DeltaIcon className="w-3 h-3" />
                                    {Math.abs(delta.percentChange).toFixed(1)}%
                                </span>
                                <span className="text-xs font-medium text-[var(--page-muted)]">{comparisonLabel || "vs last period"}</span>
                            </div>
                        ) : recordCount && !benchmarkText && !aiSuggestion ? (
                            <div className="text-xs font-medium text-[var(--page-muted)] mt-3">
                                {recordCount.toLocaleString()} records analyzed
                            </div>
                        ) : null}

                        {/* Benchmark & Outlier Row */}
                        {(benchmarkText || isOutlier) && (
                            <div className="flex items-center gap-2 mt-3">
                                {benchmarkText && <span className="text-xs font-medium text-[var(--page-muted)]">{benchmarkText}</span>}
                                {isOutlier && (
                                    <span className="px-1.5 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-500 rounded text-[10px] font-bold uppercase tracking-wider">
                                        Anomaly
                                    </span>
                                )}
                            </div>
                        )}

                        {/* AI Insight Row */}
                        {aiSuggestion && (
                            <button
                                onClick={onAIClick || (() => window.dispatchEvent(new CustomEvent('open-chat-with-query', { detail: { query: `Tell me more about this suggestion: ${aiSuggestion}` } })))}
                                className="mt-2.5 flex items-start text-left gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 transition-colors focus:outline-none"
                            >
                                <Lightbulb className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                                <span className="leading-snug">{aiSuggestion}</span>
                            </button>
                        )}
                    </div>
                </div>

                {/* Absolute Sparkline (Positioned cleanly in bottom right) */}
                {sparklineData && sparklineData.length > 2 && (
                    <div className="absolute bottom-0 right-0 opacity-80 pointer-events-none transform translate-y-2 translate-x-2">
                        <MiniSparkline data={sparklineData} color={style.hex} width={140} height={60} />
                    </div>
                )}
            </div>
        </motion.div>
    );
};

export default EnterpriseKpiCard;
