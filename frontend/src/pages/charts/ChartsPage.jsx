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

// Chart type definitions - all 16 backend-supported types with images
const CHART_TYPES = [
    { id: 'bar', label: 'Bar Chart', image: '/src/assets/bar.webp', enabled: true },
    { id: 'line', label: 'Line Chart', image: '/src/assets/line.webp', enabled: true },
    { id: 'area', label: 'Area Chart', image: '/src/assets/area.webp', enabled: true },
    { id: 'scatter', label: 'Scatter Plot', image: '/src/assets/scatter.webp', enabled: true },
    { id: 'pie', label: 'Pie Chart', image: '/src/assets/pie.webp', enabled: true },
    { id: 'treemap', label: 'Treemap', image: '/src/assets/logchart.webp', enabled: true },
    { id: 'sunburst', label: 'Sunburst', image: '/src/assets/radar.webp', enabled: true },
    { id: 'funnel', label: 'Funnel Chart', image: '/src/assets/waterfall.webp', enabled: true },
    { id: 'histogram', label: 'Histogram', image: '/src/assets/histogram.webp', enabled: true },
    { id: 'box_plot', label: 'Box Plot', image: '/src/assets/boxplot.webp', enabled: true },
    { id: 'violin', label: 'Violin Plot', image: '/src/assets/boxplot.webp', enabled: true },
    { id: 'heatmap', label: 'Heatmap', image: '/src/assets/heatmap.webp', enabled: true },
    { id: 'radar', label: 'Radar Chart', image: '/src/assets/radar.webp', enabled: true },
    { id: 'bubble', label: 'Bubble Chart', image: '/src/assets/bubble.webp', enabled: true },
    { id: 'waterfall', label: 'Waterfall', image: '/src/assets/waterfall.webp', enabled: true },
    { id: 'gauge', label: 'Gauge', image: '/src/assets/pie.webp', enabled: true },
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

    // Panel states
    const [showDataPanel, setShowDataPanel] = useState(true);
    const [showFormatPanel, setShowFormatPanel] = useState(true);
    const [showInsightsPanel, setShowInsightsPanel] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Data
    const [columns, setColumns] = useState([]);
    const [loading, setLoading] = useState(false);
    const [chartData, setChartData] = useState(null);

    // AI
    const [insights, setInsights] = useState(null);
    const [insightsLoading, setInsightsLoading] = useState(false);
    const [nlQuery, setNlQuery] = useState('');
    const [nlProcessing, setNlProcessing] = useState(false);

    // Export
    const [showExportMenu, setShowExportMenu] = useState(false);

    // Data quality
    const [dataQuality, setDataQuality] = useState(null);

    const [chartConfig, setChartConfig] = useState({
        chartType: 'bar',
        encoding: {
            x: { field: '', type: '' },
            y: { field: '', type: '', aggregate: 'sum' },
            color: null,
            size: null,
        },
        format: {
            showLegend: true,
            showLabels: false,
            showGrid: false,
            colorPalette: ['#5B88B2', '#10b981', '#f59e0b', '#ef4444', '#a78bfa'],
        },
    });

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
    }, [chartConfig.chartType, chartConfig.encoding]);

    // ── Keyboard: Esc exits fullscreen ──
    useEffect(() => {
        const handleKey = (e) => {
            if (e.key === 'Escape' && isFullscreen) setIsFullscreen(false);
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [isFullscreen]);

    // ── Data quality from metadata ──
    useEffect(() => {
        if (selectedDataset?.metadata) {
            const meta = selectedDataset.metadata;
            const nullCols = meta.column_metadata?.filter(c => c.null_count > 0) || [];
            const totalRows = meta.row_count || 0;
            const colCount = meta.column_metadata?.length || 1;
            const nullRatio = totalRows > 0
                ? nullCols.reduce((sum, c) => sum + (c.null_count / totalRows), 0) / Math.max(colCount, 1)
                : 0;

            setDataQuality({
                score: Math.round((1 - nullRatio) * 100),
                nullColumns: nullCols.length,
                totalRows,
                totalColumns: colCount,
            });
        }
    }, [selectedDataset]);

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
        try {
            const response = await chartAPI.generateChart(
                selectedDataset.id,
                chartConfig.chartType,
                chartConfig.encoding.x.field,
                chartConfig.encoding.y.field,
                chartConfig.encoding.y.aggregate
            );
            if (response.data?.traces?.length > 0) {
                setChartData(response.data);
                setInsights(null); // Clear old insights on new chart
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

    // ── AI Insights ──
    const fetchInsights = async () => {
        if (!chartData || !selectedDataset) return;
        setInsightsLoading(true);
        setShowInsightsPanel(true);
        try {
            const response = await chartAPI.getInsights(
                {
                    chart_type: chartConfig.chartType,
                    x_field: chartConfig.encoding.x.field,
                    y_field: chartConfig.encoding.y.field,
                    aggregation: chartConfig.encoding.y.aggregate,
                },
                chartData.traces || [],
                selectedDataset.id,
            );
            setInsights(response.data);
        } catch (error) {
            console.error('Failed to fetch insights:', error);
            setInsights({
                summary: 'Could not generate insights for this chart.',
                patterns: [],
                recommendations: ['Try a different chart type or fields.'],
                confidence: 0.3,
            });
        } finally {
            setInsightsLoading(false);
        }
    };

    // ── NL Refinement ──
    const handleNlQuery = async (e) => {
        e?.preventDefault();
        if (!nlQuery.trim() || nlProcessing) return;
        setNlProcessing(true);

        try {
            const q = nlQuery.toLowerCase().trim();

            // Chart type changes
            const typeMap = { 'bar': 'bar', 'line': 'line', 'scatter': 'scatter', 'pie': 'pie', 'area': 'area', 'heatmap': 'heatmap', 'box': 'box_plot', 'histogram': 'histogram', 'treemap': 'treemap', 'bubble': 'bubble', 'radar': 'radar', 'funnel': 'funnel', 'waterfall': 'waterfall', 'violin': 'violin' };
            for (const [keyword, type] of Object.entries(typeMap)) {
                if (q.includes(keyword)) {
                    updateChartType(type);
                    setNlQuery('');
                    toast.success(`Switched to ${keyword} chart`);
                    return;
                }
            }

            // Aggregation changes
            const aggMap = { 'average': 'avg', 'mean': 'avg', 'sum': 'sum', 'count': 'count', 'minimum': 'min', 'maximum': 'max', 'min': 'min', 'max': 'max' };
            for (const [keyword, agg] of Object.entries(aggMap)) {
                if (q.includes(keyword)) {
                    updateEncoding('y', { ...chartConfig.encoding.y, aggregate: agg });
                    setNlQuery('');
                    toast.success(`Changed aggregation to ${keyword}`);
                    return;
                }
            }

            // Field changes
            const allColNames = columns.map(c => typeof c === 'string' ? c : c.name);
            for (const col of allColNames) {
                if (q.includes(col.toLowerCase())) {
                    if (q.includes('x') || q.includes('horizontal') || q.includes('category')) {
                        updateEncoding('x', { field: col, type: '' });
                        setNlQuery('');
                        toast.success(`Set X axis to ${col}`);
                        return;
                    }
                    if (q.includes('y') || q.includes('vertical') || q.includes('value') || q.includes('measure')) {
                        updateEncoding('y', { field: col, type: '' });
                        setNlQuery('');
                        toast.success(`Set Y axis to ${col}`);
                        return;
                    }
                }
            }

            // Toggle changes
            if (q.includes('legend')) {
                updateFormat('showLegend', !chartConfig.format.showLegend);
                setNlQuery('');
                toast.success(`${chartConfig.format.showLegend ? 'Hid' : 'Showed'} legend`);
                return;
            }
            if (q.includes('grid')) {
                updateFormat('showGrid', !chartConfig.format.showGrid);
                setNlQuery('');
                toast.success(`${chartConfig.format.showGrid ? 'Hid' : 'Showed'} grid`);
                return;
            }
            if (q.includes('label')) {
                updateFormat('showLabels', !chartConfig.format.showLabels);
                setNlQuery('');
                toast.success(`${chartConfig.format.showLabels ? 'Hid' : 'Showed'} labels`);
                return;
            }

            toast('Try: "show as line chart", "average", or a column name', { icon: '💡' });
        } catch {
            toast.error('Could not parse that request');
        } finally {
            setNlProcessing(false);
            setNlQuery('');
        }
    };

    // ── Export ──
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
            const trace = chartData.traces[0];
            const xField = chartConfig.encoding.x.field || 'x';
            const yField = chartConfig.encoding.y.field || 'y';
            const rows = [[xField, yField].join(',')];
            const xVals = trace.x || [];
            const yVals = trace.y || trace.values || [];
            for (let i = 0; i < Math.max(xVals.length, yVals.length); i++) {
                rows.push([`"${xVals[i] ?? ''}"`, `"${yVals[i] ?? ''}"`].join(','));
            }
            const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${yField}_by_${xField}.csv`;
            a.click();
            URL.revokeObjectURL(url);
            toast.success('CSV exported!');
        } catch { toast.error('CSV export failed'); }
    };

    // ── Apply next-view suggestion ──
    const applyNextView = (view) => {
        if (view.action.chartType) updateChartType(view.action.chartType);
        if (view.action.x) updateEncoding('x', { field: view.action.x, type: '' });
        if (view.action.y) updateEncoding('y', { field: view.action.y, type: '' });
    };

    // ── Fullscreen ──
    const toggleFullscreen = () => {
        setIsFullscreen(prev => {
            if (!prev) { setShowDataPanel(false); setShowFormatPanel(false); }
            return !prev;
        });
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
            <div className="h-full flex items-center justify-center bg-noir">
                <div className="text-center max-w-sm">
                    <div className="w-12 h-12 rounded-xl bg-ocean/10 flex items-center justify-center mx-auto mb-4">
                        <Database className="w-5 h-5 text-ocean" />
                    </div>
                    <h2 className="text-base font-semibold mb-2 text-pearl">
                        No dataset selected
                    </h2>
                    <p className="mb-6 text-[13px] text-granite leading-relaxed">
                        Select a dataset from the Dashboard to start building charts.
                    </p>
                    <button
                        onClick={() => window.location.href = '/app/dashboard'}
                        className="px-4 py-2 rounded-lg bg-ocean text-white text-sm font-medium hover:bg-ocean/90 transition-colors"
                    >
                        Go to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-noir overflow-hidden">
            {/* ── Main Workspace ── */}
            <div className="flex-1 flex overflow-hidden">
                {/* Left: Data Panel */}
                <AnimatePresence mode="popLayout">
                    {showDataPanel && (
                        <MotionDiv
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: 240, opacity: 1 }}
                            exit={{ width: 0, opacity: 0 }}
                            transition={{ duration: 0.2, ease: "easeInOut" }}
                            className="bg-midnight overflow-hidden flex flex-col"
                        >
                            <div className="w-[240px] h-full">
                                <DataPanel
                                    columns={columns}
                                    encoding={chartConfig.encoding}
                                    onUpdateEncoding={updateEncoding}
                                />
                            </div>
                        </MotionDiv>
                    )}
                </AnimatePresence>

                {/* Center: Canvas */}
                <div className="flex-1 flex flex-col min-w-0 bg-noir relative">
                    <ChartCanvas
                        chartData={chartData}
                        chartConfig={chartConfig}
                        loading={loading}
                        onAskAI={async () => {
                            let chartImage = null;
                            try {
                                const plotEl = document.querySelector('.js-plotly-plot');
                                if (plotEl) {
                                    chartImage = await Plotly.toImage(plotEl, {
                                        format: 'png', width: 480, height: 280, scale: 2,
                                    });
                                }
                            } catch (e) { /* silent */ }
                            const ctx = {
                                chartType: chartConfig.chartType,
                                xField: chartConfig.encoding.x.field,
                                yField: chartConfig.encoding.y.field,
                                aggregation: chartConfig.encoding.y.aggregate,
                                datasetName: selectedDataset?.name || 'dataset',
                                chartImage,
                            };
                            window.dispatchEvent(new CustomEvent('open-chat-with-context', { detail: ctx }));
                        }}
                    />
                    <div className="flex-shrink-0">
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
                            onSave={() => toast.success('Chart saved!')}
                            onExport={() => toast.success('Exported!')}
                        />
                    </div>
                </div>

                {/* Right: Format Panel */}
                <AnimatePresence mode="popLayout">
                    {showFormatPanel && (
                        <MotionDiv
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: 280, opacity: 1 }}
                            exit={{ width: 0, opacity: 0 }}
                            transition={{ duration: 0.2, ease: "easeInOut" }}
                            className="bg-midnight overflow-hidden flex flex-col"
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
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default ChartsStudio;
