/**
 * NarrativeInsightCard — A premium, wide card design for narrative insights.
 * Ported from datasage-intelligence/src/components/InsightCard.tsx
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, AlertCircle, Link2, Users, Info, ChevronDown, ChevronUp, Database, MessageSquare } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip } from 'recharts';
import { cn } from '../../../lib/utils';
import InsightFeedback from '../../../components/features/feedback/InsightFeedback';

const NarrativeInsightCard = ({ insight, onInvestigate }) => {
    const [showDeepDive, setShowDeepDive] = useState(false);

    // Map backend types to icons
    const getIcon = (type) => {
        switch (type?.toLowerCase()) {
            case 'trend': return TrendingUp;
            case 'anomaly': return AlertCircle;
            case 'correlation': return Link2;
            case 'segment': return Users;
            default: return Info;
        }
    };

    const Icon = getIcon(insight.type);

    // Fallbacks for data mapping
    const typeLabel = insight.type || 'Insight';
    const title = insight.title || insight.type || 'Key Finding';
    const description = insight.plain_english || insight.description || 'A significant pattern was detected.';
    const tags = insight.tags || [];

    if (insight.severity) tags.push(`Severity: ${insight.severity}`);
    if (insight.impact) tags.push(`Impact: ${insight.impact}`);

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="py-12 border-b border-[var(--surface-border)] hover:bg-[var(--surface-2)]/30 transition-colors px-6 -mx-6 rounded-2xl last:border-0"
        >
            <div className="grid lg:grid-cols-12 gap-12">
                {/* Narrative Side */}
                <div className="lg:col-span-6 space-y-6">
                    <div className="flex items-center gap-3 flex-wrap">
                        <div className="p-2 bg-[var(--surface-2)] border border-[var(--surface-border)] rounded-lg">
                            <Icon className="w-4 h-4 text-[var(--accent-primary)]" />
                        </div>
                        <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--page-muted)]">{typeLabel}</span>
                        {tags.map(tag => (
                            <span key={tag} className="text-[10px] px-2 py-0.5 bg-[var(--surface-2)] text-[var(--page-muted)] border border-[var(--surface-border)] rounded-full font-medium">
                                {tag}
                            </span>
                        ))}
                    </div>

                    <div className="space-y-4">
                        <h3 className="font-serif text-3xl font-medium leading-tight text-[var(--page-text)]">
                            {title}
                        </h3>
                        <p className="text-[var(--page-muted)] leading-relaxed font-light text-lg">
                            {description}
                        </p>
                    </div>

                    {insight.value && (
                        <div className="text-4xl font-light tracking-tighter text-[var(--page-text)]">
                            {insight.value}
                        </div>
                    )}

                    <div className="flex items-center gap-6 pt-4">
                        <button
                            onClick={() => setShowDeepDive(!showDeepDive)}
                            className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-[var(--accent-primary)] hover:opacity-80 transition-opacity"
                        >
                            {showDeepDive ? 'Hide Statistical Proof' : 'View Statistical Proof'}
                            {showDeepDive ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>

                        <button
                            onClick={() => onInvestigate && onInvestigate(`Investigate this finding: "${description}". What are the implications and what should I do about it?`)}
                            className="flex items-center gap-1.5 text-[13px] text-violet-400 hover:text-violet-300 transition-colors font-medium bg-violet-500/10 px-3 py-1.5 rounded-lg border border-violet-500/20"
                        >
                            <MessageSquare className="w-3 h-3" />
                            Ask Assistant
                        </button>
                    </div>
                </div>

                {/* Visualization Side */}
                <div className="lg:col-span-6">
                    {insight.data ? (
                        <div className="h-72 w-full bg-[var(--surface-2)]/50 rounded-2xl p-6 border border-[var(--surface-border)]">
                            <ResponsiveContainer width="100%" height="100%">
                                {insight.type?.toLowerCase() === 'trend' ? (
                                    <AreaChart data={insight.data}>
                                        <XAxis dataKey="name" hide />
                                        <YAxis hide />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: 'var(--surface-1)', borderRadius: '12px', border: '1px solid var(--surface-border)', fontSize: '12px', color: 'var(--page-text)' }}
                                            itemStyle={{ color: 'var(--page-text)' }}
                                        />
                                        <Area
                                            type="monotone"
                                            dataKey="value"
                                            stroke="var(--accent-primary)"
                                            fill="var(--accent-primary)"
                                            fillOpacity={0.1}
                                            strokeWidth={3}
                                        />
                                    </AreaChart>
                                ) : (
                                    <ScatterChart>
                                        <XAxis type="number" dataKey="x" hide />
                                        <YAxis type="number" dataKey="y" hide />
                                        <ZAxis type="number" range={[50, 400]} />
                                        <Tooltip cursor={{ strokeDasharray: '3 3' }}
                                            contentStyle={{ backgroundColor: 'var(--surface-1)', borderRadius: '12px', border: '1px solid var(--surface-border)', fontSize: '12px', color: 'var(--page-text)' }}
                                            itemStyle={{ color: 'var(--page-text)' }}
                                        />
                                        <Scatter name="Data" data={insight.data} fill="var(--accent-primary)" fillOpacity={0.6} />
                                    </ScatterChart>
                                )}
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="h-72 w-full flex items-center justify-center bg-[var(--surface-2)]/30 rounded-2xl border border-dashed border-[var(--surface-border)]">
                            <div className="text-center space-y-3">
                                <div className="w-12 h-12 bg-[var(--surface-2)] rounded-full flex items-center justify-center mx-auto mb-2 border border-[var(--surface-border)]">
                                    <AlertCircle className="w-6 h-6 text-[var(--page-muted)]/50" />
                                </div>
                                <p className="text-xs text-[var(--page-muted)] font-bold uppercase tracking-widest">Qualitative Context Only</p>
                                <p className="text-[10px] text-[var(--page-muted)]/60 max-w-[200px] mx-auto">This insight is derived from pattern recognition rather than exact plotting points.</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Statistical Deep Dive */}
            <AnimatePresence>
                {showDeepDive && insight.evidence && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden mt-8"
                    >
                        <div className="bg-[var(--surface-2)] border border-[var(--surface-border)] rounded-xl p-6 grid md:grid-cols-4 gap-8">
                            {insight.evidence.p_value !== undefined && (
                                <div className="space-y-2">
                                    <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--page-muted)]">P-Value</div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-[var(--page-text)] font-mono font-bold text-lg">{insight.evidence.p_value}</span>
                                        {insight.evidence.p_value < 0.05 && <span className="text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded-full font-bold uppercase">Significant</span>}
                                    </div>
                                </div>
                            )}
                            {insight.evidence.effect_size !== undefined && (
                                <div className="space-y-2">
                                    <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--page-muted)]">Effect Size</div>
                                    <div className="text-[var(--page-text)] font-mono font-bold text-lg">{insight.evidence.effect_size}</div>
                                </div>
                            )}
                            {insight.evidence.confidence_interval && (
                                <div className="space-y-2">
                                    <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--page-muted)]">95% Confidence Interval</div>
                                    <div className="text-[var(--page-text)] font-mono font-bold text-lg">
                                        [{insight.evidence.confidence_interval[0]}, {insight.evidence.confidence_interval[1]}]
                                    </div>
                                </div>
                            )}
                            <div className="space-y-2">
                                <div className="text-[9px] font-bold uppercase tracking-widest text-[var(--page-muted)]">Feedback</div>
                                <div className="pt-1"><InsightFeedback insightId={insight.id} /></div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default NarrativeInsightCard;
