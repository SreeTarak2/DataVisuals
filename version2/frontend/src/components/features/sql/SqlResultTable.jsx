import React, { memo, useState, useMemo, useCallback } from 'react';
import { Table2, Loader2, Search, Download, Copy, Filter, Wrench, Terminal, Check } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';

/**
 * SqlResultTable — Displays SQL query results in a clean, interactive data grid
 */

const formatValue = (value) => {
  if (value === null || value === undefined) {
    return <span className="text-muted/30 italic font-mono select-none">null</span>;
  }
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return value.toLocaleString();
    return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  if (typeof value === 'boolean') {
    return (
      <span className={cn(
        "px-1.5 py-0.5 rounded text-[10px] font-bold font-mono uppercase tracking-wider",
        value ? "text-emerald-400 bg-emerald-500/10" : "text-rose-400 bg-rose-500/10"
      )}>
        {value ? 'true' : 'false'}
      </span>
    );
  }
  return String(value);
};

const SqlResultTable = memo(({
  columns = [],
  rows = [],
  rowCount = 0,
  executionTimeMs,
  error = null,
  isLoading = false,
  className,
  onFix,
  isFixing = false,
  isInitial = false,
  rowLimit, // applied LIMIT from the toolbar (optional)
}) => {
  const [filterQuery, setFilterQuery] = useState('');
  const [hoveredCell, setHoveredCell] = useState(null);
  const [copiedCell, setCopiedCell] = useState(null);

  const displayColumns = useMemo(() => {
    if (columns.length > 0) return columns;
    if (rows[0]) return Object.keys(rows[0]);
    return [];
  }, [columns, rows]);

  // Client-side search filtering
  const filteredRows = useMemo(() => {
    if (!filterQuery.trim()) return rows;
    const query = filterQuery.toLowerCase();
    return rows.filter(row => 
      displayColumns.some(col => {
        const key = typeof col === 'string' ? col : (col.key || col);
        const val = row[key];
        if (val === null || val === undefined) return false;
        return String(val).toLowerCase().includes(query);
      })
    );
  }, [rows, filterQuery, displayColumns]);

  // Export to CSV (RFC 4180 compliant)
  const handleExportCSV = () => {
    try {
      if (!rows.length) return;
      const headers = displayColumns.map(col => typeof col === 'string' ? col : (col.key || col || ''));

      // RFC 4180: always quote headers, use \r\n line endings
      const escapeCell = (val) => {
        if (val === null || val === undefined) return '""';
        const str = String(val);
        // Always quote — guarantees correctness for commas, quotes, and embedded newlines
        return `"${str.replace(/"/g, '""')}"`;
      };

      const rows_csv = rows.map(row =>
        headers.map(header => escapeCell(row[header])).join(',')
      );

      const csvContent = [
        headers.map(escapeCell).join(','),
        ...rows_csv,
      ].join('\r\n');

      const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `query_results_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Results exported as CSV');
    } catch (err) {
      toast.error('Failed to export CSV');
    }
  };

  // Copy a single cell value to clipboard
  const handleCopyCell = useCallback(async (value, rowIdx, colKey) => {
    try {
      const text = value === null || value === undefined ? '' : String(value);
      await navigator.clipboard.writeText(text);
      setCopiedCell(`${rowIdx}-${colKey}`);
      setTimeout(() => setCopiedCell(null), 1200);
    } catch (err) {
      // Fallback for restricted contexts
      toast.error('Could not copy cell');
    }
  }, []);

  // Copy JSON to clipboard
  const handleCopyJSON = () => {
    try {
      if (!rows.length) return;
      navigator.clipboard.writeText(JSON.stringify(rows, null, 2));
      toast.success('Results copied to clipboard as JSON');
    } catch (err) {
      toast.error('Failed to copy results');
    }
  };

  if (isInitial) {
    return (
      <div className={cn('sql-result-empty flex items-start justify-start h-full w-full bg-surface px-4 py-4 select-none', className)}>
        <span className="text-[12px] text-muted/50 font-medium">
          Click <strong className="text-muted/70 font-semibold font-sans">Run</strong> to execute your query
        </span>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-3 h-full w-full bg-surface p-12 text-center select-none', className)}>
        <div className="flex flex-col items-center gap-2">
          <Loader2 size={16} className="animate-spin text-accent-primary" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted/60">Executing query...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('sql-result-error p-4 bg-surface h-full w-full overflow-y-auto', className)}>
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-4.5 rounded-2xl bg-rose-500/[0.02] border border-rose-500/15 max-w-3xl mx-auto shadow-sm shadow-rose-500/[0.01]">
          <div className="flex items-start gap-3 min-w-0 flex-1">
            <div className="w-5 h-5 rounded-lg bg-rose-500/10 flex items-center justify-center shrink-0 border border-rose-500/10">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse" />
            </div>
            <div className="min-w-0 flex-1">
              <h4 className="text-[10.5px] font-bold text-rose-400 uppercase tracking-wider mb-2">Query Error</h4>
              <div className="text-xs text-rose-300/80 font-mono leading-relaxed break-all bg-rose-950/20 p-3 rounded-xl border border-rose-500/10 max-h-36 overflow-y-auto studio-scrollbar">
                {error}
              </div>
            </div>
          </div>
          {onFix && (
            <button
              onClick={onFix}
              disabled={isFixing}
              className="shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-accent-primary/30 hover:border-accent-primary bg-accent-primary/[0.04] hover:bg-accent-primary/[0.08] text-accent-primary text-[10.5px] font-bold transition-all disabled:opacity-30 active:scale-[0.98]"
            >
              {isFixing ? (
                <Loader2 size={11} className="animate-spin" />
              ) : (
                <Wrench size={11} />
              )}
              <span>Debug with AI</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!rows.length) {
    return (
      <div className={cn('sql-result-empty flex items-center justify-center h-full w-full bg-surface p-12 text-center select-none', className)}>
        <div className="flex flex-col items-center gap-3 max-w-xs mx-auto text-muted">
          <div className="w-9 h-9 rounded-xl bg-elevated/10 flex items-center justify-center border border-border/40">
            <Table2 size={14} className="opacity-60 text-muted" />
          </div>
          <div>
            <h4 className="text-[11px] font-bold text-header uppercase tracking-wider mb-1">No rows returned</h4>
            <p className="text-[10.5px] text-muted/65 leading-relaxed">
              The query executed successfully but produced no matching rows in the dataset.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('sql-result-table flex flex-col h-full w-full bg-surface overflow-hidden', className)}>
      {/* Dynamic Status / Actions Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-2 bg-surface select-none">
        
        {/* Search filter input */}
        <div className="relative group shrink-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted/40 group-focus-within:text-accent-primary transition-all duration-200" size={13} />
          <input
            type="text"
            placeholder="Search returned rows..."
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            className="w-full sm:w-56 bg-elevated/10 hover:bg-elevated/25 border border-border/40 focus:border-accent-primary/45 rounded-xl !pl-9 pr-3 py-1 text-[11.5px] font-medium text-header placeholder:text-muted/30 focus:outline-none transition-all duration-200 shadow-sm"
          />
          {filterQuery && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded-full text-[8px] font-mono font-bold bg-accent-primary/10 text-accent-primary border border-accent-primary/20">
              {filteredRows.length} found
            </span>
          )}
        </div>

        {/* Stats & Actions */}
        <div className="flex items-center justify-between sm:justify-end gap-4 shrink-0">
          <div className="flex items-center gap-3 text-[10.5px] text-muted font-medium font-mono">
            {executionTimeMs !== undefined && (
              <span className="bg-elevated/10 border border-border/40 px-2 py-0.5 rounded text-muted/70">
                {executionTimeMs < 1000
                  ? `${executionTimeMs.toFixed(0)}ms`
                  : `${(executionTimeMs / 1000).toFixed(2)}s`}
              </span>
            )}
            <span className="text-secondary font-mono text-[10px] tracking-wide">
              {filterQuery ? (
                <span>{filteredRows.length.toLocaleString()} / {rowCount.toLocaleString()} rows</span>
              ) : (
                <span>{rowCount.toLocaleString()} {rowCount === 1 ? 'row' : 'rows'}</span>
              )}
            </span>
          </div>

          <div className="w-px h-3.5 bg-border/60 hidden sm:block" />

          {/* Action buttons */}
          <div className="flex items-center gap-1">
            <button
              onClick={handleCopyJSON}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-elevated/10 hover:bg-elevated/25 border border-border/40 hover:border-border text-[11px] font-semibold text-secondary hover:text-header transition-all duration-150"
              title="Copy results as JSON"
            >
              <Copy size={11} />
              <span>JSON</span>
            </button>
            <button
              onClick={handleExportCSV}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-elevated/10 hover:bg-elevated/25 border border-border/40 hover:border-border text-[11px] font-semibold text-secondary hover:text-header transition-all duration-150"
              title="Download results as CSV"
            >
              <Download size={11} />
              <span>CSV</span>
            </button>
          </div>
        </div>

      </div>

      {/* Interactive Data Grid Scroll Area */}
      <div className="flex-1 min-h-0 overflow-auto studio-scrollbar bg-primary/5">
        {filteredRows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-muted select-none">
            <Filter size={16} className="opacity-30 mb-2" />
            <span className="text-xs text-muted/50">No matching rows found for "{filterQuery}"</span>
          </div>
        ) : (
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="sticky top-0 z-10 bg-surface/95 backdrop-blur-sm shadow-[0_1px_0_0_var(--border)] select-none">
                {/* Row Index Header Column */}
                <th className="px-3 py-2 text-center font-bold text-muted/65 uppercase tracking-wider bg-elevated/10 border-b border-border/55 w-10 border-r border-border/30 text-[9.5px]">
                  #
                </th>
                {displayColumns.map((col) => {
                  const label = typeof col === 'string'
                    ? col.replace(/_/g, ' ')
                    : (col.label || col.key || '').replace(/_/g, ' ');
                  return (
                    <th
                      key={typeof col === 'string' ? col : (col.key || col)}
                      className="px-4 py-2.5 text-left font-bold text-muted/65 uppercase tracking-wider border-b border-border/55 bg-elevated/5 whitespace-nowrap text-[9.5px]"
                    >
                      {label}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="border-b border-border/20 hover:bg-elevated/20 transition-colors duration-100 group"
                >
                  {/* Row index label */}
                  <td className="px-3 py-2.5 text-center text-muted/40 font-mono font-medium select-none bg-elevated/5 border-r border-border/20 w-10 text-[9.5px] group-hover:text-accent-primary transition-colors">
                    {rowIndex + 1}
                  </td>
                  {displayColumns.map((col) => {
                    const key = typeof col === 'string' ? col : (col.key || col);
                    const val = row[key];
                    const isNum = typeof val === 'number';
                    const cellId = `${rowIndex}-${key}`;
                    const isHovered = hoveredCell === cellId;
                    const isCopied = copiedCell === cellId;
                    return (
                      <td
                        key={cellId}
                        onMouseEnter={() => setHoveredCell(cellId)}
                        onMouseLeave={() => setHoveredCell(null)}
                        className={cn(
                          "px-4 py-2.5 whitespace-nowrap font-mono transition-colors text-[11.5px] border-r border-border/10 last:border-r-0 relative",
                          isNum ? "text-right text-blue-400/90" : "text-left text-secondary",
                          "group-hover:text-header",
                          isHovered && "bg-elevated/20"
                        )}
                      >
                        <span className="inline-flex items-center gap-1.5">
                          {formatValue(val)}
                          {/* Copy button — appears on cell hover */}
                          {isHovered && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleCopyCell(val, rowIndex, key);
                              }}
                              className={cn(
                                "shrink-0 p-1 rounded-md transition-all duration-150",
                                isCopied
                                  ? "text-emerald-400 bg-emerald-500/15"
                                  : "text-muted/30 hover:text-accent-primary hover:bg-elevated/40 opacity-0 group-hover:opacity-100"
                              )}
                              title="Copy cell value"
                            >
                              {isCopied ? (
                                <Check size={10} strokeWidth={3} />
                              ) : (
                                <Copy size={10} strokeWidth={2} />
                              )}
                            </button>
                          )}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Results grid footer — truncation / LIMIT info (only renders when a message applies) */}
      {(rowCount > rows.length || (rowLimit && rowCount >= rowLimit)) && (
        <div className="px-4 py-2 bg-elevated/10 text-[10px] text-muted/60 text-center font-mono select-none border-t border-border/30">
          {rowCount > rows.length ? (
            <span>
              Showing first {rows.length.toLocaleString()} of {rowCount.toLocaleString()} rows
              · Download CSV to view the full result set.
            </span>
          ) : (
            <span>
              {rowCount.toLocaleString()} {rowCount === 1 ? 'row' : 'rows'}
              {' · '}
              <span className="text-accent-primary/70 font-bold">LIMIT {rowLimit.toLocaleString()}</span> reached
            </span>
          )}
        </div>
      )}
    </div>
  );
});

SqlResultTable.displayName = 'SqlResultTable';

export default SqlResultTable;
