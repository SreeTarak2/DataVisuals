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
    RefreshCw,
    Filter, Loader2
} from 'lucide-react';
import { cn } from '../lib/utils';

const DashboardToolbar = ({
    onRefresh,
    isRefreshing = false,
    showFilters = false,
    onToggleFilters,
}) => {
    const [timeRangeOpen, setTimeRangeOpen] = useState(false);

    return (
        <div className="flex flex-col sm:flex-row sm:items-center justify-end gap-3 px-1 py-4 border-b border-slate-800/60">
            {/* Right: Actions */}
            <div className="flex items-center gap-2">
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
            </div>
        </div>
    );
};

export default DashboardToolbar;
