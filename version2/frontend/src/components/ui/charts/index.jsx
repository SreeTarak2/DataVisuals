// src/components/ui/charts/index.js

export { BaseChart } from './BaseChart';
export { DonutChart } from './DonutChart';
export { RadialChart } from './RadialChart';
export { BarChart } from './BarChart';
export { LineChart } from './LineChart';

/**
 * Shared Helper: ChartTrendFooter
 * Standardizes the "Trending up 5.2% ↗" text across all charts
 * if you prefer to use it standalone instead of built-in to the specific charts.
 */
export const ChartTrendFooter = ({
    trendAmount,
    trendDirection = 'up',
    trendLabel,
    className = ''
}) => {
    if (!trendAmount) return null;

    return (
        <div className={`flex flex-col items-start px-2 py-1 shrink-0 ${className}`}>
            <div className="flex items-center gap-1.5 text-sm font-medium">
                <span className="text-slate-200">
                    Trending {trendDirection} by {trendAmount}
                </span>
                {trendDirection === 'up' && <span className="text-emerald-400">↗</span>}
                {trendDirection === 'down' && <span className="text-rose-400">↘</span>}
                {trendDirection === 'neutral' && <span className="text-slate-400">→</span>}
            </div>
            {trendLabel && (
                <div className="text-xs text-slate-500 mt-0.5">
                    {trendLabel}
                </div>
            )}
        </div>
    );
};
