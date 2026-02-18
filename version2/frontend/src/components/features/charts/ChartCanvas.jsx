import React from 'react';
import { Loader2, BarChart3 } from 'lucide-react';
import PlotlyChart from './PlotlyChart';

const CHART_THEME = {
    bg: '#0b1117',
    surface: '#0d141f',
    textPrimary: '#e2e8f0', // slate-200
    textSecondary: '#64748b', // slate-500
    border: '#1e293b', // slate-800
    accent: '#2563eb', // blue-600
    warning: '#eab308' // yellow-500
};

const ChartCanvas = ({ chartData, chartConfig, loading }) => {
    // Empty state
    if (!chartConfig.encoding.x.field || !chartConfig.encoding.y.field) {
        return (
            <div className="flex-1 flex items-center justify-center bg-[#0b1117]">
                <div className="text-center max-w-md">
                    <BarChart3 size={48} className="mx-auto mb-4 text-slate-700" />
                    <h3 className="text-sm font-semibold mb-2 text-slate-300 uppercase tracking-wide">
                        Start Building
                    </h3>
                    <p className="text-xs text-slate-500 leading-relaxed px-8">
                        Select fields from the Data Panel or use the toolbar below.
                    </p>
                </div>
            </div>
        );
    }

    // Loading state
    if (loading) {
        return (
            <div className="flex-1 flex items-center justify-center bg-[#0b1117]">
                <div className="text-center">
                    <Loader2 size={24} className="mx-auto mb-3 animate-spin text-blue-500" />
                    <p className="text-xs text-slate-500 uppercase tracking-wide">
                        Generating chart...
                    </p>
                </div>
            </div>
        );
    }

    // No data state
    if (!chartData) {
        return (
            <div className="flex-1 flex items-center justify-center bg-[#0b1117]">
                <div className="text-center max-w-md">
                    <div className="w-12 h-12 mx-auto mb-4 rounded-full flex items-center justify-center bg-yellow-500/10">
                        <span className="text-xl">⚠️</span>
                    </div>
                    <h3 className="text-sm font-semibold mb-2 text-slate-300">
                        No Data Available
                    </h3>
                    <p className="text-xs text-slate-500 leading-relaxed max-w-[250px] mx-auto">
                        Try changing the aggregation or selecting different fields.
                    </p>
                </div>
            </div>
        );
    }

    // Chart display
    const { x, y } = chartConfig.encoding;

    return (
        <div className="flex-1 p-4 overflow-hidden bg-[#0b1117]">
            <div className="h-full w-full rounded border border-slate-800 overflow-hidden bg-[#0d141f]">
                <PlotlyChart
                    data={chartData.traces.map(trace => ({
                        ...trace,
                        marker: {
                            ...trace.marker,
                            color: chartConfig.format.colorPalette[0],
                        },
                        line: {
                            ...trace.line,
                            color: chartConfig.format.colorPalette[0],
                            width: 2,
                        },
                    }))}
                    layout={{
                        ...chartData.layout,
                        autosize: true,
                        paper_bgcolor: 'transparent',
                        plot_bgcolor: 'transparent',
                        font: {
                            color: CHART_THEME.textSecondary,
                            family: 'Inter, -apple-system, system-ui, sans-serif',
                            size: 11
                        },
                        title: {
                            text: `${y.field} by ${x.field}`,
                            font: { size: 14, color: CHART_THEME.textPrimary },
                            x: 0.5,
                            xanchor: 'center',
                            y: 0.98,
                        },
                        xaxis: {
                            title: { text: x.field, font: { color: CHART_THEME.textSecondary, size: 11 } },
                            showgrid: chartConfig.format.showGrid,
                            gridcolor: CHART_THEME.border,
                            zeroline: false,
                            tickfont: { color: CHART_THEME.textSecondary, size: 10 },
                            linecolor: CHART_THEME.border,
                            tickangle: -45,
                            automargin: true,
                        },
                        yaxis: {
                            title: { text: y.field, font: { color: CHART_THEME.textSecondary, size: 11 } },
                            showgrid: chartConfig.format.showGrid,
                            gridcolor: CHART_THEME.border,
                            zeroline: false,
                            tickfont: { color: CHART_THEME.textSecondary, size: 10 },
                            linecolor: CHART_THEME.border,
                        },
                        margin: { l: 50, r: 20, t: 40, b: 70 },
                        showlegend: chartConfig.format.showLegend,
                        legend: {
                            bgcolor: 'transparent',
                            font: { color: CHART_THEME.textSecondary, size: 10 },
                        },
                        hovermode: 'x unified',
                        hoverlabel: {
                            bgcolor: CHART_THEME.surface,
                            bordercolor: CHART_THEME.border,
                            font: { color: CHART_THEME.textPrimary, size: 11 },
                        },
                    }}
                    config={{
                        displayModeBar: false,
                        responsive: true,
                    }}
                    style={{ width: '100%', height: '100%' }}
                />
            </div>
        </div>
    );
};

export default ChartCanvas;
