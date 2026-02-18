import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp, TrendingDown, Database, Users, FileText, BarChart3,
  PieChart, LineChart, Activity, DollarSign, Target, Zap,
  Lightbulb, ChevronDown, ChevronUp, Eye, EyeOff, Sparkles
} from 'lucide-react';
import PlotlyChart from './features/charts/PlotlyChart';
import EnterpriseKpiCard from './ui/EnterpriseKpiCard';

const COLORS = ['#06b6d4', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#fb923c', '#84cc16', '#ec4899'];

const DashboardComponent = ({ component, datasetData }) => {
  // Only apply grid span for non-KPI components since KPIs have their own grid
  const gridSpanStyle = component.type === 'kpi' ? {} : { gridColumn: `span ${component.span || 1}` };

  const kpiIconMap = {
    TrendingUp, TrendingDown, Database, Users, FileText, BarChart3,
    PieChart, LineChart, Activity, DollarSign, Target, Zap
  };
  const IconComponent = kpiIconMap[component.config?.icon] || Database;

  // Premium Glassmorphism Cards
  const cardStyle = "relative overflow-hidden bg-black/40 backdrop-blur-md border border-white/10 rounded-xl hover:border-ocean/30 transition-all duration-300 group";

  const formatValue = (value, aggregation) => {
    if (typeof value === 'number') {
      return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
      }).format(value);
    }
    return value?.toString() || 'N/A';
  };

  const calculateKPIValue = (config, data) => {
    // Logic handled by backend hydration now, but keeping client-side fallback just in case
    // For backend-hydrated components, component.value is already set
    if (component.value !== undefined) return component.value;
    return 0;
  };

  switch (component.type) {
    case 'kpi':
      return (
        <EnterpriseKpiCard
          title={component.title}
          value={component.value ?? 0}
          format={component.format || 'number'}
          comparisonValue={component.comparisonValue}
          comparisonLabel={component.comparisonLabel || 'vs prior half'}
          targetValue={component.targetValue}
          targetLabel={component.targetLabel}
          sparklineData={component.sparklineData || []}
          status={component.status}
          icon={component.icon || 'BarChart3'}
          animationDelay={0}
        />
      );

    case 'chart':
      // Backend now provides "chart_data" directly
      const chartData = component.chart_data || { data: [], layout: {} };
      const hasData = chartData.data && chartData.data.length > 0;
      const noveltyScore = component.config?.novelty_score;

      return (
        <motion.div
          style={gridSpanStyle}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className={cardStyle}
        >
          <div className="p-5 border-b border-white/5 flex justify-between items-start">
            <div>
              <h3 className="font-bold text-gray-100 flex items-center gap-2">
                {component.title}
                {noveltyScore > 0.6 && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" /> NOVEL
                  </span>
                )}
              </h3>
              <p className="text-xs text-gray-500 mt-1">
                {component.config?.chart_type?.toUpperCase().replace('_', ' ')}
              </p>
            </div>

            {hasData && (
              <div className="text-right">
                <div className="text-xs text-gray-500">Data Points</div>
                <div className="text-sm font-mono text-ocean">{chartData.data[0]?.x?.length || chartData.data[0]?.values?.length || 0}</div>
              </div>
            )}
          </div>

          <div className="h-[400px] w-full p-4">
            {hasData ? (
              <PlotlyChart
                data={chartData.data}
                layout={{
                  ...chartData.layout,
                  paper_bgcolor: 'rgba(0,0,0,0)',
                  plot_bgcolor: 'rgba(0,0,0,0)',
                  font: { color: '#94a3b8' },
                  autosize: true,
                  margin: { t: 20, b: 40, l: 40, r: 20 }
                }}
                config={{ responsive: true, displayModeBar: false }}
                style={{ width: '100%', height: '100%' }}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
                <div className="p-4 rounded-full bg-white/5 border border-white/10">
                  <BarChart3 className="w-8 h-8 opacity-50" />
                </div>
                <p className="text-sm">No analysis pattern found for this segment.</p>
              </div>
            )}
          </div>

        </motion.div>
      );

    case 'table':
      // Table implementation (simplified for brevity, matching card style)
      const tableData = component.table_data || [];
      const columns = tableData.length > 0 ? Object.keys(tableData[0]) : [];

      return (
        <motion.div
          style={gridSpanStyle}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className={cardStyle}
        >
          <div className="p-5 border-b border-white/5">
            <h3 className="font-bold text-gray-100">{component.title}</h3>
          </div>
          <div className="overflow-x-auto p-4">
            {tableData.length > 0 ? (
              <table className="w-full text-sm text-left text-gray-400">
                <thead className="text-xs text-gray-500 uppercase bg-white/5">
                  <tr>
                    {columns.map(col => (
                      <th key={col} className="px-4 py-3">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.map((row, i) => (
                    <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                      {columns.map(col => (
                        <td key={col} className="px-4 py-3 truncate max-w-[200px]">{String(row[col])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-center py-10 text-gray-500">No data available</div>
            )}
          </div>
        </motion.div>
      );

    default:
      return null;
  }
};

export default DashboardComponent;
