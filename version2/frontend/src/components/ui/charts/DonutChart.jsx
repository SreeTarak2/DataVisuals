import React, { useMemo } from 'react';
import BaseChart from './BaseChart';
import { motion } from 'framer-motion';

/**
 * Modern Donut Chart
 * Replaces default pie charts with a clean donut featuring center text.
 * Perfect for showing parts-to-whole with a strong primary metric.
 */
export const DonutChart = ({
    data,
    centerAmount,
    centerLabel,
    trendAmount, // e.g. "5.2%"
    trendDirection = 'up', // 'up', 'down', 'neutral'
    trendLabel // e.g. "this month"
}) => {
    // Extract values and labels from raw data
    const values = data?.[0]?.y || data?.[0]?.values || [];
    const labels = data?.[0]?.x || data?.[0]?.labels || [];

    // Calculate total if not provided
    const total = useMemo(() => {
        if (centerAmount !== undefined) return centerAmount;
        return values.reduce((acc, curr) => acc + (Number(curr) || 0), 0);
    }, [values, centerAmount]);

    const defaultColors = ['#3b82f6', '#60a5fa', '#93c5fd', '#1e40af', '#bfdbfe'];

    const plotlyData = [{
        type: 'pie',
        values: values,
        labels: labels,
        hole: 0.75, // Large hole for modern donut look
        textinfo: 'none', // Hide labels on slices
        hoverinfo: 'label+percent+value',
        marker: {
            colors: data?.[0]?.marker?.colors || defaultColors,
            line: { color: 'rgba(0,0,0,0)', width: 0 } // No borders
        }
    }];

    const layout = {
        showlegend: false,
        margin: { t: 10, b: trendAmount ? 40 : 10, l: 10, r: 10 },
        hoverlabel: {
            bgcolor: '#1e293b',
            bordercolor: '#334155',
            font: { color: '#f8fafc', family: 'Inter', size: 12 }
        }
    };

    return (
        <div className="relative w-full h-full flex flex-col">
            <div className="flex-1 relative min-h-0">
                <BaseChart data={plotlyData} layout={layout}>

                    {/* Center Text Overlay */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ delay: 0.2, type: 'spring' }}
                            className="text-center"
                        >
                            <div className="text-2xl sm:text-3xl font-bold text-white tracking-tight tabular-nums">
                                {total.toLocaleString()}
                            </div>
                            <div className="text-[10px] sm:text-[11px] font-medium text-slate-400 mt-0.5">
                                {centerLabel || 'Total'}
                            </div>
                        </motion.div>
                    </div>
                </BaseChart>
            </div>

            {/* Modern Trend Footer (Shadcn style) */}
            {trendAmount && (
                <div className="flex flex-col items-center justify-center pt-2 pb-1 shrink-0">
                    <div className="flex items-center gap-1.5 text-sm font-medium">
                        <span className="text-slate-200">
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
