import { motion } from 'motion/react';
import { CheckCircle2, ArrowRight, ShieldCheck } from 'lucide-react';
import { Recommendation } from '../types';

interface ActionPlanProps {
  recommendations: Recommendation[];
}

export function ActionPlan({ recommendations }: ActionPlanProps) {
  return (
    <section className="py-24 bg-slate-50 border-b border-brand-border">
      <div className="report-container">
        <div className="grid lg:grid-cols-12 gap-16">
          <div className="lg:col-span-4 space-y-8">
            <div className="w-12 h-12 rounded-2xl bg-brand-accent flex items-center justify-center shadow-lg shadow-blue-200">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div className="space-y-4">
              <h2 className="serif text-4xl font-light leading-tight text-brand-ink">Strategic Action Plan</h2>
              <p className="text-slate-500 font-light leading-relaxed">
                Our analysis has identified three critical paths for immediate intervention. These recommendations are prioritized by their potential impact on Q2 retention and revenue stability.
              </p>
            </div>
          </div>
          
          <div className="lg:col-span-8 space-y-6">
            {recommendations.map((rec, index) => (
              <motion.div 
                key={rec.id}
                initial={{ opacity: 0, x: 10 }}
                whileInView={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                viewport={{ once: true }}
                className="bg-white p-8 rounded-2xl border border-slate-200 hover:border-brand-accent transition-all group shadow-sm hover:shadow-md"
              >
                <div className="flex items-start gap-6">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center mt-1">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  </div>
                  <div className="flex-grow space-y-4">
                    <div className="flex items-center gap-3">
                      <span className="label-caps text-brand-accent">{rec.category}</span>
                      <div className="w-1 h-1 rounded-full bg-slate-200" />
                      <span className={`text-[10px] uppercase font-bold ${
                        rec.impact === 'high' ? 'text-red-500' : 'text-orange-500'
                      }`}>
                        {rec.impact} Impact
                      </span>
                    </div>
                    <div className="space-y-2">
                      <p className="text-xl font-medium text-brand-ink group-hover:text-brand-accent transition-colors">
                        {rec.text}
                      </p>
                      <p className="text-sm text-slate-500 font-light leading-relaxed italic">
                        <span className="font-bold text-slate-400 not-italic mr-1">Rationale:</span>
                        {rec.rationale}
                      </p>
                    </div>
                  </div>
                  <ArrowRight className="w-5 h-5 text-slate-300 group-hover:text-brand-accent transition-all group-hover:translate-x-1" />
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
