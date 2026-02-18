import React from 'react';
import { Lightbulb, TrendingUp, AlertCircle, Info, Target } from 'lucide-react';
import { motion } from 'framer-motion';

const PATTERN_ICONS = {
  trend: TrendingUp,
  comparison: AlertCircle,
  correlation: TrendingUp,
  composition: Info,
  intensity: AlertCircle
};

const PATTERN_COLORS = {
  trend: { bg: 'bg-blue-500/20', border: 'border-blue-500/30', text: 'text-blue-400' },
  comparison: { bg: 'bg-purple-500/20', border: 'border-purple-500/30', text: 'text-purple-400' },
  correlation: { bg: 'bg-green-500/20', border: 'border-green-500/30', text: 'text-green-400' },
  composition: { bg: 'bg-yellow-500/20', border: 'border-yellow-500/30', text: 'text-yellow-400' },
  intensity: { bg: 'bg-red-500/20', border: 'border-red-500/30', text: 'text-red-400' }
};

const ChartInsightsCard = ({ insights }) => {
  if (!insights) return null;

  const {
    summary = '',
    patterns = [],
    recommendations = [],
    enhanced_insight = null,
    confidence = 0
  } = insights;

  const getConfidenceBadge = (score) => {
    if (score >= 0.9) return { color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30', label: 'High' };
    if (score >= 0.7) return { color: 'text-blue-400 bg-blue-500/20 border-blue-500/30', label: 'Good' };
    return { color: 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30', label: 'Fair' };
  };

  const confidenceBadge = getConfidenceBadge(confidence);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-purple-900/20 to-pink-900/20 backdrop-blur-sm border border-purple-800/50 rounded-xl p-5 hover:border-purple-700/50 transition-all duration-300"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h4 className="font-semibold text-sm text-white flex items-center gap-2">
          <div className="w-8 h-8 bg-yellow-500/20 rounded-lg flex items-center justify-center">
            <Lightbulb className="w-4 h-4 text-yellow-400" />
          </div>
          AI Insights
        </h4>
        <div className={`px-3 py-1 rounded-full text-xs font-semibold border ${confidenceBadge.color}`}>
          {(confidence * 100).toFixed(0)}% {confidenceBadge.label}
        </div>
      </div>

      {/* Summary */}
      {summary && (
        <p className="text-sm text-slate-300 mb-4 leading-relaxed">
          {summary}
        </p>
      )}

      {/* Enhanced Insight from LLM */}
      {enhanced_insight && (
        <div className="mb-4 p-3 bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-700/30 rounded-lg">
          <div className="flex items-start gap-2">
            <div className="w-6 h-6 bg-purple-500/20 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
              <Lightbulb className="w-3 h-3 text-purple-400" />
            </div>
            <div>
              <p className="text-xs font-semibold text-purple-300 mb-1">Expert AI Analysis:</p>
              <p className="text-xs text-slate-300 leading-relaxed">{enhanced_insight}</p>
            </div>
          </div>
        </div>
      )}

      {/* Detected Patterns */}
      {patterns && patterns.length > 0 && (
        <div className="mb-4">
          <h5 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">Detected Patterns:</h5>
          <div className="space-y-2">
            {patterns.map((pattern, index) => {
              const Icon = PATTERN_ICONS[pattern.type] || Info;
              const colors = PATTERN_COLORS[pattern.type] || PATTERN_COLORS.composition;
              
              return (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="flex items-start gap-3 p-3 bg-slate-800/30 border border-slate-700/50 rounded-lg hover:bg-slate-800/50 transition-colors"
                >
                  <div className={`w-8 h-8 ${colors.bg} rounded-lg flex items-center justify-center flex-shrink-0`}>
                    <Icon className={`w-4 h-4 ${colors.text}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-xs font-semibold text-white capitalize">
                        {pattern.pattern?.replace(/_/g, ' ') || pattern.type}
                      </p>
                      {pattern.confidence !== undefined && (
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${colors.bg} ${colors.border} ${colors.text}`}>
                          {(pattern.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {pattern.description || 'Pattern detected in data'}
                    </p>
                    {pattern.metric && (
                      <p className="text-xs text-slate-500 mt-1">
                        Metric: <span className="text-slate-400">{pattern.metric}</span>
                      </p>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {recommendations && recommendations.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide flex items-center gap-2">
            <Target className="w-3 h-3" />
            Recommendations:
          </h5>
          <ul className="space-y-2">
            {recommendations.map((rec, index) => (
              <motion.li
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + index * 0.05 }}
                className="flex items-start gap-2 text-xs text-slate-300 p-2 rounded-lg hover:bg-slate-800/30 transition-colors"
              >
                <span className="text-green-400 flex-shrink-0 mt-0.5">→</span>
                <span className="leading-relaxed">{rec}</span>
              </motion.li>
            ))}
          </ul>
        </div>
      )}

      {/* Empty State */}
      {!summary && (!patterns || patterns.length === 0) && (!recommendations || recommendations.length === 0) && (
        <div className="text-center py-6 text-slate-400">
          <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center mx-auto mb-3">
            <Lightbulb className="w-6 h-6 opacity-50" />
          </div>
          <p className="text-sm">No insights available for this chart</p>
        </div>
      )}
    </motion.div>
  );
};

export default ChartInsightsCard;
