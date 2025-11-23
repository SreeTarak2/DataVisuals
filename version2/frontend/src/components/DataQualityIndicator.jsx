import React from 'react';
import { CheckCircle, AlertTriangle, XCircle, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

const getQualityColor = (score) => {
  if (score >= 0.9) return {
    bg: 'bg-emerald-500',
    text: 'text-emerald-400',
    bgLight: 'bg-emerald-500/20',
    border: 'border-emerald-500/30'
  };
  if (score >= 0.7) return {
    bg: 'bg-blue-500',
    text: 'text-blue-400',
    bgLight: 'bg-blue-500/20',
    border: 'border-blue-500/30'
  };
  if (score >= 0.5) return {
    bg: 'bg-yellow-500',
    text: 'text-yellow-400',
    bgLight: 'bg-yellow-500/20',
    border: 'border-yellow-500/30'
  };
  return {
    bg: 'bg-red-500',
    text: 'text-red-400',
    bgLight: 'bg-red-500/20',
    border: 'border-red-500/30'
  };
};

const getQualityLabel = (score) => {
  if (score >= 0.9) return 'Excellent';
  if (score >= 0.7) return 'Good';
  if (score >= 0.5) return 'Fair';
  return 'Poor';
};

const getQualityIcon = (score) => {
  if (score >= 0.9) return CheckCircle;
  if (score >= 0.7) return Sparkles;
  if (score >= 0.5) return AlertTriangle;
  return XCircle;
};

const DataQualityIndicator = ({ quality, compact = false }) => {
  if (!quality) return null;

  const {
    completeness = 100,
    quality_score = 1,
    duplicates_removed = 0,
    missing_value_ratio = 0
  } = quality;

  const colors = getQualityColor(quality_score);
  const label = getQualityLabel(quality_score);
  const Icon = getQualityIcon(quality_score);

  if (compact) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${colors.bgLight} ${colors.border} ${colors.text}`}
      >
        <Icon className="w-4 h-4" />
        <span className="text-sm font-semibold">
          {label} - {(quality_score * 100).toFixed(0)}%
        </span>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-all duration-300"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <div className={`w-8 h-8 ${colors.bgLight} rounded-lg flex items-center justify-center`}>
            <Icon className={`w-4 h-4 ${colors.text}`} />
          </div>
          Data Quality
        </h3>
        <div className={`px-3 py-1 rounded-full text-xs font-semibold border ${colors.bgLight} ${colors.border} ${colors.text}`}>
          {label}
        </div>
      </div>

      {/* Overall Score Progress */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-slate-400">Overall Score</span>
          <span className={`text-sm font-bold ${colors.text}`}>
            {(quality_score * 100).toFixed(1)}%
          </span>
        </div>
        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${quality_score * 100}%` }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className={`h-full ${colors.bg} transition-all`}
          />
        </div>
      </div>

      {/* Quality Metrics Grid */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
          <div className="text-xs text-slate-400 mb-1">Completeness</div>
          <div className="flex items-baseline gap-1">
            <span className="text-lg font-bold text-white">
              {completeness.toFixed(1)}
            </span>
            <span className="text-xs text-slate-500">%</span>
          </div>
        </div>

        <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
          <div className="text-xs text-slate-400 mb-1">Missing Values</div>
          <div className="flex items-baseline gap-1">
            <span className="text-lg font-bold text-white">
              {(missing_value_ratio * 100).toFixed(1)}
            </span>
            <span className="text-xs text-slate-500">%</span>
          </div>
        </div>

        <div className="col-span-2 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
          <div className="text-xs text-slate-400 mb-1">Duplicates Removed</div>
          <div className="flex items-baseline gap-1">
            <span className="text-lg font-bold text-white">
              {duplicates_removed.toLocaleString()}
            </span>
            <span className="text-xs text-slate-500">rows</span>
          </div>
        </div>
      </div>

      {/* Quality Tips */}
      {quality_score < 0.9 && (
        <div className="mt-4 p-3 bg-blue-900/20 border border-blue-800/30 rounded-lg">
          <p className="text-xs text-blue-300 font-medium mb-1">💡 Tip:</p>
          <p className="text-xs text-slate-400">
            {quality_score < 0.5
              ? 'Consider cleaning your data to improve quality. Check for missing values and duplicates.'
              : quality_score < 0.7
              ? 'Your data quality is fair. Consider handling missing values for better insights.'
              : 'Your data quality is good. Minor improvements could enhance analysis accuracy.'}
          </p>
        </div>
      )}
    </motion.div>
  );
};

export default DataQualityIndicator;
