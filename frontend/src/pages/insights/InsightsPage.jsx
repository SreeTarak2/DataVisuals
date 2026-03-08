/**
 * InsightsPage — Premium Intelligence Report
 *
 * Full-featured insights dashboard with:
 * - Executive summary in plain English
 * - Animated stat cards with real-time counts
 * - Data quality health gauge with letter grade
 * - Key findings ranked by statistical impact (with evidence tier badges)
 * - Relationship / correlation explorer with filter
 * - Anomaly spotlight with visual ring gauge
 * - Trend analysis with mini sparklines
 * - Segment comparisons with fallback computation
 * - Driver analysis (feature importance via mutual information)
 * - Subset filter bar (?filters= param)
 * - Prioritised action plan with magnitude-based urgency scoring
 */

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Sparkles, RefreshCw, AlertTriangle, TrendingUp, Shield,
    Lightbulb, Layers, ArrowRight, MessageSquare, Target, Zap,
    AlertCircle, GitBranch, Database, Clock, BrainCircuit, Cpu,
    BarChart2, SlidersHorizontal,
} from 'lucide-react';
import useDatasetStore from '../../store/datasetStore';
import { useInsightsData } from './hooks/useInsightsData';
import { cn } from '../../lib/utils';

import ExecutiveSummary from './components/ExecutiveSummary';
import DataQualityCard from './components/DataQualityCard';
import KeyFindings from './components/KeyFindings';
import CorrelationExplorer from './components/CorrelationExplorer';
import AnomalySpotlight from './components/AnomalySpotlight';
import TrendAnalysis from './components/TrendAnalysis';
import SegmentAnalysis from './components/SegmentAnalysis';
import Recommendations from './components/Recommendations';
import DistributionInsights from './components/DistributionInsights';
import DriverAnalysis from './components/DriverAnalysis';
import FilterBar from './components/FilterBar';

// ── Animated counter ──
const AnimatedCounter = ({ value, duration = 1200 }) => {
    const [count, setCount] = useState(0);
    const rafRef = useRef(null);
    useEffect(() => {
        if (!value) { setCount(0); return; }
        const start = Date.now();
        const tick = () => {
            const p = Math.min((Date.now() - start) / duration, 1);
            const eased = 1 - Math.pow(1 - p, 3);
            setCount(Math.round(eased * value));
            if (p < 1) rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(rafRef.current);
    }, [value, duration]);
    return <span>{count}</span>;
};

// ── Empty State ──
const EmptyState = ({ onUpload }) => (
    <div className="flex items-center justify-center min-h-[70vh]">
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center max-w-md mx-auto px-6"
        >
            <div className="relative w-20 h-20 mx-auto mb-6">
                <div className="absolute inset-0 rounded-3xl animate-pulse" style={{ background: 'linear-gradient(to bottom right, var(--accent-primary-muted), rgba(59, 130, 246, 0.2))' }} />
                <div className="relative w-full h-full rounded-3xl flex items-center justify-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--accent-primary-muted)' }}>
                    <BrainCircuit className="w-10 h-10" style={{ color: 'var(--accent-primary)' }} />
                </div>
            </div>
            <h2 className="text-2xl font-bold mb-3" style={{ color: 'var(--page-text)' }}>No Dataset Selected</h2>
            <p className="text-sm leading-relaxed mb-8" style={{ color: 'var(--page-muted)' }}>
                Select a dataset from the sidebar to unlock AI-powered deep analysis,
                statistical insights, and actionable recommendations.
            </p>
            <button
                onClick={onUpload}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-white text-sm font-medium rounded-xl transition-all"
                style={{ backgroundColor: 'var(--accent-primary)' }}
            >
                <Database className="w-4 h-4" />
                Upload a Dataset
            </button>
        </motion.div>
    </div>
);

// ── Loading Skeleton ──
const LoadingSkeleton = () => (
    <div className="space-y-6 animate-pulse">
        <div className="h-14 rounded-2xl w-2/5" style={{ backgroundColor: 'var(--surface-2)' }} />
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
            {[...Array(7)].map((_, i) => (
                <div key={i} className="h-20 rounded-2xl" style={{ backgroundColor: 'var(--surface-2)' }} />
            ))}
        </div>
        <div className="h-9 rounded-xl w-full" style={{ backgroundColor: 'var(--surface-2)' }} />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="h-56 rounded-2xl" style={{ backgroundColor: 'var(--surface-2)' }} />
            <div className="lg:col-span-2 h-56 rounded-2xl" style={{ backgroundColor: 'var(--surface-2)' }} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {[...Array(4)].map((_, i) => (
                <div key={i} className="h-60 rounded-2xl" style={{ backgroundColor: 'var(--surface-2)' }} />
            ))}
        </div>
    </div>
);

// ── Error State ──
const ErrorState = ({ error, onRetry }) => (
    <div className="flex items-center justify-center min-h-[50vh]">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center max-w-md">
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl flex items-center justify-center border" style={{ backgroundColor: 'var(--semantic-error-muted)', borderColor: 'var(--semantic-error-border)' }}>
                <AlertCircle className="w-7 h-7" style={{ color: 'var(--semantic-error)' }} />
            </div>
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--page-text)' }}>Analysis Failed</h3>
            <p className="text-sm mb-5 leading-relaxed" style={{ color: 'var(--page-muted)' }}>{error}</p>
            <button
                onClick={onRetry}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-xl transition-colors border"
                style={{ backgroundColor: 'var(--surface-1)', color: 'var(--page-text)', borderColor: 'var(--surface-border)' }}
            >
                <RefreshCw className="w-4 h-4" />
                Retry Analysis
            </button>
        </motion.div>
    </div>
);

// ── Tab System ──
const TABS = [
    { id: 'overview',         label: 'Overview',       icon: Target,        countKey: null },
    { id: 'findings',         label: 'Key Findings',   icon: Zap,           countKey: 'key_findings' },
    { id: 'correlations',     label: 'Relationships',  icon: GitBranch,     countKey: 'correlations' },
    { id: 'anomalies',        label: 'Anomalies',      icon: AlertTriangle, countKey: 'anomalies' },
    { id: 'trends',           label: 'Trends',         icon: TrendingUp,    countKey: 'trends' },
    { id: 'segments',         label: 'Segments',       icon: Layers,        countKey: 'segments' },
    { id: 'drivers',          label: 'Drivers',        icon: Cpu,           countKey: 'drivers' },
    { id: 'recommendations',  label: 'Action Plan',    icon: Lightbulb,     countKey: null },
];

// ── Clickable stat card ──
const StatCard = ({ icon: Icon, label, count, color, onClick, active }) => (
    <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={onClick}
        className={cn(
            'relative flex flex-col items-start p-3.5 rounded-2xl border transition-all duration-200 text-left w-full backdrop-blur-sm',
            'bg-[var(--surface-1)]',
            active ? 'border-[var(--accent-primary)]/40 shadow-lg' : color.border,
            'hover:shadow-lg',
            color.hoverShadow,
        )}
    >
        <div className={cn('w-7 h-7 rounded-xl flex items-center justify-center mb-2', color.iconBg)}>
            <Icon className={cn('w-3.5 h-3.5', color.iconText)} />
        </div>
        <div className={cn('text-xl font-bold tabular-nums', color.text)}>
            <AnimatedCounter value={count || 0} />
        </div>
        <div className="text-[11px] mt-0.5 font-medium" style={{ color: 'var(--page-muted)' }}>{label}</div>
    </motion.button>
);

// ── Main Page ──
const InsightsPage = () => {
    const { selectedDataset } = useDatasetStore();
    const navigate = useNavigate();
    const { loading, error, data, filters, refresh, applyFilters, clearFilters } = useInsightsData(selectedDataset);
    const [activeTab, setActiveTab] = useState('overview');

    const investigateInChat = (query) => {
        navigate('/app/chat', { state: { prefillQuery: query } });
    };

    if (!selectedDataset) {
        return (
            <div className="min-h-full bg-[var(--page-bg)] px-4 py-6 sm:p-8">
                <EmptyState onUpload={() => navigate('/app/datasets')} />
            </div>
        );
    }

    if (loading && !data) {
        return (
            <div className="min-h-full bg-[var(--page-bg)] px-4 py-6 sm:p-8">
                <LoadingSkeleton />
            </div>
        );
    }

    if (error && !data) {
        return (
            <div className="min-h-full bg-[var(--page-bg)] px-4 py-6 sm:p-8">
                <ErrorState error={error} onRetry={refresh} />
            </div>
        );
    }

    if (!data) return null;

    const counts = data.counts || {};
    const healthColor = data.data_quality?.health_color || 'blue';
    const HEALTH_GRADIENT = {
        emerald: 'from-emerald-500 to-teal-400',
        blue:    'from-blue-500 to-cyan-400',
        amber:   'from-amber-500 to-orange-400',
        red:     'from-red-500 to-rose-400',
    };
    const healthGradient = HEALTH_GRADIENT[healthColor] || HEALTH_GRADIENT.blue;

    // Parse applied_filters from response for display
    const appliedFilters = data.applied_filters || {};
    const hasFilters = Object.keys(appliedFilters).length > 0 || !!filters;

    // Parse filters string to object for FilterBar
    const currentFilters = { ...appliedFilters };
    if (filters && Object.keys(appliedFilters).length === 0) {
        filters.split(',').forEach(pair => {
            const [col, val] = pair.split(':');
            if (col && val) currentFilters[col.trim()] = val.trim();
        });
    }

    return (
        <div className="min-h-full bg-[var(--page-bg)] px-4 py-6 sm:p-8 space-y-5">

            {/* ── Premium Header ── */}
            <motion.div
                initial={{ opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col sm:flex-row sm:items-start justify-between gap-4"
            >
                <div>
                    <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[11px] font-bold tracking-[0.2em] uppercase" style={{ color: 'var(--accent-primary)' }}>
                            Intelligence Report
                        </span>
                        {data.domain && data.domain !== 'general' && (
                            <span className="px-2 py-0.5 text-[10px] font-bold rounded-full uppercase tracking-wider border" style={{ backgroundColor: 'var(--accent-primary-muted)', color: 'var(--accent-muted)', borderColor: 'var(--accent-primary-muted)' }}>
                                {data.domain}
                            </span>
                        )}
                        {hasFilters && (
                            <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/25 uppercase tracking-wider flex items-center gap-1">
                                <SlidersHorizontal className="w-2.5 h-2.5" />
                                Filtered
                            </span>
                        )}
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight leading-tight" style={{ color: 'var(--page-text)' }}>
                        {data.dataset_name || selectedDataset?.name}
                    </h1>
                    <p className="text-xs mt-1.5 flex items-center gap-1.5" style={{ color: 'var(--page-muted)' }}>
                        <Clock className="w-3 h-3" />
                        {data.generated_at
                            ? `Analyzed ${new Date(data.generated_at).toLocaleString()}`
                            : 'Just analyzed'}
                        {data.filtered_row_count && (
                            <span className="ml-2 text-amber-400/70">
                                · {data.filtered_row_count.toLocaleString()} rows (filtered)
                            </span>
                        )}
                    </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                    <button
                        onClick={refresh}
                        disabled={loading}
                        className={cn(
                            'flex items-center gap-2 px-3 py-2 text-sm rounded-xl border transition-all',
                            loading
                                ? 'border-[var(--surface-border)] text-[var(--page-muted)] cursor-not-allowed opacity-60'
                                : 'border-[var(--surface-border)] text-[var(--page-muted)] hover:bg-[var(--surface-2)] hover:border-[var(--surface-border-hover)]',
                        )}
                    >
                        <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
                        {loading ? 'Analyzing…' : 'Refresh'}
                    </button>
                    <button
                        onClick={() => investigateInChat(
                            `Give me a comprehensive analysis of my ${data.dataset_name || 'dataset'} — what are the most important patterns and what should I focus on?`
                        )}
                        className="flex items-center gap-2 px-4 py-2 text-sm rounded-xl bg-[var(--accent-primary)] text-white hover:opacity-90 transition-all shadow-lg font-medium"
                    >
                        <MessageSquare className="w-4 h-4" />
                        Ask AI
                    </button>
                </div>
            </motion.div>

            {/* ── Filter Bar ── */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.05 }}
            >
                <FilterBar
                    appliedFilters={currentFilters}
                    filteredRowCount={data.filtered_row_count}
                    onApplyFilters={applyFilters}
                    onClearFilters={clearFilters}
                    loading={loading}
                />
            </motion.div>

            {/* ── Animated Stat Cards ── */}
            <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 }}
                className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5"
            >
                {/* Health Score — special card */}
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setActiveTab('overview')}
                    className={cn(
                        'relative flex flex-col items-start p-3.5 rounded-2xl border bg-[var(--surface-1)] backdrop-blur-sm hover:shadow-lg transition-all cursor-pointer text-left',
                        activeTab === 'overview' ? 'border-[var(--accent-primary)]/40 shadow-lg shadow-[var(--accent-primary)]/10' : 'border-[var(--surface-border)] hover:border-[var(--surface-border-hover)]',
                    )}
                >
                    <div className={cn('w-7 h-7 rounded-xl flex items-center justify-center mb-2 bg-gradient-to-br opacity-90', healthGradient)}>
                        <Shield className="w-3.5 h-3.5 text-white" />
                    </div>
                    <div className={cn('text-xl font-bold tabular-nums bg-gradient-to-r bg-clip-text text-transparent', healthGradient)}>
                        {data.data_quality?.health_score || '—'}
                    </div>
                    <div className="text-[11px] text-[var(--page-muted)] mt-0.5 font-medium">Health</div>
                </motion.button>

                <StatCard icon={Zap}           label="Findings"       count={counts.key_findings}  active={activeTab === 'findings'}      color={{ border: 'border-amber-500/20 hover:border-amber-500/35',   iconBg: 'bg-amber-500/10',   iconText: 'text-amber-400',   text: 'text-amber-400',   hoverShadow: 'hover:shadow-amber-500/10'   }} onClick={() => setActiveTab('findings')} />
                <StatCard icon={GitBranch}     label="Relationships"  count={counts.correlations}  active={activeTab === 'correlations'}  color={{ border: 'border-blue-500/20 hover:border-blue-500/35',     iconBg: 'bg-blue-500/10',    iconText: 'text-blue-400',    text: 'text-blue-400',    hoverShadow: 'hover:shadow-blue-500/10'    }} onClick={() => setActiveTab('correlations')} />
                <StatCard icon={AlertTriangle} label="Anomalies"      count={counts.anomalies}     active={activeTab === 'anomalies'}     color={{ border: 'border-red-500/20 hover:border-red-500/35',       iconBg: 'bg-red-500/10',     iconText: 'text-red-400',     text: 'text-red-400',     hoverShadow: 'hover:shadow-red-500/10'     }} onClick={() => setActiveTab('anomalies')} />
                <StatCard icon={TrendingUp}    label="Trends"         count={counts.trends}        active={activeTab === 'trends'}        color={{ border: 'border-emerald-500/20 hover:border-emerald-500/35',iconBg: 'bg-emerald-500/10', iconText: 'text-emerald-400', text: 'text-emerald-400', hoverShadow: 'hover:shadow-emerald-500/10' }} onClick={() => setActiveTab('trends')} />
                <StatCard icon={Layers}        label="Segments"       count={counts.segments}      active={activeTab === 'segments'}      color={{ border: 'border-purple-500/20 hover:border-purple-500/35', iconBg: 'bg-purple-500/10',  iconText: 'text-purple-400',  text: 'text-purple-400',  hoverShadow: 'hover:shadow-purple-500/10'  }} onClick={() => setActiveTab('segments')} />
                <StatCard icon={Cpu}           label="Drivers"        count={counts.drivers}       active={activeTab === 'drivers'}       color={{ border: 'border-violet-500/20 hover:border-violet-500/35', iconBg: 'bg-violet-500/10',  iconText: 'text-violet-400',  text: 'text-violet-400',  hoverShadow: 'hover:shadow-violet-500/10'  }} onClick={() => setActiveTab('drivers')} />
            </motion.div>

            {/* ── Tab Navigation ── */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.12 }}
            >
                <div className="border-b border-[var(--surface-border)]">
                    <div className="flex gap-0.5 overflow-x-auto pb-px scrollbar-none -mb-px">
                        {TABS.map(tab => {
                            const isActive = activeTab === tab.id;
                            const tabCount = tab.countKey ? counts[tab.countKey] : null;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={cn(
                                        'relative flex items-center gap-1.5 px-3 py-2.5 text-[13px] font-semibold whitespace-nowrap',
                                        'rounded-t-lg transition-all duration-200 border-b-2',
                                        isActive
                                            ? 'text-[var(--accent-primary)] border-[var(--accent-primary)] bg-[var(--accent-primary-muted)]'
                                            : 'text-[var(--page-muted)] border-transparent hover:text-[var(--page-text)] hover:bg-[var(--surface-2)]',
                                    )}
                                >
                                    <tab.icon className="w-3.5 h-3.5" />
                                    {tab.label}
                                    {tabCount > 0 && (
                                        <span className={cn(
                                            'text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[16px] text-center',
                                            isActive
                                                ? 'bg-[var(--accent-primary-muted)] text-[var(--accent-primary)]'
                                                : 'bg-[var(--surface-2)] text-[var(--page-muted)]',
                                        )}>
                                            {tabCount}
                                        </span>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                </div>
            </motion.div>

            {/* ── Tab Content ── */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                >
                    {activeTab === 'overview' && (
                        <div className="space-y-5">
                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                                <DataQualityCard quality={data.data_quality} />
                                <div className="lg:col-span-2">
                                    <ExecutiveSummary
                                        summary={data.executive_summary}
                                        datasetName={data.dataset_name}
                                        domain={data.domain}
                                        storyHeadline={data.story_headline}
                                        dataPersonality={data.data_personality}
                                        aiNarrated={data.ai_narrated}
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                {data.key_findings?.length > 0 && (
                                    <KeyFindings
                                        findings={data.key_findings.slice(0, 4)}
                                        compact
                                        onViewAll={() => setActiveTab('findings')}
                                        onInvestigate={investigateInChat}
                                    />
                                )}
                                {data.recommendations?.length > 0 && (
                                    <Recommendations
                                        recommendations={data.recommendations.slice(0, 4)}
                                        compact
                                        onViewAll={() => setActiveTab('recommendations')}
                                        onInvestigate={investigateInChat}
                                    />
                                )}
                            </div>
                            {data.correlations?.length > 0 && (
                                <CorrelationExplorer
                                    correlations={data.correlations.slice(0, 6)}
                                    compact
                                    onViewAll={() => setActiveTab('correlations')}
                                    onInvestigate={investigateInChat}
                                />
                            )}
                            {data.driver_analysis?.length > 0 && (
                                <DriverAnalysis
                                    drivers={data.driver_analysis.slice(0, 2)}
                                    onInvestigate={investigateInChat}
                                />
                            )}
                        </div>
                    )}

                    {activeTab === 'findings' && (
                        <KeyFindings findings={data.key_findings || []} onInvestigate={investigateInChat} />
                    )}

                    {activeTab === 'correlations' && (
                        <div className="space-y-5">
                            <CorrelationExplorer correlations={data.correlations || []} onInvestigate={investigateInChat} />
                            {data.distributions?.length > 0 && (
                                <DistributionInsights distributions={data.distributions} onInvestigate={investigateInChat} />
                            )}
                        </div>
                    )}

                    {activeTab === 'anomalies' && (
                        <AnomalySpotlight anomalies={data.anomalies || []} onInvestigate={investigateInChat} />
                    )}

                    {activeTab === 'trends' && (
                        <TrendAnalysis trends={data.trends || []} onInvestigate={investigateInChat} />
                    )}

                    {activeTab === 'segments' && (
                        <SegmentAnalysis segments={data.segments || []} onInvestigate={investigateInChat} />
                    )}

                    {activeTab === 'drivers' && (
                        <DriverAnalysis drivers={data.driver_analysis || []} onInvestigate={investigateInChat} />
                    )}

                    {activeTab === 'recommendations' && (
                        <Recommendations recommendations={data.recommendations || []} onInvestigate={investigateInChat} />
                    )}
                </motion.div>
            </AnimatePresence>
        </div>
    );
};

export default InsightsPage;
