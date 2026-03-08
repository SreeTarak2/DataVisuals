/**
 * DashboardHeader Component
 * 
 * Displays dashboard title, dataset metadata, domain info, and action buttons.
 * Extracted from Dashboard.jsx to improve component organization.
 */

import React from 'react';
import { useAuth } from '../../../store/authStore';
import { motion } from 'framer-motion';
import { Sparkles, RefreshCw, Loader2 } from 'lucide-react';
import { Button } from '../../../components/common/Button';
import DomainBadge from '../../../components/DomainBadge';

const DashboardHeader = ({
    selectedDataset,
    domainInfo,
    qualityMetrics,
    redesignCount,
    layoutLoading,
    onRegenerate,
    MAX_REDESIGNS
}) => {
    // Get user name from auth store
    const { user } = useAuth ? useAuth() : { user: null };

    // Time-of-day greeting
    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 18) return 'Good afternoon';
        return 'Good evening';
    };

    const userName = user?.username || user?.full_name || 'there';

    return (
        <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col lg:flex-row gap-6 items-start lg:items-center justify-between"
        >
            <div className="space-y-2">
                {/* Personalized Greeting */}
                <div className="text-3xl font-bold text-emerald-300 mb-1">
                    {getGreeting()}, {userName}!
                </div>
                {/* <h1 className="text-4xl font-bold text-white tracking-tight flex items-center gap-3">
                    <Sparkles className="w-10 h-10 text-emerald-400" />
                    DataSage AI
                </h1> */}
                <p className="text-slate-300 text-base font-medium">
                    {selectedDataset?.name ? (
                        <>
                            Intelligent analysis of: <span className="text-slate-200 font-medium">{selectedDataset.name}</span>
                            <span className="ml-4 text-sm bg-slate-800/50 px-3 py-1 rounded-full border border-slate-700 tabular-nums">
                                {selectedDataset.row_count || 0} rows • {selectedDataset.column_count || 0} columns
                            </span>
                            {selectedDataset.metadata?.data_quality?.data_cleaning_applied && (
                                <span className="ml-2 text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full border border-green-500/30">
                                    ✨ Data Cleaned
                                </span>
                            )}
                        </>
                    ) : (
                        <span className="text-slate-300 font-medium">No data has been uploaded yet</span>
                    )}
                </p>

                {/* v4.0 Enhanced Metadata Display */}
                {selectedDataset && (domainInfo || qualityMetrics) && (
                    <div className="flex flex-wrap items-center gap-3 mt-3">
                        {domainInfo && (
                            <DomainBadge
                                domain={domainInfo.domain}
                                confidence={domainInfo.confidence}
                                method={domainInfo.method}
                            />
                        )}
                    </div>
                )}
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
                <div className="text-right sm:text-left text-sm" aria-live="polite">
                    <p className="text-slate-500">Last updated</p>
                    <p className="text-slate-200 font-medium tabular-nums">
                        {new Date().toLocaleTimeString()}
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                        <Button
                            onClick={onRegenerate}
                            disabled={layoutLoading || !selectedDataset?.is_processed || redesignCount >= MAX_REDESIGNS}
                            className={`${redesignCount >= MAX_REDESIGNS
                                ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                                : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
                                } border border-slate-700 hover:border-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 transition-[background-color,border-color,color] duration-200 shadow-lg`}
                            title={`Ask AI to redesign this dashboard with fresh analysis (${redesignCount}/${MAX_REDESIGNS} used)`}
                            aria-busy={layoutLoading}
                            aria-live="polite"
                        >
                            {layoutLoading ? (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" aria-hidden="true" />
                            ) : (
                                <RefreshCw className="w-4 h-4 mr-2" aria-hidden="true" />
                            )}
                            {layoutLoading ? 'Redesigning...' : 'Redesign'}
                        </Button>

                        {redesignCount > 0 && (
                            <div
                                className={`px-3 py-1 rounded-lg text-xs font-medium tabular-nums ${redesignCount >= MAX_REDESIGNS
                                    ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                                    : redesignCount >= MAX_REDESIGNS - 1
                                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                        : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                    }`}
                                aria-label={`${MAX_REDESIGNS - redesignCount} redesigns remaining out of ${MAX_REDESIGNS}`}
                                title={`${MAX_REDESIGNS - redesignCount} redesigns remaining`}
                            >
                                {redesignCount}/{MAX_REDESIGNS}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </motion.div>
    );
};

export default DashboardHeader;
