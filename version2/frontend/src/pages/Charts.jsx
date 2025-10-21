import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, 
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis
} from 'recharts';
import { 
  BarChart3, TrendingUp, PieChart as PieIcon, ChartScatter, 
  AreaChart as AreaChartIcon, Radar as RadarIcon, Database, Save, Download, Settings, Loader2,
  ChevronLeft, ChevronRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import GlassCard from '../components/common/GlassCard';
import { toast } from 'react-hot-toast';
import { cn } from '../lib/utils';
import useDatasetStore from '../store/datasetStore';
import { datasetAPI } from '../services/api';
import Plotly from 'plotly.js-dist-min';

// Plotly Chart Component
const PlotlyChart = ({ data, layout, config }) => {
  const plotRef = React.useRef(null);

  React.useEffect(() => {
    if (plotRef.current && data && layout) {
      Plotly.newPlot(plotRef.current, data, layout, config);
    }
  }, [data, layout, config]);

  React.useEffect(() => {
    return () => {
      if (plotRef.current) {
        Plotly.purge(plotRef.current);
      }
    };
  }, []);

  return <div ref={plotRef} style={{ width: '100%', height: '100%' }} />;
};

const Charts = () => {
  const { selectedDataset } = useDatasetStore();
  
  // Add CSS for hiding scrollbars
  React.useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `
      .scrollbar-hide {
        -ms-overflow-style: none;
        scrollbar-width: none;
      }
      .scrollbar-hide::-webkit-scrollbar {
        display: none;
      }
    `;
    document.head.appendChild(style);
    return () => document.head.removeChild(style);
  }, []);
  const [chartType, setChartType] = useState('bar');
  const [xAxis, setXAxis] = useState('');
  const [yAxis, setYAxis] = useState('');
  const [aggregation, setAggregation] = useState('sum');
  const [loading, setLoading] = useState(true);
  const [chartData, setChartData] = useState([]);
  const [columns, setColumns] = useState([]);
  const [currentPage, setCurrentPage] = useState(0);

  // All chart types with images - using type ID as image name for easy backend generation
  const chartTypes = [
    { id: 'bar', image: '/src/assets/bar.webp', label: 'Bar Chart' },
    { id: 'line', image: '/src/assets/line.webp', label: 'Line Chart' },
    { id: 'pie', image: '/src/assets/pie.webp', label: 'Pie Chart' },
    { id: 'scatter', image: '/src/assets/scatter.webp', label: 'Scatter Plot' },
    { id: 'area', image: '/src/assets/area.webp', label: 'Area Chart' },
    { id: 'radar', image: '/src/assets/radar.webp', label: 'Radar Chart' },
    { id: 'histogram', image: '/src/assets/histogram.webp', label: 'Histogram' },
    { id: 'boxplot', image: '/src/assets/boxplot.webp', label: 'Box Plot' },
    { id: 'heatmap', image: '/src/assets/heatmap.webp', label: 'Heatmap' },
    { id: 'bubble', image: '/src/assets/bubble.webp', label: 'Bubble Chart' },
    { id: 'timeseries', image: '/src/assets/timeseries.webp', label: 'Time Series' },
    { id: 'candlestick', image: '/src/assets/candlestick.webp', label: 'Candlestick' },
    { id: 'funnel', image: '/src/assets/funnel.webp', label: 'Funnel Chart' },
    { id: 'treemap', image: '/src/assets/treemap.webp', label: 'Treemap' },
    { id: 'waterfall', image: '/src/assets/waterfall.webp', label: 'Waterfall' },
    { id: 'contour', image: '/src/assets/contour.webp', label: 'Contour' },
    { id: 'density', image: '/src/assets/density.webp', label: 'Density Plot' },
    { id: 'errorbar', image: '/src/assets/errorbar.webp', label: 'Error Bar' },
    { id: 'ternary', image: '/src/assets/ternary.webp', label: 'Ternary Plot' },
  ];

  // Pagination constants
  const CHART_TYPES_PER_PAGE = 12; // 4x3 grid
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
      // Validate chart generation possibility
      const xCol = columns.find(col => col.name === xAxis);
      const yCol = columns.find(col => col.name === yAxis);
      
      // Check for impossible combinations
      if (xCol && yCol) {
        // Both categorical columns - only pie charts and bar charts with count work well
        if (xCol.is_categorical && yCol.is_categorical) {
          if (chartType === 'scatter' || chartType === 'line' || chartType === 'area') {
            toast.error(`Cannot create ${chartType} chart with two categorical columns. Try pie chart or bar chart with count aggregation.`);
            return;
          }
          if (aggregation !== 'count') {
            toast.warning(`Both columns are categorical. Using "Count" aggregation for better results.`);
            setAggregation('count');
          }
        }
        // Y-axis categorical but trying numeric aggregations
        else if (yCol.is_categorical && !['count'].includes(aggregation)) {
          toast.error(`Cannot use "${aggregation}" aggregation on categorical column "${yAxis}". Use "Count" instead.`);
          setAggregation('count');
          return;
        }
        // Both categorical columns with count - show explanation
        else if (xCol.is_categorical && yCol.is_categorical && aggregation === 'count') {
          toast.info(`Showing count of "${yAxis}" values for each "${xAxis}" value. This shows how many different ${yAxis.toLowerCase()} appear per ${xAxis.toLowerCase()}.`);
        }
        // X-axis categorical, Y-axis numeric - most charts work
        else if (xCol.is_categorical && yCol.is_numeric) {
          // This is fine for most chart types
        }
        // Both numeric - scatter, line, area work well
        else if (xCol.is_numeric && yCol.is_numeric) {
          if (chartType === 'pie') {
            toast.warning(`Pie charts work best with categorical data. Consider using bar chart for numeric data.`);
          }
        }
      }
      
      generateChartData();
    }
  }, [selectedDataset, xAxis, yAxis, aggregation, chartType, columns]);


  const loadDatasetColumns = async () => {
    if (!selectedDataset) return;
    
    try {
      setLoading(true);
      
      // Use the new backend endpoint to get columns with metadata
      const response = await fetch(`/api/datasets/${selectedDataset.id}/columns`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('datasage-token')}`
        }
      });
      
      if (response.ok) {
        const result = await response.json();
        const columns = result.columns || [];
        const columnNames = columns.map(col => col.name);
        setColumns(columnNames);
        
        // Auto-select first two columns if none selected
        if (!xAxis && columnNames.length > 0) {
          setXAxis(columnNames[0]);
        }
        if (!yAxis && columnNames.length > 1) {
          setYAxis(columnNames[1]);
        }
        
        // Suggest appropriate chart type and column combinations based on data types
        if (columns.length >= 2) {
          const xCol = columns.find(col => col.name === columnNames[0]);
          const yCol = columns.find(col => col.name === columnNames[1]);
          
          if (xCol && yCol) {
            // If both are categorical, suggest pie chart
            if (xCol.is_categorical && yCol.is_categorical) {
              setChartType('pie');
              setAggregation('count');
            }
            // If x is temporal and y is numeric, suggest timeseries chart
            else if (xCol.is_temporal && yCol.is_numeric) {
              setChartType('timeseries');
            }
            // If both are numeric, suggest scatter plot
            else if (xCol.is_numeric && yCol.is_numeric) {
              setChartType('scatter');
            }
            // If Y is categorical, suggest bar chart with count
            else if (yCol.is_categorical) {
              setChartType('bar');
              setAggregation('count');
            }
            // If X is categorical and Y is numeric, suggest bar chart
            else if (xCol.is_categorical && yCol.is_numeric) {
              setChartType('bar');
              setAggregation('sum');
            }
            // Check for OHLC data for candlestick charts
            else if (xCol.is_temporal && ['open', 'high', 'low', 'close'].some(col => 
              columnNames.some(name => name.toLowerCase().includes(col)))) {
              setChartType('candlestick');
            }
            // Default to bar chart
            else {
              setChartType('bar');
            }
          }
        }
      } else {
        // Fallback: Use dataset metadata if available
        if (selectedDataset.metadata?.column_metadata) {
          const columnNames = selectedDataset.metadata.column_metadata.map(col => col.name);
        setColumns(columnNames);
        
        if (!xAxis && columnNames.length > 0) {
          setXAxis(columnNames[0]);
        }
        if (!yAxis && columnNames.length > 1) {
          setYAxis(columnNames[1]);
        }
      } else {
          // Final fallback: Use common column names
        const fallbackColumns = ['Player_Name', 'DOB', 'Batting_Hand', 'Bowling_Skill', 'Country', 'Age'];
        setColumns(fallbackColumns);
        
        if (!xAxis) setXAxis(fallbackColumns[0]);
        if (!yAxis) setYAxis(fallbackColumns[1]);
        
        toast.warning('Using sample columns - dataset may not be fully processed yet');
        }
      }
    } catch (error) {
      console.error('Failed to load dataset columns:', error);
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
        console.log('Backend response:', result);
        console.log('Chart data:', result.chart_data);
        
        // Check if backend returned any data
        if (!result.chart_data || result.chart_data.length === 0) {
          toast.error('No data available for the selected columns and aggregation. Try different columns or aggregation.');
          setChartData([]);
          return;
        }
        
        // Transform the data to match your existing chart format
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
        toast.error(error.detail || 'Failed to generate chart data');
        setChartData([]);
      }
    } catch (error) {
      console.error('Chart generation error:', error);
      toast.error('Failed to generate chart data');
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
          item.x.forEach((xValue, xIndex) => {
            transformedData.push({
              [xAxis]: xValue,
              [yAxis]: item.y[xIndex]
            });
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
      return transformedData;
    }
    
    console.log('Using raw backend data:', backendData);
    return backendData;
  };


  const renderChart = () => {
    if (loading) return (
        <div className="h-[600px] flex items-center justify-center">
          <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto">
            <Loader2 className="animate-spin w-8 h-8 text-blue-400" />
          </div>
            <div>
              <h3 className="text-lg font-semibold text-white mb-2">Generating Chart</h3>
              <p className="text-sm text-slate-400">Processing your data visualization...</p>
            </div>
          </div>
        </div>
      );
    
    if (!xAxis || !yAxis) return (
      <div className="h-[600px] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-500/20 to-slate-600/20 border border-slate-500/30 flex items-center justify-center mx-auto">
            <BarChart3 className="w-8 h-8 text-slate-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white mb-2">Ready to Visualize</h3>
            <p className="text-sm text-slate-400">Select X and Y axes to create your chart</p>
          </div>
        </div>
      </div>
    );

    const xKey = xAxis;
    const yKey = yAxis;
    const getChartTitle = () => {
      if (aggregation === 'count' && xAxis && yAxis) {
        return `Count of ${yAxis} by ${xAxis}`;
      } else if (aggregation === 'raw' && xAxis && yAxis) {
        return `${xAxis} vs ${yAxis}`;
      } else if (aggregation && aggregation !== 'raw' && xAxis && yAxis) {
        return `${aggregation.charAt(0).toUpperCase() + aggregation.slice(1)} of ${yAxis} by ${xAxis}`;
      } else {
        return `${yAxis} by ${xAxis}`;
      }
    };
    
    const chartTitle = getChartTitle();

    // Check if chart data has meaningful values
    const hasData = chartData && chartData.length > 0 && chartData.some(item => {
      // Check for different possible data structures
      const hasValue = (item[yKey] !== undefined && item[yKey] !== null) || 
          (item.y !== undefined && item.y !== null) || 
                      (item.value !== undefined && item.value !== null);
      return hasValue;
    });
    
    console.log('Chart data check:', { chartData, hasData, xKey, yKey });
    console.log('First chart data item:', chartData[0]);
    console.log('Chart data keys:', chartData[0] ? Object.keys(chartData[0]) : 'No data');
    
    // For debugging: show data values
    if (chartData && chartData.length > 0) {
      console.log('Sample data values:', chartData.slice(0, 3).map(item => ({
        [xKey]: item[xKey],
        [yKey]: item[yKey],
        yValue: item[yKey],
        isNumeric: !isNaN(item[yKey])
      })));
    }

    if (!hasData && chartData && chartData.length > 0) {
      return (
        <div className="h-[600px] flex items-center justify-center">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto">
              <BarChart3 className="w-8 h-8 text-blue-400" />
            </div>
            <div className="max-w-md mx-auto">
              <h3 className="text-lg font-semibold text-white mb-2">Data Format Issue</h3>
              <p className="text-sm text-slate-400 mb-4">Chart data received but format doesn't match expected structure.</p>
              <div className="bg-slate-800/30 rounded-lg p-4 border border-slate-600/30">
                <p className="text-sm text-slate-300 mb-2">Try these solutions:</p>
                <ul className="text-sm text-slate-400 space-y-1 text-left">
                  <li>• Use "Count" aggregation for categorical Y-axis columns</li>
                <li>• Select a numeric column for Y-axis</li>
                <li>• Try a different column combination</li>
              </ul>
              </div>
            </div>
          </div>
        </div>
      );
    }
    
    // If no data at all, show empty state
    if (!chartData || chartData.length === 0) {
      return (
        <div className="h-[600px] flex items-center justify-center">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-red-500/20 to-red-600/20 border border-red-500/30 flex items-center justify-center mx-auto">
              <BarChart3 className="w-8 h-8 text-red-400" />
            </div>
            <div className="max-w-md mx-auto">
              <h3 className="text-lg font-semibold text-white mb-2">Cannot Generate Chart</h3>
              <p className="text-sm text-slate-400 mb-4">The selected columns and aggregation cannot generate a meaningful chart.</p>
              <div className="bg-slate-800/30 rounded-lg p-4 border border-slate-600/30">
                <p className="text-sm text-slate-300 mb-2">Try these solutions:</p>
                <ul className="text-sm text-slate-400 space-y-1 text-left">
                  <li>• Use "Count" aggregation for categorical columns</li>
                  <li>• Select numeric columns for Y-axis with sum/mean/max/min</li>
                  <li>• Try pie chart for categorical vs categorical</li>
                  <li>• Use bar chart for categorical vs numeric</li>
                  <li>• Use scatter/line chart for numeric vs numeric</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      );
    }

    console.log('Rendering chart:', chartType, 'with data:', chartData);
    
    // Debug panel for troubleshooting
    const debugInfo = {
      chartType,
      xAxis,
      yAxis,
      aggregation,
      dataLength: chartData.length,
      firstItem: chartData[0],
      hasValidData: hasData
    };

    switch (chartType) {
      case 'bar':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">{chartTitle}</h3>
            {/* Debug panel - remove this in production */}
            {process.env.NODE_ENV === 'development' && (
              <div className="mb-4 p-3 bg-slate-800/50 rounded-lg border border-slate-600/50 text-xs">
                <div className="text-slate-300 font-semibold mb-2">Debug Info:</div>
                <div className="text-slate-400 space-y-1">
                  <div>Chart: {debugInfo.chartType} | X: {debugInfo.xAxis} | Y: {debugInfo.yAxis}</div>
                  <div>Aggregation: {debugInfo.aggregation} | Data Points: {debugInfo.dataLength}</div>
                  <div>Valid Data: {debugInfo.hasValidData ? 'Yes' : 'No'}</div>
                  <div>First Item: {JSON.stringify(debugInfo.firstItem)}</div>
                </div>
              </div>
            )}
            <ResponsiveContainer width="100%" height={900}>
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
            <ResponsiveContainer width="100%" height={900}>
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
        console.log('Rendering pie chart with data:', chartData);
        // Filter out zero values for better visualization
        const filteredData = chartData.filter(item => item.value > 0);
        console.log('Filtered pie chart data:', filteredData);
        
        if (filteredData.length === 0) {
          return (
            <div className="h-[600px] flex items-center justify-center">
              <div className="text-center space-y-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-pink-500/20 to-purple-600/20 border border-pink-500/30 flex items-center justify-center mx-auto">
                  <PieIcon className="w-8 h-8 text-pink-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-2">No Data to Display</h3>
                  <p className="text-sm text-slate-400">All values are zero or empty</p>
                </div>
              </div>
            </div>
          );
        }
        
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-pink-400 to-purple-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={900}>
            <PieChart>
              <Pie
                data={filteredData}
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
                {filteredData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                      fill={['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316'][index % 8]}
                  />
                ))}
              </Pie>
                <Tooltip 
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #475569',
                    borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.5)',
                    color: '#ffffff',
                    fontSize: '14px',
                    padding: '12px 16px'
                  }}
                  labelStyle={{ 
                    color: '#ffffff', 
                    fontWeight: '600', 
                    marginBottom: '8px',
                    fontSize: '16px'
                  }}
                  formatter={(value, name) => [
                    `${value} (${((value / filteredData.reduce((sum, item) => sum + item.value, 0)) * 100).toFixed(1)}%)`,
                    name
                  ]}
                />
            </PieChart>
          </ResponsiveContainer>
          </div>
        );
      case 'scatter':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-orange-400 to-red-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={900}>
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
            <ResponsiveContainer width="100%" height={900}>
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
            <ResponsiveContainer width="100%" height={900}>
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
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <ResponsiveContainer width="100%" height={900}>
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
                <Bar 
                  dataKey={yKey} 
                  fill="url(#histogramGradient)"
                  radius={[0, 0, 0, 0]}
                />
                <defs>
                  <linearGradient id="histogramGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" />
                    <stop offset="100%" stopColor="#8b5cf6" />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        );
      case 'boxplot':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-orange-400 to-red-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Box Plot</h3>
                <p className="text-sm">Box plot visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'heatmap':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-red-400 to-pink-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Heatmap</h3>
                <p className="text-sm">Heatmap visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'bubble':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Bubble Chart</h3>
                <p className="text-sm">Bubble chart visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'timeseries':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px]">
              <PlotlyChart 
                data={[{
                  x: chartData.map(item => item.x || item.timestamp),
                  y: chartData.map(item => item.y || item.value),
                  type: 'scatter',
                  mode: 'lines+markers',
                  name: yAxis,
                  line: {
                    color: '#3b82f6',
                    width: 3
                  },
                  marker: {
                    color: '#3b82f6',
                    size: 6
                  }
                }]}
                layout={{
                  title: {
                    text: chartTitle,
                    font: { color: '#ffffff', size: 18 }
                  },
                  xaxis: {
                    title: { text: xAxis, font: { color: '#94a3b8' } },
                    color: '#94a3b8',
                    gridcolor: '#374151',
                    linecolor: '#374151'
                  },
                  yaxis: {
                    title: { text: yAxis, font: { color: '#94a3b8' } },
                    color: '#94a3b8',
                    gridcolor: '#374151',
                    linecolor: '#374151'
                  },
                  plot_bgcolor: 'rgba(0,0,0,0)',
                  paper_bgcolor: 'rgba(0,0,0,0)',
                  font: { color: '#ffffff' },
                  margin: { l: 60, r: 30, t: 60, b: 60 }
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
                  toImageButtonOptions: {
                    format: 'png',
                    filename: 'timeseries_chart',
                    height: 600,
                    width: 800,
                    scale: 2
                  }
                }}
              />
            </div>
          </div>
        );
      case 'candlestick':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px]">
              <PlotlyChart 
                data={[{
                  x: chartData.map(item => item.x),
                  open: chartData.map(item => item.open),
                  high: chartData.map(item => item.high),
                  low: chartData.map(item => item.low),
                  close: chartData.map(item => item.close),
                  type: 'candlestick',
                  name: yAxis,
                  increasing: { line: { color: '#10b981' } },
                  decreasing: { line: { color: '#ef4444' } }
                }]}
                layout={{
                  title: {
                    text: chartTitle,
                    font: { color: '#ffffff', size: 18 }
                  },
                  xaxis: {
                    title: { text: xAxis, font: { color: '#94a3b8' } },
                    color: '#94a3b8',
                    gridcolor: '#374151',
                    linecolor: '#374151'
                  },
                  yaxis: {
                    title: { text: yAxis, font: { color: '#94a3b8' } },
                    color: '#94a3b8',
                    gridcolor: '#374151',
                    linecolor: '#374151'
                  },
                  plot_bgcolor: 'rgba(0,0,0,0)',
                  paper_bgcolor: 'rgba(0,0,0,0)',
                  font: { color: '#ffffff' },
                  margin: { l: 60, r: 30, t: 60, b: 60 }
                }}
                config={{
                  displayModeBar: true,
                  displaylogo: false,
                  modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
                  toImageButtonOptions: {
                    format: 'png',
                    filename: 'candlestick_chart',
                    height: 600,
                    width: 800,
                    scale: 2
                  }
                }}
              />
            </div>
          </div>
        );
      case 'funnel':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Funnel Chart</h3>
                <p className="text-sm">Funnel chart visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'treemap':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Treemap</h3>
                <p className="text-sm">Treemap visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'waterfall':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Waterfall Chart</h3>
                <p className="text-sm">Waterfall chart visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'contour':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Contour Plot</h3>
                <p className="text-sm">Contour plot visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'density':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-violet-400 to-purple-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Density Plot</h3>
                <p className="text-sm">Density plot visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'errorbar':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-rose-400 to-pink-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Error Bar Chart</h3>
                <p className="text-sm">Error bar chart visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      case 'ternary':
        return (
          <div>
            <h3 className="text-xl font-bold text-foreground mb-6 text-center bg-gradient-to-r from-amber-400 to-yellow-400 bg-clip-text text-transparent">{chartTitle}</h3>
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Ternary Plot</h3>
                <p className="text-sm">Ternary plot visualization coming soon</p>
              </div>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  if (loading && !selectedDataset) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-6">
        {/* Background Pattern */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(59,130,246,0.1),transparent_50%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(37,99,235,0.08),transparent_50%)] pointer-events-none" />
        
        <div className="relative text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto">
            <Loader2 className="animate-spin w-8 h-8 text-blue-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white mb-2">Loading Charts Studio</h3>
            <p className="text-sm text-slate-400">Preparing your visualization workspace...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!selectedDataset) {
  return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-6">
        {/* Background Pattern */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(59,130,246,0.1),transparent_50%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(37,99,235,0.08),transparent_50%)] pointer-events-none" />
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="relative text-center space-y-6 max-w-md mx-auto"
        >
          <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto">
            <Database className="w-12 h-12 text-blue-400" />
          </div>
          <div className="space-y-3">
            <h2 className="text-3xl font-bold bg-gradient-to-r from-white to-blue-100 bg-clip-text text-transparent">
              No Dataset Selected
            </h2>
            <p className="text-lg text-slate-400 leading-relaxed">
              Please select a dataset from the Dashboard to start creating beautiful visualizations.
            </p>
          </div>
            <motion.button
              whileTap={{ scale: 0.95 }}
              whileHover={{ scale: 1.02 }}
              onClick={() => window.location.href = '/dashboard'}
            className="px-8 py-4 rounded-2xl bg-gradient-to-r from-blue-600 to-blue-700 text-white hover:from-blue-500 hover:to-blue-600 transition-all duration-200 font-medium shadow-lg shadow-blue-500/25 hover:shadow-xl hover:shadow-blue-500/30"
            >
              Go to Dashboard
            </motion.button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Background Pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(59,130,246,0.1),transparent_50%)] pointer-events-none" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(37,99,235,0.08),transparent_50%)] pointer-events-none" />
      
      <div className="relative space-y-8 p-6">
        {/* Enhanced Header */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex flex-col lg:flex-row lg:items-center justify-between gap-6"
        >
          <div className="space-y-3">
        <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-white via-blue-100 to-blue-200 bg-clip-text text-transparent">
                Charts Studio
              </h1>
              <div className="flex items-center gap-2 mt-1">
                {/* <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div> */}
                {/* <span className="text-sm text-muted-foreground">Live Editor</span> */}
              </div>
            </div>
            <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
              Build professional visualizations like in Power BI—select your data and create stunning charts with intelligent recommendations.
            </p>
        </div>
        
          {/* Enhanced Action Buttons */}
          <div className="flex items-center gap-3">
          <motion.button
            whileTap={{ scale: 0.95 }}
            whileHover={{ scale: 1.02 }}
            onClick={() => toast('Chart saved!')}
              className="group px-6 py-3 rounded-2xl bg-white/5 border border-white/20 text-white hover:bg-white/10 hover:border-white/30 focus-visible-ring transition-all duration-200 flex items-center gap-2 font-medium backdrop-blur-md shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!xAxis || !yAxis}
          >
              <Save className="w-4 h-4 group-hover:rotate-12 transition-transform duration-200" />
              Save Chart
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.95 }}
            whileHover={{ scale: 1.02 }}
            onClick={() => toast('Exported to PNG')}
              className="group px-6 py-3 rounded-2xl bg-white/5 border border-white/20 text-white hover:bg-white/10 hover:border-white/30 focus-visible-ring transition-all duration-200 flex items-center gap-2 font-medium backdrop-blur-md shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!xAxis || !yAxis}
          >
              <Download className="w-4 h-4 group-hover:translate-y-0.5 transition-transform duration-200" />
            Export
          </motion.button>
        </div>
        </motion.div>

      {/* Main Layout - Left Chart, Right Controls */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="grid grid-cols-1 lg:grid-cols-3 gap-8"
        >
          {/* Enhanced Chart Preview - Takes 2/3 of the space */}
        <div className="lg:col-span-2">
            <GlassCard className="p-8 bg-gradient-to-br from-slate-900/80 to-slate-800/60 border-slate-700/50 shadow-2xl" elevated>
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                    <BarChart3 className="w-5 h-5 text-blue-400" />
              </div>
                  <h2 className="text-2xl font-bold bg-gradient-to-r from-white to-blue-100 bg-clip-text text-transparent">
                    Chart Preview
                  </h2>
            </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                    <span className="text-xs text-blue-400 font-medium">Live Preview</span>
              </div>
                  <div className="text-xs text-muted-foreground">
                    {chartData.length} data points
            </div>
                </div>
              </div>
              
              {/* Enhanced Chart Container */}
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-blue-600/5 rounded-2xl blur-xl"></div>
                <div className="relative bg-slate-950 rounded-2xl p-8 border border-slate-700/50 min-h-[700px] shadow-inner">
                  <div className="h-full">
            {renderChart()}
              </div>
                </div>
                
            </div>
          </GlassCard>
        </div>

          {/* Enhanced Controls Panel - Takes 1/3 of the space */}
        <div className="space-y-6">
            {/* Enhanced Chart Type Selector */}
            <GlassCard className="p-6 bg-gradient-to-br from-slate-900/70 to-slate-800/50 border-slate-700/50 shadow-xl" elevated>
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                    <BarChart3 className="w-4 h-4 text-blue-400" />
                  </div>
                  <h3 className="text-lg font-semibold bg-gradient-to-r from-white to-blue-100 bg-clip-text text-transparent">
                Chart Type
              </h3>
                </div>
              {totalPages > 1 && (
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/50 border border-slate-600/50">
                    <span className="text-sm text-muted-foreground">
                  {currentPage + 1} of {totalPages}
                    </span>
                </div>
              )}
            </div>
            
              {/* Enhanced Chart Types Grid */}
            <div className="relative">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentPage}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                    className="grid grid-cols-4 gap-3 min-h-[140px]"
                >
                  {getCurrentPageChartTypes().map(type => (
                <motion.button
            key={type.id}
                      whileTap={{ scale: 0.95 }}
                        whileHover={{ scale: 1.05 }}
                  onClick={() => setChartType(type.id)}
                  className={cn(
                          'group flex flex-col items-center gap-2 p-3 rounded-2xl transition-all text-xs border relative overflow-hidden backdrop-blur-sm',
                    chartType === type.id 
                            ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white border-blue-400 shadow-lg shadow-blue-500/25 ring-2 ring-blue-400/50' 
                            : 'bg-slate-800/40 text-foreground border-slate-600/50 hover:bg-slate-700/60 hover:border-slate-500/70 hover:shadow-lg hover:shadow-slate-500/10'
                        )}
                      >
                        {/* Enhanced Chart Image */}
                        <div className={cn(
                          'w-10 h-10 rounded-xl overflow-hidden border-2 transition-all duration-200',
                          chartType === type.id 
                            ? 'border-white/30 bg-white/10' 
                            : 'border-slate-600/50 bg-slate-700/50 group-hover:border-slate-500/70'
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
                          {/* Enhanced Fallback icon */}
                        <div className="w-full h-full flex items-center justify-center text-slate-400" style={{ display: 'none' }}>
                            <BarChart3 className="w-5 h-5" />
                        </div>
                      </div>
                        <span className={cn(
                          'text-xs font-medium text-center leading-tight transition-colors',
                          chartType === type.id ? 'text-white' : 'text-slate-300 group-hover:text-white'
                        )}>
                  {type.label}
                        </span>
                        
                </motion.button>
                  ))}
                  
                  {/* Fill empty slots to maintain grid layout */}
                  {Array.from({ length: CHART_TYPES_PER_PAGE - getCurrentPageChartTypes().length }, (_, index) => (
                      <div key={`empty-${index}`} className="h-24" />
                  ))}
                </motion.div>
              </AnimatePresence>
              
                {/* Enhanced Pagination Controls */}
              {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-700/50">
                  {/* Previous Button */}
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={goToPrevPage}
                    disabled={currentPage === 0}
                    className={cn(
                        'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all backdrop-blur-sm',
                      currentPage === 0
                          ? 'text-slate-500 cursor-not-allowed bg-slate-800/30'
                          : 'text-slate-300 hover:text-white bg-slate-700/50 hover:bg-slate-600/60 border border-slate-600/50 hover:border-slate-500/70'
                    )}
                  >
                    <ChevronLeft className="w-4 h-4" />
                    Previous
                  </motion.button>
                  
                    {/* Enhanced Page Indicators */}
                    <div className="flex items-center gap-2">
                    {Array.from({ length: totalPages }, (_, index) => (
                      <motion.button
                        key={index}
                        whileTap={{ scale: 0.9 }}
                        onClick={() => goToPage(index)}
                        className={cn(
                            'w-3 h-3 rounded-full transition-all duration-200',
                          currentPage === index
                              ? 'bg-gradient-to-r from-blue-500 to-blue-600 scale-125 shadow-lg shadow-blue-500/25'
                              : 'bg-slate-600 hover:bg-slate-500 hover:scale-110'
                        )}
                      />
                    ))}
                  </div>
                  
                  {/* Next Button */}
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={goToNextPage}
                    disabled={currentPage === totalPages - 1}
                    className={cn(
                        'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all backdrop-blur-sm',
                      currentPage === totalPages - 1
                          ? 'text-slate-500 cursor-not-allowed bg-slate-800/30'
                          : 'text-slate-300 hover:text-white bg-slate-700/50 hover:bg-slate-600/60 border border-slate-600/50 hover:border-slate-500/70'
                    )}
                  >
                    Next
                    <ChevronRight className="w-4 h-4" />
                  </motion.button>
                </div>
              )}
      </div>
      </GlassCard>

            {/* Enhanced Axis Configuration */}
            <GlassCard className="p-6 bg-gradient-to-br from-slate-900/70 to-slate-800/50 border-slate-700/50 shadow-xl" elevated>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                  <Settings className="w-4 h-4 text-blue-400" />
                </div>
                <h3 className="text-lg font-semibold bg-gradient-to-r from-white to-blue-100 bg-clip-text text-transparent">
                  Data Mapping
                </h3>
              </div>
              
              <div className="space-y-6">
                {/* X Axis Selection */}
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                    <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                    X Axis
                    {xAxis && (
                      <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-1 rounded-full border border-blue-500/30">
                        {xAxis}
                      </span>
                    )}
                  </label>
                <select
                  value={xAxis}
                  onChange={(e) => setXAxis(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-600/50 text-foreground focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all backdrop-blur-sm hover:bg-slate-700/50"
                  disabled={!selectedDataset}
                >
                  <option value="">Choose X column...</option>
                  {columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
            </div>

                {/* Y Axis Selection */}
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                    <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                    Y Axis
                    {yAxis && (
                      <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-1 rounded-full border border-blue-500/30">
                        {yAxis}
                      </span>
                    )}
                  </label>
                <select
                  value={yAxis}
                  onChange={(e) => setYAxis(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-600/50 text-foreground focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all backdrop-blur-sm hover:bg-slate-700/50"
                  disabled={!selectedDataset}
                >
                  <option value="">Choose Y column...</option>
                  {columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
          </div>

                {/* Enhanced Aggregation Selection */}
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                    <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                  Aggregation
                    <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-1 rounded-full border border-blue-500/30">
                    {aggregation === 'sum' ? 'Total' : 
                     aggregation === 'mean' ? 'Average' : 
                     aggregation === 'count' ? 'Count' : 
                     aggregation === 'min' ? 'Minimum' : 
                     aggregation === 'max' ? 'Maximum' :
                     aggregation === 'median' ? 'Median' :
                     aggregation === 'std' ? 'Std Dev' :
                     aggregation === 'var' ? 'Variance' : 'Sum'}
                  </span>
                </label>
                <select
                  value={aggregation}
                  onChange={(e) => setAggregation(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-600/50 text-foreground focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all backdrop-blur-sm hover:bg-slate-700/50"
                >
                  <option value="sum">Sum (Total)</option>
                  <option value="mean">Average (Mean)</option>
                  <option value="count">Count (Frequency)</option>
                  <option value="min">Minimum (Lowest)</option>
                  <option value="max">Maximum (Highest)</option>
                  <option value="median">Median (Middle)</option>
                  <option value="std">Standard Deviation</option>
                  <option value="var">Variance</option>
                </select>
                  
                  {/* Enhanced Description */}
                  <motion.div 
                    key={aggregation}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-3 rounded-lg bg-slate-800/30 border border-slate-600/30"
                  >
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {aggregation === 'sum' && 'Adds up all values in each group to show total amounts'}
                      {aggregation === 'mean' && 'Calculates the average value in each group to show typical values'}
                      {aggregation === 'count' && 'Counts the number of records in each group to show frequency'}
                      {aggregation === 'min' && 'Finds the smallest value in each group to show minimums'}
                      {aggregation === 'max' && 'Finds the largest value in each group to show maximums'}
                      {aggregation === 'median' && 'Finds the middle value in each group to show central tendency'}
                      {aggregation === 'std' && 'Calculates standard deviation to show data spread'}
                      {aggregation === 'var' && 'Calculates variance to show data variability'}
                    </p>
                  </motion.div>
              </div>
            </div>
        </GlassCard>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default Charts;