import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ScatterChart, Scatter, AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis
} from 'recharts';
import { 
  Database, Save, Download, Settings, Loader2, ChevronLeft, ChevronRight
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
  const [currentPage, setCurrentPage] = useState(0);

  // All chart types with images from assets folder
  const chartTypes = [
    { id: 'bar', image: '/src/assets/bar.webp', label: 'Bar Chart', enabled: true },
    { id: 'line', image: '/src/assets/line.webp', label: 'Line Chart', enabled: true },
    { id: 'pie', image: '/src/assets/pie.webp', label: 'Pie Chart', enabled: true },
    { id: 'scatter', image: '/src/assets/scatter.webp', label: 'Scatter Plot', enabled: true },
    { id: 'area', image: '/src/assets/area.webp', label: 'Area Chart', enabled: true },
    { id: 'radar', image: '/src/assets/radar.webp', label: 'Radar Chart', enabled: true },
    { id: 'histogram', image: '/src/assets/histogram.webp', label: 'Histogram', enabled: true },
    { id: 'boxplot', image: '/src/assets/boxplot.webp', label: 'Box Plot', enabled: false },
    { id: 'heatmap', image: '/src/assets/heatmap.webp', label: 'Heatmap', enabled: false },
    { id: 'bubble', image: '/src/assets/bubble.webp', label: 'Bubble Chart', enabled: false },
    { id: 'timeseries', image: '/src/assets/timeseries.webp', label: 'Time Series', enabled: false },
    { id: 'candlestick', image: '/src/assets/candlestick.webp', label: 'Candlestick', enabled: false },
    { id: 'funnel', image: '/src/assets/funnel.webp', label: 'Funnel Chart', enabled: false },
    { id: 'treemap', image: '/src/assets/treemap.webp', label: 'Treemap', enabled: false },
    { id: 'waterfall', image: '/src/assets/watterfall.webp', label: 'Waterfall', enabled: false },
    { id: 'contour', image: '/src/assets/contour.webp', label: 'Contour', enabled: false },
    { id: 'density', image: '/src/assets/density.webp', label: 'Density Plot', enabled: false },
    { id: 'errorbar', image: '/src/assets/errorbar.webp', label: 'Error Bar', enabled: false },
    { id: 'ternary', image: '/src/assets/ternary.webp', label: 'Ternary Plot', enabled: false },
  ];

  // Pagination constants
  const CHART_TYPES_PER_PAGE = 6; // 3x2 grid
  const totalPages = Math.ceil(chartTypes.length / CHART_TYPES_PER_PAGE);

  // Pagination helper functions
  const goToNextPage = () => {
    setCurrentPage(prev => Math.min(prev + 1, totalPages - 1));
  };

  const goToPrevPage = () => {
    setCurrentPage(prev => Math.max(prev - 1, 0));
  };

  const goToPage = (page) => {
    setCurrentPage(Math.max(0, Math.min(page, totalPages - 1)));
  };

  // Get current page chart types
  const getCurrentPageChartTypes = () => {
    const startIndex = currentPage * CHART_TYPES_PER_PAGE;
    const endIndex = startIndex + CHART_TYPES_PER_PAGE;
    return chartTypes.slice(startIndex, endIndex);
  };

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

  const transformChartData = (backendData, chartType, xAxis, yAxis) => {
    console.log('Transforming data:', { backendData, chartType, xAxis, yAxis });
    
    if (!backendData || backendData.length === 0) {
      console.log('No backend data to transform');
      return [];
    }

    // Handle different chart types and their data formats
    if (chartType === 'pie') {
      // Backend returns { labels: [], values: [], type: "pie" } for pie charts
      if (backendData[0] && backendData[0].labels && backendData[0].values) {
        const pieData = backendData[0].labels.map((label, index) => ({
          name: label,
          value: backendData[0].values[index]
        }));
        console.log('Pie chart data (from labels/values):', pieData);
        return pieData;
      } else if (backendData[0] && backendData[0].name && backendData[0].value !== undefined) {
        // Backend returns individual objects with name/value
        console.log('Pie chart data (individual objects):', backendData);
        return backendData;
      } else {
        // Fallback: transform regular data for pie chart
        console.log('Using fallback pie chart transformation');
        const pieData = backendData.map(item => ({
          name: item[xAxis] || item.name || item.label || 'Unknown',
          value: item[yAxis] || item.value || 0
        }));
        console.log('Fallback pie chart data:', pieData);
        return pieData;
      }
    } else if (chartType === 'scatter') {
      // Backend returns { x: [], y: [] } for scatter plots
      if (backendData[0] && backendData[0].x && backendData[0].y) {
        const scatterData = backendData[0].x.map((xVal, index) => ({
          x: xVal,
          y: backendData[0].y[index]
        }));
        console.log('Scatter chart data:', scatterData);
        return scatterData;
      } else {
        // Fallback: transform regular data for scatter plot
        console.log('Using fallback scatter chart transformation');
        const scatterData = backendData.map(item => ({
          x: item[xAxis] || item.x || 0,
          y: item[yAxis] || item.y || 0
        }));
        console.log('Fallback scatter chart data:', scatterData);
        return scatterData;
      }
    } else {
      // For bar, line, area charts - backend returns array of objects
      const transformedData = [];
      
      backendData.forEach((item, index) => {
        console.log(`Processing item ${index}:`, item);
        console.log(`X-axis field (${xAxis}):`, item[xAxis]);
        console.log(`Y-axis field (${yAxis}):`, item[yAxis]);
        console.log(`Y-axis is array:`, Array.isArray(item[yAxis]));
        
        // Check if backend returned x/y arrays (for scatter, area, line charts)
        if (item.x && item.y && Array.isArray(item.x) && Array.isArray(item.y)) {
          console.log(`Creating data points from x/y arrays`);
          console.log(`x array length: ${item.x.length}, y array length: ${item.y.length}`);
          item.x.forEach((xValue, xIndex) => {
            const dataPoint = {
              [xAxis]: xValue,
              [yAxis]: item.y[xIndex]
            };
            console.log(`Created data point:`, dataPoint);
            transformedData.push(dataPoint);
          });
        }
        // Check if this item has the expected structure
        else if (item[xAxis] && Array.isArray(item[yAxis])) {
          // If Y-axis is an array, create multiple data points
          console.log(`Creating multiple data points for array Y-axis`);
          item[yAxis].forEach((yValue, yIndex) => {
            transformedData.push({
              [xAxis]: item[xAxis],
              [yAxis]: yValue
            });
          });
        } else if (item[xAxis] && item[yAxis] !== undefined) {
          // Single data point
          console.log(`Creating single data point`);
          transformedData.push({
            [xAxis]: item[xAxis],
            [yAxis]: item[yAxis]
          });
        } else {
          // Try to extract data from different possible structures
          console.log(`Using fallback data extraction`);
          const xValue = item[xAxis] || item.name || item.label || item[xAxis.toLowerCase()] || 'Unknown';
          const yValue = item[yAxis] || item.value || item.y || item[yAxis.toLowerCase()] || 0;
          
          transformedData.push({
            [xAxis]: xValue,
            [yAxis]: yValue
          });
        }
      });
      
      console.log('Bar/Line chart data:', transformedData);
      console.log('Transformed data length:', transformedData.length);
      if (transformedData.length > 0) {
        console.log('First transformed item:', transformedData[0]);
        console.log('First item keys:', Object.keys(transformedData[0]));
      }
      return transformedData;
    }
    
    console.log('Using raw backend data:', backendData);
    return backendData;
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
        
        // Check if backend returned any data
        if (!result.chart_data || result.chart_data.length === 0) {
          toast.error('No data available for the selected columns and aggregation. Try different columns or aggregation.');
          setChartData([]);
          return;
        }
        
        // Transform the data to match Recharts format
        const transformedData = transformChartData(result.chart_data, chartType, xAxis, yAxis);
        console.log('Transformed data:', transformedData);
        
        // Check if transformation resulted in valid data
        if (!transformedData || transformedData.length === 0) {
          toast.error('Unable to process chart data. Try different column combinations.');
          setChartData([]);
          return;
        }
        
        setChartData(transformedData);
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
    
    console.log('Chart data check:', { chartData, hasData, xKey, yKey });
    console.log('First chart data item:', chartData[0]);
    console.log('Chart data keys:', chartData[0] ? Object.keys(chartData[0]) : 'No data');

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
    
    // If no data at all, show empty state
    if (!chartData || chartData.length === 0) {
      return (
        <div className="h-[600px] flex items-center justify-center">
          <div className="text-center">
            <div className="text-muted-foreground mb-4">
              <h3 className="text-lg font-semibold mb-2">Cannot Generate Chart</h3>
              <p className="text-sm">The selected columns and aggregation cannot generate a meaningful chart.</p>
              <p className="text-sm mt-2">Try:</p>
              <ul className="text-sm mt-1 text-left max-w-md mx-auto">
                  <li>• Use "Count" aggregation for categorical columns</li>
                  <li>• Select numeric columns for Y-axis with sum/mean/max/min</li>
                  <li>• Try pie chart for categorical vs categorical</li>
                  <li>• Use bar chart for categorical vs numeric</li>
                  <li>• Use scatter/line chart for numeric vs numeric</li>
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
                    r: 6
                  }}
                  activeDot={{ 
                    r: 8, 
                    stroke: '#3b82f6', 
                    strokeWidth: 2, 
                    fill: '#fff'
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
              >
                {chartData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                      fill={['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316'][index % 8]}
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
      case 'histogram':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">{chartTitle}</h3>
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
                  label={{ value: 'Frequency', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: 'hsl(var(--muted-foreground))', fontSize: '14px', fontWeight: '600' } }}
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
                  fill="url(#histogramGradient)"
                  radius={[2, 2, 0, 0]}
                  stroke="hsl(var(--primary))"
                  strokeWidth={1}
                />
                <defs>
                  <linearGradient id="histogramGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" />
                    <stop offset="100%" stopColor="#ec4899" />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        );
      default:
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
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <Settings className="w-5 h-5 text-primary" />
                Chart Type
              </h3>
              <div className="text-xs text-slate-500">
                  {currentPage + 1} of {totalPages}
                </div>
            </div>
            
            {/* Chart Type Grid with Pagination */}
            <div className="space-y-4">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentPage}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                  className="grid grid-cols-3 gap-3"
                >
                  {getCurrentPageChartTypes().map((type) => (
                <motion.button
            key={type.id}
                      whileHover={{ scale: type.enabled ? 1.05 : 1 }}
                      whileTap={{ scale: type.enabled ? 0.95 : 1 }}
                      onClick={() => type.enabled && setChartType(type.id)}
                      disabled={!type.enabled}
                  className={cn(
                          'group flex flex-col items-center gap-2 p-3 rounded-2xl transition-all text-xs border relative overflow-hidden backdrop-blur-sm',
                        type.enabled
                          ? chartType === type.id 
                            ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white border-blue-400 shadow-lg shadow-blue-500/25 ring-2 ring-blue-400/50' 
                            : 'bg-slate-800/40 text-foreground border-slate-600/50 hover:bg-slate-700/60 hover:border-slate-500/70 hover:shadow-lg hover:shadow-slate-500/10'
                          : 'bg-slate-800/20 text-slate-500 border-slate-700/30 cursor-not-allowed opacity-50'
                        )}
                      >
                      {/* Chart Image */}
                        <div className={cn(
                          'w-10 h-10 rounded-xl overflow-hidden border-2 transition-all duration-200',
                        type.enabled
                          ? chartType === type.id 
                            ? 'border-white/30 bg-white/10' 
                            : 'border-slate-600/50 bg-slate-700/50 group-hover:border-slate-500/70'
                          : 'border-slate-700/30 bg-slate-800/50'
                        )}>
                        <img 
                          src={type.image} 
                          alt={type.label}
                            className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-110"
                          onError={(e) => {
                            e.target.style.display = 'none';
                            e.target.nextSibling.style.display = 'flex';
                          }}
                        />
                        {/* Fallback icon */}
                        <div className="w-full h-full flex items-center justify-center text-slate-400" style={{ display: 'none' }}>
                          <Settings className="w-5 h-5" />
                        </div>
                      </div>
                        <span className={cn(
                          'text-xs font-medium text-center leading-tight transition-colors',
                        type.enabled
                          ? chartType === type.id ? 'text-white' : 'text-slate-300 group-hover:text-white'
                          : 'text-slate-500'
                        )}>
                  {type.label}
                        </span>
                      {!type.enabled && (
                        <div className="absolute inset-0 bg-slate-900/50 flex items-center justify-center">
                          <span className="text-xs text-slate-400 font-medium">Coming Soon</span>
                        </div>
                      )}
                </motion.button>
                  ))}
                  
                  {/* Fill empty slots to maintain grid layout */}
                  {Array.from({ length: CHART_TYPES_PER_PAGE - getCurrentPageChartTypes().length }, (_, index) => (
                      <div key={`empty-${index}`} className="h-24" />
                  ))}
                </motion.div>
              </AnimatePresence>
              
              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4 border-t border-slate-700/50">
                  {/* Previous Button */}
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={goToPrevPage}
                    disabled={currentPage === 0}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all',
                      currentPage === 0
                        ? 'bg-slate-700/50 text-slate-500 cursor-not-allowed'
                        : 'bg-slate-800/60 text-slate-300 hover:bg-slate-700/60 hover:text-white border border-slate-600/50'
                    )}
                  >
                    <ChevronLeft className="w-4 h-4" />
                    Previous
                  </motion.button>
                  
                  {/* Page Indicators */}
                    <div className="flex items-center gap-2">
                    {Array.from({ length: totalPages }, (_, index) => (
                      <button
                        key={index}
                        onClick={() => goToPage(index)}
                        className={cn(
                          'w-2 h-2 rounded-full transition-all',
                          currentPage === index
                            ? 'bg-blue-400 w-6'
                            : 'bg-slate-600 hover:bg-slate-500'
                        )}
                      />
                    ))}
                  </div>
                  
                  {/* Next Button */}
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={goToNextPage}
                    disabled={currentPage === totalPages - 1}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all',
                      currentPage === totalPages - 1
                        ? 'bg-slate-700/50 text-slate-500 cursor-not-allowed'
                        : 'bg-slate-800/60 text-slate-300 hover:bg-slate-700/60 hover:text-white border border-slate-600/50'
                    )}
                  >
                    Next
                    <ChevronRight className="w-4 h-4" />
                  </motion.button>
                </div>
              )}
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


          </div>
      </div>
    </div>
  );
};

export default Charts;