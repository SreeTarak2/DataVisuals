/**
 * DataPreviewTable Component — Interactive Edition
 *
 * Full-featured data table with:
 *  • Column sorting (asc / desc / none)
 *  • Global search across all columns
 *  • Per-column text filter
 *  • Client-side pagination (25 / 50 / 100 rows)
 *  • CSV export of filtered view
 *  • Smart value formatting (numbers, dates, nulls)
 *  • Keyboard shortcut: Ctrl+F focuses the search bar
 */

import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    BarChart3,
    RefreshCw,
    Search,
    Download,
    ChevronsLeft,
    ChevronsRight,
    ChevronLeft,
    ChevronRight,
    X,
    Filter,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
} from 'lucide-react';

// ─── Helpers ─────────────────────────────────────────────────────────────────

const PAGE_SIZE_OPTIONS = [25, 50, 100];

/** Pretty-print a cell value */
const formatCell = (val) => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'number') {
        if (Number.isInteger(val)) return val.toLocaleString();
        return val.toLocaleString(undefined, { maximumFractionDigits: 4 });
    }
    if (typeof val === 'boolean') return val ? 'true' : 'false';
    const s = String(val);
    return s.length > 120 ? s.slice(0, 117) + '…' : s;
};

/** Guess if a value is numeric for sorting purposes */
const numericCoerce = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
};

// ─── Component ───────────────────────────────────────────────────────────────

const DataPreviewTable = ({ dataPreview, loading, onReload, totalRows }) => {
    const [globalSearch, setGlobalSearch] = useState('');
    const [columnFilters, setColumnFilters] = useState({});
    const [sortCol, setSortCol] = useState(null);
    const [sortDir, setSortDir] = useState('asc');
    const [page, setPage] = useState(0);
    const [pageSize, setPageSize] = useState(25);
    const [showFilters, setShowFilters] = useState(false);

    const searchRef = useRef(null);

    // Ctrl+F / Cmd+F to focus search
    useEffect(() => {
        const handler = (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                searchRef.current?.focus();
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    // Reset page when filters change
    useEffect(() => { setPage(0); }, [globalSearch, columnFilters, sortCol, sortDir, pageSize]);

    // ─── Derived Data ────────────────────────────────────────────────────────

    const columns = useMemo(() => Object.keys((dataPreview && dataPreview[0]) || {}), [dataPreview]);

    const processedData = useMemo(() => {
        if (!dataPreview || dataPreview.length === 0) return [];

        let rows = [...dataPreview];

        // Global search
        if (globalSearch.trim()) {
            const q = globalSearch.toLowerCase();
            rows = rows.filter((row) =>
                columns.some((col) => {
                    const v = row[col];
                    return v !== null && v !== undefined && String(v).toLowerCase().includes(q);
                })
            );
        }

        // Per-column filters
        const activeFilters = Object.entries(columnFilters).filter(([, v]) => v.trim());
        if (activeFilters.length > 0) {
            rows = rows.filter((row) =>
                activeFilters.every(([col, filterVal]) => {
                    const v = row[col];
                    return v !== null && v !== undefined && String(v).toLowerCase().includes(filterVal.toLowerCase());
                })
            );
        }

        // Sort
        if (sortCol) {
            rows.sort((a, b) => {
                const aVal = a[sortCol];
                const bVal = b[sortCol];
                if (aVal == null && bVal == null) return 0;
                if (aVal == null) return 1;
                if (bVal == null) return -1;

                const aNum = numericCoerce(aVal);
                const bNum = numericCoerce(bVal);

                let cmp;
                if (aNum !== null && bNum !== null) {
                    cmp = aNum - bNum;
                } else {
                    cmp = String(aVal).localeCompare(String(bVal), undefined, { sensitivity: 'base' });
                }
                return sortDir === 'desc' ? -cmp : cmp;
            });
        }

        return rows;
    }, [dataPreview, globalSearch, columnFilters, sortCol, sortDir, columns]);

    const totalFilteredRows = processedData.length;
    const totalPages = Math.max(1, Math.ceil(totalFilteredRows / pageSize));
    const pagedData = useMemo(
        () => processedData.slice(page * pageSize, (page + 1) * pageSize),
        [processedData, page, pageSize]
    );

    // ─── Handlers ────────────────────────────────────────────────────────────

    const handleSort = useCallback(
        (col) => {
            if (sortCol === col) {
                if (sortDir === 'asc') setSortDir('desc');
                else { setSortCol(null); setSortDir('asc'); }
            } else {
                setSortCol(col);
                setSortDir('asc');
            }
        },
        [sortCol, sortDir]
    );

    const handleColumnFilter = useCallback((col, val) => {
        setColumnFilters((prev) => ({ ...prev, [col]: val }));
    }, []);

    const clearAllFilters = useCallback(() => {
        setGlobalSearch('');
        setColumnFilters({});
        setSortCol(null);
        setSortDir('asc');
    }, []);

    const exportCSV = useCallback(() => {
        if (processedData.length === 0) return;
        const csvRows = [
            columns.join(','),
            ...processedData.map((row) =>
                columns
                    .map((col) => {
                        const val = row[col];
                        if (val === null || val === undefined) return '';
                        const str = String(val);
                        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                            return `"${str.replace(/"/g, '""')}"`;
                        }
                        return str;
                    })
                    .join(',')
            ),
        ];
        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `data_export_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [processedData, columns]);

    // ─── Sort Icon ───────────────────────────────────────────────────────────

    const SortIcon = ({ col }) => {
        if (sortCol !== col) return <ArrowUpDown className="w-3 h-3 opacity-0 group-hover/th:opacity-40 transition-opacity" />;
        if (sortDir === 'asc') return <ArrowUp className="w-3 h-3 text-cyan-400" />;
        return <ArrowDown className="w-3 h-3 text-cyan-400" />;
    };

    // ─── Loading ─────────────────────────────────────────────────────────────

    if (loading) {
        return (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="group">
                <div className="bento-card p-6">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-8 h-8 bg-surface border border-ui-border shadow-sm rounded-lg flex items-center justify-center">
                            <BarChart3 className="w-5 h-5 text-status-success animate-pulse-skeleton" />
                        </div>
                        <h2 className="text-lg font-bold text-text-primary">Data Preview</h2>
                    </div>
                    <div className="space-y-3">
                        {[...Array(6)].map((_, i) => (
                            <div key={i} className="flex gap-4">
                                {[...Array(5)].map((_, j) => (
                                    <div key={j} className="h-4 rounded bg-ui-border animate-pulse-skeleton" style={{ width: `${60 + Math.random() * 80}px` }} />
                                ))}
                            </div>
                        ))}
                    </div>
                </div>
            </motion.div>
        );
    }

    // ─── Empty ───────────────────────────────────────────────────────────────

    if (!dataPreview || dataPreview.length === 0) {
        return (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="group">
                <div className="bento-card p-6">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-surface border border-ui-border shadow-sm rounded-lg flex items-center justify-center">
                                <BarChart3 className="w-5 h-5 text-status-success" />
                            </div>
                            <h2 className="text-lg font-bold text-text-primary">Data Preview</h2>
                        </div>
                        {onReload && (
                            <button onClick={onReload} className="p-2 rounded-lg bg-base-bg/50 hover:bg-ui-border text-text-secondary hover:text-text-primary transition-all" title="Reload">
                                <RefreshCw className="w-4 h-4" />
                            </button>
                        )}
                    </div>
                    <div className="text-center py-12 text-text-secondary">
                        <div className="w-12 h-12 bg-base-bg rounded-lg flex items-center justify-center mx-auto mb-4 border border-ui-border shadow-sm">
                            <BarChart3 className="w-6 h-6 opacity-50 text-text-secondary" />
                        </div>
                        <p className="text-sm">No data preview available</p>
                        <p className="text-xs mt-1 text-text-secondary/70">Upload a dataset to see your data here</p>
                    </div>
                </div>
            </motion.div>
        );
    }

    const activeFilterCount = (globalSearch.trim() ? 1 : 0) + Object.values(columnFilters).filter((v) => v.trim()).length;

    // ─── Main ────────────────────────────────────────────────────────────────

    return (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="group">
            <div className="bento-card overflow-hidden">
                {/* ── Toolbar ── */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 px-5 pt-5 pb-3">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-surface border border-ui-border shadow-sm rounded-lg flex items-center justify-center">
                            <BarChart3 className="w-5 h-5 text-status-success" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-text-primary">Data Preview</h2>
                            <p className="text-xs text-text-secondary">
                                {totalFilteredRows !== dataPreview.length
                                    ? `${totalFilteredRows} of ${dataPreview.length} rows`
                                    : `${dataPreview.length} rows`}
                                {totalRows ? ` (${totalRows.toLocaleString()} total in dataset)` : ''}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                        {/* Search */}
                        <div className="relative">
                            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-secondary" />
                            <input
                                ref={searchRef}
                                type="text"
                                placeholder="Search… (Ctrl+F)"
                                value={globalSearch}
                                onChange={(e) => setGlobalSearch(e.target.value)}
                                className="w-48 pl-8 pr-8 py-1.5 text-xs rounded-lg bg-base-bg border border-ui-border text-text-primary placeholder-text-secondary/70 focus:outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-all"
                            />
                            {globalSearch && (
                                <button onClick={() => setGlobalSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary">
                                    <X className="w-3 h-3" />
                                </button>
                            )}
                        </div>

                        {/* Filter toggle */}
                        <button
                            onClick={() => setShowFilters(!showFilters)}
                            className={`p-1.5 rounded-lg border text-xs flex items-center gap-1.5 transition-all ${showFilters || activeFilterCount > 0
                                ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400'
                                : 'bg-slate-800/50 border-slate-700/50 text-slate-400 hover:text-slate-300 hover:bg-slate-700/50'
                                }`}
                            title="Toggle column filters"
                        >
                            <Filter className="w-3.5 h-3.5" />
                            {activeFilterCount > 0 && (
                                <span className="text-[10px] bg-cyan-500/20 text-cyan-300 px-1.5 rounded-full">{activeFilterCount}</span>
                            )}
                        </button>

                        {/* Clear all */}
                        {activeFilterCount > 0 && (
                            <button onClick={clearAllFilters} className="p-1.5 rounded-lg bg-surface border border-ui-border text-text-secondary hover:text-status-critical hover:border-status-critical/30 transition-all text-xs" title="Clear all filters">
                                <X className="w-3.5 h-3.5" />
                            </button>
                        )}

                        {/* CSV Export */}
                        <button
                            onClick={exportCSV}
                            disabled={processedData.length === 0}
                            className="p-1.5 rounded-lg bg-surface border border-ui-border text-text-secondary hover:text-status-success hover:border-status-success/30 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                            title="Export filtered data as CSV"
                        >
                            <Download className="w-3.5 h-3.5" />
                        </button>

                        {/* Reload */}
                        {onReload && (
                            <button onClick={onReload} className="p-1.5 rounded-lg bg-surface border border-ui-border text-text-secondary hover:text-text-primary hover:bg-base-bg transition-all" title="Reload data">
                                <RefreshCw className="w-3.5 h-3.5" />
                            </button>
                        )}
                    </div>
                </div>

                {/* ── Table ── */}
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left border-collapse">
                        <thead>
                            <tr className="border-y border-ui-border bg-surface">
                                {columns.map((col) => (
                                    <th
                                        key={col}
                                        onClick={() => handleSort(col)}
                                        className="group/th py-2.5 px-4 text-xs font-semibold text-text-secondary uppercase tracking-wider cursor-pointer select-none hover:bg-base-bg transition-colors whitespace-nowrap"
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <span className="truncate max-w-[160px]">{col}</span>
                                            <SortIcon col={col} />
                                        </div>
                                    </th>
                                ))}
                            </tr>

                            {/* Per-column filters */}
                            <AnimatePresence>
                                {showFilters && (
                                    <motion.tr
                                        initial={{ opacity: 0, height: 0 }}
                                        animate={{ opacity: 1, height: 'auto' }}
                                        exit={{ opacity: 0, height: 0 }}
                                        className="border-b border-ui-border bg-base-bg/50"
                                    >
                                        {columns.map((col) => (
                                            <th key={`filter-${col}`} className="px-3 py-1.5">
                                                <input
                                                    type="text"
                                                    placeholder="Filter…"
                                                    value={columnFilters[col] || ''}
                                                    onChange={(e) => handleColumnFilter(col, e.target.value)}
                                                    className="w-full px-2 py-1 text-xs rounded bg-surface border border-ui-border text-text-primary placeholder-text-secondary focus:outline-none focus:border-cyan-500/40 transition-all"
                                                />
                                            </th>
                                        ))}
                                    </motion.tr>
                                )}
                            </AnimatePresence>
                        </thead>

                        <tbody className="divide-y divide-ui-border">
                            {pagedData.length > 0 ? (
                                pagedData.map((row, idx) => (
                                    <tr key={idx} className="hover:bg-base-bg transition-colors bg-surface">
                                        {columns.map((col) => (
                                            <td
                                                key={col}
                                                className="py-2.5 px-4 text-xs text-text-primary whitespace-nowrap max-w-[240px] truncate"
                                                title={row[col] !== null && row[col] !== undefined ? String(row[col]) : ''}
                                            >
                                                {formatCell(row[col])}
                                            </td>
                                        ))}
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={columns.length} className="text-center py-10 text-text-secondary text-sm bg-surface">
                                        No rows match your filters
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* ── Pagination Footer ── */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-5 py-3 border-t border-ui-border bg-surface">
                    <div className="flex items-center gap-2 text-xs text-text-secondary">
                        <span>Show</span>
                        <select
                            value={pageSize}
                            onChange={(e) => setPageSize(Number(e.target.value))}
                            className="bg-base-bg border border-ui-border rounded px-2 py-1 text-text-primary focus:outline-none focus:border-cyan-500/40 text-xs"
                        >
                            {PAGE_SIZE_OPTIONS.map((opt) => (
                                <option key={opt} value={opt}>{opt}</option>
                            ))}
                        </select>
                        <span>rows per page</span>
                    </div>

                    <div className="flex items-center gap-1.5">
                        <span className="text-xs text-text-secondary mr-2">
                            Page <span className="tabular-nums">{page + 1}</span> of <span className="tabular-nums">{totalPages}</span>
                        </span>
                        <button onClick={() => setPage(0)} disabled={page === 0} className="p-1 rounded hover:bg-base-bg border border-transparent hover:border-ui-border text-text-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-all" title="First page">
                            <ChevronsLeft className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} className="p-1 rounded hover:bg-base-bg border border-transparent hover:border-ui-border text-text-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-all" title="Previous page">
                            <ChevronLeft className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="p-1 rounded hover:bg-base-bg border border-transparent hover:border-ui-border text-text-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-all" title="Next page">
                            <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1} className="p-1 rounded hover:bg-base-bg border border-transparent hover:border-ui-border text-text-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-all" title="Last page">
                            <ChevronsRight className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>
            </div>
        </motion.div>
    );
};

export default DataPreviewTable;

