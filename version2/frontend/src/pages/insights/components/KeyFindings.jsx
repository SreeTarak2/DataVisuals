/**
 * KeyFindings — Renders a list of high-impact narrative insights
 */
import React from 'react';
import { Zap, ArrowRight } from 'lucide-react';
import NarrativeInsightCard from './NarrativeInsightCard';

const KeyFindings = ({ findings = [], compact = false, onViewAll, onInvestigate }) => {
    if (findings.length === 0) {
        return (
            <div className="bg-slate-900/50 border border-slate-800/60 rounded-2xl p-8 text-center">
                <Zap className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                <h3 className="text-sm font-semibold text-white mb-1">No Key Findings</h3>
                <p className="text-xs text-slate-300">No significant statistical patterns were detected.</p>
            </div>
        );
    }

    const criticalCount = findings.filter(f => f.severity === 'critical').length;
    const highCount = findings.filter(f => f.severity === 'high').length;

    // We no longer wrap this in a bounded card as NarrativeInsightCards are meant to be full-width "report" sections.
    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between pb-4 border-b border-[var(--surface-border)]">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-center justify-center">
                        <Zap className="w-5 h-5 text-amber-400" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-[var(--page-text)]">Key Findings</h3>
                        <p className="text-[13px] text-[var(--page-muted)] mt-0.5">
                            {findings.length} finding{findings.length !== 1 ? 's' : ''} ranked by impact
                            {criticalCount > 0 && <span className="text-red-400 font-bold ml-1">· {criticalCount} critical</span>}
                            {highCount > 0 && <span className="text-amber-400 font-bold ml-1">· {highCount} high</span>}
                        </p>
                    </div>
                </div>
                {compact && onViewAll && (
                    <button onClick={onViewAll} className="flex items-center gap-1 text-xs text-[var(--page-muted)] hover:text-[var(--page-text)] transition-colors font-medium">
                        View all <ArrowRight className="w-3 h-3" />
                    </button>
                )}
            </div>

            <div className="space-y-4 pt-4">
                {findings.map((finding, i) => (
                    <NarrativeInsightCard
                        key={finding.id || i}
                        insight={finding}
                        onInvestigate={onInvestigate}
                    />
                ))}
            </div>
        </div>
    );
};

export default KeyFindings;
