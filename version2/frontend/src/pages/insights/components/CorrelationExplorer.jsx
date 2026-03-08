/**
 * CorrelationExplorer — Gradient correlation bars, filter tabs, variance explained
 */
import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GitBranch, ArrowUpRight, ArrowDownRight, MessageSquare, ArrowRight } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';

const STR = {
    Strong: { badge: 'bg-[var(--cat-indigo)]/15 text-[var(--cat-indigo)] border-[var(--cat-indigo)]/30', border: 'border-l-[var(--cat-indigo)]', barPos: 'bg-gradient-to-r from-[var(--status-good)] to-emerald-400', barNeg: 'bg-gradient-to-l from-[var(--status-critical)] to-rose-400' },
    Moderate: { badge: 'bg-[var(--cat-blue)]/15 text-[var(--cat-blue)] border-[var(--cat-blue)]/30', border: 'border-l-[var(--cat-blue)]', barPos: 'bg-[var(--status-good)]', barNeg: 'bg-[var(--status-critical)]' },
    Weak: { badge: 'bg-[var(--insights-surface)] text-[var(--insights-text-secondary)] border-[var(--color-border)]', border: 'border-l-[var(--insights-text-secondary)]', barPos: 'bg-[var(--status-good)]/70', barNeg: 'bg-[var(--status-critical)]/70' },
};

const CorrelationBar = ({ value, strength }) => {
    const width = Math.abs(value) * 100;
    const isPos = value > 0;
    const cfg = STR[strength] || STR.Weak;
    const barClass = isPos ? cfg.barPos : cfg.barNeg;
    return (
        <div className="flex items-center gap-3 mt-1.5 mb-1">
            <div className="flex-1 h-2 bg-[var(--insights-bg)] border border-[var(--color-border)] rounded-full overflow-hidden relative">
                <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[var(--color-border)] z-10" />
                <motion.div
                    className={cn('absolute top-0 bottom-0 rounded-full', barClass)}
                    initial={{ width: 0, left: '50%' }}
                    animate={{ width: `${width / 2}%`, left: isPos ? '50%' : `${50 - width / 2}%` }}
                    transition={{ duration: 0.7, ease: 'easeOut' }}
                />
            </div>
            <span className={cn('text-[11px] font-mono font-bold w-12 text-right', isPos ? 'text-[var(--status-good)]' : 'text-[var(--status-critical)]')}>
                {value > 0 ? '+' : ''}{value.toFixed(2)}
            </span>
        </div>
    );
};

const CorrelationCard = ({ corr, index, onInvestigate }) => {
    const [expanded, setExpanded] = useState(false);
    const cfg = STR[corr.strength] || STR.Weak;
    return (
        <motion.div layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }}
            className={cn('rounded-xl border-l-4 border border-[var(--color-border)] bg-[var(--insights-bg)] hover:shadow-md hover:bg-[var(--insights-surface)] transition-all duration-200 overflow-hidden', cfg.border)}
        >
            <button onClick={() => setExpanded(!expanded)} className="w-full p-4 text-left">
                <div className="flex items-center gap-2 mb-2.5">
                    <span className="text-[13px] font-semibold text-[var(--insights-text-primary)]">{corr.column1}</span>
                    {corr.direction === 'positive'
                        ? <ArrowUpRight className="w-3.5 h-3.5 text-[var(--status-good)] shrink-0" />
                        : <ArrowDownRight className="w-3.5 h-3.5 text-[var(--status-critical)] shrink-0" />}
                    <span className="text-[13px] font-semibold text-[var(--insights-text-primary)]">{corr.column2}</span>
                    <span className={cn('ml-auto text-[10px] px-1.5 py-0.5 rounded-full border font-semibold uppercase tracking-wider', cfg.badge)}>{corr.strength}</span>
                </div>
                <CorrelationBar value={corr.value} strength={corr.strength} />
                <p className="text-xs text-[var(--insights-text-secondary)] leading-relaxed mt-2.5 line-clamp-2">{renderBold(corr.plain_english)}</p>
            </button>

            <AnimatePresence>
                {expanded && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }} className="overflow-hidden">
                        <div className="border-t border-[var(--color-border)] px-4 py-4 space-y-3">
                            <p className="text-xs text-[var(--insights-text-primary)] leading-relaxed mb-3">{renderBold(corr.plain_english)}</p>
                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                                {corr.variance_explained && (
                                    <div className="bg-[var(--insights-surface)] border border-[var(--color-border)] rounded-lg px-2.5 py-2 text-center">
                                        <div className="text-xs font-bold text-[var(--insights-text-primary)]">{corr.variance_explained}</div>
                                        <div className="text-[10px] text-[var(--insights-text-secondary)] mt-0.5 uppercase tracking-wide">Variance Explained</div>
                                    </div>
                                )}
                                {corr.p_value != null && (
                                    <div className="bg-[var(--insights-surface)] border border-[var(--color-border)] rounded-lg px-2.5 py-2 text-center">
                                        <div className="text-xs font-mono font-bold text-[var(--insights-text-primary)]">{corr.p_value}</div>
                                        <div className="text-[10px] text-[var(--insights-text-secondary)] mt-0.5 uppercase tracking-wide">p-value</div>
                                    </div>
                                )}
                                {corr.method && (
                                    <div className="bg-[var(--insights-surface)] border border-[var(--color-border)] rounded-lg px-2.5 py-2 text-center">
                                        <div className="text-[11px] font-bold text-[var(--insights-text-primary)] capitalize">{corr.method}</div>
                                        <div className="text-[10px] text-[var(--insights-text-secondary)] mt-0.5 uppercase tracking-wide">Method</div>
                                    </div>
                                )}
                            </div>
                            <div className="pt-2">
                                <button
                                    onClick={() => onInvestigate(`Explain the ${corr.strength.toLowerCase()} ${corr.direction} correlation (r=${corr.value}) between "${corr.column1}" and "${corr.column2}". Is this causal?`)}
                                    className="flex items-center gap-1.5 text-[13px] text-[var(--cat-violet)] hover:text-violet-300 transition-colors font-medium"
                                >
                                    <MessageSquare className="w-3 h-3" />
                                    Analyze with AI <ArrowRight className="w-2.5 h-2.5" />
                                </button>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

const FILTERS = ['All', 'Strong', 'Moderate', 'Weak'];

const CorrelationExplorer = ({ correlations = [], compact = false, onViewAll, onInvestigate }) => {
    const [filter, setFilter] = useState('All');
    const filtered = useMemo(() => filter === 'All' ? correlations : correlations.filter(c => c.strength === filter), [correlations, filter]);
    const strongCount = correlations.filter(c => c.strength === 'Strong').length;

    if (correlations.length === 0) {
        return (
            <div className="bg-[var(--insights-surface)] backdrop-blur-sm border border-[var(--color-border)] rounded-2xl p-8 text-center h-full flex flex-col justify-center items-center">
                <GitBranch className="w-8 h-8 text-[var(--insights-text-secondary)] mx-auto mb-3" />
                <h3 className="text-sm font-semibold text-[var(--insights-text-primary)] mb-1">No Significant Relationships</h3>
                <p className="text-xs text-[var(--insights-text-secondary)]">No correlations above the significance threshold were found.</p>
            </div>
        );
    }

    return (
        <div className="bg-[var(--insights-surface)] backdrop-blur-sm border border-[var(--color-border)] rounded-2xl overflow-hidden h-full">
            <div className="px-5 pt-5 pb-4 flex items-center justify-between gap-4 flex-wrap">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-[var(--cat-blue)]/10 border border-[var(--cat-blue)]/20 rounded-xl flex items-center justify-center shrink-0">
                        <GitBranch className="w-4 h-4 text-[var(--cat-blue)]" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-[var(--insights-text-primary)]">Relational Dynamics</h3>
                        <p className="text-[13px] text-[var(--insights-text-secondary)] mt-0.5">
                            {correlations.length} significant correlation{correlations.length !== 1 ? 's' : ''}
                            {strongCount > 0 && <span className="text-[var(--cat-indigo)] ml-1">· {strongCount} strong</span>}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    {!compact && FILTERS.map(f => (
                        <button key={f} onClick={() => setFilter(f)}
                            className={cn('px-2.5 py-1 text-[11px] uppercase tracking-wider font-semibold rounded-lg transition-all border',
                                filter === f ? 'bg-[var(--cat-indigo)]/15 text-[var(--cat-indigo)] border-[var(--cat-indigo)]/30' : 'text-[var(--insights-text-secondary)] border-transparent hover:text-[var(--insights-text-primary)] hover:bg-[var(--insights-bg)]'
                            )}>
                            {f}
                        </button>
                    ))}
                    {compact && onViewAll && (
                        <button onClick={onViewAll} className="flex items-center gap-1 text-xs text-[var(--insights-text-secondary)] hover:text-[var(--insights-text-primary)] transition-colors">
                            View all <ArrowRight className="w-3 h-3" />
                        </button>
                    )}
                </div>
            </div>
            <div className="px-5 pb-5 space-y-2.5">
                {filtered.map((corr, i) => (
                    <CorrelationCard key={`${corr.column1}-${corr.column2}-${i}`} corr={corr} index={i} onInvestigate={onInvestigate} />
                ))}
            </div>
        </div>
    );
};

export default CorrelationExplorer;
