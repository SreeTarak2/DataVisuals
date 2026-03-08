import React from 'react';
import { motion } from 'framer-motion';
import { BarChart3, TrendingUp, Target, AlertCircle, Eye } from 'lucide-react';
import { cn } from '../lib/utils';

const InsightCard = ({
  insight,
  onVisualize,
  onExplore,
  index,
  isHighlighted = false
}) => {
  const getInsightIcon = (type) => {
    switch (type?.toLowerCase()) {
      case 'trend':
      case 'temporal':
        return <TrendingUp className="w-4 h-4" />;
      case 'correlation':
      case 'relationship':
        return <BarChart3 className="w-4 h-4" />;
      case 'performance':
      case 'metric':
        return <Target className="w-4 h-4" />;
      case 'anomaly':
      case 'outlier':
        return <AlertCircle className="w-4 h-4" />;
      default:
        return <Eye className="w-4 h-4" />;
    }
  };

  const getInsightColor = (type) => {
    switch (type?.toLowerCase()) {
      case 'trend':
      case 'temporal':
        return 'text-status-success bg-status-success/10 border-status-success/20';
      case 'correlation':
      case 'relationship':
        return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
      case 'performance':
      case 'metric':
        return 'text-purple-400 bg-purple-500/10 border-purple-500/20';
      case 'anomaly':
      case 'outlier':
        return 'text-status-warning bg-status-warning/10 border-status-warning/20';
      default:
        return 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20';
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className={cn(
        "group relative p-4 rounded-xl border transition-all duration-200 hover:shadow-lg",
        "bg-surface backdrop-blur-sm border-ui-border",
        isHighlighted && "ring-2 ring-primary/50 shadow-lg",
        getInsightColor(insight.type)
      )}
    >
      {/* Insight Header */}
      <div className="flex items-start gap-3 mb-3">
        <div className={cn(
          "p-2 rounded-lg border",
          getInsightColor(insight.type)
        )}>
          {getInsightIcon(insight.type)}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-text-primary text-sm leading-tight">
            {insight.title}
          </h4>
          {insight.confidence && (
            <div className="flex items-center gap-1 mt-1">
              <div className="w-2 h-2 rounded-full bg-status-success" />
              <span className="text-xs text-text-secondary">
                {insight.confidence} confidence
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Insight Description */}
      <p className="text-sm text-text-secondary leading-relaxed mb-4">
        {insight.description}
      </p>

      {/* Key Metrics */}
      {insight.metrics && insight.metrics.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {insight.metrics.map((metric, idx) => (
            <div
              key={idx}
              className="px-2 py-1 rounded-md bg-base-bg text-xs text-text-secondary border border-ui-border"
            >
              <span className="font-medium">{metric.label}:</span>{' '}
              <span className="text-text-primary font-semibold">{metric.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2">
        {onVisualize && (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onVisualize(insight)}
            className="flex-1 px-3 py-2 rounded-lg bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 border border-transparent hover:border-cyan-500/30 transition-all text-sm font-medium flex items-center justify-center gap-2"
          >
            <BarChart3 className="w-4 h-4" />
            Visualize
          </motion.button>
        )}
        {onExplore && (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onExplore(insight)}
            className="px-3 py-2 rounded-lg border border-ui-border text-text-secondary hover:text-text-primary hover:bg-base-bg transition-colors text-sm font-medium flex items-center justify-center gap-2"
          >
            <Eye className="w-4 h-4" />
            Explore
          </motion.button>
        )}
      </div>

      {/* Hover Effect */}
      <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-primary/5 to-cyan-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none" />
    </motion.div>
  );
};

export default InsightCard;
