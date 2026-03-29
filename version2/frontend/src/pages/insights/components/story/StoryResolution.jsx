/**
 * StoryResolution Component
 * 
 * Displays the conclusion and recommended actions of the story.
 * Styled as the narrative conclusion with clear call-to-action.
 */

import React from 'react';
import { motion } from 'framer-motion';
import { 
    Target, 
    ChevronRight, 
    CheckCircle, 
    Clock, 
    ArrowRight,
    TrendingUp
} from 'lucide-react';

const StoryResolution = ({ resolution, onInvestigate }) => {
    if (!resolution) return null;

    const {
        story_conclusion = '',
        primary_action = {},
        secondary_actions = [],
        monitoring = {}
    } = resolution;

    const {
        title = '',
        rationale = '',
        impact = '',
        effort = 'medium'
    } = primary_action;

    const {
        key_metrics = [],
        check_frequency = 'weekly',
        success_indicator = ''
    } = monitoring;

    const effortColors = {
        low: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
        medium: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
        high: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' }
    };

    return (
        <section className="max-w-3xl mx-auto px-6 py-12 mb-8">
            {/* Divider with "Resolution" label */}
            <div className="flex items-center gap-4 mb-8">
                <div className="flex-1 h-px bg-gradient-to-r from-slate-700 to-slate-800" />
                <span className="text-xs font-bold uppercase tracking-widest text-slate-500">
                    The Path Forward
                </span>
                <div className="flex-1 h-px bg-gradient-to-l from-slate-700 to-slate-800" />
            </div>

            {/* Story Conclusion */}
            {story_conclusion && (
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="mb-8 p-6 rounded-2xl bg-gradient-to-br from-slate-800/50 to-slate-900/50 border border-slate-700/30"
                >
                    <p className="text-lg text-slate-200 leading-relaxed">
                        {story_conclusion}
                    </p>
                </motion.div>
            )}

            {/* Primary Action */}
            {primary_action && title && (
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="mb-8"
                >
                    <div className="relative p-6 rounded-2xl bg-gradient-to-br from-indigo-500/10 via-slate-800/50 to-violet-500/10 border border-indigo-500/30">
                        {/* Priority badge */}
                        <div className="absolute -top-3 left-6">
                            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-500/40">
                                <Target className="w-4 h-4 text-indigo-400" />
                                <span className="text-xs font-bold text-indigo-300 uppercase tracking-wider">
                                    Primary Action
                                </span>
                            </div>
                        </div>

                        <div className="pt-2">
                            <h3 className="text-xl font-semibold text-white mb-3">
                                {title}
                            </h3>

                            {rationale && (
                                <p className="text-slate-300 leading-relaxed mb-4">
                                    {rationale}
                                </p>
                            )}

                            <div className="flex flex-wrap items-center gap-4">
                                {/* Impact */}
                                {impact && (
                                    <div className="flex items-center gap-2">
                                        <TrendingUp className="w-4 h-4 text-cyan-400" />
                                        <span className="text-sm text-slate-300">
                                            Expected: {impact}
                                        </span>
                                    </div>
                                )}

                                {/* Effort */}
                                <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${
                                    effortColors[effort]?.bg || effortColors.medium.bg
                                } ${effortColors[effort]?.text || effortColors.medium.text} ${
                                    effortColors[effort]?.border || effortColors.medium.border
                                }`}>
                                    <Clock className="w-3 h-3" />
                                    {effort.charAt(0).toUpperCase() + effort.slice(1)} effort
                                </div>

                                {/* Ask AI button */}
                                {onInvestigate && (
                                    <button
                                        onClick={() => onInvestigate(primary_action, { type: 'recommendation', chapter: 'Resolution' })}
                                        className="ml-auto flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
                                    >
                                        Get guidance from AI
                                        <ArrowRight className="w-4 h-4" />
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </motion.div>
            )}

            {/* Secondary Actions */}
            {secondary_actions && secondary_actions.length > 0 && (
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="mb-8"
                >
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-4">
                        Supporting Actions
                    </h4>
                    <div className="space-y-3">
                        {secondary_actions.map((action, index) => (
                            <div
                                key={index}
                                className="flex items-start gap-4 p-4 rounded-xl bg-slate-800/30 border border-slate-700/30 hover:border-slate-600/30 transition-colors"
                            >
                                <div className="w-6 h-6 rounded-full bg-slate-700/50 border border-slate-600/50 flex items-center justify-center flex-shrink-0 mt-0.5">
                                    <span className="text-xs text-slate-400 font-medium">
                                        {index + 2}
                                    </span>
                                </div>
                                <div className="flex-1">
                                    <h5 className="text-sm font-medium text-white mb-1">
                                        {action.title}
                                    </h5>
                                    {action.description && (
                                        <p className="text-sm text-slate-400 leading-relaxed">
                                            {action.description}
                                        </p>
                                    )}
                                </div>
                                {onInvestigate && (
                                    <button
                                        onClick={() => onInvestigate(action, { type: 'recommendation', chapter: 'Resolution' })}
                                        className="flex-shrink-0 p-2 rounded-lg hover:bg-slate-700/50 transition-colors"
                                    >
                                        <ArrowRight className="w-4 h-4 text-slate-500" />
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </motion.div>
            )}

            {/* Monitoring Section */}
            {monitoring && (key_metrics.length > 0 || success_indicator) && (
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                    className="p-6 rounded-2xl bg-slate-800/30 border border-slate-700/30"
                >
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-4">
                        What to Monitor
                    </h4>

                    <div className="grid md:grid-cols-2 gap-6">
                        {/* Key Metrics */}
                        {key_metrics.length > 0 && (
                            <div>
                                <span className="text-xs text-slate-500 uppercase tracking-wider mb-2 block">
                                    Key Metrics
                                </span>
                                <div className="flex flex-wrap gap-2">
                                    {key_metrics.map((metric, index) => (
                                        <span
                                            key={index}
                                            className="px-3 py-1 rounded-full bg-slate-700/50 border border-slate-600/30 text-sm text-slate-300"
                                        >
                                            {metric}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Frequency & Success */}
                        <div className="space-y-3">
                            {check_frequency && (
                                <div className="flex items-center gap-3">
                                    <Clock className="w-4 h-4 text-slate-500" />
                                    <span className="text-sm text-slate-400">
                                        Check <span className="text-white font-medium">{check_frequency}</span>
                                    </span>
                                </div>
                            )}
                            {success_indicator && (
                                <div className="flex items-center gap-3">
                                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                                    <span className="text-sm text-slate-400">
                                        Success: <span className="text-white">{success_indicator}</span>
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                </motion.div>
            )}
        </section>
    );
};

export default StoryResolution;
