/**
 * DashboardHeader Component - Enterprise Edition
 * 
 * Professional executive-style header for B2B analytics dashboard.
 * Focus on dataset context and metadata, not casual greetings.
 */

import React from 'react';
import { motion } from 'framer-motion';
import {
    Database, RefreshCw, Loader2, Clock,
    LayoutGrid, CheckCircle, FileSpreadsheet,
    Columns, Rows
} from 'lucide-react';
import { Button } from '../../../components/Button';
import DomainBadge from '../../../components/DomainBadge';

const DashboardHeader = ({
    selectedDataset,
    domainInfo,
    qualityMetrics,
    redesignCount,
    layoutLoading,
    onRegenerate,
    MAX_REDESIGNS,
    onRefresh,
    isRefreshing
}) => {

    // Format number with comma separators
    const formatNumber = (num) => {
        if (!num) return '0';
        return new Intl.NumberFormat('en-US').format(num);
    };

    return (
        <motion.header
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="border-b border-slate-800/60 pb-6 mb-6"
        >
            {/* Main Header Row */}
            <div className="flex flex-col lg:flex-row gap-4 lg:items-center justify-between">
                {/* Left: Dataset Info */}
                <div className="space-y-3">
                    {/* Dataset Title */}
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center">
                            <FileSpreadsheet className="w-5 h-5 text-slate-400" />
                        </div>
                        <div>
                            <h1 className="text-xl font-semibold text-white tracking-tight">
                                {selectedDataset?.name || 'Dataset Analytics'}
                            </h1>
                            {selectedDataset && (
                                <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                                    <span className="flex items-center gap-1.5">
                                        <Rows className="w-3 h-3" />
                                        {formatNumber(selectedDataset.row_count)} rows
                                    </span>
                                    <span className="w-1 h-1 rounded-full bg-slate-700" />
                                    <span className="flex items-center gap-1.5">
                                        <Columns className="w-3 h-3" />
                                        {formatNumber(selectedDataset.column_count)} columns
                                    </span>

                                    {/* Domain Badge */}
                                    {domainInfo && (
                                        <>
                                            <span className="w-1 h-1 rounded-full bg-slate-700" />
                                            <span className="bg-slate-800 px-2 py-0.5 rounded text-slate-400">
                                                {domainInfo.domain}
                                            </span>
                                        </>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-3">
                    {/* Refresh Data Button */}
                    <Button
                        onClick={onRefresh}
                        disabled={isRefreshing || layoutLoading}
                        className="bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 p-2 rounded-lg transition-colors"
                        title="Refresh Data"
                    >
                        {isRefreshing ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <RefreshCw className="w-4 h-4" />
                        )}
                    </Button>

                    <div className="w-px h-8 bg-slate-800 mx-1"></div>

                    {/* Redesign Button */}
                    <div className="flex items-center gap-2">
                        <Button
                            onClick={onRegenerate}
                            disabled={layoutLoading || !selectedDataset?.is_processed || redesignCount >= MAX_REDESIGNS}
                            className={`
                                px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200
                                ${redesignCount >= MAX_REDESIGNS
                                    ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                                    : 'bg-slate-800 hover:bg-slate-700 text-white border border-slate-600 hover:border-slate-500 shadow-sm'
                                }
                            `}
                            title={`Regenerate dashboard layout (${redesignCount}/${MAX_REDESIGNS} used)`}
                        >
                            {layoutLoading ? (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                                <RefreshCw className="w-4 h-4 mr-2" />
                            )}
                            {layoutLoading ? 'Regenerating...' : 'Regenerate'}
                        </Button>

                        {/* Usage Counter */}
                        {redesignCount > 0 && (
                            <div className={`
                                px-2.5 py-1 rounded-md text-xs font-medium tabular-nums
                                ${redesignCount >= MAX_REDESIGNS
                                    ? 'bg-red-500/15 text-red-400 border border-red-500/30'
                                    : redesignCount >= MAX_REDESIGNS - 1
                                        ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                                }
                            `}>
                                {redesignCount}/{MAX_REDESIGNS}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </motion.header>
    );
};

export default DashboardHeader;

