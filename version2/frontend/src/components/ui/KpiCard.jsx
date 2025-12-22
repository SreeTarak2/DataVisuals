import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '../../lib/utils';
import GlassCard from '../common/GlassCard';
import PlotlyChart from '../PlotlyChart';

const KpiCard = ({ title, value, change, trendData = [], color = 'primary' }) => {
  const isPositive = change >= 0;
  const TrendIcon = isPositive ? TrendingUp : TrendingDown;

  const getChangeColor = () => (isPositive ? 'text-green-400' : 'text-red-400');
  const getTrendStroke = () => (isPositive ? '#22c55e' : '#ef4444'); // Tailwind green/red hex

  return (
    <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="w-full">
      <GlassCard className="p-5 md:p-6 bg-slate-900/90 dark:bg-slate-950/90 border-slate-700/50" elevated hover>
        {/* Content */}
        <div className="relative z-10">
          <h3 className="text-sm font-medium text-slate-300 mb-1 truncate">{title}</h3>
          <p className="text-2xl md:text-3xl font-bold text-white mb-3">{value}</p>

          {/* Change Indicator */}
          <div className="flex items-center gap-1 mb-3">
            <TrendIcon className={cn('w-4 h-4', getChangeColor())} />
            <span className={cn('text-sm font-semibold', getChangeColor())}>
              {isPositive ? '+' : ''}{change}%
            </span>
            <span className="text-xs text-slate-400">from last period</span>
          </div>

          {/* Sparkline */}
          {trendData.length > 0 && (
            <div className="hidden md:block h-12 bg-[#0d1117] rounded-lg">
              <PlotlyChart
                data={[{
                  x: trendData.map((_, i) => i),
                  y: trendData.map(d => d.y),
                  type: 'scatter',
                  mode: 'lines',
                  line: {
                    color: getTrendStroke(),
                    width: 2,
                    shape: 'spline'
                  }
                }]}
                layout={{
                  margin: { l: 0, r: 0, t: 0, b: 0 },
                  showlegend: false,
                  xaxis: { visible: false },
                  yaxis: { visible: false }
                }}
                config={{
                  displayModeBar: false,
                  staticPlot: true
                }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          )}
        </div>
      </GlassCard>
    </motion.div>
  );
};

export default KpiCard;
