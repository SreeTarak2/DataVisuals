import React from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  Database, 
  RefreshCw, 
  ShieldCheck,
  Activity
} from 'lucide-react';
import { motion } from 'framer-motion';

// --- Sub-Component: Circular Progress Ring ---
const CircularProgress = ({ score, label, subLabel, color, icon: Icon }) => {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score * circumference);

  return (
    <div className="flex items-center gap-4">
      {/* Ring Chart */}
      <div className="relative w-16 h-16 flex-shrink-0">
        {/* Background Ring */}
        <svg className="w-full h-full -rotate-90" viewBox="0 0 70 70">
          <circle
            cx="35"
            cy="35"
            r={radius}
            stroke="currentColor"
            strokeWidth="6"
            fill="transparent"
            className="text-slate-800"
          />
          {/* Progress Ring */}
          <motion.circle
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1, ease: "easeOut" }}
            cx="35"
            cy="35"
            r={radius}
            stroke="currentColor"
            strokeWidth="6"
            fill="transparent"
            strokeDasharray={circumference}
            strokeLinecap="round"
            className={color}
          />
        </svg>
        {/* Center Text */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold text-white">{(score * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Label Text */}
      <div className="flex flex-col">
        <span className="text-sm font-medium text-slate-200">{label}</span>
        <div className="flex items-center gap-1.5">
          <span className={`text-xs ${color.replace('text-', 'bg-')}/10 px-1.5 py-0.5 rounded text-slate-400`}>
            {subLabel}
          </span>
          {score < 0.8 && <AlertTriangle className="w-3 h-3 text-amber-500" />}
          {score >= 0.8 && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
        </div>
      </div>
    </div>
  );
};

const DataQualityIndicator = ({ data = {} }) => {
  // Default values based on "Foundational KPIs" 
  const {
    overall_score = 0.86,
    completeness = 0.90, // % of required fields present [cite: 9]
    accuracy = 0.78,     // % of values passing format rules [cite: 11]
    consistency = 0.69,  // Cross-system agreement [cite: 13]
    timeliness = 0.74,   // Data currency/lag [cite: 16]
    freshness = 'High',  // Operational insight
    last_updated = '21m ago',
    total_records = '5.6 M'
  } = data;

  const getStatusColor = (score) => {
    if (score >= 0.9) return 'text-emerald-400';
    if (score >= 0.7) return 'text-cyan-400'; // Matching the reference image blue/cyan
    if (score >= 0.5) return 'text-amber-400';
    return 'text-rose-400';
  };

  const getOverallLabel = (score) => {
    if (score >= 0.9) return 'EXCELLENT';
    if (score >= 0.8) return 'GOOD';
    if (score >= 0.6) return 'FAIR';
    return 'POOR';
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-md w-full bg-[#1e232f] border border-slate-800/60 rounded-3xl p-6 shadow-2xl relative overflow-hidden font-sans"
    >
      {/* Background Glow Effect */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/5 rounded-full blur-3xl -z-0 pointer-events-none" />

      {/* Header */}
      <div className="flex justify-between items-start mb-6 z-10 relative">
        <div>
          <h2 className="text-slate-400 text-xs font-bold tracking-wider uppercase mb-1">Customer Data Health</h2>
          <div className="flex items-baseline gap-3">
            <span className="text-5xl font-light text-white tracking-tight">
              {(overall_score * 100).toFixed(0)}
            </span>
            <div className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase bg-cyan-500 text-slate-900`}>
              {getOverallLabel(overall_score)}
            </div>
          </div>
        </div>
        
        {/* Main Hero Circle (Overall) */}
        <div className="relative w-16 h-16">
           <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
            <path
              className="text-slate-800"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              stroke="currentColor"
              strokeWidth="4"
            />
            <motion.path
              initial={{ pathLength: 0 }}
              animate={{ pathLength: overall_score }}
              transition={{ duration: 1.5, ease: "easeOut" }}
              className="text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.5)]"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              stroke="currentColor"
              strokeWidth="4"
              strokeDasharray="100, 100"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
             <ShieldCheck className="w-6 h-6 text-slate-500" />
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-y-6 gap-x-4 mb-8 z-10 relative">
        <CircularProgress 
          score={completeness} 
          label="Completeness" 
          subLabel="Null checks"
          color="text-cyan-400" // Matching reference Cyan
        />
        <CircularProgress 
          score={accuracy} 
          label="Accuracy" 
          subLabel="Valid format"
          color="text-amber-400" // Matching reference Yellow/Gold
        />
        <CircularProgress 
          score={consistency} 
          label="Consistency" 
          subLabel="Duplicates"
          color="text-cyan-400" 
        />
        <CircularProgress 
          score={timeliness} 
          label="Timeliness" 
          subLabel="SLA check"
          color="text-amber-400" 
        />
      </div>

      {/* Footer: Freshness & Meta */}
      <div className="border-t border-slate-800/80 pt-5 z-10 relative">
        <div className="flex justify-between items-end mb-2">
          <div className="flex items-center gap-2 text-slate-300 text-sm font-medium">
             <Activity className="w-4 h-4 text-cyan-400" />
             Data Freshness
          </div>
          <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider">{freshness}</span>
        </div>
        
        {/* Freshness Bar */}
        <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden mb-4">
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: '85%' }}
            className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 rounded-full"
          />
        </div>

        <div className="flex justify-between items-center text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            <span>Updated: {last_updated}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5" />
            <span>{total_records} Records</span>
          </div>
        </div>
      </div>

    </motion.div>
  );
};

export default DataQualityIndicator;