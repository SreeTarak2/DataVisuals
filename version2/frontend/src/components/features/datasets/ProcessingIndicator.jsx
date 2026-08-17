import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Loader2, AlertTriangle, RefreshCw, Database } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import useDatasetStore from '@/store/datasetStore';

/**
 * ProcessingIndicator — global view of in-flight dataset jobs.
 *
 * Shown in the header while any dataset is being processed (or has failed):
 * - Amber pill with a spinner + job count while jobs are running.
 * - Red pill with an alert icon when nothing is running but something failed.
 * - Click → dropdown: in-flight jobs with live stage + progress bar, and
 *   failed jobs (red) with an inline Retry action.
 * - Clicking a job navigates to that dataset's dashboard.
 *
 * Updates arrive instantly via the WebSocket `processing_update` push
 * (patched into the dataset store), with an 8s poll as fallback while any
 * job is running. Polling stops automatically when nothing is in flight.
 */

// Statuses that mean "still working" (matches the backend state map).
const ACTIVE_STATUSES = new Set([
  'pending', 'queued', 'running',
  'loading', 'cleaning', 'normalizing', 'metadata', 'domain_detection',
  'kpi_pipeline', 'profiling', 'analysis', 'quis_analysis', 'charts',
  'quality', 'consolidating', 'saving', 'artifact_generation',
  'strategic_advisor', 'vector_indexing',
]);

const getDatasetId = (d) => d?.id || d?._id || null;

const humanize = (value) =>
  String(value || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

const ProcessingIndicator = ({ className }) => {
  const navigate = useNavigate();
  const { datasets, fetchDatasets, setSelectedDataset, reprocessDataset } = useDatasetStore();

  const [isOpen, setIsOpen] = useState(false);
  const [retrying, setRetrying] = useState(null);
  const rootRef = useRef(null);

  const inFlight = datasets.filter(
    (d) => ACTIVE_STATUSES.has(String(d.processing_status || d.status || '').toLowerCase())
  );
  const failed = datasets.filter(
    (d) => String(d.processing_status || d.status || '').toLowerCase() === 'failed'
  );

  const hasJobs = inFlight.length > 0 || failed.length > 0;

  // Poll while jobs are in flight (WS pushes cover the real-time path; the
  // poll is the fallback when the socket is down). Stops automatically.
  useEffect(() => {
    if (inFlight.length === 0) return undefined;
    const interval = setInterval(() => {
      fetchDatasets(true).catch((err) => console.warn('Processing poll failed:', err));
    }, 8000);
    return () => clearInterval(interval);
  }, [inFlight.length, fetchDatasets]);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (!rootRef.current?.contains(e.target)) setIsOpen(false);
    };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, [isOpen]);

  const handleToggle = () => {
    setIsOpen((open) => !open);
    if (!isOpen) {
      // Pull fresh statuses when the dropdown opens
      fetchDatasets(true, true).catch(() => {});
    }
  };

  const handleOpenDataset = useCallback((dataset) => {
    setSelectedDataset(dataset);
    setIsOpen(false);
    navigate('/app/dashboard');
  }, [navigate, setSelectedDataset]);

  const handleRetry = useCallback(async (e, dataset) => {
    e.stopPropagation();
    const id = getDatasetId(dataset);
    if (!id) return;
    setRetrying(id);
    try {
      await reprocessDataset(id);
    } finally {
      setRetrying(null);
    }
  }, [reprocessDataset]);

  if (!hasJobs) return null;

  const count = inFlight.length;
  const isProcessing = inFlight.length > 0;

  return (
    <div className={cn('relative', className)} ref={rootRef}>
      <button
        onClick={handleToggle}
        className={cn(
          'flex items-center gap-1.5 pl-2 pr-2.5 h-8 rounded-lg transition-all hover:scale-[1.04] active:scale-95',
          isOpen && 'bg-[var(--bg-active)]/50'
        )}
        style={{
          color: isProcessing ? 'var(--accent-warning, #f59e0b)' : 'var(--accent-error, #ef4444)',
          backgroundColor: isProcessing
            ? 'rgba(245, 158, 11, 0.08)'
            : 'rgba(239, 68, 68, 0.08)',
          border: '1px solid',
          borderColor: isProcessing
            ? 'rgba(245, 158, 11, 0.25)'
            : 'rgba(239, 68, 68, 0.25)',
        }}
        title={isProcessing ? `${count} dataset${count === 1 ? '' : 's'} processing` : `${failed.length} dataset${failed.length === 1 ? '' : 's'} failed`}
        aria-label={isProcessing ? `${count} datasets processing` : `${failed.length} failed datasets`}
      >
        {isProcessing ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <AlertTriangle className="w-3.5 h-3.5" />
        )}
        <span className="text-[11px] font-bold tabular-nums">
          {isProcessing ? count : failed.length}
        </span>
      </button>

      {isOpen && (
        <div
          className="absolute right-0 top-full mt-1.5 z-50 w-[340px] max-w-[calc(100vw-24px)] overflow-hidden rounded-lg"
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
            <span className="text-[13px] font-semibold" style={{ color: 'var(--text-header)' }}>
              {isProcessing ? 'Processing' : 'Needs attention'}
              {(inFlight.length > 0 || failed.length > 0) && (
                <span className="ml-2 text-[11px] font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {inFlight.length} running{failed.length > 0 ? ` · ${failed.length} failed` : ''}
                </span>
              )}
            </span>
            <button
              onClick={() => fetchDatasets(true, true).catch(() => {})}
              className="p-1.5 rounded-md transition-colors hover:bg-[var(--bg-active)]/50"
              style={{ color: 'var(--text-secondary)' }}
              title="Refresh status"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* In-flight jobs */}
          {inFlight.length > 0 && (
            <div className="border-b" style={{ borderColor: 'var(--border)' }}>
              <div className="px-3 pt-2.5 pb-1 text-[10px] uppercase tracking-[0.08em] font-medium" style={{ color: 'var(--text-muted)' }}>
                Running
              </div>
              {inFlight.map((ds) => {
                const progress = Math.min(100, Math.max(0, Number(ds.processing_progress || 0)));
                const stage = ds.current_stage_label || humanize(ds.processing_status);
                return (
                  <button
                    key={getDatasetId(ds)}
                    onClick={() => handleOpenDataset(ds)}
                    className="w-full flex items-start gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-[var(--bg-active)]/40"
                  >
                    <div
                      className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                      style={{ backgroundColor: 'rgba(245, 158, 11, 0.12)' }}
                    >
                      <Database className="w-3 h-3" style={{ color: 'var(--accent-warning, #f59e0b)' }} />
                    </div>
                    <span className="flex-1 min-w-0">
                      <span className="flex items-center gap-1.5">
                        <span className="block text-[13px] font-medium truncate" style={{ color: 'var(--text-header)' }}>
                          {ds.name || ds.filename || 'Unnamed'}
                        </span>
                        <Loader2 className="w-3 h-3 animate-spin shrink-0" style={{ color: 'var(--accent-warning, #f59e0b)' }} />
                      </span>
                      <span className="block mt-0.5 text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                        {stage} · {progress}%
                      </span>
                      <span className="block mt-1.5 h-1 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--bg-active, rgba(255,255,255,0.06))' }}>
                        <span
                          className="block h-full rounded-full transition-all duration-500"
                          style={{ width: `${progress}%`, backgroundColor: 'var(--accent-warning, #f59e0b)' }}
                        />
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Failed jobs */}
          {failed.length > 0 && (
            <div>
              <div className="px-3 pt-2.5 pb-1 text-[10px] uppercase tracking-[0.08em] font-medium" style={{ color: 'var(--text-muted)' }}>
                Failed
              </div>
              {failed.map((ds) => {
                const id = getDatasetId(ds);
                const error = ds.processing_error || ds.error || 'Processing failed';
                const isRetrying = retrying === id;
                return (
                  <div
                    key={id}
                    role="button"
                    tabIndex={0}
                    onClick={() => handleOpenDataset(ds)}
                    onKeyDown={(e) => e.key === 'Enter' && handleOpenDataset(ds)}
                    className="w-full flex items-start gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-[var(--bg-active)]/40 cursor-pointer"
                  >
                    <div
                      className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                      style={{ backgroundColor: 'rgba(239, 68, 68, 0.12)' }}
                    >
                      <AlertTriangle className="w-3 h-3" style={{ color: 'var(--accent-error, #ef4444)' }} />
                    </div>
                    <span className="flex-1 min-w-0">
                      <span className="block text-[13px] font-medium truncate" style={{ color: 'var(--text-header)' }}>
                        {ds.name || ds.filename || 'Unnamed'}
                      </span>
                      <span className="block mt-0.5 text-[11px] leading-snug line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
                        {error}
                      </span>
                    </span>
                    <button
                      onClick={(e) => handleRetry(e, ds)}
                      disabled={isRetrying}
                      className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-colors shrink-0 disabled:opacity-50"
                      style={{
                        color: 'var(--accent-error, #ef4444)',
                        background: 'rgba(239, 68, 68, 0.08)',
                        border: '1px solid rgba(239, 68, 68, 0.25)',
                      }}
                      title="Retry processing"
                    >
                      {isRetrying ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <RefreshCw className="w-3 h-3" />
                      )}
                      Retry
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ProcessingIndicator;
