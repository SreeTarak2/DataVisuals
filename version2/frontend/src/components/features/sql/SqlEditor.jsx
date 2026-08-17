import React, { useRef, useEffect, useState, useCallback, memo, forwardRef, useImperativeHandle } from 'react';
import { cn } from '@/lib/utils';

// CodeMirror 6 — static ESM imports (Vite-native)
import { EditorView, keymap, placeholder as cmPlaceholder, lineNumbers, highlightSpecialChars } from '@codemirror/view';
import { EditorState, Compartment } from '@codemirror/state';
import { sql, StandardSQL } from '@codemirror/lang-sql';
import { oneDark } from '@codemirror/theme-one-dark';
import { autocompletion, closeBrackets, completionKeymap, acceptCompletion } from '@codemirror/autocomplete';
import { history, defaultKeymap, historyKeymap } from '@codemirror/commands';
import { searchKeymap } from '@codemirror/search';
import { indentOnInput, foldGutter, foldKeymap } from '@codemirror/language';

// ── Utility: map a DB type string to a display badge ──────────────
const TYPE_BADGE = (type) => {
  const t = (type || '').toLowerCase();
  if (['numeric', 'integer', 'int', 'float', 'double', 'int64', 'float64', 'int32', 'float32', 'decimal', 'number', 'bigint', 'smallint', 'tinyint', 'real'].includes(t)) {
    return { label: 'num', css: 'color:#60a5fa' };     // blue
  }
  if (['timestamp', 'datetime', 'date', 'time', 'datetime64', 'timestamptz', 'timetz', 'interval'].includes(t)) {
    return { label: 'time', css: 'color:#34d399' };    // emerald
  }
  if (['text', 'string', 'str', 'object', 'varchar', 'char', 'nchar', 'nvarchar', 'clob', 'mediumtext', 'longtext'].includes(t)) {
    return { label: 'text', css: 'color:#fbbf24' };    // amber
  }
  if (['bool', 'boolean', 'bit'].includes(t)) {
    return { label: 'bool', css: 'color:#a78bfa' };    // purple
  }
  if (['json', 'jsonb', 'array', 'list', 'map', 'struct'].includes(t)) {
    return { label: 'json', css: 'color:#f472b6' };    // pink
  }
  if (['uuid', 'guid', 'uniqueidentifier'].includes(t)) {
    return { label: 'uuid', css: 'color:#38bdf8' };    // cyan
  }
  return { label: (t || '?').slice(0, 4), css: 'color:#a1a1aa' }; // zinc
};

// ── SQL snippet definitions: expanded keywords + snippet templates ─
const SQL_SNIPPETS = [
  // ── Core DML ──
  { label: 'SELECT',           apply: 'SELECT ',                        type: 'keyword', detail: 'Retrieve rows' },
  { label: 'SELECT *',         apply: 'SELECT * FROM ',                  type: 'keyword', detail: 'Select all columns' },
  { label: 'FROM',             apply: 'FROM ',                            type: 'keyword', detail: 'Specify table' },
  { label: 'WHERE',            apply: 'WHERE ',                           type: 'keyword', detail: 'Filter rows' },
  { label: 'GROUP BY',         apply: 'GROUP BY ',                       type: 'keyword', detail: 'Group rows' },
  { label: 'HAVING',           apply: 'HAVING ',                          type: 'keyword', detail: 'Filter groups' },
  { label: 'ORDER BY',         apply: 'ORDER BY ',                       type: 'keyword', detail: 'Sort rows' },
  { label: 'LIMIT',            apply: 'LIMIT ',                           type: 'keyword', detail: 'Max rows' },
  { label: 'OFFSET',           apply: 'OFFSET ',                          type: 'keyword', detail: 'Skip rows' },
  { label: 'AS',               apply: 'AS ',                              type: 'keyword', detail: 'Alias' },
  { label: 'DISTINCT',         apply: 'DISTINCT ',                        type: 'keyword', detail: 'Unique rows only' },
  { label: 'ALL',              apply: 'ALL ',                             type: 'keyword', detail: 'Include duplicates' },

  // ── JOIN variants ──
  { label: 'JOIN',             apply: 'JOIN ',                            type: 'keyword', detail: 'Join table' },
  { label: 'LEFT JOIN',        apply: 'LEFT JOIN ',                      type: 'keyword', detail: 'Left outer join' },
  { label: 'RIGHT JOIN',       apply: 'RIGHT JOIN ',                     type: 'keyword', detail: 'Right outer join' },
  { label: 'INNER JOIN',       apply: 'INNER JOIN ',                     type: 'keyword', detail: 'Inner join' },
  { label: 'CROSS JOIN',       apply: 'CROSS JOIN ',                     type: 'keyword', detail: 'Cross join' },
  { label: 'NATURAL JOIN',     apply: 'NATURAL JOIN ',                   type: 'keyword', detail: 'Natural join' },
  { label: 'ON',               apply: 'ON ',                              type: 'keyword', detail: 'Join condition' },
  { label: 'USING',            apply: 'USING ',                           type: 'keyword', detail: 'Join using column' },

  // ── Set operations ──
  { label: 'UNION',            apply: 'UNION\n',                          type: 'keyword', detail: 'Combine result sets' },
  { label: 'UNION ALL',        apply: 'UNION ALL\n',                     type: 'keyword', detail: 'Union with duplicates' },
  { label: 'INTERSECT',        apply: 'INTERSECT\n',                     type: 'keyword', detail: 'Intersection' },
  { label: 'EXCEPT',           apply: 'EXCEPT\n',                        type: 'keyword', detail: 'Set difference' },

  // ── CTE / Subquery ──
  { label: 'WITH',             apply: 'WITH ',                            type: 'keyword', detail: 'Common Table Expression' },
  { label: 'WITH RECURSIVE',   apply: 'WITH RECURSIVE ',                 type: 'keyword', detail: 'Recursive CTE' },

  // ── Window functions ──
  { label: 'OVER',             apply: 'OVER (',                           type: 'keyword', detail: 'Window function' },
  { label: 'PARTITION BY',     apply: 'PARTITION BY ',                   type: 'keyword', detail: 'Window partition' },
  { label: 'ROW_NUMBER()',     apply: 'ROW_NUMBER() OVER (',            type: 'function', detail: 'Row number' },
  { label: 'RANK()',           apply: 'RANK() OVER (',                  type: 'function', detail: 'Rank' },
  { label: 'DENSE_RANK()',     apply: 'DENSE_RANK() OVER (',            type: 'function', detail: 'Dense rank' },
  { label: 'LAG()',            apply: 'LAG(',                             type: 'function', detail: 'Previous row value' },
  { label: 'LEAD()',           apply: 'LEAD(',                            type: 'function', detail: 'Next row value' },
  { label: 'NTILE()',          apply: 'NTILE(',                           type: 'function', detail: 'Bucket rows' },

  // ── Aggregate functions ──
  { label: 'SUM()',            apply: 'SUM(',                             type: 'function', detail: 'Sum aggregate' },
  { label: 'COUNT()',          apply: 'COUNT(',                           type: 'function', detail: 'Count aggregate' },
  { label: 'AVG()',            apply: 'AVG(',                             type: 'function', detail: 'Average aggregate' },
  { label: 'MIN()',            apply: 'MIN(',                             type: 'function', detail: 'Minimum aggregate' },
  { label: 'MAX()',            apply: 'MAX(',                             type: 'function', detail: 'Maximum aggregate' },
  { label: 'COUNT(DISTINCT )', apply: 'COUNT(DISTINCT ',                 type: 'function', detail: 'Count distinct' },
  { label: 'MEDIAN()',         apply: 'MEDIAN(',                          type: 'function', detail: 'Median' },
  { label: 'MODE()',           apply: 'MODE(',                            type: 'function', detail: 'Statistical mode' },
  { label: 'STDDEV()',         apply: 'STDDEV(',                          type: 'function', detail: 'Standard deviation' },
  { label: 'VARIANCE()',       apply: 'VARIANCE(',                        type: 'function', detail: 'Variance' },
  { label: 'STRING_AGG()',     apply: 'STRING_AGG(',                      type: 'function', detail: 'String aggregate' },
  { label: 'ARRAY_AGG()',      apply: 'ARRAY_AGG(',                       type: 'function', detail: 'Array aggregate' },
  { label: 'LIST()',           apply: 'LIST(',                            type: 'function', detail: 'List (DuckDB)' },
  { label: 'APPROX_COUNT_DISTINCT()', apply: 'APPROX_COUNT_DISTINCT(',   type: 'function', detail: 'Approx count distinct' },
  { label: 'APPROX_QUANTILE()',       apply: 'APPROX_QUANTILE(',         type: 'function', detail: 'Approx quantile' },

  // ── Scalar functions ──
  { label: 'COALESCE()',       apply: 'COALESCE(',                        type: 'function', detail: 'First non-null' },
  { label: 'NULLIF()',         apply: 'NULLIF(',                          type: 'function', detail: 'Null if equal' },
  { label: 'CAST()',           apply: 'CAST(',                            type: 'function', detail: 'Type cast' },
  { label: 'ROUND()',          apply: 'ROUND(',                           type: 'function', detail: 'Round number' },
  { label: 'ABS()',            apply: 'ABS(',                             type: 'function', detail: 'Absolute value' },
  { label: 'LENGTH()',         apply: 'LENGTH(',                          type: 'function', detail: 'String length' },
  { label: 'SUBSTRING()',      apply: 'SUBSTRING(',                       type: 'function', detail: 'Substring' },
  { label: 'TRIM()',           apply: 'TRIM(',                            type: 'function', detail: 'Trim whitespace' },
  { label: 'UPPER()',          apply: 'UPPER(',                           type: 'function', detail: 'Uppercase' },
  { label: 'LOWER()',          apply: 'LOWER(',                           type: 'function', detail: 'Lowercase' },
  { label: 'CONCAT()',         apply: 'CONCAT(',                          type: 'function', detail: 'String concat' },
  { label: 'REPLACE()',        apply: 'REPLACE(',                         type: 'function', detail: 'String replace' },
  { label: 'EXTRACT()',        apply: 'EXTRACT(',                         type: 'function', detail: 'Extract date part' },
  { label: 'DATE_TRUNC()',     apply: 'DATE_TRUNC(',                      type: 'function', detail: 'Truncate date' },
  { label: 'DATEDIFF()',       apply: 'DATEDIFF(',                        type: 'function', detail: 'Date difference' },
  { label: 'DATEADD()',        apply: 'DATEADD(',                         type: 'function', detail: 'Date add' },
  { label: 'STRFTIME()',       apply: 'STRFTIME(',                        type: 'function', detail: 'Format date' },
  { label: 'CASE',             apply: 'CASE\n  WHEN  THEN \n  ELSE \nEND', type: 'keyword', detail: 'Conditional expression' },
  { label: 'IIF()',            apply: 'IIF(',                             type: 'function', detail: 'Inline if' },

  // ── DuckDB-specific ──
  { label: 'PIVOT',            apply: 'PIVOT ',                           type: 'keyword', detail: 'Pivot (DuckDB)' },
  { label: 'UNPIVOT',          apply: 'UNPIVOT ',                         type: 'keyword', detail: 'Unpivot (DuckDB)' },
  { label: 'QUALIFY',          apply: 'QUALIFY ',                         type: 'keyword', detail: 'Filter window (DuckDB)' },
  { label: 'SAMPLE',           apply: 'SAMPLE ',                          type: 'keyword', detail: 'Random sample (DuckDB)' },
  { label: 'POSITIONAL JOIN',  apply: 'POSITIONAL JOIN ',                 type: 'keyword', detail: 'Positional join (DuckDB)' },
  { label: 'ASOF JOIN',        apply: 'ASOF JOIN ',                       type: 'keyword', detail: 'As-of join (DuckDB)' },
  { label: 'SEMI JOIN',        apply: 'SEMI JOIN ',                       type: 'keyword', detail: 'Semi join (DuckDB)' },
  { label: 'ANTI JOIN',        apply: 'ANTI JOIN ',                       type: 'keyword', detail: 'Anti join (DuckDB)' },
  { label: 'UNNEST()',         apply: 'UNNEST(',                          type: 'function', detail: 'Unnest array (DuckDB)' },
  { label: 'GENERATE_SERIES()', apply: 'GENERATE_SERIES(',                type: 'function', detail: 'Generate series (DuckDB)' },
  { label: 'COLUMNS()',        apply: 'COLUMNS(',                         type: 'function', detail: 'Columns expression list (DuckDB)' },

  // ── Conditional operators (WHERE context) ──
  { label: '=',                 apply: ' = ',                              type: 'operator', detail: 'Equals' },
  { label: '!=',                apply: ' != ',                             type: 'operator', detail: 'Not equals' },
  { label: '<>',                apply: ' <> ',                             type: 'operator', detail: 'Not equals' },
  { label: '>',                 apply: ' > ',                              type: 'operator', detail: 'Greater than' },
  { label: '<',                 apply: ' < ',                              type: 'operator', detail: 'Less than' },
  { label: '>=',                apply: ' >= ',                             type: 'operator', detail: 'Greater or equal' },
  { label: '<=',                apply: ' <= ',                             type: 'operator', detail: 'Less or equal' },
  { label: 'LIKE',              apply: ' LIKE ',                           type: 'keyword', detail: 'Pattern match' },
  { label: 'ILIKE',             apply: ' ILIKE ',                          type: 'keyword', detail: 'Case-insensitive pattern' },
  { label: 'NOT LIKE',          apply: ' NOT LIKE ',                       type: 'keyword', detail: 'Negative pattern match' },
  { label: 'IN',                apply: ' IN ',                             type: 'keyword', detail: 'Set membership' },
  { label: 'NOT IN',            apply: ' NOT IN ',                         type: 'keyword', detail: 'Not in set' },
  { label: 'BETWEEN',           apply: ' BETWEEN ',                        type: 'keyword', detail: 'Range check' },
  { label: 'IS NULL',           apply: ' IS NULL',                         type: 'keyword', detail: 'Null check' },
  { label: 'IS NOT NULL',       apply: ' IS NOT NULL',                     type: 'keyword', detail: 'Not null check' },
  { label: 'AND',               apply: ' AND ',                            type: 'keyword', detail: 'Logical AND' },
  { label: 'OR',                apply: ' OR ',                             type: 'keyword', detail: 'Logical OR' },
  { label: 'NOT',               apply: ' NOT ',                            type: 'keyword', detail: 'Logical NOT' },
  { label: 'EXISTS',            apply: ' EXISTS (',                        type: 'keyword', detail: 'Exists subquery' },
  { label: 'ANY',               apply: ' ANY ',                            type: 'keyword', detail: 'Any comparison' },
  { label: 'ALL',               apply: ' ALL ',                            type: 'keyword', detail: 'All comparison' },

  // ── ORDER BY modifiers ──
  { label: 'ASC',               apply: ' ASC',                             type: 'keyword', detail: 'Ascending order' },
  { label: 'DESC',              apply: ' DESC',                            type: 'keyword', detail: 'Descending order' },
  { label: 'NULLS FIRST',       apply: ' NULLS FIRST',                     type: 'keyword', detail: 'Nulls first' },
  { label: 'NULLS LAST',        apply: ' NULLS LAST',                      type: 'keyword', detail: 'Nulls last' },

  // ── Table ref ──
  { label: 'data',              apply: 'data',                             type: 'table', detail: 'Current dataset' },
];

// ── Column options builder from metadata ──────────────────────────
function buildColumnOptions(cols) {
  return (cols || []).map(col => {
    const name = typeof col === 'string' ? col : col.name;
    const type = typeof col === 'string' ? '' : (col.type || col.dtype || '');
    const badge = TYPE_BADGE(type);
    return {
      label: name,
      type: 'column',
      detail: badge.label,
      detailStyle: badge.css,
      apply: name.includes(' ') ? `"${name}"` : name,
    };
  });
}

// ── Custom completion source ─────────────────────────────────────
function createCompletionSource(columnOptions) {
  return (context) => {
    const word = context.matchBefore(/\w*/);
    if (!word || (word.from === word.to && !context.explicit)) return null;

    const fullText = context.state.doc.toString();
    const before = fullText.slice(0, word.from).toUpperCase();

    // ── Context detection ──
    // Walk backwards from cursor to find the most recent clause
    const textBeforeCursor = fullText.slice(0, context.pos).toUpperCase();

    // Simple heuristic: check which clause we're in
    const afterSelect     = /\bSELECT\b[^;]*$/.test(textBeforeCursor) && !/\bFROM\b/.test(textBeforeCursor);
    const afterFrom       = /\bFROM\b[^;]*$/.test(textBeforeCursor) && !/\bWHERE\b/.test(textBeforeCursor) && !/\bJOIN\b/.test(textBeforeCursor);
    const afterWhere      = /\bWHERE\b[^;]*$/.test(textBeforeCursor) && !/\bGROUP\b/.test(textBeforeCursor);
    const afterGroupBy    = /\bGROUP\s+BY\b[^;]*$/.test(textBeforeCursor) && !/\bHAVING\b/.test(textBeforeCursor);
    const afterHaving     = /\bHAVING\b[^;]*$/.test(textBeforeCursor) && !/\bORDER\b/.test(textBeforeCursor);
    const afterOrderBy    = /\bORDER\s+BY\b[^;]*$/.test(textBeforeCursor) && !/\bLIMIT\b/.test(textBeforeCursor);
    const afterOn         = /\bON\b[^;]*$/.test(textBeforeCursor);
    const afterLimit      = /\bLIMIT\b[^;]*$/.test(textBeforeCursor);
    const afterJoin       = /\b(JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|CROSS\s+JOIN|NATURAL\s+JOIN|SEMI\s+JOIN|ANTI\s+JOIN|ASOF\s+JOIN|POSITIONAL\s+JOIN)\b[^;]*$/.test(textBeforeCursor);
    const inOrderByClause = /\bORDER\s+BY\b[^;]*$/.test(textBeforeCursor);
    const inGroupByClause = /\bGROUP\s+BY\b[^;]*$/.test(textBeforeCursor);

    const wordLower = word.text.toLowerCase();

    // ── Build option list ──
    let options = [];

    // Columns are relevant in SELECT, WHERE, GROUP BY, ORDER BY, HAVING, ON
    if (afterSelect || afterWhere || afterHaving || inOrderByClause || inGroupByClause || afterOn) {
      options = [...columnOptions];
    }

    // After FROM / JOIN → table names only
    if (afterFrom || afterJoin) {
      options = SQL_SNIPPETS.filter(s => s.type === 'table');
      options.push(...columnOptions); // also suggest columns for subqueries
      return {
        from: word.from,
        options: options.filter(o => o.label.toLowerCase().startsWith(wordLower)),
      };
    }

    // After LIMIT → only numbers
    if (afterLimit) {
      return null;
    }

    // After ORDER BY → columns + ASC/DESC/NULLS
    if (inOrderByClause) {
      options = options.concat(SQL_SNIPPETS.filter(s =>
        ['ASC', 'DESC', 'NULLS FIRST', 'NULLS LAST'].includes(s.label)
      ));
      return {
        from: word.from,
        options: options.filter(o => o.label.toLowerCase().startsWith(wordLower)),
      };
    }

    // After GROUP BY → columns only
    if (inGroupByClause) {
      return {
        from: word.from,
        options: options.filter(o => o.type === 'column' && o.label.toLowerCase().startsWith(wordLower)),
      };
    }

    // General context: suggest everything that matches
    const allSnippets = (word.from === 0 && !/\bFROM\b/.test(fullText.toUpperCase()))
      ? SQL_SNIPPETS.filter(s => !['ASC', 'DESC', 'NULLS FIRST', 'NULLS LAST', '=', '!=', '<>', '>', '<', '>=', '<=', 'LIKE', 'ILIKE', 'NOT LIKE', 'IN', 'NOT IN', 'BETWEEN', 'IS NULL', 'IS NOT NULL', 'AND', 'OR', 'NOT', 'EXISTS', 'ANY'].includes(s.label))
      : SQL_SNIPPETS;
    options = options.concat(allSnippets);

    // In WHERE context, push operators and boolean keywords to the top
    if (afterWhere) {
      const operators = SQL_SNIPPETS.filter(s =>
        ['=', '!=', '<>', '>', '<', '>=', '<=', 'LIKE', 'ILIKE', 'NOT LIKE', 'IN', 'NOT IN', 'BETWEEN', 'IS NULL', 'IS NOT NULL', 'AND', 'OR', 'NOT', 'EXISTS', 'ANY', 'ALL'].includes(s.label)
      );
      options = [...options, ...operators];
    }

    return {
      from: word.from,
      options: options.filter(o => o.label.toLowerCase().startsWith(wordLower)),
      filter: false,
    };
  };
}

// ── Custom completion renderer for type badges ───────────────────
const completionRenderer = (parent, data, index, options) => {
  const item = document.createElement('div');
  item.className = 'cm-completion-item';

  // Type badge
  const badge = document.createElement('span');
  badge.className = 'cm-completion-badge';
  if (data.type === 'column' && data.detail) {
    badge.textContent = data.detail;
    badge.style.cssText = data.detailStyle || 'color:#a1a1aa';
  } else if (data.type === 'function') {
    badge.textContent = 'fn';
    badge.style.color = '#818cf8';
  } else if (data.type === 'keyword') {
    badge.textContent = 'kw';
    badge.style.color = '#34d399';
  } else if (data.type === 'operator') {
    badge.textContent = 'op';
    badge.style.color = '#f472b6';
  } else if (data.type === 'table') {
    badge.textContent = 'tbl';
    badge.style.color = '#38bdf8';
  } else {
    badge.textContent = '?';
    badge.style.color = '#a1a1aa';
  }
  item.appendChild(badge);

  // Label
  const label = document.createElement('span');
  label.className = 'cm-completion-label';
  label.textContent = data.label;
  item.appendChild(label);

  parent.appendChild(item);
};


// ═══════════════════════════════════════════════════════════════════
// SqlEditor Component
// ═══════════════════════════════════════════════════════════════════
const SqlEditor = memo(forwardRef(({
  value = '',
  onChange,
  columns = [],
  readOnly = false,
  height = '200px',
  placeholder = 'SELECT ... FROM data WHERE ...',
  className = '',
  editorId,
}, ref) => {
  const containerRef = useRef(null);
  const viewRef = useRef(null);
  // Compartment lets us swap the autocomplete extension without rebuilding the view
  const autocompleteCompartment = useRef(new Compartment());
  // Ref that always holds the latest editorId so the Mod+Enter keymap closure
  // never goes stale when datasetId changes after mount.
  const editorIdRef = useRef(editorId);
  editorIdRef.current = editorId;
  const [isReady, setIsReady] = useState(false);
  // ── Cursor position for Ln/Col status bar ──
  const [cursorPos, setCursorPos] = useState({ line: 1, col: 1 });
  const cursorCallbackRef = useRef(null);
  cursorCallbackRef.current = (pos) => setCursorPos(pos);

  // ── Expose imperative methods to parent (for selected-text execution) ──
  useImperativeHandle(ref, () => ({
    /** Returns the currently highlighted text in the editor, or null */
    getSelectedText: () => {
      const view = viewRef.current;
      if (!view) return null;
      const sel = view.state.selection.main;
      if (sel.empty) return null;
      return view.state.sliceDoc(sel.from, sel.to);
    },
    /** Low-level access to the CodeMirror EditorView */
    getEditorView: () => viewRef.current,
  }), []);

  // ── Build autocomplete extension from column metadata ──
  const buildAutocomplete = useCallback((cols) => {
    const columnOptions = buildColumnOptions(cols);
    const completionSource = createCompletionSource(columnOptions);

    return autocompletion({
      override: [completionSource],
      activateOnTyping: true,
      maxRenderedOptions: 20,
      defaultKeymap: true,
      closeOnBlur: true,
      // Custom renderer for type badges
      render: completionRenderer,
    });
  }, []);

  // ── Initialize CodeMirror once on mount ──
  useEffect(() => {
    if (!containerRef.current) return;

    const extensions = [
      // SQL language
      sql({ dialect: StandardSQL, defaultDialect: StandardSQL }),
      // Dark theme
      oneDark,
      // Autocomplete — wrapped in compartment for live column updates
      autocompleteCompartment.current.of(buildAutocomplete([])),
      // Close brackets automatically
      closeBrackets(),
      // Keybindings
      keymap.of([
        { key: 'Tab', run: acceptCompletion },
        ...completionKeymap,
        ...defaultKeymap,
        ...historyKeymap,
        ...foldKeymap,
        ...searchKeymap,
        // Cmd+Enter / Ctrl+Enter
        {
          key: 'Mod-Enter',
          run: () => {
            const event = new CustomEvent('sql-editor-run', {
              detail: { editorId: editorIdRef.current },
            });
            document.dispatchEvent(event);
            return true;
          },
        },
      ]),
      // Line numbers in the gutter
      lineNumbers(),
      // Code folding gutter (fold/unfold CTEs, subqueries)
      foldGutter(),
      // Auto-indent on Enter
      indentOnInput(),
      // Visible markers for special/invisible chars
      highlightSpecialChars(),
      // ── Cursor position tracking for Ln/Col status bar ──
      EditorView.updateListener.of((update) => {
        if (update.docChanged && onChange) {
          onChange(update.view.state.doc.toString());
        }
        if (update.selectionSet || update.docChanged) {
          const pos = update.view.state.selection.main.head;
          const lineObj = update.view.state.doc.lineAt(pos);
          const col = pos - lineObj.from + 1;
          cursorCallbackRef.current?.({ line: lineObj.number, col });
        }
      }),
      // History support (Ctrl+Z / Ctrl+Shift+Z)
      history(),
      // Read-only guard
      EditorState.readOnly.of(readOnly),
      // Disable spellcheck in editor
      EditorView.contentAttributes.of({ spellcheck: 'false' }),
      // Placeholder text
      placeholder ? cmPlaceholder(placeholder) : [],
      // Custom theme overrides
      EditorView.theme({
        '&': {
          height,
          backgroundColor: 'var(--bg-primary) !important',
          color: 'var(--text-primary) !important',
        },
        '.cm-scroller': {
          height: '100% !important',
          fontFamily: "'JetBrains Mono', 'Space Grotesk', 'Fira Code', monospace",
          fontSize: '13.5px',
          lineHeight: '1.65',
          overflow: 'auto',
        },
        '.cm-content': {
          padding: '16px 0px 16px 4px',
          caretColor: 'var(--text-header)',
        },
        '.cm-gutters': {
          borderRight: 'none',
          backgroundColor: 'var(--bg-primary) !important',
          color: 'var(--text-muted) !important',
        },
        '.cm-gutterElement': {
          padding: '0 4px 0 8px',
        },
        '.cm-activeLine': {
          backgroundColor: 'rgba(255, 255, 255, 0.02) !important',
        },
        '.cm-activeLineGutter': {
          backgroundColor: 'rgba(255, 255, 255, 0.04) !important',
          color: 'var(--text-header) !important',
        },
        '.cm-cursor': {
          borderLeftColor: 'var(--text-header) !important',
        },
        '.cm-selectionBackground': {
          backgroundColor: 'var(--accent-primary-light) !important',
        },
        // ── Custom completion tooltip styling ──
        '.cm-tooltip.cm-tooltip-autocomplete': {
          border: '1px solid var(--border) !important',
          borderRadius: '10px !important',
          backgroundColor: 'var(--bg-surface) !important',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05) !important',
          overflow: 'hidden',
          minWidth: '240px',
        },
        '.cm-tooltip.cm-tooltip-autocomplete > ul': {
          maxHeight: '320px',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '12px',
          padding: '6px !important',
          backgroundColor: 'var(--bg-surface) !important',
        },
        '.cm-tooltip.cm-tooltip-autocomplete > ul > li': {
          padding: '6px 10px !important',
          borderRadius: '6px !important',
          color: 'var(--text-secondary) !important',
          display: 'flex !important',
          alignItems: 'center !important',
          gap: '8px !important',
          minHeight: '28px',
        },
        '.cm-tooltip.cm-tooltip-autocomplete > ul > li[aria-selected]': {
          backgroundColor: 'var(--accent-primary-light) !important',
          color: 'var(--text-header) !important',
        },
        // ── Completion item internal elements ──
        '.cm-completionItem': {
          display: 'flex !important',
          alignItems: 'center !important',
          gap: '8px !important',
        },
        '.cm-completionIcon': { display: 'none !important' },
        '.cm-completionLabel': {
          fontWeight: 500,
          flex: 1,
        },
        '.cm-completionDetail': {
          display: 'none !important',
        },
        // ── Custom completion item badge + label ──
        '.cm-completion-badge': {
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          minWidth: '28px',
          padding: '1px 5px',
          borderRadius: '4px',
          fontSize: '9px',
          fontWeight: 700,
          fontFamily: "'JetBrains Mono', monospace",
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          opacity: 0.8,
        },
        '.cm-completion-label': {
          flex: 1,
          fontSize: '12px',
        },
        // ── Placeholder ──
        '.cm-placeholder': {
          color: 'var(--text-muted)',
          opacity: 0.4,
          fontFamily: "'JetBrains Mono', monospace",
        },
      }),
    ];

    const state = EditorState.create({ doc: value, extensions });

    const view = new EditorView({
      state,
      parent: containerRef.current,
    });

    viewRef.current = view;
    setIsReady(true);

    return () => {
      view.destroy();
      viewRef.current = null;
      setIsReady(false);
    };
  }, []); // Run once on mount

  // ── Hot-swap autocomplete when columns change ──
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch({
      effects: autocompleteCompartment.current.reconfigure(buildAutocomplete(columns)),
    });
  }, [columns, buildAutocomplete]);

  // ── Sync editor content when value prop changes ──
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const currentText = view.state.doc.toString();
    if (value !== currentText) {
      view.dispatch({
        changes: { from: 0, to: currentText.length, insert: value },
      });
    }
  }, [value]);

  return (
    <div
      style={{ height }}
      className={cn(
        'sql-editor overflow-hidden transition-colors duration-200 flex flex-col relative',
        height === '100%'
          ? 'border-none rounded-none bg-primary'
          : 'rounded-xl border border-border bg-surface shadow-sm',
        !isReady && 'min-h-[60px] items-center justify-center text-muted text-xs',
        className
      )}
      data-editor-id={editorId}
    >
      {/* CodeMirror container — fills available space */}
      <div ref={containerRef} className="flex-1 min-h-0 w-full" />

      {/* Loading overlay (shown before CodeMirror initialises) */}
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-primary/80">
          <span className="text-xs text-muted/50">Loading editor...</span>
        </div>
      )}
    </div>
  );
}));

SqlEditor.displayName = 'SqlEditor';

export default SqlEditor;
