/**
 * StoryReader Component
 * 
 * Main container for displaying the narrative story view.
 * Combines all story sub-components into a cohesive reading experience.
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Sparkles, FileText, AlertTriangle, TrendingUp } from 'lucide-react';
import StoryHero from './StoryHero';
import StoryOpening from './StoryOpening';
import StoryFinding from './StoryFinding';
import StoryComplication from './StoryComplication';
import StoryResolution from './StoryResolution';

const StoryReader = ({ story, datasetName, datasetId, onInvestigate, onClose, onSwitchToReport }) => {
    const handleSwitchToReport = onSwitchToReport || onClose;
    if (!story) {
        return (
            <div className="flex items-center justify-center py-20">
                <div className="text-center">
                    <div className="w-16 h-16 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mx-auto mb-4">
                        <BookOpen className="w-8 h-8 text-slate-600" />
                    </div>
                    <p className="text-slate-500">Story not available</p>
                </div>
            </div>
        );
    }

    const {
        findings = [],
        complications = [],
        resolution = null
    } = story;

    // Filter out empty findings (fallback template data has empty title + narrative)
    const validFindings = useMemo(
        () => findings.filter(f => f.title || f.narrative),
        [findings]
    );
    const validComplications = useMemo(
        () => complications.filter(c => c.title || c.narrative),
        [complications]
    );
    const hasContent = validFindings.length > 0 || validComplications.length > 0;

    // Build the story flow once per story data change — Math.random() inside must not run on every render
    const storyFlow = useMemo(
        () => buildStoryFlow(validFindings, validComplications),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [story]
    );

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="min-h-screen pb-20"
        >
            {/* Story Hero Section */}
            <StoryHero story={story} datasetName={datasetName} datasetId={datasetId} onSwitchToReport={handleSwitchToReport} />

            {/* Story Opening - Key Takeaway & Why It Matters */}
            <StoryOpening opening={story.opening} />

            {/* Story Flow - The main narrative */}
            <div className="mb-12">
                {/* Section header with stats */}
                <div className="max-w-3xl mx-auto px-6 mb-8">
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                                <Sparkles className="w-4 h-4 text-indigo-400" />
                            </div>
                            <div>
                                <h2 className="text-lg font-semibold text-white">The Investigation</h2>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    {validFindings.length} finding{validFindings.length !== 1 ? 's' : ''}
                                    {validComplications.length > 0 && ` · ${validComplications.length} risk${validComplications.length !== 1 ? 's' : ''}`}
                                    {resolution && ' · resolution'}
                                </p>
                            </div>
                        </div>
                        {/* Quick stat chips */}
                        <div className="flex items-center gap-2 flex-wrap">
                            {validFindings.length > 0 && (
                                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                                    <TrendingUp className="w-3 h-3" /> {validFindings.length} insights
                                </span>
                            )}
                            {validComplications.length > 0 && (
                                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 border border-amber-500/20 text-amber-400">
                                    <AlertTriangle className="w-3 h-3" /> {validComplications.length} risks
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Empty state when all findings have no content */}
                {!hasContent && (
                    <div className="max-w-3xl mx-auto px-6 py-10 text-center">
                        <div className="w-14 h-14 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mx-auto mb-4">
                            <BookOpen className="w-7 h-7 text-slate-600" />
                        </div>
                        <h3 className="text-slate-300 font-medium mb-2">Story content is minimal</h3>
                        <p className="text-sm text-slate-500 mb-5 max-w-xs mx-auto">
                            The narrative generation used a baseline template. The full report has all the detailed analysis.
                        </p>
                        {handleSwitchToReport && (
                            <button onClick={handleSwitchToReport}
                                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-white bg-slate-700 hover:bg-slate-600 transition-colors border border-slate-600">
                                <FileText className="w-4 h-4" /> View Full Report
                            </button>
                        )}
                    </div>
                )}

                {/* Story elements in flow order */}
                {storyFlow.map((item, index) => {
                    if (item.type === 'finding') {
                        return (
                            <StoryFinding
                                key={item.data.id || `finding-${index}`}
                                finding={item.data}
                                index={index}
                                isLast={index === storyFlow.length - 1 && !resolution}
                                onInvestigate={onInvestigate}
                            />
                        );
                    } else if (item.type === 'complication') {
                        return (
                            <StoryComplication
                                key={item.data.id || `risk-${index}`}
                                complication={item.data}
                                index={index}
                                onInvestigate={onInvestigate}
                            />
                        );
                    } else if (item.type === 'transition') {
                        return (
                            <StoryTransition key={`transition-${index}`} text={item.text} />
                        );
                    }
                    return null;
                })}
            </div>

            {/* Story Resolution - The Path Forward */}
            {resolution && (
                <StoryResolution
                    resolution={resolution}
                    onInvestigate={onInvestigate}
                />
            )}

            {/* Story Footer */}
            <footer className="max-w-3xl mx-auto px-6 py-8 mt-8 border-t border-slate-800">
                <div className="flex items-center justify-between text-sm text-slate-500">
                    <div className="flex items-center gap-2">
                        <BookOpen className="w-4 h-4" />
                        <span>End of story</span>
                    </div>
                    <div className="flex items-center gap-4">
                        {story.metadata?.generation_method && (
                            <span className="text-xs">
                                Generated: {story.metadata.generation_method.replace('_', ' ')}
                            </span>
                        )}
                    </div>
                </div>
            </footer>
        </motion.div>
    );
};

/**
 * Build the story flow by intelligently weaving complications into findings
 */
function buildStoryFlow(findings, complications) {
    const flow = [];
    
    // If there are no findings or complications, return empty
    if (findings.length === 0 && complications.length === 0) {
        return flow;
    }

    // Simple strategy: Interleave complications after findings
    // In a more advanced version, we could use the "connects_to" field
    // to determine placement based on narrative logic
    
    const findingsCopy = [...findings];
    const complicationsCopy = [...complications];

    let findingIndex = 0;
    let complicationIndex = 0;

    while (findingIndex < findingsCopy.length || complicationIndex < complicationsCopy.length) {
        // Add a finding
        if (findingIndex < findingsCopy.length) {
            flow.push({
                type: 'finding',
                data: findingsCopy[findingIndex]
            });
            findingIndex++;
        }

        // Add a complication after some findings
        if (complicationIndex < complicationsCopy.length && findingIndex >= 2) {
            flow.push({
                type: 'complication',
                data: complicationsCopy[complicationIndex]
            });
            complicationIndex++;
        }

        // After every 2 findings without a complication, maybe add one
        if (complicationIndex < complicationsCopy.length && findingIndex % 2 === 0 && findingIndex > 0) {
            // Check if we should add a transition text first
            if (Math.random() > 0.5) {
                flow.push({
                    type: 'transition',
                    text: getRandomTransition()
                });
            }
        }
    }

    // Add remaining complications at the end
    while (complicationIndex < complicationsCopy.length) {
        flow.push({
            type: 'complication',
            data: complicationsCopy[complicationIndex]
        });
        complicationIndex++;
    }

    return flow;
}

/**
 * Get a random natural transition phrase
 */
function getRandomTransition() {
    const transitions = [
        "But there's more to this story...",
        "Here's what makes this interesting...",
        "This is where things get surprising...",
        "Now let's look at the other side...",
        "However, there's a complication...",
        "This pattern becomes clearer when we look closer...",
        "There's something else happening here...",
        "But we found something unexpected..."
    ];
    return transitions[Math.floor(Math.random() * transitions.length)];
}

/**
 * Story Transition - Visual connector between story elements
 */
const StoryTransition = ({ text }) => (
    <div className="max-w-3xl mx-auto px-6 py-4">
        <div className="flex items-center gap-4">
            <div className="flex-1 h-px bg-linear-to-r from-transparent via-slate-700 to-transparent" />
            <p className="text-sm text-slate-500 italic text-center px-4">
                {text}
            </p>
            <div className="flex-1 h-px bg-linear-to-r from-transparent via-slate-700 to-transparent" />
        </div>
    </div>
);

export default StoryReader;
