import React, { useState } from 'react';
import { Info, ChevronDown, ChevronUp, CheckCircle, Award } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const LAYER_DESCRIPTIONS = {
  statistical_rules: 'Objective rules based on data characteristics',
  domain_patterns: 'Industry-specific best practices',
  business_context: 'Audience-aware recommendations',
  visual_best_practices: 'Perceptual effectiveness (Cleveland hierarchy)',
  llm_validation: 'AI expert review',
  user_feedback: 'Learned from user preferences'
};

const LAYER_ICONS = {
  statistical_rules: '📊',
  domain_patterns: '🎯',
  business_context: '💼',
  visual_best_practices: '👁️',
  llm_validation: '🤖',
  user_feedback: '👥'
};

const ChartIntelligencePanel = ({ intelligence }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!intelligence) return null;

  const {
    confidence = 0,
    layers_applied = [],
    expert_alignment = 0,
    selection_reasoning = '',
    statistical_rules_matched = [],
    domain_patterns_matched = []
  } = intelligence;

  const getConfidenceColor = (score) => {
    if (score >= 0.9) return {
      bg: 'bg-emerald-500/20',
      border: 'border-emerald-500/30',
      text: 'text-emerald-400'
    };
    if (score >= 0.7) return {
      bg: 'bg-blue-500/20',
      border: 'border-blue-500/30',
      text: 'text-blue-400'
    };
    return {
      bg: 'bg-yellow-500/20',
      border: 'border-yellow-500/30',
      text: 'text-yellow-400'
    };
  };

  const confidenceColors = getConfidenceColor(confidence);
  const alignmentColors = getConfidenceColor(expert_alignment);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-blue-900/20 to-purple-900/20 backdrop-blur-sm border border-blue-800/50 rounded-xl p-4 hover:border-blue-700/50 transition-all duration-300"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
            <Info className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <h4 className="font-semibold text-sm text-white">AI Chart Intelligence</h4>
            <p className="text-xs text-slate-400">Why this chart was selected</p>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-semibold ${confidenceColors.bg} ${confidenceColors.border} ${confidenceColors.text} border`}>
          {(confidence * 100).toFixed(0)}% Confident
        </div>
      </div>

      {/* Selection Reasoning */}
      <p className="text-sm text-slate-300 mb-3 leading-relaxed">
        {selection_reasoning || 'Selected based on data characteristics and best practices'}
      </p>

      {/* Expert Alignment Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
          <span className="flex items-center gap-1">
            <Award className="w-3 h-3" />
            Expert Alignment
          </span>
          <span className="font-semibold text-white">{(expert_alignment * 100).toFixed(0)}%</span>
        </div>
        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${expert_alignment * 100}%` }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className={`h-full ${alignmentColors.bg.replace('/20', '')} transition-all`}
          />
        </div>
      </div>

      {/* Expandable Layers Section */}
      <div className="mt-3">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between text-xs font-medium text-slate-300 hover:text-white transition-colors py-2 px-3 rounded-lg hover:bg-slate-800/50"
        >
          <span className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-400" />
            Intelligence Layers ({layers_applied.length}/6)
          </span>
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="mt-2 space-y-2"
            >
              {layers_applied.map((layer) => (
                <motion.div
                  key={layer}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-start gap-2 p-3 bg-slate-800/30 border border-slate-700/50 rounded-lg hover:bg-slate-800/50 transition-colors"
                >
                  <span className="text-lg flex-shrink-0">{LAYER_ICONS[layer] || '✓'}</span>
                  <div className="flex-1">
                    <p className="text-xs font-medium text-white capitalize">
                      {layer.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {LAYER_DESCRIPTIONS[layer] || 'Applied to chart selection'}
                    </p>
                  </div>
                  <span className="text-green-400 flex-shrink-0">✓</span>
                </motion.div>
              ))}

              {/* Statistical Rules Matched */}
              {statistical_rules_matched && statistical_rules_matched.length > 0 && (
                <div className="mt-3 p-3 bg-blue-900/20 border border-blue-800/30 rounded-lg">
                  <p className="text-xs font-semibold text-blue-300 mb-2">Statistical Rules Matched:</p>
                  <ul className="space-y-1">
                    {statistical_rules_matched.map((rule, i) => (
                      <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                        <span className="text-blue-400 flex-shrink-0">→</span>
                        <span>{rule}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Domain Patterns Matched */}
              {domain_patterns_matched && domain_patterns_matched.length > 0 && (
                <div className="mt-2 p-3 bg-purple-900/20 border border-purple-800/30 rounded-lg">
                  <p className="text-xs font-semibold text-purple-300 mb-2">Domain Patterns Applied:</p>
                  <ul className="space-y-1">
                    {domain_patterns_matched.map((pattern, i) => (
                      <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                        <span className="text-purple-400 flex-shrink-0">→</span>
                        <span>{pattern}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

export default ChartIntelligencePanel;
