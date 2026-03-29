/**
 * StoryOpening Component
 * 
 * Displays the key takeaway and "why it matters" sections of the story.
 */

import React from 'react';
import { Lightbulb, Info } from 'lucide-react';

// Generic fallback strings the backend uses when LLM story fails
const FALLBACK_STRINGS = new Set([
    'key patterns and insights have been identified.',
    'understanding these patterns informs better decisions.',
    'further exploration can reveal additional insights.',
]);
const isFallback = (text) => !text || FALLBACK_STRINGS.has(text.trim().toLowerCase());

const StoryOpening = ({ opening }) => {
    if (!opening) return null;

    const {
        takeaway = '',
        why_matters = ''
    } = opening;

    // Don't render if both are empty or clearly fallback template text
    if (isFallback(takeaway) && isFallback(why_matters)) return null;

    return (
        <section className="max-w-3xl mx-auto px-6 py-8 mb-8">
            {/* Key Takeaway */}
            {takeaway && (
                <div className="relative mb-8">
                    <div className="flex items-start gap-4 p-6 rounded-2xl bg-gradient-to-br from-slate-800/50 to-slate-900/50 border border-slate-700/30">
                        <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                            <Lightbulb className="w-5 h-5 text-amber-400" />
                        </div>
                        <div className="flex-1">
                            <h2 className="text-xs font-bold uppercase tracking-wider text-amber-400 mb-3">
                                Key Takeaway
                            </h2>
                            <p className="text-base md:text-lg text-slate-200 leading-relaxed">
                                {takeaway}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Why It Matters */}
            {why_matters && (
                <div className="relative mb-4">
                    <div className="flex items-start gap-4 p-6 rounded-2xl bg-slate-800/30 border border-slate-700/20">
                        <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
                            <Info className="w-5 h-5 text-cyan-400" />
                        </div>
                        <div className="flex-1">
                            <h2 className="text-xs font-bold uppercase tracking-wider text-cyan-400 mb-3">
                                Why It Matters
                            </h2>
                            <p className="text-base text-slate-300 leading-relaxed">
                                {why_matters}
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
};

export default StoryOpening;
