/**
 * TrendAnalysis — Mini SVG sparklines, strength bars, seasonality badges
 */
import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus, MessageSquare, ArrowRight, Clock } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';

// Generate a deterministic-ish sparkline based on direction + strength
const MiniSparkline = ({ direction, strength }) => {
    const pts = useMemo(() => {
        const trend = direction === 'increasing' ? 1 : direction === 'decreasing' ? -1 : 0;
        let cur = 50;
        return Array.from({ length: 20 }, (_, i) => {
            const noise = (Math.sin(i * 2.5 + strength * 10) * 10 * (1 - strength * 0.4));
            cur = Math.max(8, Math.min(92, cur + trend * strength * 2 + noise));
            return cur;
        });
    }, [direction, strength]);

    const min = Math.min(...pts); const max = Math.max(...pts); const range = max - min || 1;
    const W = 80; const H = 32;
    const polyline = pts.map((v, i) => `${(i / (pts.length - 1)) * W},${H - ((v - min) / range) * H}`).join(' ');
    const fillPath = `M 0,${H} ${pts.map((v, i) => `L ${(i / (pts.length - 1)) * W},${H - ((v - min) / range) * H}`).join(' ')} L ${W},${H} Z`;
    const color = direction === 'increasing' ? '#10b981' : direction === 'decreasing' ? '#f87171' : '#94a3b8';

    return (
        <svg width={W} height={H} className="shrink-0">
            <defs>
                <linearGradient id={`sg-${direction}-${Math.round(strength*100)}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.25" />
                    <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
            </defs>
            <path d={fillPath} fill={`url(#sg-${direction}-${Math.round(strength*100)})`} />
            <polyline points={polyline} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
};

const TrendCard = ({ trend, index, onInvestigate }) => {
    const isUp   = trend.direction === 'increasing';
    const isDown = trend.direction === 'decreasing';
    const Icon   = isUp ? TrendingUp : isDown ? TrendingDown : Minus;
    const color     = isUp ? 'text-emerald-400' : isDown ? 'text-red-400' : 'text-slate-200';
    const border    = isUp ? 'border-l-emerald-500' : isDown ? 'border-l-red-500' : 'border-l-slate-700';
    const iconBg    = isUp ? 'bg-emerald-500/10 border-emerald-500/20' : isDown ? 'bg-red-500/10 border-red-500/20' : 'bg-[var(--surface-2)] border-[var(--surface-border)]';
    const barColor  = isUp ? 'bg-emerald-500' : isDown ? 'bg-red-400' : 'bg-slate-500';

    return (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}
            className={cn('p-4 rounded-xl border-l-4 border bg-[var(--surface-1)] hover:bg-[var(--surface-2)] transition-all border-[var(--surface-border)]', border)}
        >
            <div className="flex items-start gap-3">
                <div className={cn('w-8 h-8 rounded-xl border flex items-center justify-center shrink-0', iconBg)}>
                    <Icon className={cn('w-4 h-4', color)} />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                        <div className="flex items-center gap-2 flex-wrap min-w-0">
                            <span className="text-[13px] font-semibold truncate" style={{ color: 'var(--page-text)' }}>{trend.column}</span>
                            {trend.is_significant && (
                                <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold shrink-0">Significant</span>
                            )}
                            {trend.seasonality && (
                                <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-500/15 text-blue-400 border border-blue-500/30 font-semibold shrink-0 capitalize">{trend.seasonality}</span>
                            )}
                        </div>
                        <MiniSparkline direction={trend.direction} strength={trend.strength} />
                    </div>

                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs" style={{ color: 'var(--page-muted)' }}>Strength</span>
                        <div className="flex-1 h-1.5 bg-[var(--surface-2)] rounded-full overflow-hidden max-w-[100px]">
                            <motion.div className={cn('h-full rounded-full', barColor)} initial={{ width: 0 }} animate={{ width: `${trend.strength * 100}%` }} transition={{ duration: 0.8, ease: 'easeOut' }} />
                        </div>
                        <span className={cn('text-xs font-mono font-bold', color)}>{trend.strength.toFixed(2)}</span>
                        {trend.p_value !== undefined && <span className="text-xs font-mono ml-1" style={{ color: 'var(--page-muted)' }}>p={trend.p_value.toFixed(4)}</span>}
                    </div>

                    <p className="text-xs leading-relaxed mb-2.5" style={{ color: 'var(--page-text)' }}>{renderBold(trend.plain_english)}</p>

                    <button
                        onClick={() => onInvestigate(`Analyze the ${trend.direction || 'temporal'} trend in "${trend.column}" (strength=${trend.strength}, p=${trend.p_value}). What is driving this? Is it seasonal? What should I expect next?`)}
                        className="flex items-center gap-1.5 text-[13px] transition-colors font-medium"
                        style={{ color: 'var(--accent-primary)' }}
                    >
                        <MessageSquare className="w-3 h-3" />
                        Forecast with AI <ArrowRight className="w-2.5 h-2.5" />
                    </button>
                </div>
            </div>
        </motion.div>
    );
};

const TrendAnalysis = ({ trends = [], onInvestigate }) => {
    if (trends.length === 0) {
        return (
            <div className="rounded-2xl p-8 text-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center border" style={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--surface-border)' }}>
                    <Clock className="w-6 h-6" style={{ color: 'var(--page-muted)' }} />
                </div>
                <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--page-text)' }}>No Temporal Trends</h3>
                <p className="text-xs" style={{ color: 'var(--page-muted)' }}>No time-based columns found or no significant trends detected.</p>
            </div>
        );
    }

    const sigCount = trends.filter(t => t.is_significant).length;

    return (
        <div className="backdrop-blur-sm rounded-2xl overflow-hidden border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
            <div className="px-5 pt-5 pb-4">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center justify-center">
                        <TrendingUp className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--page-text)' }}>Trend Analysis</h3>
                        <p className="text-[13px] mt-0.5" style={{ color: 'var(--page-muted)' }}>
                            {trends.length} temporal pattern{trends.length !== 1 ? 's' : ''}
                            {sigCount > 0 && <span className="text-emerald-400 ml-1">· {sigCount} significant</span>}
                        </p>
                    </div>
                </div>
            </div>
            <div className="px-5 pb-5 space-y-3">
                {trends.map((trend, i) => (
                    <TrendCard key={`${trend.column}-${i}`} trend={trend} index={i} onInvestigate={onInvestigate} />
                ))}
            </div>
        </div>
    );
};

export default TrendAnalysis;
