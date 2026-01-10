/**
 * DashboardToolbar Component
 * 
 * Enterprise-grade toolbar for B2B analytics dashboard.
 * Benchmarked against Power BI, Tableau, and Looker design patterns.
 * 
 * Features:
 * - Workspace/dataset context breadcrumb
 * - Time range selector
 * - Refresh button with last updated timestamp
 * - Filter toggle (future implementation)
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
    RefreshCw, Clock, ChevronRight, Calendar,
    Filter, Loader2, Home, Database
} from 'lucide-react';
import { cn } from '../lib/utils';

const TIME_RANGES = [
    { id: 'today', label: 'Today' },
    { id: '7d', label: 'Last 7 Days' },
    { id: '30d', label: 'Last 30 Days' },
    { id: '90d', label: 'Last 90 Days' },
    { id: 'all', label: 'All Time' },
];

const DashboardToolbar = ({
    datasetName = 'Dataset',
    workspaceName = 'Workspace',
    onRefresh,
    isRefreshing = false,
    lastUpdated,
    onTimeRangeChange,
    selectedTimeRange = 'all',
    showFilters = false,
    onToggleFilters,
}) => {
    const [timeRangeOpen, setTimeRangeOpen] = useState(false);

    const formatLastUpdated = () => {
        if (!lastUpdated) return null;
        const date = new Date(lastUpdated);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const selectedRange = TIME_RANGES.find(r => r.id === selectedTimeRange) || TIME_RANGES[4];

    return (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-1 py-4 border-b border-slate-800/60">
            {/* Left: Breadcrumb Navigation */}
            <nav className="flex items-center gap-2 text-sm" aria-label="Breadcrumb">
                <div className="flex items-center gap-1.5 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer">
                    <Home className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">{workspaceName}</span>
                </div>

                <ChevronRight className="w-3.5 h-3.5 text-slate-600" />

                <div className="flex items-center gap-1.5 text-slate-300 font-medium">
                    <Database className="w-3.5 h-3.5 text-cyan-500" />
                    <span className="truncate max-w-[200px] sm:max-w-[300px]">{datasetName}</span>
                </div>
            </nav>

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
                {/* Time Range Selector */}
                <div className="relative">
                    <motion.button
                        whileTap={{ scale: 0.97 }}
                        onClick={() => setTimeRangeOpen(!timeRangeOpen)}
                        className={cn(
                            "flex items-center gap-2 px-3 py-2 text-sm rounded-lg border transition-all",
                            "bg-slate-800/60 border-slate-700/50 text-slate-300",
                            "hover:bg-slate-800 hover:border-slate-600"
                        )}
                    >
                        <Calendar className="w-3.5 h-3.5 text-slate-400" />
                        <span className="hidden sm:inline">{selectedRange.label}</span>
                    </motion.button>

                    {/* Time Range Dropdown */}
                    {timeRangeOpen && (
                        <>
                            <div
                                className="fixed inset-0 z-10"
                                onClick={() => setTimeRangeOpen(false)}
                            />
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="absolute right-0 top-full mt-1 z-20 w-40 bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1"
                            >
                                {TIME_RANGES.map((range) => (
                                    <button
                                        key={range.id}
                                        onClick={() => {
                                            onTimeRangeChange?.(range.id);
                                            setTimeRangeOpen(false);
                                        }}
                                        className={cn(
                                            "w-full text-left px-3 py-2 text-sm transition-colors",
                                            range.id === selectedTimeRange
                                                ? "bg-cyan-500/10 text-cyan-400"
                                                : "text-slate-300 hover:bg-slate-700"
                                        )}
                                    >
                                        {range.label}
                                    </button>
                                ))}
                            </motion.div>
                        </>
                    )}
                </div>

                {/* Filter Toggle */}
                {onToggleFilters && (
                    <motion.button
                        whileTap={{ scale: 0.97 }}
                        onClick={onToggleFilters}
                        className={cn(
                            "flex items-center gap-2 px-3 py-2 text-sm rounded-lg border transition-all",
                            showFilters
                                ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                                : "bg-slate-800/60 border-slate-700/50 text-slate-400 hover:bg-slate-800 hover:border-slate-600"
                        )}
                    >
                        <Filter className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Filters</span>
                    </motion.button>
                )}

                {/* Refresh Button */}
                <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={onRefresh}
                    disabled={isRefreshing}
                    className={cn(
                        "flex items-center gap-2 px-3 py-2 text-sm rounded-lg border transition-all",
                        "bg-slate-800/60 border-slate-700/50 text-slate-300",
                        "hover:bg-slate-800 hover:border-slate-600",
                        "disabled:opacity-50 disabled:cursor-not-allowed"
                    )}
                    title="Refresh dashboard"
                >
                    {isRefreshing ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                        <RefreshCw className="w-3.5 h-3.5" />
                    )}
                </motion.button>

                {/* Last Updated */}
                {formatLastUpdated() && (
                    <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-500">
                        <Clock className="w-3 h-3" />
                        <span>Updated {formatLastUpdated()}</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DashboardToolbar;
