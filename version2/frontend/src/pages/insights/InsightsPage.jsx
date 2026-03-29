import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useScroll, useSpring, AnimatePresence } from 'framer-motion';
import {
    RefreshCw, AlertCircle, Database, MessageSquare, Clock, ChevronRight,
    FileText, Calendar, ShieldCheck, TrendingUp,
    ArrowRight, Zap, AlertTriangle, Layers,
    Cpu, Shield, Users, Link2, ChevronDown, ChevronUp, Info, Sparkles,
    BarChart3, Target, Eye, BookOpen, Download, Loader2,
} from 'lucide-react';
import { reportsAPI, getAuthToken } from '../../services/api';
import {
    AreaChart, Area, ResponsiveContainer, ScatterChart, Scatter,
    XAxis, YAxis, ZAxis, Tooltip, BarChart, Bar, Cell,
} from 'recharts';
import useDatasetStore from '../../store/datasetStore';
import useDashboardActionStore from '../../store/dashboardActionStore';
import { useInsightsData } from './hooks/useInsightsData';
import { cn } from '../../lib/utils';
import { renderBold } from '../../lib/renderBold';
import ExecutiveSummary from './components/ExecutiveSummary';
import { StoryReader, StoryPlaceholder } from './components/story';
import './insights-editorial.css';

const MotionDiv = motion.div;


// ═══════════════════════════════════════════════════════════
//  CONSTANTS & HELPERS
// ═══════════════════════════════════════════════════════════

const ICON_BY_TYPE = {
    trend: TrendingUp, anomaly: AlertTriangle, correlation: Link2,
    segment: Users, summary: Sparkles, distribution: BarChart3,
    driver: Cpu, comparison: Target, hidden_pattern: Eye,
};

const CHART_COLORS = {
    primary: '#3B82F6',
    emerald: '#34D399',
    amber: '#FBBF24',
    red: '#F87171',
    purple: '#A78BFA',
};

const toScatter = (arr = []) =>
    arr.slice(0, 16).map((v, i) => ({
        x: Number(v?.x ?? v?.value ?? i * 7 + 5),
        y: Number(v?.y ?? v?.score ?? (i + 1) * 6),
        z: Number(v?.z ?? 100),
    }));

const severityColor = (sev) => {
    if (sev === 'high' || sev === 'critical') return 'text-red-400';
    if (sev === 'medium') return 'text-amber-400';
    return 'text-emerald-400';
};

const stripMarkdown = (text) => {
    if (!text) return '';
    return text.replace(/\*\*/g, '').replace(/\*/g, '').replace(/⚠️/g, '').replace(/⚡/g, '').replace(/📈/g, '').replace(/📉/g, '');
};


// ═══════════════════════════════════════════════════════════
//  EMPTY / LOADING / ERROR STATES
// ═══════════════════════════════════════════════════════════

const EmptyState = ({ onUpload }) => (
    <div className="insights-editorial-page min-h-[70vh] flex items-center justify-center" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="text-center max-w-md mx-auto px-6">
            <div className="relative w-20 h-20 mx-auto mb-6">
                <div className="absolute inset-0 rounded-3xl bg-blue-500/10 animate-pulse" />
                <div className="relative w-full h-full rounded-3xl flex items-center justify-center border border-blue-500/20 bg-slate-900">
                    <Database className="w-10 h-10 text-blue-400" />
                </div>
            </div>
            <h2 className="text-2xl font-bold mb-3 text-slate-100">No Dataset Selected</h2>
            <p className="text-sm leading-relaxed mb-8 text-slate-400">
                Select a dataset to generate the narrative intelligence report.
            </p>
            <button onClick={onUpload}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-white text-sm font-medium rounded-xl transition-all bg-blue-600 hover:bg-blue-500">
                <Database className="w-4 h-4" /> Upload a Dataset
            </button>
        </div>
    </div>
);

const LoadingSkeleton = ({ title = 'Preparing Narrative Intelligence', description = 'We are assembling the latest story, evidence, and action plan for this dataset.' }) => (
    <div className="insights-editorial-page min-h-screen" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="report-container py-16 space-y-8 animate-pulse">
            <div className="space-y-4">
                <div className="h-4 w-32 rounded-lg" style={{ background: 'var(--surface-2)' }} />
                <div className="h-16 w-3/4 rounded-2xl" style={{ background: 'var(--surface-2)' }} />
                <div className="h-6 w-2/3 rounded-lg" style={{ background: 'var(--surface-2)' }} />
            </div>
            <div className="space-y-2 max-w-2xl">
                <h2 className="text-2xl font-semibold" style={{ color: 'var(--ink)' }}>{title}</h2>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-soft)' }}>{description}</p>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
                {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-36 rounded-2xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }} />
                ))}
            </div>
            <div className="space-y-6">
                {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-48 rounded-2xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }} />
                ))}
            </div>
        </div>
    </div>
);

const ErrorState = ({ error, onRetry }) => (
    <div className="insights-editorial-page min-h-[50vh] flex items-center justify-center">
        <div className="text-center max-w-md px-6">
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl flex items-center justify-center"
                 style={{ background: 'var(--red-bg)', border: '1px solid rgba(248,113,113,0.2)' }}>
                <AlertCircle className="w-7 h-7 text-red-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Analysis Failed</h3>
            <p className="text-sm mb-5 leading-relaxed" style={{ color: 'var(--ink-muted)' }}>{error}</p>
            <button onClick={onRetry}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-xl transition-colors"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-vis)' }}>
                <RefreshCw className="w-4 h-4" /> Retry Analysis
            </button>
        </div>
    </div>
);

const ArtifactBanner = ({ selectedDataset, artifactStatus, reportStatus, onRefresh }) => {
    const processingProgress = selectedDataset?.processing_progress || 0;
    const processingStatus = selectedDataset?.processing_status || 'processing';
    const insightsError = selectedDataset?.artifact_status?.insights_error;

    if (selectedDataset?.is_processed === false) {
        return (
            <div className="report-container pt-6">
                <div className="surface-card p-4 flex items-center justify-between gap-4">
                    <div>
                        <div className="text-sm font-semibold">Dataset analysis in progress</div>
                        <div className="text-xs" style={{ color: 'var(--ink-soft)' }}>
                            {processingStatus.replace(/_/g, ' ')} · {processingProgress}%
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (artifactStatus === 'pending' || artifactStatus === 'generating') {
        return (
            <div className="report-container pt-6">
                <div className="surface-card p-4 flex items-center justify-between gap-4">
                    <div>
                        <div className="text-sm font-semibold">Preparing intelligence brief</div>
                        <div className="text-xs" style={{ color: 'var(--ink-soft)' }}>
                            Your dataset is processed. The executive story and action plan are being assembled now.
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (artifactStatus === 'failed') {
        return (
            <div className="report-container pt-6">
                <div className="surface-card p-4 flex items-center justify-between gap-4">
                    <div>
                        <div className="text-sm font-semibold text-red-400">Insights preparation failed</div>
                        <div className="text-xs" style={{ color: 'var(--ink-soft)' }}>
                            {insightsError || 'The background report generation failed. You can retry now.'}
                        </div>
                    </div>
                    <button onClick={onRefresh} className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'var(--surface-2)' }}>
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    if (reportStatus === 'cached') {
        return (
            <div className="report-container pt-6">
                <div className="surface-card p-4 flex items-center justify-between gap-4">
                    <div>
                        <div className="text-sm font-semibold">Showing ready report</div>
                        <div className="text-xs" style={{ color: 'var(--ink-soft)' }}>
                            This narrative brief was prepared in the background and loaded from cache for speed.
                        </div>
                    </div>
                    <button onClick={onRefresh} className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'var(--surface-2)' }}>
                        Refresh
                    </button>
                </div>
            </div>
        );
    }

    return null;
};


// ═══════════════════════════════════════════════════════════
//  ① THE HOOK — Report Header
// ═══════════════════════════════════════════════════════════

const ReportHeader = ({ datasetName, reportId, headline, summary, qualityScore, generatedAt, domain, totalRows, totalCols }) => (
    <header className="pt-20 pb-16 ambient-glow" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="report-container relative z-10">
            <MotionDiv initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="space-y-10">
                {/* Meta Row */}
                <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-5">
                        <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4" style={{ color: 'var(--ink-dim)' }} />
                            <span className="label-caps">{reportId}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4" style={{ color: 'var(--ink-dim)' }} />
                            <span className="label-caps">
                                {generatedAt ? new Date(generatedAt).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : 'Generated Today'}
                            </span>
                        </div>
                        {domain && domain !== 'general' && (
                            <span className="label-caps px-2.5 py-0.5 rounded-md" style={{ background: 'var(--accent-glow)', color: 'var(--accent-hot)' }}>
                                {domain}
                            </span>
                        )}
                    </div>
                    {typeof qualityScore === 'number' && (
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full"
                             style={{ background: 'var(--emerald-bg)', border: '1px solid rgba(52,211,153,0.15)' }}>
                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                                {qualityScore}% Data Quality
                            </span>
                        </div>
                    )}
                </div>

                {/* Headline */}
                <div className="space-y-6 max-w-4xl">
                    <h1 className="serif text-5xl md:text-6xl lg:text-[4.5rem] font-light leading-[1.08] tracking-tight">
                        {headline || 'Narrative Intelligence Report'}
                    </h1>
                    <div className="flex gap-6 items-start">
                        <div className="w-10 h-px mt-4 flex-shrink-0" style={{ background: 'var(--accent)' }} />
                        <p className="text-lg font-light leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
                            {summary || 'A strategic narrative generated from patterns, outliers, and relationships in your data.'}
                        </p>
                    </div>
                </div>

                {/* Dataset Context */}
                <div className="flex flex-wrap items-center gap-6 pt-2">
                    <div className="flex items-center gap-2">
                        <span className="label-caps">Source:</span>
                        <span className="text-sm font-medium" style={{ color: 'var(--accent-hot)' }}>{datasetName}</span>
                    </div>
                    {totalRows && (
                        <div className="flex items-center gap-2">
                            <span className="label-caps">Rows:</span>
                            <span className="text-sm font-medium" style={{ color: 'var(--ink-soft)' }}>{Number(totalRows).toLocaleString()}</span>
                        </div>
                    )}
                    {totalCols && (
                        <div className="flex items-center gap-2">
                            <span className="label-caps">Columns:</span>
                            <span className="text-sm font-medium" style={{ color: 'var(--ink-soft)' }}>{totalCols}</span>
                        </div>
                    )}
                </div>
            </MotionDiv>
        </div>
    </header>
);


// ═══════════════════════════════════════════════════════════
//  ② THE SCOREBOARD — KPI Grid
// ═══════════════════════════════════════════════════════════

const MetricGrid = ({ kpis }) => (
    <section className="py-14" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="report-container">
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
                {kpis.map((kpi, i) => (
                    <motion.div key={kpi.label}
                        initial={{ opacity: 0, y: 12 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.08 }}
                        viewport={{ once: true }}
                        className="surface-card glow-hover p-5 space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="label-caps">{kpi.label}</span>
                            {kpi.badge && (
                                <span className={cn('text-[10px] font-bold uppercase tracking-wider', kpi.badgeTone)}>
                                    {kpi.badge}
                                </span>
                            )}
                        </div>
                        <div className="text-3xl font-light tracking-tight stat-value">{kpi.value}</div>
                        <p className="text-[11px] font-light leading-relaxed" style={{ color: 'var(--ink-dim)' }}>{kpi.description}</p>
                    </motion.div>
                ))}
            </div>
        </div>
    </section>
);


// ═══════════════════════════════════════════════════════════
//  ③ DATA TRUST — Compact Quality Badge Row
// ═══════════════════════════════════════════════════════════

const DataTrustBar = ({ quality, counts }) => {
    const items = [
        { icon: Shield, label: 'Health', value: `${quality.health_score || 0}%`, color: (quality.health_score || 0) >= 80 ? 'text-emerald-400' : 'text-amber-400' },
        { icon: Zap, label: 'Findings', value: counts.key_findings || 0, color: 'text-blue-400' },
        { icon: Link2, label: 'Correlations', value: counts.correlations || 0, color: 'text-purple-400' },
        { icon: AlertTriangle, label: 'Anomalies', value: counts.anomalies || 0, color: counts.anomalies > 0 ? 'text-red-400' : 'text-slate-500' },
        { icon: TrendingUp, label: 'Trends', value: counts.trends || 0, color: 'text-emerald-400' },
        { icon: Layers, label: 'Segments', value: counts.segments || 0, color: 'text-amber-400' },
        { icon: Cpu, label: 'Drivers', value: counts.drivers || 0, color: 'text-cyan-400' },
    ];

    return (
        <section className="py-8" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="report-container">
                <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-3">
                    {items.map((item) => (
                        <div key={item.label} className="surface-card p-3.5 flex flex-col items-start">
                            <div className="w-7 h-7 rounded-lg flex items-center justify-center mb-2" style={{ background: 'var(--surface-2)' }}>
                                <item.icon className={cn('w-3.5 h-3.5', item.color)} />
                            </div>
                            <div className="text-xl font-bold stat-value">{item.value}</div>
                            <div className="text-[11px] mt-0.5 font-medium" style={{ color: 'var(--ink-dim)' }}>{item.label}</div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
};


// ═══════════════════════════════════════════════════════════
//  CHAPTER SECTION — Story-Arc Layout
// ═══════════════════════════════════════════════════════════

const ChapterSection = ({ chapterNum, title, narrative, findingCount, children }) => (
    <section className="py-20" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="report-container">
            <div className="grid lg:grid-cols-12 gap-12">
                {/* Sticky sidebar */}
                <div className="lg:col-span-4 lg:sticky lg:top-28 h-fit space-y-6">
                    <div className="relative">
                        <span className="chapter-num">{chapterNum}</span>
                        <div className="relative z-10 pt-8 space-y-4">
                            <h2 className="serif text-4xl font-light leading-tight">{title}</h2>
                            <p className="font-light leading-relaxed" style={{ color: 'var(--ink-soft)' }}>{narrative}</p>
                        </div>
                    </div>
                    {typeof findingCount === 'number' && findingCount > 0 && (
                        <div className="pt-4">
                            <div className="label-caps mb-1.5">Section Findings</div>
                            <div className="text-xs font-bold" style={{ color: 'var(--accent)' }}>{findingCount} Insight{findingCount !== 1 ? 's' : ''} Identified</div>
                        </div>
                    )}
                </div>
                {/* Content */}
                <div className="lg:col-span-8">{children}</div>
            </div>
        </div>
    </section>
);


// ═══════════════════════════════════════════════════════════
//  INSIGHT CARD — Dark Narrative Card
// ═══════════════════════════════════════════════════════════

const InsightCard = ({ insight, onInvestigate, investigateContext = {} }) => {
    const [showProof, setShowProof] = useState(false);
    const Icon = ICON_BY_TYPE[insight.type] || Info;

    const hasTrendData = insight.type === 'trend' && Array.isArray(insight.data) && insight.data.length > 1;
    const hasScatterData = ['correlation', 'distribution', 'anomaly'].includes(insight.type) && Array.isArray(insight.data) && insight.data.length > 1;
    const hasBarData = insight.type === 'driver' && Array.isArray(insight.data) && insight.data.length > 0;

    return (
        <motion.div initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
            className="py-10" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="grid lg:grid-cols-12 gap-10">
                {/* Narrative Side */}
                <div className="lg:col-span-5 space-y-5">
                    <div className="flex items-center gap-3 flex-wrap">
                        <div className="p-2 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                            <Icon className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                        </div>
                        <span className="label-caps">{insight.type}</span>
                        {insight.severity && (
                            <span className={cn('tag-chip', severityColor(insight.severity))}>
                                {insight.severity}
                            </span>
                        )}
                        {(insight.tags || []).slice(0, 2).map((tag) => (
                            <span key={tag} className="tag-chip">{tag}</span>
                        ))}
                    </div>

                    <div className="space-y-3">
                        <h3 className="serif text-2xl md:text-3xl font-medium leading-tight">{stripMarkdown(insight.title)}</h3>
                        <p className="font-light leading-relaxed text-[15px]" style={{ color: 'var(--ink-soft)' }}>
                            {renderBold(insight.description)}
                        </p>
                    </div>

                    {insight.value && (
                        <div className="text-3xl font-light tracking-tight gradient-text">{stripMarkdown(insight.value)}</div>
                    )}

                    <div className="flex items-center gap-4 pt-1">
                        {insight.context && (
                            <button onClick={() => setShowProof((v) => !v)}
                                className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors"
                                style={{ color: 'var(--accent)' }}>
                                {showProof ? 'Hide Proof' : 'Statistical Proof'}
                                {showProof ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                            </button>
                        )}
                        {onInvestigate && (
                            <button onClick={() => onInvestigate(insight, investigateContext)}
                                className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors"
                                style={{ color: 'var(--ink-dim)' }}>
                                <MessageSquare className="w-3 h-3" /> Ask AI
                            </button>
                        )}
                    </div>
                </div>

                {/* Visualization Side */}
                <div className="lg:col-span-7">
                    {hasTrendData ? (
                        <div className="chart-container h-56">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={insight.data}>
                                    <XAxis dataKey="name" tick={{ fill: '#64748B', fontSize: 10 }} axisLine={false} tickLine={false} />
                                    <YAxis hide />
                                    <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid rgba(148,163,184,0.14)', borderRadius: '12px', color: '#F1F5F9' }} />
                                    <Area type="monotone" dataKey="value" stroke={CHART_COLORS.primary} fill={CHART_COLORS.primary} fillOpacity={0.08} strokeWidth={2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    ) : hasScatterData ? (
                        <div className="chart-container h-56">
                            <ResponsiveContainer width="100%" height="100%">
                                <ScatterChart>
                                    <XAxis type="number" dataKey="x" tick={{ fill: '#64748B', fontSize: 10 }} axisLine={false} tickLine={false} />
                                    <YAxis type="number" dataKey="y" tick={{ fill: '#64748B', fontSize: 10 }} axisLine={false} tickLine={false} />
                                    <ZAxis type="number" range={[40, 180]} />
                                    <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid rgba(148,163,184,0.14)', borderRadius: '12px', color: '#F1F5F9' }}
                                             cursor={{ stroke: 'rgba(148,163,184,0.2)', strokeDasharray: '3 3' }} />
                                    <Scatter data={insight.data} fill={CHART_COLORS.purple} fillOpacity={0.6} />
                                </ScatterChart>
                            </ResponsiveContainer>
                        </div>
                    ) : hasBarData ? (
                        <div className="chart-container h-56">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={insight.data} layout="vertical">
                                    <XAxis type="number" tick={{ fill: '#64748B', fontSize: 10 }} axisLine={false} tickLine={false} />
                                    <YAxis type="category" dataKey="name" tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={false} tickLine={false} width={100} />
                                    <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid rgba(148,163,184,0.14)', borderRadius: '12px', color: '#F1F5F9' }} />
                                    <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                                        {insight.data.map((_, idx) => (
                                            <Cell key={idx} fill={idx === 0 ? CHART_COLORS.primary : idx === 1 ? CHART_COLORS.purple : CHART_COLORS.emerald} fillOpacity={0.7} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="h-56 w-full flex items-center justify-center rounded-2xl"
                             style={{ background: 'var(--surface-1)', border: '1px dashed var(--border-vis)' }}>
                            <div className="text-center space-y-2">
                                <BookOpen className="w-7 h-7 mx-auto" style={{ color: 'var(--surface-3)' }} />
                                <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--ink-dim)' }}>Narrative Finding</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Statistical Proof Panel */}
            <AnimatePresence>
                {showProof && insight.context && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                        className="mt-8 analyst-panel grid md:grid-cols-4 gap-6 overflow-hidden">
                        <div className="space-y-1.5">
                            <div className="label-caps" style={{ fontSize: '9px' }}>Confidence</div>
                            <div className="font-bold">{insight.context.confidence || '95% CI'}</div>
                        </div>
                        <div className="space-y-1.5">
                            <div className="label-caps" style={{ fontSize: '9px' }}>Sample Size</div>
                            <div className="font-bold">N = {insight.context.sampleSize || 'Full dataset'}</div>
                        </div>
                        <div className="space-y-1.5">
                            <div className="label-caps" style={{ fontSize: '9px' }}>Methodology</div>
                            <div style={{ color: 'var(--ink-soft)' }}>{insight.context.methodology || 'Statistical extraction'}</div>
                        </div>
                        <div className="space-y-1.5">
                            <div className="label-caps" style={{ fontSize: '9px' }}>Evidence Tier</div>
                            <div className={cn('font-bold',
                                insight.context.evidenceTier === 'strong' ? 'text-emerald-400' :
                                insight.context.evidenceTier === 'moderate' ? 'text-amber-400' : 'text-slate-400')}>
                                {(insight.context.evidenceTier || 'assessed').toUpperCase()}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};


// ═══════════════════════════════════════════════════════════
//  ⑦ STRATEGIC ACTION PLAN
// ═══════════════════════════════════════════════════════════

const ActionPlan = ({ recommendations, onInvestigate, investigateContext = {} }) => (
    <section className="py-24" style={{ background: 'var(--surface-1)', borderBottom: '1px solid var(--border)' }}>
        <div className="report-container">
            <div className="grid lg:grid-cols-12 gap-16">
                <div className="lg:col-span-4 space-y-6">
                    <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                         style={{ background: 'var(--accent)', boxShadow: '0 0 40px rgba(59,130,246,0.2)' }}>
                        <Target className="w-6 h-6 text-white" />
                    </div>
                    <div className="space-y-4">
                        <h2 className="serif text-4xl font-light leading-tight">Strategic Action Plan</h2>
                        <p className="font-light leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
                            Recommended operational moves ranked by urgency and evidence strength. Each action is data-backed.
                        </p>
                    </div>
                </div>

                <div className="lg:col-span-8 space-y-5">
                    {recommendations.length === 0 ? (
                        <div className="surface-card p-8 text-sm" style={{ color: 'var(--ink-muted)' }}>
                            No recommendations were generated for this dataset yet.
                        </div>
                    ) : recommendations.map((rec, index) => {
                        const urgency = rec.urgency_score || 50;
                        const urgencyColor = urgency >= 80 ? 'text-red-400' : urgency >= 50 ? 'text-amber-400' : 'text-emerald-400';
                        return (
                            <motion.div key={rec.id || index}
                                initial={{ opacity: 0, x: 10 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                transition={{ delay: index * 0.06 }}
                                viewport={{ once: true }}
                                className="rec-card group">
                                <div className="flex items-start gap-5">
                                    <div className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center mt-0.5"
                                         style={{ background: 'var(--accent-glow)', border: '1px solid rgba(59,130,246,0.2)' }}>
                                        <span className="text-sm font-bold" style={{ color: 'var(--accent)' }}>{index + 1}</span>
                                    </div>
                                    <div className="flex-grow space-y-3">
                                        <div className="flex items-center gap-3 flex-wrap">
                                            <span className="label-caps" style={{ color: 'var(--accent)' }}>{rec.category || 'Action'}</span>
                                            <div className="w-1 h-1 rounded-full" style={{ background: 'var(--surface-3)' }} />
                                            <span className={cn('text-[10px] uppercase font-bold', urgencyColor)}>
                                                {urgency >= 80 ? 'Critical' : urgency >= 50 ? 'Important' : 'Suggested'}
                                            </span>
                                            {rec.urgency_score && (
                                                <span className="text-[10px] font-mono" style={{ color: 'var(--ink-dim)' }}>
                                                    score: {Math.round(rec.urgency_score)}
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-lg font-medium group-hover:text-blue-400 transition-colors">
                                            {stripMarkdown(rec.title || rec.text || rec.recommendation || 'Recommended action')}
                                        </p>
                                        <p className="text-sm font-light leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
                                            {renderBold(rec.description || rec.rationale || '')}
                                        </p>
                                        <button onClick={() => onInvestigate({ title: rec.title || rec.text, description: rec.description || rec.rationale }, { ...investigateContext, type: 'recommendation', title: rec.title })}
                                            className="text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--accent)' }}>
                                            Investigate in chat →
                                        </button>
                                    </div>
                                    <ArrowRight className="w-5 h-5 flex-shrink-0 mt-1 group-hover:translate-x-1 transition-transform"
                                        style={{ color: 'var(--ink-dim)' }} />
                                </div>
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </div>
    </section>
);


// ═══════════════════════════════════════════════════════════
//  ⑧ METHODOLOGY APPENDIX (REMOVED)
// ═══════════════════════════════════════════════════════════
// const MethodologyFooter = ({ data, quality }) => (
//     ... component removed ...
// );



// ═══════════════════════════════════════════════════════════
//  EMPTY CHAPTER PLACEHOLDER
// ═══════════════════════════════════════════════════════════

const EmptyChapter = ({ label }) => (
    <div className="surface-card p-8 text-center">
        <BookOpen className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--surface-3)' }} />
        <p className="text-sm" style={{ color: 'var(--ink-dim)' }}>
            No {label} were detected in this dataset.
        </p>
    </div>
);


// ═══════════════════════════════════════════════════════════
//  DOWNLOAD BUTTON — standalone with its own loading state
// ═══════════════════════════════════════════════════════════

const DownloadReportButton = ({ datasetId, datasetName }) => {
    const [downloading, setDownloading] = useState(false);

    const handleDownload = async () => {
        if (!datasetId || downloading) return;
        setDownloading(true);
        try {
            const token = getAuthToken();
            const url = reportsAPI.downloadPDF(datasetId);
            const response = await fetch(url, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = objectUrl;
            link.download = `analysis-report-${(datasetName || 'dataset').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.pdf`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(objectUrl);
        } catch (err) {
            console.error('PDF download error:', err);
            alert('Failed to download PDF. Please try again.');
        } finally {
            setDownloading(false);
        }
    };

    return (
        <button
            onClick={handleDownload}
            disabled={downloading || !datasetId}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', color: '#fff' }}
        >
            {downloading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</>
            ) : (
                <><Download className="w-4 h-4" /> Download Report</>
            )}
        </button>
    );
};


// ═══════════════════════════════════════════════════════════
//  MAIN PAGE COMPONENT
// ═══════════════════════════════════════════════════════════

const InsightsPage = () => {
    const { selectedDataset } = useDatasetStore();
    const navigate = useNavigate();
    const { loading, error, data, filters, refresh, artifactStatus, storyStatus } = useInsightsData(selectedDataset);

    // Sync loading/refresh to store for Header access (individual selectors prevent re-render loops)
    const setInsightsLoading = useDashboardActionStore((s) => s.setInsightsLoading);
    const setOnInsightsRefresh = useDashboardActionStore((s) => s.setOnInsightsRefresh);
    useEffect(() => { setInsightsLoading(loading); }, [loading, setInsightsLoading]);
    useEffect(() => { setOnInsightsRefresh(refresh); }, [refresh, setOnInsightsRefresh]);

    const { scrollYProgress } = useScroll();
    const scaleX = useSpring(scrollYProgress, { stiffness: 100, damping: 30, restDelta: 0.001 });

    const hasStory = data?.story && data?.is_story_available;
    const isStoryGenerating = storyStatus === 'generating' || storyStatus === 'not_started';
    const datasetId = selectedDataset?.id || selectedDataset?._id || data?.dataset_id;
    const datasetName = data?.dataset_name || selectedDataset?.name;

    const investigateInChat = useCallback((queryOrInsight, context = {}) => {
        const baseQuery = typeof queryOrInsight === 'string'
            ? queryOrInsight
            : `Investigate: ${queryOrInsight.title}. ${queryOrInsight.description || ''}`;
        const qualityScore = data?.data_quality?.health_score;
        const rowCount = data?.data_quality?.total_rows;
        const contextPrefix = context.chapter
            ? `[Context: "${context.chapter}" section of "${datasetName}" analysis. ${qualityScore ? `Data quality: ${qualityScore}%.` : ''} ${rowCount ? `${rowCount.toLocaleString()} rows.` : ''}]`
            : `[Context: Analyzing "${datasetName}". ${qualityScore ? `Data quality: ${qualityScore}%.` : ''} ${rowCount ? `${rowCount.toLocaleString()} rows.` : ''}]`;
        window.dispatchEvent(new CustomEvent('open-chat-with-query', {
            detail: {
                query: `${contextPrefix}\n\n${baseQuery}`,
                source: 'analysis-page',
                insightContext: { type: context.type || 'general', chapter: context.chapter || null },
                datasetContext: { name: datasetName, qualityScore, rowCount, colCount: data?.data_quality?.total_columns },
            }
        }));
    }, [data, datasetName]);

    // ── Map backend response → story-arc structure ──
    const report = useMemo(() => {
        if (!data) return null;
        const q = data.data_quality || {};
        const c = data.counts || {};
        const storyArc = data.story_arc || {};

        const keyFindings = (data.key_findings || []).map((item, idx) => ({
            id: `kf-${idx}`,
            type: item.category || item.type?.replace(' ', '_')?.toLowerCase() || 'summary',
            title: item.title || item.type || 'Key Finding',
            description: item.plain_english || item.description || '',
            value: item.impact || null,
            severity: item.severity || 'medium',
            tags: [item.type, item.category].filter(Boolean),
            context: {
                confidence: item.evidence?.p_value !== undefined ? `p = ${item.evidence.p_value}` : '95% CI',
                sampleSize: item.evidence?.sample_size,
                methodology: item.evidence?.methodology || item.type,
                evidenceTier: item.evidence_tier || 'assessed',
            },
        }));

        const trends = (data.trends || []).map((item, idx) => ({
            id: `tr-${idx}`,
            type: 'trend',
            title: `${(item.direction || 'trend').charAt(0).toUpperCase() + (item.direction || 'trend').slice(1)} trend in ${item.column || 'metric'}`,
            description: item.plain_english || '',
            value: item.strength !== undefined ? `τ = ${Number(item.strength).toFixed(3)}` : null,
            severity: item.is_significant ? 'high' : 'medium',
            tags: [item.column, item.direction, item.seasonality].filter(Boolean),
            data: (item.series || []).slice(0, 20).map((p, i) => ({ name: p.name || p.x || String(i + 1), value: Number(p.value ?? p.y ?? i + 1) })),
            context: { confidence: item.p_value !== undefined ? `p = ${Number(item.p_value).toFixed(4)}` : '95% CI', methodology: 'Mann-Kendall trend test', evidenceTier: item.is_significant ? 'strong' : 'moderate' },
        }));

        const correlations = (data.correlations || []).map((item, idx) => ({
            id: `co-${idx}`,
            type: 'correlation',
            title: `${item.column1 || 'X'} ↔ ${item.column2 || 'Y'}`,
            description: item.plain_english || `${item.strength} ${item.direction} correlation (r = ${item.value})`,
            value: item.value !== undefined ? `r = ${Number(item.value).toFixed(3)}` : null,
            severity: item.severity || (Math.abs(item.value) >= 0.7 ? 'high' : 'medium'),
            tags: [item.column1, item.column2, item.strength].filter(Boolean),
            data: toScatter(item.points || []),
            context: { confidence: item.p_value !== undefined ? `p = ${Number(item.p_value).toFixed(5)}` : '95% CI', methodology: `${item.method || 'Pearson'} correlation`, evidenceTier: item.abs_value >= 0.7 ? 'strong' : item.abs_value >= 0.4 ? 'moderate' : 'weak', sampleSize: null },
        }));

        const distributions = (data.distributions || []).map((item, idx) => ({
            id: `di-${idx}`,
            type: 'distribution',
            title: `Distribution of ${item.column || 'variable'}`,
            description: item.plain_english || '',
            value: item.skewness !== undefined ? `Skew = ${Number(item.skewness).toFixed(2)}` : null,
            severity: item.severity || 'medium',
            tags: [item.column, item.distribution_type].filter(Boolean),
            data: toScatter(item.points || item.buckets || []),
            context: { confidence: item.normality_p_value !== undefined ? `Normality p = ${item.normality_p_value}` : 'N/A', methodology: 'Distribution profiling', evidenceTier: Math.abs(item.skewness || 0) > 1.5 ? 'strong' : 'moderate' },
        }));

        const anomalies = (data.anomalies || []).map((item, idx) => ({
            id: `an-${idx}`,
            type: 'anomaly',
            title: `Outliers in ${item.column || 'variable'}`,
            description: item.plain_english || `${item.count} outliers detected (${item.percentage}%)`,
            value: item.percentage !== undefined ? `${item.percentage}% anomalous` : null,
            severity: item.severity || 'medium',
            tags: [item.column, item.method].filter(Boolean),
            data: toScatter(item.points || item.outliers || []),
            context: { methodology: item.method || 'IQR outlier detection', evidenceTier: item.severity === 'high' ? 'strong' : 'moderate' },
        }));

        const segments = (data.segments || []).map((item, idx) => ({
            id: `sg-${idx}`,
            type: 'segment',
            title: item.segment || 'Segment contrast',
            description: item.plain_english || '',
            value: item.deviation !== undefined ? `${Number(item.deviation).toFixed(1)}σ deviation` : null,
            severity: item.severity || 'medium',
            tags: [item.column, item.direction].filter(Boolean),
            context: { methodology: 'Segment contrast analysis', evidenceTier: (item.deviation || 0) > 2 ? 'strong' : 'moderate' },
        }));

        const drivers = (data.driver_analysis || []).map((item, idx) => ({
            id: `dr-${idx}`,
            type: 'driver',
            title: `Drivers of ${item.target || 'target'}`,
            description: item.plain_english || '',
            value: null,
            severity: 'medium',
            tags: [item.target, item.method].filter(Boolean),
            data: (item.drivers || []).slice(0, 6).map((d) => ({ name: d.column || d.driver || 'Unknown', value: Math.round((d.importance || 0) * 1000) / 10 })),
            context: { methodology: 'Mutual Information ranking', evidenceTier: 'moderate' },
        }));

        const ch1 = [...keyFindings, ...trends].slice(0, 10);
        const ch2 = [...correlations, ...drivers, ...distributions].slice(0, 10);
        const ch3 = [...anomalies, ...segments].slice(0, 10);

        const health = Number(q.health_score || 0);
        const totalFindings = Number(c.key_findings || keyFindings.length);
        const totalCorrs = Number(c.correlations || correlations.length);
        const totalAnoms = Number(c.anomalies || anomalies.length);

        const kpis = [
            { label: 'Data Health', value: `${health}%`, badge: q.health_label || 'Assessed', badgeTone: health >= 80 ? 'text-emerald-400' : health >= 65 ? 'text-amber-400' : 'text-red-400', description: `Completeness ${q.completeness || 0}% · Uniqueness ${q.uniqueness || 0}%` },
            { label: 'Rows Analysed', value: Number(q.total_rows || 0).toLocaleString(), badge: `${q.total_columns || 0} cols`, badgeTone: 'text-blue-400', description: data.applied_filters ? `Filtered subset across ${Object.keys(data.applied_filters).length} condition(s).` : 'Full dataset included in this report.' },
            { label: 'Strong Signals', value: `${totalFindings + totalCorrs}`, badge: `${totalCorrs} relationships`, badgeTone: 'text-purple-400', description: 'Findings and relationships with enough evidence to shape decisions.' },
            { label: 'Action Items', value: `${(data.recommendations || []).length}`, badge: `${totalAnoms} risk flags`, badgeTone: totalAnoms > 0 ? 'text-red-400' : 'text-emerald-400', description: 'Prioritized actions derived from the strongest patterns and risks.' },
        ];

        return { kpis, ch1, ch2, ch3, quality: q, counts: c, storyArc };
    }, [data]);

    // ── Guards ──
    if (!selectedDataset) return <EmptyState onUpload={() => navigate('/app/datasets')} />;
    if (loading && !data) {
        const pendingArtifact = artifactStatus === 'pending' || artifactStatus === 'generating';
        return (
            <LoadingSkeleton
                title={pendingArtifact ? 'Preparing Analysis' : 'Loading Analysis'}
                description={pendingArtifact
                    ? 'Your dataset is processed. We are now preparing the narrative, evidence sections, and action plan.'
                    : 'Fetching the latest analysis for this dataset.'}
            />
        );
    }
    if (error && !data) return <ErrorState error={error} onRetry={refresh} />;
    if (!data || !report) return <LoadingSkeleton />;

    const reportId = `AN-${String(datasetId || '0000').slice(-6).toUpperCase()}`;

    return (
        <div className="insights-editorial-page min-h-screen pb-0" style={{ backgroundColor: 'var(--bg-primary)' }}>
            {/* Scroll progress bar */}
            <motion.div
                className="fixed top-0 left-0 right-0 h-0.5 z-50 origin-left"
                style={{ scaleX, background: 'linear-gradient(90deg,#6366f1,#8b5cf6)' }}
            />

            <ArtifactBanner
                selectedDataset={selectedDataset}
                artifactStatus={artifactStatus}
                reportStatus={data?.report_status}
                onRefresh={refresh}
            />

            {/* ── TOP BAR ── dataset name + download button */}
            <div className="sticky top-0 z-40 border-b" style={{ borderColor: 'var(--border)', background: 'rgba(10,12,20,0.92)', backdropFilter: 'blur(16px)' }}>
                <div className="report-container py-2.5 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <Sparkles className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                        <span className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
                            {datasetName}
                        </span>
                        <span className="text-[11px] px-2 py-0.5 rounded-md font-medium" style={{ background: 'var(--surface-1)', color: 'var(--ink-dim)' }}>
                            {reportId}
                        </span>
                        {isStoryGenerating && !hasStory && (
                            <span className="flex items-center gap-1.5 text-xs text-slate-500">
                                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse inline-block" />
                                Narrative generating…
                            </span>
                        )}
                    </div>
                    <DownloadReportButton datasetId={datasetId} datasetName={datasetName} />
                </div>
            </div>

            {/* ── NARRATIVE STORY (when available) ── */}
            <AnimatePresence mode="wait">
                {hasStory ? (
                    <motion.div
                        key="story-section"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.4 }}
                    >
                        <StoryReader
                            story={data.story}
                            datasetName={datasetName}
                            datasetId={datasetId}
                            onInvestigate={investigateInChat}
                            onSwitchToReport={null}
                        />
                        {/* Divider between story and detailed analysis */}
                        <div className="report-container py-6">
                            <div className="flex items-center gap-4">
                                <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                                <span className="text-xs font-semibold uppercase tracking-widest px-4" style={{ color: 'var(--ink-dim)' }}>
                                    Detailed Analysis
                                </span>
                                <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                            </div>
                        </div>
                    </motion.div>
                ) : isStoryGenerating ? (
                    <motion.div
                        key="story-generating"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                    >
                        <StoryPlaceholder />
                    </motion.div>
                ) : null}
            </AnimatePresence>

            {/* ── DETAILED ANALYSIS REPORT ── always visible */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.1 }}
            >
                {/* ── ① THE HOOK ── */}
                <ReportHeader
                    datasetName={datasetName}
                    reportId={reportId}
                    headline={data.story_headline || datasetName || 'Analysis Report'}
                    summary={report.storyArc?.hook || data.executive_summary}
                    qualityScore={report.quality.health_score}
                    generatedAt={data.generated_at}
                    domain={data.domain}
                    totalRows={report.quality.total_rows}
                    totalCols={report.quality.total_columns}
                />

                <section className="py-12" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="report-container">
                        <ExecutiveSummary
                            summary={data.executive_summary}
                            storyHeadline={data.story_headline}
                            dataPersonality={data.data_personality}
                            aiNarrated={data.ai_narrated}
                        />
                    </div>
                </section>

                {/* ── ② THE SCOREBOARD ── */}
                <MetricGrid kpis={report.kpis} />

                {/* ── ③ DATA TRUST BAR ── */}
                <DataTrustBar quality={report.quality} counts={report.counts} />

                {/* ── ④ CHAPTER 1: What's Happening ── */}
                <ChapterSection chapterNum="I" title="What's Happening"
                    narrative={report.storyArc?.chapters?.happening || 'The most significant signals and temporal patterns in your data.'}
                    findingCount={report.ch1.length}>
                    {report.ch1.length === 0
                        ? <EmptyChapter label="key findings or trends" />
                        : report.ch1.map((insight) => <InsightCard key={insight.id} insight={insight} onInvestigate={investigateInChat} investigateContext={{ chapter: "I: What's Happening", type: insight.type }} />)
                    }
                </ChapterSection>

                {/* ── ⑤ CHAPTER 2: Why It's Happening ── */}
                <ChapterSection chapterNum="II" title="Why It's Happening"
                    narrative={report.storyArc?.chapters?.drivers || 'The driving forces behind the patterns. Correlations reveal relationships, drivers quantify influence.'}
                    findingCount={report.ch2.length}>
                    {report.ch2.length === 0
                        ? <EmptyChapter label="correlations, drivers, or distributions" />
                        : report.ch2.map((insight) => <InsightCard key={insight.id} insight={insight} onInvestigate={investigateInChat} investigateContext={{ chapter: "II: Why It's Happening", type: insight.type }} />)
                    }
                </ChapterSection>

                {/* ── ⑥ CHAPTER 3: What's At Risk ── */}
                <ChapterSection chapterNum="III" title="What's At Risk"
                    narrative={report.storyArc?.chapters?.risks || 'Anomalies that deviate from expected behavior and segments where patterns diverge.'}
                    findingCount={report.ch3.length}>
                    {report.ch3.length === 0
                        ? <EmptyChapter label="anomalies or segments" />
                        : report.ch3.map((insight) => <InsightCard key={insight.id} insight={insight} onInvestigate={investigateInChat} investigateContext={{ chapter: "III: What's At Risk", type: insight.type }} />)
                    }
                </ChapterSection>

                {/* ── ⑦ STRATEGIC ACTION PLAN ── */}
                <ActionPlan
                    recommendations={data.recommendations || []}
                    onInvestigate={investigateInChat}
                    investigateContext={{ chapter: 'Strategic Action Plan', type: 'recommendation' }}
                />
            </motion.div>
        </div>
    );
};

export default InsightsPage;
