/**
 * DriverAnalysis — Feature importance visualization showing what drives each target variable.
 * Uses mutual information scores from the backend FeatureAnalyzer.
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Target, ChevronDown, MessageSquare, ArrowRight, Cpu } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { renderBold } from '../../../lib/renderBold';

const ImportanceBar = ({ value, maxValue, rank }) => {
    const pct = maxValue > 0 ? (value / maxValue) * 100 : 0;
    const colors = [
        'bg-gradient-to-r from-violet-600 to-violet-400',
        'bg-gradient-to-r from-blue-600 to-blue-400',
        'bg-gradient-to-r from-cyan-600 to-cyan-400',
        'bg-gradient-to-r from-teal-600 to-teal-400',
        'bg-gradient-to-r from-emerald-600 to-emerald-400',
    ];
    return (
        <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-slate-800/80 rounded-full overflow-hidden">
                <motion.div
                    className={cn('h-full rounded-full', colors[rank % colors.length])}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.8, ease: 'easeOut', delay: rank * 0.08 }}
                />
            </div>
            <span className="text-xs font-mono font-bold text-slate-300 w-14 text-right tabular-nums">
                {value.toFixed(4)}
            </span>
        </div>
    );
};

const DriverCard = ({ driver, index, onInvestigate }) => {
    const [expanded, setExpanded] = useState(false);
    const maxImportance = driver.drivers?.[0]?.importance || 1;

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.06 }}
            className="rounded-xl border border-slate-800/60 bg-slate-900/40 hover:bg-slate-800/40 hover:border-slate-700/60 transition-all duration-200 overflow-hidden"
        >
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full p-4 text-left"
            >
                <div className="flex items-center gap-3 mb-3">
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500/20 to-blue-500/20 border border-violet-500/25 flex items-center justify-center shrink-0">
                        <Target className="w-4 h-4 text-violet-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-white">
                                What drives <span className="text-violet-400">{driver.target}</span>?
                            </span>
                            <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700/60 font-mono uppercase tracking-wider">
                                {driver.method?.replace('_', ' ')}
                            </span>
                        </div>
                    </div>
                    <ChevronDown className={cn(
                        'w-4 h-4 text-slate-500 shrink-0 transition-transform duration-200',
                        expanded && 'rotate-180'
                    )} />
                </div>

                {/* Top drivers horizontal bars */}
                <div className="space-y-2">
                    {driver.drivers?.slice(0, expanded ? undefined : 3).map((d, i) => (
                        <div key={d.column}>
                            <div className="flex items-center justify-between mb-0.5">
                                <span className="text-xs text-slate-300 font-medium truncate max-w-[60%]">
                                    {d.column}
                                </span>
                                <span className="text-[11px] text-slate-500">
                                    #{i + 1}
                                </span>
                            </div>
                            <ImportanceBar
                                value={d.importance}
                                maxValue={maxImportance}
                                rank={i}
                            />
                        </div>
                    ))}
                </div>
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
                        <div className="border-t border-slate-800/60 px-4 py-3 space-y-3">
                            {driver.plain_english && (
                                <p className="text-xs text-slate-300 leading-relaxed">
                                    {renderBold(driver.plain_english)}
                                </p>
                            )}
                            <button
                                onClick={() => onInvestigate(
                                    `Explain the key drivers of "${driver.target}". The top driver is "${driver.drivers?.[0]?.column}" with importance ${driver.drivers?.[0]?.importance}. Is this causal or just correlational? What actions can I take based on these drivers?`
                                )}
                                className="flex items-center gap-1.5 text-[13px] text-violet-400 hover:text-violet-300 transition-colors font-medium"
                            >
                                <MessageSquare className="w-3 h-3" />
                                Analyze drivers with AI
                                <ArrowRight className="w-2.5 h-2.5" />
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

const DriverAnalysis = ({ drivers = [], onInvestigate }) => {
    if (drivers.length === 0) {
        return (
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-8 text-center">
                <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-slate-800/60 border border-slate-700/40 flex items-center justify-center">
                    <Cpu className="w-6 h-6 text-slate-500" />
                </div>
                <h3 className="text-sm font-semibold text-white mb-1">No Driver Analysis</h3>
                <p className="text-xs text-slate-400">Not enough numeric columns to compute feature importance.</p>
            </div>
        );
    }

    const totalDrivers = drivers.reduce((sum, d) => sum + (d.drivers?.length || 0), 0);

    return (
        <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/60 rounded-2xl overflow-hidden">
            <div className="px-5 pt-5 pb-4">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-violet-500/10 border border-violet-500/20 rounded-xl flex items-center justify-center">
                        <Cpu className="w-4 h-4 text-violet-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">Driver Analysis</h3>
                        <p className="text-[13px] text-slate-400 mt-0.5">
                            {totalDrivers} feature{totalDrivers !== 1 ? 's' : ''} across {drivers.length} target{drivers.length !== 1 ? 's' : ''}
                            <span className="text-violet-400/70 ml-1.5">· Mutual Information</span>
                        </p>
                    </div>
                </div>
            </div>
            <div className="px-5 pb-5 space-y-3">
                {drivers.map((driver, i) => (
                    <DriverCard
                        key={driver.target || i}
                        driver={driver}
                        index={i}
                        onInvestigate={onInvestigate}
                    />
                ))}
            </div>
        </div>
    );
};

export default DriverAnalysis;
