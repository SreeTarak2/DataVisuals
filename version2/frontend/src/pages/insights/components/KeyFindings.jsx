/**
 * KeyFindings — Ranked findings with numbered cards, severity borders, evidence stats
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Zap, AlertTriangle, ChevronDown, MessageSquare, ArrowRight,
    AlertCircle, Info, CheckCircle, Triangle,
} from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';
import InsightFeedback from '../../../components/features/feedback/InsightFeedback';

const SEV = {
    critical: { badge: 'bg-red-500/15 text-red-400 border-red-500/30',   border: 'border-l-red-500',    icon: AlertCircle,  iconColor: 'text-red-400',   numBg: 'bg-red-500/10 text-red-400 border-red-500/20'   },
    high:     { badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30', border: 'border-l-amber-500', icon: AlertTriangle, iconColor: 'text-amber-400', numBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
    medium:   { badge: 'bg-blue-500/15 text-blue-400 border-blue-500/30',   border: 'border-l-blue-500',  icon: Info,         iconColor: 'text-blue-400',   numBg: 'bg-blue-500/10 text-blue-400 border-blue-500/20'   },
    low:      { badge: 'bg-slate-600/20 text-slate-200 border-slate-600/30', border: 'border-l-slate-700', icon: CheckCircle,  iconColor: 'text-slate-200',  numBg: 'bg-slate-800 text-slate-200 border-slate-700'      },
    info:     { badge: 'bg-slate-600/20 text-slate-200 border-slate-600/30', border: 'border-l-slate-700', icon: Info,         iconColor: 'text-slate-200',  numBg: 'bg-slate-800 text-slate-200 border-slate-700'      },
};

const FindingCard = ({ finding, index, onInvestigate, expanded, onToggle }) => {
    const cfg = SEV[finding.severity] || SEV.info;
    const Icon = cfg.icon;

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04 }}
            className={cn(
                'relative rounded-xl border-l-4 border overflow-hidden',
                'border-[var(--surface-border)] bg-[var(--surface-1)]',
                'hover:border-[var(--surface-border-hover)] hover:bg-[var(--surface-2)] transition-all duration-200',
                cfg.border,
            )}
        >
            {/* Simpson's Paradox banner */}
            {finding.is_simpson_paradox && (
                <div className="bg-red-500/15 border-b border-red-500/20 px-4 py-1.5 flex items-center gap-2">
                    <Triangle className="w-3 h-3 text-red-400 fill-red-400" />
                    <span className="text-[13px] font-bold text-red-400 tracking-wide">SIMPSON'S PARADOX DETECTED</span>
                </div>
            )}

            <button onClick={onToggle} className="w-full flex items-start gap-3 p-4 text-left">
                {/* Rank number */}
                <div className={cn('w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 font-bold text-xs tabular-nums', cfg.numBg)}>
                    {String(index + 1).padStart(2, '0')}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-start gap-2 mb-1.5">
                        <span className="text-[13px] font-semibold leading-snug flex-1" style={{ color: 'var(--page-text)' }}>
                            {finding.title || finding.type}
                        </span>
                        {finding.evidence_tier && (
                            <span className={cn('text-[10px] px-1.5 py-0.5 rounded-full border font-bold uppercase tracking-wider shrink-0',
                                finding.evidence_tier === 'strong' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
                                finding.evidence_tier === 'moderate' ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' :
                                'bg-slate-700/40 text-slate-400 border-slate-600/30'
                            )}>
                                {finding.evidence_tier === 'strong' ? '● Strong' : finding.evidence_tier === 'moderate' ? '● Moderate' : '○ Weak'}
                            </span>
                        )}
                        <span className={cn('text-xs px-1.5 py-0.5 rounded-full border font-semibold shrink-0', cfg.badge)}>
                            {finding.impact || finding.severity}
                        </span>
                    </div>

                    <p className="text-xs leading-relaxed line-clamp-2" style={{ color: 'var(--page-muted)' }}>
                        {renderBold(finding.plain_english || finding.description)}
                    </p>

                    {/* Inline evidence chips */}
                    {finding.evidence && Object.keys(finding.evidence).length > 0 && (
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                            {finding.evidence.p_value !== undefined && (
                                <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ color: 'var(--page-muted)', backgroundColor: 'var(--surface-2)' }}>p={finding.evidence.p_value}</span>
                            )}
                            {finding.evidence.effect_size !== undefined && (
                                <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ color: 'var(--page-muted)', backgroundColor: 'var(--surface-2)' }}>d={finding.evidence.effect_size}</span>
                            )}
                            {finding.evidence.effect_interpretation && (
                                <span className="text-xs px-1.5 py-0.5 rounded-full border" style={{ color: 'var(--accent-primary)', backgroundColor: 'var(--accent-primary-muted)', borderColor: 'var(--accent-primary-muted)' }}>
                                    {finding.evidence.effect_interpretation}
                                </span>
                            )}
                        </div>
                    )}
                </div>

                <ChevronDown className={cn('w-4 h-4 text-slate-600 shrink-0 transition-transform mt-1', expanded && 'rotate-180')} />
            </button>

            <AnimatePresence>
                {expanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                    >
                        <div className="border-t border-slate-800/60 px-4 py-4 space-y-3">
                            <p className="text-xs text-slate-300 leading-relaxed">
                                {renderBold(finding.plain_english || finding.description)}
                            </p>

                            {/* Evidence stats grid */}
                            {finding.evidence && Object.keys(finding.evidence).length > 0 && (
                                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                    {finding.evidence.p_value !== undefined && (
                                        <div className="bg-slate-800/60 rounded-lg p-2.5 text-center">
                                            <div className="text-xs font-mono font-bold text-white">{finding.evidence.p_value}</div>
                                            <div className="text-xs text-slate-300 mt-0.5">p-value</div>
                                        </div>
                                    )}
                                    {finding.evidence.effect_size !== undefined && (
                                        <div className="bg-slate-800/60 rounded-lg p-2.5 text-center">
                                            <div className="text-xs font-mono font-bold text-white">{finding.evidence.effect_size}</div>
                                            <div className="text-xs text-slate-300 mt-0.5">Effect size</div>
                                        </div>
                                    )}
                                    {finding.evidence.confidence_interval && (
                                        <div className="bg-slate-800/60 rounded-lg p-2.5 text-center">
                                            <div className="text-xs font-mono font-bold text-white">
                                                [{finding.evidence.confidence_interval[0]}, {finding.evidence.confidence_interval[1]}]
                                            </div>
                                            <div className="text-xs text-slate-300 mt-0.5">95% CI</div>
                                        </div>
                                    )}
                                </div>
                            )}

                            <div className="flex items-center gap-3">
                                <button
                                    onClick={() => onInvestigate(`Investigate this finding: "${finding.plain_english || finding.description}". What are the implications and what should I do about it?`)}
                                    className="flex items-center gap-1.5 text-[13px] text-violet-400 hover:text-violet-300 transition-colors font-medium"
                                >
                                    <MessageSquare className="w-3 h-3" />
                                    Dig deeper with AI
                                    <ArrowRight className="w-2.5 h-2.5" />
                                </button>
                                <InsightFeedback insightId={finding.id} />
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

const KeyFindings = ({ findings = [], compact = false, onViewAll, onInvestigate }) => {
    const [expandedId, setExpandedId] = useState(null);

    if (findings.length === 0) {
        return (
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-8 text-center">
                <Zap className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                <h3 className="text-sm font-semibold text-white mb-1">No Key Findings</h3>
                <p className="text-xs text-slate-300">No significant statistical patterns were detected.</p>
            </div>
        );
    }

    const criticalCount = findings.filter(f => f.severity === 'critical').length;
    const highCount     = findings.filter(f => f.severity === 'high').length;

    return (
        <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/60 rounded-2xl overflow-hidden">
            <div className="px-5 pt-5 pb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-center justify-center">
                        <Zap className="w-4 h-4 text-amber-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">Key Findings</h3>
                        <p className="text-[13px] text-slate-300 mt-0.5">
                            {findings.length} finding{findings.length !== 1 ? 's' : ''} ranked by impact
                            {criticalCount > 0 && <span className="text-red-400 ml-1">· {criticalCount} critical</span>}
                            {highCount > 0 && <span className="text-amber-400 ml-1">· {highCount} high</span>}
                        </p>
                    </div>
                </div>
                {compact && onViewAll && (
                    <button onClick={onViewAll} className="flex items-center gap-1 text-xs text-slate-300 hover:text-slate-300 transition-colors">
                        View all <ArrowRight className="w-3 h-3" />
                    </button>
                )}
            </div>

            <div className="px-5 pb-5 space-y-2.5">
                {findings.map((finding, i) => (
                    <FindingCard
                        key={finding.id || i}
                        finding={finding}
                        index={i}
                        onInvestigate={onInvestigate}
                        expanded={expandedId === (finding.id || i)}
                        onToggle={() => setExpandedId(expandedId === (finding.id || i) ? null : (finding.id || i))}
                    />
                ))}
            </div>
        </div>
    );
};

export default KeyFindings;
