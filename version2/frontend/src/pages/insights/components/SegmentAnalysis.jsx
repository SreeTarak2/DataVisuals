/**
 * SegmentAnalysis — Dual comparison bars, sigma deviation, direction colors
 */
import React from 'react';
import { motion } from 'framer-motion';
import { Layers, ArrowUpRight, ArrowDownRight, Minus, MessageSquare, ArrowRight } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';
import InsightFeedback from '../../../components/features/feedback/InsightFeedback';

const SegmentBar = ({ value, overall, color }) => {
    const max = Math.max(Math.abs(value), Math.abs(overall), 1);
    const segW = Math.abs(value / max) * 100;
    const ovW  = Math.abs(overall / max) * 100;
    return (
        <div className="space-y-1">
            <div className="flex items-center gap-2">
                <span className="text-xs w-12 shrink-0" style={{ color: 'var(--page-muted)' }}>Segment</span>
                <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--surface-2)' }}>
                    <motion.div className={cn('h-full rounded-full', color)} initial={{ width: 0 }} animate={{ width: `${segW}%` }} transition={{ duration: 0.7, ease: 'easeOut' }} />
                </div>
                <span className={cn('text-xs font-mono font-bold w-12 text-right', color.replace('bg-', 'text-').replace('/80', '').replace('/60', ''))}>{typeof value === 'number' ? value.toFixed(2) : value}</span>
            </div>
            <div className="flex items-center gap-2">
                <span className="text-xs w-12 shrink-0" style={{ color: 'var(--page-muted)' }}>Overall</span>
                <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--surface-2)' }}>
                    <motion.div className="h-full rounded-full bg-slate-600" initial={{ width: 0 }} animate={{ width: `${ovW}%` }} transition={{ duration: 0.7, ease: 'easeOut', delay: 0.1 }} />
                </div>
                <span className="text-xs font-mono w-12 text-right" style={{ color: 'var(--page-text)' }}>{typeof overall === 'number' ? overall.toFixed(2) : overall}</span>
            </div>
        </div>
    );
};

const SegmentCard = ({ segment, index, onInvestigate }) => {
    const isHigher  = segment.direction === 'higher';
    const isLower   = segment.direction === 'lower';
    const Icon      = isHigher ? ArrowUpRight : isLower ? ArrowDownRight : Minus;
    const dirColor  = isHigher ? 'text-emerald-400' : isLower ? 'text-red-400' : 'text-slate-200';
    const border    = isHigher ? 'border-l-emerald-500' : isLower ? 'border-l-red-500' : 'border-l-slate-700';
    const barColor  = isHigher ? 'bg-emerald-500/80' : isLower ? 'bg-red-400/80' : 'bg-slate-500/60';
    const deviationAbs = Math.abs(segment.deviation || 0);
    const deviationBadge = deviationAbs >= 2 ? 'bg-red-500/15 text-red-400 border-red-500/30' : deviationAbs >= 1 ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' : 'bg-[var(--surface-2)] border-[var(--surface-border)]';

    return (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}
            className={cn('p-4 rounded-xl border-l-4 border transition-all', border)}
            style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}
        >
            <div className="flex items-start justify-between gap-3 mb-3">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                        <span className="text-[13px] font-semibold" style={{ color: 'var(--page-text)' }}>{segment.column}</span>
                        <span className="text-xs text-slate-300">·</span>
                        <span className="text-[13px] font-medium" style={{ color: 'var(--page-muted)' }}>{segment.segment_value}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Icon className={cn('w-3.5 h-3.5 shrink-0', dirColor)} />
                        <span className={cn('text-[13px] font-semibold', dirColor)}>
                            {isHigher ? 'Above' : isLower ? 'Below' : 'Near'} average
                        </span>
                        {segment.deviation !== undefined && (
                            <span className={cn('text-xs px-1.5 py-0.5 rounded-full border font-mono font-semibold shrink-0', deviationBadge)}>
                                {(segment.deviation >= 0 ? '+' : '')}{segment.deviation.toFixed(1)}σ
                            </span>
                        )}
                    </div>
                </div>
                <div className="shrink-0 text-right">
                    <div className="text-xs" style={{ color: 'var(--page-muted)' }}>Size</div>
                    <div className="text-[13px] font-semibold" style={{ color: 'var(--page-muted)' }}>{segment.count} rows</div>
                    {segment.percentage !== undefined && <div className="text-xs text-slate-300">{segment.percentage.toFixed(1)}%</div>}
                </div>
            </div>

            <SegmentBar value={segment.mean_value} overall={segment.overall_mean} color={barColor} />

            {segment.plain_english && (
                <p className="text-xs leading-relaxed mt-2.5 mb-2.5" style={{ color: 'var(--page-text)' }}>{renderBold(segment.plain_english)}</p>
            )}

            <div className="flex items-center gap-3 mt-2.5">
                <button
                    onClick={() => onInvestigate(`Analyze the "${segment.column}" segment "${segment.segment_value}": it is ${segment.direction} than average by ${segment.deviation}σ (segment mean: ${segment.mean_value}, overall: ${segment.overall_mean}). What is unique about this group and what actions should I take?`)}
                    className="flex items-center gap-1.5 text-[13px] transition-colors font-medium"
                    style={{ color: 'var(--accent-primary)' }}
                >
                    <MessageSquare className="w-3 h-3" />
                    Explore this segment <ArrowRight className="w-2.5 h-2.5" />
                </button>
                <InsightFeedback insightId={`seg-${segment.column}-${segment.segment_value}`} />
            </div>
        </motion.div>
    );
};

const SegmentAnalysis = ({ segments = [], onInvestigate }) => {
    if (segments.length === 0) {
        return (
            <div className="rounded-2xl p-8 text-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center border" style={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--surface-border)' }}>
                    <Layers className="w-6 h-6" style={{ color: 'var(--page-muted)' }} />
                </div>
                <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--page-text)' }}>No Segments Found</h3>
                <p className="text-xs" style={{ color: 'var(--page-muted)' }}>No categorical columns with notable group differences detected.</p>
            </div>
        );
    }

    const highDeviation = segments.filter(s => Math.abs(s.deviation || 0) >= 2).length;

    return (
        <div className="backdrop-blur-sm rounded-2xl overflow-hidden border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
            <div className="px-5 pt-5 pb-4">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-center">
                        <Layers className="w-4 h-4 text-purple-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--page-text)' }}>Segment Analysis</h3>
                        <p className="text-[13px] mt-0.5" style={{ color: 'var(--page-muted)' }}>
                            {segments.length} group comparison{segments.length !== 1 ? 's' : ''}
                            {highDeviation > 0 && <span className="text-red-400 ml-1">· {highDeviation} outlier group{highDeviation !== 1 ? 's' : ''}</span>}
                        </p>
                    </div>
                </div>
            </div>
            <div className="px-5 pb-5 space-y-3">
                {segments.map((seg, i) => (
                    <SegmentCard key={`${seg.column}-${seg.segment_value}-${i}`} segment={seg} index={i} onInvestigate={onInvestigate} />
                ))}
            </div>
        </div>
    );
};

export default SegmentAnalysis;
