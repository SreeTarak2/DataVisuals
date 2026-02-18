import React, { useState, useEffect, useCallback } from 'react';
import { Database, Settings, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import useDatasetStore from '../../store/datasetStore';
import { datasetAPI, chartAPI } from '../../services/api';
import DataPanel from '../../components/features/charts/DataPanel';
import ChartCanvas from '../../components/features/charts/ChartCanvas';
import FormatPanel from '../../components/features/charts/FormatPanel';
import EncodingBar from '../../components/features/charts/EncodingBar';

// Enterprise color palette
const COLORS = {
    bg: '#0d1117',
    surface: '#161b22',
    border: '#30363d',
    textPrimary: '#e6edf3',
    textSecondary: '#8b949e',
    accent: '#58a6ff',
    success: '#3fb950',
    warning: '#d29922',
    error: '#f85149',
};

// Chart type definitions - all 16 backend-supported types with images
const CHART_TYPES = [
    { id: 'bar', label: 'Bar Chart', image: '/src/assets/bar.webp', enabled: true },
    { id: 'line', label: 'Line Chart', image: '/src/assets/line.webp', enabled: true },
    { id: 'area', label: 'Area Chart', image: '/src/assets/area.webp', enabled: true },
    { id: 'scatter', label: 'Scatter Plot', image: '/src/assets/scatter.webp', enabled: true },
    { id: 'pie', label: 'Pie Chart', image: '/src/assets/pie.webp', enabled: true },
    { id: 'treemap', label: 'Treemap', image: '/src/assets/logchart.webp', enabled: true }, // Using logchart as placeholder
    { id: 'sunburst', label: 'Sunburst', image: '/src/assets/radar.webp', enabled: true }, // Using radar as placeholder
    { id: 'funnel', label: 'Funnel Chart', image: '/src/assets/waterfall.webp', enabled: true },
    { id: 'histogram', label: 'Histogram', image: '/src/assets/histogram.webp', enabled: true },
    { id: 'box_plot', label: 'Box Plot', image: '/src/assets/boxplot.webp', enabled: true },
    { id: 'violin', label: 'Violin Plot', image: '/src/assets/boxplot.webp', enabled: true }, // Using boxplot as placeholder
    { id: 'heatmap', label: 'Heatmap', image: '/src/assets/heatmap.webp', enabled: true },
    { id: 'radar', label: 'Radar Chart', image: '/src/assets/radar.webp', enabled: true },
    { id: 'bubble', label: 'Bubble Chart', image: '/src/assets/bubble.webp', enabled: true },
    { id: 'waterfall', label: 'Waterfall', image: '/src/assets/waterfall.webp', enabled: true },
    { id: 'gauge', label: 'Gauge', image: '/src/assets/pie.webp', enabled: true }, // Using pie as placeholder
];

const ChartsStudio = () => {
    const { selectedDataset } = useDatasetStore();

    // Panel visibility
    const [showDataPanel, setShowDataPanel] = useState(true);
    const [showFormatPanel, setShowFormatPanel] = useState(true);

    // Data state
    const [columns, setColumns] = useState([]);
    const [loading, setLoading] = useState(false);
    const [chartData, setChartData] = useState(null);

    // Chart configuration
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
            colorPalette: ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#a371f7'],
        },
    });

    // Load dataset columns
    useEffect(() => {
        if (selectedDataset?.is_processed) {
            loadColumns();
        }
    }, [selectedDataset]);

    // Regenerate chart when config changes
    useEffect(() => {
        if (chartConfig.encoding.x.field && chartConfig.encoding.y.field) {
            generateChart();
        }
    }, [chartConfig.chartType, chartConfig.encoding]);

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

    // No dataset selected
    if (!selectedDataset) {
        return (
            <div className="h-full flex items-center justify-center bg-[#0b1117]">
                <div className="text-center">
                    <Database className="w-12 h-12 mx-auto mb-4 text-slate-700" />
                    <h2 className="text-lg font-semibold mb-2 text-slate-300">
                        No Dataset Selected
                    </h2>
                    <p className="mb-6 text-sm text-slate-500">
                        Select a dataset from the Dashboard to start building charts.
                    </p>
                    <button
                        onClick={() => window.location.href = '/dashboard'}
                        className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
                    >
                        Go to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-[#0b1117] overflow-hidden">
            {/* Toolbar */}
            <header className="h-8 min-h-[32px] flex items-center justify-between px-2 border-b border-slate-800 bg-[#0d141f]">
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5">
                        <button
                            onClick={() => setShowDataPanel(!showDataPanel)}
                            className={`p-1 rounded transition-colors ${showDataPanel ? 'bg-blue-500/10 text-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
                            title="Toggle Data Panel"
                        >
                            <Database size={12} />
                        </button>
                        <h1 className="text-xs font-semibold text-slate-200">
                            Charts Studio
                        </h1>
                    </div>
                    <div className="h-3 w-[1px] bg-slate-700" />
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        {selectedDataset?.name}
                    </span>
                </div>

                <div className="flex items-center gap-1.5">
                    <button
                        onClick={() => toast.success('Chart saved!')}
                        disabled={!chartData}
                        className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        Save
                    </button>
                    <button
                        onClick={() => toast.success('Exported!')}
                        disabled={!chartData}
                        className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        Export
                    </button>
                    <div className="h-3 w-[1px] bg-slate-700" />
                    <button
                        onClick={() => setShowFormatPanel(!showFormatPanel)}
                        className={`p-1 rounded transition-colors ${showFormatPanel ? 'bg-blue-500/10 text-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
                        title="Toggle Format Panel"
                    >
                        <Settings size={12} />
                    </button>
                </div>
            </header>

            {/* Main Workspace */}
            <div className="flex-1 flex overflow-hidden">
                {/* Data Panel (Left Sidebar) */}
                <AnimatePresence mode="popLayout">
                    {showDataPanel && (
                        <motion.div
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: 240, opacity: 1 }}
                            exit={{ width: 0, opacity: 0 }}
                            transition={{ duration: 0.2, ease: "easeInOut" }}
                            className="bg-[#0b1117] overflow-hidden flex flex-col"
                        >
                            <div className="w-[240px] h-full">
                                <DataPanel
                                    columns={columns}
                                    encoding={chartConfig.encoding}
                                    onUpdateEncoding={updateEncoding}
                                />
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Center Canvas */}
                <div className="flex-1 flex flex-col min-w-0 bg-[#0b1117] relative">
                    <ChartCanvas
                        chartData={chartData}
                        chartConfig={chartConfig}
                        loading={loading}
                    />

                    {/* Encoding Bar (Bottom Fixed) */}
                    <div className="flex-shrink-0">
                        <EncodingBar
                            columns={columns}
                            encoding={chartConfig.encoding}
                            onUpdateEncoding={updateEncoding}
                            onRefresh={generateChart}
                        />
                    </div>
                </div>

                {/* Format Panel (Right Sidebar) */}
                <AnimatePresence mode="popLayout">
                    {showFormatPanel && (
                        <motion.div
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: 280, opacity: 1 }}
                            exit={{ width: 0, opacity: 0 }}
                            transition={{ duration: 0.2, ease: "easeInOut" }}
                            className="bg-[#0b1117] overflow-hidden flex flex-col"
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
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default ChartsStudio;
