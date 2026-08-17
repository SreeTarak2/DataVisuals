import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  History, Search, X, Clock, Database, Loader2,
  CheckCircle2, XCircle, Ban, AlertCircle, Trash2,
  Code2, ArrowRight
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';
import { sqlAPI } from '@/services/api';
import { ScrollArea } from '@/components/ui/scroll-area';

/**
 * QueryHistoryDrawer — Slide-out panel for browsing past SQL queries.
 *
 * Fetches history from GET /api/v2/query/history (already stored by the
 * backend on every query execution).  Clicking an entry restores the SQL
 * into the editor.  Delete is supported via DELETE /api/v2/query/{id}.
 */
const QueryHistoryDrawer = ({
  isOpen,
  onClose,
  onRestoreSql,
  datasetId = null,
}) => {
  const [queries, setQueries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [deletingIds, setDeletingIds] = useState(new Set());
  const searchRef = useRef(null);

  // ── Fetch history when drawer opens ───────────────────────────────
  const fetchHistory = useCallback(async () => {
    if (!isOpen) return;
    setLoading(true);
    try {
      const res = await sqlAPI.getQueryHistory(datasetId, 50, 0);
      const data = res.data;
      setQueries(data.queries || []);
    } catch (err) {
      console.error('Failed to fetch query history:', err);
      toast.error('Could not load query history');
      setQueries([]);
    } finally {
      setLoading(false);
    }
  }, [isOpen, datasetId]);

  useEffect(() => {
    if (isOpen) {
      fetchHistory();
      // Auto-focus search after animation
      setTimeout(() => searchRef.current?.focus(), 250);
    }
  }, [isOpen, fetchHistory]);

  // ── Delete ────────────────────────────────────────────────────────
  const handleDelete = useCallback(async (e, entry) => {
    e.stopPropagation();
    if (deletingIds.has(entry.query_id)) return;

    setDeletingIds((prev) => new Set(prev).add(entry.query_id));
    try {
      await sqlAPI.deleteQuery(entry.query_id);
      setQueries((prev) => prev.filter((q) => q.query_id !== entry.query_id));
      toast.success('Query deleted');
    } catch (err) {
      toast.error('Failed to delete query');
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(entry.query_id);
        return next;
      });
    }
  }, [deletingIds]);

  // ── Restore SQL → editor ──────────────────────────────────────────
  const handleRestore = useCallback((entry) => {
    onRestoreSql(entry.sql);
    onClose();
    toast.success('Query restored to editor');
  }, [onRestoreSql, onClose]);

  // ── Helpers ───────────────────────────────────────────────────────

  /** Extract first meaningful line from SQL for the preview snippet */
  const getSqlPreview = (sql) => {
    const cleaned = sql
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('--'))
      .join(' ');
    return cleaned.length > 90 ? cleaned.slice(0, 87) + '...' : cleaned;
  };

  /** Human-friendly relative timestamp */
  const formatTime = (isoStr) => {
    if (!isoStr) return '';
    const date = new Date(isoStr);
    const now = Date.now();
    const diffMs = now - date.getTime();

    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;

    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;

    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;

    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  /** Status icon + colour */
  const statusMeta = (status) => {
    switch (status) {
      case 'completed':
        return { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/[0.08]' };
      case 'failed':
        return { icon: XCircle, color: 'text-rose-400', bg: 'bg-rose-500/[0.08]' };
      case 'cancelled':
        return { icon: Ban, color: 'text-zinc-400', bg: 'bg-zinc-500/[0.08]' };
      case 'running':
      case 'queued':
        return { icon: Loader2, color: 'text-amber-400', bg: 'bg-amber-500/[0.08]', spin: true };
      default:
        return { icon: AlertCircle, color: 'text-zinc-400', bg: 'bg-zinc-500/[0.08]' };
    }
  };

  // ── Filtered list ─────────────────────────────────────────────────
  const filtered = search.trim()
    ? queries.filter((q) =>
        q.sql.toLowerCase().includes(search.toLowerCase())
      )
    : queries;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
          />

          {/* Drawer Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 z-50 w-[420px] max-w-[90vw] bg-surface border-l border-border shadow-2xl shadow-black/20 flex flex-col"
          >
            {/* ── Header ── */}
            <div className="shrink-0 px-5 pt-5 pb-3 border-b border-border">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-accent-primary/10 flex items-center justify-center">
                    <History size={15} className="text-accent-primary" />
                  </div>
                  <div>
                    <h2 className="text-[11px] font-black text-header uppercase tracking-[0.15em]">
                      Query History
                    </h2>
                    <p className="text-[9.5px] text-muted/60 mt-0.5">
                      {loading ? 'Loading...' : `${queries.length} queries`}
                    </p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg text-muted/40 hover:text-header hover:bg-elevated/50 transition-all duration-150 border border-transparent hover:border-border/40"
                >
                  <X size={14} />
                </button>
              </div>

              {/* Search */}
              <div className="relative group">
                <Search
                  size={13}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted/40 group-focus-within:text-accent-primary transition-colors"
                  strokeWidth={2.5}
                />
                <input
                  ref={searchRef}
                  type="text"
                  placeholder="Search queries..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full bg-elevated/10 hover:bg-elevated/25 border border-border/40 focus:border-accent-primary/45 rounded-xl !pl-9 pr-3 py-1.5 text-[11.5px] font-medium text-header placeholder:text-muted/30 focus:outline-none transition-all duration-200"
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-muted/30 hover:text-header transition-colors"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            </div>

            {/* ── List ── */}
            <ScrollArea className="flex-1 px-3 py-2 [&>*]:h-full">
              {/* Loading state */}
              {loading && (
                <div className="flex items-center justify-center gap-2.5 py-20 text-muted">
                  <Loader2 size={14} className="animate-spin text-accent-primary" />
                  <span className="text-[11px] font-medium uppercase tracking-wider">
                    Loading history...
                  </span>
                </div>
              )}

              {/* Empty state */}
              {!loading && queries.length === 0 && (
                <div className="flex flex-col items-center gap-3 py-20 text-muted px-8 text-center">
                  <div className="w-12 h-12 rounded-xl bg-elevated/20 flex items-center justify-center border border-border/30">
                    <History size={18} className="opacity-50" />
                  </div>
                  <span className="text-xs font-semibold text-header">No Query History Yet</span>
                  <span className="text-[10.5px] text-muted/60 leading-relaxed max-w-[220px]">
                    Run a query and it will automatically appear here for quick reuse.
                  </span>
                </div>
              )}

              {/* No search results */}
              {!loading && queries.length > 0 && filtered.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-16 text-muted">
                  <Search size={18} className="opacity-30" />
                  <span className="text-xs">
                    No matches for &quot;{search}&quot;
                  </span>
                </div>
              )}

              {/* Entry list */}
              {!loading && filtered.length > 0 && (
                <div className="space-y-1 pb-2">
                  {filtered.map((entry) => {
                    const status = statusMeta(entry.status);
                    const StatusIcon = status.icon;
                    return (
                      <div
                        key={entry.query_id}
                        onClick={() => handleRestore(entry)}
                        className="group relative flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all duration-150 hover:bg-elevated/40 border border-transparent hover:border-border/30 active:scale-[0.99]"
                      >
                        {/* Status icon */}
                        <div className={cn(
                          'mt-0.5 w-6 h-6 rounded-md flex items-center justify-center shrink-0',
                          status.bg
                        )}>
                          <StatusIcon
                            size={12}
                            className={cn(status.color, status.spin && 'animate-spin')}
                          />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0 space-y-1">
                          {/* SQL preview */}
                          <div className="flex items-start gap-2">
                            <code className="flex-1 text-[11px] font-mono leading-relaxed text-secondary truncate group-hover:text-header transition-colors">
                              {getSqlPreview(entry.sql)}
                            </code>
                          </div>

                          {/* Metadata row */}
                          <div className="flex items-center gap-2.5 flex-wrap text-[9.5px] text-muted/60">
                            {/* Timestamp */}
                            <span className="flex items-center gap-1">
                              <Clock size={9} strokeWidth={2.5} />
                              {formatTime(entry.created_at)}
                            </span>

                            {/* Execution time */}
                            {entry.execution_time_ms != null && entry.status === 'completed' && (
                              <span className="font-mono">
                                {entry.execution_time_ms < 1000
                                  ? `${entry.execution_time_ms}ms`
                                  : `${(entry.execution_time_ms / 1000).toFixed(1)}s`}
                              </span>
                            )}

                            {/* Row count */}
                            {entry.row_count != null && entry.status === 'completed' && (
                              <span>
                                {entry.row_count.toLocaleString()} rows
                              </span>
                            )}

                            {/* Status label */}
                            <span className={cn('capitalize', status.color)}>
                              {entry.status}
                            </span>

                            {/* Dataset hint */}
                            {entry.dataset_id && datasetId && entry.dataset_id !== datasetId && (
                              <span className="flex items-center gap-1 opacity-50">
                                <Database size={9} />
                                different dataset
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Restore hint + Delete */}
                        <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                          <button
                            onClick={(e) => handleDelete(e, entry)}
                            disabled={deletingIds.has(entry.query_id)}
                            className="p-1.5 rounded-lg text-muted/40 hover:text-rose-400 hover:bg-rose-500/10 transition-all duration-150"
                            title="Delete this query"
                          >
                            {deletingIds.has(entry.query_id) ? (
                              <Loader2 size={11} className="animate-spin" />
                            ) : (
                              <Trash2 size={11} />
                            )}
                          </button>
                          <ArrowRight size={12} className="text-accent-primary/40" />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </ScrollArea>

            {/* ── Footer hint ── */}
            <div className="shrink-0 px-5 py-3 border-t border-border/50 bg-elevated/5">
              <p className="text-[9px] text-muted/40 text-center font-mono">
                Click any query to restore · Hover for delete
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default QueryHistoryDrawer;
