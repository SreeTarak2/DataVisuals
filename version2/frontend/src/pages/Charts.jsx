import React, { useState, useEffect } from 'react';
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
      // Default layout without grid lines
      const defaultLayout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {
          color: '#e2e8f0',
          family: 'Inter, system-ui, sans-serif'
        },
        xaxis: {
          color: '#64748b',
          showgrid: false, // Remove grid lines
          zeroline: false,
          showline: true,
          linecolor: '#374151',
          linewidth: 1
        },
        yaxis: {
          color: '#64748b',
          showgrid: false, // Remove grid lines
          zeroline: false,
          showline: true,
          linecolor: '#374151',
          linewidth: 1
        },
        margin: {
          l: 60,
          r: 30,
          t: 30,
          b: 60
        },
        showlegend: true,
        legend: {
          x: 1,
          y: 1,
          bgcolor: 'rgba(0,0,0,0)',
          bordercolor: 'rgba(0,0,0,0)',
          font: {
            color: '#e2e8f0'
          }
        }
      };

      // Merge with provided layout
      const finalLayout = { ...defaultLayout, ...layout };

      Plotly.newPlot(plotRef.current, data, finalLayout, {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
        displaylogo: false,
        ...config
      });
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

    // Convert chart data to Plotly format
    const getPlotlyData = () => {
    switch (chartType) {
      case 'bar':
          return [{
            x: chartData.map(item => item[xKey]),
            y: chartData.map(item => item[yKey]),
            type: 'bar',
            marker: {
              color: '#3b82f6',
              line: {
                color: '#1d4ed8',
                width: 1
              }
            },
            name: yAxis
          }];

      case 'line':
          return [{
            x: chartData.map(item => item[xKey]),
            y: chartData.map(item => item[yKey]),
            type: 'scatter',
            mode: 'lines+markers',
            line: {
              color: '#10b981',
              width: 3
            },
            marker: {
              color: '#3b82f6',
              size: 6
            },
            name: yAxis
          }];

      case 'pie':
        const filteredData = chartData.filter(item => item.value > 0);
          return [{
            labels: filteredData.map(item => item.name),
            values: filteredData.map(item => item.value),
            type: 'pie',
            marker: {
              colors: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316']
            },
            textinfo: 'label+percent',
            textposition: 'outside'
          }];

      case 'scatter':
          return [{
            x: chartData.map(item => item[xKey]),
            y: chartData.map(item => item[yKey]),
            type: 'scatter',
            mode: 'markers',
            marker: {
              color: '#3b82f6',
              size: 8,
              opacity: 0.7
            },
            name: yAxis
          }];

      case 'area':
          return [{
            x: chartData.map(item => item[xKey]),
            y: chartData.map(item => item[yKey]),
            type: 'scatter',
            mode: 'lines',
            fill: 'tonexty',
            line: {
              color: '#10b981',
              width: 2
            },
            fillcolor: 'rgba(16, 185, 129, 0.3)',
            name: yAxis
          }];

      case 'radar':
          return [{
            r: chartData.map(item => item[yKey]),
            theta: chartData.map(item => item[xKey]),
            type: 'scatterpolar',
            fill: 'toself',
            line: {
              color: '#3b82f6'
            },
            fillcolor: 'rgba(59, 130, 246, 0.3)',
            name: yAxis
          }];

      case 'histogram':
          return [{
            x: chartData.map(item => item[xKey]),
            type: 'histogram',
            marker: {
              color: '#3b82f6',
              line: {
                color: '#1d4ed8',
                width: 1
              }
            },
            name: xAxis
          }];

      case 'boxplot':
          return [{
            y: chartData.map(item => item[yKey]),
            type: 'box',
            marker: {
              color: '#3b82f6'
            },
            name: yAxis
          }];

      case 'heatmap':
          // For heatmap, we need to restructure the data
          const heatmapData = chartData[0];
          if (heatmapData && heatmapData.x && heatmapData.y && heatmapData.z) {
            return [{
              x: heatmapData.x,
              y: heatmapData.y,
              z: heatmapData.z,
              type: 'heatmap',
              colorscale: 'Viridis'
            }];
          }
          return [];

      case 'bubble':
          const bubbleData = chartData[0];
          if (bubbleData && bubbleData.x && bubbleData.y && bubbleData.marker) {
            return [{
              x: bubbleData.x,
              y: bubbleData.y,
              mode: 'markers',
              marker: {
                size: bubbleData.marker.size,
                    color: '#3b82f6',
                opacity: 0.7
              },
              type: 'scatter',
              name: yAxis
            }];
          }
          return [];

        default:
          return [{
            x: chartData.map(item => item[xKey]),
            y: chartData.map(item => item[yKey]),
            type: 'bar',
                  marker: {
              color: '#3b82f6'
            },
            name: yAxis
          }];
      }
    };

    const getPlotlyLayout = () => {
      const baseLayout = {
                  title: {
                    text: chartTitle,
          font: {
            color: '#e2e8f0',
            size: 20
          },
          x: 0.5
                  },
                  xaxis: {
          title: xAxis,
          color: '#64748b',
          showgrid: false,
          zeroline: false,
          showline: true,
          linecolor: '#374151',
          linewidth: 1
                  },
                  yaxis: {
          title: yAxis,
          color: '#64748b',
          showgrid: false,
          zeroline: false,
          showline: true,
          linecolor: '#374151',
          linewidth: 1
        },
        margin: {
          l: 60,
          r: 30,
          t: 60,
          b: 60
        }
      };

      // Chart-specific layout adjustments
      if (chartType === 'pie') {
        baseLayout.showlegend = true;
        baseLayout.legend = {
          x: 1,
          y: 1,
          bgcolor: 'rgba(0,0,0,0)',
          bordercolor: 'rgba(0,0,0,0)',
          font: { color: '#e2e8f0' }
        };
      }

      return baseLayout;
    };

        return (
          <div>
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
            <div className="h-[600px]">
              <PlotlyChart 
            data={getPlotlyData()}
            layout={getPlotlyLayout()}
                config={{
              responsive: true,
                  displayModeBar: true,
                  modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
              displaylogo: false
                }}
              />
            </div>
          </div>
        );
  };

  // Load dataset columns on component mount
  useEffect(() => {
    if (selectedDataset) {
      loadDatasetColumns();
    }
  }, [selectedDataset]);

  // Generate chart data when dependencies change
  useEffect(() => {
    if (selectedDataset && xAxis && yAxis) {
      generateChartData();
    }
  }, [selectedDataset, chartType, xAxis, yAxis, aggregation]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="space-y-8"
        >
          {/* Header */}
          <div className="text-center space-y-4">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="text-4xl font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent"
            >
              Chart Studio
            </motion.h1>
            <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-slate-400 text-lg max-w-2xl mx-auto"
            >
              Create beautiful, interactive visualizations from your data with our advanced charting tools
            </motion.p>
          </div>

          {/* Main Content */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Chart Preview */}
        <div className="lg:col-span-2">
              <GlassCard className="p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <BarChart3 className="w-5 h-5 text-white" />
              </div>
                  <div>
                    <h2 className="text-xl font-semibold text-white">Chart Preview</h2>
                    <div className="flex items-center gap-2 text-sm text-slate-400">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                      <span>Live Preview</span>
                      <span>•</span>
                      <span>{chartData ? chartData.length : 0} data points</span>
            </div>
                </div>
              </div>
              
                {loading ? (
                  <div className="h-[600px] flex items-center justify-center">
                    <div className="text-center space-y-4">
                      <Loader2 className="w-8 h-8 text-blue-400 animate-spin mx-auto" />
                      <p className="text-slate-400">Generating chart...</p>
              </div>
                </div>
                ) : (
                  renderChart()
                )}
          </GlassCard>
        </div>

            {/* Configuration Panel */}
        <div className="space-y-6">
              {/* Chart Type Selection */}
              <GlassCard className="p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                    <BarChart3 className="w-4 h-4 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Chart Type</h3>
                    <p className="text-sm text-slate-400">Choose your visualization</p>
                </div>
                  <div className="ml-auto text-xs text-slate-500">
                  {currentPage + 1} of {totalPages}
                </div>
            </div>
            
                {/* Chart Type Grid */}
                <div className="space-y-4">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentPage}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.3 }}
                      className="grid grid-cols-4 gap-3"
                >
                      {getCurrentPageChartTypes().map((type) => (
                <motion.button
            key={type.id}
                        whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
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

              {/* Data Mapping */}
              <GlassCard className="p-6">
              <div className="flex items-center gap-3 mb-6">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-green-500 to-teal-600 flex items-center justify-center">
                    <Settings className="w-4 h-4 text-white" />
                </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Data Mapping</h3>
                    <p className="text-sm text-slate-400">Configure your data axes</p>
                  </div>
              </div>
              
              <div className="space-y-6">
                {/* X Axis Selection */}
                  <div className="space-y-3">
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                    <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                    X Axis
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
                  <div className="space-y-3">
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                    <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                    Y Axis
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
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default Charts;
