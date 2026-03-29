/**
 * PowerBIInsightCards
 *
 * A clean, minimalist insight card design matching the requested style.
 * - Icon on the left
 * - Title and description aligned to the right
 * - Important text (numbers, dates, metrics) highlighted in accent color.
 */

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    TrendingUp, AlertTriangle, Link2, Users, BarChart3,
    Cpu, Target, Eye, Sparkles, Info,
    ChevronDown, ChevronRight, MessageSquare, ChevronUp
} from 'lucide-react';
import {
    LineChart, Line, ScatterChart, Scatter,
    BarChart, Bar, XAxis, YAxis, ZAxis, ResponsiveContainer, Cell,
} from 'recharts';
import { cn } from '../../../lib/utils';

// ─── Config ──────────────────────────────────────────────────────────────────

const TYPE_META = {
    anomaly:      { label: 'Anomalies',    icon: AlertTriangle, color: '#ef4444' },
    trend:        { label: 'Trends',       icon: TrendingUp,    color: '#3b82f6' },
    correlation:  { label: 'Correlations', icon: Link2,         color: '#a78bfa' },
    driver:       { label: 'Drivers',      icon: Cpu,           color: '#22d3ee' },
    segment:      { label: 'Segments',     icon: Users,         color: '#f59e0b' },
    distribution: { label: 'Distribution', icon: BarChart3,     color: '#10b981' },
    comparison:   { label: 'Comparisons',  icon: Target,        color: '#f472b6' },
    hidden_pattern:{ label: 'Patterns',    icon: Eye,           color: '#818cf8' },
    summary:      { label: 'Summaries',    icon: Sparkles,      color: '#6366f1' },
};

const FALLBACK_META = { label: 'Insights', icon: Info, color: '#64748b' };
const SECTION_ORDER = ['anomaly', 'trend', 'correlation', 'driver', 'segment', 'distribution', 'comparison', 'hidden_pattern', 'summary'];

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Highlights numbers, percentages, currency, dates, and **markdown bold**. */
const HighlightedText = ({ text }) => {
    if (!text) return null;

    // Split by **markdown bold**
    const parts = text.split(/(\*\*.*?\*\*)/g);
    
    return (
        <>
            {parts.map((part, i) => {
                if (part.startsWith('**') && part.endsWith('**')) {
                    const innerText = part.slice(2, -2);
                    return <span key={i} className="font-semibold" style={{ color: 'var(--accent-primary, #2563eb)' }}>{innerText}</span>;
                } else {
                    const pattern = /(\$[\d,]+(?:\.\d+)?[KMB]?|\d+(?:,\d{3})*(?:\.\d+)?%?(?:\×)?|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?|\d{4}-\d{2}-\d{2})/g;
                    const subParts = [];
                    let last = 0;
                    let match;
                    while ((match = pattern.exec(part)) !== null) {
                        if (match.index > last) subParts.push(part.slice(last, match.index));
                        subParts.push(
                            <span key={`${i}-${match.index}`} className="font-semibold" style={{ color: 'var(--accent-primary, #2563eb)' }}>
                                {match[0]}
                            </span>
                        );
                        last = match.index + match[0].length;
                    }
                    if (last < part.length) subParts.push(part.slice(last));
                    return <React.Fragment key={i}>{subParts}</React.Fragment>;
                }
            })}
        </>
    );
};

const toSparklinePoints = (data) => {
    if (!Array.isArray(data) || data.length < 2) return null;
    return data.slice(0, 20).map((d, i) => ({
        v: typeof d === 'object' ? (d.value ?? d.y ?? d.v ?? 0) : Number(d),
        i,
    }));
};

const toScatterPoints = (data) => {
    if (!Array.isArray(data) || data.length < 2) return null;
    return data.slice(0, 20).map((d, idx) => ({
        x: Number(d?.x ?? d?.value ?? idx),
        y: Number(d?.y ?? d?.score ?? (idx + 1) * 3),
        z: 100,
    }));
};

const toBarPoints = (data) => {
    if (!Array.isArray(data) || data.length === 0) return null;
    return data.slice(0, 6).map((d, i) => ({
        name: d?.name ?? d?.label ?? String(i + 1),
        v: Number(d?.value ?? d?.count ?? d?.v ?? 0),
    }));
};

// ─── Sparkline Thumbnail ─────────────────────────────────────────────────────

const Sparkline = ({ insight }) => {
    const type = insight.type?.toLowerCase();
    const iconColor = 'var(--accent-primary, #2563eb)';

    if (type === 'trend' || type === 'anomaly') {
        const points = toSparklinePoints(insight.data);
        if (points) {
            return (
                <ResponsiveContainer width={40} height={28}>
                    <LineChart data={points} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
                        <Line
                            type="monotone"
                            dataKey="v"
                            stroke={iconColor}
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                        />
                    </LineChart>
                </ResponsiveContainer>
            );
        }
    }

    if (type === 'correlation' || type === 'distribution' || type === 'hidden_pattern') {
        const points = toScatterPoints(insight.data);
        if (points) {
            return (
                <ResponsiveContainer width={40} height={28}>
                    <ScatterChart margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
                        <XAxis dataKey="x" hide />
                        <YAxis dataKey="y" hide />
                        <ZAxis range={[8, 16]} />
                        <Scatter data={points} fill={iconColor} fillOpacity={0.8} isAnimationActive={false} />
                    </ScatterChart>
                </ResponsiveContainer>
            );
        }
    }

    if (type === 'driver' || type === 'comparison' || type === 'segment') {
        const points = toBarPoints(insight.data);
        if (points) {
            return (
                <ResponsiveContainer width={40} height={28}>
                    <BarChart data={points} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
                        <Bar dataKey="v" fill={iconColor} radius={[1, 1, 0, 0]} isAnimationActive={false} />
                    </BarChart>
                </ResponsiveContainer>
            );
        }
    }

    // Fallback: icon
    const meta = TYPE_META[type] || FALLBACK_META;
    const Icon = meta.icon;
    return <Icon size={24} style={{ color: iconColor, strokeWidth: 1.5 }} />;
};

// ─── Single Card ─────────────────────────────────────────────────────────────

const PBICard = ({ insight, onInvestigate }) => {
    const description  = insight.plain_english || insight.description || '';
    const title = (insight.title || insight.type || 'Finding')
        .replace(/\*\*/g, '').replace(/\*/g, '').trim();

    return (
        <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg transition-all duration-200"
            style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '1px solid var(--border, #e5e7eb)',
                boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}
        >
            <div className="flex items-start gap-4 p-4">
                {/* Thumbnail Icon */}
                <div className="shrink-0 mt-0.5 w-[40px] flex justify-center">
                    <Sparkline insight={insight} />
                </div>

                {/* Text Block */}
                <div className="flex-1 min-w-0 flex flex-col">
                    {/* Title */}
                    <h4 className="text-[14px] font-medium leading-[1.3] mb-1" style={{ color: 'var(--text-header, #111827)' }}>
                        {title}
                    </h4>

                    {/* Narrative */}
                    {description && (
                        <p className="text-[14px] leading-[1.6]" style={{ color: 'var(--text-secondary, #4b5563)' }}>
                            <HighlightedText text={description} />
                        </p>
                    )}

                    {/* Action */}
                    {onInvestigate && (
                        <div className="mt-3">
                            <button
                                onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    onInvestigate(insight);
                                }}
                                className="flex items-center gap-1.5 text-[12px] font-medium transition-opacity hover:opacity-80"
                                style={{ color: 'var(--accent-primary, #2563eb)' }}
                            >
                                <MessageSquare size={13} />
                                Ask AI
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
};

// ─── Section Header ───────────────────────────────────────────────────────────

const SectionHeader = ({ meta, expanded, onToggle }) => {
    return (
        <button
            onClick={onToggle}
            className="w-full flex items-center gap-2 py-2 group text-left transition-colors hover:bg-black/5 dark:hover:bg-white/5 rounded-md px-1"
        >
            <motion.div animate={{ rotate: expanded ? 180 : 90 }} transition={{ duration: 0.2 }}>
                <ChevronUp size={18} style={{ color: 'var(--text-muted, #9ca3af)' }} />
            </motion.div>
            
            <span
                className="text-[15px] font-medium tracking-wide"
                style={{ color: 'var(--text-primary, #1f2937)' }}
            >
                {meta.label}
            </span>
        </button>
    );
};

// ─── Grouped Section ─────────────────────────────────────────────────────────

const GroupedSection = ({ typeKey, insights, onInvestigate, defaultExpanded }) => {
    const [expanded, setExpanded] = useState(defaultExpanded);
    const meta = TYPE_META[typeKey] || FALLBACK_META;

    return (
        <div className="mb-4">
            <SectionHeader
                meta={meta}
                expanded={expanded}
                onToggle={() => setExpanded((v) => !v)}
            />

            <AnimatePresence initial={false}>
                {expanded && (
                    <motion.div
                        key="cards"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2, ease: 'easeInOut' }}
                        className="overflow-hidden"
                    >
                        <div className="pt-2 pb-1 space-y-3 px-1">
                            {insights.map((insight, idx) => (
                                <PBICard
                                    key={insight.id || idx}
                                    insight={insight}
                                    onInvestigate={onInvestigate}
                                />
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

// ─── Empty State ──────────────────────────────────────────────────────────────

const EmptyCards = () => (
    <div
        className="flex flex-col items-center justify-center py-12 text-center rounded-lg"
        style={{ border: '1px dashed var(--border, #e5e7eb)' }}
    >
        <Sparkles size={28} style={{ color: 'var(--text-muted, #9ca3af)', marginBottom: 8 }} />
        <p className="text-[14px] font-medium" style={{ color: 'var(--text-secondary, #4b5563)' }}>
            No insight cards available yet.
        </p>
    </div>
);

// ─── Root Component ───────────────────────────────────────────────────────────

const PowerBIInsightCards = ({ insights = [], onInvestigate, className }) => {
    const groups = useMemo(() => {
        const map = {};
        (insights || []).forEach((ins) => {
            const key = (ins.type || ins.finding_type || 'summary').toLowerCase();
            if (!map[key]) map[key] = [];
            map[key].push(ins);
        });
        return map;
    }, [insights]);

    const orderedKeys = useMemo(() => {
        const known = SECTION_ORDER.filter((k) => groups[k]?.length > 0);
        const unknown = Object.keys(groups).filter((k) => !SECTION_ORDER.includes(k) && groups[k]?.length > 0);
        return [...known, ...unknown];
    }, [groups]);

    if (orderedKeys.length === 0) return <EmptyCards />;

    return (
        <div className={cn('space-y-2', className)}>
            {orderedKeys.map((typeKey, idx) => (
                <GroupedSection
                    key={typeKey}
                    typeKey={typeKey}
                    insights={groups[typeKey]}
                    onInvestigate={onInvestigate}
                    defaultExpanded={idx === 0}
                />
            ))}
        </div>
    );
};

export default PowerBIInsightCards;
