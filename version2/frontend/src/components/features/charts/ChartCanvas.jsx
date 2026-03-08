import React from 'react';
import { Loader2, BarChart3, MessageSquare } from 'lucide-react';
import { motion } from 'framer-motion';
import PlotlyChart from './PlotlyChart';

const CHART_THEME = {
    bg: '#020203',
    surface: '#1A191C',
    textPrimary: '#CAD2FD',
    textSecondary: '#6C6E79',
    border: 'rgba(202,210,253,0.06)',
    gridline: 'rgba(202,210,253,0.04)',
};

const ChartCanvas = ({ chartData, chartConfig, loading, onAskAI }) => {
    // Empty state
    if (!chartConfig.encoding.x.field || !chartConfig.encoding.y.field) {
        return (
            <div className="flex-1 flex items-center justify-center bg-noir">
                <div className="text-center max-w-md">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-ocean/10 flex items-center justify-center">
                        <BarChart3 size={24} className="text-ocean" />
                    </div>
                    <h3 className="text-[13px] font-semibold mb-1.5 text-pearl">
                        Start Building
                    </h3>
                    <p className="text-[11px] text-granite leading-relaxed px-8">
                        Select fields from the Data Panel or use the toolbar below.
                    </p>
                </div>
            </div>
        );
    }

    // Loading state
    if (loading) {
        return (
            <div className="flex-1 flex items-center justify-center bg-noir">
                <div className="text-center">
                    <Loader2 size={20} className="mx-auto mb-3 animate-spin text-ocean" />
                    <p className="text-[11px] text-granite tracking-wide">
                        Generating chart…
                    </p>
                </div>
            </div>
        );
    }

    // No data state
    if (!chartData) {
        return (
            <div className="flex-1 flex items-center justify-center bg-noir">
                <div className="text-center max-w-md">
                    <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-gold/10 flex items-center justify-center">
                        <span className="text-lg">⚠️</span>
                    </div>
                    <h3 className="text-[13px] font-semibold mb-1.5 text-pearl">
                        No Data Available
                    </h3>
                    <p className="text-[11px] text-granite leading-relaxed max-w-[250px] mx-auto">
                        Try changing the aggregation or selecting different fields.
                    </p>
                </div>
            </div>
        );
    }

    // Chart display
    const { x, y } = chartConfig.encoding;

    return (
        <div className="flex-1 p-4 overflow-hidden bg-noir relative">
            <div className="h-full w-full rounded-lg border border-pearl/[0.06] overflow-hidden bg-midnight">

            {/* ── Ask AI about this chart ── */}
            {onAskAI && (
                <motion.button
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={onAskAI}
                    className="absolute top-7 right-7 z-20 w-8 h-8 rounded-lg bg-midnight/90 border border-pearl/[0.06] flex items-center justify-center text-granite hover:text-ocean hover:border-ocean/30 hover:bg-ocean/5 transition-all backdrop-blur-sm shadow-lg group"
                    title="Ask AI about this chart"
                >
                    <MessageSquare size={14} />
                    <span className="absolute right-full mr-2 px-2 py-1 rounded-md bg-midnight border border-pearl/[0.06] text-[10px] text-pearl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity shadow-lg">
                        Ask AI
                    </span>
                </motion.button>
            )}
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
                            size: 11,
                        },
                        title: {
                            text: `${y.field} by ${x.field}`,
                            font: { size: 13, color: CHART_THEME.textPrimary },
                            x: 0.5,
                            xanchor: 'center',
                            y: 0.98,
                        },
                        xaxis: {
                            title: { text: x.field, font: { color: CHART_THEME.textSecondary, size: 11 } },
                            showgrid: chartConfig.format.showGrid,
                            gridcolor: CHART_THEME.gridline,
                            zeroline: false,
                            tickfont: { color: CHART_THEME.textSecondary, size: 10 },
                            linecolor: CHART_THEME.border,
                            tickangle: -45,
                            automargin: true,
                        },
                        yaxis: {
                            title: { text: y.field, font: { color: CHART_THEME.textSecondary, size: 11 } },
                            showgrid: chartConfig.format.showGrid,
                            gridcolor: CHART_THEME.gridline,
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
