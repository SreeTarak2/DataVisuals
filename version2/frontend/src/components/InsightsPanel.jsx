import React from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp, TrendingDown, Target, Lightbulb, AlertTriangle,
  CheckCircle, BarChart3, PieChart, LineChart, Activity,
  DollarSign, Users, Zap, Brain, Search, Filter
} from 'lucide-react';

const InsightsPanel = ({ insights, prioritizedColumns, datasetInfo }) => {
  const getInsightIcon = (type) => {
    const iconMap = {
      'trend': TrendingUp,
      'performance': BarChart3,
      'distribution': PieChart,
      'correlation': LineChart,
      'anomaly': AlertTriangle,
      'recommendation': Lightbulb,
      'priority': Target,
      'quis': Brain,
      'subspace': Search
    };
    return iconMap[type] || Lightbulb;
  };

  const getInsightColor = (type) => {
    const colorMap = {
      'trend': 'text-green-400 bg-green-500/20',
      'performance': 'text-blue-400 bg-blue-500/20',
      'distribution': 'text-purple-400 bg-purple-500/20',
      'correlation': 'text-orange-400 bg-orange-500/20',
      'anomaly': 'text-red-400 bg-red-500/20',
      'recommendation': 'text-yellow-400 bg-yellow-500/20',
      'priority': 'text-emerald-400 bg-emerald-500/20',
      'quis': 'text-cyan-400 bg-cyan-500/20',
      'subspace': 'text-pink-400 bg-pink-500/20'
    };
    return colorMap[type] || 'text-slate-400 bg-slate-500/20';
  };

  return (
    <div className="space-y-6">
      {/* Dataset Overview & Prioritized Columns */}
      {prioritizedColumns && prioritizedColumns.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-xl p-6 border border-blue-500/20"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
              <Brain className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Data Intelligence Analysis</h3>
              <p className="text-xs text-slate-400">QUIS & Subspace Search Results</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-semibold text-blue-300 mb-3">Prioritized Columns</h4>
              <div className="space-y-2">
                {prioritizedColumns.slice(0, 5).map((column, index) => (
                  <div key={index} className="flex items-center justify-between bg-slate-800/50 rounded-lg p-3">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-blue-400"></div>
                      <span className="text-sm font-medium text-white">{column.name}</span>
                    </div>
                    <div className="text-xs text-slate-400">
                      Priority: {column.priority || (index + 1)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-green-300 mb-3">Key Insights</h4>
              <div className="space-y-2">
                <div className="text-sm text-slate-300">
                  <strong>Data Quality:</strong> {datasetInfo?.data_quality || 'High quality dataset with minimal missing values'}
                </div>
                <div className="text-sm text-slate-300">
                  <strong>Patterns Found:</strong> {prioritizedColumns.length} significant patterns identified
                </div>
                <div className="text-sm text-slate-300">
                  <strong>Recommendation:</strong> Focus on {prioritizedColumns[0]?.name} for primary analysis
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* AI Insights */}
      {insights && insights.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gradient-to-br from-emerald-500/10 to-teal-500/10 rounded-xl p-6 border border-emerald-500/20"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center">
              <Lightbulb className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">AI-Generated Insights</h3>
              <p className="text-xs text-slate-400">Automated analysis and recommendations</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {insights.map((insight, index) => {
              const IconComponent = getInsightIcon(insight.type);
              const colorClass = getInsightColor(insight.type);

              return (
                <div key={index} className="bg-slate-800/50 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${colorClass}`}>
                      <IconComponent className="w-4 h-4" />
                    </div>
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-white mb-1">{insight.title}</h4>
                      <p className="text-xs text-slate-400 mb-2">{insight.description}</p>
                      {insight.confidence && (
                        <div className="text-xs text-slate-500">
                          Confidence: {insight.confidence}%
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* Dashboard Usage Guide - Dynamic, not dataset-specific */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-xl p-6 border border-purple-500/20"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">How to Use This Dashboard</h3>
            <p className="text-xs text-slate-400">Getting the most from your data</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-slate-800/50 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-blue-400" />
              Understanding Your Charts
            </h4>
            <p className="text-sm text-slate-300 mb-2">
              Each visualization is automatically generated based on your data's structure:
            </p>
            <ul className="text-xs text-slate-400 space-y-1 ml-4">
              <li>• Bar charts compare values across categories</li>
              <li>• Line charts show trends over time</li>
              <li>• Pie charts display proportional distributions</li>
            </ul>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
              <PieChart className="w-4 h-4 text-green-400" />
              Interacting with Data
            </h4>
            <p className="text-sm text-slate-300 mb-2">
              Get more details by interacting with the visualizations:
            </p>
            <ul className="text-xs text-slate-400 space-y-1 ml-4">
              <li>• Hover over data points for detailed values</li>
              <li>• Use the regenerate button for alternative views</li>
              <li>• Check KPI cards for key metrics summary</li>
            </ul>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default InsightsPanel;
