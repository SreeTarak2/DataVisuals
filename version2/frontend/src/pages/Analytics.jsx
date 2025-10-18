import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ScatterChart, Scatter, AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis
} from 'recharts';
import { 
  BarChart3, TrendingUp, PieChart as PieIcon, ChartScatter, 
  AreaChart as AreaChartIcon, Radar as RadarIcon, Database, Save, Download, Settings, Loader2 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import GlassCard from '../components/common/GlassCard';
import { toast } from 'react-hot-toast';
import { cn } from '../lib/utils';
import useDatasetStore from '../store/datasetStore';
import { datasetAPI } from '../services/api';

const Analytics = () => {
  const { datasets, selectedDataset, setSelectedDataset, fetchDatasets } = useDatasetStore();
  const [chartType, setChartType] = useState('bar');
  const [xAxis, setXAxis] = useState('');
  const [yAxis, setYAxis] = useState('');
  const [aggregation, setAggregation] = useState('sum');
  const [loading, setLoading] = useState(true);
  const [chartData, setChartData] = useState([]);
  const [columns, setColumns] = useState([]);

  // All chart types with icons
  const chartTypes = [
    { id: 'bar', icon: BarChart3, label: 'Bar Chart' },
    { id: 'line', icon: TrendingUp, label: 'Line Chart' },
    { id: 'pie', icon: PieIcon, label: 'Pie Chart' },
    { id: 'scatter', icon: ChartScatter, label: 'Scatter Plot' },
    { id: 'area', icon: AreaChartIcon, label: 'Area Chart' },
    { id: 'radar', icon: RadarIcon, label: 'Radar Chart' },
  ];

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        await fetchDatasets();
        if (datasets.length > 0 && !selectedDataset) {
        setSelectedDataset(datasets[0]);
        }
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [fetchDatasets, datasets.length, selectedDataset, setSelectedDataset]);

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
    
    try {
      setLoading(true);
      // Get dataset data to extract columns
      const response = await datasetAPI.getDatasetData(selectedDataset.id, 1, 10);
      if (response.data && response.data.length > 0) {
        const sampleRow = response.data[0];
        const columnNames = Object.keys(sampleRow);
        setColumns(columnNames);
      }
    } catch (error) {
      console.error('Failed to load columns:', error);
      toast.error('Failed to load dataset columns');
    } finally {
      setLoading(false);
    }
  };

  const generateChartData = async () => {
    if (!selectedDataset || !xAxis || !yAxis) return;
    
    setLoading(true);
    try {
      // Call the new analytics API endpoint
      const response = await fetch('/api/analytics/generate-chart', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          dataset_id: selectedDataset.id,
          chart_type: chartType,
          x_axis: xAxis,
          y_axis: yAxis,
          aggregation: aggregation
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        setChartData(result.chart_data);
        toast.success('Chart data generated successfully');
      } else {
        throw new Error('Failed to generate chart data');
      }
    } catch (error) {
      console.error('Failed to generate chart data:', error);
      toast.error('Failed to generate chart data');
    } finally {
      setLoading(false);
    }
  };

  const renderChart = () => {
    if (loading) return (
        <div className="h-[600px] flex items-center justify-center">
        <Loader2 className="animate-spin w-8 h-8 text-primary" />
        </div>
      );
    
    if (!xAxis || !yAxis) return (
      <div className="h-[600px] flex items-center justify-center text-muted-foreground">
        Select X and Y axes to visualize
      </div>
    );

    const xKey = xAxis;
    const yKey = yAxis;

    switch (chartType) {
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={700}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.2)" />
              <XAxis dataKey={xKey} stroke="hsl(var(--muted-foreground))" />
              <YAxis stroke="hsl(var(--muted-foreground))" />
              <Tooltip />
              <Legend />
              <Bar dataKey={yKey} fill="hsl(var(--primary))" />
            </BarChart>
          </ResponsiveContainer>
        );
      case 'line':
        return (
          <ResponsiveContainer width="100%" height={700}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.2)" />
              <XAxis dataKey={xKey} stroke="hsl(var(--muted-foreground))" />
              <YAxis stroke="hsl(var(--muted-foreground))" />
              <Tooltip />
              <Line type="monotone" dataKey={yKey} stroke="hsl(var(--primary))" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        );
      case 'pie':
        return (
          <ResponsiveContainer width="100%" height={700}>
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value" 
                nameKey="name" 
                cx="50%"
                cy="50%"
                outerRadius={120}
                fill="#8884d8"
                label
              >
                {chartData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={['hsl(var(--primary))', 'hsl(var(--secondary))', 'hsl(var(--success))', 'hsl(var(--destructive))'][index % 4]} 
                  />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        );
      case 'scatter':
        return (
          <ResponsiveContainer width="100%" height={700}>
            <ScatterChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.2)" />
              <XAxis type="number" dataKey="x" stroke="hsl(var(--muted-foreground))" />
              <YAxis type="number" dataKey="y" stroke="hsl(var(--muted-foreground))" />
              <Tooltip />
              <Scatter dataKey="y" fill="hsl(var(--primary))" />
            </ScatterChart>
          </ResponsiveContainer>
        );
      case 'area':
        return (
          <ResponsiveContainer width="100%" height={700}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.2)" />
              <XAxis dataKey={xKey} stroke="hsl(var(--muted-foreground))" />
              <YAxis stroke="hsl(var(--muted-foreground))" />
              <Tooltip />
              <Area type="monotone" dataKey={yKey} stroke="hsl(var(--primary))" fill="hsl(var(--primary))/0.3" />
            </AreaChart>
          </ResponsiveContainer>
        );
      case 'radar':
        return (
          <ResponsiveContainer width="100%" height={700}>
            <RadarChart data={chartData}>
              <PolarGrid stroke="hsl(var(--border)/0.2)" />
              <PolarAngleAxis dataKey={xKey} stroke="hsl(var(--muted-foreground))" />
              <Radar dataKey={yKey} stroke="hsl(var(--primary))" fill="hsl(var(--primary))/0.3" />
              <Tooltip />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        );
      default:
        return null;
    }
  };

  if (loading && !selectedDataset) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="animate-spin w-8 h-8 text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Analytics Studio</h1>
          <p className="text-muted-foreground mt-2">Build visualizations like in Power BI—select data and create charts.</p>
        </div>
        
        {/* Action Buttons - Top Right */}
        <div className="flex items-center gap-2">
          <motion.button
            whileTap={{ scale: 0.95 }}
            whileHover={{ scale: 1.02 }}
            onClick={() => toast('Chart saved!')}
            className="px-3 py-2 rounded-xl bg-white/5 border border-white/20 text-foreground hover:bg-white/10 hover:border-white/30 focus-visible-ring transition-all duration-200 flex items-center gap-2 text-sm font-medium backdrop-blur-md shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!xAxis || !yAxis}
          >
            <Save className="w-4 h-4" />
            Save
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.95 }}
            whileHover={{ scale: 1.02 }}
            onClick={() => toast('Exported to PNG')}
            className="px-3 py-2 rounded-xl bg-white/5 border border-white/20 text-foreground hover:bg-white/10 hover:border-white/30 focus-visible-ring transition-all duration-200 flex items-center gap-2 text-sm font-medium backdrop-blur-md shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!xAxis || !yAxis}
          >
            <Download className="w-4 h-4" />
            Export
          </motion.button>
        </div>
      </div>

      {/* Main Layout - Left Chart, Right Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Preview - Takes 2/3 of the space */}
        <div className="lg:col-span-2">
          <GlassCard className="p-6" elevated>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-foreground">Chart Preview</h2>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Database className="w-4 h-4" />
                <span>{selectedDataset?.name || 'No Dataset'}</span>
              </div>
            </div>
            {renderChart()}
          </GlassCard>
        </div>

        {/* Controls Panel - Takes 1/3 of the space */}
        <div className="space-y-4">
      {/* Dataset Selector */}
          <GlassCard className="p-4" elevated>
            <h3 className="text-lg font-semibold text-foreground mb-3">Dataset</h3>
            <select
              value={selectedDataset?.id || ''}
              onChange={(e) => setSelectedDataset(datasets.find(d => d.id === e.target.value))}
              className="w-full px-3 py-2 rounded-lg glass-effect border border-border/50 text-foreground focus:ring-primary"
            >
              <option value="">Select dataset...</option>
              {datasets.map(d => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
        </GlassCard>

      {/* Chart Type Selector */}
          <GlassCard className="p-4" elevated>
            <h3 className="text-lg font-semibold text-foreground mb-3">Chart Type</h3>
            <div className="grid grid-cols-2 gap-2">
              {chartTypes.map(type => (
                <motion.button
            key={type.id}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setChartType(type.id)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-sm',
                    chartType === type.id 
                      ? 'bg-primary text-primary-foreground' 
                      : 'bg-accent text-foreground hover:bg-primary/10'
                  )}
                >
                  <type.icon className="w-4 h-4" />
                  {type.label}
                </motion.button>
        ))}
      </div>
      </GlassCard>

          {/* Axis Configuration */}
          <GlassCard className="p-4" elevated>
            <h3 className="text-lg font-semibold text-foreground mb-3">Data Mapping</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-1">X Axis</label>
                <select
                  value={xAxis}
                  onChange={(e) => setXAxis(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg glass-effect border border-border/50 text-foreground focus:ring-primary"
                  disabled={!selectedDataset}
                >
                  <option value="">Choose X column...</option>
                  {columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
            </div>

              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-1">Y Axis</label>
                <select
                  value={yAxis}
                  onChange={(e) => setYAxis(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg glass-effect border border-border/50 text-foreground focus:ring-primary"
                  disabled={!selectedDataset}
                >
                  <option value="">Choose Y column...</option>
                  {columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
          </div>

              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-1">Aggregation</label>
                <select
                  value={aggregation}
                  onChange={(e) => setAggregation(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg glass-effect border border-border/50 text-foreground focus:ring-primary"
                >
                  <option value="sum">Sum</option>
                  <option value="avg">Average</option>
                  <option value="count">Count</option>
                  <option value="min">Minimum</option>
                  <option value="max">Maximum</option>
                </select>
              </div>
            </div>
        </GlassCard>

          </div>
      </div>
    </div>
  );
};

export default Analytics;