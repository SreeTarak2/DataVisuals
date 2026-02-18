import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Zap,
    TrendingUp,
    AlertTriangle,
    CheckCircle,
    Lightbulb,
    ChevronRight,
    ChevronDown,
    Brain,
    Target,
    BarChart3,
    Filter,
    Search
} from 'lucide-react';
import { transformInsights } from '../utils/insightTransformer';

const iconMap = {
    'trend': TrendingUp,
    'performance': BarChart3,
    'correlation': Zap,
    'anomaly': AlertTriangle,
    'recommendation': Lightbulb,
    'quality': CheckCircle,
    'quis': Brain,
    'subspace': Search
};

const colorMap = {
    'trend': 'text-green-400 bg-green-500/10 border-green-500/20',
    'performance': 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    'correlation': 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    'anomaly': 'text-red-400 bg-red-500/10 border-red-500/20',
    'recommendation': 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    'quality': 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    'quis': 'text-purple-400 bg-purple-500/10 border-purple-500/20',
    'subspace': 'text-pink-400 bg-pink-500/10 border-pink-500/20'
};

const InsightCard = ({ insight, index }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    // Use transformed display values or fall back to raw values
    const title = insight.displayTitle || insight.title || 'Insight';
    const description = insight.displayDescription || insight.description || '';
    const action = insight.displayAction || 'Explore this pattern in Charts Studio.';
    const confidence = insight.displayConfidence || insight.confidence || 85;

    // Determine category for styling
    const category = insight.category || 'correlation';
    const IconComponent = iconMap[category] || Lightbulb;
    const colorClass = colorMap[category] || 'text-slate-400 bg-slate-500/10 border-slate-500/20';

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            className={`rounded-xl border border-slate-800 bg-slate-900/40 hover:bg-slate-800/40 transition-all duration-300 overflow-hidden ${isExpanded ? 'ring-1 ring-blue-500/30' : ''}`}
        >
            <div
                className="p-4 flex items-start gap-4 cursor-pointer"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className={`p-2 rounded-lg ${colorClass} flex-shrink-0 mt-0.5`}>
                    <IconComponent className="w-5 h-5" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-4 mb-1">
                        <h3 className="text-sm font-semibold text-white truncate pr-2">
                            {title}
                        </h3>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${confidence > 80 ? 'bg-green-500/20 text-green-400' :
                            confidence > 60 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-slate-500/20 text-slate-400'
                            }`}>
                            {Math.round(confidence)}%
                        </span>
                    </div>

                    <p className={`text-xs text-slate-400 leading-relaxed ${!isExpanded ? 'line-clamp-2' : ''}`}>
                        {description}
                    </p>

                    {/* Compact footer when collapsed */}
                    {!isExpanded && (
                        <div className="flex items-center gap-4 mt-3">
                            <span className="text-[10px] bg-slate-800 text-slate-500 px-2 py-0.5 rounded uppercase tracking-wider font-semibold">
                                {category}
                            </span>
                            <span className="text-[10px] text-slate-600 flex items-center gap-1 group-hover:text-blue-400 transition-colors">
                                View Details <ChevronDown className="w-3 h-3" />
                            </span>
                        </div>
                    )}
                </div>
            </div>

            {/* Expanded Content */}
            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden border-t border-slate-800/50 bg-slate-900/30"
                    >
                        <div className="p-4 pl-[4.5rem] space-y-3">
                            {/* Detailed breakdown if available */}
                            {insight.details && (
                                <div>
                                    <h4 className="text-xs font-semibold text-slate-300 mb-1">Analysis Details</h4>
                                    <p className="text-sm text-slate-400">{insight.details}</p>
                                </div>
                            )}

                            {/* Subspace/Dimensions Info */}
                            {insight.dimensions && (
                                <div className="flex flex-wrap gap-2">
                                    {insight.dimensions.map((dim, i) => (
                                        <span key={i} className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-400 border border-slate-700">
                                            {dim}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* Action Item */}
                            <div className="flex items-start gap-2 bg-blue-500/5 p-3 rounded-lg border border-blue-500/10">
                                <Target className="w-4 h-4 text-blue-400 mt-0.5" />
                                <div>
                                    <h5 className="text-xs font-semibold text-blue-300">Recommendation</h5>
                                    <p className="text-xs text-blue-200/70 mt-0.5">
                                        {action}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

const InsightsSection = ({ insights = [], loading, datasetInfo }) => {
    const [activeTab, setActiveTab] = useState('all');

    // Transform all insights first
    const transformedInsights = useMemo(() => {
        return transformInsights(insights || []);
    }, [insights]);

    // Memoized filtering using transformed category
    const filteredInsights = useMemo(() => {
        if (!transformedInsights.length) return [];
        if (activeTab === 'all') return transformedInsights;

        return transformedInsights.filter(insight => {
            return activeTab === 'other'
                ? !['correlation', 'trend', 'anomaly'].includes(insight.category)
                : insight.category === activeTab;
        });
    }, [transformedInsights, activeTab]);

    // Counts for tabs using transformed categories
    const counts = useMemo(() => {
        if (!transformedInsights.length) return { all: 0, correlation: 0, trend: 0, anomaly: 0 };
        return {
            all: transformedInsights.length,
            correlation: transformedInsights.filter(i => i.category === 'correlation').length,
            trend: transformedInsights.filter(i => i.category === 'trend').length,
            anomaly: transformedInsights.filter(i => i.category === 'anomaly').length
        };
    }, [transformedInsights]);

    if (loading) {
        return (
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-6 min-h-[300px] flex items-center justify-center">
                <div className="text-center space-y-4">
                    <div className="relative w-16 h-16 mx-auto">
                        <div className="absolute inset-0 rounded-full border-2 border-slate-800"></div>
                        <div className="absolute inset-0 rounded-full border-t-2 border-blue-500 animate-spin"></div>
                        <Brain className="absolute inset-0 m-auto w-6 h-6 text-blue-400 animate-pulse" />
                    </div>
                    <p className="text-sm text-slate-400 font-medium">Analyzing data patterns...</p>
                </div>
            </div>
        );
    }

    if (!insights || insights.length === 0) {
        return (
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-8 text-center">
                <div className="w-16 h-16 bg-slate-800/50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Lightbulb className="w-8 h-8 text-slate-500" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">No Insights Yet</h3>
                <p className="text-slate-400 max-w-md mx-auto mb-6">
                    Upload a dataset and let our AI analyze it to uncover hidden patterns, correlations, and trends.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header & Tabs */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-xl flex items-center justify-center border border-blue-500/10">
                        <Zap className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-white">AI Insights</h2>
                        <p className="text-xs text-slate-400">
                            {datasetInfo?.name ? `Analysis for ${datasetInfo.name}` : 'Automated Data Analysis'}
                        </p>
                    </div>
                </div>

                {/* Tabs */}
                <div className="flex p-1 bg-slate-900/80 rounded-lg border border-slate-800/50 overflow-x-auto scrollbar-hide">
                    {[
                        { id: 'all', label: 'All', icon: Filter },
                        { id: 'correlation', label: 'Correlations', icon: Zap },
                        { id: 'trend', label: 'Trends', icon: TrendingUp },
                        { id: 'anomaly', label: 'Anomalies', icon: AlertTriangle },
                    ].map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all whitespace-nowrap ${activeTab === tab.id
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                                : 'text-slate-400 hover:text-white hover:bg-slate-800'
                                }`}
                        >
                            <tab.icon className="w-3.5 h-3.5" />
                            {tab.label}
                            <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] ${activeTab === tab.id ? 'bg-white/20' : 'bg-slate-800'
                                }`}>
                                {counts[tab.id] || 0}
                            </span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Content Grid */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 10 }}
                    transition={{ duration: 0.2 }}
                    className="grid grid-cols-1 md:grid-cols-2 gap-4"
                >
                    {filteredInsights.length > 0 ? (
                        filteredInsights.map((insight, index) => (
                            <InsightCard key={index} insight={insight} index={index} />
                        ))
                    ) : (
                        <div className="col-span-full py-12 text-center text-slate-500 bg-slate-900/30 rounded-xl border border-dashed border-slate-800">
                            <p>No insights found for this category.</p>
                        </div>
                    )}
                </motion.div>
            </AnimatePresence>
        </div>
    );
};

export default InsightsSection;
