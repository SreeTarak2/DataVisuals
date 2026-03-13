import { ReportSection as SectionType } from '../types';
import { InsightCard } from './InsightCard';

interface ReportSectionProps {
  section: SectionType;
}

export function ReportSection({ section }: ReportSectionProps) {
  return (
    <section className="py-20 border-b border-brand-border last:border-0">
      <div className="report-container">
        <div className="grid lg:grid-cols-12 gap-12">
          {/* Section Narrative */}
          <div className="lg:col-span-4 lg:sticky lg:top-32 h-fit space-y-6">
            <div className="space-y-4">
              <h2 className="serif text-4xl font-light leading-tight text-brand-ink">
                {section.title}
              </h2>
              <p className="text-slate-500 leading-relaxed font-light">
                {section.narrative}
              </p>
            </div>
            <div className="pt-4">
              <div className="label-caps mb-2">Section Findings</div>
              <div className="text-xs font-bold text-brand-accent">
                {section.insights.length} Key Insights Identified
              </div>
            </div>
          </div>

          {/* Section Insights */}
          <div className="lg:col-span-8">
            {section.insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
