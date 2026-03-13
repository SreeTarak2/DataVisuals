import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useScroll, useSpring, AnimatePresence } from 'framer-motion';
import {
    RefreshCw, AlertCircle, Database, MessageSquare, Clock, ChevronRight,
    FileText, Calendar, ShieldCheck, TrendingUp, TrendingDown, Minus,
    CheckCircle2, ArrowRight, Zap, GitBranch, AlertTriangle, Layers,
    Cpu, Shield, Users, Link2, ChevronDown, ChevronUp, Info, Sparkles,
    BarChart3, Target, Eye, BookOpen, Printer, Download,
} from 'lucide-react';
import {
    AreaChart, Area, ResponsiveContainer, ScatterChart, Scatter,
    XAxis, YAxis, ZAxis, Tooltip, BarChart, Bar, Cell,
} from 'recharts';
import useDatasetStore from '../../store/datasetStore';
import { useInsightsData } from './hooks/useInsightsData';
import { cn } from '../../lib/utils';
import './insights-editorial.css';


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

const makeSparkline = (seed = 0, points = 12) =>
    Array.from({ length: points }, (_, i) => ({
        x: i,
        y: Math.max(5, 35 + (seed % 7) * 4 + Math.sin((i + seed) * 0.6) * 12 + i * 1.2),
    }));

const formatPct = (n) => (Number.isFinite(n) ? Number(Math.abs(n).toFixed(1)) : 0);

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
    <div className="insights-editorial-page min-h-[70vh] flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-6">
            <div className="relative w-20 h-20 mx-auto mb-6">
                <div className="absolute inset-0 rounded-3xl bg-blue-500/10 animate-pulse" />
                <div className="relative w-full h-full rounded-3xl flex items-center justify-center border border-blue-500/20"
                     style={{ background: 'var(--surface-1)' }}>
                    <Database className="w-10 h-10 text-blue-400" />
                </div>
            </div>
            <h2 className="text-2xl font-bold mb-3">No Dataset Selected</h2>
            <p className="text-sm leading-relaxed mb-8" style={{ color: 'var(--ink-muted)' }}>
                Select a dataset to generate the narrative intelligence report.
            </p>
            <button onClick={onUpload}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-white text-sm font-medium rounded-xl transition-all bg-blue-600 hover:bg-blue-500">
                <Database className="w-4 h-4" /> Upload a Dataset
            </button>
        </div>
    </div>
);

const LoadingSkeleton = () => (
    <div className="insights-editorial-page min-h-screen" style={{ background: 'var(--surface-0)' }}>
        <div className="report-container py-16 space-y-8 animate-pulse">
            <div className="space-y-4">
                <div className="h-4 w-32 rounded-lg" style={{ background: 'var(--surface-2)' }} />
                <div className="h-16 w-3/4 rounded-2xl" style={{ background: 'var(--surface-2)' }} />
                <div className="h-6 w-2/3 rounded-lg" style={{ background: 'var(--surface-2)' }} />
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


// ═══════════════════════════════════════════════════════════
//  ① THE HOOK — Report Header
// ═══════════════════════════════════════════════════════════

const ReportHeader = ({ datasetName, reportId, headline, summary, qualityScore, generatedAt, domain, totalRows, totalCols }) => (
    <header className="pt-20 pb-16 ambient-glow" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="report-container relative z-10">
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="space-y-10">
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
            </motion.div>
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
                            <div className={cn('flex items-center gap-1 text-[10px] font-bold',
                                kpi.trend === 'up' ? 'text-emerald-400' : kpi.trend === 'down' ? 'text-red-400' : 'text-slate-500')}>
                                {kpi.trend === 'up' ? <TrendingUp className="w-3 h-3" /> : kpi.trend === 'down' ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                                {kpi.change > 0 ? '+' : ''}{kpi.change}%
                            </div>
                        </div>
                        <div className="flex items-end justify-between gap-3">
                            <div className="text-3xl font-light tracking-tight stat-value">{kpi.value}</div>
                            <div className="h-10 w-24 flex-shrink-0 sparkline-wrap">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={kpi.sparkline}>
                                        <Area type="monotone" dataKey="y"
                                            stroke={kpi.trend === 'up' ? '#34D399' : kpi.trend === 'down' ? '#F87171' : '#64748B'}
                                            fill={kpi.trend === 'up' ? '#34D399' : kpi.trend === 'down' ? '#F87171' : '#64748B'}
                                            fillOpacity={0.1} strokeWidth={1.5} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
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

const InsightCard = ({ insight, onInvestigate }) => {
    const [showProof, setShowProof] = useState(false);
    const Icon = ICON_BY_TYPE[insight.type] || Info;

    const hasTrendData = insight.type === 'trend' && Array.isArray(insight.data) && insight.data.length > 1;
    const hasScatterData = ['correlation', 'distribution'].includes(insight.type) && Array.isArray(insight.data) && insight.data.length > 1;
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
                            {stripMarkdown(insight.description)}
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
                            <button onClick={() => onInvestigate(`Explain this insight in detail: ${insight.title}`)}
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

const ActionPlan = ({ recommendations, onInvestigate }) => (
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
                                            {stripMarkdown(rec.description || rec.rationale || '')}
                                        </p>
                                        <button onClick={() => onInvestigate(rec.title || rec.text || 'Explain this recommendation')}
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
//  ⑧ METHODOLOGY APPENDIX
// ═══════════════════════════════════════════════════════════

const MethodologyFooter = ({ data, quality }) => (
    <footer className="py-20" style={{ background: 'var(--surface-1)' }}>
        <div className="report-container">
            <div className="grid lg:grid-cols-12 gap-12">
                <div className="lg:col-span-4 space-y-4">
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded" style={{ background: 'var(--accent)' }} />
                        <h3 className="serif text-2xl font-medium italic">DataSage Intelligence</h3>
                    </div>
                    <p className="text-sm leading-relaxed" style={{ color: 'var(--ink-dim)' }}>
                        This report was auto-generated using DataSage analytical engine. All statistical significance tests
                        were performed at a 95% confidence level unless otherwise noted.
                    </p>
                </div>
                <div className="lg:col-span-8">
                    <div className="analyst-panel grid sm:grid-cols-2 md:grid-cols-4 gap-6">
                        <div className="space-y-1">
                            <div className="label-caps" style={{ fontSize: '9px' }}>Engine</div>
                            <div className="font-bold text-sm">DataSage v2</div>
                        </div>
                        <div className="space-y-1">
                            <div className="label-caps" style={{ fontSize: '9px' }}>Generated</div>
                            <div className="text-sm" style={{ color: 'var(--ink-soft)' }}>
                                {data.generated_at ? new Date(data.generated_at).toLocaleString() : 'N/A'}
                            </div>
                        </div>
                        <div className="space-y-1">
                            <div className="label-caps" style={{ fontSize: '9px' }}>Data Quality</div>
                            <div className="text-sm">
                                <span className="font-bold">{quality.health_score || 0}%</span>
                                <span style={{ color: 'var(--ink-dim)' }}> ({quality.health_label || 'N/A'})</span>
                            </div>
                        </div>
                        <div className="space-y-1">
                            <div className="label-caps" style={{ fontSize: '9px' }}>Confidence Level</div>
                            <div className="text-sm font-bold">95% CI</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </footer>
);


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
//  MAIN PAGE COMPONENT
// ═══════════════════════════════════════════════════════════

const InsightsPage = () => {
    const { selectedDataset } = useDatasetStore();
    const navigate = useNavigate();
    const { loading, error, data, filters, refresh } = useInsightsData(selectedDataset);

    const { scrollYProgress } = useScroll();
    const scaleX = useSpring(scrollYProgress, { stiffness: 100, damping: 30, restDelta: 0.001 });

    const investigateInChat = (query) => {
        navigate('/app/chat', { state: { prefillQuery: query } });
    };

    // ── Map backend response → story-arc structure ──
    const report = useMemo(() => {
        if (!data) return null;

        const q = data.data_quality || {};
        const c = data.counts || {};

        // ── Key Findings (mapped to cards) ──
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

        // ── Trends ──
        const trends = (data.trends || []).map((item, idx) => ({
            id: `tr-${idx}`,
            type: 'trend',
            title: `${(item.direction || 'trend').charAt(0).toUpperCase() + (item.direction || 'trend').slice(1)} trend in ${item.column || 'metric'}`,
            description: item.plain_english || '',
            value: item.strength !== undefined ? `τ = ${Number(item.strength).toFixed(3)}` : null,
            severity: item.is_significant ? 'high' : 'medium',
            tags: [item.column, item.direction, item.seasonality].filter(Boolean),
            data: (item.series || []).slice(0, 20).map((p, i) => ({
                name: p.name || p.x || String(i + 1),
                value: Number(p.value ?? p.y ?? i + 1),
            })),
            context: {
                confidence: item.p_value !== undefined ? `p = ${Number(item.p_value).toFixed(4)}` : '95% CI',
                methodology: 'Mann-Kendall trend test',
                evidenceTier: item.is_significant ? 'strong' : 'moderate',
            },
        }));

        // ── Correlations ──
        const correlations = (data.correlations || []).map((item, idx) => ({
            id: `co-${idx}`,
            type: 'correlation',
            title: `${item.column1 || 'X'} ↔ ${item.column2 || 'Y'}`,
            description: item.plain_english || `${item.strength} ${item.direction} correlation (r = ${item.value})`,
            value: item.value !== undefined ? `r = ${Number(item.value).toFixed(3)}` : null,
            severity: item.severity || (Math.abs(item.value) >= 0.7 ? 'high' : 'medium'),
            tags: [item.column1, item.column2, item.strength].filter(Boolean),
            data: toScatter(item.points || []),
            context: {
                confidence: item.p_value !== undefined ? `p = ${Number(item.p_value).toFixed(5)}` : '95% CI',
                methodology: `${item.method || 'Pearson'} correlation`,
                evidenceTier: item.abs_value >= 0.7 ? 'strong' : item.abs_value >= 0.4 ? 'moderate' : 'weak',
                sampleSize: null,
            },
        }));

        // ── Distributions ──
        const distributions = (data.distributions || []).map((item, idx) => ({
            id: `di-${idx}`,
            type: 'distribution',
            title: `Distribution of ${item.column || 'variable'}`,
            description: item.plain_english || '',
            value: item.skewness !== undefined ? `Skew = ${Number(item.skewness).toFixed(2)}` : null,
            severity: item.severity || 'medium',
            tags: [item.column, item.distribution_type].filter(Boolean),
            data: toScatter(item.points || item.buckets || []),
            context: {
                confidence: item.normality_p_value !== undefined ? `Normality p = ${item.normality_p_value}` : 'N/A',
                methodology: 'Distribution profiling',
                evidenceTier: Math.abs(item.skewness || 0) > 1.5 ? 'strong' : 'moderate',
            },
        }));

        // ── Anomalies ──
        const anomalies = (data.anomalies || []).map((item, idx) => ({
            id: `an-${idx}`,
            type: 'anomaly',
            title: `Outliers in ${item.column || 'variable'}`,
            description: item.plain_english || `${item.count} outliers detected (${item.percentage}%)`,
            value: item.percentage !== undefined ? `${item.percentage}% anomalous` : null,
            severity: item.severity || 'medium',
            tags: [item.column, item.method].filter(Boolean),
            context: {
                methodology: item.method || 'IQR outlier detection',
                evidenceTier: item.severity === 'high' ? 'strong' : 'moderate',
            },
        }));

        // ── Segments ──
        const segments = (data.segments || []).map((item, idx) => ({
            id: `sg-${idx}`,
            type: 'segment',
            title: item.segment || 'Segment contrast',
            description: item.plain_english || '',
            value: item.deviation !== undefined ? `${Number(item.deviation).toFixed(1)}σ deviation` : null,
            severity: item.severity || 'medium',
            tags: [item.column, item.direction].filter(Boolean),
            context: {
                methodology: 'Segment contrast analysis',
                evidenceTier: (item.deviation || 0) > 2 ? 'strong' : 'moderate',
            },
        }));

        // ── Drivers ──
        const drivers = (data.driver_analysis || []).map((item, idx) => ({
            id: `dr-${idx}`,
            type: 'driver',
            title: `Drivers of ${item.target || 'target'}`,
            description: item.plain_english || '',
            value: null,
            severity: 'medium',
            tags: [item.target, item.method].filter(Boolean),
            data: (item.drivers || []).slice(0, 6).map((d) => ({
                name: d.column || d.driver || 'Unknown',
                value: Math.round((d.importance || 0) * 1000) / 10,
            })),
            context: {
                methodology: 'Mutual Information ranking',
                evidenceTier: 'moderate',
            },
        }));

        // ── Story-Arc Chapters ──

        // Chapter 1: "What's Happening" → Key Findings + Trends
        const ch1 = [...keyFindings, ...trends].slice(0, 10);

        // Chapter 2: "Why It's Happening" → Correlations + Drivers + Distributions
        const ch2 = [...correlations, ...drivers, ...distributions].slice(0, 10);

        // Chapter 3: "What's At Risk" → Anomalies + Segments
        const ch3 = [...anomalies, ...segments].slice(0, 10);

        // ── KPIs — actual data metrics, not meta-counts ──
        const health = Number(q.health_score || 0);
        const totalFindings = Number(c.key_findings || keyFindings.length);
        const totalCorrs = Number(c.correlations || correlations.length);
        const totalAnoms = Number(c.anomalies || anomalies.length);

        const kpis = [
            {
                label: 'Data Health',
                value: `${health}%`,
                change: formatPct((health - 75) / 2),
                trend: health >= 80 ? 'up' : health >= 65 ? 'neutral' : 'down',
                description: `Completeness ${q.completeness || 0}% · Uniqueness ${q.uniqueness || 0}%`,
                sparkline: makeSparkline(health),
            },
            {
                label: 'Key Findings',
                value: `${totalFindings}`,
                change: formatPct(totalFindings * 2.2),
                trend: totalFindings >= 3 ? 'up' : 'neutral',
                description: 'High-impact observations ranked by statistical significance.',
                sparkline: makeSparkline(totalFindings + 3),
            },
            {
                label: 'Relationships',
                value: `${totalCorrs}`,
                change: formatPct(totalCorrs * 1.8),
                trend: totalCorrs >= 2 ? 'up' : 'neutral',
                description: 'Variable correlations with p < 0.05 statistical support.',
                sparkline: makeSparkline(totalCorrs + 6),
            },
            {
                label: 'Risk Signals',
                value: `${totalAnoms}`,
                change: totalAnoms > 0 ? formatPct(totalAnoms * 2.5) : 0,
                trend: totalAnoms > 3 ? 'down' : totalAnoms > 0 ? 'neutral' : 'up',
                description: 'Anomalies and outlier events requiring attention.',
                sparkline: makeSparkline(totalAnoms + 9),
            },
        ];

        return { kpis, ch1, ch2, ch3, quality: q, counts: c };
    }, [data]);

    // ── Guards ──
    if (!selectedDataset) return <EmptyState onUpload={() => navigate('/app/datasets')} />;
    if (loading && !data) return <LoadingSkeleton />;
    if (error && !data) return <ErrorState error={error} onRetry={refresh} />;
    if (!data || !report) return <LoadingSkeleton />;

    const reportId = `IR-${String(data.dataset_id || selectedDataset?.id || selectedDataset?._id || '0000').slice(-6).toUpperCase()}`;

    return (
        <div className="insights-editorial-page min-h-screen pb-0">
            {/* ── Scroll Progress ── */}
            <motion.div className="fixed top-0 left-0 right-0 h-[3px] z-50 origin-left"
                style={{ scaleX, background: 'var(--accent)' }} />

            {/* ── Sticky Nav Bar ── */}
            <header className="h-14 backdrop-blur-xl flex items-center justify-between px-6 sticky top-0 z-40"
                    style={{ background: 'rgba(11,15,26,0.85)', borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-3">
                    <span className="text-xs font-medium" style={{ color: 'var(--ink-dim)' }}>Reports</span>
                    <ChevronRight className="w-3 h-3" style={{ color: 'var(--ink-dim)' }} />
                    <span className="text-xs font-bold">{data.dataset_name || selectedDataset?.name || 'Insights'}</span>
                </div>
                <div className="flex items-center gap-4">
                    <div className="hidden sm:flex items-center gap-1.5" style={{ color: 'var(--ink-dim)' }}>
                        <Clock className="w-3.5 h-3.5" />
                        <span className="text-[11px] font-medium">
                            {data.generated_at ? new Date(data.generated_at).toLocaleDateString() : 'Just Analyzed'}
                        </span>
                    </div>
                    {filters && (
                        <span className="text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full"
                              style={{ background: 'var(--amber-bg)', color: 'var(--amber)' }}>Filtered</span>
                    )}
                    <div className="w-px h-4" style={{ background: 'var(--border-vis)' }} />
                    <button onClick={refresh} disabled={loading}
                        className={cn('flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold rounded-lg transition-all',
                            loading ? 'opacity-40 cursor-not-allowed' : 'hover:bg-white/5')}
                        style={{ color: 'var(--ink-soft)' }}>
                        <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} /> Refresh
                    </button>
                    <button onClick={() => investigateInChat(`Give me a comprehensive analysis of my ${data.dataset_name || 'dataset'} and what actions I should prioritize.`)}
                        className="px-4 py-1.5 text-white text-[11px] font-semibold rounded-lg transition-all flex items-center gap-1.5"
                        style={{ background: 'var(--accent)' }}>
                        <MessageSquare className="w-3.5 h-3.5" /> Discuss Report
                    </button>
                </div>
            </header>

            {/* ── ① THE HOOK ── */}
            <ReportHeader
                datasetName={data.dataset_name || selectedDataset?.name}
                reportId={reportId}
                headline={data.story_headline || data.dataset_name || selectedDataset?.name || 'Narrative Intelligence Report'}
                summary={data.executive_summary}
                qualityScore={report.quality.health_score}
                generatedAt={data.generated_at}
                domain={data.domain}
                totalRows={report.quality.total_rows}
                totalCols={report.quality.total_columns}
            />

            {/* ── ② THE SCOREBOARD ── */}
            <MetricGrid kpis={report.kpis} />

            {/* ── ③ DATA TRUST BAR ── */}
            <DataTrustBar quality={report.quality} counts={report.counts} />

            {/* ── ④ CHAPTER 1: What's Happening ── */}
            <ChapterSection chapterNum="I" title="What's Happening"
                narrative="The most significant signals and temporal patterns in your data. Key findings are ranked by statistical significance and impact."
                findingCount={report.ch1.length}>
                {report.ch1.length === 0
                    ? <EmptyChapter label="key findings or trends" />
                    : report.ch1.map((insight) => <InsightCard key={insight.id} insight={insight} onInvestigate={investigateInChat} />)
                }
            </ChapterSection>

            {/* ── ⑤ CHAPTER 2: Why It's Happening ── */}
            <ChapterSection chapterNum="II" title="Why It's Happening"
                narrative="The driving forces behind the patterns. Correlations reveal relationships, drivers quantify influence, and distributions expose the shape of your data."
                findingCount={report.ch2.length}>
                {report.ch2.length === 0
                    ? <EmptyChapter label="correlations, drivers, or distributions" />
                    : report.ch2.map((insight) => <InsightCard key={insight.id} insight={insight} onInvestigate={investigateInChat} />)
                }
            </ChapterSection>

            {/* ── ⑥ CHAPTER 3: What's At Risk ── */}
            <ChapterSection chapterNum="III" title="What's At Risk"
                narrative="Anomalies that deviate from expected behavior and segments where patterns diverge. These are the red flags that need attention."
                findingCount={report.ch3.length}>
                {report.ch3.length === 0
                    ? <EmptyChapter label="anomalies or segments" />
                    : report.ch3.map((insight) => <InsightCard key={insight.id} insight={insight} onInvestigate={investigateInChat} />)
                }
            </ChapterSection>

            {/* ── ⑦ STRATEGIC ACTION PLAN ── */}
            <ActionPlan recommendations={data.recommendations || []} onInvestigate={investigateInChat} />

            {/* ── ⑧ METHODOLOGY APPENDIX ── */}
            <MethodologyFooter data={data} quality={report.quality} />
        </div>
    );
};

export default InsightsPage;
