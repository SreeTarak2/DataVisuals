/**
 * SegmentAnalysis — Highlights group comparisons using NarrativeInsightCards
 */
import React from 'react';
import { Layers } from 'lucide-react';
import NarrativeInsightCard from './NarrativeInsightCard';

const SegmentAnalysis = ({ segments = [], onInvestigate }) => {
    if (segments.length === 0) {
        return (
            <div className="rounded-2xl p-8 text-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center border" style={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--surface-border)' }}>
                    <Layers className="w-6 h-6" style={{ color: 'var(--page-muted)' }} />
                </div>
                <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--page-text)' }}>No Segments Found</h3>
                <p className="text-xs" style={{ color: 'var(--page-muted)' }}>No categorical columns with notable group differences detected.</p>
            </div>
        );
    }

    const highDeviation = segments.filter(s => Math.abs(s.deviation || 0) >= 2).length;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between pb-4 border-b border-[var(--surface-border)]">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-center">
                        <Layers className="w-5 h-5 text-purple-400" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-[var(--page-text)]">Segment Analysis</h3>
                        <p className="text-[13px] text-[var(--page-muted)] mt-0.5">
                            {segments.length} group comparison{segments.length !== 1 ? 's' : ''}
                            {highDeviation > 0 && <span className="text-red-400 font-bold ml-1">· {highDeviation} outlier group{highDeviation !== 1 ? 's' : ''}</span>}
                        </p>
                    </div>
                </div>
            </div>

            <div className="space-y-4 pt-4">
                {segments.map((seg, i) => (
                    <NarrativeInsightCard
                        key={`${seg.column}-${seg.segment_value}-${i}`}
                        insight={{
                            type: 'Driver / Segment',
                            title: `Notable behavior in ${seg.column} (${seg.segment_value})`,
                            description: seg.plain_english || `This segment deviates from the average by ${seg.deviation?.toFixed(1) || 0}σ.`,
                            tags: [seg.direction === 'higher' ? 'Above Average' : seg.direction === 'lower' ? 'Below Average' : 'Different', `${seg.count} rows`],
                            value: typeof seg.mean_value === 'number' ? seg.mean_value.toFixed(2) : String(seg.mean_value),
                            evidence: {
                                "Segment Mean": seg.mean_value,
                                "Overall Mean": seg.overall_mean,
                                "Deviation": `${seg.deviation?.toFixed(1)}σ`
                            }
                        }}
                        onInvestigate={onInvestigate}
                    />
                ))}
            </div>
        </div>
    );
};

export default SegmentAnalysis;
