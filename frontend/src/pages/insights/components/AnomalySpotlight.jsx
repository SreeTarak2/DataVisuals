/**
 * AnomalySpotlight — SVG ring gauge per anomaly, severity-based borders
 */
import React from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, MessageSquare, ArrowRight, CheckCircle, Activity } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';

const SEV = {
    high:   { track: 'stroke-red-900/50',     fill: 'stroke-red-400',     text: 'text-red-400',     border: 'border-l-red-500',    badge: 'bg-red-500/15 text-red-400 border-red-500/30'   },
    medium: { track: 'stroke-amber-900/50',   fill: 'stroke-amber-400',   text: 'text-amber-400',   border: 'border-l-amber-500',  badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
    low:    { track: 'stroke-emerald-900/50', fill: 'stroke-emerald-400', text: 'text-emerald-400', border: 'border-l-emerald-600', badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
};

const AnomalyRing = ({ percentage, severity }) => {
    const cfg = SEV[severity] || SEV.low;
    const size = 64; const sw = 6; const r = (size - sw) / 2;
    const circ = r * 2 * Math.PI;
    const fillPct = Math.min(percentage * 5, 100);
    return (
        <div className="relative shrink-0" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <circle cx={size/2} cy={size/2} r={r} fill="none" strokeWidth={sw} className={cfg.track} />
                <motion.circle cx={size/2} cy={size/2} r={r} fill="none" strokeWidth={sw} strokeLinecap="round"
                    className={cfg.fill}
                    initial={{ strokeDashoffset: circ }}
                    animate={{ strokeDashoffset: circ - (fillPct / 100) * circ }}
                    transition={{ duration: 0.9, ease: 'easeOut' }}
                    strokeDasharray={circ}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={cn('text-xs font-bold', cfg.text)}>{percentage}%</span>
            </div>
        </div>
    );
};

const AnomalyCard = ({ anomaly, index, onInvestigate }) => {
    const cfg = SEV[anomaly.severity] || SEV.low;
    return (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}
            className={cn('flex items-start gap-4 p-4 rounded-xl border-l-4 border transition-all', cfg.border)}
            style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}
        >
            <AnomalyRing percentage={anomaly.percentage} severity={anomaly.severity} />
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <span className="text-[13px] font-semibold" style={{ color: 'var(--page-text)' }}>{anomaly.column}</span>
                    <span className={cn('text-xs px-1.5 py-0.5 rounded-full border font-semibold', cfg.badge)}>{anomaly.count} outliers</span>
                    <span className="text-xs px-1.5 py-0.5 rounded-full border" style={{ backgroundColor: 'var(--surface-2)', color: 'var(--page-text)', borderColor: 'var(--surface-border)' }}>{anomaly.method}</span>
                </div>
                <p className="text-xs leading-relaxed mb-2.5" style={{ color: 'var(--page-text)' }}>{renderBold(anomaly.plain_english)}</p>
                <button
                    onClick={() => onInvestigate(`I found ${anomaly.count} outliers (${anomaly.percentage}%) in column "${anomaly.column}" using ${anomaly.method}. Show me these outliers, explain why they might exist, and advise whether I should keep or remove them.`)}
                    className="flex items-center gap-1.5 text-[13px] transition-colors font-medium"
                    style={{ color: 'var(--accent-primary)' }}
                >
                    <MessageSquare className="w-3 h-3" />
                    Investigate with AI <ArrowRight className="w-2.5 h-2.5" />
                </button>
            </div>
        </motion.div>
    );
};

const AnomalySpotlight = ({ anomalies = [], onInvestigate }) => {
    if (anomalies.length === 0) {
        return (
            <div className="rounded-2xl p-8 text-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                    <CheckCircle className="w-6 h-6 text-emerald-400" />
                </div>
                <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--page-text)' }}>No Anomalies Detected</h3>
                <p className="text-xs" style={{ color: 'var(--page-muted)' }}>All columns are within expected ranges. Your data looks clean!</p>
            </div>
        );
    }

    const highCount   = anomalies.filter(a => a.severity === 'high').length;
    const mediumCount = anomalies.filter(a => a.severity === 'medium').length;

    return (
        <div className="backdrop-blur-sm rounded-2xl overflow-hidden border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
            <div className="px-5 pt-5 pb-4">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center justify-center">
                        <Activity className="w-4 h-4 text-red-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--page-text)' }}>Anomalies & Outliers</h3>
                        <p className="text-[13px] mt-0.5" style={{ color: 'var(--page-muted)' }}>
                            {anomalies.length} column{anomalies.length !== 1 ? 's' : ''} with unusual patterns
                            {highCount > 0 && <span className="text-red-400 ml-1">· {highCount} high</span>}
                            {mediumCount > 0 && <span className="text-amber-400 ml-1">· {mediumCount} moderate</span>}
                        </p>
                    </div>
                </div>
            </div>
            <div className="px-5 pb-5 space-y-3">
                {anomalies.map((anomaly, i) => (
                    <AnomalyCard key={`${anomaly.column}-${i}`} anomaly={anomaly} index={i} onInvestigate={onInvestigate} />
                ))}
            </div>
        </div>
    );
};

export default AnomalySpotlight;
