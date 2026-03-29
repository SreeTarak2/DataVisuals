/**
 * InsightsBar — v3.0
 *
 * What changed vs v2.0:
 * - Surfaces effect_size, p_value, columns that the backend sends but v2 never rendered
 * - Stops stripping statistical context (humanizeDescription was removing r-values etc.)
 * - Summary card shows parsed stat-chips extracted from the description text
 * - Insight card: column pills + visual effect bar replace the two generic sub-boxes
 * - Tighter layout: more findings visible without scrolling
 */

import React, { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Zap, TrendingUp, AlertTriangle, Lightbulb,
    ChevronDown, ChevronUp, Activity, BarChart3,
    MessageSquare, Copy, Check, ArrowRight, Sparkles,
    Eye, FileText, ShieldAlert, GitBranch, Layers,
} from 'lucide-react';
import useChatStore from '../../../store/chatStore';
import useDatasetStore from '../../../store/datasetStore';
import InsightFeedback from '../../../components/features/feedback/InsightFeedback';

// ── Icon mapping ──────────────────────────────────────────────────────────────
const ICON_MAP = {
    success: Sparkles, info: Activity, warning: AlertTriangle,
    trend: TrendingUp, anomaly: AlertTriangle, correlation: GitBranch,
    distribution: BarChart3, recommendation: Lightbulb,
    subspace: Eye, default: Zap,
};

// ── Accent colours per type (inline-style safe — no Tailwind arbitrary values) ──
const ACCENTS = {
    success: { primary: '#34d399', bg: 'rgba(52,211,153,0.08)', border: 'rgba(52,211,153,0.22)', leftBorder: '#34d399' },
    info: { primary: '#60a5fa', bg: 'rgba(96,165,250,0.08)', border: 'rgba(96,165,250,0.22)', leftBorder: '#60a5fa' },
    warning: { primary: '#fbbf24', bg: 'rgba(251,191,36,0.08)', border: 'rgba(251,191,36,0.22)', leftBorder: '#fbbf24' },
    trend: { primary: '#a78bfa', bg: 'rgba(167,139,250,0.08)', border: 'rgba(167,139,250,0.22)', leftBorder: '#a78bfa' },
    default: { primary: '#94a3b8', bg: 'rgba(148,163,184,0.08)', border: 'rgba(148,163,184,0.20)', leftBorder: '#94a3b8' },
};

const VISIBLE_COUNT = 3;

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Clean junk punctuation but KEEP r-values and numbers — they're useful context. */
const cleanDescription = (desc) => {
    if (!desc) return '';
    return desc
        .replace(/\.{2,}/g, '.')
        .replace(/\s{2,}/g, ' ')
        .trim();
};

/** Convert numeric effect_size → label + bar fill % */
const effectLabel = (e) => {
    if (e == null) return null;
    const abs = Math.abs(e);
    if (abs >= 0.8) return { text: 'Very strong', pct: 95, color: '#34d399' };
    if (abs >= 0.6) return { text: 'Strong', pct: 78, color: '#34d399' };
    if (abs >= 0.4) return { text: 'Moderate', pct: 55, color: '#fbbf24' };
    if (abs >= 0.2) return { text: 'Weak', pct: 30, color: '#f87171' };
    return { text: 'Negligible', pct: 12, color: '#6b7280' };
};

/** Convert confidence number → qualitative label */
const confidenceLabel = (c) => {
    if (c >= 95) return { text: 'Very high', color: '#34d399' };
    if (c >= 80) return { text: 'High', color: '#60a5fa' };
    if (c >= 60) return { text: 'Moderate', color: '#fbbf24' };
    return { text: 'Low', color: '#94a3b8' };
};

const typeLabel = (t) => ({
    success: 'Key Finding', info: 'Relationship', warning: 'Anomaly',
    trend: 'Trend', correlation: 'Correlation', distribution: 'Distribution',
    subspace: 'Hidden Pattern', anomaly: 'Anomaly',
}[t] || 'Insight');

const severityClasses = (s) => s === 'high'
    ? { bg: 'rgba(239,68,68,0.10)', color: '#f87171', border: 'rgba(239,68,68,0.20)', label: 'Priority' }
    : s === 'medium'
        ? { bg: 'rgba(251,191,36,0.10)', color: '#fbbf24', border: 'rgba(251,191,36,0.20)', label: 'Review' }
        : { bg: 'rgba(148,163,184,0.08)', color: '#94a3b8', border: 'rgba(148,163,184,0.18)', label: 'Monitor' };

/**
 * Extract key numbers from the executive summary description text so we can
 * show them as stat chips rather than burying them in prose.
 * Patterns we look for: "N rows", "N columns", "N correlations", "N outliers"
 */
const extractSummaryChips = (description = '') => {
    const chips = [];
    const patterns = [
        { re: /([\d,]+)\s*rows?/i, label: 'Rows', icon: '⊞' },
        { re: /([\d,]+)\s*columns?/i, label: 'Columns', icon: '⊟' },
        { re: /([\d,]+)\s*(?:strong\s+)?correlations?/i, label: 'Correlations', icon: '⇌' },
        { re: /([\d,]+)\s*outliers?/i, label: 'Outliers', icon: '◉' },
        { re: /([\d,]+)\s*columns?\s+deviate/i, label: 'Non-normal cols', icon: '≠' },
    ];
    for (const { re, label, icon } of patterns) {
        const m = description.match(re);
        if (m) chips.push({ value: m[1], label, icon });
    }
    return chips;
};

// ── Sub-components ────────────────────────────────────────────────────────────

const ColumnPills = ({ columns = [] }) => {
    if (!columns.length) return null;
    return (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
            {columns.slice(0, 4).map(col => (
                <span key={col} style={{
                    fontSize: 10, fontWeight: 600,
                    padding: '2px 7px', borderRadius: 4,
                    background: 'rgba(99,102,241,0.12)',
                    border: '1px solid rgba(99,102,241,0.25)',
                    color: '#a5b4fc', letterSpacing: '0.02em',
                    fontFamily: 'monospace',
                }}>
                    {col.replace(/_/g, ' ')}
                </span>
            ))}
        </div>
    );
};

const EffectBar = ({ effectSize, pValue }) => {
    const ef = effectLabel(effectSize);
    if (!ef) return null;
    const pLabel = pValue != null
        ? pValue < 0.001 ? 'p<0.001' : pValue < 0.01 ? `p=${pValue.toFixed(3)}` : `p=${pValue.toFixed(2)}`
        : null;
    return (
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Bar */}
            <div style={{ flex: 1, height: 4, borderRadius: 3, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                <div style={{
                    height: '100%', width: `${ef.pct}%`, borderRadius: 3,
                    background: `linear-gradient(90deg, ${ef.color}80, ${ef.color})`,
                    transition: 'width 0.4s ease',
                }} />
            </div>
            {/* Label */}
            <span style={{ fontSize: 10, fontWeight: 600, color: ef.color, whiteSpace: 'nowrap', minWidth: 64 }}>
                {ef.text}
                {effectSize != null && (
                    <span style={{ opacity: 0.7, fontWeight: 400 }}> ({Math.abs(effectSize).toFixed(2)})</span>
                )}
            </span>
            {pLabel && (
                <span style={{
                    fontSize: 9, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
                    background: 'rgba(255,255,255,0.06)', color: '#6b7280',
                }}>
                    {pLabel}
                </span>
            )}
        </div>
    );
};

// ── Main component ────────────────────────────────────────────────────────────

const InsightsBar = ({ insights = [], loading = false }) => {
    const [expanded, setExpanded] = useState(false);
    const [copiedId, setCopiedId] = useState(null);
    const navigate = useNavigate();
    const { selectedDataset } = useDatasetStore();
    const selectedDatasetId = selectedDataset?.id || selectedDataset?._id || null;

    const { summary, findings } = useMemo(() => {
        const s = insights.find(i => i.id === 'executive_summary');
        const f = insights.filter(i => i.id !== 'executive_summary');
        return { summary: s, findings: f };
    }, [insights]);

    const handleInvestigate = useCallback((insight) => {
        if (!selectedDatasetId) return;
        const query = `Investigate this insight in detail: "${insight.title}". ${insight.description || ''} — provide deeper analysis, possible causes, and recommended actions.`;
        window.dispatchEvent(new CustomEvent('open-chat-with-query', { detail: { query } }));
    }, [selectedDatasetId]);

    const handleCopy = useCallback((insight) => {
        const text = `${insight.title}\n${insight.description || ''}`;
        navigator.clipboard.writeText(text).then(() => {
            setCopiedId(insight.id || insight.title);
            setTimeout(() => setCopiedId(null), 2000);
        });
    }, []);

    if (loading) {
        return (
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
                className="rounded-2xl p-6"
            >
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                        style={{ background: 'var(--accent-primary-light)', border: '1px solid var(--accent-primary)' }}>
                        <Sparkles className="w-5 h-5 animate-pulse" style={{ color: 'var(--accent-primary)' }} />
                    </div>
                    <div>
                        <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Analyzing your data…</p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>Finding the most important patterns</p>
                    </div>
                </div>
            </motion.div>
        );
    }

    if (!insights || insights.length === 0) return null;

    const visibleFindings = expanded ? findings : findings.slice(0, VISIBLE_COUNT);
    const hasMore = findings.length > VISIBLE_COUNT;

    return (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
            className="border rounded-2xl overflow-hidden"
        >
            {/* ── Header ── */}
            <div className="flex items-center justify-between px-5 pt-4 pb-3.5"
                style={{ borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                        style={{ background: 'var(--accent-primary-light)', border: '1px solid var(--accent-primary)' }}>
                        <Sparkles className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                    </div>
                    <div>
                        <h3 className="text-[14px] font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                            Key Insights
                        </h3>
                        <p className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                            AI-detected patterns &amp; signals
                        </p>
                    </div>
                </div>
                {findings.length > 0 && (
                    <span className="text-[11px] px-2.5 py-1 rounded-full"
                        style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                        {findings.length} finding{findings.length !== 1 ? 's' : ''}
                    </span>
                )}
            </div>

            <div className="px-4 pb-4 pt-3 space-y-3">
                {/* ── Summary card — stat chips + description ── */}
                {summary && (() => {
                    const chips = extractSummaryChips(summary.description || '');
                    return (
                        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                            className="rounded-xl p-4 group/summary"
                            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                        >
                            <div className="flex items-center gap-2 mb-3">
                                <FileText className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--accent-primary)' }} />
                                <span className="text-[12px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                                    Dataset Summary
                                </span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                                    style={{ background: 'var(--accent-primary-light)', color: 'var(--accent-primary)' }}>
                                    AI Generated
                                </span>
                            </div>

                            {/* Stat chips — extracted from the description text */}
                            {chips.length > 0 && (
                                <div className="flex flex-wrap gap-2 mb-3">
                                    {chips.map(chip => (
                                        <div key={chip.label} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg"
                                            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                                            <span style={{ fontSize: 12 }}>{chip.icon}</span>
                                            <span className="text-[13px] font-bold tabular-nums"
                                                style={{ color: 'var(--text-primary)' }}>{chip.value}</span>
                                            <span className="text-[10px]"
                                                style={{ color: 'var(--text-secondary)' }}>{chip.label}</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                {cleanDescription(summary.description)}
                            </p>

                            {/* Actions */}
                            <div className="flex items-center gap-2 mt-3 opacity-0 group-hover/summary:opacity-100 focus-within:opacity-100 transition-opacity duration-200">
                                <button onClick={() => handleInvestigate(summary)}
                                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all"
                                    style={{ border: '1px solid rgba(99,102,241,0.25)', color: 'rgba(165,180,252,0.7)' }}
                                >
                                    <MessageSquare className="w-3 h-3" />
                                    Ask AI about this
                                    <ArrowRight className="w-2.5 h-2.5" />
                                </button>
                                <button onClick={() => handleCopy(summary)}
                                    className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-all"
                                    style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                                >
                                    {copiedId === summary.id ? (
                                        <><Check className="w-3 h-3 text-emerald-400" /><span className="text-emerald-400">Copied</span></>
                                    ) : (
                                        <><Copy className="w-3 h-3" />Copy</>
                                    )}
                                </button>
                            </div>
                        </motion.div>
                    );
                })()}

                {/* ── Insight cards ── */}
                {visibleFindings.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                        <AnimatePresence mode="popLayout">
                            {visibleFindings.map((insight, i) => {
                                const type = insight.type || 'default';
                                const accent = ACCENTS[type] || ACCENTS.default;
                                const Icon = ICON_MAP[type] || ICON_MAP.default;
                                const insightId = insight.id || `insight-${i}`;
                                const isCopied = copiedId === (insight.id || insight.title);
                                const conf = confidenceLabel(insight.confidence);
                                const tLabel = typeLabel(type);
                                const sev = insight.severity ? severityClasses(insight.severity) : null;
                                const columns = insight.columns || [];
                                const hasEffect = insight.effect_size != null;

                                return (
                                    <motion.div key={insightId}
                                        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: -8 }}
                                        transition={{ delay: i * 0.05, duration: 0.22 }}
                                        className="flex flex-col rounded-xl overflow-hidden group/card transition-all duration-200 hover:shadow-lg"
                                        style={{
                                            background: 'var(--bg-elevated)',
                                            border: `1px solid var(--border)`,
                                            borderLeft: `3px solid ${accent.leftBorder}`,
                                        }}
                                    >
                                        {/* Card header */}
                                        <div className="px-3.5 pt-3 pb-2 flex items-center justify-between gap-2">
                                            <div className="flex items-center gap-2">
                                                <div className="w-5 h-5 rounded flex items-center justify-center shrink-0"
                                                    style={{ background: accent.bg, border: `1px solid ${accent.border}` }}>
                                                    <Icon className="w-3 h-3" style={{ color: accent.primary }} />
                                                </div>
                                                <span className="text-[10px] font-bold uppercase tracking-wider"
                                                    style={{ color: accent.primary }}>
                                                    {tLabel}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                                {sev && (
                                                    <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full border"
                                                        style={{ background: sev.bg, color: sev.color, borderColor: sev.border }}>
                                                        {sev.label}
                                                    </span>
                                                )}
                                                {insight.confidence != null && (
                                                    <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full"
                                                        style={{ color: conf.color, background: `${conf.color}15` }}>
                                                        {conf.text}
                                                    </span>
                                                )}
                                            </div>
                                        </div>

                                        {/* Title */}
                                        <div className="px-3.5">
                                            <p className="text-[13px] font-semibold leading-snug"
                                                style={{ color: 'var(--text-primary)' }}>
                                                {insight.title}
                                            </p>
                                        </div>

                                        {/* Column pills — show which fields are involved */}
                                        {columns.length > 0 && (
                                            <div className="px-3.5">
                                                <ColumnPills columns={columns} />
                                            </div>
                                        )}

                                        {/* Effect bar — visual strength of the finding */}
                                        {hasEffect && (
                                            <div className="px-3.5">
                                                <EffectBar effectSize={insight.effect_size} pValue={insight.p_value} />
                                            </div>
                                        )}

                                        {/* Description — keep stats, just clean whitespace */}
                                        <div className="px-3.5 mt-2 flex-1">
                                            <p className="text-[11.5px] leading-relaxed line-clamp-3"
                                                style={{ color: 'var(--text-secondary)' }}>
                                                {cleanDescription(insight.description)}
                                            </p>
                                        </div>

                                        {/* Inline action hint (replaces the two generic sub-boxes) */}
                                        {insight.recommended_action && (
                                            <div className="px-3.5 mt-2">
                                                <p className="text-[11px] leading-relaxed line-clamp-2"
                                                    style={{ color: 'var(--text-muted)' }}>
                                                    <span style={{ color: accent.primary, marginRight: 4 }}>→</span>
                                                    {insight.recommended_action}
                                                </p>
                                            </div>
                                        )}

                                        {/* Action buttons */}
                                        <div className="px-3.5 py-2.5 mt-1 flex items-center justify-between
                                            opacity-100 sm:opacity-0 sm:group-hover/card:opacity-100
                                            focus-within:opacity-100 transition-opacity duration-200"
                                            style={{ borderTop: '1px solid var(--border)' }}>
                                            <div className="flex items-center gap-1.5">
                                                <button onClick={() => handleInvestigate(insight)}
                                                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all"
                                                    style={{
                                                        border: `1px solid ${accent.border}`,
                                                        color: `${accent.primary}CC`,
                                                        background: 'transparent',
                                                    }}
                                                    onMouseEnter={e => e.currentTarget.style.background = accent.bg}
                                                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                                >
                                                    <MessageSquare className="w-3 h-3" />
                                                    Investigate
                                                    <ArrowRight className="w-2.5 h-2.5" />
                                                </button>
                                                <button onClick={() => handleCopy(insight)}
                                                    className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-all"
                                                    style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                                                >
                                                    {isCopied ? (
                                                        <><Check className="w-3 h-3 text-emerald-400" /><span className="text-emerald-400">Copied</span></>
                                                    ) : (
                                                        <><Copy className="w-3 h-3" />Copy</>
                                                    )}
                                                </button>
                                            </div>
                                            <InsightFeedback
                                                variant="compact"
                                                insightText={`${insight.title}. ${insight.description || ''}`}
                                                datasetId={selectedDatasetId}
                                            />
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                    </div>
                )}
            </div>

            {/* ── Show more / collapse ── */}
            {hasMore && (
                <button onClick={() => setExpanded(!expanded)}
                    className="w-full flex items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition-all"
                    style={{
                        borderTop: '1px solid var(--border)',
                        background: 'var(--bg-elevated)',
                        color: 'var(--accent-primary)',
                    }}
                >
                    {expanded ? (
                        <>Show fewer <ChevronUp className="w-3.5 h-3.5" /></>
                    ) : (
                        <>{findings.length - VISIBLE_COUNT} more insight{findings.length - VISIBLE_COUNT !== 1 ? 's' : ''} <ChevronDown className="w-3.5 h-3.5" /></>
                    )}
                </button>
            )}

            {/* ── Footer link ── */}
            {selectedDatasetId && (
                <div className="px-5 py-3" style={{ borderTop: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
                    <button onClick={() => navigate('/app/analysis')}
                        className="inline-flex items-center gap-2 text-[11.5px] font-medium transition-colors"
                        style={{ color: 'var(--accent-primary)' }}
                    >
                        Open the full intelligence report
                        <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                </div>
            )}
        </motion.div>
    );
};

export default InsightsBar;
