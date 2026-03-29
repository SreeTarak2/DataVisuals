/**
 * StoryPlaceholder Component
 * 
 * Animated placeholder shown while the narrative story is being generated.
 * Provides visual feedback that the story is being created.
 */

import React from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Sparkles, Clock } from 'lucide-react';

const StoryPlaceholder = () => {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="max-w-3xl mx-auto px-6 py-12"
        >
            {/* Header */}
            <div className="text-center mb-12">
                <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="inline-flex items-center gap-3 px-6 py-3 rounded-full bg-gradient-to-r from-indigo-500/10 via-violet-500/10 to-purple-500/10 border border-indigo-500/20 mb-6"
                >
                    <Sparkles className="w-5 h-5 text-indigo-400 animate-pulse" />
                    <span className="text-sm font-medium text-indigo-300">
                        Crafting your narrative story...
                    </span>
                </motion.div>

                <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">
                    Weaving Your Data Story
                </h2>
                <p className="text-slate-400 max-w-md mx-auto">
                    Our AI is analyzing your insights and transforming them into a compelling narrative that anyone can understand.
                </p>
            </div>

            {/* Animated Cards */}
            <div className="space-y-6">
                {/* Opening Card */}
                <motion.div
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    className="relative p-6 rounded-2xl bg-slate-800/30 border border-slate-700/30 overflow-hidden"
                >
                    <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/5 to-violet-500/5" />
                    <div className="relative">
                        <div className="flex items-center gap-3 mb-4">
                            <BookOpen className="w-5 h-5 text-indigo-400" />
                            <div className="h-5 w-32 bg-slate-700/50 rounded animate-pulse" />
                        </div>
                        <div className="space-y-2">
                            <div className="h-4 w-full bg-slate-700/50 rounded animate-pulse" />
                            <div className="h-4 w-3/4 bg-slate-700/50 rounded animate-pulse" />
                            <div className="h-4 w-5/6 bg-slate-700/50 rounded animate-pulse" />
                        </div>
                    </div>
                </motion.div>

                {/* Finding Cards */}
                {[1, 2, 3].map((i) => (
                    <motion.div
                        key={i}
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        transition={{ delay: 0.4 + i * 0.1 }}
                        className="flex gap-6 p-6 rounded-2xl bg-slate-800/20 border border-slate-700/20"
                    >
                        <div className="flex-shrink-0">
                            <div className="w-12 h-12 rounded-2xl bg-slate-700/50 animate-pulse" />
                        </div>
                        <div className="flex-1 space-y-3">
                            <div className="h-5 w-48 bg-slate-700/50 rounded animate-pulse" />
                            <div className="space-y-2">
                                <div className="h-4 w-full bg-slate-700/50 rounded animate-pulse" />
                                <div className="h-4 w-2/3 bg-slate-700/50 rounded animate-pulse" />
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>

            {/* Footer Info */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.8 }}
                className="mt-12 text-center"
            >
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-800/50 border border-slate-700/30">
                    <Clock className="w-4 h-4 text-slate-500" />
                    <span className="text-sm text-slate-500">
                        Usually takes 30-60 seconds
                    </span>
                </div>
                <p className="mt-4 text-xs text-slate-600">
                    The story will appear automatically when ready. Base insights are available below.
                </p>
            </motion.div>
        </motion.div>
    );
};

export default StoryPlaceholder;
