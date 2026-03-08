import React, { useState } from 'react';
import { Info, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * ExplanationPanel Component
 * 
 * Displays AI-generated insights and explanations for charts.
 * Implements explainable AI UX patterns with:
 * - Collapsible panel
 * - Confidence score visualization
 * - Clear natural language summaries
 * 
 * Props:
 * - explanation: Natural language text explaining the chart
 * - confidence: Confidence score (0-1)
 * - patterns: Optional array of detected patterns
 * - compact: Whether to use compact mode
 */
const ExplanationPanel = ({ 
  explanation, 
  confidence = 0, 
  patterns = [],
  compact = false 
}) => {
  const [expanded, setExpanded] = useState(false);

  // Don't render if no explanation
  if (!explanation && patterns.length === 0) {
    return null;
  }

  // Calculate confidence level and color
  const getConfidenceInfo = (score) => {
    if (score >= 0.8) return { level: 'High', color: 'text-green-400', bg: 'bg-green-500/20' };
    if (score >= 0.5) return { level: 'Medium', color: 'text-yellow-400', bg: 'bg-yellow-500/20' };
    return { level: 'Low', color: 'text-orange-400', bg: 'bg-orange-500/20' };
  };

  const confidenceInfo = getConfidenceInfo(confidence);

  if (compact) {
    return (
      <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-gray-300">{explanation}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6">
      {/* Header Button */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 bg-purple-500/10 hover:bg-purple-500/20 
                   border border-purple-500/30 rounded-lg transition-all duration-200 group"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Sparkles className="w-5 h-5 text-purple-400" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-semibold text-white">AI Insights</h3>
            <p className="text-xs text-gray-400">What does this chart show?</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {confidence > 0 && (
            <span className={`text-xs px-2 py-1 rounded ${confidenceInfo.bg} ${confidenceInfo.color}`}>
              {confidenceInfo.level} Confidence
            </span>
          )}
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-gray-400 group-hover:text-purple-400 transition-colors" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400 group-hover:text-purple-400 transition-colors" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-2 p-4 bg-gray-900/50 border border-gray-700/50 rounded-lg space-y-4">
              {/* Main Explanation */}
              {explanation && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                    Summary
                  </h4>
                  <p className="text-sm text-gray-300 leading-relaxed">
                    {explanation}
                  </p>
                </div>
              )}

              {/* Detected Patterns */}
              {patterns.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                    Detected Patterns
                  </h4>
                  <ul className="space-y-2">
                    {patterns.map((pattern, index) => (
                      <li key={index} className="flex items-start gap-2 text-sm">
                        <span className="text-purple-400">•</span>
                        <span className="text-gray-300">{pattern}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Confidence Score Details */}
              {confidence > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                    Confidence Score
                  </h4>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${confidence * 100}%` }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className={`h-full ${
                          confidence >= 0.8 ? 'bg-green-500' :
                          confidence >= 0.5 ? 'bg-yellow-500' :
                          'bg-orange-500'
                        }`}
                      />
                    </div>
                    <span className={`text-sm font-semibold ${confidenceInfo.color}`}>
                      {(confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-2">
                    {confidence >= 0.8 && "High confidence - This chart type is highly suitable for your data."}
                    {confidence >= 0.5 && confidence < 0.8 && "Medium confidence - This chart works well but consider alternatives."}
                    {confidence < 0.5 && "Low confidence - You may want to explore other chart types."}
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ExplanationPanel;
