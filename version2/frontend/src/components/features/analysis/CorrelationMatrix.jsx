import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Info, Maximize2, X, Download, Filter } from 'lucide-react';

const CorrelationMatrix = ({ datasetId, title = "Variable Correlations" }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [hoveredCell, setHoveredCell] = useState(null);
    const [isMaximized, setIsMaximized] = useState(false);

    useEffect(() => {
        const fetchCorrelation = async () => {
            try {
                setLoading(true);
                const response = await fetch(`/api/dashboard/${datasetId}/analytics/correlation`);
                if (!response.ok) throw new Error('Failed to fetch correlation data');
                const result = await response.json();
                setData(result);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        if (datasetId) fetchCorrelation();
    }, [datasetId]);

    if (loading) return (
        <div className="flex items-center justify-center h-64 bg-slate-900/50 rounded-xl animate-pulse">
            <div className="text-slate-400 text-sm font-medium">Computing Correlation Matrix...</div>
        </div>
    );

    if (error || !data || !data.columns.length) return (
        <div className="flex items-center justify-center h-64 bg-slate-900/50 rounded-xl border border-dashed border-slate-700">
            <div className="text-slate-500 text-sm">No correlation data available for this dataset.</div>
        </div>
    );

    const { columns, matrix } = data;

    const getColor = (value) => {
        // Red for negative, Blue for positive, White for zero
        const abs = Math.abs(value);
        if (value > 0) return `rgba(59, 130, 246, ${abs})`; // Blue-500
        if (value < 0) return `rgba(239, 68, 68, ${abs})`;   // Red-500
        return 'rgba(30, 41, 59, 0.5)';
    };

    return (
        <motion.div
            layout
            className={`relative bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-800 p-6 flex flex-col ${isMaximized ? 'fixed inset-4 z-50' : 'h-full'}`}
        >
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                        {title}
                        <div className="group relative">
                            <Info size={14} className="text-slate-500 cursor-help" />
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-slate-800 text-xs text-slate-300 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 border border-slate-700 shadow-xl">
                                Calculates Pearson correlation (-1 to +1) between all numeric variables.
                            </div>
                        </div>
                    </h3>
                    <p className="text-xs text-slate-500 mt-1">Based on {data.sample_size} observations</p>
                </div>
                <div className="flex items-center gap-2">
                    <button className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors">
                        <Download size={18} />
                    </button>
                    <button
                        onClick={() => setIsMaximized(!isMaximized)}
                        className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors"
                    >
                        {isMaximized ? <X size={18} /> : <Maximize2 size={18} />}
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto custom-scrollbar">
                <div
                    className="grid"
                    style={{
                        gridTemplateColumns: `auto repeat(${columns.length}, 1fr)`,
                        minWidth: columns.length * 60 + 100
                    }}
                >
                    {/* Header Spacer */}
                    <div className="h-10"></div>
                    {/* Top Labels */}
                    {columns.map((col, i) => (
                        <div key={`header-${i}`} className="h-10 text-[10px] text-slate-400 font-medium px-1 flex items-end justify-center text-center transform -rotate-45 origin-bottom-left truncate max-w-[80px]">
                            {col.replace(/_/g, ' ')}
                        </div>
                    ))}

                    {/* Matrix Rows */}
                    {matrix.map((row, i) => (
                        <React.Fragment key={`row-${i}`}>
                            {/* Side Label */}
                            <div className="pr-4 py-2 text-xs text-slate-400 font-medium flex items-center justify-end text-right border-r border-slate-800/50 truncate max-w-[120px]">
                                {columns[i].replace(/_/g, ' ')}
                            </div>
                            {/* Cells */}
                            {row.map((val, j) => (
                                <motion.div
                                    key={`cell-${i}-${j}`}
                                    initial={{ scale: 0.9, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    transition={{ delay: (i + j) * 0.01 }}
                                    onMouseEnter={() => setHoveredCell({ r: i, c: j, val })}
                                    onMouseLeave={() => setHoveredCell(null)}
                                    className="aspect-square m-0.5 rounded-md relative flex items-center justify-center group cursor-pointer"
                                    style={{ backgroundColor: getColor(val) }}
                                >
                                    {Math.abs(val) > 0.4 && (
                                        <span className={`text-[10px] font-bold ${Math.abs(val) > 0.7 ? 'text-white' : 'text-slate-900 opacity-50'}`}>
                                            {val.toFixed(2)}
                                        </span>
                                    )}

                                    {/* Tooltip */}
                                    {hoveredCell?.r === i && hoveredCell?.c === j && (
                                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 p-2 bg-slate-950 text-[10px] text-white rounded shadow-2xl z-20 whitespace-nowrap pointer-events-none border border-slate-800">
                                            <div className="font-bold text-blue-400">{columns[i]} × {columns[j]}</div>
                                            <div className="mt-1">Correlation: <span className={val > 0 ? 'text-blue-400' : 'text-red-400'}>{val.toFixed(4)}</span></div>
                                            <div className="text-slate-500 uppercase tracking-tighter mt-0.5">
                                                {Math.abs(val) > 0.7 ? 'Strong' : Math.abs(val) > 0.3 ? 'Moderate' : 'Weak'} {val > 0 ? 'Positive' : 'Negative'}
                                            </div>
                                        </div>
                                    )}
                                </motion.div>
                            ))}
                        </React.Fragment>
                    ))}
                </div>
            </div>

            {/* Legend */}
            <div className="mt-6 flex items-center justify-center gap-8 text-[10px] text-slate-500 font-medium border-t border-slate-800 pt-4">
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-red-500"></div>
                    <span>Strong Negative (-1.0)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-slate-800"></div>
                    <span>No Correlation (0.0)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-blue-500"></div>
                    <span>Strong Positive (1.0)</span>
                </div>
            </div>
        </motion.div>
    );
};

export default CorrelationMatrix;
