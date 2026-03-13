import { ReportHeader } from './components/ReportHeader';
import { MetricGrid } from './components/MetricGrid';
import { ActionPlan } from './components/ActionPlan';
import { ReportSection } from './components/ReportSection';
import { mockReport } from './mockData';
import { motion, useScroll, useSpring } from 'motion/react';
import { LayoutDashboard, FileText, Share2, Download, Settings, ChevronRight } from 'lucide-react';

export default function App() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });

  return (
    <div className="min-h-screen bg-white selection:bg-brand-accent selection:text-white">
      {/* Progress Bar */}
      <motion.div
        className="fixed top-0 left-0 right-0 h-1 bg-brand-accent z-50 origin-left"
        style={{ scaleX }}
      />

      {/* Sidebar Navigation (Analyst Style) */}
      <aside className="fixed left-0 top-0 bottom-0 w-16 bg-white border-r border-brand-border z-40 flex flex-col items-center py-8 gap-8">
        <div className="w-10 h-10 rounded-xl bg-brand-accent flex items-center justify-center text-white font-bold shadow-lg shadow-blue-100">DS</div>
        <nav className="flex flex-col gap-6">
          <button className="p-2 text-brand-accent bg-blue-50 rounded-lg"><LayoutDashboard className="w-5 h-5" /></button>
          <button className="p-2 text-slate-400 hover:text-brand-ink transition-colors"><FileText className="w-5 h-5" /></button>
          <button className="p-2 text-slate-400 hover:text-brand-ink transition-colors"><Share2 className="w-5 h-5" /></button>
          <button className="p-2 text-slate-400 hover:text-brand-ink transition-colors"><Download className="w-5 h-5" /></button>
        </nav>
        <div className="mt-auto">
          <button className="p-2 text-slate-400 hover:text-brand-ink transition-colors"><Settings className="w-5 h-5" /></button>
        </div>
      </aside>

      <main className="pl-16">
        {/* Global Header */}
        <header className="h-16 bg-white/80 backdrop-blur-md border-b border-brand-border flex items-center justify-between px-8 sticky top-0 z-40">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
              <span>Reports</span>
              <ChevronRight className="w-3 h-3" />
              <span className="text-brand-ink font-bold">{mockReport.reportId}</span>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex -space-x-2">
              {[1, 2, 3].map(i => (
                <div key={i} className="w-7 h-7 rounded-full border-2 border-white bg-slate-200 overflow-hidden">
                  <img src={`https://picsum.photos/seed/user${i}/100/100`} alt="User" referrerPolicy="no-referrer" />
                </div>
              ))}
            </div>
            <div className="w-px h-4 bg-slate-200" />
            <button className="px-4 py-1.5 bg-brand-ink text-white text-xs font-semibold rounded-lg hover:bg-slate-800 transition-all shadow-sm">
              Publish Report
            </button>
          </div>
        </header>

        <ReportHeader 
          datasetName={mockReport.datasetName}
          reportId={mockReport.reportId}
          headline={mockReport.storyHeadline}
          summary={mockReport.executiveSummary}
          qualityScore={mockReport.dataQualityScore}
        />

        <MetricGrid kpis={mockReport.kpis} />

        <ActionPlan recommendations={mockReport.recommendations} />

        {mockReport.sections.map((section) => (
          <ReportSection key={section.id} section={section} />
        ))}

        <footer className="py-24 bg-slate-50 border-t border-brand-border">
          <div className="report-container flex flex-col md:flex-row justify-between items-start gap-16">
            <div className="space-y-6 max-w-sm">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-brand-accent" />
                <h3 className="serif text-2xl font-medium italic">DataSage Intelligence</h3>
              </div>
              <p className="text-slate-500 text-sm leading-relaxed">
                This report was generated using DataSage Engine v2.4. All statistical significance tests were performed at a 95% confidence level.
              </p>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-3 gap-12">
              <div className="space-y-4">
                <div className="label-caps">Platform</div>
                <div className="flex flex-col gap-2 text-sm text-slate-500">
                  <a href="#" className="hover:text-brand-ink transition-colors">Dashboard</a>
                  <a href="#" className="hover:text-brand-ink transition-colors">Data Sources</a>
                  <a href="#" className="hover:text-brand-ink transition-colors">Integrations</a>
                </div>
              </div>
              <div className="space-y-4">
                <div className="label-caps">Resources</div>
                <div className="flex flex-col gap-2 text-sm text-slate-500">
                  <a href="#" className="hover:text-brand-ink transition-colors">Documentation</a>
                  <a href="#" className="hover:text-brand-ink transition-colors">API Reference</a>
                  <a href="#" className="hover:text-brand-ink transition-colors">Methodology</a>
                </div>
              </div>
              <div className="space-y-4">
                <div className="label-caps">Legal</div>
                <div className="flex flex-col gap-2 text-sm text-slate-500">
                  <a href="#" className="hover:text-brand-ink transition-colors">Privacy Policy</a>
                  <a href="#" className="hover:text-brand-ink transition-colors">Terms of Service</a>
                  <a href="#" className="hover:text-brand-ink transition-colors">Security</a>
                </div>
              </div>
            </div>
          </div>
          
          <div className="report-container mt-24 pt-8 border-t border-slate-200 flex justify-between items-center">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">© 2026 DataSage AI. All rights reserved.</span>
            <div className="flex items-center gap-2 text-[10px] font-bold text-emerald-600 uppercase tracking-widest">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Engine v2.4.0 Online
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}
