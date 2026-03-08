/**
 * EnterpriseKpiCard Component
 *
 * Compact, enterprise-grade KPI card inspired by Stripe/Shopify dashboards.
 *
 * Features:
 * - Primary value callout with proper formatting (K/M/B abbreviations)
 * - Period-over-period delta with directional arrow
 * - Lightweight SVG sparkline (no Plotly dependency)
 * - Three-dot context menu (Investigate / Copy / Export)
 * - Optional top-values breakdown list
 * - Goal progress tracking with visual bar
 * - Status-based accent colors
 * - Compact ~140px height, reference-image style
 */

import React, { useMemo, useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import {
    TrendingUp, TrendingDown, Minus,
    DollarSign, Users, FileText, BarChart3,
    Activity, Target, Zap, Database, Package,
    ShoppingCart, Percent, Hash, Calendar,
    MoreHorizontal, MessageSquare, Copy, Download
} from 'lucide-react';
import { cn } from '../../lib/utils';

// Icon mapping
const ICON_MAP = {
    DollarSign, Users, FileText, BarChart3, Activity,
    Target, Zap, Database, Package, ShoppingCart,
    Percent, Hash, Calendar, TrendingUp
};

// Status color configurations
const STATUS_CONFIG = {
    success: {
        border: 'border-l-emerald-500',
        bg: 'bg-emerald-500/10',
        text: 'text-emerald-400',
    },
    warning: {
        border: 'border-l-amber-500',
        bg: 'bg-amber-500/10',
        text: 'text-amber-400',
    },
    critical: {
        border: 'border-l-red-500',
        bg: 'bg-red-500/10',
        text: 'text-red-400',
    },
    neutral: {
        border: 'border-l-slate-600',
        bg: 'bg-slate-500/10',
        text: 'text-slate-400',
    }
};

// ─── Value Formatter ─────────────────────────────────────────────────────────

const formatValue = (value, format = 'number') => {
    if (value === null || value === undefined || value === 'N/A') return 'N/A';

    const num = typeof value === 'string' ? parseFloat(value.replace(/[^0-9.-]/g, '')) : value;
    if (isNaN(num)) return String(value);

    switch (format) {
        case 'currency':
            if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
            if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
            if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(1)}K`;
            return new Intl.NumberFormat('en-US', {
                style: 'currency', currency: 'USD',
                minimumFractionDigits: 0, maximumFractionDigits: 2
            }).format(num);
        case 'percentage':
            return `${num.toFixed(1)}%`;
        case 'decimal':
            return num.toFixed(2);
        case 'integer':
            if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
            if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
            if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
            return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(num);
        default:
            if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
            if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
            if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
            return new Intl.NumberFormat('en-US', {
                minimumFractionDigits: 0, maximumFractionDigits: 2
            }).format(num);
    }
};

// ─── SVG Sparkline ───────────────────────────────────────────────────────────

const MiniSparkline = ({ data, color = '#06b6d4', height = 40, width = 100 }) => {
    if (!data || data.length < 2) return null;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padding = 2;

    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * (width - padding * 2) + padding;
        const y = height - padding - ((v - min) / range) * (height - padding * 2);
        return `${x},${y}`;
    });

    const pathD = `M ${points.join(' L ')}`;
    const areaD = `${pathD} L ${width - padding},${height} L ${padding},${height} Z`;

    return (
        <svg width={width} height={height} className="overflow-visible">
            <defs>
                <linearGradient id={`sparkGrad-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.25" />
                    <stop offset="100%" stopColor={color} stopOpacity="0.02" />
                </linearGradient>
            </defs>
            <path d={areaD} fill={`url(#sparkGrad-${color.replace('#', '')})`} />
            <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            {/* Current value dot */}
            <circle
                cx={width - padding}
                cy={height - padding - ((data[data.length - 1] - min) / range) * (height - padding * 2)}
                r="2.5"
                fill={color}
            />
        </svg>
    );
};

const ContextMenu = ({ title, value, format, onInvestigate }) => {
    const [open, setOpen] = useState(false);
    const menuRef = useRef(null);

    const handleCopy = useCallback(() => {
        navigator.clipboard.writeText(`${title}: ${formatValue(value, format)}`);
        toast.success('Copied to clipboard', { duration: 1500 });
        setOpen(false);
    }, [title, value, format]);

    const handleInvestigate = useCallback(() => {
        onInvestigate?.();
        setOpen(false);
    }, [onInvestigate]);

    return (
        <div className="relative" ref={menuRef}>
            <button
                onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
                className="p-1 rounded-md text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:outline-none transition-colors duration-200"
                title="Options"
                aria-label={`Options for ${title}`}
                aria-expanded={open}
                aria-haspopup="menu"
            >
                <MoreHorizontal className="w-4 h-4" />
            </button>
            <AnimatePresence>
                {open && (
                    <>
                        <button
                            className="fixed inset-0 z-40 w-full h-full cursor-default focus-visible:outline-none"
                            onClick={(e) => { e.stopPropagation(); setOpen(false); }}
                            aria-label="Close menu"
                            tabIndex={-1}
                        />
                        <motion.div
                            role="menu"
                            initial={{ opacity: 0, scale: 0.95, y: -4 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: -4 }}
                            transition={{ duration: 0.12 }}
                            className="absolute right-0 top-8 z-50 w-44 py-1 rounded-lg bg-slate-800 border border-slate-700/80 shadow-xl shadow-black/40 origin-top-right"
                        >
                            <button
                                role="menuitem"
                                onClick={handleInvestigate}
                                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-300 hover:bg-slate-700/60 focus-visible:bg-slate-700/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-500 transition-colors duration-150"
                            >
                                <MessageSquare className="w-3.5 h-3.5 text-cyan-400" />
                                Investigate in Chat
                            </button>
                            <button
                                role="menuitem"
                                onClick={handleCopy}
                                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-300 hover:bg-slate-700/60 focus-visible:bg-slate-700/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-500 transition-colors duration-150"
                            >
                                <Copy className="w-3.5 h-3.5 text-slate-400" />
                                Copy Value
                            </button>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
};

// ─── Main Card ───────────────────────────────────────────────────────────────

const EnterpriseKpiCard = ({
    title,
    value,
    format = 'number',
    comparisonValue,
    comparisonLabel,
    deltaPercent,
    targetValue,
    targetLabel,
    sparklineData = [],
    topValues,
    recordCount,
    status: explicitStatus,
    icon = 'BarChart3',
    animationDelay = 0
}) => {
    const navigate = useNavigate();

    // Calculate delta from comparison if not pre-computed
    const delta = useMemo(() => {
        if (deltaPercent !== null && deltaPercent !== undefined) {
            return {
                percentChange: deltaPercent,
                direction: deltaPercent > 0 ? 'up' : deltaPercent < 0 ? 'down' : 'neutral'
            };
        }
        if (comparisonValue && comparisonValue !== 0) {
            const currentNum = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''));
            const prevNum = typeof comparisonValue === 'number' ? comparisonValue : parseFloat(String(comparisonValue).replace(/[^0-9.-]/g, ''));
            if (!isNaN(currentNum) && !isNaN(prevNum) && prevNum !== 0) {
                const pct = ((currentNum - prevNum) / Math.abs(prevNum)) * 100;
                return {
                    percentChange: pct,
                    direction: pct > 0 ? 'up' : pct < 0 ? 'down' : 'neutral'
                };
            }
        }
        return null;
    }, [value, comparisonValue, deltaPercent]);

    // Status
    const status = useMemo(() => {
        if (explicitStatus) return explicitStatus;
        if (!delta) return 'neutral';
        if (delta.percentChange <= -10) return 'critical';
        if (delta.percentChange <= 0) return 'warning';
        return 'success';
    }, [delta, explicitStatus]);

    // Goal progress
    const goalProgress = useMemo(() => {
        if (!targetValue) return null;
        const curr = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''));
        const tgt = typeof targetValue === 'number' ? targetValue : parseFloat(String(targetValue).replace(/[^0-9.-]/g, ''));
        if (isNaN(curr) || isNaN(tgt) || tgt === 0) return null;
        return { progress: Math.min((curr / tgt) * 100, 100), achieved: curr >= tgt };
    }, [value, targetValue]);

    const IconComponent = ICON_MAP[icon] || BarChart3;
    const statusStyle = STATUS_CONFIG[status] || STATUS_CONFIG.neutral;

    const DeltaIcon = delta?.direction === 'up' ? TrendingUp :
        delta?.direction === 'down' ? TrendingDown : Minus;

    const sparkColor = status === 'success' ? '#10b981' :
        status === 'warning' ? '#f59e0b' :
            status === 'critical' ? '#ef4444' : '#06b6d4';

    const handleInvestigate = useCallback(() => {
        const query = `Analyze the KPI "${title}" which currently shows ${formatValue(value, format)}. Break it down by segments, show contributing factors, and identify any anomalies.`;
        navigate('/app/chat', { state: { prefillQuery: query } });
    }, [title, value, format, navigate]);

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: animationDelay, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="h-full"
            aria-live="polite"
        >
            <div
                className={cn(
                    "group relative h-full rounded-xl border-l-[3px] bg-slate-900/80 border border-slate-800/80",
                    "backdrop-blur-sm transition-[background-color,border-color,box-shadow,transform] duration-200",
                    "hover:bg-slate-900/95 hover:border-slate-700/80 hover:shadow-lg hover:shadow-black/30 hover:-translate-y-0.5",
                    statusStyle.border,
                )}
            >
                <div className="p-4 flex flex-col justify-between h-full gap-3">
                    {/* Row 1: Title + Icon + Context Menu */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0" id={`kpi-title-${title.replace(/\s+/g, '-')}`}>
                            <div className={cn(
                                "w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0",
                                statusStyle.bg
                            )} aria-hidden="true">
                                <IconComponent className={cn("w-3.5 h-3.5", statusStyle.text)} />
                            </div>
                            <span className="text-[13px] font-semibold text-slate-300 truncate">
                                {title}
                            </span>
                        </div>
                        <ContextMenu
                            title={title}
                            value={value}
                            format={format}
                            onInvestigate={handleInvestigate}
                        />
                    </div>

                    {/* Row 2: Value + Delta */}
                    <div className="flex items-end justify-between gap-2">
                        <div className="min-w-0">
                            <div
                                className="text-[1.65rem] font-extrabold text-white tracking-tight leading-none tabular-nums"
                                aria-labelledby={`kpi-title-${title.replace(/\s+/g, '-')}`}
                            >
                                {formatValue(value, format)}
                            </div>

                            {/* Delta indicator */}
                            {delta && (
                                <div className="flex items-center gap-1.5 mt-1.5">
                                    <span className={cn(
                                        "inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums",
                                        delta.direction === 'up' ? 'text-emerald-400' :
                                            delta.direction === 'down' ? 'text-red-400' : 'text-slate-400'
                                    )} aria-label={`${delta.direction === 'up' ? 'Increased by' : delta.direction === 'down' ? 'Decreased by' : 'Changed by'} ${Math.abs(delta.percentChange).toFixed(1)} percent`}>
                                        <DeltaIcon className="w-3 h-3" aria-hidden="true" />
                                        {Math.abs(delta.percentChange).toFixed(1)}%
                                    </span>
                                    {comparisonLabel && (
                                        <span className="text-xs text-slate-400">{comparisonLabel}</span>
                                    )}
                                </div>
                            )}

                            {/* Record count subtitle */}
                            {!delta && recordCount && (
                                <p className="text-xs text-slate-400 mt-1 tabular-nums">
                                    {recordCount.toLocaleString()} records
                                </p>
                            )}
                        </div>

                        {/* Mini sparkline (right side) */}
                        {sparklineData && sparklineData.length > 2 && (
                            <div className="flex-shrink-0" aria-hidden="true">
                                <MiniSparkline data={sparklineData} color={sparkColor} height={36} width={80} />
                            </div>
                        )}
                    </div>

                    {/* Row 3: Top values breakdown (for categorical KPIs) */}
                    {topValues && topValues.length > 0 && !sparklineData?.length && (
                        <div className="space-y-1 border-t border-slate-800/60 pt-2">
                            {topValues.slice(0, 3).map((item, i) => (
                                <div key={i} className="flex items-center justify-between text-xs">
                                    <span className="text-slate-400 truncate mr-2">{item.name}</span>
                                    <span className="text-slate-500 font-mono tabular-nums flex-shrink-0">
                                        {item.count?.toLocaleString()}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Row 3 alt: Goal progress bar */}
                    {goalProgress && (
                        <div className="space-y-1 border-t border-slate-800/60 pt-2" aria-label={`Goal progress: ${goalProgress.progress.toFixed(0)} percent`}>
                            <div className="flex items-center justify-between text-xs" aria-hidden="true">
                                <span className="text-slate-500">
                                    {targetLabel || `Goal: ${formatValue(targetValue, format)}`}
                                </span>
                                <span className={cn(
                                    "font-medium tabular-nums",
                                    goalProgress.achieved ? 'text-emerald-400' : 'text-slate-400'
                                )}>
                                    {goalProgress.progress.toFixed(0)}%
                                </span>
                            </div>
                            <div className="h-1 bg-slate-800 rounded-full overflow-hidden" role="progressbar" aria-valuenow={goalProgress.progress.toFixed(0)} aria-valuemin="0" aria-valuemax="100">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${goalProgress.progress}%` }}
                                    transition={{ duration: 0.6, delay: animationDelay + 0.2 }}
                                    className={cn(
                                        "h-full rounded-full",
                                        goalProgress.achieved ? 'bg-emerald-500' :
                                            goalProgress.progress >= 75 ? 'bg-emerald-500' :
                                                goalProgress.progress >= 50 ? 'bg-amber-500' : 'bg-slate-500'
                                    )}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
};

export default EnterpriseKpiCard;
