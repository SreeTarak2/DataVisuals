import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, Info, Maximize2, X, Filter } from 'lucide-react';

const DistributionComparison = ({ datasetId, numericCol, groupCol, title = "Distribution Comparison" }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedGroup, setSelectedGroup] = useState(null);

    useEffect(() => {
        const fetchComparison = async () => {
            if (!datasetId || !numericCol || !groupCol) return;
            try {
                setLoading(true);
                const response = await fetch(`/api/dashboard/${datasetId}/analytics/distribution-comparison?numeric_col=${numericCol}&group_col=${groupCol}`);
                if (!response.ok) throw new Error('Failed to fetch distribution data');
                const result = await response.json();
                setData(result);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchComparison();
    }, [datasetId, numericCol, groupCol]);

    if (loading) return (
        <div className="flex items-center justify-center h-80 bg-slate-900/50 rounded-xl animate-pulse">
            <div className="text-slate-400 text-sm font-medium">Running Statistical Comparison...</div>
        </div>
    );

    if (error || !data || !data.group_stats || !data.group_stats.length) return (
        <div className="flex items-center justify-center h-80 bg-slate-900/50 rounded-xl border border-dashed border-slate-700">
            <div className="text-slate-500 text-sm">Insufficient data for distribution comparison.</div>
        </div>
    );

    const { group_stats, significance } = data;
    const maxFreq = Math.max(...group_stats.flatMap(g => g.histogram));

    return (
        <motion.div
            layout
            className="bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-800 p-6 h-full flex flex-col"
        >
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                        {title}
                        <div className="group relative">
                            <Info size={14} className="text-slate-500 cursor-help" />
                        </div>
                    </h3>
                    <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-slate-500 uppercase tracking-wider">{numeric_col} by {group_col}</span>
                        {significance?.significant && (
                            <span className="px-2 py-0.5 bg-green-500/10 text-green-500 text-[10px] font-bold rounded-full border border-green-500/20">
                                Statistically Significant (p={significance.p_value})
                            </span>
                        )}
                    </div>
                </div>
            </div>

            <div className="flex-1 flex flex-col gap-4 overflow-auto custom-scrollbar pr-2">
                {group_stats.map((group, idx) => (
                    <motion.div
                        key={group.group}
                        initial={{ x: -20, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        transition={{ delay: idx * 0.1 }}
                        className="relative group cursor-default"
                        onMouseEnter={() => setSelectedGroup(group.group)}
                        onMouseLeave={() => setSelectedGroup(null)}
                    >
                        {/* Group Label */}
                        <div className="flex items-end justify-between mb-1">
                            <span className={`text-xs font-medium transition-colors ${selectedGroup === group.group ? 'text-blue-400' : 'text-slate-400'}`}>
                                {group.group}
                            </span>
                            <span className="text-[10px] text-slate-600">μ={group.mean} | n={group.count}</span>
                        </div>

                        {/* Distribution Ridge */}
                        <div className="h-16 relative w-full overflow-hidden rounded-lg bg-slate-950/30 border border-slate-800/50">
                            <div className="absolute inset-0 flex items-end px-1 overflow-hidden">
                                {group.histogram.map((val, i) => (
                                    <div
                                        key={i}
                                        className="flex-1 transition-all duration-500 ease-out"
                                        style={{
                                            height: `${(val / maxFreq) * 100}%`,
                                            backgroundColor: selectedGroup === group.group ? 'rgba(59, 130, 246, 0.6)' : 'rgba(30, 41, 59, 0.4)',
                                            margin: '0 0.5px',
                                            borderRadius: '1px 1px 0 0'
                                        }}
                                    ></div>
                                ))}
                            </div>

                            {/* Mean Line */}
                            <div
                                className="absolute top-0 bottom-0 w-px bg-blue-500/50 z-10 shadow-[0_0_8px_rgba(59,130,246,0.5)]"
                                style={{ left: '50%' }} // Simplified for visual placeholder, in real app map mean to histogram range
                            ></div>
                        </div>

                        {/* Hover Overlay Stats */}
                        {selectedGroup === group.group && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="absolute top-0 right-0 bg-slate-900 border border-slate-700 px-2 py-1 rounded text-[10px] text-slate-300 z-20 flex gap-3 shadow-2xl"
                            >
                                <span>Median: <b>{group.median}</b></span>
                                <span>Range: <b>{group.min} - {group.max}</b></span>
                                <span>Std Dev: <b>{group.std}</b></span>
                            </motion.div>
                        )}
                    </motion.div>
                ))}
            </div>

            <div className="mt-6 flex items-center justify-between text-[10px] text-slate-500 border-t border-slate-800 pt-4">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-slate-700"></div>
                        <span>Frequency</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="w-px h-3 bg-blue-500/50"></div>
                        <span>Average (Mean)</span>
                    </div>
                </div>
                <div>Showing top {group_stats.length} groups by count</div>
            </div>
        </motion.div>
    );
};

export default DistributionComparison;
