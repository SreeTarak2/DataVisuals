/**
 * StoryComplication Component
 * 
 * Displays risks, anomalies, and warnings within the narrative.
 * Styled distinctly to draw attention to potential issues.
 */

import React from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, ShieldAlert, ArrowRight } from 'lucide-react';

const StoryComplication = ({ complication, index, onInvestigate }) => {
    if (!complication) return null;

    const {
        id = `risk-${index}`,
        type = 'risk',
        title = '',
        narrative = '',
        urgency = 'medium',
        evidence = {},
        mitigation = ''
    } = complication;

    const urgencyConfig = {
        critical: {
            bg: 'bg-red-500/10',
            border: 'border-red-500/30',
            text: 'text-red-400',
            icon: AlertTriangle,
            badge: 'bg-red-500/20 text-red-300 border-red-500/40'
        },
        high: {
            bg: 'bg-amber-500/10',
            border: 'border-amber-500/30',
            text: 'text-amber-400',
            icon: AlertTriangle,
            badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40'
        },
        medium: {
            bg: 'bg-orange-500/10',
            border: 'border-orange-500/30',
            text: 'text-orange-400',
            icon: ShieldAlert,
            badge: 'bg-orange-500/20 text-orange-300 border-orange-500/40'
        }
    };

    const config = urgencyConfig[urgency] || urgencyConfig.medium;
    const Icon = config.icon;

    const renderMarkdown = (text) => {
        if (!text) return null;
        const parts = text.split(/(\*\*[^*]+\*\*)/g);
        return parts.map((part, i) => {
            if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
            }
            return part;
        });
    };

    return (
        <motion.section
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
            className="max-w-3xl mx-auto px-6 py-8 mb-8"
        >
            {/* Warning banner */}
            <div className={`
                relative p-6 rounded-2xl border-l-4
                ${config.bg} ${config.border}
                before:absolute before:inset-0 before:rounded-2xl before:border
                before:${config.border}
            `}>
                {/* Header */}
                <div className="flex items-start gap-4 mb-4">
                    <div className={`
                        w-12 h-12 rounded-xl flex items-center justify-center
                        ${urgency === 'critical' ? 'bg-red-500/20' : urgency === 'high' ? 'bg-amber-500/20' : 'bg-orange-500/20'}
                    `}>
                        <Icon className={`w-6 h-6 ${config.text}`} />
                    </div>
                    
                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                            <span className={`
                                px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border
                                ${config.badge}
                            `}>
                                {urgency === 'critical' ? 'Critical' : urgency === 'high' ? 'High Priority' : 'Needs Attention'}
                            </span>
                        </div>
                        <h3 className="text-lg font-semibold text-white leading-tight">
                            {title}
                        </h3>
                    </div>
                </div>

                {/* Narrative */}
                <p className="text-base text-slate-300 leading-relaxed mb-4">
                    {renderMarkdown(narrative)}
                </p>

                {/* Evidence */}
                {evidence && Object.keys(evidence).length > 0 && (
                    <div className="mb-4 p-4 rounded-xl bg-slate-900/30 border border-slate-800/50">
                        <div className="grid grid-cols-2 gap-4 text-sm">
                            {evidence.metric && (
                                <div>
                                    <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">
                                        Current Value
                                    </span>
                                    <span className="text-white font-medium">
                                        {evidence.metric}
                                    </span>
                                </div>
                            )}
                            {evidence.threshold && (
                                <div>
                                    <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">
                                        Expected Range
                                    </span>
                                    <span className="text-slate-300">
                                        {evidence.threshold}
                                    </span>
                                </div>
                            )}
                            {evidence.risk_description && (
                                <div className="col-span-2">
                                    <span className="text-slate-500 block text-xs uppercase tracking-wider mb-1">
                                        What This Means
                                    </span>
                                    <span className="text-slate-300">
                                        {evidence.risk_description}
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Mitigation */}
                {mitigation && (
                    <div className="flex items-start gap-3 p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
                        <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-emerald-400 text-xs font-bold">→</span>
                        </div>
                        <div>
                            <span className="text-emerald-400 text-xs font-bold uppercase tracking-wider block mb-1">
                                Suggested Action
                            </span>
                            <p className="text-sm text-slate-300">
                                {mitigation}
                            </p>
                        </div>
                    </div>
                )}

                {/* Ask AI button */}
                {onInvestigate && (
                    <div className="mt-4 pt-4 border-t border-slate-700/30">
                        <button
                            onClick={() => onInvestigate(complication)}
                            className="flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
                        >
                            Investigate this risk with AI
                            <ArrowRight className="w-4 h-4" />
                        </button>
                    </div>
                )}
            </div>
        </motion.section>
    );
};

export default StoryComplication;
