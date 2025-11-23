import React from 'react';
import { motion } from 'framer-motion';

const DOMAIN_ICONS = {
  automotive: '🚗',
  healthcare: '🏥',
  ecommerce: '🛒',
  sales: '💰',
  finance: '💵',
  hr: '👥',
  sports: '⚽',
  unknown: '❓'
};

const DOMAIN_COLORS = {
  automotive: {
    bg: 'bg-blue-500/20',
    border: 'border-blue-500/30',
    text: 'text-blue-400'
  },
  healthcare: {
    bg: 'bg-green-500/20',
    border: 'border-green-500/30',
    text: 'text-green-400'
  },
  ecommerce: {
    bg: 'bg-purple-500/20',
    border: 'border-purple-500/30',
    text: 'text-purple-400'
  },
  sales: {
    bg: 'bg-yellow-500/20',
    border: 'border-yellow-500/30',
    text: 'text-yellow-400'
  },
  finance: {
    bg: 'bg-emerald-500/20',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400'
  },
  hr: {
    bg: 'bg-pink-500/20',
    border: 'border-pink-500/30',
    text: 'text-pink-400'
  },
  sports: {
    bg: 'bg-orange-500/20',
    border: 'border-orange-500/30',
    text: 'text-orange-400'
  },
  unknown: {
    bg: 'bg-gray-500/20',
    border: 'border-gray-500/30',
    text: 'text-gray-400'
  }
};

const METHOD_LABELS = {
  'rule-based': 'Pattern Matching',
  'llm': 'AI Analysis',
  'hybrid': 'Hybrid (AI + Rules)'
};

const DomainBadge = ({ domain, confidence, method, className = '' }) => {
  if (!domain) return null;

  const icon = DOMAIN_ICONS[domain] || DOMAIN_ICONS.unknown;
  const colors = DOMAIN_COLORS[domain] || DOMAIN_COLORS.unknown;
  const methodLabel = METHOD_LABELS[method] || method;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`group relative ${className}`}
    >
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${colors.bg} ${colors.border} ${colors.text} font-medium text-sm transition-all duration-200 hover:scale-105`}>
        <span className="text-base">{icon}</span>
        <span className="capitalize">{domain}</span>
        {confidence !== undefined && (
          <span className="text-xs opacity-75 font-semibold">
            {(confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {/* Tooltip */}
      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden group-hover:block z-50">
        <motion.div
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-slate-900 border border-slate-700 rounded-lg shadow-xl p-3 min-w-[200px]"
        >
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Domain:</span>
              <span className="text-white font-semibold capitalize">{domain}</span>
            </div>
            {confidence !== undefined && (
              <div className="flex justify-between">
                <span className="text-slate-400">Confidence:</span>
                <span className="text-white font-semibold">{(confidence * 100).toFixed(1)}%</span>
              </div>
            )}
            {method && (
              <div className="flex justify-between">
                <span className="text-slate-400">Method:</span>
                <span className="text-white font-semibold">{methodLabel}</span>
              </div>
            )}
          </div>
          {/* Arrow */}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-px">
            <div className="border-4 border-transparent border-t-slate-700"></div>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};

export default DomainBadge;
