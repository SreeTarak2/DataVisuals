import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp, TrendingDown, Database, Users, FileText, BarChart3,
  PieChart, LineChart, Activity, DollarSign, Target, Zap,
  Lightbulb, ChevronDown, ChevronUp, Eye, EyeOff
} from 'lucide-react';
import PlotlyChart from './PlotlyChart';
import IntelligentChartExplanation from './IntelligentChartExplanation';
import EnterpriseKpiCard from './ui/EnterpriseKpiCard';
import { hydrateEnterpriseKpiComponent } from '../pages/Dashboard/utils/kpiCalculations';

const COLORS = ['#06b6d4', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#fb923c', '#84cc16', '#ec4899'];

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
    console.log('============ CHART DATA GENERATION DEBUG ============');
    console.log('Config received:', JSON.stringify(config, null, 2));
    console.log('Data length:', data?.length);
    console.log('Data is array?', Array.isArray(data));

    if (!data || data.length === 0 || !config) {
      console.log('❌ No data or config, returning fallback');
      console.log('data?', !!data, 'data.length?', data?.length, 'config?', !!config);
      return generateFallbackChartData(config);
    }
    if (data.length > 0) {
      console.log('✅ Available columns in data:', Object.keys(data[0]));
      console.log('First data row sample:', data[0]);
    }
    try {
      // The chart type can be in either 'type' or 'chart_type' field
      const chart_type = config.type || config.chart_type;
      const { columns, aggregation, group_by } = config;
      console.log('📊 Chart config:', { chart_type, columns, aggregation, group_by });
      // Find actual column names in dataset
      const availableColumns = data.length > 0 ? Object.keys(data[0]) : [];

      if (!columns || columns.length === 0) {
        console.error('❌ No columns specified in config');
        return generateFallbackChartData(config);
      }

      console.log('🔍 Looking for columns:', columns);
      console.log('📋 Available columns:', availableColumns);

      // Filter out null/undefined columns before matching (pie charts only need one column)
      const validColumns = columns.filter(col => col != null && col !== '');
      console.log('🔍 Valid columns (after filtering nulls):', validColumns);

      const actualCols = validColumns.map(col => findActualCol(col, availableColumns));
      console.log('✅ Matched columns:', actualCols);

      const missingColumns = actualCols.filter(col => !col);
      if (missingColumns.length > 0) {
        console.error('❌ Missing columns after matching!');
        console.error('   Requested:', columns);
        console.error('   Available:', availableColumns);
        console.error('   Matched:', actualCols);

        // Try to use any available numeric and categorical columns
        const numericCols = availableColumns.filter(col => {
          const val = data[0][col];
          return typeof val === 'number' || (!isNaN(parseFloat(val)) && isFinite(val));
        });
        const categoricalCols = availableColumns.filter(col => {
          const val = data[0][col];
          return typeof val === 'string' || val instanceof String;
        });

        console.log('   Numeric columns available:', numericCols);
        console.log('   Categorical columns available:', categoricalCols);

        if (numericCols.length > 0 && categoricalCols.length > 0) {
          console.log('✅ Using fallback columns:', categoricalCols[0], numericCols[0]);
          actualCols[0] = categoricalCols[0];
          actualCols[1] = numericCols[0];
        } else {
          console.error('❌ Cannot find suitable fallback columns, using fallback data');
          return generateFallbackChartData(config);
        }
      }
      // Use actual column names for mapping
      const xCol = actualCols[0];
      const yCol = actualCols[1]; // May be undefined for single-column charts like pie
      const groupCol = group_by ? findActualCol(group_by, availableColumns) : xCol;

      console.log('📍 Using columns - X:', xCol, 'Y:', yCol, 'Group:', groupCol);

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
        console.log('✅ Generated line chart data:', result.length, 'points');
        console.log('   Sample point:', result[0]);
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
        console.log('✅ Generated bar chart data:', result.length, 'points');
        console.log('   Sample point:', result[0]);
        return result.length > 0 ? result : generateFallbackChartData(config);
      } else if ((chart_type === 'pie_chart' || chart_type === 'pie') && actualCols.length >= 1) {
        const grouped = {};

        // Pie charts can work with just one column (count occurrences) or two columns (aggregate values)
        if (!yCol || yCol === xCol) {
          // Single column: count occurrences of each unique value
          console.log('📊 Pie chart: counting occurrences of', xCol);
          data.forEach(row => {
            const key = row[xCol];
            if (key != null && key !== '') {
              grouped[key] = (grouped[key] || 0) + 1;
            }
          });
          const result = Object.entries(grouped)
            .map(([key, count]) => ({
              name: String(key),
              value: count
            }))
            .sort((a, b) => b.value - a.value)
            .slice(0, 8);
          console.log('✅ Generated pie chart data (count):', result.length, 'slices');
          console.log('   Sample slice:', result[0]);
          return result.length > 0 ? result : generateFallbackChartData(config);
        } else {
          // Two columns: aggregate numeric values by category
          console.log('📊 Pie chart: aggregating', yCol, 'by', xCol);
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
            .sort((a, b) => b.value - a.value)
            .slice(0, 8);
          console.log('✅ Generated pie chart data (aggregate):', result.length, 'slices');
          console.log('   Sample slice:', result[0]);
          return result.length > 0 ? result : generateFallbackChartData(config);
        }
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

  // No fallback data - return empty array to show proper empty states
  // Previously returned fake placeholder data which was misleading
  const generateFallbackChartData = (config) => {
    // Return empty array - the chart component will show an empty state
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
      // Hydrate with enterprise data (comparisons, goals, sparklines)
      // Use real data only - no mock comparison or target values
      const enterpriseKpiData = hydrateEnterpriseKpiComponent(component, datasetData, {
        enableMockComparison: false,
        enableMockTarget: false
      });

      return (
        <EnterpriseKpiCard
          title={component.title}
          value={enterpriseKpiData.value}
          format={enterpriseKpiData.format}
          comparisonValue={enterpriseKpiData.comparisonValue}
          comparisonLabel={enterpriseKpiData.comparisonLabel}
          targetValue={enterpriseKpiData.targetValue}
          targetLabel={enterpriseKpiData.targetLabel}
          sparklineData={enterpriseKpiData.sparklineData}
          icon={enterpriseKpiData.icon}
          animationDelay={0}
        />
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

            <div className="h-[600px] bg-[#0d1117] rounded-xl p-4">
              {chartData.length > 0 ? (
                <PlotlyChart
                  data={chartData}
                  chartType={component.config?.chart_type}
                  config={{
                    columns: component.config?.columns || Object.keys(chartData[0] || {})
                  }}
                  style={{ width: '100%', height: '100%' }}
                />
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
