/**
 * AnomalySpotlight — Highlights anomalies using NarrativeInsightCards
 */
import React from 'react';
import { Activity, CheckCircle } from 'lucide-react';
import NarrativeInsightCard from './NarrativeInsightCard';

const AnomalySpotlight = ({ anomalies = [], onInvestigate }) => {
    if (anomalies.length === 0) {
        return (
            <div className="rounded-2xl p-8 text-center border" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                    <CheckCircle className="w-6 h-6 text-emerald-400" />
                </div>
                <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--page-text)' }}>No Anomalies Detected</h3>
                <p className="text-xs" style={{ color: 'var(--page-muted)' }}>All columns are within expected ranges. Your data looks clean!</p>
            </div>
        );
    }

    const highCount = anomalies.filter(a => a.severity === 'high').length;
    const mediumCount = anomalies.filter(a => a.severity === 'medium').length;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between pb-4 border-b border-[var(--surface-border)]">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center justify-center">
                        <Activity className="w-5 h-5 text-red-400" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-[var(--page-text)]">Anomalies & Outliers</h3>
                        <p className="text-[13px] text-[var(--page-muted)] mt-0.5">
                            {anomalies.length} column{anomalies.length !== 1 ? 's' : ''} with unusual patterns
                            {highCount > 0 && <span className="text-red-400 font-bold ml-1">· {highCount} high</span>}
                            {mediumCount > 0 && <span className="text-amber-400 font-bold ml-1">· {mediumCount} moderate</span>}
                        </p>
                    </div>
                </div>
            </div>

            <div className="space-y-4 pt-4">
                {anomalies.map((anomaly, i) => (
                    <NarrativeInsightCard
                        key={`${anomaly.column}-${i}`}
                        insight={{
                            type: 'Anomaly',
                            title: `Outliers in ${anomaly.column}`,
                            description: anomaly.plain_english,
                            severity: anomaly.severity,
                            tags: [anomaly.method, `${anomaly.count} outliers`],
                            value: `${anomaly.percentage}%`,
                        }}
                        onInvestigate={onInvestigate}
                    />
                ))}
            </div>
        </div>
    );
};

export default AnomalySpotlight;
