/**
 * DataPreviewTable Component — Modern Data Grid Edition
 *
 * Enterprise-grade data table with:
 *  • Column type detection (number, date, boolean, string)
 *  • Smart sorting (numeric and text)
 *  • Global search across all columns
 *  • Per-column text filters
 *  • Client-side pagination (25 / 50 / 100 rows)
 *  • CSV export of filtered view
 *  • Smart value formatting
 *  • Light/Dark mode support
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
} from 'lucide-react';

const PAGE_SIZE_OPTIONS = [25, 50, 100];

// ─── Helpers ─────────────────────────────────────────────────────────────────

const formatCell = (val) => {
  if (val === null || val === undefined) return { display: '—', type: 'null' };

  if (typeof val === 'boolean') {
    return {
      display: val,
      type: 'boolean',
    };
  }

  if (typeof val === 'number') {
    return {
      display: Number.isInteger(val) ? val.toLocaleString() : val.toLocaleString(undefined, { maximumFractionDigits: 4 }),
      type: 'number',
    };
  }

  const s = String(val);

  // Check for date patterns
  const datePatterns = [
    /^\d{4}-\d{2}-\d{2}$/,
    /^\d{2}\/\d{2}\/\d{4}$/,
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/,
  ];
  for (const pattern of datePatterns) {
    if (pattern.test(s)) {
      try {
        const date = new Date(val);
        if (!isNaN(date.getTime())) {
          return {
            display: date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }),
            type: 'date',
          };
        }
      } catch {
        // Not a valid date
      }
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
  const values = rows.map((r) => r[columnName]).filter((v) => v !== null && v !== undefined);
  if (values.length === 0) return 'string';

  // Check for numbers
  const numCount = values.filter((v) => typeof v === 'number' || numericCoerce(v) !== null).length;
  if (numCount / values.length > 0.8) return 'number';

  // Check for booleans
  const boolValues = ['true', 'false', 'True', 'False', 'TRUE', 'FALSE', true, false, 'yes', 'no', 'Yes', 'No'];
  const boolCount = values.filter((v) => boolValues.includes(v)).length;
  if (boolCount / values.length > 0.8) return 'boolean';

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
  useEffect(() => {
    setPage(0);
  }, [globalSearch, columnFilters, sortCol, sortDir, pageSize]);

  // ─── Column Type Detection ────────────────────────────────────────────────

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

  // ─── Derived Data ──────────────────────────────────────────────────────────

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
          cmp = String(aVal).localeCompare(String(bVal), undefined, { sensitivity: 'base' });
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

  // ─── Handlers ─────────────────────────────────────────────────────────────

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
    try {
      if (a.parentNode === document.body) {
        document.body.removeChild(a);
      }
    } catch (err) {
      console.error('Failed to remove temporary export element', err);
    }
    URL.revokeObjectURL(url);
  }, [processedData, columns]);

  // ─── Sort Icon ─────────────────────────────────────────────────────────────

  const SortIcon = ({ col }) => {
    if (sortCol !== col)
      return <ArrowUpDown className="w-3.5 h-3.5 opacity-0 group-hover/th:opacity-50 transition-opacity" />;
    if (sortDir === 'asc') return <ArrowUp className="w-3.5 h-3.5" style={{ color: 'var(--accent-primary)' }} />;
    return <ArrowDown className="w-3.5 h-3.5" style={{ color: 'var(--accent-primary)' }} />;
  };

  // ─── Loading ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="data-table-container">
          <div className="data-table-toolbar">
            <div className="data-table-title">
              <div className="data-table-title-icon">
                <BarChart3 className="w-5 h-5" />
              </div>
              <div className="data-table-title-text">
                <h2>Data Preview</h2>
                <p>Loading your data...</p>
              </div>
            </div>
          </div>
          <div className="data-table-skeleton">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="data-table-skeleton-row">
                {[...Array(6)].map((_, j) => (
                  <div
                    key={j}
                    className="data-table-skeleton-cell"
                    style={{ width: `${80 + Math.random() * 100}px`, animationDelay: `${i * 0.1}s` }}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    );
  }

  // ─── Empty ─────────────────────────────────────────────────────────────────

  if (!dataPreview || dataPreview.length === 0) {
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="data-table-container">
          <div className="data-table-toolbar">
            <div className="data-table-title">
              <div className="data-table-title-icon">
                <BarChart3 className="w-5 h-5" />
              </div>
              <div className="data-table-title-text">
                <h2>Data Preview</h2>
                <p>No data to display</p>
              </div>
            </div>
            {onReload && (
              <button className="data-table-btn" onClick={onReload} title="Reload">
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
          </div>
          <div className="data-table-empty">
            <div className="data-table-empty-icon">
              <BarChart3 className="w-6 h-6" />
            </div>
            <h3>No data available</h3>
            <p>Upload a dataset to see your data here</p>
          </div>
        </div>
      </motion.div>
    );
  }

  const activeFilterCount =
    (globalSearch.trim() ? 1 : 0) + Object.values(columnFilters).filter((v) => v.trim()).length;

  // ─── Main ──────────────────────────────────────────────────────────────────

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
      <div className="data-table-container">
        {/* ── Toolbar ── */}
        <div className="data-table-toolbar">
          <div className="data-table-title">
            <div className="data-table-title-icon">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div className="data-table-title-text">
              <h2>Data Preview</h2>
              <p>
                {totalFilteredRows != null && dataPreview != null && dataPreview.length > 0
                  ? (totalFilteredRows !== dataPreview.length
                    ? `${totalFilteredRows.toLocaleString()} of ${dataPreview.length.toLocaleString()} rows`
                    : `${dataPreview.length.toLocaleString()} rows`)
                  : 'Loading...'}
                {totalRows ? ` (${totalRows.toLocaleString()} total)` : ''}
              </p>
            </div>
          </div>

          <div className="data-table-actions">
            {/* Search */}
            <div className="data-table-search">
              <Search className="data-table-search-icon w-4 h-4" />
              <input
                ref={searchRef}
                type="text"
                placeholder="Search... (Ctrl+F)"
                value={globalSearch}
                onChange={(e) => setGlobalSearch(e.target.value)}
                className="data-table-search-input"
              />
              {globalSearch && (
                <button
                  onClick={() => setGlobalSearch('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Filter toggle */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`data-table-btn ${showFilters || activeFilterCount > 0 ? 'active' : ''}`}
              title="Toggle column filters"
            >
              <Filter className="w-4 h-4" />
              {activeFilterCount > 0 && <span className="data-table-badge">{activeFilterCount}</span>}
            </button>

            {/* Clear all */}
            {activeFilterCount > 0 && (
              <button onClick={clearAllFilters} className="data-table-btn" title="Clear all filters">
                <X className="w-4 h-4" />
              </button>
            )}

            {/* CSV Export */}
            <button
              onClick={exportCSV}
              disabled={processedData.length === 0}
              className="data-table-btn"
              title="Export as CSV"
            >
              <Download className="w-4 h-4" />
            </button>

            {/* Reload */}
            {onReload && (
              <button onClick={onReload} className="data-table-btn" title="Reload data">
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* ── Table ── */}
        <div style={{ overflowX: 'auto', maxHeight: '600px', overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th
                    key={col}
                    onClick={() => handleSort(col)}
                    className={`sortable ${sortCol === col ? 'sorted' : ''}`}
                  >
                    <div className="data-table-th-content">
                      <span
                        className="col-type-icon"
                        style={{
                          backgroundColor:
                            columnTypes[col] === 'number'
                              ? 'rgba(47, 128, 237, 0.15)'
                              : columnTypes[col] === 'date'
                              ? 'rgba(242, 153, 74, 0.15)'
                              : columnTypes[col] === 'boolean'
                              ? 'rgba(187, 107, 217, 0.15)'
                              : 'var(--bg-surface)',
                          color:
                            columnTypes[col] === 'number'
                              ? 'var(--accent-primary)'
                              : columnTypes[col] === 'date'
                              ? 'var(--accent-warning)'
                              : columnTypes[col] === 'boolean'
                              ? 'var(--accent-purple)'
                              : 'var(--text-muted)',
                        }}
                      >
                        {getColumnTypeIcon(columnTypes[col])}
                      </span>
                      <span className="data-table-th-label">{col}</span>
                      <span className="data-table-th-icon">
                        <SortIcon col={col} />
                      </span>
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
                    className="data-table-filter-row"
                  >
                    {columns.map((col) => (
                      <th key={`filter-${col}`}>
                        <input
                          type="text"
                          placeholder="Filter..."
                          value={columnFilters[col] || ''}
                          onChange={(e) => handleColumnFilter(col, e.target.value)}
                          className="data-table-filter-input"
                        />
                      </th>
                    ))}
                  </motion.tr>
                )}
              </AnimatePresence>
            </thead>

            <tbody>
              {pagedData.length > 0 ? (
                pagedData.map((row, idx) => (
                  <tr key={idx}>
                    {columns.map((col) => {
                      const { display, type } = formatCell(row[col], columnTypes[col]);
                      return (
                        <td
                          key={col}
                          className={
                            type === 'number'
                              ? 'data-table-cell--number'
                              : type === 'date'
                              ? 'data-table-cell--date'
                              : type === 'null'
                              ? 'data-table-cell--null'
                              : ''
                          }
                          title={String(row[col] ?? '')}
                        >
                          {type === 'boolean' ? (
                            <span
                              className={`boolean-badge ${row[col] ? 'boolean-badge--true' : 'boolean-badge--false'}`}
                            >
                              {row[col] ? (
                                <>
                                  <Check className="w-3 h-3" /> True
                                </>
                              ) : (
                                <>
                                  <XCircle className="w-3 h-3" /> False
                                </>
                              )}
                            </span>
                          ) : (
                            display
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={columns.length}
                    style={{
                      textAlign: 'center',
                      padding: '40px 20px',
                      color: 'var(--text-muted)',
                    }}
                  >
                    No rows match your filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ── Pagination Footer ── */}
        <div className="data-table-footer">
          <div className="data-table-footer-info">
            <span>Show</span>
            <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
              {PAGE_SIZE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
            <span>rows per page</span>
          </div>

          <div className="data-table-pagination">
            <span
              style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
                marginRight: '8px',
              }}
            >
              Page {page + 1} of {totalPages}
            </span>
            <button
              onClick={() => setPage(0)}
              disabled={page === 0}
              className="data-table-page-btn"
              title="First page"
            >
              <ChevronsLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="data-table-page-btn"
              title="Previous page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            {/* Page numbers */}
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum;
              if (totalPages <= 5) {
                pageNum = i;
              } else if (page < 3) {
                pageNum = i;
              } else if (page > totalPages - 4) {
                pageNum = totalPages - 5 + i;
              } else {
                pageNum = page - 2 + i;
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`data-table-page-btn ${page === pageNum ? 'active' : ''}`}
                >
                  {pageNum + 1}
                </button>
              );
            })}

            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="data-table-page-btn"
              title="Next page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage(totalPages - 1)}
              disabled={page >= totalPages - 1}
              className="data-table-page-btn"
              title="Last page"
            >
              <ChevronsRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default DataPreviewTable;
