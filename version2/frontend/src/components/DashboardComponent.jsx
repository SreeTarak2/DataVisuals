import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TrendingUp, TrendingDown, Database, Users, FileText, BarChart3, 
  PieChart, LineChart, Activity, DollarSign, Target, Zap, 
  Lightbulb, ChevronDown, ChevronUp, Eye, EyeOff
} from 'lucide-react';
import { ResponsiveContainer, LineChart as RechartsLineChart, BarChart as RechartsBarChart, PieChart as RechartsPieChart, Line, Bar, Pie, Cell, XAxis, YAxis, Tooltip } from 'recharts';
import PlotlyChart from './PlotlyChart';

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
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 0,
          maximumFractionDigits: 0
        }).format(value);
      } else if (aggregation === 'count' || aggregation === 'nunique') {
        return new Intl.NumberFormat('en-US').format(value);
      }
    }
    return value?.toString() || 'N/A';
  };

  const generateChartData = (config, data) => {
    console.log('Generating chart data:', { config, dataLength: data?.length });
    
    if (!data || !config) {
      console.log('No data or config, returning fallback');
      return generateFallbackChartData(config);
    }
    
    // Log available columns for debugging
    if (data.length > 0) {
      console.log('Available columns:', Object.keys(data[0]));
    }

    try {
      const { chart_type, columns, aggregation, group_by } = config;
      console.log('Chart config:', { chart_type, columns, aggregation, group_by });
      
      // Check if required columns exist in data
      if (data.length > 0) {
        const availableColumns = Object.keys(data[0]);
        const missingColumns = columns.filter(col => !availableColumns.includes(col));
        if (missingColumns.length > 0) {
          console.error('Missing columns:', missingColumns, 'Available:', availableColumns);
          return generateFallbackChartData(config);
        }
      }
      
      if (chart_type === 'line_chart' && columns.length >= 2) {
        // Group data by the group_by column and aggregate
        const grouped = {};
        data.forEach(row => {
          const key = row[group_by || columns[0]];
          if (!grouped[key]) grouped[key] = [];
          grouped[key].push(row[columns[1]]);
        });

        const result = Object.entries(grouped).map(([key, values]) => ({
          [group_by || columns[0]]: key,  // Use group_by column for X-axis
          [columns[1]]: aggregation === 'sum' ? values.reduce((a, b) => a + b, 0) :
                       aggregation === 'mean' ? values.reduce((a, b) => a + b, 0) / values.length :
                       values.length
        }));
        
        console.log('Generated line chart data:', result);
        return result.length > 0 ? result : generateFallbackChartData(config);
      } else if (chart_type === 'bar_chart' && columns.length >= 2) {
        // Similar logic for bar charts
        const grouped = {};
        data.forEach(row => {
          const key = row[group_by || columns[0]];
          if (!grouped[key]) grouped[key] = [];
          grouped[key].push(row[columns[1]]);
        });

        const result = Object.entries(grouped).map(([key, values]) => ({
          [group_by || columns[0]]: key,  // Use group_by column for X-axis
          [columns[1]]: aggregation === 'sum' ? values.reduce((a, b) => a + b, 0) :
                       aggregation === 'mean' ? values.reduce((a, b) => a + b, 0) / values.length :
                       values.length
        }));
        
        console.log('Generated bar chart data:', result);
        return result.length > 0 ? result : generateFallbackChartData(config);
      } else if (chart_type === 'pie_chart' && columns.length >= 2) {
        const grouped = {};
        data.forEach(row => {
          const key = row[columns[0]];
          if (!grouped[key]) grouped[key] = [];
          grouped[key].push(row[columns[1]]);
        });

        const result = Object.entries(grouped).map(([key, values]) => ({
          name: key,
          value: aggregation === 'sum' ? values.reduce((a, b) => a + b, 0) :
                 aggregation === 'mean' ? values.reduce((a, b) => a + b, 0) / values.length :
                 values.length
        }));
        
        console.log('Generated pie chart data:', result);
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
      return data.slice(0, 10).map(row => {
        const filteredRow = {};
        config.columns.forEach(col => {
          filteredRow[col] = row[col] || 'N/A';
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
      const values = data.map(row => row[config.column]).filter(val => val != null);
      
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
                          dataKey={component.config?.group_by || Object.keys(chartData[0] || {})[0]}
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
                          dataKey={component.config?.columns?.[1] || Object.keys(chartData[0] || {})[1]}
                          stroke="#3b82f6" 
                          strokeWidth={4}
                          dot={{ fill: '#3b82f6', strokeWidth: 2, r: 6 }}
                          activeDot={{ r: 8, stroke: '#3b82f6', strokeWidth: 2, fill: '#1e40af' }}
                        />
                      </RechartsLineChart>
                    ) : component.config?.chart_type === 'bar_chart' ? (
                      <RechartsBarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 40 }}>
                        <XAxis 
                          dataKey={component.config?.group_by || Object.keys(chartData[0] || {})[0]}
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
                          dataKey={component.config?.columns?.[1] || Object.keys(chartData[0] || {})[1]}
                          fill="#10b981"
                          radius={[6, 6, 0, 0]}
                          maxBarSize={60}
                        />
                      </RechartsBarChart>
                    ) : component.config?.chart_type === 'pie_chart' ? (
                      <RechartsPieChart>
                        <Pie
                          data={chartData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                          labelStyle={{ fontSize: '14px', fill: '#e2e8f0' }}
                          outerRadius={180}
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
                    ) : (
                      <div className="flex items-center justify-center h-full text-slate-400">
                        <div className="text-center">
                          <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                          <p>Unsupported chart type</p>
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
              
              {/* Insights Panel - Below chart, full width */}
              {component.insight && (
                <div className="mt-6 bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-xl p-6 border border-blue-500/20">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
                      <Lightbulb className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-white">AI Insights</h3>
                      <p className="text-xs text-slate-400">Why this chart matters for your business</p>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {component.insight.insight?.summary && (
                      <div>
                        <h4 className="text-sm font-semibold text-blue-300 mb-2">Summary</h4>
                        <p className="text-sm text-slate-300 leading-relaxed">
                          {component.insight.insight.summary}
                        </p>
                      </div>
                    )}
                    
                    {component.insight.insight?.key_findings && component.insight.insight.key_findings.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-green-300 mb-2">Key Findings</h4>
                        <ul className="space-y-2">
                          {component.insight.insight.key_findings.slice(0, 3).map((finding, index) => (
                            <li key={index} className="text-sm text-slate-300 flex items-start gap-2">
                              <span className="text-green-400 mt-1">✓</span>
                              <span>{finding}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {component.insight.insight?.recommendations && component.insight.insight.recommendations.length > 0 && (
                      <div className="md:col-span-2">
                        <h4 className="text-sm font-semibold text-amber-300 mb-2">Recommended Actions</h4>
                        <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {component.insight.insight.recommendations.slice(0, 4).map((rec, index) => (
                            <li key={index} className="text-sm text-slate-300 flex items-start gap-2 bg-amber-500/5 rounded-lg p-3 border border-amber-500/10">
                              <span className="text-amber-400 mt-0.5">→</span>
                              <span>{rec}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
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
