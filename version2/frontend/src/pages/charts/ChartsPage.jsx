import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Database, Loader2, Maximize2, Minimize2, Lightbulb,
    Sparkles, X, Send, Download, Image, FileSpreadsheet,
    ArrowRight, AlertTriangle, CheckCircle2,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import Plotly from 'plotly.js-dist-min';
import useDatasetStore from '../../store/datasetStore';
import { datasetAPI, chartAPI } from '../../services/api';
import DataPanel from '../../components/features/charts/DataPanel';
import ChartCanvas from '../../components/features/charts/ChartCanvas';
import FormatPanel from '../../components/features/charts/FormatPanel';
import EncodingBar from '../../components/features/charts/EncodingBar';
import ChartInsightsCard from '../../components/features/charts/ChartInsightsCard';

// Chart type definitions - all 16 backend-supported types with icons
const CHART_TYPES = [
    { id: 'bar', label: 'Bar Chart', enabled: true },
    { id: 'line', label: 'Line Chart', enabled: true },
    { id: 'area', label: 'Area Chart', enabled: true },
    { id: 'scatter', label: 'Scatter Plot', enabled: true },
    { id: 'pie', label: 'Pie Chart', enabled: true },
    { id: 'treemap', label: 'Treemap', enabled: true },
    { id: 'sunburst', label: 'Sunburst', enabled: true },
    { id: 'funnel', label: 'Funnel Chart', enabled: true },
    { id: 'histogram', label: 'Histogram', enabled: true },
    { id: 'box_plot', label: 'Box Plot', enabled: true },
    { id: 'violin', label: 'Violin Plot', enabled: true },
    { id: 'heatmap', label: 'Heatmap', enabled: true },
    { id: 'radar', label: 'Radar Chart', enabled: true },
    { id: 'bubble', label: 'Bubble Chart', enabled: true },
    { id: 'waterfall', label: 'Waterfall', enabled: true },
    { id: 'gauge', label: 'Gauge', enabled: true },
];

const MotionDiv = motion.div;

// ── Suggested next views helper ──
const generateNextViews = (columns, currentEncoding, currentChartType) => {
    if (!columns.length) return [];
    const views = [];
    const usedX = currentEncoding.x.field;
    const usedY = currentEncoding.y.field;
    const numericCols = columns.filter(c => {
        const t = (typeof c === 'string' ? 'unknown' : c.type?.toLowerCase()) || '';
        return ['numeric', 'integer', 'float', 'int64', 'float64'].includes(t);
    }).map(c => typeof c === 'string' ? c : c.name);
    const catCols = columns.filter(c => {
        const t = (typeof c === 'string' ? 'unknown' : c.type?.toLowerCase()) || '';
        return ['categorical', 'string', 'object', 'text'].includes(t);
    }).map(c => typeof c === 'string' ? c : c.name);

    // Suggest different chart type with same data
    const altTypes = ['bar', 'line', 'scatter', 'area', 'pie'].filter(t => t !== currentChartType);
    if (usedX && usedY && altTypes.length) {
        views.push({
            label: `${altTypes[0].charAt(0).toUpperCase() + altTypes[0].slice(1)} view`,
            icon: '📊',
            action: { chartType: altTypes[0], x: usedX, y: usedY },
        });
    }

    // Suggest a different Y field
    const otherNumeric = numericCols.filter(c => c !== usedY && c !== usedX);
    if (usedX && otherNumeric.length) {
        views.push({
            label: `${otherNumeric[0]} by ${usedX}`,
            icon: '📈',
            action: { chartType: currentChartType, x: usedX, y: otherNumeric[0] },
        });
    }

    // Suggest a different X field
    const otherCat = catCols.filter(c => c !== usedX);
    if (usedY && otherCat.length) {
        views.push({
            label: `${usedY} by ${otherCat[0]}`,
            icon: '🔄',
            action: { chartType: currentChartType, x: otherCat[0], y: usedY },
        });
    }

    // Suggest scatter if two numeric
    if (numericCols.length >= 2 && currentChartType !== 'scatter') {
        const [a, b] = numericCols;
        views.push({
            label: `${a} vs ${b} scatter`,
            icon: '⚡',
            action: { chartType: 'scatter', x: a, y: b },
        });
    }

    // Suggest pie for categorical
    if (catCols.length && numericCols.length && currentChartType !== 'pie') {
        views.push({
            label: `${numericCols[0]} by ${catCols[0]} (pie)`,
            icon: '🥧',
            action: { chartType: 'pie', x: catCols[0], y: numericCols[0] },
        });
    }

    return views.slice(0, 5);
};


const ChartsStudio = () => {
    const { selectedDataset } = useDatasetStore();

    // Panel states — collapsed by default on small screens
    const isMobile = typeof window !== 'undefined' && window.innerWidth < 900;
    const [showDataPanel, setShowDataPanel] = useState(!isMobile);
    const [showFormatPanel, setShowFormatPanel] = useState(!isMobile);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Data
    const [columns, setColumns] = useState([]);
    const [loading, setLoading] = useState(false);
    const [chartData, setChartData] = useState(null);

    // Export
    const [showExportMenu, setShowExportMenu] = useState(false);


    // Insights
    const [insights, setInsights] = useState(null);

    const [chartConfig, setChartConfig] = useState({
        chartType: 'bar',
        encoding: {
            x: { field: '', type: '' },
            y: { field: '', type: '', aggregate: 'sum' },
            group_by: '',
            color: null,
            size: null,
        },
        format: {
            showLegend: true,
            showLabels: false,
            showGrid: false,
            colorPalette: ['#7C3AED', '#0891B2', '#F59E0B', '#EF4444', '#8B5CF6'],
        },
    });

    const [rowLimit, setRowLimit] = useState(10000);

    // ── Load columns ──
    useEffect(() => {
        if (selectedDataset?.is_processed) {
            loadColumns();
        }
    }, [selectedDataset]);

    // ── Auto-generate chart ──
    useEffect(() => {
        if (chartConfig.encoding.x.field && chartConfig.encoding.y.field) {
            generateChart();
        }
    }, [chartConfig.chartType, chartConfig.encoding, rowLimit]);

    const loadColumns = async () => {
        if (!selectedDataset) return;
        try {
            if (selectedDataset.metadata?.column_metadata) {
                setColumns(selectedDataset.metadata.column_metadata);
                return;
            }
            const response = await datasetAPI.getDatasetData(selectedDataset.id, 1, 10);
            if (response.data?.data?.length > 0) {
                const colNames = Object.keys(response.data.data[0]);
                setColumns(colNames.map(name => ({ name, type: 'unknown' })));
            }
        } catch (error) {
            console.error('Failed to load columns:', error);
            toast.error('Failed to load dataset columns');
        }
    };

    const generateChart = async () => {
        if (!selectedDataset || !chartConfig.encoding.x.field || !chartConfig.encoding.y.field) return;
        setLoading(true);
        setInsights(null);
        try {
            const response = await chartAPI.renderChart(
                selectedDataset.id,
                chartConfig.chartType,
                [chartConfig.encoding.x.field, chartConfig.encoding.y.field],
                chartConfig.encoding.y.aggregate,
                {
                    include_insights: true,
                    limit: rowLimit,
                    groupBy: chartConfig.encoding.group_by,
                }
            );
            if (response.data?.traces?.length > 0) {
                setChartData(response.data);
                if (response.data.explanation || response.data.confidence > 0) {
                    setInsights({
                        summary: response.data.explanation,
                        confidence: response.data.confidence,
                    });
                }
            } else {
                setChartData(null);
                toast.error('No data for this configuration');
            }
        } catch (error) {
            console.error('Chart generation failed:', error);
            toast.error('Failed to generate chart');
            setChartData(null);
        } finally {
            setLoading(false);
        }
    };

    // AI deep analysis via /charts/explain
    const [insightsLoading, setInsightsLoading] = useState(false);
    const [showInsights, setShowInsights] = useState(false);

    const handleDeepAnalysis = async () => {
        if (!selectedDataset || !chartData) return;
        setInsightsLoading(true);
        setShowInsights(true);
        try {
            const chartKey = `${chartConfig.chartType}_${chartConfig.encoding.x.field}_${chartConfig.encoding.y.field}`;
            const response = await chartAPI.explainChart(
                selectedDataset.id,
                chartKey,
                {
                    chart_type: chartConfig.chartType,
                    columns: [chartConfig.encoding.x.field, chartConfig.encoding.y.field],
                    aggregation: chartConfig.encoding.y.aggregate,
                }
            );
            if (response.data) {
                setInsights(prev => ({
                    ...prev,
                    summary: response.data.explanation || prev?.summary || '',
                    enhanced_insight: response.data.explanation || '',
                    patterns: response.data.key_insights?.map((k, i) => ({ type: 'trend', description: k })) || [],
                    recommendations: response.data.reading_guide
                        ? [{ action: response.data.reading_guide }]
                        : [],
                    confidence: prev?.confidence || 0.8,
                }));
            }
        } catch (err) {
            console.error('Deep analysis failed:', err);
            toast.error('Failed to generate analysis');
        } finally {
            setInsightsLoading(false);
        }
    };

    const handleExportPNG = async () => {
        setShowExportMenu(false);
        const plotEl = document.querySelector('.js-plotly-plot');
        if (!plotEl) { toast.error('No chart to export'); return; }
        try {
            await Plotly.downloadImage(plotEl, {
                format: 'png', width: 1920, height: 1080,
                filename: `${chartConfig.encoding.y.field}_by_${chartConfig.encoding.x.field}`,
            });
            toast.success('PNG exported!');
        } catch { toast.error('Export failed'); }
    };

    const handleExportSVG = async () => {
        setShowExportMenu(false);
        const plotEl = document.querySelector('.js-plotly-plot');
        if (!plotEl) { toast.error('No chart to export'); return; }
        try {
            await Plotly.downloadImage(plotEl, {
                format: 'svg', width: 1920, height: 1080,
                filename: `${chartConfig.encoding.y.field}_by_${chartConfig.encoding.x.field}`,
            });
            toast.success('SVG exported!');
        } catch { toast.error('Export failed'); }
    };

    const handleExportCSV = () => {
        setShowExportMenu(false);
        if (!chartData?.traces?.length) { toast.error('No data to export'); return; }
        try {
            const xField = chartConfig.encoding.x.field || 'x';

            // Collect all series — skip fill/area ghost traces (no name, fill=tozeroy)
            const dataTraces = chartData.traces.filter(t =>
                t.name !== undefined || (t.x && t.y) || (t.labels && t.values)
            ).filter(t => t.fill !== 'tozeroy');

            if (dataTraces.length === 0) { toast.error('No data to export'); return; }

            const isPieType = dataTraces[0].labels && dataTraces[0].values;

            let rows;
            if (isPieType) {
                // Pie / donut: label, value
                rows = [['"Label"', '"Value"'].join(',')];
                const labels = dataTraces[0].labels || [];
                const values = dataTraces[0].values || [];
                for (let i = 0; i < labels.length; i++) {
                    rows.push([`"${labels[i] ?? ''}"`, `"${values[i] ?? ''}"`].join(','));
                }
            } else if (dataTraces.length === 1) {
                // Single series: x, y
                const trace = dataTraces[0];
                const yField = trace.name || chartConfig.encoding.y.field || 'y';
                rows = [[`"${xField}"`, `"${yField}"`].join(',')];
                const xVals = trace.x || [];
                const yVals = trace.y || [];
                for (let i = 0; i < Math.max(xVals.length, yVals.length); i++) {
                    rows.push([`"${xVals[i] ?? ''}"`, `"${yVals[i] ?? ''}"`].join(','));
                }
            } else {
                // Multi-series: x, series1, series2, …
                const header = [`"${xField}"`, ...dataTraces.map(t => `"${t.name || 'series'}"`)].join(',');
                rows = [header];
                // Use the x values from the first trace as the index
                const xVals = dataTraces[0].x || [];
                for (let i = 0; i < xVals.length; i++) {
                    const rowVals = [`"${xVals[i] ?? ''}"`];
                    for (const trace of dataTraces) {
                        rowVals.push(`"${(trace.y || [])[i] ?? ''}"`);
                    }
                    rows.push(rowVals.join(','));
                }
            }

            const filename = `${chartConfig.encoding.y.field || 'chart'}_by_${xField}`;
            const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${filename}.csv`;
            a.click();
            URL.revokeObjectURL(url);
            toast.success('CSV exported!');
        } catch (err) {
            console.error('CSV export failed:', err);
            toast.error('CSV export failed');
        }
    };

    const updateEncoding = useCallback((channel, value) => {
        setChartConfig(prev => ({
            ...prev,
            encoding: {
                ...prev.encoding,
                [channel]: typeof value === 'string'
                    ? { ...prev.encoding[channel], field: value }
                    : { ...prev.encoding[channel], ...value }
            }
        }));
    }, []);

    const updateChartType = useCallback((type) => {
        setChartConfig(prev => ({ ...prev, chartType: type }));
    }, []);

    const updateFormat = useCallback((key, value) => {
        setChartConfig(prev => ({
            ...prev,
            format: { ...prev.format, [key]: value }
        }));
    }, []);

    /* ── No dataset ── */
    if (!selectedDataset) {
        return (
            <div className="h-full flex items-center justify-center bg-primary">
                <div className="text-center max-w-sm px-10 py-12 rounded-3xl bg-surface border border-border shadow-soft">
                    <div className="w-20 h-20 rounded-2xl bg-accent-primary-light flex items-center justify-center mx-auto mb-8">
                        <Database className="w-10 h-10 text-accent-primary" />
                    </div>
                    <h2 className="text-xl font-bold mb-3 text-header">
                        No Dataset Selected
                    </h2>
                    <p className="mb-10 text-[14px] text-secondary leading-relaxed font-medium">
                        Select a processed dataset from your dashboard to begin building visualizations.
                    </p>
                    <button
                        onClick={() => window.location.href = '/app/dashboard'}
                        className="w-full px-8 py-3.5 rounded-xl bg-accent-primary text-white text-sm font-black uppercase tracking-widest hover:bg-accent-primary-hover shadow-lg shadow-accent-primary/20 transition-all hover:translate-y-[-1px] active:translate-y-[0px]"
                    >
                        Go to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-primary overflow-hidden">
            {/* ── Main Workspace ── */}
            <div className="flex-1 flex overflow-hidden">
                {/* Left: Data Panel — side column on desktop, overlay drawer on mobile */}
                <AnimatePresence mode="popLayout" initial={false}>
                    {showDataPanel && (
                        <>
                            {/* Mobile backdrop */}
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                onClick={() => setShowDataPanel(false)}
                                className="fixed inset-0 z-30 bg-black/40 md:hidden"
                            />
                            <MotionDiv
                                initial={{ x: -240, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: -240, opacity: 0 }}
                                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                className="fixed md:relative inset-y-0 left-0 z-40 md:z-20 w-[240px] flex flex-col shadow-xl md:shadow-none"
                            >
                                <div className="w-[240px] h-full">
                                    <DataPanel
                                        columns={columns}
                                        encoding={chartConfig.encoding}
                                        onUpdateEncoding={updateEncoding}
                                    />
                                </div>
                            </MotionDiv>
                        </>
                    )}
                </AnimatePresence>

                {/* Center: Canvas Area */}
                <div className="flex-1 flex flex-col min-w-0 bg-secondary relative">

                    <div className="flex-1 min-h-0 flex flex-col relative z-10 overflow-hidden">
                        {/* Status / Precision Bar (Zen Style) */}
                        {selectedDataset?.row_count > 10000 && (
                            <div className="absolute top-5 right-5 z-50 flex items-center gap-4 animate-in fade-in slide-in-from-top-2 duration-500">
                                <div className="flex gap-1.5 p-1 bg-surface/60 backdrop-blur-xl border border-border shadow-2xl rounded-full">
                                    {[
                                        { label: 'Draft', value: 10000 },
                                        { label: 'Deep', value: 1000000 },
                                    ].map(mode => (
                                        <button
                                            key={mode.label}
                                            onClick={() => setRowLimit(mode.value)}
                                            className={cn(
                                                "px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest transition-all",
                                                rowLimit === mode.value
                                                    ? "bg-accent-primary text-white shadow-lg shadow-accent-primary/20"
                                                    : "text-muted hover:text-header hover:bg-elevated"
                                            )}
                                        >
                                            {mode.label}
                                        </button>
                                    ))}
                                </div>
                                <div className="hidden lg:flex flex-col items-end">
                                    <span className="text-[10px] font-black text-header/40 uppercase tracking-widest leading-none">Dataset Scale</span>
                                    <span className="text-[11px] font-black text-accent-primary leading-tight mt-0.5">
                                        {rowLimit > 100000 ? 'Full Precision' : '10K Samples'}
                                    </span>
                                </div>
                            </div>
                        )}

                        <ChartCanvas
                            chartData={chartData}
                            chartConfig={chartConfig}
                            loading={loading}
                            onReset={() => {
                                setChartData(null);
                                setInsights(null);
                                setShowInsights(false);
                                setChartConfig(prev => ({
                                    ...prev,
                                    encoding: { x: { field: '', type: '' }, y: { field: '', type: '', aggregate: 'sum' }, group_by: '', color: null, size: null },
                                }));
                            }}
                            onAskAI={async (chip) => {
                                // If a chip string was passed, use chat context
                                if (typeof chip === 'string') {
                                    window.dispatchEvent(new CustomEvent('open-chat-with-context', {
                                        detail: { prompt: chip, datasetName: selectedDataset?.name || 'dataset' }
                                    }));
                                    return;
                                }
                                // Otherwise trigger deep analysis
                                await handleDeepAnalysis();
                            }}
                        />

                        {/* AI Insights Panel */}
                        <AnimatePresence>
                            {showInsights && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className="shrink-0 border-t border-border overflow-hidden"
                                >
                                    <div className="p-5">
                                        {insightsLoading ? (
                                            <div className="flex items-center gap-3 text-accent-primary">
                                                <motion.div
                                                    animate={{ rotate: 360 }}
                                                    transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                                                    className="w-4 h-4 border-2 border-accent-primary/20 border-t-accent-primary rounded-full"
                                                />
                                                <span className="text-[12px] font-bold">Generating deep analysis…</span>
                                            </div>
                                        ) : insights ? (
                                            <div className="relative">
                                                <button
                                                    onClick={() => setShowInsights(false)}
                                                    className="absolute top-0 right-0 p-1.5 rounded-lg text-muted hover:text-header transition-colors"
                                                    title="Close insights"
                                                >
                                                    <X size={14} />
                                                </button>
                                                <ChartInsightsCard insights={insights} />
                                            </div>
                                        ) : null}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Integrated Encoding Toolbar */}
                    <div className="shrink-0 p-3 mt-auto relative z-20">
                        <EncodingBar
                            columns={columns}
                            encoding={chartConfig.encoding}
                            onUpdateEncoding={updateEncoding}
                            onRefresh={generateChart}
                            showDataPanel={showDataPanel}
                            onToggleDataPanel={() => setShowDataPanel(!showDataPanel)}
                            showFormatPanel={showFormatPanel}
                            onToggleFormatPanel={() => setShowFormatPanel(!showFormatPanel)}
                            chartData={chartData}
                            onSave={() => toast.success('Workspace saved')}
                            onExport={() => setShowExportMenu(true)}
                        />
                    </div>
                </div>

                {/* Right: Format Panel — side column on desktop, overlay drawer on mobile */}
                <AnimatePresence mode="popLayout" initial={false}>
                    {showFormatPanel && (
                        <>
                            {/* Mobile backdrop */}
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                onClick={() => setShowFormatPanel(false)}
                                className="fixed inset-0 z-30 bg-black/40 md:hidden"
                            />
                            <MotionDiv
                                initial={{ x: 280, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: 280, opacity: 0 }}
                                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                className="fixed md:relative inset-y-0 right-0 z-40 md:z-20 w-[280px] flex flex-col shadow-xl md:shadow-none"
                            >
                                <div className="w-[280px] h-full">
                                    <FormatPanel
                                        format={chartConfig.format}
                                        chartType={chartConfig.chartType}
                                        chartTypes={CHART_TYPES}
                                        onUpdateFormat={updateFormat}
                                        onUpdateChartType={updateChartType}
                                    />
                                </div>
                            </MotionDiv>
                        </>
                    )}
                </AnimatePresence>
            </div>

            {/* Export Menu Overlay */}
            <AnimatePresence>
                {showExportMenu && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setShowExportMenu(false)}
                            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-md"
                        />
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: 10 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 10 }}
                            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[101] w-full max-w-sm p-10 rounded-2xl bg-surface shadow-[0_48px_96px_-12px_rgba(0,0,0,0.5)]"
                        >
                            <div className="flex items-center justify-between mb-8">
                                <h3 className="text-lg font-black text-header tracking-tight uppercase">Export Workflow</h3>
                                <button onClick={() => setShowExportMenu(false)} className="text-muted hover:text-header transition-colors cursor-pointer">
                                    <X size={20} />
                                </button>
                            </div>

                            <div className="grid gap-4">
                                <button onClick={handleExportPNG} className="flex items-center gap-5 p-5 rounded-xl bg-secondary/30 hover:bg-accent-primary hover:text-white transition-all group cursor-pointer">
                                    <div className="w-12 h-12 flex items-center justify-center rounded-xl bg-surface shadow-inner">
                                        <Image size={24} className="text-accent-primary group-hover:text-white transition-colors" />
                                    </div>
                                    <div className="text-left">
                                        <div className="text-[12px] font-black uppercase tracking-wider">Raster (PNG)</div>
                                        <div className="text-[11px] opacity-40 font-bold mt-0.5 group-hover:opacity-80 transition-opacity">Presentation ready image</div>
                                    </div>
                                    <ArrowRight size={16} className="ml-auto opacity-0 group-hover:opacity-100 transition-all -translate-x-2 group-hover:translate-x-0" />
                                </button>

                                <button onClick={handleExportSVG} className="flex items-center gap-5 p-5 rounded-xl bg-secondary/30 hover:bg-accent-purple hover:text-white transition-all group cursor-pointer">
                                    <div className="w-12 h-12 flex items-center justify-center rounded-xl bg-surface shadow-inner">
                                        <Maximize2 size={24} className="text-accent-purple group-hover:text-white transition-colors" />
                                    </div>
                                    <div className="text-left">
                                        <div className="text-[12px] font-black uppercase tracking-wider">Vector (SVG)</div>
                                        <div className="text-[11px] opacity-40 font-bold mt-0.5 group-hover:opacity-80 transition-opacity">Scalable graphics node</div>
                                    </div>
                                    <ArrowRight size={16} className="ml-auto opacity-0 group-hover:opacity-100 transition-all -translate-x-2 group-hover:translate-x-0" />
                                </button>

                                <button onClick={handleExportCSV} className="flex items-center gap-5 p-5 rounded-xl bg-secondary/30 hover:bg-accent-secondary hover:text-white transition-all group cursor-pointer">
                                    <div className="w-12 h-12 flex items-center justify-center rounded-xl bg-surface shadow-inner">
                                        <FileSpreadsheet size={24} className="text-accent-secondary group-hover:text-white transition-colors" />
                                    </div>
                                    <div className="text-left">
                                        <div className="text-[12px] font-black uppercase tracking-wider">Dataset (CSV)</div>
                                        <div className="text-[11px] opacity-40 font-bold mt-0.5 group-hover:opacity-80 transition-opacity">Raw computed results</div>
                                    </div>
                                    <ArrowRight size={16} className="ml-auto opacity-0 group-hover:opacity-100 transition-all -translate-x-2 group-hover:translate-x-0" />
                                </button>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
};

export default ChartsStudio;
