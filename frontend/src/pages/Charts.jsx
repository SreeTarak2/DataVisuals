import React, { useState, useEffect } from 'react';
import {
  Database, Save, Download, Loader2, BarChart3, LineChart, PieChart,
  ScatterChart, AreaChart, Activity, BarChart2, TrendingUp
} from 'lucide-react';
import { motion } from 'framer-motion';
import PlotlyChart from '../components/PlotlyChart';
import { toast } from 'react-hot-toast';
import { cn } from '../lib/utils';
import useDatasetStore from '../store/datasetStore';
import { datasetAPI, chartAPI } from '../services/api';

// Chart type definitions - matches backend ChartType enum
// Backend supports: bar, line, pie, histogram, box_plot, scatter, heatmap, treemap, grouped_bar, area
const CHART_TYPES = [
  // Fully supported chart types
  { id: 'bar', label: 'Bar', icon: BarChart3, color: '#3b82f6', enabled: true },
  { id: 'line', label: 'Line', icon: TrendingUp, color: '#10b981', enabled: true },
  { id: 'pie', label: 'Pie', icon: PieChart, color: '#f59e0b', enabled: true },
  { id: 'scatter', label: 'Scatter', icon: ScatterChart, color: '#ef4444', enabled: true },
  { id: 'area', label: 'Area', icon: AreaChart, color: '#06b6d4', enabled: true },
  { id: 'histogram', label: 'Histogram', icon: BarChart2, color: '#ec4899', enabled: true },
  { id: 'box_plot', label: 'Box Plot', icon: BarChart2, color: '#14b8a6', enabled: true },
  { id: 'heatmap', label: 'Heatmap', icon: Activity, color: '#f97316', enabled: true },
  { id: 'treemap', label: 'Treemap', icon: BarChart2, color: '#84cc16', enabled: true },
  { id: 'grouped_bar', label: 'Grouped Bar', icon: BarChart3, color: '#8b5cf6', enabled: true },
];

const AGGREGATIONS = [
  { id: 'sum', label: 'Sum' },
  { id: 'avg', label: 'Average' },
  { id: 'count', label: 'Count' },
  { id: 'min', label: 'Min' },
  { id: 'max', label: 'Max' },
];

const Charts = () => {
  const { selectedDataset } = useDatasetStore();
  const [chartType, setChartType] = useState('bar');
  const [xAxis, setXAxis] = useState('');
  const [yAxis, setYAxis] = useState('');
  const [aggregation, setAggregation] = useState('sum');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [chartData, setChartData] = useState(null);
  const [columns, setColumns] = useState([]);
  const chartRef = React.useRef(null);

  // Get current chart's accent color
  const currentChartColor = CHART_TYPES.find(t => t.id === chartType)?.color || '#3b82f6';

  useEffect(() => {
    if (selectedDataset) {
      loadDatasetColumns();
    }
  }, [selectedDataset]);

  useEffect(() => {
    if (selectedDataset && xAxis && yAxis) {
      generateChartData();
    }
  }, [selectedDataset, xAxis, yAxis, aggregation, chartType]);

  const loadDatasetColumns = async () => {
    if (!selectedDataset) return;
    if (!selectedDataset.is_processed) {
      toast.error('Dataset is still processing...');
      return;
    }

    try {
      if (selectedDataset.metadata?.column_metadata) {
        const columnNames = selectedDataset.metadata.column_metadata.map(col => col.name);
        setColumns(columnNames);
        if (!xAxis && columnNames.length > 0) setXAxis(columnNames[0]);
        if (!yAxis && columnNames.length > 1) setYAxis(columnNames[1]);
        return;
      }

      const response = await datasetAPI.getDatasetData(selectedDataset.id, 1, 10);
      if (response.data?.data?.length > 0) {
        const columnNames = Object.keys(response.data.data[0]);
        setColumns(columnNames);
        if (!xAxis && columnNames.length > 0) setXAxis(columnNames[0]);
        if (!yAxis && columnNames.length > 1) setYAxis(columnNames[1]);
      }
    } catch (error) {
      console.error('Failed to load columns:', error);
      toast.error('Failed to load dataset columns');
    }
  };

  const generateChartData = async () => {
    if (!selectedDataset || !xAxis || !yAxis) return;

    setLoading(true);
    try {
      const response = await chartAPI.generateChart(
        selectedDataset.id,
        chartType,
        xAxis,
        yAxis,
        aggregation
      );

      if (response.data?.traces?.length > 0) {
        setChartData(response.data);
      } else {
        setChartData(null);
        toast.error('No data for selected columns. Try different options.');
      }
    } catch (error) {
      toast.error('Failed to generate chart');
      setChartData(null);
    } finally {
      setLoading(false);
    }
  };

  // Save chart to dashboard
  const handleSaveChart = async () => {
    if (!chartData || !selectedDataset) return;

    setSaving(true);
    try {
      const chartConfig = {
        chart_type: chartType,
        columns: [xAxis, yAxis],
        aggregation: aggregation,
        title: `${yAxis} by ${xAxis}`
      };

      await chartAPI.saveChart(
        selectedDataset.id,
        chartConfig,
        chartConfig.title
      );

      toast.success('Chart saved to dashboard!');
    } catch (error) {
      toast.error('Failed to save chart');
    } finally {
      setSaving(false);
    }
  };

  // Export chart as PNG
  const handleExportChart = async () => {
    if (!chartRef.current) {
      toast.error('Chart not ready for export');
      return;
    }

    try {
      // Find the Plotly chart div
      const plotlyDiv = chartRef.current.querySelector('.js-plotly-plot');
      if (plotlyDiv) {
        const Plotly = (await import('plotly.js-dist-min')).default;
        await Plotly.downloadImage(plotlyDiv, {
          format: 'png',
          filename: `chart_${chartType}_${xAxis}_${yAxis}`,
          width: 1920,
          height: 1080,
          scale: 2
        });
        toast.success('Chart exported as PNG!');
      } else {
        toast.error('Chart element not found');
      }
    } catch (error) {
      toast.error('Failed to export chart');
    }
  };

  // No dataset selected
  if (!selectedDataset) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0a0f]">
        <div className="text-center">
          <Database className="w-16 h-16 text-slate-600 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-slate-300 mb-2">No Dataset Selected</h2>
          <p className="text-slate-500 mb-6">Select a dataset from the Dashboard first.</p>
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={() => window.location.href = '/dashboard'}
            className="px-6 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-500 transition-colors"
          >
            Go to Dashboard
          </motion.button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 flex flex-col">
      {/* Compact Toolbar */}
      <div className="mb-4 space-y-3">
        {/* Header Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-white">Charts</h1>
            <span className="text-sm text-slate-500 bg-slate-800/50 px-2 py-1 rounded">
              {selectedDataset?.name}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={handleSaveChart}
              disabled={!chartData || saving}
              className="px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-all disabled:opacity-40"
              style={{ backgroundColor: currentChartColor }}
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? 'Saving...' : 'Save'}
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={handleExportChart}
              disabled={!chartData}
              className="px-4 py-2 rounded-lg bg-slate-700 text-white font-medium flex items-center gap-2 hover:bg-slate-600 transition-all disabled:opacity-40"
            >
              <Download className="w-4 h-4" />
              Export
            </motion.button>
          </div>
        </div>

        {/* Controls Row */}
        <div className="flex flex-col gap-3 p-3 bg-slate-900/50 rounded-xl border border-slate-800">
          {/* Chart Type Selector - Horizontal Scrollable */}
          <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {CHART_TYPES.map((type) => {
              const Icon = type.icon;
              const isActive = chartType === type.id;
              const isEnabled = type.enabled !== false;
              return (
                <motion.button
                  key={type.id}
                  whileHover={{ scale: isEnabled ? 1.05 : 1 }}
                  whileTap={{ scale: isEnabled ? 0.95 : 1 }}
                  onClick={() => isEnabled && setChartType(type.id)}
                  disabled={!isEnabled}
                  title={isEnabled ? type.label : `${type.label} - Coming Soon`}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap flex-shrink-0',
                    isEnabled
                      ? isActive
                        ? 'text-white shadow-lg'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800'
                      : 'text-slate-600 cursor-not-allowed opacity-50'
                  )}
                  style={isActive && isEnabled ? { backgroundColor: type.color } : {}}
                >
                  <Icon className="w-4 h-4" />
                  <span>{type.label}</span>
                </motion.button>
              );
            })}
          </div>

          {/* Data Mapping - Inline */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-500 uppercase">X</label>
              <select
                value={xAxis}
                onChange={(e) => setXAxis(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select...</option>
                {columns.map(col => <option key={col} value={col}>{col}</option>)}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-500 uppercase">Y</label>
              <select
                value={yAxis}
                onChange={(e) => setYAxis(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select...</option>
                {columns.map(col => <option key={col} value={col}>{col}</option>)}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-500 uppercase">Agg</label>
              <select
                value={aggregation}
                onChange={(e) => setAggregation(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {AGGREGATIONS.map(agg => <option key={agg.id} value={agg.id}>{agg.label}</option>)}
              </select>
            </div>
          </div>
        </div>

        {/* Full-Width Chart Area */}
        <div className="flex-1 bg-[#0d1117] rounded-xl border border-slate-800/50 p-6" style={{ minHeight: 'calc(100vh - 200px)' }}>
          {loading ? (
            <div className="h-full flex items-center justify-center" style={{ minHeight: '500px' }}>
              <Loader2 className="w-10 h-10 animate-spin" style={{ color: currentChartColor }} />
            </div>
          ) : !xAxis || !yAxis ? (
            <div className="h-full flex items-center justify-center text-slate-500" style={{ minHeight: '500px' }}>
              Select X and Y axes to create a visualization
            </div>
          ) : !chartData ? (
            <div className="h-full flex items-center justify-center" style={{ minHeight: '500px' }}>
              <div className="text-center text-slate-500">
                <p className="mb-2">No data available for this configuration.</p>
                <p className="text-sm">Try selecting a numeric column for Y-axis or use "Count" aggregation.</p>
              </div>
            </div>
          ) : (
            <div ref={chartRef} style={{ width: '100%', height: 'calc(100vh - 250px)', minHeight: '500px' }}>
              <PlotlyChart
                data={chartData.traces.map(trace => ({
                  ...trace,
                  marker: {
                    ...trace.marker,
                    color: currentChartColor,
                  },
                  line: {
                    ...trace.line,
                    color: currentChartColor,
                    width: 3,
                  },
                }))}
                layout={{
                  ...chartData.layout,
                  autosize: true,
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  font: { color: '#e2e8f0', family: 'Inter, system-ui, sans-serif' },
                  title: {
                    text: `${yAxis} by ${xAxis}`,
                    font: { size: 18, color: '#f1f5f9' },
                    x: 0.5,
                    xanchor: 'center'
                  },
                  xaxis: {
                    title: { text: xAxis, font: { color: '#94a3b8', size: 12 } },
                    showgrid: false,
                    zeroline: false,
                    tickfont: { color: '#64748b', size: 10 },
                    linecolor: '#334155',
                    tickangle: -45
                  },
                  yaxis: {
                    title: { text: yAxis, font: { color: '#94a3b8', size: 12 } },
                    showgrid: false,
                    zeroline: false,
                    tickfont: { color: '#64748b', size: 10 },
                    linecolor: '#334155'
                  },
                  margin: { l: 70, r: 40, t: 60, b: 100 },
                  showlegend: false,
                  hovermode: 'x unified',
                  hoverlabel: {
                    bgcolor: '#1e293b',
                    bordercolor: '#334155',
                    font: { color: '#f1f5f9' }
                  }
                }}
                config={{
                  displayModeBar: false,
                  responsive: true
                }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Charts;