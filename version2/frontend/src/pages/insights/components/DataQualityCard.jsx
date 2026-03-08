/**
 * DataQualityCard — Premium health gauge with letter grade, metric bars, and quick stats
 */
import React from 'react';
import { motion } from 'framer-motion';
import { Shield, CheckCircle, Info } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';

const HEALTH_CONFIG = {
    emerald: { track: 'stroke-emerald-900/50', fill: 'stroke-emerald-400', text: 'text-emerald-400', bg: 'from-emerald-500/15 to-teal-500/10',   border: 'border-emerald-500/20', label: 'text-emerald-300', grade: 'A' },
    blue:    { track: 'stroke-blue-900/50',    fill: 'stroke-blue-400',    text: 'text-blue-400',    bg: 'from-blue-500/15 to-cyan-500/10',       border: 'border-blue-500/20',    label: 'text-blue-300',    grade: 'B' },
    amber:   { track: 'stroke-amber-900/50',   fill: 'stroke-amber-400',   text: 'text-amber-400',   bg: 'from-amber-500/15 to-orange-500/10',    border: 'border-amber-500/20',   label: 'text-amber-300',   grade: 'C' },
    red:     { track: 'stroke-red-900/50',     fill: 'stroke-red-400',     text: 'text-red-400',     bg: 'from-red-500/15 to-rose-500/10',        border: 'border-red-500/20',     label: 'text-red-300',     grade: 'D' },
};

const AnimatedGauge = ({ value, color }) => {
    const cfg = HEALTH_CONFIG[color] || HEALTH_CONFIG.blue;
    const size = 120; const sw = 10; const r = (size - sw) / 2;
    const circ = r * 2 * Math.PI;
    return (
        <div className="relative shrink-0" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={sw} className={cfg.track} strokeLinecap="round" />
                <motion.circle
                    cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={sw} strokeLinecap="round"
                    className={cfg.fill}
                    initial={{ strokeDashoffset: circ }}
                    animate={{ strokeDashoffset: circ - (value / 100) * circ }}
                    transition={{ duration: 1.4, ease: 'easeOut' }}
                    strokeDasharray={circ}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <motion.span className={cn('text-3xl font-bold', cfg.text)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
                    {Math.round(value)}
                </motion.span>
                <span className="text-xs text-slate-300 font-medium -mt-0.5">/ 100</span>
            </div>
        </div>
    );
};

const MetricBar = ({ label, value }) => {
    const barColor = value >= 95 ? 'bg-emerald-500' : value >= 80 ? 'bg-blue-500' : value >= 60 ? 'bg-amber-500' : 'bg-red-500';
    return (
        <div>
            <div className="flex justify-between text-[13px] mb-1">
                <span className="text-slate-200">{label}</span>
                <span className="text-slate-300 font-medium font-mono">{value}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <motion.div
                    className={cn('h-full rounded-full', barColor)}
                    initial={{ width: 0 }}
                    animate={{ width: `${value}%` }}
                    transition={{ duration: 0.9, ease: 'easeOut', delay: 0.3 }}
                />
            </div>
        </div>
    );
};

const DataQualityCard = ({ quality }) => {
    if (!quality) return null;
    const cfg = HEALTH_CONFIG[quality.health_color] || HEALTH_CONFIG.blue;

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative bg-slate-900/50 backdrop-blur-sm border border-slate-800/60 rounded-2xl overflow-hidden"
        >
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-slate-600/40 to-transparent" />

            <div className="p-6">
                {/* Header */}
                <div className="flex items-center gap-2 mb-5">
                    <div className={cn('w-8 h-8 rounded-xl flex items-center justify-center bg-gradient-to-br border', cfg.bg, cfg.border)}>
                        <Shield className={cn('w-4 h-4', cfg.text)} />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">Data Quality</h3>
                        <p className="text-[13px] text-slate-300">Health assessment</p>
                    </div>
                </div>

                {/* Gauge + Letter Grade */}
                <div className="flex items-center gap-4 mb-5">
                    <AnimatedGauge value={quality.health_score} color={quality.health_color} />
                    <div>
                        <motion.div
                            initial={{ scale: 0.5, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ delay: 0.6, type: 'spring' }}
                            className={cn('text-5xl font-black leading-none', cfg.text)}
                        >
                            {cfg.grade}
                        </motion.div>
                        <div className={cn('text-sm font-semibold mt-1', cfg.label)}>{quality.health_label}</div>
                        <div className="text-xs text-slate-300 mt-1">
                            {quality.total_rows?.toLocaleString()} rows · {quality.total_columns} cols
                        </div>
                    </div>
                </div>

                {/* Metric Progress Bars */}
                <div className="space-y-3 mb-4">
                    <MetricBar label="Completeness" value={quality.completeness} />
                    <MetricBar label="Uniqueness"   value={quality.uniqueness} />
                </div>

                {/* Quick Stats Grid */}
                <div className="grid grid-cols-2 gap-2 mb-4">
                    {quality.total_missing_cells > 0 ? (
                        <div className="bg-amber-500/8 border border-amber-500/15 rounded-xl p-2.5 text-center">
                            <div className="text-[13px] font-bold text-amber-400">{quality.total_missing_cells.toLocaleString()}</div>
                            <div className="text-xs text-slate-300">missing cells</div>
                        </div>
                    ) : (
                        <div className="bg-emerald-500/8 border border-emerald-500/15 rounded-xl p-2.5 text-center flex flex-col items-center">
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-400 mb-0.5" />
                            <div className="text-xs text-slate-300">No missing</div>
                        </div>
                    )}
                    {quality.duplicate_rows > 0 ? (
                        <div className="bg-red-500/8 border border-red-500/15 rounded-xl p-2.5 text-center">
                            <div className="text-[13px] font-bold text-red-400">{quality.duplicate_rows.toLocaleString()}</div>
                            <div className="text-xs text-slate-300">duplicates</div>
                        </div>
                    ) : (
                        <div className="bg-emerald-500/8 border border-emerald-500/15 rounded-xl p-2.5 text-center flex flex-col items-center">
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-400 mb-0.5" />
                            <div className="text-xs text-slate-300">No duplicates</div>
                        </div>
                    )}
                </div>

                {/* Tips */}
                {quality.tips?.length > 0 && (
                    <div className="space-y-1.5 pt-3 border-t border-slate-800/40">
                        {quality.tips.map((tip, i) => (
                            <div key={i} className="flex items-start gap-2 text-[13px] text-slate-200">
                                <Info className="w-3 h-3 text-slate-300 shrink-0 mt-0.5" />
                                <span>{renderBold(tip)}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </motion.div>
    );
};

export default DataQualityCard;
