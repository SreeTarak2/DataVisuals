import { motion } from 'motion/react';
import { TrendingUp, AlertCircle, Link2, Users, Info, ChevronDown, ChevronUp, Database } from 'lucide-react';
import { Insight } from '../types';
import { AreaChart, Area, ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip } from 'recharts';
import { useState } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface InsightCardProps {
  insight: Insight;
}

export function InsightCard({ insight }: InsightCardProps) {
  const [showDeepDive, setShowDeepDive] = useState(false);

  const Icon = {
    trend: TrendingUp,
    anomaly: AlertCircle,
    correlation: Link2,
    segment: Users
  }[insight.type];

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="py-12 border-b border-slate-100 last:border-0"
    >
      <div className="grid lg:grid-cols-12 gap-12">
        {/* Narrative Side */}
        <div className="lg:col-span-5 space-y-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-50 rounded-lg">
              <Icon className="w-4 h-4 text-slate-400" />
            </div>
            <span className="label-caps">{insight.type}</span>
            {insight.tags.map(tag => (
              <span key={tag} className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full font-medium">
                {tag}
              </span>
            ))}
          </div>

          <div className="space-y-4">
            <h3 className="serif text-3xl font-medium leading-tight text-brand-ink">
              {insight.title}
            </h3>
            <p className="text-slate-500 leading-relaxed font-light">
              {insight.description}
            </p>
          </div>

          {insight.value && (
            <div className="text-4xl font-light tracking-tighter text-brand-ink">
              {insight.value}
            </div>
          )}

          <button 
            onClick={() => setShowDeepDive(!showDeepDive)}
            className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-brand-accent hover:text-blue-700 transition-colors"
          >
            {showDeepDive ? 'Hide Statistical Proof' : 'View Statistical Proof'}
            {showDeepDive ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>

        {/* Visualization Side */}
        <div className="lg:col-span-7">
          {insight.data ? (
            <div className="h-64 w-full bg-slate-50/50 rounded-2xl p-6 border border-slate-100">
              <ResponsiveContainer width="100%" height="100%">
                {insight.type === 'trend' ? (
                  <AreaChart data={insight.data}>
                    <XAxis dataKey="name" hide />
                    <YAxis hide />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#fff', borderRadius: '12px', border: '1px solid #F1F5F9', fontSize: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
                    />
                    <Area 
                      type="monotone" 
                      dataKey="value" 
                      stroke="#2563EB" 
                      fill="#2563EB" 
                      fillOpacity={0.05} 
                      strokeWidth={2}
                    />
                  </AreaChart>
                ) : (
                  <ScatterChart>
                    <XAxis type="number" dataKey="x" hide />
                    <YAxis type="number" dataKey="y" hide />
                    <ZAxis type="number" range={[50, 200]} />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                    <Scatter name="Data" data={insight.data} fill="#2563EB" fillOpacity={0.6} />
                  </ScatterChart>
                )}
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 w-full flex items-center justify-center bg-slate-50 rounded-2xl border border-dashed border-slate-200">
              <div className="text-center space-y-2">
                <AlertCircle className="w-8 h-8 text-slate-300 mx-auto" />
                <p className="text-xs text-slate-400 font-medium uppercase tracking-widest">Qualitative Finding</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Statistical Deep Dive */}
      {showDeepDive && insight.analyticalContext && (
        <motion.div 
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="mt-12 analyst-panel grid md:grid-cols-4 gap-8"
        >
          <div className="space-y-2">
            <div className="label-caps !text-[9px]">Confidence Level</div>
            <div className="flex items-center gap-2">
              <span className="text-brand-ink font-bold">P = {insight.analyticalContext.pValue}</span>
              <span className="text-[10px] text-emerald-600 font-bold uppercase">Significant</span>
            </div>
          </div>
          <div className="space-y-2">
            <div className="label-caps !text-[9px]">Sample Size</div>
            <div className="text-brand-ink font-bold">N = {insight.analyticalContext.sampleSize}</div>
          </div>
          <div className="space-y-2">
            <div className="label-caps !text-[9px]">Methodology</div>
            <div className="text-slate-500 leading-tight">{insight.analyticalContext.methodology}</div>
          </div>
          <div className="space-y-2">
            <div className="label-caps !text-[9px]">Data Origin</div>
            <div className="flex items-center gap-1.5 text-slate-500">
              <Database className="w-3 h-3" />
              {insight.analyticalContext.dataOrigin}
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
