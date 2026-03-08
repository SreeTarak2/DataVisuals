/**
 * ExecutiveSummary — AI-generated narrative intelligence with premium design
 */
import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, BrainCircuit, Newspaper, Fingerprint } from 'lucide-react';
import { renderBold } from '../../../lib/renderBold';

const ExecutiveSummary = ({ summary, datasetName, domain, storyHeadline, dataPersonality, aiNarrated }) => {
    if (!summary) return null;

    // If AI-narrated, the summary is a flowing paragraph — split into sentences
    // If template, split on sentence boundaries as before
    const sentences = summary
        .split(/(?<=\.\s)(?=[A-Z\*\u26A1\uD83D])/g)
        .filter(s => s.trim().length > 0);

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="relative h-full backdrop-blur-sm border rounded-2xl overflow-hidden"
            style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--surface-border)' }}
        >
            {/* Top gradient accent line */}
            <div className="absolute top-0 left-0 right-0 h-px opacity-60" style={{ background: 'linear-gradient(to right, transparent, var(--accent-primary), transparent)' }} />
            {/* Subtle background glow */}
            <div className="absolute -top-12 -right-12 w-32 h-32 rounded-full blur-2xl pointer-events-none opacity-30" style={{ backgroundColor: 'var(--accent-primary)' }} />

            <div className="relative p-6 h-full flex flex-col">
                {/* Header */}
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center border" style={{ background: 'linear-gradient(to bottom right, var(--accent-primary-muted), rgba(59, 130, 246, 0.2))', borderColor: 'var(--accent-primary-muted)' }}>
                        <Sparkles className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--page-text)' }}>Executive Summary</h3>
                        <p className="text-[13px] mt-0.5" style={{ color: 'var(--page-muted)' }}>
                            {aiNarrated ? 'AI-generated narrative intelligence' : 'AI-generated plain-English analysis'}
                        </p>
                    </div>
                    <div className="ml-auto">
                        <span className={`flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-lg border ${
                            aiNarrated
                                ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                                : ''
                        }`} style={!aiNarrated ? { color: 'var(--accent-primary)', backgroundColor: 'var(--accent-primary-muted)', borderColor: 'var(--accent-primary-muted)' } : {}}>
                            <BrainCircuit className="w-3 h-3" />
                            {aiNarrated ? 'AI Narrated' : 'AI Analyzed'}
                        </span>
                    </div>
                </div>

                {/* Story Headline — only when AI narrated */}
                {aiNarrated && storyHeadline && (
                    <motion.div
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.15 }}
                        className="flex items-start gap-2.5 mb-4 pb-4 border-b"
                        style={{ borderColor: 'var(--surface-border)' }}
                    >
                        <Newspaper className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                        <p className="text-[15px] font-semibold text-amber-300/90 leading-snug">
                            {storyHeadline}
                        </p>
                    </motion.div>
                )}

                {/* Numbered sentence bullets */}
                <div className="space-y-3 flex-1">
                    {sentences.map((sentence, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.18 + i * 0.07 }}
                            className="flex items-start gap-3"
                        >
                            <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 border" style={{ backgroundColor: 'var(--accent-primary-muted)', borderColor: 'var(--accent-primary-muted)' }}>
                                <span className="text-[13px] font-bold" style={{ color: 'var(--accent-primary)' }}>{i + 1}</span>
                            </div>
                            <p className="text-sm leading-relaxed" style={{ color: 'var(--page-muted)' }}>
                                {renderBold(sentence.trim())}
                            </p>
                        </motion.div>
                    ))}
                </div>

                {/* Data Personality — only when AI narrated */}
                {aiNarrated && dataPersonality && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.5 }}
                        className="flex items-start gap-2.5 mt-4 pt-4 border-t"
                        style={{ borderColor: 'var(--surface-border)' }}
                    >
                        <Fingerprint className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                        <p className="text-xs italic leading-relaxed" style={{ color: 'var(--page-muted)' }}>
                            {renderBold(dataPersonality)}
                        </p>
                    </motion.div>
                )}
            </div>
        </motion.div>
    );
};

export default ExecutiveSummary;
