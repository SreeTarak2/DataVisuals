import React from 'react';
import { Lightbulb, TrendingUp, AlertCircle, Info, Target } from 'lucide-react';
import { motion } from 'framer-motion';
import InsightFeedback from '@/components/features/feedback/InsightFeedback';

const PATTERN_ICONS = {
  trend: TrendingUp,
  comparison: AlertCircle,
  correlation: TrendingUp,
  composition: Info,
  intensity: AlertCircle,
};

const PATTERN_COLORS = {
  trend:       { bg: 'bg-[#5B88B2]/15', border: 'border-[#5B88B2]/20', text: 'text-[#5B88B2]' },
  comparison:  { bg: 'bg-[#a78bfa]/15', border: 'border-[#a78bfa]/20', text: 'text-[#a78bfa]' },
  correlation: { bg: 'bg-[#10b981]/15', border: 'border-[#10b981]/20', text: 'text-[#10b981]' },
  composition: { bg: 'bg-[#f59e0b]/15', border: 'border-[#f59e0b]/20', text: 'text-[#f59e0b]' },
  intensity:   { bg: 'bg-[#ef4444]/15', border: 'border-[#ef4444]/20', text: 'text-[#ef4444]' },
};

const ChartInsightsCard = ({ insights }) => {
  if (!insights) return null;

  const {
    summary = '',
    patterns = [],
    recommendations = [],
    enhanced_insight = null,
    confidence = 0,
  } = insights;

  const getConfidenceBadge = (score) => {
    if (score >= 0.9) return { color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20', label: 'High' };
    if (score >= 0.7) return { color: 'text-[#5B88B2] bg-[#5B88B2]/10 border-[#5B88B2]/20', label: 'Good' };
    return { color: 'text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/20', label: 'Fair' };
  };

  const confidenceBadge = getConfidenceBadge(confidence);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-midnight border border-pearl/[0.06] rounded-xl p-5 hover:border-pearl/[0.12] transition-all duration-300"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-[13px] font-semibold text-pearl flex items-center gap-2.5">
          <div className="w-8 h-8 bg-ocean/10 rounded-lg flex items-center justify-center">
            <Lightbulb className="w-4 h-4 text-ocean" />
          </div>
          AI Insights
        </h4>
        <div className={`px-2.5 py-1 rounded-full text-[10px] font-semibold border ${confidenceBadge.color}`}>
          {(confidence * 100).toFixed(0)}% {confidenceBadge.label}
        </div>
      </div>

      {/* Summary */}
      {summary && (
        <p className="text-[12px] text-granite mb-4 leading-relaxed">
          {summary}
        </p>
      )}

      {/* Enhanced Insight from LLM */}
      {enhanced_insight && (
        <div className="mb-4 p-3 bg-pearl/[0.02] border border-pearl/[0.06] rounded-lg">
          <div className="flex items-start gap-2">
            <div className="w-6 h-6 bg-ocean/10 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5">
              <Lightbulb className="w-3 h-3 text-ocean" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-pearl mb-1">Expert AI Analysis</p>
              <p className="text-[11px] text-granite leading-relaxed">{enhanced_insight}</p>
            </div>
          </div>
        </div>
      )}

      {/* Detected Patterns */}
      {patterns && patterns.length > 0 && (
        <div className="mb-4">
          <h5 className="text-[10px] font-semibold text-granite mb-2 uppercase tracking-wider">Detected Patterns</h5>
          <div className="space-y-1.5">
            {patterns.map((pattern, index) => {
              const Icon = PATTERN_ICONS[pattern.type] || Info;
              const colors = PATTERN_COLORS[pattern.type] || PATTERN_COLORS.composition;

              return (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="flex items-start gap-3 p-3 bg-pearl/[0.02] border border-pearl/[0.04] rounded-lg hover:border-pearl/[0.08] transition-colors"
                >
                  <div className={`w-7 h-7 ${colors.bg} rounded-md flex items-center justify-center flex-shrink-0`}>
                    <Icon className={`w-3.5 h-3.5 ${colors.text}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="text-[11px] font-semibold text-pearl capitalize">
                        {pattern.pattern?.replace(/_/g, ' ') || pattern.type}
                      </p>
                      {pattern.confidence !== undefined && (
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium border ${colors.bg} ${colors.border} ${colors.text}`}>
                          {(pattern.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-granite leading-relaxed">
                      {pattern.description || 'Pattern detected in data'}
                    </p>
                    {pattern.metric && (
                      <p className="text-[10px] text-granite/60 mt-0.5">
                        Metric: <span className="text-granite">{pattern.metric}</span>
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
          <h5 className="text-[10px] font-semibold text-granite mb-2 uppercase tracking-wider flex items-center gap-1.5">
            <Target className="w-3 h-3" />
            Recommendations
          </h5>
          <ul className="space-y-1">
            {recommendations.map((rec, index) => (
              <motion.li
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + index * 0.05 }}
                className="flex items-start gap-2 text-[11px] text-granite p-2 rounded-md hover:bg-pearl/[0.02] transition-colors"
              >
                <span className="text-emerald-500 flex-shrink-0 mt-0.5">→</span>
                <span className="leading-relaxed">{rec}</span>
              </motion.li>
            ))}
          </ul>
        </div>
      )}

      {/* Empty State */}
      {!summary && (!patterns || patterns.length === 0) && (!recommendations || recommendations.length === 0) && (
        <div className="text-center py-6">
          <div className="w-12 h-12 bg-pearl/[0.04] rounded-xl flex items-center justify-center mx-auto mb-3">
            <Lightbulb className="w-5 h-5 text-granite" />
          </div>
          <p className="text-[12px] text-granite">No insights available for this chart</p>
        </div>
      )}

      {/* Feedback — Train the Belief Store */}
      {(summary || enhanced_insight || (patterns && patterns.length > 0)) && (
        <div className="pt-3 mt-3 border-t border-pearl/[0.06] flex items-center justify-between">
          <span className="text-[10px] text-granite/60 uppercase tracking-wider font-medium">
            Rate these insights
          </span>
          <InsightFeedback
            variant="compact"
            insightText={summary || enhanced_insight || patterns?.[0]?.description || ''}
          />
        </div>
      )}
    </motion.div>
  );
};

export default ChartInsightsCard;
