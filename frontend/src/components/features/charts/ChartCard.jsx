/**
 * ChartCard Component
 * 
 * Enterprise-grade chart wrapper for B2B analytics dashboard.
 * Provides consistent styling, action toolbar, and export capabilities.
 * 
 * Features:
 * - Title bar with chart type indicator
 * - Action toolbar (fullscreen, export, filter)
 * - Consistent border/shadow styling  
 * - Loading skeleton matching chart dimensions
 */

import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Maximize2, Minimize2, Download, MoreVertical,
    BarChart3, LineChart, PieChart, ScatterChart,
    Image, FileSpreadsheet, X
} from 'lucide-react';
import { cn } from '../lib/utils';

const CHART_ICONS = {
    bar_chart: BarChart3,
    bar: BarChart3,
    line_chart: LineChart,
    line: LineChart,
    pie_chart: PieChart,
    pie: PieChart,
    scatter_plot: ScatterChart,
    scatter: ScatterChart,
    default: BarChart3,
};

const ChartCard = ({
    title,
    subtitle,
    chartType = 'bar',
    children,
    loading = false,
    onExportImage,
    onExportCsv,
    className,
}) => {
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [showMenu, setShowMenu] = useState(false);
    const cardRef = useRef(null);

    const ChartIcon = CHART_ICONS[chartType] || CHART_ICONS.default;

    const handleFullscreen = () => {
        if (!isFullscreen && cardRef.current) {
            cardRef.current.requestFullscreen?.();
        } else if (document.fullscreenElement) {
            document.exitFullscreen?.();
        }
        setIsFullscreen(!isFullscreen);
    };

    const handleExportImage = async () => {
        setShowMenu(false);
        onExportImage?.();
    };

    const handleExportCsv = () => {
        setShowMenu(false);
        onExportCsv?.();
    };

    // Loading skeleton
    if (loading) {
        return (
            <div className={cn(
                "bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden",
                className
            )}>
                <div className="p-4 border-b border-slate-800/50">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-slate-800 rounded-lg animate-pulse" />
                        <div className="space-y-2">
                            <div className="h-4 w-32 bg-slate-800 rounded animate-pulse" />
                            <div className="h-3 w-24 bg-slate-800/60 rounded animate-pulse" />
                        </div>
                    </div>
                </div>
                <div className="h-[400px] bg-slate-800/20 animate-pulse" />
            </div>
        );
    }

    return (
        <>
            <motion.div
                ref={cardRef}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn(
                    "bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden",
                    "hover:border-slate-700/80 transition-all duration-300",
                    "shadow-lg shadow-black/10",
                    isFullscreen && "fixed inset-4 z-50 rounded-2xl",
                    className
                )}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800/50 bg-slate-900/40">
                    {/* Title Area */}
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-800/80 flex items-center justify-center">
                            <ChartIcon className="w-4 h-4 text-cyan-400" />
                        </div>
                        <div>
                            <h3 className="text-sm font-semibold text-white">{title}</h3>
                            {subtitle && (
                                <p className="text-xs text-slate-500">{subtitle}</p>
                            )}
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1">
                        {/* Fullscreen Toggle */}
                        <button
                            onClick={handleFullscreen}
                            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                            title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                        >
                            {isFullscreen ? (
                                <Minimize2 className="w-4 h-4" />
                            ) : (
                                <Maximize2 className="w-4 h-4" />
                            )}
                        </button>

                        {/* Export Menu */}
                        <div className="relative">
                            <button
                                onClick={() => setShowMenu(!showMenu)}
                                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                                title="Export options"
                            >
                                <MoreVertical className="w-4 h-4" />
                            </button>

                            <AnimatePresence>
                                {showMenu && (
                                    <>
                                        <div
                                            className="fixed inset-0 z-10"
                                            onClick={() => setShowMenu(false)}
                                        />
                                        <motion.div
                                            initial={{ opacity: 0, scale: 0.95, y: -4 }}
                                            animate={{ opacity: 1, scale: 1, y: 0 }}
                                            exit={{ opacity: 0, scale: 0.95, y: -4 }}
                                            className="absolute right-0 top-full mt-1 z-20 w-44 bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1"
                                        >
                                            <button
                                                onClick={handleExportImage}
                                                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700 transition-colors"
                                            >
                                                <Image className="w-4 h-4" />
                                                Export as PNG
                                            </button>
                                            <button
                                                onClick={handleExportCsv}
                                                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700 transition-colors"
                                            >
                                                <FileSpreadsheet className="w-4 h-4" />
                                                Export as CSV
                                            </button>
                                        </motion.div>
                                    </>
                                )}
                            </AnimatePresence>
                        </div>
                    </div>
                </div>

                {/* Chart Content */}
                <div className={cn(
                    "p-4 bg-[#0d1117]",
                    isFullscreen ? "h-[calc(100%-60px)]" : "h-[400px]"
                )}>
                    {children}
                </div>
            </motion.div>

            {/* Fullscreen backdrop */}
            {isFullscreen && (
                <div
                    className="fixed inset-0 bg-black/80 z-40"
                    onClick={handleFullscreen}
                />
            )}
        </>
    );
};

export default ChartCard;
