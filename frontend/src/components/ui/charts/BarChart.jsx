import React from 'react';
import BaseChart from './BaseChart';

/**
 * Modern Bar Chart
 * Removes all grid lines, uses clean rounded bars, 
 * and handles both categorical and histogram data elegantly.
 */
export const BarChart = ({
    data,
    color = '#8b5cf6', // violet-500
    trendAmount,
    trendDirection = 'up',
    trendLabel
}) => {
    // Extract values and labels from raw data
    const yValues = data?.[0]?.y || [];
    const xValues = data?.[0]?.x || [];

    const plotlyData = [{
        type: 'bar',
        x: xValues,
        y: yValues,
        hoverinfo: 'x+y',
        marker: {
            color: data?.[0]?.marker?.color || color,
            // Optional: add border radius manually if supported, 
            // Plotly 2+ supports some rounded corners
            line: {
                width: 0
            }
        }
    }];

    const layout = {
        barmode: 'group',
        margin: { t: 10, b: trendAmount ? 50 : 30, l: 40, r: 10 },
        xaxis: {
            showgrid: false,
            zeroline: false,
            showline: true,
            linecolor: 'rgba(255,255,255,0.05)',
            tickcolor: 'rgba(255,255,255,0)',
            tickfont: { color: '#94a3b8', size: 10 },
            tickangle: 0,
            automargin: true
        },
        yaxis: {
            showgrid: true,
            gridcolor: 'rgba(255,255,255,0.03)',
            gridwidth: 1,
            zeroline: false,
            showline: false,
            tickcolor: 'rgba(255,255,255,0)',
            tickfont: { color: '#64748b', size: 10 },
            automargin: true
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
                <div className="flex flex-col items-start px-2 pt-1 shrink-0 mt-[-10px]">
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
