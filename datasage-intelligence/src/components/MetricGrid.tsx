import { motion } from 'motion/react';
import { KPI } from '../types';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';

interface MetricGridProps {
  kpis: KPI[];
}

export function MetricGrid({ kpis }: MetricGridProps) {
  return (
    <section className="py-16 bg-white border-b border-brand-border">
      <div className="report-container">
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-12">
          {kpis.map((kpi, i) => (
            <motion.div 
              key={kpi.label}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              viewport={{ once: true }}
              className="space-y-4"
            >
              <div className="flex items-center justify-between">
                <span className="label-caps">{kpi.label}</span>
                <div className={`flex items-center gap-1 text-[10px] font-bold ${
                  kpi.trend === 'up' ? 'text-emerald-600' : kpi.trend === 'down' ? 'text-red-600' : 'text-slate-400'
                }`}>
                  {kpi.trend === 'up' ? <TrendingUp className="w-3 h-3" /> : kpi.trend === 'down' ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                  {kpi.change > 0 ? '+' : ''}{kpi.change}%
                </div>
              </div>
              
              <div className="flex items-end justify-between gap-4">
                <div className="text-4xl font-light tracking-tight text-brand-ink">
                  {kpi.value}
                </div>
                <div className="h-10 w-24 flex-shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={kpi.sparkline}>
                      <Area 
                        type="monotone" 
                        dataKey="y" 
                        stroke={kpi.trend === 'up' ? '#10b981' : kpi.trend === 'down' ? '#ef4444' : '#94a3b8'} 
                        fill={kpi.trend === 'up' ? '#10b981' : kpi.trend === 'down' ? '#ef4444' : '#94a3b8'} 
                        fillOpacity={0.1} 
                        strokeWidth={1.5}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
              
              <p className="text-[11px] text-slate-400 leading-relaxed font-light">
                {kpi.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
