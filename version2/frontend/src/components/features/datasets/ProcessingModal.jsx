import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';

import useDatasetStore from '../../../store/datasetStore';
import { toast } from 'react-hot-toast';

const STEPS = [
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

const STAGE_PROGRESS_MAP = [
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

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" strokeWidth="1.8" xmlns="http://www.w3.org/2000/svg">
    <path d="M2 7.5l3.5 3.5 6.5-7" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const SpinnerIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.3"/>
    <path d="M7 1.5A5.5 5.5 0 0 1 12.5 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const CloseIcon = () => (
  <svg width="12" height="12" viewBox="0 0 14 14" fill="none" strokeWidth="1.5" xmlns="http://www.w3.org/2000/svg">
    <path d="M1 1l12 12M13 1L1 13"/>
  </svg>
);

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
    width: 480px;
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

  .pm-step.pending .pm-step-label {
    color: var(--text-muted);
  }

  .pm-step-time {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-muted);
  }

  .pm-step.done .pm-step-time {
    color: var(--accent-success);
    opacity: 0.7;
  }

  .pm-step.active .pm-step-time {
    color: var(--accent-primary);
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
`;

const ProcessingModal = ({ isOpen, datasetId, onClose }) => {
  const navigate = useNavigate();
  const { fetchDatasets, clearProcessingState } = useDatasetStore();
  
  const [stage, setStage] = useState('uploaded');
  const [progress, setProgress] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  
  const pollRef = useRef(null);
  const navigateRef = useRef(false);

  const getStageFromProgress = (progressValue, processingStatus) => {
    if (processingStatus === 'completed' || processingStatus === 'success') {
      return { key: 'completed', progress: 100 };
    }
    
    for (const stage of STAGE_PROGRESS_MAP) {
      if (progressValue <= stage.max) {
        return { key: stage.key, progress: progressValue };
      }
    }
    return { key: 'artifact_generation', progress: progressValue };
  };

  const getStepState = (stepKey) => {
    const currentStageIndex = STEPS.findIndex(s => s.key === stage);
    const stepIndex = STEPS.findIndex(s => s.key === stepKey);
    
    if (isComplete || stage === 'completed') return 'done';
    if (stepIndex < currentStageIndex) return 'done';
    if (stepIndex === currentStageIndex) return 'active';
    return 'pending';
  };

  const checkProcessingStatus = async () => {
    if (!datasetId || navigateRef.current) return;

    try {
      const datasets = await fetchDatasets(true);
      const dataset = datasets.find(d => d.id === datasetId || d._id === datasetId);
      
      if (!dataset) return;

      const currentProgress = dataset.processing_progress || 0;
      const currentStatus = dataset.processing_status || '';
      const { key, progress: stageProgress } = getStageFromProgress(currentProgress, currentStatus);
      
      setStage(key);
      setProgress(stageProgress);

      const artifactStatus = dataset.artifact_status || {};
      const isProcessed = dataset.is_processed;
      const dashboardReady = artifactStatus.dashboard_design === 'ready';
      const insightsReady = artifactStatus.insights_report === 'ready';

      if (isProcessed && dashboardReady && insightsReady) {
        setIsComplete(true);
        setStage('completed');
        setProgress(100);
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        toast.success('Processing complete!', { id: 'processing-complete' });
      } else if (isProcessed && !dashboardReady) {
        setStage('artifact_generation');
      }
    } catch (err) {
      console.error('Error checking processing status:', err);
    }
  };

  useEffect(() => {
    if (!isOpen || !datasetId) return;
    
    setStage('uploaded');
    setProgress(0);
    setIsComplete(false);
    navigateRef.current = false;

    checkProcessingStatus();
    pollRef.current = setInterval(checkProcessingStatus, 5000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [isOpen, datasetId]);

  const handleGoToDashboard = () => {
    navigateRef.current = true;
    clearProcessingState();
    if (onClose) onClose();
    navigate('/app/dashboard');
  };

  const handleGoToDatasets = () => {
    navigateRef.current = true;
    clearProcessingState();
    if (onClose) onClose();
    navigate('/app/datasets');
  };

  const handleClose = () => {
    clearProcessingState();
    if (onClose) onClose();
  };

  const currentStageInfo = STEPS.find(s => s.key === stage) || STEPS[0];

  if (!isOpen) return null;

  const renderStepIcon = (state) => {
    switch (state) {
      case 'done':
        return <span className="pm-step-icon done"><CheckIcon /></span>;
      case 'active':
        return <span className="pm-step-icon active"><SpinnerIcon /></span>;
      default:
        return <span className="pm-step-icon pending" />;
    }
  };

  return createPortal(
    <>
      <style>{styles}</style>
      <div className="pm-backdrop">
        <div className="pm-modal">
            <div className="pm-header">
              <span className="pm-header-dot" />
              <span className="pm-header-label">Pipeline Execution</span>
              <span className="pm-header-badge">AI GENERATION</span>
            </div>

            <div className="pm-body">
              <div className="pm-title-block">
                <h2>{isComplete ? 'Processing Complete' : 'Processing Dataset'}</h2>
                <p>
                  {isComplete 
                    ? 'Your dashboard is ready with AI-generated insights'
                    : 'Running analysis pipeline — please wait or check back later'
                  }
                </p>
              </div>

              {!isComplete && (
                <div className="pm-progress-section">
                  <div className="pm-progress-meta">
                    <span className="pm-progress-stage">{currentStageInfo.label}</span>
                    <span className="pm-progress-pct">{progress}%</span>
                  </div>
                  <div className="pm-progress-track">
                    <div className="pm-progress-fill" style={{ width: `${progress}%` }} />
                  </div>
                  <div className="pm-progress-sub">Processing: {currentStageInfo.label.toLowerCase()}</div>
                </div>
              )}

              {isComplete && (
                <div className="pm-complete-icon">
                  <CheckIcon />
                </div>
              )}

              <ul className="pm-steps">
                {STEPS.map((step) => {
                  const state = getStepState(step.key);
                  return (
                    <li key={step.key} className={`pm-step ${state}`}>
                      {renderStepIcon(state)}
                      <span className="pm-step-label">{step.label}</span>
                      <span className="pm-step-time">
                        {state === 'done' ? 'done' : state === 'active' ? '...' : '—'}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="pm-footer">
              <span className="pm-footer-info">
                {isComplete ? 'Ready to explore' : `ETA ~${Math.max(1, Math.ceil((100 - progress) / 10))}s`}
              </span>
              <div className="pm-footer-actions">
                {isComplete ? (
                  <>
                    <button className="pm-btn pm-btn-primary" onClick={handleGoToDashboard}>
                      Go to Dashboard
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
