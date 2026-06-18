import React from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, Zap, ArrowRight, ShieldAlert, Activity } from 'lucide-react';
import { useChartTheme } from '../../../hooks/useChartTheme';

/**
 * AnomalyFeed Component
 * Surfaces automated outlier detection and statistical deviations in an executive-ready feed.
 */
const AnomalyFeed = ({ component }) => {
  const { colors } = useChartTheme();
  
  const anomalies = component.chart_data?.anomalies || component.data?.anomalies || [];

  if (anomalies.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <div className="p-4 rounded-full mb-4" style={{ background: `${colors?.success}15` }}>
          <ShieldAlert className="w-8 h-8" style={{ color: colors?.success }} />
        </div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: colors?.text }}>System Healthy</h3>
        <p className="text-xs opacity-50" style={{ color: colors?.text }}>
          No significant statistical anomalies detected in the current data slice.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-auto custom-scrollbar p-4 space-y-4">
        {anomalies.map((anomaly, idx) => {
          const isHighSeverity = anomaly.severity === 'high' || (anomaly.z_score && Math.abs(anomaly.z_score) > 4);
          const accentColor = isHighSeverity ? colors?.danger : colors?.warning;

          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="relative p-4 rounded-xl border overflow-hidden group"
              style={{ 
                background: `${accentColor}05`,
                borderColor: `${accentColor}20`
              }}
            >
              {/* Severity Sidebar */}
              <div 
                className="absolute left-0 top-0 bottom-0 w-1" 
                style={{ background: accentColor }}
              />

              <div className="flex items-start gap-4">
                <div 
                  className="p-2 rounded-lg" 
                  style={{ background: `${accentColor}15` }}
                >
                  <AlertTriangle className="w-4 h-4" style={{ color: accentColor }} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <h4 className="text-sm font-bold truncate" style={{ color: colors?.text }}>
                      {anomaly.title || 'Significant Deviation'}
                    </h4>
                    <span 
                      className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider"
                      style={{ background: `${accentColor}20`, color: accentColor }}
                    >
                      {anomaly.severity || 'Detected'}
                    </span>
                  </div>

                  <p className="text-xs leading-relaxed mb-3 opacity-80" style={{ color: colors?.text }}>
                    {anomaly.description}
                  </p>

                  <div className="flex flex-wrap gap-2">
                    {anomaly.metrics?.map((m, i) => (
                      <div 
                        key={i}
                        className="flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-mono"
                        style={{ background: colors?.cardBg, border: `1px solid ${colors?.border}` }}
                      >
                        <span className="opacity-50">{m.label}:</span>
                        <span className="font-bold" style={{ color: accentColor }}>{m.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Prompt */}
              <div className="mt-4 pt-3 border-t flex items-center justify-between" style={{ borderColor: `${accentColor}10` }}>
                <span className="text-[10px] opacity-40 italic" style={{ color: colors?.text }}>
                  Impact: {anomaly.impact || 'Operational Variance'}
                </span>
                <button 
                  className="flex items-center gap-1 text-[11px] font-semibold transition-transform group-hover:translate-x-1"
                  style={{ color: accentColor }}
                >
                  Investigate <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            </motion.div>
          );
        })}
      </div>
      
      <div className="px-4 py-3 bg-black/5 flex items-center justify-between border-t" style={{ borderColor: colors?.border }}>
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 opacity-40" style={{ color: colors?.text }} />
          <span className="text-[10px] font-medium opacity-40" style={{ color: colors?.text }}>
            Automated monitoring active
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Zap className="w-3 h-3" style={{ color: colors?.primary }} />
          <span className="text-[10px] font-bold" style={{ color: colors?.primary }}>
            AI ENRICHED
          </span>
        </div>
      </div>
    </div>
  );
};

export default AnomalyFeed;
