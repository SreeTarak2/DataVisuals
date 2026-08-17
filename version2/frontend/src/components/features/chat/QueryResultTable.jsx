/**
 * QueryResultTable — Renders SQL query results as a styled table
 *
 * Displays column headers with formatted values, row counts,
 * and scrollable overflow for large result sets.
 */
import React from 'react';
import { Table2 } from 'lucide-react';
import { formatTableValue, getTableColumns } from './chatUtils';

const QueryResultTable = ({ table }) => {
  const rows = Array.isArray(table?.rows) ? table.rows : [];
  const columns = getTableColumns(table);
  if (!rows.length || !columns.length) return null;

  const totalRows = table?.totalRows ?? rows.length;
  const displayedRows = table?.displayedRows ?? rows.length;

  return (
    <div className="chat-table-wrapper mt-3">
      <div className="flex items-center justify-between gap-2 border-b border-border bg-elevated/40 px-3 py-2">
        <div className="flex items-center gap-2 min-w-0">
          <Table2 size={13} className="text-muted shrink-0" />
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted">Query Results</span>
        </div>
        <span className="text-[10px] text-muted shrink-0">{displayedRows.toLocaleString()} of {totalRows.toLocaleString()}</span>
      </div>
      <div className="max-h-[260px] overflow-auto bg-surface">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column) => (
                  <td key={`${rowIndex}-${column.key}`}>{formatTableValue(row?.[column.key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default QueryResultTable;
