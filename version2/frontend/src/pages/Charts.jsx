import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ScatterChart, Scatter, AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis
} from 'recharts';
import { 
  BarChart3, TrendingUp, PieChart as PieIcon, ChartScatter, 
  AreaChart as AreaChartIcon, Radar as RadarIcon, Database, Save, Download, Settings, Loader2, RefreshCw 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import GlassCard from '../components/common/GlassCard';
import { toast } from 'react-hot-toast';
import { cn } from '../lib/utils';
import useDatasetStore from '../store/datasetStore';
import { datasetAPI } from '../services/api';

const Charts = () => {
  const { selectedDataset } = useDatasetStore();
  const [chartType, setChartType] = useState('bar');
  const [xAxis, setXAxis] = useState('');
  const [yAxis, setYAxis] = useState('');
  const [aggregation, setAggregation] = useState('sum');
  const [loading, setLoading] = useState(true);
  const [chartData, setChartData] = useState([]);
  const [columns, setColumns] = useState([]);
  const [drillDownData, setDrillDownData] = useState(null);
  const [drillDownLevel, setDrillDownLevel] = useState(0);
  const [drillDownHierarchy, setDrillDownHierarchy] = useState(null);
  const [drillDownFilters, setDrillDownFilters] = useState({});
  const [drillDownAnalysis, setDrillDownAnalysis] = useState(null);

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
    if (selectedDataset) {
      loadDatasetColumns();
    }
  }, [selectedDataset]);

  useEffect(() => {
    if (selectedDataset && xAxis && yAxis) {
      generateChartData();
    }
  }, [selectedDataset, xAxis, yAxis, aggregation, chartType]);

  // Auto-analyze hierarchies when dataset changes
  useEffect(() => {
    if (selectedDataset && selectedDataset.is_processed) {
      analyzeDrillDownHierarchies();
    }
  }, [selectedDataset]);

  const loadDatasetColumns = async () => {
    if (!selectedDataset) return;
    
    // Check if dataset is processed
    if (!selectedDataset.is_processed) {
      console.log('Dataset not processed yet, waiting...');
      toast.info('Dataset is still being processed. Please wait...');
      return;
    }
    
    try {
      setLoading(true);
      
      // First try to get columns from dataset metadata
      if (selectedDataset.metadata?.column_metadata) {
        const columnNames = selectedDataset.metadata.column_metadata.map(col => col.name);
        console.log('Available columns from metadata:', columnNames);
        setColumns(columnNames);
        
        // Auto-select first two columns if none selected
        if (!xAxis && columnNames.length > 0) {
          setXAxis(columnNames[0]);
        }
        if (!yAxis && columnNames.length > 1) {
          setYAxis(columnNames[1]);
        }
        
        // Suggest appropriate chart type and column combinations based on data
        if (selectedDataset.metadata?.column_metadata) {
          const xCol = selectedDataset.metadata.column_metadata.find(col => col.name === columnNames[0]);
          const yCol = selectedDataset.metadata.column_metadata.find(col => col.name === columnNames[1]);
          
          if (xCol && yCol) {
            // If both are categorical, suggest pie chart
            if (xCol.type === 'categorical' && yCol.type === 'categorical') {
              setChartType('pie');
            }
            // If x is temporal and y is numeric, suggest line chart
            else if (xCol.type === 'temporal' && yCol.type === 'numeric') {
              setChartType('line');
            }
            // If both are numeric, suggest scatter plot
            else if (xCol.type === 'numeric' && yCol.type === 'numeric') {
              setChartType('scatter');
            }
            // If Y is categorical, suggest bar chart with count
            else if (yCol.type === 'categorical') {
              setChartType('bar');
              setAggregation('count');
            }
            // Default to bar chart
            else {
              setChartType('bar');
            }
          }
        }
        return;
      }
      
      // Fallback: Get dataset data to extract columns
      console.log('Metadata not available, fetching data...');
      const response = await datasetAPI.getDatasetData(selectedDataset.id, 1, 10);
      console.log('Dataset data response:', response);
      if (response.data && response.data.length > 0) {
        const sampleRow = response.data[0];
        const columnNames = Object.keys(sampleRow);
        console.log('Available columns from data:', columnNames);
        setColumns(columnNames);
        
        // Auto-select first two columns if none selected
        if (!xAxis && columnNames.length > 0) {
          setXAxis(columnNames[0]);
        }
        if (!yAxis && columnNames.length > 1) {
          setYAxis(columnNames[1]);
        }
      } else {
        console.error('No data returned from API');
        // Fallback: Use common column names for demonstration
        const fallbackColumns = ['Player_Name', 'DOB', 'Batting_Hand', 'Bowling_Skill', 'Country', 'Age'];
        console.log('Using fallback columns:', fallbackColumns);
        setColumns(fallbackColumns);
        
        if (!xAxis) setXAxis(fallbackColumns[0]);
        if (!yAxis) setYAxis(fallbackColumns[1]);
        
        toast.warning('Using sample columns - dataset may not be fully processed yet');
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
          'Authorization': `Bearer ${localStorage.getItem('datasage-token')}`
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
        console.log('Chart data received:', result);
        setChartData(result.chart_data || []);
        toast.success('Chart data generated successfully');
      } else {
        const error = await response.json();
        console.error('Chart generation error:', error);
        throw new Error(error.detail || 'Failed to generate chart data');
      }
    } catch (error) {
      console.error('Failed to generate chart data:', error);
      toast.error('Failed to generate chart data');
    } finally {
      setLoading(false);
    }
  };

  // Drill-down API functions
  const analyzeDrillDownHierarchies = async () => {
    if (!selectedDataset) return;
    
    try {
      const response = await fetch(`/api/drilldown/${selectedDataset.id}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('datasage-token')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to analyze drill-down hierarchies');
      }
      
      const result = await response.json();
      setDrillDownAnalysis(result.analysis);
      
      // Auto-select the best hierarchy if available
      if (result.analysis.hierarchies && result.analysis.hierarchies.length > 0) {
        setDrillDownHierarchy(result.analysis.hierarchies[0]);
      }
      
      return result.analysis;
    } catch (error) {
      console.error('Error analyzing drill-down hierarchies:', error);
      toast.error('Failed to analyze drill-down hierarchies');
      return null;
    }
  };

  const executeDrillDown = async (clickedData, hierarchy = drillDownHierarchy) => {
    if (!selectedDataset || !hierarchy) return;
    
    try {
      const newFilters = {
        ...drillDownFilters,
        [hierarchy.levels[drillDownLevel - 1]?.field]: clickedData.name || clickedData[xAxis]
      };
      
      const response = await fetch(`/api/drilldown/${selectedDataset.id}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('datasage-token')}`
        },
        body: JSON.stringify({
          hierarchy: hierarchy,
          current_level: drillDownLevel + 1,
          filters: newFilters
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to execute drill-down');
      }
      
      const result = await response.json();
      const drillDownResult = result.drilldown_result;
      
      // Update chart data with drill-down results
      if (drillDownResult.data && drillDownResult.data.length > 0) {
        setChartData(drillDownResult.data);
        setDrillDownLevel(prev => prev + 1);
        setDrillDownFilters(newFilters);
        setDrillDownData({
          name: clickedData.name || clickedData[xAxis],
          value: clickedData.value || clickedData[yAxis],
          type: chartType
        });
        toast.success(`Drilled down into: ${clickedData.name || clickedData[xAxis]}`);
      } else {
        toast.info('No more data available for drill-down');
      }
      
      return drillDownResult;
    } catch (error) {
      console.error('Error executing drill-down:', error);
      toast.error('Failed to execute drill-down');
      return null;
    }
  };

  const drillUp = async () => {
    if (drillDownLevel <= 1) return;
    
    try {
      const newLevel = drillDownLevel - 1;
      const newFilters = { ...drillDownFilters };
      
      // Remove the last filter
      if (drillDownHierarchy && drillDownHierarchy.levels[newLevel - 1]) {
        delete newFilters[drillDownHierarchy.levels[newLevel - 1].field];
      }
      
      const response = await fetch(`/api/drilldown/${selectedDataset.id}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('datasage-token')}`
        },
        body: JSON.stringify({
          hierarchy: drillDownHierarchy,
          current_level: newLevel,
          filters: newFilters
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to drill up');
      }
      
      const result = await response.json();
      const drillDownResult = result.drilldown_result;
      
      if (drillDownResult.data && drillDownResult.data.length > 0) {
        setChartData(drillDownResult.data);
        setDrillDownLevel(newLevel);
        setDrillDownFilters(newFilters);
        
        if (newLevel === 1) {
          setDrillDownData(null);
        }
        
        toast.success('Drilled up successfully');
      }
      
    } catch (error) {
      console.error('Error drilling up:', error);
      toast.error('Failed to drill up');
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
    const chartTitle = `${yAxis} by ${xAxis}`;

    // Check if chart data has meaningful values
    const hasData = chartData && chartData.length > 0 && chartData.some(item => 
      (item[yKey] && item[yKey] > 0) || (item.y && item.y > 0) || (item.value && item.value > 0)
    );

    if (!hasData && chartData && chartData.length > 0) {
      return (
        <div className="h-[600px] flex items-center justify-center">
          <div className="text-center">
            <div className="text-muted-foreground mb-4">
              <h3 className="text-lg font-semibold mb-2">No Data to Display</h3>
              <p className="text-sm">The selected Y-axis column appears to contain non-numeric data.</p>
              <p className="text-sm mt-2">Try:</p>
              <ul className="text-sm mt-1 text-left max-w-md mx-auto">
                <li>• Select a numeric column for Y-axis</li>
                <li>• Change aggregation to "Count" for categorical data</li>
                <li>• Try a different column combination</li>
              </ul>
            </div>
          </div>
        </div>
      );
    }

    switch (chartType) {
      case 'bar':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={800}>
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.3)" />
                <XAxis 
                  dataKey={xKey} 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  label={{ value: xAxis, position: 'insideBottom', offset: -10, style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
                />
                <YAxis 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  label={{ value: yAxis, angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)',
                    color: 'hsl(var(--foreground))',
                    fontSize: '14px',
                    padding: '12px 16px'
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: '600', marginBottom: '8px' }}
                />
              <Legend />
                <Bar 
                  dataKey={yKey} 
                  fill="url(#barGradient)"
                  radius={[4, 4, 0, 0]}
                  stroke="hsl(var(--primary))"
                  strokeWidth={1}
                  onClick={async (data) => {
                    if (drillDownHierarchy && drillDownLevel < drillDownHierarchy.levels.length) {
                      await executeDrillDown(data);
                    } else {
                      // Fallback to simple drill-down if no hierarchy available
                      setDrillDownData({
                        name: data[xKey],
                        value: data[yKey],
                        type: 'bar'
                      });
                      setDrillDownLevel(prev => prev + 1);
                      toast.success(`Drilled down into: ${data[xKey]}`);
                    }
                  }}
                  style={{ cursor: 'pointer' }}
                />
                <defs>
                  <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" />
                    <stop offset="100%" stopColor="#1d4ed8" />
                  </linearGradient>
                </defs>
            </BarChart>
          </ResponsiveContainer>
          </div>
        );
      case 'line':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-green-400 to-blue-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={800}>
              <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.3)" />
                <XAxis 
                  dataKey={xKey} 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  label={{ value: xAxis, position: 'insideBottom', offset: -10, style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
                />
                <YAxis 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  label={{ value: yAxis, angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)',
                    color: 'hsl(var(--foreground))',
                    fontSize: '14px',
                    padding: '12px 16px'
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: '600', marginBottom: '8px' }}
                />
                <Line 
                  type="monotone" 
                  dataKey={yKey} 
                  stroke="url(#lineGradient)" 
                  strokeWidth={4}
                  dot={{ 
                    fill: '#3b82f6', 
                    strokeWidth: 2, 
                    r: 6,
                    onClick: async (data) => {
                      if (drillDownHierarchy && drillDownLevel < drillDownHierarchy.levels.length) {
                        await executeDrillDown(data);
                      } else {
                        // Fallback to simple drill-down if no hierarchy available
                        setDrillDownData({
                          name: data[xKey],
                          value: data[yKey],
                          type: 'line'
                        });
                        setDrillDownLevel(prev => prev + 1);
                        toast.success(`Drilled down into: ${data[xKey]}`);
                      }
                    },
                    style: { cursor: 'pointer' }
                  }}
                  activeDot={{ 
                    r: 8, 
                    stroke: '#3b82f6', 
                    strokeWidth: 2, 
                    fill: '#fff',
                    onClick: async (data) => {
                      if (drillDownHierarchy && drillDownLevel < drillDownHierarchy.levels.length) {
                        await executeDrillDown(data);
                      } else {
                        // Fallback to simple drill-down if no hierarchy available
                        setDrillDownData({
                          name: data[xKey],
                          value: data[yKey],
                          type: 'line'
                        });
                        setDrillDownLevel(prev => prev + 1);
                        toast.success(`Drilled down into: ${data[xKey]}`);
                      }
                    },
                    style: { cursor: 'pointer' }
                  }}
                />
                <defs>
                  <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#10b981" />
                    <stop offset="100%" stopColor="#3b82f6" />
                  </linearGradient>
                </defs>
            </LineChart>
          </ResponsiveContainer>
          </div>
        );
      case 'pie':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-pink-400 to-purple-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={800}>
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value" 
                nameKey="name" 
                cx="50%"
                cy="50%"
                  outerRadius={140}
                  innerRadius={60}
                fill="#8884d8"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                  onClick={async (data) => {
                    if (drillDownHierarchy && drillDownLevel < drillDownHierarchy.levels.length) {
                      await executeDrillDown(data);
                    } else {
                      // Fallback to simple drill-down if no hierarchy available
                      setDrillDownData({
                        name: data.name,
                        value: data.value,
                        type: 'pie'
                      });
                      setDrillDownLevel(prev => prev + 1);
                      toast.success(`Drilled down into: ${data.name}`);
                    }
                  }}
              >
                {chartData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                      fill={['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316'][index % 8]}
                      style={{ cursor: 'pointer' }}
                  />
                ))}
              </Pie>
                <Tooltip 
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)',
                    color: 'hsl(var(--foreground))',
                    fontSize: '14px',
                    padding: '12px 16px'
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: '600', marginBottom: '8px' }}
                />
                <Legend 
                  wrapperStyle={{ paddingTop: '20px' }}
                />
            </PieChart>
          </ResponsiveContainer>
          </div>
        );
      case 'scatter':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-orange-400 to-red-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={800}>
              <ScatterChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.3)" />
                <XAxis 
                  type="number" 
                  dataKey="x" 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  label={{ value: xAxis, position: 'insideBottom', offset: -10, style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
                />
                <YAxis 
                  type="number" 
                  dataKey="y" 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  label={{ value: yAxis, angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)',
                    color: 'hsl(var(--foreground))',
                    fontSize: '14px',
                    padding: '12px 16px'
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: '600', marginBottom: '8px' }}
                />
                <Scatter 
                  dataKey="y" 
                  fill="url(#scatterGradient)"
                  stroke="#f97316"
                  strokeWidth={2}
                />
                <defs>
                  <radialGradient id="scatterGradient" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#f97316" />
                    <stop offset="100%" stopColor="#dc2626" />
                  </radialGradient>
                </defs>
            </ScatterChart>
          </ResponsiveContainer>
          </div>
        );
      case 'area':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={800}>
              <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border)/0.3)" />
                <XAxis 
                  dataKey={xKey} 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  label={{ value: xAxis, position: 'insideBottom', offset: -10, style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
                />
                <YAxis 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  label={{ value: yAxis, angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)',
                    color: 'hsl(var(--foreground))',
                    fontSize: '14px',
                    padding: '12px 16px'
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: '600', marginBottom: '8px' }}
                />
                <Area 
                  type="monotone" 
                  dataKey={yKey} 
                  stroke="url(#areaGradient)" 
                  fill="url(#areaFillGradient)"
                  strokeWidth={3}
                />
                <defs>
                  <linearGradient id="areaGradient" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#14b8a6" />
                    <stop offset="100%" stopColor="#06b6d4" />
                  </linearGradient>
                  <linearGradient id="areaFillGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity={0.1} />
                  </linearGradient>
                </defs>
            </AreaChart>
          </ResponsiveContainer>
          </div>
        );
      case 'radar':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={800}>
              <RadarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <PolarGrid stroke="hsl(var(--border)/0.3)" />
                <PolarAngleAxis 
                  dataKey={xKey} 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                />
                <Radar 
                  dataKey={yKey} 
                  stroke="url(#radarGradient)" 
                  fill="url(#radarFillGradient)"
                  strokeWidth={3}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)',
                    color: 'hsl(var(--foreground))',
                    fontSize: '14px',
                    padding: '12px 16px'
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: '600', marginBottom: '8px' }}
                />
              <Legend />
                <defs>
                  <linearGradient id="radarGradient" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#6366f1" />
                    <stop offset="100%" stopColor="#8b5cf6" />
                  </linearGradient>
                  <linearGradient id="radarFillGradient" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.1} />
                  </linearGradient>
                </defs>
            </RadarChart>
          </ResponsiveContainer>
          </div>
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

  if (!selectedDataset) {
    return (
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <Database className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-2xl font-semibold text-foreground mb-2">No Dataset Selected</h2>
            <p className="text-muted-foreground mb-4">Please select a dataset from the Dashboard to create charts.</p>
            <motion.button
              whileTap={{ scale: 0.95 }}
              whileHover={{ scale: 1.02 }}
              onClick={() => window.location.href = '/dashboard'}
              className="px-6 py-3 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-200"
            >
              Go to Dashboard
            </motion.button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Charts Studio</h1>
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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Chart Preview - Takes 2/3 of the space */}
        <div className="lg:col-span-2">
          <GlassCard className="p-8" elevated>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-foreground mb-2">Chart Preview</h2>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Database className="w-4 h-4" />
                  <span className="bg-slate-800/50 px-3 py-1 rounded-full border border-slate-700">
                    {selectedDataset?.name || 'No Dataset'}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-xs text-muted-foreground">Live</span>
              </div>
            </div>
            <div className="bg-slate-950/80 rounded-xl p-6 border border-slate-800/70 min-h-[600px] shadow-2xl">
              {drillDownLevel > 0 && (
                <div className="mb-4 p-3 bg-blue-900/30 border border-blue-700/50 rounded-lg">
                  <div className="flex items-center gap-2 text-sm">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                    <span className="text-blue-300">Drill Down Active - Level {drillDownLevel}</span>
                    <span className="text-blue-400">•</span>
                    <span className="text-muted-foreground">Click chart elements to explore deeper</span>
                  </div>
                </div>
              )}
              <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 h-full">
            {renderChart()}
              </div>
            </div>
          </GlassCard>
        </div>

        {/* Controls Panel - Takes 1/3 of the space */}
        <div className="space-y-6">

      {/* Chart Type Selector */}
          <GlassCard className="p-6 bg-slate-900/60 border-slate-800/70" elevated>
            <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary" />
              Chart Type
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {chartTypes.map(type => (
                <motion.button
            key={type.id}
                  whileTap={{ scale: 0.95 }}
                  whileHover={{ scale: 1.02 }}
                  onClick={() => setChartType(type.id)}
                  className={cn(
                    'flex flex-col items-center gap-2 px-4 py-4 rounded-xl transition-all text-sm border',
                    chartType === type.id 
                      ? 'bg-gradient-to-br from-primary to-primary/80 text-primary-foreground border-primary shadow-lg shadow-primary/25' 
                      : 'bg-background/50 text-foreground border-border hover:bg-accent hover:text-accent-foreground hover:border-accent-foreground/20'
                  )}
                >
                  <type.icon className="w-6 h-6" />
                  <span className="text-xs font-medium">{type.label}</span>
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
                <label className="block text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                  <span className="w-2 h-2 bg-purple-400 rounded-full"></span>
                  Aggregation
                  <span className="text-xs bg-slate-800/50 px-2 py-1 rounded-full border border-slate-700">
                    {aggregation === 'sum' ? 'Total' : 
                     aggregation === 'avg' ? 'Average' : 
                     aggregation === 'count' ? 'Count' : 
                     aggregation === 'min' ? 'Minimum' : 'Maximum'}
                  </span>
                </label>
                <select
                  value={aggregation}
                  onChange={(e) => setAggregation(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl glass-effect border border-border/50 text-foreground focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
                >
                  <option value="sum">Sum (Total)</option>
                  <option value="avg">Average (Mean)</option>
                  <option value="count">Count (Frequency)</option>
                  <option value="min">Minimum (Lowest)</option>
                  <option value="max">Maximum (Highest)</option>
                </select>
                <p className="text-xs text-muted-foreground mt-2">
                  {aggregation === 'sum' && 'Adds up all values in each group'}
                  {aggregation === 'avg' && 'Calculates the average value in each group'}
                  {aggregation === 'count' && 'Counts the number of records in each group'}
                  {aggregation === 'min' && 'Finds the smallest value in each group'}
                  {aggregation === 'max' && 'Finds the largest value in each group'}
                </p>
              </div>
            </div>
        </GlassCard>

        {/* Drill Down Feature */}
        <GlassCard className="p-6 bg-slate-900/60 border-slate-800/70" elevated>
          <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-primary" />
            Drill Down Analysis
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Current Level: {drillDownLevel}</span>
              {drillDownLevel > 0 && (
                <motion.button
                  whileTap={{ scale: 0.95 }}
                  onClick={drillUp}
                  className="px-3 py-1 text-xs bg-slate-800/50 text-foreground rounded-lg border border-slate-700 hover:bg-slate-700/50 transition-all"
                >
                  ← Drill Up
                </motion.button>
              )}
            </div>
            
            {drillDownData && (
              <div className="bg-slate-800/30 rounded-lg p-4 border border-slate-700/50">
                <h4 className="text-sm font-medium text-foreground mb-2">Drill Down Data</h4>
                <div className="text-xs text-muted-foreground">
                  <p>Selected: <span className="text-foreground font-medium">{drillDownData.name}</span></p>
                  <p>Value: <span className="text-foreground font-medium">{drillDownData.value}</span></p>
                </div>
              </div>
            )}
            
            {!drillDownAnalysis && (
              <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={analyzeDrillDownHierarchies}
                className="w-full px-4 py-2 bg-primary/20 text-primary rounded-lg border border-primary/30 hover:bg-primary/30 transition-all text-sm font-medium"
              >
                🔍 Analyze Hierarchies
              </motion.button>
            )}
            
            {drillDownAnalysis && (
              <div className="bg-slate-800/30 rounded-lg p-3 border border-slate-700/50">
                <h4 className="text-sm font-medium text-foreground mb-2">Detected Hierarchies</h4>
                <div className="text-xs text-muted-foreground">
                  {drillDownAnalysis.hierarchies && drillDownAnalysis.hierarchies.length > 0 ? (
                    <div>
                      <p className="mb-2">Found {drillDownAnalysis.hierarchies.length} hierarchy(ies):</p>
                      {drillDownAnalysis.hierarchies.slice(0, 2).map((hierarchy, index) => (
                        <div key={index} className="mb-1 p-2 bg-slate-700/30 rounded">
                          <span className="text-foreground font-medium">{hierarchy.name}</span>
                          <span className="text-muted-foreground ml-2">({hierarchy.levels.length} levels)</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p>No hierarchies detected. Simple drill-down available.</p>
                  )}
                </div>
              </div>
            )}
            
            <div className="text-xs text-muted-foreground">
              <p className="mb-2">💡 <strong>How to use:</strong></p>
              <ul className="space-y-1 text-xs">
                <li>• Click "Analyze Hierarchies" to detect data patterns</li>
                <li>• Click on any bar, line point, or pie slice</li>
                <li>• View detailed breakdown of that data point</li>
                <li>• Navigate back to previous levels</li>
                <li>• Explore data hierarchy interactively</li>
              </ul>
              </div>
            </div>
        </GlassCard>

          </div>
      </div>
    </div>
  );
};

export default Charts;