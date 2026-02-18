/**
 * InsightsBar Component
 * 
 * A compact, professional insights section that displays real QUIS analysis
 * data in a clean 2-column grid. Replaces the previous InsightsPanel,
 * ExecutiveSummary, and InsightsSection components.
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Zap,
    TrendingUp,
    AlertTriangle,
    CheckCircle,
    Lightbulb,
    ChevronDown,
    ChevronUp,
    Search,
    Activity,
    BarChart3,
    Shield,
} from 'lucide-react';

const ICON_MAP = {
    success: CheckCircle,
    info: Lightbulb,
    warning: AlertTriangle,
    trend: TrendingUp,
    anomaly: AlertTriangle,
    correlation: Activity,
    distribution: BarChart3,
    recommendation: Lightbulb,
    quis: Search,
    subspace: Search,
    default: Zap,
};

const COLOR_MAP = {
    success: {
        icon: 'text-emerald-400',
        bg: 'bg-emerald-500/10',
        border: 'border-emerald-500/20',
        badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    },
    info: {
        icon: 'text-blue-400',
        bg: 'bg-blue-500/10',
        border: 'border-blue-500/20',
        badge: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    },
    warning: {
        icon: 'text-amber-400',
        bg: 'bg-amber-500/10',
        border: 'border-amber-500/20',
        badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    },
    default: {
        icon: 'text-slate-400',
        bg: 'bg-slate-500/10',
        border: 'border-slate-500/20',
        badge: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
    },
};

const VISIBLE_COUNT = 4;

const InsightsBar = ({ insights = [], loading = false }) => {
    const [expanded, setExpanded] = useState(false);

    if (loading) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/80 rounded-2xl p-5"
            >
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-500/15 rounded-lg flex items-center justify-center">
                        <Zap className="w-4 h-4 text-blue-400 animate-pulse" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">Analyzing patterns…</h3>
                        <p className="text-xs text-slate-500 mt-0.5">Running QUIS statistical analysis</p>
                    </div>
                </div>
            </motion.div>
        );
    }

    if (!insights || insights.length === 0) return null;

    const visibleInsights = expanded ? insights : insights.slice(0, VISIBLE_COUNT);
    const hasMore = insights.length > VISIBLE_COUNT;

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/80 rounded-2xl overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-5 pt-5 pb-3">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-500/15 rounded-lg flex items-center justify-center">
                        <Shield className="w-4 h-4 text-blue-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">Statistical Insights</h3>
                        <p className="text-xs text-slate-500 mt-0.5">
                            {insights.length} pattern{insights.length !== 1 ? 's' : ''} detected via QUIS analysis
                        </p>
                    </div>
                </div>
            </div>

            {/* Insights Grid */}
            <div className="px-5 pb-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <AnimatePresence mode="popLayout">
                        {visibleInsights.map((insight, i) => {
                            const type = insight.type || 'default';
                            const colors = COLOR_MAP[type] || COLOR_MAP.default;
                            const Icon = ICON_MAP[type] || ICON_MAP.default;

                            return (
                                <motion.div
                                    key={insight.id || `insight-${i}`}
                                    initial={{ opacity: 0, scale: 0.97 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.97 }}
                                    transition={{ delay: i * 0.04 }}
                                    className={`
                                        flex items-start gap-3 p-3.5 rounded-xl
                                        bg-slate-800/40 border border-slate-700/40
                                        hover:bg-slate-800/60 hover:border-slate-700/60
                                        transition-all duration-200
                                    `}
                                >
                                    <div className={`
                                        w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5
                                        ${colors.bg} ${colors.border} border
                                    `}>
                                        <Icon className={`w-3.5 h-3.5 ${colors.icon}`} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <p className="text-[13px] font-medium text-slate-200 truncate">
                                                {insight.title}
                                            </p>
                                            {insight.confidence && (
                                                <span className={`
                                                    text-[10px] px-1.5 py-0.5 rounded-full border flex-shrink-0
                                                    ${colors.badge}
                                                `}>
                                                    {insight.confidence}%
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">
                                            {insight.description}
                                        </p>
                                    </div>
                                </motion.div>
                            );
                        })}
                    </AnimatePresence>
                </div>
            </div>

            {/* Expand / Collapse */}
            {hasMore && (
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="
                        w-full flex items-center justify-center gap-1.5 py-2.5
                        text-xs text-slate-500 hover:text-slate-300
                        border-t border-slate-800/60
                        bg-slate-900/40 hover:bg-slate-800/40
                        transition-all duration-200
                    "
                >
                    {expanded ? (
                        <>Show less <ChevronUp className="w-3.5 h-3.5" /></>
                    ) : (
                        <>Show {insights.length - VISIBLE_COUNT} more <ChevronDown className="w-3.5 h-3.5" /></>
                    )}
                </button>
            )}
        </motion.div>
    );
};

export default InsightsBar;
