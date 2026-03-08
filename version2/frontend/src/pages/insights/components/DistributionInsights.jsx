/**
 * DistributionInsights — Bell-curve SVG, skewness direction bars, kurtosis chips
 */
import React from 'react';
import { motion } from 'framer-motion';
import { BarChart2, MessageSquare, ArrowRight } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';
import InsightFeedback from '../../../components/features/feedback/InsightFeedback';

// Mini SVG bell curve, skewed left or right based on skewness value
const BellCurve = ({ skewness = 0, kurtosis = 3 }) => {
    const W = 72; const H = 36;
    // Generate a skewed bell curve using a quadratic bezier approximation
    const sk = Math.max(-3, Math.min(3, skewness));
    const kt = Math.max(1, Math.min(6, kurtosis || 3));

    // center shifts with skewness, height increases with kurtosis
    const cx  = W / 2 - sk * 6;
    const top = H - Math.min(32, 18 + kt * 2);
    const spread = Math.max(18, 30 - Math.abs(sk) * 3);

    // peak & tails
    const lx = cx - spread; const rx = cx + spread;
    const path = `M ${Math.max(2, lx - 4)},${H - 2} Q ${cx - spread * 0.5},${top + 8} ${cx},${top} Q ${cx + spread * 0.5},${top + 8} ${Math.min(W - 2, rx + 4)},${H - 2}`;

    const isRight = sk > 0.5;
    const isLeft  = sk < -0.5;
    const strokeColor = isRight ? '#f59e0b' : isLeft ? '#60a5fa' : '#8b5cf6';
    const fillColor   = isRight ? '#f59e0b15' : isLeft ? '#60a5fa15' : '#8b5cf615';

    return (
        <svg width={W} height={H} className="shrink-0">
            <path d={path} fill={fillColor} />
            <path d={path} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" />
            {/* Vertical center dashed line */}
            <line x1={cx} y1={top} x2={cx} y2={H - 2} stroke={strokeColor} strokeWidth="0.75" strokeDasharray="2,2" opacity="0.5" />
        </svg>
    );
};

const SkewBar = ({ skewness = 0 }) => {
    const clamped = Math.max(-3, Math.min(3, skewness));
    const pct = ((clamped + 3) / 6) * 100; // 0–100%, 50% is center
    const isRight = clamped > 0.3;
    const isLeft  = clamped < -0.3;
    const thumbColor = isRight ? 'bg-amber-400' : isLeft ? 'bg-blue-400' : 'bg-purple-400';

    return (
        <div className="relative h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--surface-2)' }}>
            <div className="absolute inset-y-0 left-1/2 w-px" style={{ backgroundColor: 'var(--surface-border)' }} />
            <motion.div
                className={cn('absolute inset-y-0 rounded-full', clamped >= 0 ? 'left-1/2' : '', thumbColor)}
                style={clamped >= 0 ? { left: '50%', width: `${(clamped / 3) * 50}%` } : { right: '50%', width: `${(-clamped / 3) * 50}%` }}
                initial={{ width: 0 }} animate={{ width: `${Math.abs(clamped / 3) * 50}%` }}
                transition={{ duration: 0.7, ease: 'easeOut' }}
            />
        </div>
    );
};

const DistCard = ({ dist, index, onInvestigate }) => {
    const sk = dist.skewness ?? 0;
    const kt = dist.kurtosis ?? 3;
    const isNormal  = dist.is_normal;
    const isRightSk = sk > 0.5;
    const isLeftSk  = sk < -0.5;
    const skLabel   = isRightSk ? 'Right-skewed' : isLeftSk ? 'Left-skewed' : 'Symmetric';
    const skColor   = isRightSk ? 'text-amber-400' : isLeftSk ? 'text-blue-400' : 'text-purple-400';
    const border    = isRightSk ? 'border-l-amber-500' : isLeftSk ? 'border-l-blue-500' : 'border-l-purple-500';

    const ktLabel = kt > 4.5 ? 'Leptokurtic' : kt < 2 ? 'Platykurtic' : 'Mesokurtic';
    const ktColor = kt > 4.5 ? 'text-red-400' : kt < 2 ? 'text-slate-200' : 'text-emerald-400';

    return (
        <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: index * 0.04 }}
            className={cn('p-3.5 rounded-xl border-l-4 border bg-[var(--surface-1)] hover:bg-[var(--surface-2)] transition-all border-[var(--surface-border)]', border)}
        >
            <div className="flex items-start gap-3 mb-2.5">
                <BellCurve skewness={sk} kurtosis={kt} />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-[13px] font-semibold truncate" style={{ color: 'var(--page-text)' }}>{dist.column}</span>
                        <span className={cn('text-xs px-1.5 py-0.5 rounded-full border font-semibold shrink-0',
                            isNormal ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                        )}>
                            {isNormal ? 'Normal' : 'Non-normal'}
                        </span>
                    </div>
                    <div className="flex items-center gap-3 flex-wrap">
                        <span className={cn('text-xs font-semibold', skColor)}>{skLabel}</span>
                        <span className="text-xs font-mono" style={{ color: 'var(--page-muted)' }}>sk={sk.toFixed(2)}</span>
                        <span className={cn('text-xs font-semibold', ktColor)}>{ktLabel}</span>
                        <span className="text-xs font-mono" style={{ color: 'var(--page-muted)' }}>kt={kt.toFixed(2)}</span>
                    </div>
                </div>
            </div>

            <div className="mb-2.5 px-1">
                <div className="flex items-center justify-between mb-1">
                    <span className="text-[13px]" style={{ color: 'var(--page-muted)' }}>← Left skew</span>
                    <span className="text-[13px] font-semibold" style={{ color: 'var(--page-muted)' }}>Skewness</span>
                    <span className="text-[13px]" style={{ color: 'var(--page-muted)' }}>Right skew →</span>
                </div>
                <SkewBar skewness={sk} />
            </div>

            {dist.plain_english && (
                <p className="text-[13px] leading-relaxed mb-2.5" style={{ color: 'var(--page-text)' }}>{renderBold(dist.plain_english)}</p>
            )}

            <div className="flex items-center gap-3">
                <button
                    onClick={() => onInvestigate(`Analyze the distribution of "${dist.column}": skewness=${sk.toFixed(3)}, kurtosis=${kt.toFixed(3)}, is_normal=${isNormal}. What transformation would make this more normal? Are there outliers driving the skew?`)}
                    className="flex items-center gap-1.5 text-[13px] transition-colors font-medium"
                    style={{ color: 'var(--accent-primary)' }}
                >
                    <MessageSquare className="w-3 h-3" />
                    Analyze with AI <ArrowRight className="w-2.5 h-2.5" />
                </button>
                <InsightFeedback insightId={`dist-${dist.column}`} />
            </div>
        </motion.div>
    );
};

const DistributionInsights = ({ distributions = [], onInvestigate }) => {
    if (distributions.length === 0) {
        return (
            <div className="rounded-2xl p-8 text-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center border" style={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--surface-border)' }}>
                    <BarChart2 className="w-6 h-6" style={{ color: 'var(--page-muted)' }} />
                </div>
                <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--page-text)' }}>No Numeric Columns</h3>
                <p className="text-xs" style={{ color: 'var(--page-muted)' }}>No numeric columns found for distribution analysis.</p>
            </div>
        );
    }

    const normalCount   = distributions.filter(d => d.is_normal).length;
    const nonNormCount  = distributions.length - normalCount;
    const skewedCount   = distributions.filter(d => Math.abs(d.skewness ?? 0) > 0.5).length;

    return (
        <div className="backdrop-blur-sm rounded-2xl overflow-hidden border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
            <div className="px-5 pt-5 pb-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-center">
                            <BarChart2 className="w-4 h-4 text-purple-400" />
                        </div>
                        <div>
                            <h3 className="text-sm font-semibold" style={{ color: 'var(--page-text)' }}>Distribution Analysis</h3>
                            <p className="text-[13px] mt-0.5" style={{ color: 'var(--page-muted)' }}>
                                {distributions.length} numeric column{distributions.length !== 1 ? 's' : ''}
                                {skewedCount > 0 && <span className="text-amber-400 ml-1">· {skewedCount} skewed</span>}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        {normalCount > 0    && <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">{normalCount} normal</span>}
                        {nonNormCount > 0   && <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">{nonNormCount} non-normal</span>}
                    </div>
                </div>
            </div>
            <div className="px-5 pb-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
                {distributions.map((dist, i) => (
                    <DistCard key={`${dist.column}-${i}`} dist={dist} index={i} onInvestigate={onInvestigate} />
                ))}
            </div>
        </div>
    );
};

export default DistributionInsights;
