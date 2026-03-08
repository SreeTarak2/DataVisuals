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
    aggregation: 'sum',
  });

  const chartTypes = [
    { id: 'bar', name: 'Bar Chart', icon: BarChart3, requiresY: true },
    { id: 'line', name: 'Line Chart', icon: LineChart, requiresY: true },
    { id: 'pie', name: 'Pie Chart', icon: PieChart, requiresY: true },
    { id: 'scatter', name: 'Scatter Plot', icon: ChartScatter, requiresY: true },
    { id: 'area', name: 'Area Chart', icon: AreaChart, requiresY: true },
  ];

  const aggregationTypes = [
    { id: 'sum', name: 'Sum', description: 'Add all values' },
    { id: 'mean', name: 'Average', description: 'Calculate mean' },
    { id: 'count', name: 'Count', description: 'Count occurrences' },
    { id: 'max', name: 'Maximum', description: 'Find highest value' },
    { id: 'min', name: 'Minimum', description: 'Find lowest value' },
    { id: 'raw', name: 'Raw Data', description: 'No aggregation' },
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
          datasetInfo: response.data.dataset_info,
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
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#0a0e14] border border-white/[0.06] rounded-xl p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-slate-200">Configure Chart</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-500 hover:text-slate-300 hover:bg-white/[0.04] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-6">
          {/* Chart Type Selection */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-3">
              Chart Type
            </label>
            <div className="grid grid-cols-2 gap-2">
              {chartTypes.map((chartType) => {
                const Icon = chartType.icon;
                return (
                  <button
                    key={chartType.id}
                    onClick={() => setChartConfig(prev => ({ ...prev, chartType: chartType.id }))}
                    className={`p-3.5 rounded-lg border transition-all ${
                      chartConfig.chartType === chartType.id
                        ? 'border-white/[0.15] bg-white/[0.06]'
                        : 'border-white/[0.06] hover:border-white/[0.10] bg-white/[0.02]'
                    }`}
                  >
                    <Icon className="w-5 h-5 text-slate-400 mb-1.5" />
                    <div className="text-[12px] font-medium text-slate-300">
                      {chartType.name}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* X-Axis Selection */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
              X-Axis (Category)
            </label>
            <select
              value={chartConfig.xAxis}
              onChange={(e) => setChartConfig(prev => ({ ...prev, xAxis: e.target.value }))}
              className="w-full p-2.5 bg-white/[0.04] border border-white/[0.06] rounded-lg text-[12px] text-slate-300 outline-none focus:border-white/[0.15] transition-colors"
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
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
                Y-Axis (Value)
              </label>
              <select
                value={chartConfig.yAxis}
                onChange={(e) => setChartConfig(prev => ({ ...prev, yAxis: e.target.value }))}
                className="w-full p-2.5 bg-white/[0.04] border border-white/[0.06] rounded-lg text-[12px] text-slate-300 outline-none focus:border-white/[0.15] transition-colors"
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
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-3">
              Aggregation
            </label>
            <div className="grid grid-cols-2 gap-2">
              {aggregationTypes.map((agg) => (
                <button
                  key={agg.id}
                  onClick={() => setChartConfig(prev => ({ ...prev, aggregation: agg.id }))}
                  className={`p-3 rounded-lg border transition-all text-left ${
                    chartConfig.aggregation === agg.id
                      ? 'border-white/[0.15] bg-white/[0.06]'
                      : 'border-white/[0.06] hover:border-white/[0.10] bg-white/[0.02]'
                  }`}
                >
                  <div className="text-[12px] font-medium text-slate-300">{agg.name}</div>
                  <div className="text-[10px] text-slate-600">{agg.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-3 pt-4 border-t border-white/[0.06]">
            <button
              onClick={onClose}
              className="px-4 py-2 text-[12px] text-slate-500 hover:text-slate-300 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleGenerateChart}
              disabled={loading || !chartConfig.xAxis || (selectedChartType?.requiresY && !chartConfig.yAxis)}
              className="px-5 py-2 bg-white text-[#020203] disabled:bg-white/10 disabled:text-slate-600 disabled:cursor-not-allowed rounded-md text-[12px] font-medium hover:bg-slate-200 transition-colors"
            >
              {loading ? 'Generating…' : 'Generate Chart'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChartConfigModal;

