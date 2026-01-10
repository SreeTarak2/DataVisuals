import React from 'react';
import { Loader2, BarChart3 } from 'lucide-react';
import PlotlyChart from '../../../components/PlotlyChart';

const ChartCanvas = ({ chartData, chartConfig, loading, colors }) => {
    // Empty state
    if (!chartConfig.encoding.x.field || !chartConfig.encoding.y.field) {
        return (
            <div
                className="flex-1 flex items-center justify-center"
                style={{ backgroundColor: colors.bg }}
            >
                <div className="text-center max-w-md">
                    <BarChart3
                        size={64}
                        className="mx-auto mb-4 opacity-20"
                        style={{ color: colors.textSecondary }}
                    />
                    <h3
                        className="text-lg font-medium mb-2"
                        style={{ color: colors.textPrimary }}
                    >
                        Start Building Your Chart
                    </h3>
                    <p
                        className="text-sm leading-relaxed"
                        style={{ color: colors.textSecondary }}
                    >
                        Select fields from the Data Panel on the left, or use the Encoding Bar below to assign X and Y axes.
                    </p>
                </div>
            </div>
        );
    }

    // Loading state
    if (loading) {
        return (
            <div
                className="flex-1 flex items-center justify-center"
                style={{ backgroundColor: colors.bg }}
            >
                <div className="text-center">
                    <Loader2
                        size={32}
                        className="mx-auto mb-3 animate-spin"
                        style={{ color: colors.accent }}
                    />
                    <p
                        className="text-sm"
                        style={{ color: colors.textSecondary }}
                    >
                        Generating chart...
                    </p>
                </div>
            </div>
        );
    }

    // No data state
    if (!chartData) {
        return (
            <div
                className="flex-1 flex items-center justify-center"
                style={{ backgroundColor: colors.bg }}
            >
                <div className="text-center max-w-md">
                    <div
                        className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center"
                        style={{ backgroundColor: `${colors.warning}20` }}
                    >
                        <span className="text-2xl">⚠️</span>
                    </div>
                    <h3
                        className="text-lg font-medium mb-2"
                        style={{ color: colors.textPrimary }}
                    >
                        No Data Available
                    </h3>
                    <p
                        className="text-sm leading-relaxed"
                        style={{ color: colors.textSecondary }}
                    >
                        The selected configuration returned no data. Try using "Count" aggregation for categorical columns, or select a numeric column for the Y-axis.
                    </p>
                </div>
            </div>
        );
    }

    // Chart display
    const { x, y } = chartConfig.encoding;

    return (
        <div
            className="flex-1 p-4 overflow-hidden"
            style={{ backgroundColor: colors.bg }}
        >
            <div
                className="h-full w-full rounded-lg overflow-hidden"
                style={{ backgroundColor: colors.surface }}
            >
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
                            color: colors.textSecondary,
                            family: 'Inter, -apple-system, system-ui, sans-serif',
                            size: 12
                        },
                        title: {
                            text: `${y.field} by ${x.field}`,
                            font: { size: 16, color: colors.textPrimary },
                            x: 0.5,
                            xanchor: 'center',
                            y: 0.98,
                        },
                        xaxis: {
                            title: { text: x.field, font: { color: colors.textSecondary, size: 12 } },
                            showgrid: chartConfig.format.showGrid,
                            gridcolor: colors.border,
                            zeroline: false,
                            tickfont: { color: colors.textSecondary, size: 11 },
                            linecolor: colors.border,
                            tickangle: -45,
                            automargin: true,
                        },
                        yaxis: {
                            title: { text: y.field, font: { color: colors.textSecondary, size: 12 } },
                            showgrid: chartConfig.format.showGrid,
                            gridcolor: colors.border,
                            zeroline: false,
                            tickfont: { color: colors.textSecondary, size: 11 },
                            linecolor: colors.border,
                        },
                        margin: { l: 60, r: 20, t: 50, b: 80 },
                        showlegend: chartConfig.format.showLegend,
                        legend: {
                            bgcolor: 'transparent',
                            font: { color: colors.textSecondary },
                        },
                        hovermode: 'x unified',
                        hoverlabel: {
                            bgcolor: colors.surface,
                            bordercolor: colors.border,
                            font: { color: colors.textPrimary, size: 12 },
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
