/**
 * StoryHero Component
 * 
 * Displays the story title, subtitle, and metadata at the top of the narrative.
 */

import React from 'react';
import { Clock, Calendar, Sparkles, Info } from 'lucide-react';

// Detect generic fallback hook phrases the backend uses when LLM story fails
const FALLBACK_HOOKS = new Set([
    "here's what your data reveals.",
    "your data has a story to tell.",
    "here is what the data says.",
]);
const isTemplatStory = (hook) => !hook || FALLBACK_HOOKS.has(hook.trim().toLowerCase());

const StoryHero = ({ story, datasetName, datasetId, onSwitchToReport }) => {
    if (!story) return null;

    const {
        title = 'Your Data Story',
        subtitle = '',
        opening = {},
        metadata = {}
    } = story;

    const {
        reading_time_minutes = 3,
        theme = 'exploration',
        confidence_score = 0,
        generated_at = null,
        overall_health = null,
        top_priority = null
    } = metadata;

    const themeColors = {
        growth: { bg: 'bg-emerald-500/5', border: 'border-emerald-500/20', text: 'text-emerald-400' },
        decline: { bg: 'bg-red-500/5', border: 'border-red-500/20', text: 'text-red-400' },
        risk: { bg: 'bg-amber-500/5', border: 'border-amber-500/20', text: 'text-amber-400' },
        warning: { bg: 'bg-amber-500/5', border: 'border-amber-500/20', text: 'text-amber-400' },
        opportunity: { bg: 'bg-blue-500/5', border: 'border-blue-500/20', text: 'text-blue-400' },
        exploration: { bg: 'bg-violet-500/5', border: 'border-violet-500/20', text: 'text-violet-400' },
        mixed: { bg: 'bg-slate-500/5', border: 'border-slate-500/20', text: 'text-slate-400' },
    };

    const themeStyle = themeColors[theme] || themeColors.exploration;

    const formatDate = (dateStr) => {
        if (!dateStr) return null;
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return null;
        }
    };

    const isTemplate = isTemplatStory(opening?.hook);

    return (
        <header className="relative py-12 px-6 mb-8">
            {/* Background gradient */}
            <div 
                className="absolute inset-0 opacity-50"
                style={{
                    background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(59, 130, 246, 0.04) 50%, rgba(139, 92, 246, 0.06) 100%)'
                }}
            />

            <div className="relative max-w-3xl mx-auto">
                {/* Story icon and dataset */}
                <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/30 flex items-center justify-center">
                        <Sparkles className="w-5 h-5 text-indigo-400" />
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                            Data Story
                        </p>
                        <p className="text-sm text-slate-300">
                            {datasetName}
                        </p>
                    </div>
                </div>

                {/* Title */}
                <h1 className="text-3xl md:text-4xl font-bold text-white mb-4 leading-tight">
                    {title}
                </h1>

                {/* Subtitle */}
                {subtitle && (
                    <p className="text-lg text-slate-400 mb-6 leading-relaxed">
                        {subtitle}
                    </p>
                )}

                {/* Opening hook */}
                {opening.hook && (
                    <div className="relative mb-8">
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-indigo-500 to-violet-500 rounded-full" />
                        <p className="pl-6 text-lg md:text-xl text-slate-200 leading-relaxed font-light italic">
                            "{opening.hook}"
                        </p>
                    </div>
                )}

                {/* Metadata bar */}
                <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-slate-800">
                    {/* Reading time */}
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                        <Clock className="w-4 h-4" />
                        <span>{reading_time_minutes} min read</span>
                    </div>

                    {/* Generated time */}
                    {generated_at && (
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                            <Calendar className="w-4 h-4" />
                            <span>{formatDate(generated_at)}</span>
                        </div>
                    )}

                    {/* Overall health badge */}
                    {overall_health && (
                        <span className={`px-3 py-1 rounded-full text-xs font-medium border ${
                            overall_health === 'Strong' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                            overall_health === 'Stable' ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' :
                            overall_health === 'Needs attention' ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' :
                            overall_health === 'Critical' ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                            'bg-slate-500/10 border-slate-500/30 text-slate-400'
                        }`}>
                            {overall_health}
                        </span>
                    )}

                    {/* Theme badge */}
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${themeStyle.bg} ${themeStyle.border} ${themeStyle.text} border`}>
                        {theme.charAt(0).toUpperCase() + theme.slice(1).replace('_', ' ')}
                    </span>

                    {/* Confidence indicator */}
                    {confidence_score > 0 && (
                        <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                                <div 
                                    className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500"
                                    style={{ width: `${confidence_score * 100}%` }}
                                />
                            </div>
                            <span className="text-xs text-slate-500">
                                {Math.round(confidence_score * 100)}% confidence
                            </span>
                        </div>
                    )}

                </div>

                {/* Top priority */}
                {top_priority && (
                    <div className="mt-4 p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                        <p className="text-xs font-medium text-indigo-400 mb-1">Top Priority</p>
                        <p className="text-sm text-slate-300">{top_priority}</p>
                    </div>
                )}

                {/* Template/fallback data warning */}
                {isTemplate && (
                    <div className="mt-5 flex items-start gap-3 p-4 rounded-xl bg-amber-500/5 border border-amber-500/20">
                        <Info className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                            <p className="text-sm text-amber-300 font-medium mb-0.5">Narrative generating</p>
                            <p className="text-xs text-slate-400 leading-relaxed">
                                The AI narrative for this dataset is still being generated. The detailed analysis below has all the findings and evidence.
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </header>
    );
};

export default StoryHero;
