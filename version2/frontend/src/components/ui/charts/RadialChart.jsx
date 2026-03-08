import React from 'react';
import BaseChart from './BaseChart';
import { motion } from 'framer-motion';

/**
 * Modern RadialChart (Gauge)
 * Perfect for KPI rates, completion scores, and progress metrics.
 */
export const RadialChart = ({
    value = 0,
    max = 100,
    label = 'Value',
    color = '#3b82f6', // blue-500
    bgColor = 'rgba(255,255,255,0.05)',
    trendAmount,
    trendDirection = 'up',
    trendLabel
}) => {
    // Normalize value
    const numValue = typeof value === 'number' ? value : parseFloat(value) || 0;

    const plotlyData = [{
        type: 'indicator',
        mode: 'gauge',
        value: numValue,
        gauge: {
            axis: { range: [0, max], visible: false },
            bar: { color: color, thickness: 0.35 },
            bgcolor: bgColor,
            borderwidth: 0,
            shape: 'angular',
        }
    }];

    const layout = {
        margin: { t: 20, b: trendAmount ? 40 : 20, l: 20, r: 20 },
    };

    return (
        <div className="relative w-full h-full flex flex-col">
            <div className="flex-1 relative min-h-0">
                <BaseChart data={plotlyData} layout={layout} config={{ staticPlot: true }}>

                    {/* Centered Value Text overlay */}
                    <div className="absolute inset-x-0 bottom-[35%] flex flex-col items-center justify-end pointer-events-none">
                        <motion.div
                            initial={{ y: 10, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            transition={{ delay: 0.1 }}
                            className="text-center"
                        >
                            <div className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight tabular-nums drop-shadow-sm">
                                {numValue.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                            </div>
                            <div className="text-xs font-semibold text-slate-400 mt-1 uppercase tracking-wider">
                                {label}
                            </div>
                        </motion.div>
                    </div>
                </BaseChart>
            </div>

            {trendAmount && (
                <div className="flex flex-col items-center justify-center pt-1 pb-2 shrink-0">
                    <div className="flex items-center gap-1.5 text-[13px] font-medium">
                        <span className="text-slate-300">
                            Trending {trendDirection} by {trendAmount}
                        </span>
                        {trendDirection === 'up' && <span className="text-emerald-400">↗</span>}
                        {trendDirection === 'down' && <span className="text-rose-400">↘</span>}
                        {trendDirection === 'neutral' && <span className="text-slate-400">→</span>}
                    </div>
                    {trendLabel && (
                        <div className="text-[11px] text-slate-500 mt-0.5">
                            {trendLabel}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
