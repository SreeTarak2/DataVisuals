import React from 'react';
import BaseChart from './BaseChart';

/**
 * Modern Line Chart
 * Emphasizes smooth spline lines, removes grid clutter, 
 * and adds an optional filled area for an elegant aesthetic.
 */
export const LineChart = ({
    data,
    color = '#0ea5e9', // sky-500
    fillArea = false,
    enableDots = true,
    trendAmount,
    trendDirection = 'up',
    trendLabel
}) => {
    const yValues = data?.[0]?.y || [];
    const xValues = data?.[0]?.x || [];

    const plotlyData = [{
        type: 'scatter',
        x: xValues,
        y: yValues,
        mode: enableDots ? 'lines+markers' : 'lines',
        line: {
            color: data?.[0]?.line?.color || color,
            width: 3,
            shape: 'spline', // Crucial: smooth curves instead of jaggy lines
            smoothing: 1.3
        },
        marker: {
            color: data?.[0]?.marker?.color || color,
            size: 6,
            symbol: 'circle',
            line: {
                color: '#0f172a', // Background color to make dot pop
                width: 2
            }
        },
        fill: fillArea ? 'tozeroy' : 'none',
        // Plotly doesn't natively do gradient fills well without complex layout shapes,
        // so we use a flat semi-transparent fill if requested
        fillcolor: fillArea ? `${color}15` : undefined, // 15 = ~8% opacity hex alpha
        hoverinfo: 'x+y'
    }];

    const layout = {
        margin: { t: 15, b: trendAmount ? 45 : 30, l: 40, r: 15 },
        xaxis: {
            showgrid: false,
            zeroline: false,
            showline: true,
            linecolor: 'rgba(255,255,255,0.05)',
            tickcolor: 'rgba(255,255,255,0)',
            tickfont: { color: '#94a3b8', size: 10 },
            tickangle: 0,
            automargin: true,
            title: { text: '' }
        },
        yaxis: {
            showgrid: true,
            gridcolor: 'rgba(255,255,255,0.04)',
            gridwidth: 1,
            zeroline: false,
            showline: false,
            tickcolor: 'rgba(255,255,255,0)',
            tickfont: { color: '#64748b', size: 10 },
            automargin: true,
            title: { text: '' }
        },
        hoverlabel: {
            bgcolor: '#1e293b',
            bordercolor: '#334155',
            font: { color: '#f8fafc', family: 'Inter', size: 12 }
        }
    };

    return (
        <div className="relative w-full h-full flex flex-col">
            <div className="flex-1 relative min-h-0">
                <BaseChart data={plotlyData} layout={layout} />
            </div>

            {trendAmount && (
                <div className="flex flex-col items-start px-2 pt-1 pb-1 shrink-0 mt-[-5px]">
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
            )}
        </div>
    );
};
