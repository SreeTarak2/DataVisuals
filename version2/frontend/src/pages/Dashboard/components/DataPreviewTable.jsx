/**
 * DataPreviewTable Component — Professional SaaS Edition
 * 
 * Features:
 *  • Precision Column Type Detection
 *  • Smart Value Formatting (Currency, Date, Boolean, Numeric)
 *  • Global search & Per-column filters
 *  • Responsive horizontal scroll with sticky headers
 *  • Enterprise pagination controls
 *  • Theme-aware styling (Light/Dark)
 */

import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  BarChart3,
  RefreshCw,
  Search,
  Download,
  ChevronsLeft,
  ChevronsRight,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  X,
  Filter,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Hash,
  Calendar,
  ToggleLeft,
  Type,
  Check,
  XCircle,
  MoreVertical,
  Copy,
  Table as TableIcon
} from 'lucide-react';
import { toast } from 'react-hot-toast';

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200];

// ─── Helpers ─────────────────────────────────────────────────────────────────

const formatCell = (val, type) => {
  if (val === null || val === undefined) return { display: '—', type: 'null' };

  if (type === 'boolean' || typeof val === 'boolean') {
    return {
      display: !!val,
      type: 'boolean',
    };
  }

  if (type === 'number' || typeof val === 'number') {
    const num = typeof val === 'number' ? val : Number(val);
    if (isNaN(num)) return { display: String(val), type: 'string' };
    
    // Smart formatting for numbers
    if (Math.abs(num) > 1000000) {
      return {
        display: (num / 1000000).toLocaleString(undefined, { maximumFractionDigits: 2 }) + 'M',
        type: 'number'
      };
    }
    
    return {
      display: Number.isInteger(num) ? num.toLocaleString() : num.toLocaleString(undefined, { maximumFractionDigits: 4 }),
      type: 'number',
    };
  }

  const s = String(val);

  if (type === 'date') {
    try {
      const date = new Date(val);
      if (!isNaN(date.getTime())) {
        return {
          display: date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }),
          type: 'date',
        };
      }
    } catch {
      // Fallback to string
    }
  }

  return {
    display: s.length > 120 ? s.slice(0, 117) + '…' : s,
    type: 'string',
  };
};

const numericCoerce = (v) => {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

const detectColumnType = (columnName, rows) => {
  const sampleSize = Math.min(rows.length, 50);
  const values = rows.slice(0, sampleSize).map((r) => r[columnName]).filter((v) => v !== null && v !== undefined);
  
  if (values.length === 0) return 'string';

  // Check for booleans
  const boolValues = ['true', 'false', 'True', 'False', 'TRUE', 'FALSE', true, false];
  const boolCount = values.filter((v) => boolValues.includes(v)).length;
  if (boolCount / values.length > 0.8) return 'boolean';

  // Check for numbers
  const numCount = values.filter((v) => typeof v === 'number' || (!isNaN(parseFloat(v)) && isFinite(v))).length;
  if (numCount / values.length > 0.8) return 'number';

  // Check for dates
  const datePatterns = [
    /^\d{4}-\d{2}-\d{2}$/,
    /^\d{2}\/\d{2}\/\d{4}$/,
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/,
  ];
  const dateCount = values.filter((v) => {
    const s = String(v);
    return datePatterns.some((p) => p.test(s)) && !isNaN(new Date(v).getTime());
  }).length;
  if (dateCount / values.length > 0.7) return 'date';

  return 'string';
};

const getColumnTypeIcon = (type) => {
  switch (type) {
    case 'number':
      return <Hash className="w-3 h-3" />;
    case 'date':
      return <Calendar className="w-3 h-3" />;
    case 'boolean':
      return <ToggleLeft className="w-3 h-3" />;
    default:
      return <Type className="w-3 h-3" />;
  }
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
  const [isPageSizeOpen, setIsPageSizeOpen] = useState(false);

  const searchRef = useRef(null);
  const dropdownRef = useRef(null);

  // Keyboard shortcuts
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

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsPageSizeOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Reset page when filters change
  useEffect(() => {
    setPage(0);
  }, [globalSearch, columnFilters, sortCol, sortDir, pageSize]);

  const columns = useMemo(
    () => Object.keys((dataPreview && dataPreview[0]) || {}),
    [dataPreview]
  );

  const columnTypes = useMemo(() => {
    if (!dataPreview || dataPreview.length === 0) return {};
    const types = {};
    columns.forEach((col) => {
      types[col] = detectColumnType(col, dataPreview);
    });
    return types;
  }, [columns, dataPreview]);

  // Process data
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
        const colType = columnTypes[sortCol];

        let cmp;
        if (colType === 'number' && aNum !== null && bNum !== null) {
          cmp = aNum - bNum;
        } else {
          cmp = String(aVal).localeCompare(String(bVal), undefined, { numeric: true, sensitivity: 'base' });
        }
        return sortDir === 'desc' ? -cmp : cmp;
      });
    }

    return rows;
  }, [dataPreview, globalSearch, columnFilters, sortCol, sortDir, columns, columnTypes]);

  const totalFilteredRows = processedData.length;
  const totalPages = Math.max(1, Math.ceil(totalFilteredRows / pageSize));
  const pagedData = useMemo(
    () => processedData.slice(page * pageSize, (page + 1) * pageSize),
    [processedData, page, pageSize]
  );

  const handleSort = useCallback(
    (col) => {
      if (sortCol === col) {
        if (sortDir === 'asc') setSortDir('desc');
        else {
          setSortCol(null);
          setSortDir('asc');
        }
      } else {
        setSortCol(col);
        setSortDir('asc');
      }
    },
    [sortCol, sortDir]
  );

  const handleCopyCell = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Value copied', { duration: 1500, style: { fontSize: '12px' } });
  };

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
    toast.success('CSV Exported');
  }, [processedData, columns]);

  const SortIcon = ({ col }) => {
    if (sortCol !== col)
      return <ArrowUpDown className="w-3.5 h-3.5 opacity-0 group-hover/th:opacity-50 transition-opacity" />;
    if (sortDir === 'asc') return <ArrowUp className="w-3.5 h-3.5 text-accent-primary" />;
    return <ArrowDown className="w-3.5 h-3.5 text-accent-primary" />;
  };

  if (loading) {
    return (
      <div className="data-table-container min-h-[400px] flex flex-col">
        <div className="data-table-toolbar animate-pulse">
           <div className="h-10 w-48 bg-white/5 rounded-lg" />
           <div className="h-10 w-64 bg-white/5 rounded-lg" />
        </div>
        <div className="flex-grow p-4 space-y-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-10 w-full bg-white/5 rounded-md animate-pulse" style={{ opacity: 1 - i*0.1 }} />
          ))}
        </div>
      </div>
    );
  }

  if (!dataPreview || dataPreview.length === 0) {
    return (
      <div className="data-table-container min-h-[300px] flex flex-col items-center justify-center p-10 text-center">
        <div className="p-4 rounded-2xl bg-white/5 mb-4">
           <TableIcon className="w-8 h-8 text-muted" />
        </div>
        <h3 className="text-lg font-semibold text-header mb-1">No data available</h3>
        <p className="text-sm text-muted max-w-xs mb-6">Connect a dataset or upload a file to begin analyzing your data.</p>
        {onReload && (
           <button className="btn-primary" onClick={onReload}>
             <RefreshCw className="w-4 h-4 mr-2" />
             Reload Dataset
           </button>
        )}
      </div>
    );
  }

  const activeFilterCount = (globalSearch.trim() ? 1 : 0) + Object.values(columnFilters).filter((v) => v.trim()).length;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }}
      className="data-table-container flex flex-col shadow-2xl"
    >
      {/* ── Toolbar ── */}
      <div className="data-table-toolbar glass-modern sticky top-0 z-30">
        <div className="flex items-center gap-4">
          <div className="data-table-title-icon hidden sm:flex">
            <TableIcon className="w-4 h-4" />
          </div>
          <div className="data-table-title-text">
            <h2>Data Preview</h2>
            <p className="text-micro">
              {totalFilteredRows.toLocaleString()} rows visible 
              {totalRows ? ` • ${totalRows.toLocaleString()} total` : ''}
            </p>
          </div>
        </div>

        <div className="data-table-actions">
          <div className="data-table-search group">
            <Search className="data-table-search-icon w-3.5 h-3.5 group-focus-within:text-accent-primary transition-colors" />
            <input
              ref={searchRef}
              type="text"
              placeholder="Quick search... (Ctrl+F)"
              value={globalSearch}
              onChange={(e) => setGlobalSearch(e.target.value)}
              className="data-table-search-input"
            />
            {globalSearch && (
              <button onClick={() => setGlobalSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 hover:text-header transition-colors">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-1.5 ml-2 border-l border-white/10 pl-3">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`data-table-btn ${showFilters || activeFilterCount > 0 ? 'active' : ''}`}
              title="Filter columns"
            >
              <Filter className="w-4 h-4" />
              {activeFilterCount > 0 && <span className="data-table-badge">{activeFilterCount}</span>}
            </button>

            <button onClick={exportCSV} className="data-table-btn" title="Export CSV">
              <Download className="w-4 h-4" />
            </button>

            {onReload && (
              <button onClick={onReload} className="data-table-btn" title="Refresh">
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Table Grid ── */}
      <div className="flex-grow overflow-auto relative studio-scrollbar">
        <table className="data-table w-full border-separate border-spacing-0">
          <thead className="sticky top-0 z-20">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className={`group/th sortable border-b border-border py-4 px-6 ${sortCol === col ? 'bg-white/[0.03]' : ''}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5 overflow-hidden">
                      <div className={`p-1 rounded-md ${
                        columnTypes[col] === 'number' ? 'bg-blue-500/10 text-blue-400' :
                        columnTypes[col] === 'date' ? 'bg-amber-500/10 text-amber-400' :
                        columnTypes[col] === 'boolean' ? 'bg-emerald-500/10 text-emerald-400' :
                        'bg-white/5 text-muted'
                      }`}>
                        {getColumnTypeIcon(columnTypes[col])}
                      </div>
                      <span className="font-semibold text-[13px] tracking-tight truncate text-header">{col}</span>
                    </div>
                    <SortIcon col={col} />
                  </div>
                </th>
              ))}
            </tr>

            {/* Filter Row */}
            <AnimatePresence>
              {showFilters && (
                <motion.tr
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="bg-surface/80 backdrop-blur-md"
                >
                  {columns.map((col) => (
                    <th key={`filter-${col}`} className="px-4 py-2 border-b border-border">
                      <input
                        type="text"
                        placeholder={`Filter ${col}...`}
                        value={columnFilters[col] || ''}
                        onChange={(e) => setColumnFilters(prev => ({ ...prev, [col]: e.target.value }))}
                        className="w-full bg-white/5 border border-white/10 rounded-md py-1.5 px-3 text-[12px] focus:border-accent-primary outline-none transition-all placeholder:text-muted/50"
                      />
                    </th>
                  ))}
                </motion.tr>
              )}
            </AnimatePresence>
          </thead>

          <tbody className="divide-y divide-white/[0.04]">
            {pagedData.length > 0 ? (
              pagedData.map((row, idx) => (
                <tr key={idx} className="hover:bg-white/[0.02] transition-colors group/tr">
                  {columns.map((col) => {
                    const { display, type } = formatCell(row[col], columnTypes[col]);
                    return (
                      <td
                        key={col}
                        className={`py-3.5 px-6 whitespace-nowrap text-[13px] relative ${
                          type === 'number' ? 'text-right font-mono' : ''
                        }`}
                        onDoubleClick={() => handleCopyCell(String(row[col]))}
                      >
                        {type === 'boolean' ? (
                          <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium border ${
                            row[col] 
                              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                              : 'bg-red-500/10 border-red-500/20 text-red-400'
                          }`}>
                            {row[col] ? <Check className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                            {String(row[col])}
                          </div>
                        ) : type === 'null' ? (
                          <span className="text-muted/40 italic">null</span>
                        ) : (
                          <span className={`${type === 'number' ? 'text-blue-400/80' : 'text-secondary'} group-hover/tr:text-header transition-colors`}>
                            {display}
                          </span>
                        )}
                        
                        <button 
                          onClick={() => handleCopyCell(String(row[col]))}
                          className="absolute right-1 top-1/2 -translate-y-1/2 p-1 opacity-0 group-hover:opacity-100 hover:bg-white/10 rounded-md transition-all z-10"
                        >
                          <Copy className="w-3 h-3 text-muted" />
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="py-20 text-center text-muted text-sm italic">
                  No matches found for your current filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination Footer ── */}
      <div className="data-table-footer glass-modern border-t border-border px-6 py-4">
        <div className="flex items-center gap-6 text-[12px] text-muted font-medium">
          <div className="flex items-center gap-3">
            <span className="opacity-70">Show</span>
            <div className="relative" ref={dropdownRef}>
              <button 
                onClick={() => setIsPageSizeOpen(!isPageSizeOpen)}
                className="flex items-center gap-4 bg-white/5 border border-white/10 hover:border-accent-primary/50 rounded-lg py-1.5 px-3 transition-all duration-200 group min-w-[70px] justify-between"
              >
                <span className="text-[12px] font-bold text-header">{pageSize}</span>
                <ChevronDown className={`w-3 h-3 text-muted group-hover:text-header transition-transform duration-300 ${isPageSizeOpen ? 'rotate-180' : ''}`} />
              </button>
              
              <AnimatePresence>
                {isPageSizeOpen && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: -4, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute bottom-full left-0 mb-2 min-w-[80px] glass-modern border border-white/10 rounded-xl overflow-hidden z-50 shadow-2xl"
                  >
                    {PAGE_SIZE_OPTIONS.map((opt) => (
                      <button
                        key={opt}
                        onClick={() => {
                          setPageSize(opt);
                          setIsPageSizeOpen(false);
                        }}
                        className={`w-full text-left px-4 py-2 text-[12px] transition-colors ${
                          pageSize === opt 
                            ? 'bg-accent-primary text-white' 
                            : 'hover:bg-white/10 text-muted hover:text-header'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <span className="opacity-70 whitespace-nowrap">rows per page</span>
          </div>
          <div className="h-4 w-[1px] bg-white/10 hidden sm:block" />
          <span className="hidden sm:block opacity-60">
             Showing {Math.min(totalFilteredRows, page * pageSize + 1)}-{Math.min(totalFilteredRows, (page + 1) * pageSize)} of {totalFilteredRows.toLocaleString()}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setPage(0)}
            disabled={page === 0}
            className="data-table-page-btn"
          >
            <ChevronsLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="data-table-page-btn"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-1 mx-2">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum;
              if (totalPages <= 5) pageNum = i;
              else if (page < 3) pageNum = i;
              else if (page > totalPages - 4) pageNum = totalPages - 5 + i;
              else pageNum = page - 2 + i;
              
              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`min-w-[32px] h-8 rounded-lg text-[12px] font-semibold transition-all ${
                    page === pageNum 
                      ? 'bg-accent-primary text-white shadow-lg shadow-accent-primary/20' 
                      : 'hover:bg-white/5 text-muted hover:text-header'
                  }`}
                >
                  {pageNum + 1}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="data-table-page-btn"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
          <button
            onClick={() => setPage(totalPages - 1)}
            disabled={page >= totalPages - 1}
            className="data-table-page-btn"
          >
            <ChevronsRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </motion.div>
  );
};

export default DataPreviewTable;
