import { motion } from 'motion/react';
import { FileText, Calendar, ShieldCheck, Share2, Download } from 'lucide-react';

interface ReportHeaderProps {
  datasetName: string;
  reportId: string;
  headline: string;
  summary: string;
  qualityScore: number;
}

export function ReportHeader({ datasetName, reportId, headline, summary, qualityScore }: ReportHeaderProps) {
  return (
    <header className="pt-24 pb-16 border-b border-brand-border bg-white">
      <div className="report-container">
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-12"
        >
          {/* Metadata Row */}
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-brand-muted" />
                <span className="label-caps">{reportId}</span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-brand-muted" />
                <span className="label-caps">March 9, 2026</span>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-100">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span className="text-[10px] font-bold uppercase tracking-wider">Verified: {qualityScore}% Quality</span>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-2 hover:bg-slate-50 rounded-lg transition-colors text-brand-muted hover:text-brand-ink">
                  <Share2 className="w-4 h-4" />
                </button>
                <button className="p-2 hover:bg-slate-50 rounded-lg transition-colors text-brand-muted hover:text-brand-ink">
                  <Download className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Headline & Summary */}
          <div className="space-y-8 max-w-4xl">
            <h1 className="serif text-5xl md:text-6xl lg:text-7xl font-light leading-[1.1] tracking-tight text-brand-ink">
              {headline}
            </h1>
            <div className="flex gap-8 items-start">
              <div className="w-12 h-px bg-brand-accent mt-4 flex-shrink-0" />
              <p className="text-xl text-slate-500 font-light leading-relaxed">
                {summary}
              </p>
            </div>
          </div>

          {/* Dataset Context */}
          <div className="pt-4 flex items-center gap-3">
            <span className="label-caps">Source Dataset:</span>
            <span className="text-sm font-medium text-slate-600 underline decoration-slate-200 underline-offset-4 cursor-pointer hover:text-brand-accent transition-colors">
              {datasetName}
            </span>
          </div>
        </motion.div>
      </div>
    </header>
  );
}
