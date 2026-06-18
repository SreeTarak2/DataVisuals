import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';

import useDatasetStore from '../../../store/datasetStore';
import { datasetAPI } from '../../../services/api';
import { toast } from 'react-hot-toast';

// ── Fallback steps (used when /stages endpoint returns no data yet) ──────────
const FALLBACK_STEPS = [
  { key: 'uploaded', label: 'Upload Complete' },
  { key: 'loading', label: 'Loading Dataset' },
  { key: 'cleaning', label: 'Cleaning Data' },
  { key: 'domain_detection', label: 'Detecting Domain' },
  { key: 'profiling', label: 'Profiling Data' },
  { key: 'analysis', label: 'Running Analysis' },
  { key: 'quis_analysis', label: 'Deep Analysis' },
  { key: 'charts', label: 'Generating Charts' },
  { key: 'quality', label: 'Calculating Quality' },
  { key: 'consolidating', label: 'Consolidating' },
  { key: 'saving', label: 'Saving' },
  { key: 'artifact_generation', label: 'AI Generation' },
  { key: 'vector_indexing', label: 'Indexing' },
];

const FALLBACK_PROGRESS_MAP = [
  { max: 5, key: 'loading' },
  { max: 15, key: 'cleaning' },
  { max: 25, key: 'domain_detection' },
  { max: 35, key: 'profiling' },
  { max: 55, key: 'analysis' },
  { max: 65, key: 'quis_analysis' },
  { max: 70, key: 'charts' },
  { max: 80, key: 'quality' },
  { max: 85, key: 'consolidating' },
  { max: 90, key: 'saving' },
  { max: 96, key: 'artifact_generation' },
  { max: 100, key: 'vector_indexing' },
];

// Max progress to show during fallback mode (before real /stages data arrives).
// Prevents the bar from jumping to 99% before any stages are visible.
const FALLBACK_MAX_PROGRESS = 50;

// ── Icons ────────────────────────────────────────────────────────────────────

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" strokeWidth="1.8" xmlns="http://www.w3.org/2000/svg">
    <path d="M2 7.5l3.5 3.5 6.5-7" strokeLinecap="round" strokeLinejoin="round" stroke="currentColor"/>
  </svg>
);

const SpinnerIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.3"/>
    <path d="M7 1.5A5.5 5.5 0 0 1 12.5 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const ErrorIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" strokeWidth="1.5" xmlns="http://www.w3.org/2000/svg">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor"/>
    <path d="M5 5l4 4M9 5l-4 4" stroke="currentColor" strokeLinecap="round"/>
  </svg>
);

const CloseIcon = () => (
  <svg width="12" height="12" viewBox="0 0 14 14" fill="none" strokeWidth="1.5" xmlns="http://www.w3.org/2000/svg">
    <path d="M1 1l12 12M13 1L1 13" stroke="currentColor"/>
  </svg>
);

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = `
  .pm-backdrop {
    position: fixed;
    inset: 0;
    background: var(--bg-overlay);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 70;
  }

  .pm-modal {
    width: 520px;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow: hidden;
    box-shadow: var(--shadow-lg);
  }

  .pm-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-elevated);
  }

  .pm-header-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent-primary);
    box-shadow: 0 0 6px var(--accent-primary);
    animation: pm-pulse 2s ease-in-out infinite;
  }

  @keyframes pm-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  .pm-header-label {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-secondary);
  }

  .pm-header-badge {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--accent-primary);
    background: var(--accent-primary-light);
    border: 1px solid rgba(47,128,237,0.2);
    padding: 2px 8px;
    border-radius: 2px;
    letter-spacing: 0.06em;
  }

  .pm-body {
    padding: 24px 20px 20px;
  }

  .pm-title-block {
    margin-bottom: 24px;
  }

  .pm-title-block h2 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-header);
    letter-spacing: -0.01em;
    margin-bottom: 4px;
  }

  .pm-title-block p {
    font-size: 12px;
    color: var(--text-secondary);
    font-weight: 400;
  }

  .pm-progress-section {
    margin-bottom: 24px;
  }

  .pm-progress-meta {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }

  .pm-progress-stage {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-secondary);
    letter-spacing: 0.04em;
  }

  .pm-progress-pct {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 600;
    color: var(--accent-primary);
    letter-spacing: 0.02em;
  }

  .pm-progress-track {
    height: 3px;
    background: var(--border);
    border-radius: 0;
    overflow: hidden;
    position: relative;
  }

  .pm-progress-fill {
    height: 100%;
    background: var(--accent-primary);
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .pm-progress-sub {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 6px;
    font-family: var(--font-mono);
  }

  .pm-steps {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0;
    border: 1px solid var(--border);
    border-radius: 2px;
    overflow: hidden;
  }

  .pm-step {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 9px 14px;
    border-bottom: 1px solid var(--border);
    position: relative;
    transition: background 0.2s;
  }

  .pm-step:last-child {
    border-bottom: none;
  }

  .pm-step.done {
    background: transparent;
  }

  .pm-step.active {
    background: var(--accent-primary-light);
  }

  .pm-step.failed {
    background: rgba(239, 68, 68, 0.08);
  }

  .pm-step-icon {
    width: 16px;
    height: 16px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pm-step-icon.done {
    color: var(--accent-success);
  }

  .pm-step-icon.active {
    color: var(--accent-primary);
    animation: pm-spin 0.7s linear infinite;
  }

  .pm-step-icon.failed {
    color: var(--accent-error);
  }

  @keyframes pm-spin {
    to { transform: rotate(360deg); }
  }

  .pm-step-icon.pending {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pm-step-icon.pending::before {
    content: '';
    width: 5px;
    height: 5px;
    background: var(--text-muted);
    border-radius: 50%;
  }

  .pm-step-label {
    font-size: 12px;
    font-weight: 500;
    font-family: var(--font-sans);
    letter-spacing: 0.01em;
  }

  .pm-step.done .pm-step-label {
    color: var(--text-secondary);
  }

  .pm-step.active .pm-step-label {
    color: var(--text-header);
  }

  .pm-step.failed .pm-step-label {
    color: var(--accent-error);
  }

  .pm-step.pending .pm-step-label {
    color: var(--text-muted);
  }

  .pm-step-time {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .pm-step.done .pm-step-time {
    color: var(--accent-success);
    opacity: 0.7;
  }

  .pm-step.active .pm-step-time {
    color: var(--accent-primary);
  }

  .pm-step.failed .pm-step-time {
    color: var(--accent-error);
  }

  .pm-step-error {
    font-size: 10px;
    color: var(--accent-error);
    font-family: var(--font-mono);
    margin-top: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 300px;
    opacity: 0.8;
  }

  .pm-footer {
    padding: 16px 20px;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .pm-footer-info {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .pm-footer-actions {
    display: flex;
    gap: 8px;
  }

  .pm-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    font-family: var(--font-sans);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    border-radius: 4px;
    transition: border-color 0.15s, color 0.15s, background 0.15s;
    letter-spacing: 0.02em;
  }

  .pm-btn:hover {
    border-color: var(--border-hover);
    color: var(--text-primary);
    background: rgba(255,255,255,0.04);
  }

  .pm-btn-primary {
    background: var(--accent-primary-light);
    border-color: var(--accent-primary);
    color: var(--accent-primary);
  }

  .pm-btn-primary:hover {
    background: rgba(47,128,237,0.2);
    border-color: var(--accent-primary);
    color: var(--accent-primary);
  }

  .pm-btn-danger {
    background: rgba(239,68,68,0.1);
    border-color: var(--accent-error);
    color: var(--accent-error);
  }

  .pm-btn-danger:hover {
    background: rgba(239,68,68,0.2);
  }

  .pm-complete-icon {
    width: 48px;
    height: 48px;
    margin: 0 auto 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(63,185,80,0.15);
    border-radius: 50%;
  }

  .pm-complete-icon svg {
    color: var(--accent-success);
  }

  .pm-stage-error-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    margin-bottom: 12px;
    background: rgba(239,68,68,0.06);
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: 2px;
    font-size: 11px;
    color: var(--accent-error);
    font-family: var(--font-mono);
  }
`;


// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDuration(ms) {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const min = Math.floor(ms / 60000);
  const sec = Math.floor((ms % 60000) / 1000);
  return `${min}m ${sec}s`;
}

function getFallbackStageFromProgress(progressValue, processingStatus) {
  if (processingStatus === 'completed' || processingStatus === 'success') {
    return { key: 'completed', progress: 100 };
  }
  for (const stage of FALLBACK_PROGRESS_MAP) {
    if (progressValue <= stage.max) {
      return { key: stage.key, progress: progressValue };
    }
  }
  return { key: 'artifact_generation', progress: progressValue };
}

function getFallbackStepState(stepKey, currentKey, isComplete) {
  if (isComplete || currentKey === 'completed') return 'done';
  const currentIdx = FALLBACK_STEPS.findIndex(s => s.key === currentKey);
  const stepIdx = FALLBACK_STEPS.findIndex(s => s.key === stepKey);
  if (stepIdx === -1 || currentIdx === -1) return 'pending';
  if (stepIdx < currentIdx) return 'done';
  if (stepIdx === currentIdx) return 'active';
  return 'pending';
}

// ── Component ────────────────────────────────────────────────────────────────

const ProcessingModal = ({ isOpen, datasetId, onClose }) => {
  const navigate = useNavigate();
  const { fetchDatasets, clearProcessingState, reprocessDataset } = useDatasetStore();

  // Real stage data from /stages endpoint
  const [stages, setStages] = useState([]);
  const [stagesLoaded, setStagesLoaded] = useState(false);

  // Fallback state (when stages endpoint returns empty)
  const [fallbackStage, setFallbackStage] = useState('uploaded');
  const [fallbackProgress, setFallbackProgress] = useState(0);

  const [isComplete, setIsComplete] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  const datasetPollRef = useRef(null);
  const stagesPollRef = useRef(null);
  const navigateRef = useRef(false);
  const highestProgressRef = useRef(0);

  // ── Determine effective state ──────────────────────────────────────────────
  const useRealStages = stagesLoaded && stages.length > 0;

  // Current running stage label (for progress bar header)
  const currentStageLabel = useRealStages
    ? (() => {
        const running = stages.find(s => s.status === 'running');
        const failed = stages.find(s => s.status === 'failed');
        const lastDone = [...stages].reverse().find(s => s.status === 'done');
        return running?.label || failed?.label || lastDone?.label || '';
      })()
    : FALLBACK_STEPS.find(s => s.key === fallbackStage)?.label || '';

  // Compute raw progress, then clamp it so it never visually regresses.
  const rawProgress = useRealStages
    ? (() => {
        const done = stages.filter(s => s.status === 'done').length;
        const total = stages.length || 15;
        return Math.min(Math.round((done / total) * 100), 99);
      })()
    : Math.min(fallbackProgress, FALLBACK_MAX_PROGRESS);

  // Mutate ref during render (not effect) so the progress never
  // flickers backward on the next paint when switching fallback→real stages.
  if (rawProgress > highestProgressRef.current) {
    highestProgressRef.current = rawProgress;
  }
  const currentProgress = highestProgressRef.current;

  // ── Polling ────────────────────────────────────────────────────────────────

  const checkProcessingStatus = async () => {
    if (!datasetId || navigateRef.current) return;

    try {
      const datasets = await fetchDatasets(true);
      const dataset = datasets.find(d => d.id === datasetId || d._id === datasetId);

      if (!dataset) return;

      const dsProgress = dataset.processing_progress || 0;
      const dsStatus = dataset.processing_status || '';
      const artifactStatus = dataset.artifact_status || {};
      const isProcessed = dataset.is_processed;

      // Update fallback state (cap progress during fallback to avoid misleading 99%)
      const cappedProgress = Math.min(dsProgress, FALLBACK_MAX_PROGRESS);
      const { key, progress } = getFallbackStageFromProgress(cappedProgress, dsStatus);
      setFallbackStage(key);
      setFallbackProgress(progress);

      // Check completion
      const dashboardReady = artifactStatus.dashboard_design === 'ready';
      const insightsReady = artifactStatus.insights_report === 'ready';

      if (isProcessed && dashboardReady && insightsReady) {
        setIsComplete(true);
        setHasError(false);
        if (datasetPollRef.current) clearInterval(datasetPollRef.current);
        if (stagesPollRef.current) clearInterval(stagesPollRef.current);
        datasetPollRef.current = null;
        stagesPollRef.current = null;
        toast.success('Processing complete!', { id: 'processing-complete' });
      } else if (dataset.processing_status === 'failed') {
        setHasError(true);
      }
    } catch (err) {
      console.error('Error checking processing status:', err);
    }
  };

  const fetchStagesData = async () => {
    if (!datasetId || navigateRef.current) return;

    try {
      const response = await datasetAPI.getDatasetStages(datasetId);
      const fetched = response.data?.stages || [];
      
      // Deduplicate stages by name or label, keeping the latest state 
      // but preserving original sequence order.
      const uniqueStagesMap = new Map();
      fetched.forEach(stage => {
        const key = stage.name || stage.label;
        if (key) {
          uniqueStagesMap.set(key, stage);
        }
      });
      const deduplicatedStages = Array.from(uniqueStagesMap.values());
      
      setStages(deduplicatedStages);
      if (!stagesLoaded && deduplicatedStages.length > 0) {
        setStagesLoaded(true);
      }
      // If stages are empty but we've been polling for a while, mark as loaded
      // so the UI doesn't wait forever for the first stage to appear
      if (!stagesLoaded && stagesPollRef.current) {
        // After 10 seconds, give up waiting for stages and use fallback
      }
    } catch {
      // Silently ignore — stages endpoint may not exist for legacy datasets
    }
  };

  useEffect(() => {
    if (!isOpen || !datasetId) return;

    // Reset state
    setStages([]);
    setStagesLoaded(false);
    setFallbackStage('uploaded');
    setFallbackProgress(0);
    setIsComplete(false);
    setHasError(false);
    navigateRef.current = false;
    highestProgressRef.current = 0;

    // Initial fetch
    checkProcessingStatus();
    fetchStagesData();

    datasetPollRef.current = setInterval(checkProcessingStatus, 5000);
    stagesPollRef.current = setInterval(fetchStagesData, 5000);

    // Fallback: if no stages appear after 10s, use progress-based display
    const fallbackTimer = setTimeout(() => {
      if (stages.length === 0) {
        setStagesLoaded(true); // signals "use fallback since no stages available"
      }
    }, 10000);

    return () => {
      if (datasetPollRef.current) clearInterval(datasetPollRef.current);
      if (stagesPollRef.current) clearInterval(stagesPollRef.current);
      clearTimeout(fallbackTimer);
      datasetPollRef.current = null;
      stagesPollRef.current = null;
    };
  }, [isOpen, datasetId, retryKey]);

  // Once fallback timer fires, check if we got stages
  useEffect(() => {
    if (stages.length > 0 && !stagesLoaded) {
      setStagesLoaded(true);
    }
  }, [stages]);

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleGoToDashboard = () => {
    navigateRef.current = true;
    clearProcessingState();
    if (onClose) onClose();
    navigate('/app/dashboard');
  };

  const handleGoToProfile = () => {
    navigateRef.current = true;
    clearProcessingState();
    if (onClose) onClose();
    navigate(`/app/datasets/${datasetId}/profile`);
  };

  const handleGoToDatasets = () => {
    navigateRef.current = true;
    clearProcessingState();
    if (onClose) onClose();
    navigate('/app/datasets');
  };

  const handleRetry = async () => {
    setHasError(false);
    setStages([]);
    setStagesLoaded(false);
    setFallbackStage('uploaded');
    setFallbackProgress(0);
    setIsComplete(false);
    setRetryKey(k => k + 1);

    const result = await reprocessDataset(datasetId);
    if (!result?.success) {
      setHasError(true);
    }
  };

  const handleClose = () => {
    clearProcessingState();
    if (onClose) onClose();
  };

  if (!isOpen) return null;

  // ── Stage rendering ────────────────────────────────────────────────────────

  const renderRealStages = () => {
    // Determine which step is active (the first "running" stage)
    const activeIdx = stages.findIndex(s => s.status === 'running');
    const failedIdx = stages.findIndex(s => s.status === 'failed');
    const hasAnyFailed = failedIdx !== -1;

    const getState = (index) => {
      if (index < activeIdx || (hasAnyFailed && index < failedIdx)) return 'done';
      if (index === activeIdx) return 'active';
      if (index === failedIdx) return 'failed';
      return 'pending';
    };

    return stages.map((stage, idx) => (
      <li key={stage.name || idx} className={`pm-step ${getState(idx)}`}>
        <span className={`pm-step-icon ${getState(idx)}`}>
          {getState(idx) === 'done' && <CheckIcon />}
          {getState(idx) === 'active' && <SpinnerIcon />}
          {getState(idx) === 'failed' && <ErrorIcon />}
          {getState(idx) === 'pending' && null}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span className="pm-step-label">{stage.label || stage.name}</span>
          {stage.error && (
            <div className="pm-step-error" title={stage.error}>
              {stage.error}
            </div>
          )}
        </div>
        <span className="pm-step-time">
          {getState(idx) === 'done' && formatDuration(stage.duration_ms)}
          {getState(idx) === 'active' && '...'}
          {getState(idx) === 'failed' && formatDuration(stage.duration_ms)}
          {getState(idx) === 'pending' && '—'}
        </span>
      </li>
    ));
  };

  const renderFallbackStages = () => {
    return FALLBACK_STEPS.map((step) => {
      const state = getFallbackStepState(step.key, fallbackStage, isComplete);
      return (
        <li key={step.key} className={`pm-step ${state}`}>
          <span className={`pm-step-icon ${state}`}>
            {state === 'done' && <CheckIcon />}
            {state === 'active' && <SpinnerIcon />}
            {state === 'pending' && null}
          </span>
          <span className="pm-step-label">{step.label}</span>
          <span className="pm-step-time">
            {state === 'done' ? 'done' : state === 'active' ? '...' : '—'}
          </span>
        </li>
      );
    });
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return createPortal(
    <>
      <style>{styles}</style>
      <div className="pm-backdrop">
        <div className="pm-modal">
          <div className="pm-header">
            <span className="pm-header-dot" />
            <span className="pm-header-label">Pipeline Execution</span>
            <span className="pm-header-badge">
              {hasError ? 'FAILED' : isComplete ? 'COMPLETE' : 'IN PROGRESS'}
            </span>
          </div>

          <div className="pm-body">
            <div className="pm-title-block">
              <h2>
                {hasError
                  ? 'Processing Failed'
                  : isComplete
                    ? 'Processing Complete'
                    : 'Processing Dataset'}
              </h2>
              <p>
                {hasError
                  ? 'An error occurred during processing. You can retry or view your datasets.'
                  : isComplete
                    ? 'Your data profile is ready — explore column details, statistics, and patterns'
                    : 'Running analysis pipeline — please wait or check back later'}
              </p>
            </div>

            {hasError && (
              <div className="pm-stage-error-banner">
                <ErrorIcon />
                One or more pipeline stages failed. The dataset may have partial results.
              </div>
            )}

            {!isComplete && !hasError && (
              <div className="pm-progress-section">
                <div className="pm-progress-meta">
                  <span className="pm-progress-stage">
                    {currentStageLabel || 'Processing'}
                  </span>
                  <span className="pm-progress-pct">{currentProgress}%</span>
                </div>
                <div className="pm-progress-track">
                  <div className="pm-progress-fill" style={{ width: `${currentProgress}%` }} />
                </div>
                <div className="pm-progress-sub">
                  {currentStageLabel
                    ? `Processing: ${currentStageLabel.toLowerCase()}`
                    : 'Starting pipeline...'}
                </div>
              </div>
            )}

            {isComplete && (
              <div className="pm-complete-icon">
                <svg width="28" height="28" viewBox="0 0 14 14" fill="none" strokeWidth="1.8" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2 7.5l3.5 3.5 6.5-7" strokeLinecap="round" strokeLinejoin="round" stroke="currentColor"/>
                </svg>
              </div>
            )}

            <ul className="pm-steps">
              {useRealStages ? renderRealStages() : renderFallbackStages()}
            </ul>
          </div>

          <div className="pm-footer">
            <span className="pm-footer-info">
              {hasError
                ? 'Partial results available'
                : isComplete
                  ? 'Ready to explore'
                  : `ETA ~${Math.max(1, Math.ceil((100 - currentProgress) / 10))}s`}
            </span>
            <div className="pm-footer-actions">
              {isComplete ? (
                <>
                  <button className="pm-btn pm-btn-primary" onClick={handleGoToProfile}>
                    View Profile
                  </button>
                  <button className="pm-btn" onClick={handleGoToDashboard}>
                    Go to Dashboard
                  </button>
                </>
              ) : hasError ? (
                <>
                  <button className="pm-btn pm-btn-danger" onClick={handleRetry}>
                    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" strokeWidth="1.5" xmlns="http://www.w3.org/2000/svg">
                      <path d="M1 7a6 6 0 0 1 10.5-4M13 1v4.5H8.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    Retry Processing
                  </button>
                  <button className="pm-btn" onClick={handleGoToDatasets}>
                    View Datasets
                  </button>
                </>
              ) : (
                <button className="pm-btn" onClick={handleClose}>
                  <CloseIcon />
                  Close & Check Later
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>,
    document.body
  );
};

export default ProcessingModal;
