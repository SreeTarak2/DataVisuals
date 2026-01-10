import React, { useState, useEffect, useCallback } from 'react';
import { Database, Settings, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import useDatasetStore from '../../store/datasetStore';
import { datasetAPI, chartAPI } from '../../services/api';
import DataPanel from './components/DataPanel';
import ChartCanvas from './components/ChartCanvas';
import FormatPanel from './components/FormatPanel';
import EncodingBar from './components/EncodingBar';

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
    const [showFormatPanel, setShowFormatPanel] = useState(false);

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
            <div className="h-screen flex items-center justify-center" style={{ backgroundColor: COLORS.bg }}>
                <div className="text-center">
                    <Database className="w-16 h-16 mx-auto mb-4" style={{ color: COLORS.textSecondary }} />
                    <h2 className="text-xl font-semibold mb-2" style={{ color: COLORS.textPrimary }}>
                        No Dataset Selected
                    </h2>
                    <p className="mb-6" style={{ color: COLORS.textSecondary }}>
                        Select a dataset from the Dashboard to start building charts.
                    </p>
                    <motion.button
                        whileTap={{ scale: 0.95 }}
                        onClick={() => window.location.href = '/dashboard'}
                        className="px-6 py-3 rounded-lg font-medium"
                        style={{ backgroundColor: COLORS.accent, color: '#fff' }}
                    >
                        Go to Dashboard
                    </motion.button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-screen flex flex-col" style={{ backgroundColor: COLORS.bg }}>
            {/* Header */}
            <header
                className="h-12 flex items-center justify-between px-4 border-b"
                style={{ backgroundColor: COLORS.surface, borderColor: COLORS.border }}
            >
                <div className="flex items-center gap-3">
                    <h1 className="text-base font-semibold" style={{ color: COLORS.textPrimary }}>
                        Charts Studio
                    </h1>
                    <span
                        className="text-xs px-2 py-0.5 rounded"
                        style={{ backgroundColor: COLORS.bg, color: COLORS.textSecondary }}
                    >
                        {selectedDataset?.name}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <motion.button
                        whileTap={{ scale: 0.95 }}
                        onClick={() => toast.success('Chart saved!')}
                        disabled={!chartData}
                        className="px-3 py-1.5 rounded text-sm font-medium disabled:opacity-40"
                        style={{ backgroundColor: COLORS.accent, color: '#fff' }}
                    >
                        Save
                    </motion.button>
                    <motion.button
                        whileTap={{ scale: 0.95 }}
                        onClick={() => toast.success('Exported!')}
                        disabled={!chartData}
                        className="px-3 py-1.5 rounded text-sm font-medium disabled:opacity-40"
                        style={{ backgroundColor: COLORS.surface, color: COLORS.textPrimary, border: `1px solid ${COLORS.border}` }}
                    >
                        Export
                    </motion.button>
                </div>
            </header>

            {/* Main Content */}
            <div className="flex-1 flex overflow-hidden">
                {/* Left Panel Toggle */}
                <button
                    onClick={() => setShowDataPanel(!showDataPanel)}
                    className="absolute left-0 top-1/2 -translate-y-1/2 z-10 p-1 rounded-r"
                    style={{ backgroundColor: COLORS.surface, border: `1px solid ${COLORS.border}` }}
                >
                    {showDataPanel ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
                </button>

                {/* Data Panel (Left Sidebar) */}
                <AnimatePresence>
                    {showDataPanel && (
                        <motion.div
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: 280, opacity: 1 }}
                            exit={{ width: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="border-r overflow-hidden"
                            style={{ backgroundColor: COLORS.surface, borderColor: COLORS.border }}
                        >
                            <DataPanel
                                columns={columns}
                                encoding={chartConfig.encoding}
                                onUpdateEncoding={updateEncoding}
                                colors={COLORS}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Chart Canvas (Center) */}
                <div className="flex-1 flex flex-col overflow-hidden">
                    <ChartCanvas
                        chartData={chartData}
                        chartConfig={chartConfig}
                        loading={loading}
                        colors={COLORS}
                    />

                    {/* Encoding Bar (Bottom) */}
                    <EncodingBar
                        columns={columns}
                        encoding={chartConfig.encoding}
                        onUpdateEncoding={updateEncoding}
                        onRefresh={generateChart}
                        colors={COLORS}
                    />
                </div>

                {/* Format Panel Toggle */}
                <button
                    onClick={() => setShowFormatPanel(!showFormatPanel)}
                    className="absolute right-0 top-1/2 -translate-y-1/2 z-10 p-1 rounded-l"
                    style={{ backgroundColor: COLORS.surface, border: `1px solid ${COLORS.border}` }}
                >
                    <Settings size={16} style={{ color: COLORS.textSecondary }} />
                </button>

                {/* Format Panel (Right Sidebar) */}
                <AnimatePresence>
                    {showFormatPanel && (
                        <motion.div
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: 280, opacity: 1 }}
                            exit={{ width: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="border-l overflow-hidden"
                            style={{ backgroundColor: COLORS.surface, borderColor: COLORS.border }}
                        >
                            <FormatPanel
                                format={chartConfig.format}
                                chartType={chartConfig.chartType}
                                chartTypes={CHART_TYPES}
                                onUpdateFormat={updateFormat}
                                onUpdateChartType={updateChartType}
                                colors={COLORS}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default ChartsStudio;
