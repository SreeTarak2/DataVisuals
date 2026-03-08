/**
 * InsightsBar Component — v2.0
 * 
 * Redesigned to be genuinely useful for normal users:
 * - Executive Summary gets a prominent hero card
 * - Insight cards have human-readable titles and descriptions
 * - Confidence shown as qualitative labels, not raw percentages
 * - Visual hierarchy by insight type (color-coded borders & icons)
 * - Shows top 3 insights initially — quality over quantity
 */

import React, { useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
    Zap,
    TrendingUp,
    TrendingDown,
    AlertTriangle,
    CheckCircle,
    Lightbulb,
    ChevronDown,
    ChevronUp,
    Search,
    Activity,
    BarChart3,
    MessageSquare,
    Copy,
    Check,
    ArrowRight,
    Sparkles,
    Eye,
    Shuffle,
    FileText,
} from 'lucide-react';
import useChatStore from '../../../store/chatStore';
import useDatasetStore from '../../../store/datasetStore';
import InsightFeedback from '../../../components/features/feedback/InsightFeedback';

// ── Icon mapping by insight type ──
const ICON_MAP = {
    success: Sparkles,
    info: Activity,
    warning: AlertTriangle,
    trend: TrendingUp,
    anomaly: AlertTriangle,
    correlation: Activity,
    distribution: BarChart3,
    recommendation: Lightbulb,
    quis: Search,
    subspace: Eye,
    default: Zap,
};

// ── Richer color themes per insight type ──
const COLOR_MAP = {
    success: {
        icon: 'text-emerald-400',
        bg: 'bg-emerald-500/8',
        border: 'border-emerald-500/25',
        borderAccent: 'border-l-emerald-500',
        badge: 'bg-emerald-500/12 text-emerald-400',
        action: 'hover:bg-emerald-500/10 hover:text-emerald-400 hover:border-emerald-500/30',
        glow: 'shadow-emerald-500/5',
    },
    info: {
        icon: 'text-blue-400',
        bg: 'bg-blue-500/8',
        border: 'border-blue-500/25',
        borderAccent: 'border-l-blue-500',
        badge: 'bg-blue-500/12 text-blue-400',
        action: 'hover:bg-blue-500/10 hover:text-blue-400 hover:border-blue-500/30',
        glow: 'shadow-blue-500/5',
    },
    warning: {
        icon: 'text-amber-400',
        bg: 'bg-amber-500/8',
        border: 'border-amber-500/25',
        borderAccent: 'border-l-amber-500',
        badge: 'bg-amber-500/12 text-amber-400',
        action: 'hover:bg-amber-500/10 hover:text-amber-400 hover:border-amber-500/30',
        glow: 'shadow-amber-500/5',
    },
    trend: {
        icon: 'text-violet-400',
        bg: 'bg-violet-500/8',
        border: 'border-violet-500/25',
        borderAccent: 'border-l-violet-500',
        badge: 'bg-violet-500/12 text-violet-400',
        action: 'hover:bg-violet-500/10 hover:text-violet-400 hover:border-violet-500/30',
        glow: 'shadow-violet-500/5',
    },
    default: {
        icon: 'text-slate-400',
        bg: 'bg-slate-500/8',
        border: 'border-slate-500/25',
        borderAccent: 'border-l-slate-500',
        badge: 'bg-slate-500/12 text-slate-400',
        action: 'hover:bg-slate-500/10 hover:text-slate-300 hover:border-slate-500/30',
        glow: 'shadow-slate-500/5',
    },
};

const VISIBLE_COUNT = 3;

// ── Convert confidence number to a human-readable label ──
const getConfidenceLabel = (confidence) => {
    if (confidence >= 95) return { text: 'Very High', color: 'text-emerald-400 bg-emerald-500/10' };
    if (confidence >= 80) return { text: 'High', color: 'text-blue-400 bg-blue-500/10' };
    if (confidence >= 60) return { text: 'Moderate', color: 'text-amber-400 bg-amber-500/10' };
    return { text: 'Low', color: 'text-slate-400 bg-slate-500/10' };
};

// ── Get a human-friendly type label ──
const getTypeLabel = (type) => {
    const labels = {
        success: 'Key Finding',
        info: 'Relationship',
        warning: 'Attention',
        trend: 'Trend',
        anomaly: 'Anomaly',
    };
    return labels[type] || 'Insight';
};

// ── Clean up any remaining statistical jargon from descriptions ──
const humanizeDescription = (desc) => {
    if (!desc) return '';
    return desc
        // Remove raw p-value references
        .replace(/\.\s*p[=<]\d+\.\d+/gi, '')
        // Remove effect size references
        .replace(/\.\s*effect\s*size[=:]\s*\d+\.\d+(\s*\([^)]*\))?/gi, '')
        // Remove confidence interval references
        .replace(/\.\s*95%\s*CI:\s*\[[^\]]+\]/gi, '')
        // Remove normality test references  
        .replace(/\.\s*Normality test:\s*p[=<]\d+\.\d+/gi, '')
        // Remove r= correlation coefficient
        .replace(/\s*\(r[=:]\s*-?\d+\.\d+[^)]*\)/gi, '')
        // Clean up double periods and trailing dots
        .replace(/\.{2,}/g, '.')
        .replace(/\.\s*$/, '.')
        .trim();
};

const InsightsBar = ({ insights = [], loading = false }) => {
    const [expanded, setExpanded] = useState(false);
    const [copiedId, setCopiedId] = useState(null);
    const navigate = useNavigate();

    const { startNewConversation, sendMessageStreaming } = useChatStore();
    const { selectedDataset } = useDatasetStore();

    // Separate executive summary from other insights
    const { summary, findings } = useMemo(() => {
        const summaryInsight = insights.find(i => i.id === 'executive_summary');
        const rest = insights.filter(i => i.id !== 'executive_summary');
        return { summary: summaryInsight, findings: rest };
    }, [insights]);

    // ── Investigate: open chat with a pre-filled investigation query ──
    const handleInvestigate = useCallback((insight) => {
        if (!selectedDataset?.id) return;

        const query = `Investigate this insight in detail: "${insight.title}". ${insight.description || ''} — provide deeper analysis, possible causes, and recommended actions.`;
        navigate('/app/chat', { state: { prefillQuery: query } });
    }, [selectedDataset, navigate]);

    // ── Copy insight text to clipboard ──
    const handleCopy = useCallback((insight) => {
        const text = `${insight.title}\n${insight.description || ''}`;
        navigator.clipboard.writeText(text).then(() => {
            setCopiedId(insight.id || insight.title);
            setTimeout(() => setCopiedId(null), 2000);
        });
    }, []);

    if (loading) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/80 rounded-2xl p-6"
                aria-live="polite"
                aria-busy="true"
            >
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-indigo-500/10 rounded-xl flex items-center justify-center border border-indigo-500/20" aria-hidden="true">
                        <Sparkles className="w-5 h-5 text-indigo-400 animate-pulse" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">Analyzing your data…</h3>
                        <p className="text-xs text-slate-500 mt-0.5">Finding the most important patterns</p>
                    </div>
                </div>
            </motion.div>
        );
    }

    if (!insights || insights.length === 0) return null;

    const visibleFindings = expanded ? findings : findings.slice(0, VISIBLE_COUNT);
    const hasMore = findings.length > VISIBLE_COUNT;

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/80 rounded-2xl overflow-hidden"
            aria-label="Data Insights"
        >
            {/* ─── Header ─── */}
            <div className="flex items-center justify-between px-6 pt-5 pb-4">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-indigo-500/10 rounded-xl flex items-center justify-center border border-indigo-500/20" aria-hidden="true">
                        <Sparkles className="w-4.5 h-4.5 text-indigo-400" />
                    </div>
                    <div>
                        <h3 className="text-[15px] font-bold text-slate-100 tracking-tight">Key Insights</h3>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                            Top findings from AI analysis
                        </p>
                    </div>
                </div>
                {findings.length > 0 && (
                    <span className="text-[11px] text-slate-500 bg-slate-800/60 px-2.5 py-1 rounded-full">
                        {findings.length} finding{findings.length !== 1 ? 's' : ''}
                    </span>
                )}
            </div>

            <div className="px-5 pb-5 space-y-4">
                {/* ─── Executive Summary Hero Card ─── */}
                {summary && (
                    <motion.div
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="relative p-4 rounded-xl bg-gradient-to-br from-indigo-500/8 via-slate-800/40 to-violet-500/8 border border-indigo-500/20 group/summary"
                    >
                        <div className="flex items-start gap-3">
                            <div className="w-8 h-8 rounded-lg bg-indigo-500/15 flex items-center justify-center flex-shrink-0 border border-indigo-500/25" aria-hidden="true">
                                <FileText className="w-4 h-4 text-indigo-400" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1.5">
                                    <h4 className="text-[13px] font-semibold text-indigo-300">Summary</h4>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/12 text-indigo-400">
                                        AI Generated
                                    </span>
                                </div>
                                <p className="text-[12.5px] text-slate-300 leading-relaxed">
                                    {humanizeDescription(summary.description)}
                                </p>
                            </div>
                        </div>
                        {/* Summary actions */}
                        <div className="flex items-center gap-2 mt-3 ml-11 opacity-0 group-hover/summary:opacity-100 focus-within:opacity-100 transition-opacity duration-200">
                            <button
                                onClick={() => handleInvestigate(summary)}
                                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium border border-indigo-500/25 text-indigo-400/70 hover:bg-indigo-500/10 hover:text-indigo-300 transition-all duration-150"
                                title="Dig deeper with AI"
                            >
                                <MessageSquare className="w-3 h-3" aria-hidden="true" />
                                Ask AI about this
                                <ArrowRight className="w-2.5 h-2.5" aria-hidden="true" />
                            </button>
                            <button
                                onClick={() => handleCopy(summary)}
                                className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] border border-slate-700/40 text-slate-500 hover:text-slate-300 hover:bg-slate-700/30 transition-all duration-150"
                                title="Copy summary"
                            >
                                {copiedId === summary.id ? (
                                    <><Check className="w-3 h-3 text-emerald-400" /><span className="text-emerald-400">Copied</span></>
                                ) : (
                                    <><Copy className="w-3 h-3" />Copy</>
                                )}
                            </button>
                        </div>
                    </motion.div>
                )}

                {/* ─── Insight Cards ─── */}
                {visibleFindings.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" role="list">
                        <AnimatePresence mode="popLayout">
                            {visibleFindings.map((insight, i) => {
                                const type = insight.type || 'default';
                                const colors = COLOR_MAP[type] || COLOR_MAP.default;
                                const Icon = ICON_MAP[type] || ICON_MAP.default;
                                const insightId = insight.id || `insight-${i}`;
                                const isCopied = copiedId === (insight.id || insight.title);
                                const confLabel = getConfidenceLabel(insight.confidence);
                                const typeLabel = getTypeLabel(type);

                                return (
                                    <motion.div
                                        key={insightId}
                                        role="listitem"
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: -8 }}
                                        transition={{ delay: i * 0.05, duration: 0.25 }}
                                        className={`
                                            flex flex-col gap-3 p-3.5 rounded-xl
                                            bg-slate-800/30 border border-slate-700/30
                                            border-l-2 ${colors.borderAccent}
                                            hover:bg-slate-800/50 hover:border-slate-700/50
                                            hover:shadow-lg ${colors.glow}
                                            transition-all duration-200 group/card
                                        `}
                                        aria-labelledby={`insight-title-${insightId}`}
                                        aria-describedby={`insight-desc-${insightId}`}
                                    >
                                        {/* Card header: type badge + confidence */}
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <div className={`
                                                    w-6 h-6 rounded-md flex items-center justify-center
                                                    ${colors.bg} ${colors.border} border
                                                `} aria-hidden="true">
                                                    <Icon className={`w-3 h-3 ${colors.icon}`} />
                                                </div>
                                                <span className={`text-[10px] font-semibold uppercase tracking-wider ${colors.icon}`}>
                                                    {typeLabel}
                                                </span>
                                            </div>
                                            {insight.confidence != null && (
                                                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${confLabel.color}`}>
                                                    {confLabel.text}
                                                </span>
                                            )}
                                        </div>

                                        {/* Title & description */}
                                        <div className="flex-1 min-w-0">
                                            <p id={`insight-title-${insightId}`} className="text-[13px] font-semibold text-slate-200 leading-snug mb-1">
                                                {insight.title}
                                            </p>
                                            <p id={`insight-desc-${insightId}`} className="text-[11.5px] text-slate-400 leading-relaxed line-clamp-3">
                                                {humanizeDescription(insight.description)}
                                            </p>
                                        </div>

                                        {/* Action buttons */}
                                        <div className="flex items-center justify-between opacity-0 group-hover/card:opacity-100 focus-within:opacity-100 transition-opacity duration-200">
                                            <div className="flex items-center gap-1.5">
                                                <button
                                                    onClick={() => handleInvestigate(insight)}
                                                    className={`
                                                        flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium
                                                        border border-slate-700/40 text-slate-500
                                                        ${colors.action}
                                                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500
                                                        transition-all duration-150
                                                    `}
                                                    title="Ask AI to investigate this insight"
                                                >
                                                    <MessageSquare className="w-3 h-3" aria-hidden="true" />
                                                    Investigate
                                                    <ArrowRight className="w-2.5 h-2.5" aria-hidden="true" />
                                                </button>

                                                <button
                                                    onClick={() => handleCopy(insight)}
                                                    className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] border border-slate-700/40 text-slate-500 hover:text-slate-300 hover:bg-slate-700/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 transition-all duration-150"
                                                    title="Copy insight"
                                                    aria-live="polite"
                                                >
                                                    {isCopied ? (
                                                        <><Check className="w-3 h-3 text-emerald-400" aria-hidden="true" /><span className="text-emerald-400">Copied</span></>
                                                    ) : (
                                                        <><Copy className="w-3 h-3" aria-hidden="true" />Copy</>
                                                    )}
                                                </button>
                                            </div>

                                            <InsightFeedback
                                                variant="compact"
                                                insightText={`${insight.title}. ${insight.description || ''}`}
                                                datasetId={selectedDataset?.id}
                                            />
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                    </div>
                )}
            </div>

            {/* ─── Expand / Collapse ─── */}
            {hasMore && (
                <button
                    onClick={() => setExpanded(!expanded)}
                    aria-expanded={expanded}
                    className="
                        w-full flex items-center justify-center gap-1.5 py-2.5
                        text-[11px] font-medium text-slate-500 hover:text-slate-300
                        border-t border-slate-800/50
                        bg-slate-900/30 hover:bg-slate-800/30
                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:ring-inset
                        transition-all duration-200
                    "
                >
                    {expanded ? (
                        <>Show fewer insights <ChevronUp className="w-3.5 h-3.5" aria-hidden="true" /></>
                    ) : (
                        <>{findings.length - VISIBLE_COUNT} more insight{findings.length - VISIBLE_COUNT !== 1 ? 's' : ''} <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /></>
                    )}
                </button>
            )}
        </motion.div>
    );
};

export default InsightsBar;
