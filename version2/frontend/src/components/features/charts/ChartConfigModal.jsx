import React, { useState, useEffect } from 'react';
import { X, BarChart3, LineChart, PieChart, ChartScatter, AreaChart } from 'lucide-react';
import { datasetAPI, chartAPI } from '../services/api';

const ChartConfigModal = ({ isOpen, onClose, datasetId, onChartGenerated }) => {
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [chartConfig, setChartConfig] = useState({
    chartType: 'bar',
    xAxis: '',
    yAxis: '',
    aggregation: 'sum'
  });

  const chartTypes = [
    { id: 'bar', name: 'Bar Chart', icon: BarChart3, requiresY: true },
    { id: 'line', name: 'Line Chart', icon: LineChart, requiresY: true },
    { id: 'pie', name: 'Pie Chart', icon: PieChart, requiresY: true },
    { id: 'scatter', name: 'Scatter Plot', icon: ChartScatter, requiresY: true },
    { id: 'area', name: 'Area Chart', icon: AreaChart, requiresY: true }
  ];

  const aggregationTypes = [
    { id: 'sum', name: 'Sum', description: 'Add all values' },
    { id: 'mean', name: 'Average', description: 'Calculate mean' },
    { id: 'count', name: 'Count', description: 'Count occurrences' },
    { id: 'max', name: 'Maximum', description: 'Find highest value' },
    { id: 'min', name: 'Minimum', description: 'Find lowest value' },
    { id: 'raw', name: 'Raw Data', description: 'No aggregation' }
  ];

  useEffect(() => {
    if (isOpen && datasetId) {
      loadColumns();
    }
  }, [isOpen, datasetId]);

  const loadColumns = async () => {
    try {
      setLoading(true);
      const response = await datasetAPI.getDatasetColumns(datasetId);
      if (response.data.success) {
        setColumns(response.data.columns);
      }
    } catch (error) {
      console.error('Failed to load columns:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateChart = async () => {
    try {
      setLoading(true);
      const response = await chartAPI.generateChart(
        datasetId,
        chartConfig.chartType,
        chartConfig.xAxis,
        chartConfig.yAxis,
        chartConfig.aggregation
      );

      if (response.data) {
        onChartGenerated({
          chartData: response.data.chart_data,
          chartType: response.data.chart_type,
          xAxis: response.data.x_axis,
          yAxis: response.data.y_axis,
          aggregation: response.data.aggregation,
          datasetInfo: response.data.dataset_info
        });
        onClose();
      }
    } catch (error) {
      console.error('Failed to generate chart:', error);
    } finally {
      setLoading(false);
    }
  };

  const selectedChartType = chartTypes.find(ct => ct.id === chartConfig.chartType);
  const numericColumns = columns.filter(col => col.is_numeric);
  const categoricalColumns = columns.filter(col => col.is_categorical);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-slate-900 rounded-2xl p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white">Configure Chart</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="space-y-6">
          {/* Chart Type Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">
              Chart Type
            </label>
            <div className="grid grid-cols-2 gap-3">
              {chartTypes.map((chartType) => {
                const Icon = chartType.icon;
                return (
                  <button
                    key={chartType.id}
                    onClick={() => setChartConfig(prev => ({ ...prev, chartType: chartType.id }))}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      chartConfig.chartType === chartType.id
                        ? 'border-blue-500 bg-blue-500/10'
                        : 'border-slate-700 hover:border-slate-600'
                    }`}
                  >
                    <Icon className="w-6 h-6 text-slate-300 mb-2" />
                    <div className="text-sm font-medium text-slate-300">
                      {chartType.name}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* X-Axis Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">
              X-Axis (Category)
            </label>
            <select
              value={chartConfig.xAxis}
              onChange={(e) => setChartConfig(prev => ({ ...prev, xAxis: e.target.value }))}
              className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Select X-axis column</option>
              {categoricalColumns.map((column) => (
                <option key={column.name} value={column.name}>
                  {column.name} ({column.type})
                </option>
              ))}
            </select>
          </div>

          {/* Y-Axis Selection */}
          {selectedChartType?.requiresY && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-3">
                Y-Axis (Value)
              </label>
              <select
                value={chartConfig.yAxis}
                onChange={(e) => setChartConfig(prev => ({ ...prev, yAxis: e.target.value }))}
                className="w-full p-3 bg-slate-800 border border-slate-700 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select Y-axis column</option>
                {numericColumns.map((column) => (
                  <option key={column.name} value={column.name}>
                    {column.name} ({column.type})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Aggregation Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">
              Aggregation
            </label>
            <div className="grid grid-cols-2 gap-3">
              {aggregationTypes.map((agg) => (
                <button
                  key={agg.id}
                  onClick={() => setChartConfig(prev => ({ ...prev, aggregation: agg.id }))}
                  className={`p-3 rounded-lg border-2 transition-all text-left ${
                    chartConfig.aggregation === agg.id
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="font-medium text-slate-300">{agg.name}</div>
                  <div className="text-xs text-slate-400">{agg.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end space-x-3 pt-4">
            <button
              onClick={onClose}
              className="px-6 py-2 text-slate-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleGenerateChart}
              disabled={loading || !chartConfig.xAxis || (selectedChartType?.requiresY && !chartConfig.yAxis)}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              {loading ? 'Generating...' : 'Generate Chart'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChartConfigModal;

