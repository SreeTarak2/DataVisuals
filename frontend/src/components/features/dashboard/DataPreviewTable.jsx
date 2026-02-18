/**
 * DataPreviewTable Component
 * 
 * Displays a preview table of the dataset (first 10 rows).
 * Extracted from Dashboard.jsx to improve component organization.
 */

import React from 'react';
import { motion } from 'framer-motion';
import { BarChart3, RefreshCw } from 'lucide-react';

const DataPreviewTable = ({ dataPreview, loading, onReload }) => {
    if (loading) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="group"
            >
                <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6">
                    <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
                        <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center">
                            <BarChart3 className="w-5 h-5 text-green-400" />
                        </div>
                        Data Preview
                    </h2>
                    <div className="text-center py-12 text-slate-400">
                        <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center mx-auto mb-4 animate-pulse">
                            <BarChart3 className="w-6 h-6 opacity-50" />
                        </div>
                        <p className="text-sm">Loading preview...</p>
                    </div>
                </div>
            </motion.div>
        );
    }

    if (!dataPreview || dataPreview.length === 0) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="group"
            >
                <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                            <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center">
                                <BarChart3 className="w-5 h-5 text-green-400" />
                            </div>
                            Data Preview
                        </h2>
                        <div className="flex items-center gap-4 text-sm text-slate-400">
                            {onReload && (
                                <button
                                    onClick={onReload}
                                    className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-700 text-slate-400 hover:text-white transition-all"
                                    title="Reload data preview"
                                >
                                    <RefreshCw className="w-4 h-4" />
                                </button>
                            )}
                            <span>No data available</span>
                        </div>
                    </div>

                    <div className="text-center py-12 text-slate-400">
                        <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center mx-auto mb-4">
                            <BarChart3 className="w-6 h-6 opacity-50" />
                        </div>
                        <p className="text-sm">No data preview available</p>
                        <p className="text-xs mt-1">Upload a dataset to see your data here</p>
                    </div>
                </div>
            </motion.div>
        );
    }

    const columns = Object.keys(dataPreview[0] || {});

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="group"
        >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center">
                            <BarChart3 className="w-5 h-5 text-green-400" />
                        </div>
                        Data Preview
                    </h2>
                    <div className="flex items-center gap-4 text-sm text-slate-400">
                        {onReload && (
                            <button
                                onClick={onReload}
                                className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-700 text-slate-400 hover:text-white transition-all"
                                title="Reload data preview"
                            >
                                <RefreshCw className="w-4 h-4" />
                            </button>
                        )}
                        <span>Showing {dataPreview.length} rows</span>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-slate-700">
                                {columns.map((col) => (
                                    <th
                                        key={col}
                                        className="text-left py-3 px-4 text-sm font-semibold text-slate-300 bg-slate-800/50"
                                    >
                                        {col}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {dataPreview.map((row, idx) => (
                                <tr
                                    key={idx}
                                    className="border-b border-slate-800 hover:bg-slate-800/30 transition-colors"
                                >
                                    {columns.map((col) => (
                                        <td key={col} className="py-3 px-4 text-sm text-slate-400">
                                            {row[col] !== null && row[col] !== undefined ? String(row[col]) : '-'}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </motion.div>
    );
};

export default DataPreviewTable;

