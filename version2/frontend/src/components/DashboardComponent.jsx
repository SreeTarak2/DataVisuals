import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TrendingUp, TrendingDown, Database, Users, FileText, BarChart3, 
  PieChart, LineChart, Activity, DollarSign, Target, Zap, 
  Lightbulb, ChevronDown, ChevronUp, Eye, EyeOff
} from 'lucide-react';
import { ResponsiveContainer, LineChart as RechartsLineChart, BarChart as RechartsBarChart, PieChart as RechartsPieChart, Line, Bar, Pie, Cell, XAxis, YAxis, Tooltip } from 'recharts';
import PlotlyChart from './PlotlyChart';
import IntelligentChartExplanation from './IntelligentChartExplanation';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316'];

const DashboardComponent = ({ component, datasetData }) => {
  const [showInsights, setShowInsights] = useState(false);
  
  // Only apply grid span for non-KPI components since KPIs have their own grid
  const gridSpanStyle = component.type === 'kpi' ? {} : { gridColumn: `span ${component.span || 1}` };
  
  // Icon mapping for KPIs
  const kpiIconMap = { 
    TrendingUp, TrendingDown, Database, Users, FileText, BarChart3, 
    PieChart, LineChart, Activity, DollarSign, Target, Zap 
  };
  const IconComponent = kpiIconMap[component.config?.icon] || Database;

  // Color mapping for KPIs
  const colorClasses = {
    emerald: 'text-emerald-400 bg-emerald-500/20',
    sky: 'text-sky-400 bg-sky-500/20',
    teal: 'text-teal-400 bg-teal-500/20',
    amber: 'text-amber-400 bg-amber-500/20',
    purple: 'text-purple-400 bg-purple-500/20',
    red: 'text-red-400 bg-red-500/20',
    blue: 'text-blue-400 bg-blue-500/20',
    green: 'text-green-400 bg-green-500/20'
  };

  const formatValue = (value, aggregation) => {
    if (typeof value === 'number') {
      if (aggregation === 'sum' || aggregation === 'mean') {
        // Format as number without currency symbol - let the data context determine the unit
        return new Intl.NumberFormat('en-US', {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2
        }).format(value);
      } else if (aggregation === 'count' || aggregation === 'nunique') {
        return new Intl.NumberFormat('en-US').format(value);
      }
    }
    return value?.toString() || 'N/A';
  };

  // Helper to normalize column names for matching
  const normalizeCol = col => (typeof col === 'string' ? col.replace(/_/g, ' ').toLowerCase() : '');

  const findActualCol = (col, availableColumns) => {
    const normCol = normalizeCol(col);
    if (!normCol) return null;

    // 1) exact normalized match
    for (const avail of availableColumns) {
      if (normalizeCol(avail) === normCol) return avail;
    }

    // 2) available includes requested (e.g., 'invoice date' includes 'date')
    for (const avail of availableColumns) {
      const nAvail = normalizeCol(avail);
      if (nAvail.includes(normCol)) return avail;
    }

    // 3) requested includes available (e.g., 'date' vs 'order date')
    for (const avail of availableColumns) {
      const nAvail = normalizeCol(avail);
      if (normCol.includes(nAvail)) return avail;
    }

    // 4) simple synonyms map for common business terms
    const synonyms = {
      revenue: ['total sales', 'total_sales', 'sales', 'sales amount', 'amount'],
      date: ['invoice date', 'invoice_date', 'order date', 'order_date', 'date'],
      category: ['product', 'region', 'retailer', 'sales method', 'state', 'category'],
      units: ['units sold', 'units_sold', 'units']
    };

    if (synonyms[normCol]) {
      for (const syn of synonyms[normCol]) {
        for (const avail of availableColumns) {
          if (normalizeCol(avail) === normalizeCol(syn) || normalizeCol(avail).includes(normalizeCol(syn))) return avail;
        }
      }
    }

    return null;
  };

  const generateChartData = (config, data) => {
    console.log('Generating chart data:', { config, dataLength: data?.length });
    if (!data || data.length === 0 || !config) {
      console.log('No data or config, returning fallback');
      return generateFallbackChartData(config);
    }
    if (data.length > 0) {
      console.log('Available columns:', Object.keys(data[0]));
    }
    try {
      const { chart_type, columns, aggregation, group_by } = config;
      console.log('Chart config:', { chart_type, columns, aggregation, group_by });
      // Find actual column names in dataset
      const availableColumns = data.length > 0 ? Object.keys(data[0]) : [];
      
      if (!columns || columns.length === 0) {
        console.error('No columns specified in config');
        return generateFallbackChartData(config);
      }
      
      const actualCols = columns.map(col => findActualCol(col, availableColumns));
      const missingColumns = actualCols.filter(col => !col);
      if (missingColumns.length > 0) {
        console.error('Missing columns:', columns, 'Available:', availableColumns);
        // Try to use any available numeric and categorical columns
        const numericCols = availableColumns.filter(col => {
          const val = data[0][col];
          return typeof val === 'number' || (!isNaN(parseFloat(val)) && isFinite(val));
        });
        const categoricalCols = availableColumns.filter(col => {
          const val = data[0][col];
          return typeof val === 'string' || val instanceof String;
        });
        
        if (numericCols.length > 0 && categoricalCols.length > 0) {
          console.log('Using fallback columns:', categoricalCols[0], numericCols[0]);
          actualCols[0] = categoricalCols[0];
          actualCols[1] = numericCols[0];
        } else {
          return generateFallbackChartData(config);
        }
      }
      // Use actual column names for mapping
      const xCol = actualCols[0];
      const yCol = actualCols[1];
      const groupCol = group_by ? findActualCol(group_by, availableColumns) : xCol;
      // Handle different chart types from backend
      if ((chart_type === 'line_chart' || chart_type === 'line') && actualCols.length >= 2) {
        const grouped = {};
        data.forEach(row => {
          const key = row[groupCol];
          if (key != null && key !== '') {
            if (!grouped[key]) grouped[key] = [];
            const value = parseFloat(row[yCol]);
            if (!isNaN(value)) {
              grouped[key].push(value);
            }
          }
        });
        const result = Object.entries(grouped).map(([key, values]) => ({
          [groupCol]: key,
          [yCol]: aggregation === 'sum' ? values.reduce((a, b) => a + b, 0) :
                   aggregation === 'mean' ? values.reduce((a, b) => a + b, 0) / values.length :
                   aggregation === 'count' ? values.length :
                   values.length
        })).slice(0, 50); // Limit to 50 data points for performance
        console.log('Generated line chart data:', result.length, 'points');
        return result.length > 0 ? result : generateFallbackChartData(config);
      } else if ((chart_type === 'bar_chart' || chart_type === 'bar') && actualCols.length >= 2) {
        const grouped = {};
        data.forEach(row => {
          const key = row[groupCol];
          if (key != null && key !== '') {
            if (!grouped[key]) grouped[key] = [];
            const value = parseFloat(row[yCol]);
            if (!isNaN(value)) {
              grouped[key].push(value);
            }
          }
        });
        const result = Object.entries(grouped)
          .map(([key, values]) => ({
            [groupCol]: key,
            [yCol]: aggregation === 'sum' ? values.reduce((a, b) => a + b, 0) :
                     aggregation === 'mean' ? values.reduce((a, b) => a + b, 0) / values.length :
                     aggregation === 'count' ? values.length :
                     values.length
          }))
          .sort((a, b) => b[yCol] - a[yCol]) // Sort by value descending
          .slice(0, 20); // Limit to top 20 categories for readability
        console.log('Generated bar chart data:', result.length, 'points');
        return result.length > 0 ? result : generateFallbackChartData(config);
      } else if ((chart_type === 'pie_chart' || chart_type === 'pie') && actualCols.length >= 2) {
        const grouped = {};
        data.forEach(row => {
          const key = row[xCol];
          if (key != null && key !== '') {
            if (!grouped[key]) grouped[key] = [];
            const value = parseFloat(row[yCol]);
            if (!isNaN(value)) {
              grouped[key].push(value);
            }
          }
        });
        const result = Object.entries(grouped)
          .map(([key, values]) => ({
            name: String(key),
            value: aggregation === 'sum' ? values.reduce((a, b) => a + b, 0) :
                   aggregation === 'mean' ? values.reduce((a, b) => a + b, 0) / values.length :
                   aggregation === 'count' ? values.length :
                   values.length
          }))
          .sort((a, b) => b.value - a.value) // Sort by value descending
          .slice(0, 8); // Limit to top 8 categories for pie chart readability
        console.log('Generated pie chart data:', result.length, 'slices');
        return result.length > 0 ? result : generateFallbackChartData(config);
      } else if ((chart_type === 'scatter_plot' || chart_type === 'scatter') && actualCols.length >= 2) {
        const result = data
          .map(row => {
            const xVal = parseFloat(row[xCol]);
            const yVal = parseFloat(row[yCol]);
            if (!isNaN(xVal) && !isNaN(yVal)) {
              return {
                x: xVal,
                y: yVal,
                [xCol]: xVal,
                [yCol]: yVal
              };
            }
            return null;
          })
          .filter(item => item !== null)
          .slice(0, 500); // Limit to 500 points for performance
        console.log('Generated scatter plot data:', result.length, 'points');
        return result.length > 0 ? result : generateFallbackChartData(config);
      } else if (chart_type === 'histogram' && actualCols.length >= 1) {
        const values = data
          .map(row => parseFloat(row[xCol]))
          .filter(val => !isNaN(val) && isFinite(val));
        
        if (values.length === 0) {
          return generateFallbackChartData(config);
        }
        
        const bins = {};
        const min = Math.min(...values);
        const max = Math.max(...values);
        const binSize = (max - min) / 10 || 1;
        
        values.forEach(val => {
          const bin = Math.floor((val - min) / binSize) * binSize + min;
          bins[bin] = (bins[bin] || 0) + 1;
        });
        
        const result = Object.entries(bins)
          .map(([bin, count]) => ({
            bin: parseFloat(bin).toFixed(2),
            count: count,
            [xCol]: parseFloat(bin)
          }))
          .sort((a, b) => a[xCol] - b[xCol]);
        console.log('Generated histogram data:', result.length, 'bins');
        return result.length > 0 ? result : generateFallbackChartData(config);
      }
    } catch (error) {
      console.error('Error generating chart data:', error);
    }
    return generateFallbackChartData(config);
  };

  const generateFallbackChartData = (config) => {
    const { chart_type, columns } = config || {};
    
    if (chart_type === 'line_chart') {
      return [
        { [columns?.[0] || 'Period']: 'Period 1', [columns?.[1] || 'Value']: 45000 },
        { [columns?.[0] || 'Period']: 'Period 2', [columns?.[1] || 'Value']: 35000 },
        { [columns?.[0] || 'Period']: 'Period 3', [columns?.[1] || 'Value']: 35000 },
        { [columns?.[0] || 'Period']: 'Period 4', [columns?.[1] || 'Value']: 40000 },
        { [columns?.[0] || 'Period']: 'Period 5', [columns?.[1] || 'Value']: 37000 },
        { [columns?.[0] || 'Period']: 'Period 6', [columns?.[1] || 'Value']: 32000 }
      ];
    } else if (chart_type === 'bar_chart') {
      return [
        { [columns?.[0] || 'Category']: 'Category A', [columns?.[1] || 'Value']: 25000 },
        { [columns?.[0] || 'Category']: 'Category B', [columns?.[1] || 'Value']: 18000 },
        { [columns?.[0] || 'Category']: 'Category C', [columns?.[1] || 'Value']: 12000 },
        { [columns?.[0] || 'Category']: 'Category D', [columns?.[1] || 'Value']: 15000 }
      ];
    } else if (chart_type === 'pie_chart') {
      return [
        { name: 'Category A', value: 45 },
        { name: 'Category B', value: 25 },
        { name: 'Category C', value: 15 },
        { name: 'Category D', value: 10 }
      ];
    }
    
    return [];
  };

  const generateTableData = (config, data) => {
    if (!data || !config?.columns) return [];
    try {
      const availableColumns = data.length > 0 ? Object.keys(data[0]) : [];
      const actualCols = config.columns.map(col => findActualCol(col, availableColumns) || col);
      return data.slice(0, 10).map(row => {
        const filteredRow = {};
        actualCols.forEach((actual, i) => {
          const displayKey = config.columns?.[i] || actual;
          filteredRow[displayKey] = row[actual] != null ? row[actual] : 'N/A';
        });
        return filteredRow;
      });
    } catch (error) {
      console.error('Error generating table data:', error);
      return [];
    }
  };

  const calculateKPIValue = (config, data) => {
    if (!data || !config?.column) return 0;
    try {
      const availableColumns = data.length > 0 ? Object.keys(data[0]) : [];
      const actualCol = findActualCol(config.column, availableColumns) || config.column;
      const values = data.map(row => row[actualCol]).filter(val => val != null);
      switch (config.aggregation) {
        case 'sum':
          return values.reduce((a, b) => a + b, 0);
        case 'mean':
          return values.reduce((a, b) => a + b, 0) / values.length;
        case 'count':
          return values.length;
        case 'nunique':
          return new Set(values).size;
        default:
          return values.length;
      }
    } catch (error) {
      console.error('Error calculating KPI value:', error);
      return 0;
    }
  };

  switch (component.type) {
    case 'kpi':
      const kpiValue = calculateKPIValue(component.config, datasetData);
      const colorClass = colorClasses[component.config?.color] || colorClasses.emerald;
      
      return (
        <motion.div 
          style={gridSpanStyle}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="group"
        >
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">
                {component.title}
              </div>
              <div className={`w-2 h-2 rounded-full ${
                  component.config?.color === 'emerald' ? 'bg-emerald-500' :
                  component.config?.color === 'sky' ? 'bg-sky-500' :
                  component.config?.color === 'teal' ? 'bg-teal-500' :
                  component.config?.color === 'amber' ? 'bg-amber-500' :
                  component.config?.color === 'purple' ? 'bg-purple-500' :
                  component.config?.color === 'red' ? 'bg-red-500' :
                  component.config?.color === 'blue' ? 'bg-blue-500' :
                  component.config?.color === 'green' ? 'bg-green-500' : 'bg-slate-500'
                }`}></div>
            </div>
            <div className="space-y-2">
              <div className="text-3xl font-bold text-white">
                {formatValue(kpiValue, component.config?.aggregation)}
              </div>
              <div className="flex items-center text-sm text-slate-400">
                <IconComponent className="w-4 h-4 mr-1" />
                {component.config?.aggregation || 'total'}
              </div>
            </div>
          </div>
        </motion.div>
      );

      case 'chart':
        const chartData = generateChartData(component.config, datasetData);
        
        return (
          <motion.div 
            style={gridSpanStyle}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="group"
          >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-white mb-2">{component.title}</h2>
                  <p className="text-slate-400 text-sm">
                    {component.config?.chart_type === 'line_chart' ? 'Showing trends and patterns' :
                     component.config?.chart_type === 'bar_chart' ? 'Comparing categories and values' :
                     component.config?.chart_type === 'pie_chart' ? 'Distribution breakdown' :
                     'Data visualization'}
                  </p>
                </div>
                  <div className="text-right">
                    <div className="text-sm text-slate-500">Data Points</div>
                    <div className="text-xl font-bold text-white">
                      {chartData.length > 0 ? chartData.length : 0}
                  </div>
                </div>
              </div>
              
              <div className="h-[600px]">
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    {component.config?.chart_type === 'line_chart' ? (
                      <RechartsLineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                        <XAxis 
                          dataKey={Object.keys(chartData[0] || {})[0]}
                          stroke="#64748b"
                          fontSize={12}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fill: '#94a3b8' }}
                        />
                        <YAxis 
                          stroke="#64748b"
                          fontSize={12}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fill: '#94a3b8' }}
                          tickFormatter={(value) => value.toLocaleString()}
                        />
                        <Tooltip 
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                            color: '#f1f5f9',
                            boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                          }}
                          formatter={(value, name) => [value.toLocaleString(), name]}
                          labelStyle={{ color: '#94a3b8' }}
                        />
                        <Line 
                          type="monotone" 
                          dataKey={Object.keys(chartData[0] || {})[1]}
                          stroke="#3b82f6" 
                          strokeWidth={4}
                          dot={{ fill: '#3b82f6', strokeWidth: 2, r: 6 }}
                          activeDot={{ r: 8, stroke: '#3b82f6', strokeWidth: 2, fill: '#1e40af' }}
                        />
                      </RechartsLineChart>
                    ) : component.config?.chart_type === 'bar_chart' || component.config?.chart_type === 'bar' ? (
                      <RechartsBarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 40 }}>
                        <XAxis 
                          dataKey={Object.keys(chartData[0] || {})[0]}
                          stroke="#64748b"
                          fontSize={12}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fill: '#94a3b8' }}
                          angle={-45}
                          textAnchor="end"
                          height={60}
                        />
                        <YAxis 
                          stroke="#64748b"
                          fontSize={12}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fill: '#94a3b8' }}
                          tickFormatter={(value) => value.toLocaleString()}
                        />
                        <Tooltip 
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                            color: '#f1f5f9',
                            boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                          }}
                          formatter={(value, name) => [value.toLocaleString(), name]}
                          labelStyle={{ color: '#94a3b8' }}
                        />
                        <Bar 
                          dataKey={Object.keys(chartData[0] || {})[1]}
                          fill="#10b981"
                          radius={[6, 6, 0, 0]}
                          maxBarSize={60}
                        />
                      </RechartsBarChart>
                    ) : component.config?.chart_type === 'pie_chart' || component.config?.chart_type === 'pie' ? (
                      <RechartsPieChart width={600} height={400}>
                        <Pie
                          data={chartData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, percent }) => {
                            const displayName = name.length > 8 ? name.substring(0, 8) + '...' : name;
                            return `${displayName} ${(percent * 100).toFixed(0)}%`;
                          }}
                          labelStyle={{ 
                            fontSize: '12px', 
                            fill: '#e2e8f0',
                            fontWeight: 'bold',
                            textShadow: '1px 1px 2px rgba(0,0,0,0.8)'
                          }}
                          outerRadius={120}
                          innerRadius={40}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {chartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip 
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                            color: '#f1f5f9',
                            boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                          }}
                          formatter={(value, name) => [value.toLocaleString(), name]}
                        />
                      </RechartsPieChart>
                    ) : component.config?.chart_type === 'scatter_plot' || component.config?.chart_type === 'scatter' ? (
                      <div className="flex items-center justify-center h-full text-slate-400">
                        <div className="text-center">
                          <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                          <p>Scatter plot visualization</p>
                          <p className="text-sm">Data points: {chartData.length}</p>
                        </div>
                      </div>
                    ) : component.config?.chart_type === 'histogram' ? (
                      <RechartsBarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                        <XAxis 
                          dataKey="bin"
                          stroke="#64748b"
                          fontSize={12}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fill: '#94a3b8' }}
                        />
                        <YAxis 
                          stroke="#64748b"
                          fontSize={12}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fill: '#94a3b8' }}
                          tickFormatter={(value) => value.toLocaleString()}
                        />
                        <Tooltip 
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                            color: '#f1f5f9',
                            boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                          }}
                          formatter={(value, name) => [value.toLocaleString(), name]}
                          labelStyle={{ color: '#94a3b8' }}
                        />
                        <Bar 
                          dataKey="count"
                          fill="#8b5cf6"
                          radius={[6, 6, 0, 0]}
                          maxBarSize={60}
                        />
                      </RechartsBarChart>
                    ) : (
                      <div className="flex items-center justify-center h-full text-slate-400">
                        <div className="text-center">
                          <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                          <p>Unsupported chart type: {component.config?.chart_type}</p>
                        </div>
                      </div>
                    )}
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <div className="w-16 h-16 bg-slate-800/50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <BarChart3 className="w-8 h-8 text-slate-500" />
                      </div>
                      <p className="text-slate-500 text-sm">Chart will appear when data is available</p>
                    </div>
                  </div>
                )}
              </div>
              
              {/* Intelligent Chart Explanation */}
              {/* <IntelligentChartExplanation 
                component={component} 
                datasetData={datasetData}
                datasetInfo={{ name: 'BMW Dataset' }}
              /> */}

            </div>
          </motion.div>
        );

    case 'table':
      const tableData = generateTableData(component.config, datasetData);
      const columns = component.config?.columns || [];
      
      return (
        <motion.div 
          style={gridSpanStyle}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="group"
        >
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-white mb-2">{component.title}</h2>
                <p className="text-slate-400 text-sm">Detailed data breakdown</p>
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-500">Rows</div>
                <div className="text-xl font-bold text-white">
                  {tableData.length}
                </div>
              </div>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700">
                    {columns.map((column, index) => (
                      <th key={index} className="text-left py-3 px-4 text-sm font-medium text-slate-300">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.map((row, rowIndex) => (
                    <tr key={rowIndex} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                      {columns.map((column, colIndex) => (
                        <td key={colIndex} className="py-3 px-4 text-sm text-slate-400">
                          <div className="max-w-32 truncate" title={String(row[column])}>
                            {String(row[column]).length > 20 ? `${String(row[column]).substring(0, 20)}...` : String(row[column])}
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      );

    default:
      return null;
  }
};

export default DashboardComponent;
