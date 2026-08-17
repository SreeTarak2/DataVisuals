import React, { useState, useCallback, memo, useEffect, useRef } from 'react';
import { 
  Play, Bot, Wrench, Square, 
  Loader2, Terminal,
  Heart, AlignLeft, ChevronDown, GripHorizontal
} from 'lucide-react';

import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';
import { sqlAPI } from '@/services/api';
import SqlEditor from './SqlEditor';
import SqlResultTable from './SqlResultTable';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
import useDatasetStore from '@/store/datasetStore';

const SqlEditorPanel = memo(({
  initialSql = '',
  datasetId,
  columns = [],
  isOpen = true,
  onClose,
  onSaveAsMetric,
  rowLimit: initialRowLimit = 1000,
  className,
  compact = false,
  queryId,
  onSqlChange,
  isFavorite,
  onToggleFavorite,
  onToggleChat,
  externalSql,
  onExternalSqlConsumed,
}) => {
  const { datasets = [], setSelectedDataset, selectedDataset } = useDatasetStore();
  const [role, setRole] = useState('postgres');

  const storageKey = datasetId ? `sql-draft-${datasetId}` : null;
  const [sql, setSql] = useState(() => {
    if (!compact && storageKey) {
      try {
        const saved = localStorage.getItem(storageKey);
        if (saved) return saved;
      } catch {}
    }
    return initialSql;
  });
  
  const [rowLimit, setRowLimit] = useState(initialRowLimit);
  const [isFixing, setIsFixing] = useState(false);

  useEffect(() => {
    setRowLimit(initialRowLimit);
  }, [initialRowLimit]);

  useEffect(() => {
    if (!compact && storageKey) {
      try {
        if (sql) localStorage.setItem(storageKey, sql);
        else localStorage.removeItem(storageKey);
      } catch {}
    }
  }, [sql, compact, storageKey]);

  // Sync sql changes to parent tab state
  useEffect(() => {
    if (onSqlChange && sql !== initialSql) {
      onSqlChange(sql);
    }
  }, [sql, onSqlChange]);

  const [isExecuting, setIsExecuting] = useState(false);
  const [queryIdState, setQueryIdState] = useState(null);
  const [executionStatus, setExecutionStatus] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [results, setResults] = useState(null);
  const [execError, setExecError] = useState(null);
  const [isUsingSelection, setIsUsingSelection] = useState(false);
  const editorRef = useRef(null);
  const abortControllerRef = useRef(null);
  const isExecutingRef = useRef(false);

  // Use a Ref + State combo for the execution lock:
  // - Ref is synchronous (no bracing), prevents double-clicks from racing
  // - State drives the UI (button disabled/enabled, loader spinner)
  // Both are set in the same call stack, so they stay in sync.

  // ── Cleanup on unmount: abort any in-flight query execution ──
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  // ── Resizing Split Pane state & listeners ──
  const [topHeight, setTopHeight] = useState(300);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  const startDrag = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newHeight = e.clientY - containerRect.top;
      const totalHeight = containerRect.height || (window.innerHeight - 200);

      if (newHeight >= 100 && (totalHeight - newHeight) >= 80) {
        setTopHeight(newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging]);

  useEffect(() => {
    // Only reset editor contents and pane measurements when the tab changes
    if (initialSql) {
      setSql(initialSql);
    }
    setResults(null);
    setExecError(null);
    setTopHeight(300);
  }, [queryId]);

  // ── External SQL insertion from ChatPanel ──
  useEffect(() => {
    if (externalSql) {
      setSql(externalSql);
      onSqlChange?.(externalSql);
      onExternalSqlConsumed?.();
    }
  }, [externalSql, onSqlChange, onExternalSqlConsumed]);

  const elapsedRef = useRef(null);
  useEffect(() => {
    if (executionStatus === 'running' || executionStatus === 'polling') {
      setElapsed(0);
      const start = Date.now();
      elapsedRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - start) / 1000));
      }, 1000);
    } else {
      if (elapsedRef.current) {
        clearInterval(elapsedRef.current);
        elapsedRef.current = null;
      }
    }
    return () => {
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    };
  }, [executionStatus]);

  const handleCancel = useCallback(async () => {
    // 1. Abort local polling first (stops in-flight axios requests immediately)
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    if (!queryIdState) {
      isExecutingRef.current = false;
      setExecutionStatus('failed');
      setExecError('Query was cancelled');
      setIsExecuting(false);
      return;
    }

    // 2. Tell the server to cancel the backend execution
    try {
      await sqlAPI.cancelQuery(queryIdState);
    } catch (err) {
      // Server cancel may fail (e.g. query already finished), that's fine
    }

    setExecutionStatus('failed');
    setExecError('Query was cancelled');
    setIsExecuting(false);
  }, [queryIdState]);

  const handleRun = useCallback(async () => {
    // ── Ref-based execution lock (synchronous, no stale-state races) ──
    if (!datasetId || isExecutingRef.current) return;
    isExecutingRef.current = true;

    const selectedText = editorRef.current?.getSelectedText?.();
    const sqlToExecute = (selectedText && selectedText.trim())
      ? selectedText.trim()
      : sql.trim();

    if (!sqlToExecute) {
      isExecutingRef.current = false;
      return;
    }
    setIsUsingSelection(!!(selectedText && selectedText.trim()));

    // ── Abort previous in-flight execution ──
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsExecuting(true);
    setExecutionStatus('running');
    setExecError(null);
    setResults(null);
    setQueryIdState(null);

    try {
      const response = await sqlAPI.executeSql(datasetId, sqlToExecute, rowLimit, controller.signal);

      // Guard: if this execution was superseded or unmounted, don't set state
      if (abortControllerRef.current !== controller) return;

      const data = response.data;
      if (data.query_id) {
        setQueryIdState(data.query_id);
      }

      if (data.success) {
        setExecutionStatus('completed');
        setResults({
          columns: data.columns || [],
          rows: data.data || [],
          rowCount: data.row_count || 0,
          executionTimeMs: data.execution_time_ms || 0,
        });
      } else if (data.error === 'Query cancelled') {
        // Intentional cancel — silent, no error toast
        setExecutionStatus('failed');
        setExecError(data.error);
      } else {
        setExecutionStatus('failed');
        setExecError(data.error || 'Query execution failed');
        toast.error(data.error || 'Query execution failed');
      }
    } catch (err) {
      // Guard: don't set state if a newer execution has started
      if (abortControllerRef.current !== controller) return;

      setExecutionStatus('failed');
      const detail = err.response?.data?.detail || err.message || 'Failed to execute query';
      setExecError(detail);
      toast.error('Query execution failed');
    } finally {
      // Only clear the ref if this controller is still the active one
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      isExecutingRef.current = false;
      setIsExecuting(false);
      setIsUsingSelection(false);
    }
  }, [sql, datasetId, rowLimit]);

  const formatSql = useCallback((raw) => {
    const s = raw.trim().replace(/;\s*$/, '') + ';';
    const keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING', 'OFFSET'];
    let result = s;
    for (const kw of keywords) {
      const re = new RegExp(`\\b${kw}\\b`, 'i');
      const match = result.match(re);
      if (match && match.index > 0) {
        result = result.slice(0, match.index) + '\n' + kw + result.slice(match.index + kw.length);
      }
    }
    const lines = result.split('\n');
    const formatted = lines.map((line, i) => {
      const trimmed = line.trim();
      if (i === 0) return trimmed;
      if (/^(SELECT|FROM|WHERE|GROUP|ORDER|LIMIT|HAVING|OFFSET)/.test(trimmed)) return trimmed;
      return '  ' + trimmed;
    }).join('\n');
    return formatted;
  }, []);

  const handleFix = useCallback(async () => {
    if (!sql.trim() || !datasetId || !execError) return;
    setIsFixing(true);
    const toastId = toast.loading('AI is fixing SQL...', { id: 'sql-fix' });

    try {
      const response = await sqlAPI.fixSql(datasetId, sql.trim(), execError);
      const data = response.data;

      if (data.success && data.fixed_sql) {
        setSql(data.fixed_sql);
        setExecError(null);
        setResults(null);
        toast.success('SQL fixed by AI! Run query to verify.', { id: toastId });
      } else {
        toast.error(data.error || 'Could not fix SQL', { id: toastId });
      }
    } catch (err) {
      toast.error('AI Fix failed. Try adjusting SQL manually.', { id: toastId });
    } finally {
      setIsFixing(false);
    }
  }, [sql, datasetId, execError]);

  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.editorId === `sql-editor-${datasetId}`) {
        handleRun();
      }
    };
    document.addEventListener('sql-editor-run', handler);
    return () => document.removeEventListener('sql-editor-run', handler);
  }, [handleRun, datasetId]);

  if (!isOpen) return null;

  const isRunning = executionStatus === 'running' || executionStatus === 'polling';
  const hasResults = results !== null || execError !== null || isExecuting;

  // ── Top Toolbar (Supabase Layout Redesign) ──
  const topToolbar = (
    <div className={cn(
      'flex items-center justify-between gap-3 px-4 py-2 border-b border-border bg-surface select-none flex-wrap shrink-0 w-full',
      compact && 'py-1.5 border-b-0'
    )}>
      {/* Left side: empty spacer */}
      <div />

      {/* Right side controls */}
      <div className="flex items-center gap-3">


        {/* Favorite query toggle */}
        <button
          onClick={onToggleFavorite}
          className={cn(
            "p-1.5 rounded-lg transition-all duration-150 border border-transparent",
            isFavorite
              ? "text-amber-500 bg-amber-500/10 border-amber-500/20"
              : "text-secondary hover:text-header hover:bg-elevated/50"
          )}
          title={isFavorite ? 'Remove from Favorites' : 'Add to Favorites'}
        >
          <Heart size={14} fill={isFavorite ? "currentColor" : "none"} />
        </button>

        {/* Format SQL */}
        <button
          onClick={() => {
            setSql(prev => formatSql(prev));
            toast.success('SQL formatted');
          }}
          disabled={!sql.trim()}
          className="p-1.5 rounded-lg text-secondary hover:text-header hover:bg-elevated/50 border border-transparent transition-all duration-150 disabled:opacity-30"
          title="Format SQL"
        >
          <AlignLeft size={14} />
        </button>

        {/* AI Assistant — opens ChatPanel */}
        <button
          onClick={onToggleChat}
          disabled={!datasetId}
          className="p-1.5 rounded-lg text-secondary hover:text-accent-primary hover:bg-accent-primary/10 border border-transparent transition-all duration-150 disabled:opacity-30"
          title="AI Assistant (generate, explain, browse history)"
        >
          <Bot size={14} />
        </button>

        {/* Save Metric */}
        {onSaveAsMetric && results && !execError && (
          <button
            onClick={() => onSaveAsMetric(sql)}
            className="p-1.5 rounded-lg text-secondary hover:text-header hover:bg-elevated/50 transition-all duration-150 border border-transparent"
            title="Save as Metric"
          >
            <Terminal size={14} />
          </button>
        )}



        {/* Limit Dropdown Selector */}
        {!compact && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-1 px-2 py-1.5 rounded-lg border border-border text-[11px] font-semibold text-secondary hover:text-header hover:bg-elevated/35 transition-all">
                <span>Limit: <strong className="text-header font-bold">{rowLimit === 1000000 ? 'All' : `${rowLimit} rows`}</strong></span>
                <ChevronDown size={11} className="opacity-60 shrink-0 ml-0.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-36 bg-surface border border-border rounded-lg shadow-xl p-1 z-50">
              <DropdownMenuLabel className="px-2 py-1 text-[10px] font-black text-muted/60 uppercase tracking-wider">
                Row Limit Presets
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="my-1 bg-border/40" />
              {[100, 500, 1000, 5000, -1].map((value) => {
                const label = value === -1 ? 'All rows' : `${value} rows`;
                const isSelected = rowLimit === value || (value === -1 && rowLimit === 1000000);
                return (
                  <DropdownMenuItem
                    key={value}
                    onClick={() => setRowLimit(value === -1 ? 1000000 : value)}
                    className={cn(
                      "px-2 py-1.5 text-xs rounded-md cursor-pointer hover:bg-elevated transition-colors flex items-center justify-between",
                      isSelected ? "text-accent-primary bg-accent-primary/5 font-medium" : "text-secondary"
                    )}
                  >
                    <span>{label}</span>
                    {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-accent-primary" />}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        {/* Run Button */}
        <button
          onClick={handleRun}
          disabled={isExecuting || !sql.trim()}
          title={isUsingSelection ? 'Run Selected (Ctrl+Enter / ⌘+Enter)' : 'Run Query (Ctrl+Enter / ⌘+Enter)'}
          className={cn(
            'flex items-center gap-1.5 px-4.5 py-1.5 rounded-lg text-[11px] font-bold tracking-wider transition-all duration-200 active:scale-[0.98]',
            'bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white hover:shadow-md hover:shadow-accent-primary/10',
            'disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:active:scale-100',
            isRunning && 'opacity-85 animate-pulse'
          )}
        >
          {isRunning ? (
            <Loader2 size={11} className="animate-spin text-white" />
          ) : (
            <Play size={10} fill="currentColor" />
          )}
          <span>{isRunning ? `${elapsed}s` : 'RUN'}</span>
          {isUsingSelection && !isRunning && (
            <span className="ml-1 px-1 py-0.2 rounded text-[8px] font-bold bg-white/20 text-white/90">
              Sel
            </span>
          )}
        </button>

        {/* Cancel button */}
        {isRunning && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-1.5 p-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-all duration-150 border border-rose-500/10"
            title="Cancel Execution"
          >
            <Square size={11} fill="currentColor" />
          </button>
        )}
      </div>
    </div>
  );

  // ── Unified Top Layout (Editor Canvas + AI Panels) ──
  const topPane = (
    <div className="flex flex-col h-full w-full bg-primary overflow-hidden">
      {topToolbar}
      
      {/* CodeMirror SQL Editor Canvas */}
      <div className="flex-1 min-h-0 bg-primary">
        <SqlEditor
          ref={editorRef}
          value={sql}
          onChange={setSql}
          columns={columns}
          readOnly={false}
          height="100%"
          placeholder="SELECT region, SUM(revenue) FROM data GROUP BY region ORDER BY SUM(revenue) DESC;"
          editorId={`sql-editor-${datasetId}`}
        />
      </div>

      {/* Removed: AI SQL Generator Input and AI Explanation — now handled by ChatPanel */}
    </div>
  );

  return (
    <div ref={containerRef} className={cn(
      'sql-editor-panel flex flex-col h-full w-full overflow-hidden bg-primary relative',
      compact && 'rounded-xl border border-border bg-surface shadow-2xl border-t-0 rounded-t-none',
      className
    )}>
      {/* Global transparent drag capture overlay */}
      {isDragging && (
        <div className="fixed inset-0 z-50 cursor-row-resize bg-transparent select-none" />
      )}

      {compact ? (
        // Standard stacked layout for small/compact dashboard embeds
        <div className="flex-1 flex flex-col h-full w-full overflow-hidden min-h-0">
          {topToolbar}
          <div className="shrink-0 bg-primary">
            <SqlEditor
              ref={editorRef}
              value={sql}
              onChange={setSql}
              columns={columns}
              readOnly={false}
              height="180px"
              placeholder="SELECT region, SUM(revenue) FROM data GROUP BY region ORDER BY SUM(revenue) DESC;"
              editorId={`sql-editor-${datasetId}`}
            />
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto">
            <SqlResultTable
              columns={results?.columns || []}
              rows={results?.rows || []}
              rowCount={results?.rowCount || 0}
              executionTimeMs={results?.executionTimeMs}
              error={execError}
              isLoading={isExecuting}
              onFix={handleFix}
              isFixing={isFixing}
              rowLimit={rowLimit}
            />
          </div>
        </div>
      ) : (
        // Resizable split layout
        <div className="flex-1 flex flex-col h-full w-full overflow-hidden min-h-0 relative">
          {/* Top Pane: Editor & Toolbar */}
          <div style={{ height: `${topHeight}px` }} className="shrink-0 overflow-hidden w-full flex flex-col">
            {topPane}
          </div>

          {/* Resize Handle (Splitter Bar Divider) */}
          <div
            onMouseDown={startDrag}
            className="h-2 w-full cursor-row-resize relative z-20 shrink-0 flex items-center justify-center bg-border/40 hover:bg-accent-primary/25 transition-all duration-150"
            title="Drag to resize panels"
          >
            {/* Grab Handle Icon — Always Visible */}
            <div className="px-1.5 py-0.5 rounded bg-surface border border-border flex items-center justify-center hover:border-accent-primary/45 hover:text-accent-primary text-muted/60 transition-colors shadow-sm relative z-30 scale-90">
              <GripHorizontal size={13} />
            </div>
          </div>

          {/* Bottom Pane: Results Grid */}
          <div className="flex-1 min-h-0 overflow-hidden w-full flex flex-col bg-surface">
            {/* Supabase-style tab header inside bottom split-pane */}
            <div className="flex items-center gap-4 px-4 border-b border-border bg-surface/30 h-8 select-none shrink-0">
              <button className="h-full border-b-2 border-accent-primary text-[11px] font-bold text-header px-1">
                Results
              </button>
            </div>

            <div className="flex-1 min-h-0 w-full flex flex-col">
              <SqlResultTable
                columns={results?.columns || []}
                rows={results?.rows || []}
                rowCount={results?.rowCount || 0}
                executionTimeMs={results?.executionTimeMs}
                error={execError}
                isLoading={isExecuting}
                onFix={handleFix}
                isFixing={isFixing}
                isInitial={results === null && execError === null && !isExecuting}
                rowLimit={rowLimit}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

SqlEditorPanel.displayName = 'SqlEditorPanel';

export default SqlEditorPanel;
