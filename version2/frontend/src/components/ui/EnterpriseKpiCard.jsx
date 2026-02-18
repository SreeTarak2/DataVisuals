/**
 * EnterpriseKpiCard Component
 * 
 * Enterprise-grade KPI card designed for B2B analytics dashboards.
 * Benchmarked against Power BI, Tableau, and Looker design patterns.
 * 
 * Features:
 * - Primary value callout with proper formatting
 * - Period-over-period comparison with delta indicators
 * - Goal progress tracking with visual bar
 * - Embedded sparkline for trend visualization
 * - Status-based conditional formatting
 * - Professional, executive-ready styling
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import {
    TrendingUp, TrendingDown, Minus,
    DollarSign, Users, FileText, BarChart3,
    Activity, Target, Zap, Database, Package,
    ShoppingCart, Percent, Hash, Calendar
} from 'lucide-react';
import PlotlyChart from '../features/charts/PlotlyChart';
import { cn } from '../../lib/utils';

// Icon mapping for semantic KPI icons
const ICON_MAP = {
    DollarSign, Users, FileText, BarChart3, Activity,
    Target, Zap, Database, Package, ShoppingCart,
    Percent, Hash, Calendar, TrendingUp
};

// Status color configurations (Power BI inspired)
const STATUS_CONFIG = {
    success: {
        border: 'border-l-emerald-500',
        bg: 'bg-emerald-500/10',
        text: 'text-emerald-400',
        glow: 'shadow-emerald-500/20'
    },
    warning: {
        border: 'border-l-amber-500',
        bg: 'bg-amber-500/10',
        text: 'text-amber-400',
        glow: 'shadow-amber-500/20'
    },
    critical: {
        border: 'border-l-red-500',
        bg: 'bg-red-500/10',
        text: 'text-red-400',
        glow: 'shadow-red-500/20'
    },
    neutral: {
        border: 'border-l-slate-500',
        bg: 'bg-slate-500/10',
        text: 'text-slate-400',
        glow: 'shadow-slate-500/20'
    }
};

/**
 * Format value based on type
 */
const formatValue = (value, format = 'number') => {
    if (value === null || value === undefined || value === 'N/A') {
        return 'N/A';
    }

    const num = typeof value === 'string' ? parseFloat(value.replace(/[^0-9.-]/g, '')) : value;

    if (isNaN(num)) {
        return String(value);
    }

    switch (format) {
        case 'currency':
            if (num >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
            if (num >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
            if (num >= 1e3) return `$${(num / 1e3).toFixed(1)}K`;
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0
            }).format(num);

        case 'percentage':
            return `${num.toFixed(1)}%`;

        case 'decimal':
            return num.toFixed(2);

        case 'integer':
        case 'number':
        default:
            if (num >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
            if (num >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
            if (num >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
            return new Intl.NumberFormat('en-US', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 2
            }).format(num);
    }
};

/**
 * Calculate comparison delta
 */
const calculateDelta = (current, previous) => {
    if (!previous || previous === 0) return null;

    const currentNum = typeof current === 'number' ? current : parseFloat(String(current).replace(/[^0-9.-]/g, ''));
    const previousNum = typeof previous === 'number' ? previous : parseFloat(String(previous).replace(/[^0-9.-]/g, ''));

    if (isNaN(currentNum) || isNaN(previousNum)) return null;

    const delta = currentNum - previousNum;
    const percentChange = (delta / Math.abs(previousNum)) * 100;

    return {
        delta,
        percentChange,
        direction: delta > 0 ? 'up' : delta < 0 ? 'down' : 'neutral'
    };
};

/**
 * Determine KPI status based on delta or explicit status
 */
const determineStatus = (delta, explicitStatus, thresholds = { critical: -10, warning: 0 }) => {
    if (explicitStatus) return explicitStatus;
    if (!delta) return 'neutral';

    if (delta.percentChange <= thresholds.critical) return 'critical';
    if (delta.percentChange <= thresholds.warning) return 'warning';
    return 'success';
};

const EnterpriseKpiCard = ({
    // Core data
    title,
    value,
    format = 'number',

    // Comparison
    comparisonValue,
    comparisonLabel = 'vs last period',

    // Goal tracking
    targetValue,
    targetLabel,

    // Trend visualization
    sparklineData = [],

    // Status & appearance
    status: explicitStatus,
    icon = 'BarChart3',
    thresholds,

    // Animation
    animationDelay = 0
}) => {
    // Calculate delta for comparison
    const delta = useMemo(() =>
        calculateDelta(value, comparisonValue),
        [value, comparisonValue]
    );

    // Determine status
    const status = useMemo(() =>
        determineStatus(delta, explicitStatus, thresholds),
        [delta, explicitStatus, thresholds]
    );

    // Calculate goal progress
    const goalProgress = useMemo(() => {
        if (!targetValue) return null;

        const currentNum = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''));
        const targetNum = typeof targetValue === 'number' ? targetValue : parseFloat(String(targetValue).replace(/[^0-9.-]/g, ''));

        if (isNaN(currentNum) || isNaN(targetNum) || targetNum === 0) return null;

        const progress = Math.min((currentNum / targetNum) * 100, 100);
        return {
            progress,
            achieved: currentNum >= targetNum,
            remaining: Math.max(targetNum - currentNum, 0)
        };
    }, [value, targetValue]);

    // Get icon component
    const IconComponent = ICON_MAP[icon] || BarChart3;

    // Get status styling
    const statusStyle = STATUS_CONFIG[status] || STATUS_CONFIG.neutral;

    // Delta icon
    const DeltaIcon = delta?.direction === 'up' ? TrendingUp :
        delta?.direction === 'down' ? TrendingDown : Minus;

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: animationDelay, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="h-full"
        >
            <div
                className={cn(
                    // Base card styling - professional, not playful
                    "relative h-full rounded-xl border-l-4 bg-slate-900/80 border border-slate-800/80",
                    "backdrop-blur-sm transition-all duration-300",
                    "hover:border-slate-700/80 hover:bg-slate-900/90",
                    // Status accent border
                    statusStyle.border,
                    // Subtle shadow
                    "shadow-lg shadow-black/20"
                )}
            >
                <div className="p-5 space-y-4">
                    {/* Header: Title + Icon */}
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                            {title}
                        </span>
                        <div className={cn(
                            "w-8 h-8 rounded-lg flex items-center justify-center",
                            statusStyle.bg
                        )}>
                            <IconComponent className={cn("w-4 h-4", statusStyle.text)} />
                        </div>
                    </div>

                    {/* Primary Value - Large Callout */}
                    <div className="space-y-1">
                        <div className="text-3xl font-bold text-white tracking-tight">
                            {formatValue(value, format)}
                        </div>

                        {/* Delta Indicator */}
                        {delta && (
                            <div className="flex items-center gap-2">
                                <div className={cn(
                                    "flex items-center gap-1 text-sm font-medium",
                                    delta.direction === 'up' ? 'text-emerald-400' :
                                        delta.direction === 'down' ? 'text-red-400' : 'text-slate-400'
                                )}>
                                    <DeltaIcon className="w-3.5 h-3.5" />
                                    <span>
                                        {delta.direction === 'up' ? '+' : ''}
                                        {delta.percentChange.toFixed(1)}%
                                    </span>
                                </div>
                                <span className="text-xs text-slate-500">
                                    {comparisonLabel}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Goal Progress Bar */}
                    {goalProgress && (
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-500">
                                    {targetLabel || `Goal: ${formatValue(targetValue, format)}`}
                                </span>
                                <span className={cn(
                                    "font-medium",
                                    goalProgress.achieved ? 'text-emerald-400' : 'text-slate-400'
                                )}>
                                    {goalProgress.progress.toFixed(0)}%
                                </span>
                            </div>
                            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${goalProgress.progress}%` }}
                                    transition={{ duration: 0.8, delay: animationDelay + 0.2, ease: "easeOut" }}
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

                    {/* Sparkline */}
                    {sparklineData && sparklineData.length > 1 && (
                        <div className="h-[60px] mt-3 -mx-2 -mb-2 overflow-hidden">
                            <PlotlyChart
                                data={[{
                                    x: sparklineData.map((_, i) => i),
                                    y: sparklineData.map(d => typeof d === 'object' ? d.y : d),
                                    type: 'scatter',
                                    mode: 'lines',
                                    fill: 'tozeroy',
                                    line: {
                                        color: status === 'success' ? '#10b981' :
                                            status === 'warning' ? '#f59e0b' :
                                                status === 'critical' ? '#ef4444' : '#64748b',
                                        width: 2,
                                        shape: 'spline'
                                    },
                                    fillcolor: status === 'success' ? 'rgba(16, 185, 129, 0.15)' :
                                        status === 'warning' ? 'rgba(245, 158, 11, 0.15)' :
                                            status === 'critical' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(100, 116, 139, 0.15)',
                                    hoverinfo: 'skip'
                                }]}
                                layout={{
                                    margin: { l: 0, r: 0, t: 5, b: 0 },
                                    showlegend: false,
                                    xaxis: { visible: false, fixedrange: true },
                                    yaxis: { visible: false, fixedrange: true },
                                    paper_bgcolor: 'transparent',
                                    plot_bgcolor: 'transparent',
                                    autosize: true,
                                    height: 60
                                }}
                                config={{
                                    displayModeBar: false,
                                    staticPlot: true,
                                    responsive: true
                                }}
                                style={{ width: '100%', height: '60px' }}
                            />
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
};

export default EnterpriseKpiCard;
