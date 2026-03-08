/**
 * FilterBar — Allows users to apply subset filters on the insights endpoint.
 * Parses dataset columns and lets users pick column:value pairs.
 * Displays active filters as removable chips.
 */
import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Filter, X, Plus, ChevronDown, SlidersHorizontal } from 'lucide-react';
import { cn } from '../../../lib/utils';

const FilterChip = ({ column, value, onRemove }) => (
    <motion.span
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-violet-500/15 text-violet-300 border border-violet-500/25 rounded-lg text-xs font-medium"
    >
        <span className="text-slate-400">{column}:</span>
        <span className="font-semibold">{value}</span>
        <button
            onClick={onRemove}
            className="ml-0.5 p-0.5 hover:bg-violet-500/20 rounded transition-colors"
        >
            <X className="w-3 h-3" />
        </button>
    </motion.span>
);

const FilterBar = ({ appliedFilters = {}, filteredRowCount, onApplyFilters, onClearFilters, loading }) => {
    const [isAdding, setIsAdding] = useState(false);
    const [column, setColumn] = useState('');
    const [value, setValue] = useState('');
    const inputRef = useRef(null);
    const activeCount = Object.keys(appliedFilters).length;

    useEffect(() => {
        if (isAdding && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isAdding]);

    const handleAdd = () => {
        const col = column.trim();
        const val = value.trim();
        if (!col || !val) return;

        const newFilters = { ...appliedFilters, [col]: val };
        const filterStr = Object.entries(newFilters)
            .map(([k, v]) => `${k}:${v}`)
            .join(',');
        onApplyFilters(filterStr);
        setColumn('');
        setValue('');
        setIsAdding(false);
    };

    const handleRemove = (colToRemove) => {
        const newFilters = { ...appliedFilters };
        delete newFilters[colToRemove];
        if (Object.keys(newFilters).length === 0) {
            onClearFilters();
        } else {
            const filterStr = Object.entries(newFilters)
                .map(([k, v]) => `${k}:${v}`)
                .join(',');
            onApplyFilters(filterStr);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') handleAdd();
        if (e.key === 'Escape') { setIsAdding(false); setColumn(''); setValue(''); }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2 flex-wrap"
        >
            {/* Filter icon + label */}
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span className="font-medium">Filters</span>
            </div>

            {/* Active filter chips */}
            <AnimatePresence>
                {Object.entries(appliedFilters).map(([col, val]) => (
                    <FilterChip
                        key={col}
                        column={col}
                        value={val}
                        onRemove={() => handleRemove(col)}
                    />
                ))}
            </AnimatePresence>

            {/* Filtered row count */}
            {activeCount > 0 && filteredRowCount !== undefined && (
                <span className="text-[11px] text-slate-500 font-mono">
                    ({filteredRowCount.toLocaleString()} rows)
                </span>
            )}

            {/* Add filter inline form */}
            <AnimatePresence>
                {isAdding ? (
                    <motion.div
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: 'auto' }}
                        exit={{ opacity: 0, width: 0 }}
                        className="flex items-center gap-1.5 overflow-hidden"
                    >
                        <input
                            ref={inputRef}
                            type="text"
                            value={column}
                            onChange={(e) => setColumn(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="column"
                            className="w-24 px-2 py-1 text-xs bg-slate-800/80 border border-slate-700/60 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
                        />
                        <span className="text-slate-600 text-xs">:</span>
                        <input
                            type="text"
                            value={value}
                            onChange={(e) => setValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="value"
                            className="w-24 px-2 py-1 text-xs bg-slate-800/80 border border-slate-700/60 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
                        />
                        <button
                            onClick={handleAdd}
                            disabled={!column.trim() || !value.trim()}
                            className="px-2 py-1 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed font-medium"
                        >
                            Apply
                        </button>
                        <button
                            onClick={() => { setIsAdding(false); setColumn(''); setValue(''); }}
                            className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
                        >
                            <X className="w-3.5 h-3.5" />
                        </button>
                    </motion.div>
                ) : (
                    <motion.button
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        onClick={() => setIsAdding(true)}
                        disabled={loading}
                        className={cn(
                            'flex items-center gap-1 px-2 py-1 text-xs rounded-lg border transition-all',
                            loading
                                ? 'border-slate-800 text-slate-600 cursor-not-allowed'
                                : 'border-slate-700/50 text-slate-400 hover:text-slate-300 hover:border-slate-600 hover:bg-slate-800/40',
                        )}
                    >
                        <Plus className="w-3 h-3" />
                        Add filter
                    </motion.button>
                )}
            </AnimatePresence>

            {/* Clear all */}
            {activeCount > 0 && (
                <button
                    onClick={onClearFilters}
                    className="text-[11px] text-red-400/70 hover:text-red-400 transition-colors ml-1"
                >
                    Clear all
                </button>
            )}
        </motion.div>
    );
};

export default FilterBar;
