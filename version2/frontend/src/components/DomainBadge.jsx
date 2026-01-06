/**
 * DomainBadge Component
 * 
 * Displays a styled badge showing the detected domain/category of a dataset
 * along with confidence level and detection method.
 */

import React from 'react';
import { Brain, Sparkles, FileSearch } from 'lucide-react';

const DomainBadge = ({ domain, confidence, method }) => {
    if (!domain) return null;

    // Determine confidence level styling
    const getConfidenceStyle = (conf) => {
        const percentage = conf * 100;
        if (percentage >= 80) {
            return {
                bg: 'bg-emerald-500/20',
                border: 'border-emerald-500/40',
                text: 'text-emerald-400',
                label: 'High'
            };
        }
        if (percentage >= 50) {
            return {
                bg: 'bg-amber-500/20',
                border: 'border-amber-500/40',
                text: 'text-amber-400',
                label: 'Medium'
            };
        }
        return {
            bg: 'bg-slate-500/20',
            border: 'border-slate-500/40',
            text: 'text-slate-400',
            label: 'Low'
        };
    };

    // Get icon based on detection method
    const getMethodIcon = (m) => {
        switch (m?.toLowerCase()) {
            case 'ai':
            case 'llm':
                return <Brain className="w-3.5 h-3.5" />;
            case 'auto':
            case 'automatic':
                return <Sparkles className="w-3.5 h-3.5" />;
            default:
                return <FileSearch className="w-3.5 h-3.5" />;
        }
    };

    const confStyle = getConfidenceStyle(confidence || 0);
    const confidencePercent = Math.round((confidence || 0) * 100);

    return (
        <div
            className={`
                inline-flex items-center gap-2 px-3 py-1.5 rounded-lg
                ${confStyle.bg} ${confStyle.border} border
                transition-all duration-200 hover:scale-105
            `}
        >
            {/* Domain Icon & Name */}
            <div className="flex items-center gap-1.5">
                <span className={confStyle.text}>
                    {getMethodIcon(method)}
                </span>
                <span className="text-sm font-medium text-slate-200 capitalize">
                    {domain}
                </span>
            </div>

            {/* Confidence Indicator */}
            {confidence !== undefined && (
                <div className="flex items-center gap-1.5 pl-2 border-l border-slate-600/50">
                    <div className="w-12 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all duration-500 ${confidencePercent >= 80
                                    ? 'bg-emerald-400'
                                    : confidencePercent >= 50
                                        ? 'bg-amber-400'
                                        : 'bg-slate-400'
                                }`}
                            style={{ width: `${confidencePercent}%` }}
                        />
                    </div>
                    <span className={`text-xs font-medium ${confStyle.text}`}>
                        {confidencePercent}%
                    </span>
                </div>
            )}

            {/* Method Tag */}
            {method && (
                <span className="text-xs text-slate-500 uppercase tracking-wider">
                    {method}
                </span>
            )}
        </div>
    );
};

export default DomainBadge;
