/**
 * InsightsSection Component
 * 
 * Displays AI-generated insights with icons and confidence scores.
 * Extracted from Dashboard.jsx to improve component organization.
 */

import React from 'react';
import { motion } from 'framer-motion';
import {
    Zap,
    TrendingUp,
    AlertTriangle,
    CheckCircle,
    Lightbulb,
    ChevronRight
} from 'lucide-react';

const iconMap = {
    TrendingUp,
    AlertTriangle,
    CheckCircle,
    Lightbulb,
    Zap
};

const InsightsSection = ({ insights, loading }) => {
    if (loading) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-6">
                    <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
                        <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
                            <Zap className="w-5 h-5 text-blue-400" />
                        </div>
                        AI Insights
                    </h2>
                    <div className="text-center py-8 text-slate-400">
                        <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center mx-auto mb-4 animate-pulse">
                            <Zap className="w-6 h-6 opacity-50" />
                        </div>
                        <p className="text-sm">Generating insights...</p>
                    </div>
                </div>
            </motion.div>
        );
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
        >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
                <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
                        <Zap className="w-5 h-5 text-blue-400" />
                    </div>
                    AI Insights
                </h2>
                <div className="space-y-4">
                    {insights && insights.length > 0 ? (
                        insights.map((insight, i) => {
                            const IconComponent = iconMap[insight.icon] || Zap;
                            return (
                                <motion.div
                                    key={insight.id || i}
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: i * 0.1 }}
                                    className="flex items-start gap-4 p-4 rounded-2xl border border-slate-800 bg-slate-800/30 hover:bg-slate-800/50 hover:border-slate-700 transition-all duration-200"
                                >
                                    <div className="flex-shrink-0 mt-1">
                                        <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
                                            <IconComponent className="w-4 h-4 text-blue-400" />
                                        </div>
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            <p className="text-sm text-white font-medium">{insight.title}</p>
                                            {insight.confidence && (
                                                <span className="text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                                    {insight.confidence}%
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-xs text-slate-400 leading-relaxed">{insight.description}</p>
                                    </div>
                                    <button className="ml-auto p-1 text-slate-400 hover:text-white transition-colors relative top-2">
                                        <ChevronRight className="w-6 h-6" />
                                    </button>
                                </motion.div>
                            );
                        })
                    ) : (
                        <div className="text-center py-8 text-slate-400">
                            <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center mx-auto mb-4">
                                <Zap className="w-6 h-6 opacity-50" />
                            </div>
                            <p className="text-sm">No insights available. Upload a dataset to get started.</p>
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
};

export default InsightsSection;
