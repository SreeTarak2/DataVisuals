/**
 * TrendAnalysis — Highlights trends using NarrativeInsightCards
 */
import React from 'react';
import { TrendingUp, Clock } from 'lucide-react';
import NarrativeInsightCard from './NarrativeInsightCard';

const TrendAnalysis = ({ trends = [], onInvestigate }) => {
    if (trends.length === 0) {
        return (
            <div className="rounded-2xl p-8 text-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center border" style={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--surface-border)' }}>
                    <Clock className="w-6 h-6" style={{ color: 'var(--page-muted)' }} />
                </div>
                <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--page-text)' }}>No Temporal Trends</h3>
                <p className="text-xs" style={{ color: 'var(--page-muted)' }}>No time-based columns found or no significant trends detected.</p>
            </div>
        );
    }

    const sigCount = trends.filter(t => t.is_significant).length;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between pb-4 border-b border-[var(--surface-border)]">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center justify-center">
                        <TrendingUp className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-[var(--page-text)]">Trend Analysis</h3>
                        <p className="text-[13px] text-[var(--page-muted)] mt-0.5">
                            {trends.length} temporal pattern{trends.length !== 1 ? 's' : ''}
                            {sigCount > 0 && <span className="text-emerald-400 font-bold ml-1">· {sigCount} significant</span>}
                        </p>
                    </div>
                </div>
            </div>

            <div className="space-y-4 pt-4">
                {trends.map((trend, i) => (
                    <NarrativeInsightCard
                        key={`${trend.column}-${i}`}
                        insight={{
                            type: 'Trend',
                            title: `${trend.direction === 'increasing' ? 'Upward' : trend.direction === 'decreasing' ? 'Downward' : 'Stable'} Trend in ${trend.column}`,
                            description: trend.plain_english,
                            tags: [trend.direction, trend.seasonality && `Seasonality: ${trend.seasonality}`].filter(Boolean),
                            evidence: {
                                p_value: trend.p_value,
                                effect_size: trend.strength.toFixed(2)
                            }
                        }}
                        onInvestigate={onInvestigate}
                    />
                ))}
            </div>
        </div>
    );
};

export default TrendAnalysis;
