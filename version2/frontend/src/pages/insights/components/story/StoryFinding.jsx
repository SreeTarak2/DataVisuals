/**
 * StoryFinding Component
 * 
 * Displays an individual finding within the narrative story.
 * Each finding has a title, narrative text, and optional evidence.
 */

import React from 'react';
import { motion } from 'framer-motion';
import { 
    TrendingUp, 
    TrendingDown, 
    Activity, 
    Zap, 
    AlertTriangle,
    ArrowRight,
    ChevronDown,
    ChevronUp
} from 'lucide-react';
import { useState } from 'react';

const ICONS = {
    trend: TrendingUp,
    discovery: Zap,
    pattern: Activity,
    connection: Activity,
    anomaly: AlertTriangle,
    risk: AlertTriangle,
    default: Activity
};

const StoryFinding = ({ finding, index, isLast = false, onInvestigate }) => {
    const [expanded, setExpanded] = useState(false);
    const [showProof, setShowProof] = useState(false);

    if (!finding) return null;

    const {
        id = `finding-${index}`,
        type = 'discovery',
        title = '',
        narrative = '',
        evidence = {},
        importance = 5
    } = finding;

    // Skip findings with no real content — happens when story uses fallback templates
    if (!title && !narrative) return null;

    const Icon = ICONS[type] || ICONS.default;
    const importanceColor = importance >= 8 ? 'text-red-400' : importance >= 6 ? 'text-amber-400' : 'text-cyan-400';

    // Visual weight based on importance
    const borderColor = importance >= 8 ? 'border-red-500/40' : importance >= 6 ? 'border-amber-500/30' : 'border-slate-700/40';
    const bgColor = importance >= 8 ? 'bg-red-500/3' : importance >= 6 ? 'bg-amber-500/3' : '';

    const renderMarkdown = (text) => {
        if (!text) return null;
        
        // Simple markdown-like rendering for bold text
        const parts = text.split(/(\*\*[^*]+\*\*)/g);
        return parts.map((part, i) => {
            if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
            }
            return part;
        });
    };

    return (
        <motion.article
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5, delay: Math.min(index * 0.08, 0.4) }}
            className={`relative max-w-3xl mx-auto px-6 py-8 mb-4 rounded-2xl border-l-4 ${borderColor} ${bgColor}`}
        >
            {/* Finding connector line */}
            {!isLast && (
                <div 
                    className="absolute left-8 top-full w-0.5 h-6 bg-gradient-to-b from-slate-700 to-slate-800"
                    style={{ left: '2rem' }}
                />
            )}

            <div className="flex gap-6">
                {/* Finding number/icon */}
                <div className="flex-shrink-0">
                    <div className={`
                        w-12 h-12 rounded-2xl flex items-center justify-center
                        ${type === 'anomaly' || type === 'risk' 
                            ? 'bg-red-500/10 border border-red-500/20' 
                            : type === 'connection'
                            ? 'bg-blue-500/10 border border-blue-500/20'
                            : 'bg-slate-800/80 border border-slate-700/50'
                        }
                    `}>
                        <Icon 
                            className={`w-6 h-6 ${
                                type === 'anomaly' || type === 'risk' 
                                    ? 'text-red-400' 
                                    : type === 'connection'
                                    ? 'text-blue-400'
                                    : 'text-slate-400'
                            }`} 
                        />
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    {/* Title */}
                    <h3 className="text-lg font-semibold text-white mb-3 leading-tight">
                        {title}
                    </h3>

                    {/* Narrative text */}
                    <div className="text-base text-slate-300 leading-relaxed mb-4">
                        {renderMarkdown(narrative)}
                    </div>

                    {/* Evidence section */}
                    {evidence && Object.keys(evidence).length > 0 && (
                        <div className="mb-4">
                            <button
                                onClick={() => setShowProof(!showProof)}
                                className="flex items-center gap-2 text-xs font-medium text-slate-500 hover:text-slate-300 transition-colors"
                            >
                                {showProof ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                {showProof ? 'Hide' : 'Show'} evidence
                            </button>

                            {showProof && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className="mt-3 p-4 rounded-xl bg-slate-900/50 border border-slate-800/50"
                                >
                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                        {evidence.key_metric && (
                                            <div>
                                                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">
                                                    Key Metric
                                                </span>
                                                <span className="text-white font-medium">
                                                    {evidence.key_metric}
                                                </span>
                                            </div>
                                        )}
                                        {evidence.confidence && (
                                            <div>
                                                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">
                                                    Confidence
                                                </span>
                                                <span className={`font-medium ${
                                                    evidence.confidence === 'high' 
                                                        ? 'text-emerald-400' 
                                                        : evidence.confidence === 'medium'
                                                        ? 'text-amber-400'
                                                        : 'text-slate-400'
                                                }`}>
                                                    {evidence.confidence.charAt(0).toUpperCase() + evidence.confidence.slice(1)}
                                                </span>
                                            </div>
                                        )}
                                        {evidence.supporting_details && evidence.supporting_details.length > 0 && (
                                            <div className="col-span-2">
                                                <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">
                                                    Supporting Details
                                                </span>
                                                <ul className="space-y-1">
                                                    {evidence.supporting_details.map((detail, i) => (
                                                        <li key={i} className="text-slate-300 text-sm">
                                                            • {detail}
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                    </div>
                                </motion.div>
                            )}
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-4 pt-2">
                        {onInvestigate && (
                            <button
                                onClick={() => onInvestigate(finding)}
                                className="flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
                            >
                                Ask AI about this
                                <ArrowRight className="w-4 h-4" />
                            </button>
                        )}

                        {/* Importance indicator */}
                        {importance >= 7 && (
                            <span className={`text-xs font-medium ${importanceColor}`}>
                                High importance
                            </span>
                        )}
                    </div>
                </div>
            </div>
        </motion.article>
    );
};

export default StoryFinding;
