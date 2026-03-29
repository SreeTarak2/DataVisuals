/**
 * DashboardHeader Component
 * 
 * Displays dashboard title, dataset metadata, domain info, and action buttons.
 * Extracted from Dashboard.jsx to improve component organization.
 */

import React from 'react';
import { useAuth } from '../../../store/authStore';
import { motion } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';
import DomainBadge from '../../../components/DomainBadge';

const MotionDiv = motion.div;

const DashboardHeader = ({
    selectedDataset,
    domainInfo,
    qualityMetrics,
    dashboardLoading,
    artifactPreparing,
    dashboardArtifactStatus,
    MAX_REDESIGNS,
    lastUpdatedAt,
    insightsSummary,
}) => {
    // Get user name from auth store
    const { user } = useAuth();

    // Time-of-day greeting
    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 18) return 'Good afternoon';
        return 'Good evening';
    };

    const userName = user?.username || user?.full_name || 'there';
    const processingProgress = selectedDataset?.processing_progress || 0;
    const processingStatus = selectedDataset?.processing_status || null;
    const dashboardError = selectedDataset?.artifact_status?.dashboard_error;
    const formattedUpdatedAt = lastUpdatedAt
        ? new Date(lastUpdatedAt).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
        : 'Awaiting analysis';

    return (
        <MotionDiv
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col lg:flex-row gap-6 items-start lg:items-center justify-between"
        >
            <div className="space-y-2">
                {/* Personalized Greeting */}
                <div className="text-3xl font-bold text-slate-100 mb-1">
                    {getGreeting()}, <span className="bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">{userName}!</span>
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
                {selectedDataset && (domainInfo || qualityMetrics || dashboardArtifactStatus || processingStatus || insightsSummary?.high_priority_findings > 0) && (
                    <div className="flex flex-wrap items-center gap-3 mt-3">
                        {domainInfo && (
                            <DomainBadge
                                domain={domainInfo.domain}
                                confidence={domainInfo.confidence}
                                method={domainInfo.method}
                            />
                        )}
                        {dashboardArtifactStatus && dashboardArtifactStatus !== 'ready' && (
                            <span className="text-xs bg-indigo-500/15 text-indigo-300 px-2.5 py-1 rounded-full border border-indigo-500/30">
                                Dashboard artifact: {dashboardArtifactStatus}
                            </span>
                        )}
                        {processingStatus && selectedDataset?.is_processed === false && (
                            <span className="text-xs bg-blue-500/15 text-blue-300 px-2.5 py-1 rounded-full border border-blue-500/30">
                                {processingStatus.replace(/_/g, ' ')} · {processingProgress}%
                            </span>
                        )}
                        {insightsSummary?.high_priority_findings > 0 && (
                            <span className="inline-flex items-center gap-1.5 text-xs bg-amber-500/15 text-amber-300 px-2.5 py-1 rounded-full border border-amber-500/30">
                                <AlertTriangle className="w-3 h-3" aria-hidden="true" />
                                {insightsSummary.high_priority_findings} priority finding{insightsSummary.high_priority_findings !== 1 ? 's' : ''}
                            </span>
                        )}
                        {dashboardArtifactStatus === 'failed' && dashboardError && (
                            <span className="text-xs bg-red-500/15 text-red-300 px-2.5 py-1 rounded-full border border-red-500/30">
                                Dashboard prep failed
                            </span>
                        )}
                    </div>
                )}
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
                <div className="text-right sm:text-left text-sm" aria-live="polite">
                    <p className="text-slate-500">Last updated</p>
                    <p className="text-slate-200 font-medium tabular-nums">
                        {formattedUpdatedAt}
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    {/* Redesign button moved to Header component */}
                    {artifactPreparing && (
                        <div className="px-3 py-1 rounded-lg text-xs font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                            Preparing dashboard
                        </div>
                    )}
                </div>
            </div>
        </MotionDiv>
    );
};

export default DashboardHeader;
