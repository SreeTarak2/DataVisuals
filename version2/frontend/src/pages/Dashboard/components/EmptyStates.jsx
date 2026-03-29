/**
 * EmptyStates Component
 * 
 * Handles various empty states for the dashboard:
 * - No dataset selected
 * - Empty dataset (0 rows/columns)
 * - Dataset still processing
 * 
 * Extracted from Dashboard.jsx to improve component organization.
 */

import React from 'react';
import { Database, AlertTriangle, Upload, RefreshCw, CheckCircle2, CloudUpload } from 'lucide-react';
import { Button } from '../../../components/common/Button';
import { Loader2 } from 'lucide-react';
import useDatasetStore from '../../../store/datasetStore';

const EmptyStates = ({ type, selectedDataset, onUpload, onNavigateToDatasets, onRegenerate }) => {
    const { activeUpload } = useDatasetStore();
    const processingProgress = selectedDataset?.processing_progress || 0;
    const processingStatus = selectedDataset?.processing_status || 'processing';
    if (type === 'no-dataset') {
        return (
            <div className="text-center py-20 rounded-xl border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)' }}>
                <Database className="w-16 h-16 mx-auto mb-6" style={{ color: 'var(--text-muted)' }} />
                <h3 className="text-2xl font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>No Data Has Been Uploaded</h3>
                <p className="mb-8 max-w-md mx-auto" style={{ color: 'var(--text-secondary)' }}>
                    Upload your first dataset to begin your AI-powered data exploration journey.
                    Our intelligent system will automatically analyze and create beautiful visualizations for you.
                </p>
                <Button
                    onClick={onUpload}
                    className="text-white px-6 py-3 text-lg"
                    style={{ background: 'var(--accent-success)' }}
                >
                    <Upload className="w-5 h-5 mr-2" />
                    Upload Your First Dataset
                </Button>
            </div>
        );
    }

    if (type === 'empty-dataset') {
        return (
            <div className="text-center py-20 rounded-xl border-2" style={{ background: 'var(--accent-error)', opacity: 0.1, borderColor: 'var(--accent-error)', borderOpacity: 0.3 }}>
                <AlertTriangle className="w-16 h-16 mx-auto mb-6" style={{ color: 'var(--accent-error)' }} />
                <h3 className="text-2xl font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Dataset is Empty</h3>
                <p className="mb-4 max-w-md mx-auto" style={{ color: 'var(--text-secondary)' }}>
                    This dataset has <span className="font-bold" style={{ color: 'var(--accent-error)' }}>{selectedDataset.row_count || 0} rows</span> and{' '}
                    <span className="font-bold" style={{ color: 'var(--accent-error)' }}>{selectedDataset.column_count || 0} columns</span>.
                </p>
                <p className="mb-8 max-w-md mx-auto" style={{ color: 'var(--text-secondary)' }}>
                    Please upload a valid CSV file with actual data or check if the file was processed correctly.
                </p>
                <div className="flex gap-4 justify-center">
                    <Button
                        onClick={onUpload}
                        className="text-white px-6 py-3"
                        style={{ background: 'var(--accent-success)' }}
                    >
                        <Upload className="w-5 h-5 mr-2" />
                        Upload New Dataset
                    </Button>
                    <Button
                        onClick={onNavigateToDatasets}
                        className="text-white px-6 py-3"
                        style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                    >
                        <Database className="w-5 h-5 mr-2" />
                        View All Datasets
                    </Button>
                </div>
            </div>
        );
    }

    if (type === 'processing-dataset') {
        return (
            <div className="text-center py-20 rounded-xl border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)' }}>
                <Loader2 className="w-16 h-16 mx-auto mb-6 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                <h3 className="text-2xl font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Analyzing Dataset</h3>
                <p className="mb-8 max-w-md mx-auto" style={{ color: 'var(--text-secondary)' }}>
                    We are currently processing your dataset and generating AI insights. This might take a minute depending on the dataset size.
                </p>
                <p className="text-sm mb-2" style={{ color: 'var(--accent-primary)' }}>Stage: {processingStatus.replace(/_/g, ' ')}</p>
                <p className="text-sm mb-8" style={{ color: 'var(--text-muted)' }}>Progress: {processingProgress}%</p>
                <div className="flex gap-4 justify-center">
                    <Button
                        onClick={onNavigateToDatasets}
                        className="text-white px-6 py-3"
                        style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                    >
                        <Database className="w-5 h-5 mr-2" />
                        View All Datasets
                    </Button>
                </div>
            </div>
        );
    }

    if (type === 'generation-failed') {
        return (
            <div className="text-center py-20 rounded-xl border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)' }}>
                <AlertTriangle className="w-16 h-16 mx-auto mb-6" style={{ color: 'var(--accent-warning)' }} />
                <h3 className="text-2xl font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Dashboard Generation Failed</h3>
                <p className="mb-2 max-w-md mx-auto" style={{ color: 'var(--text-secondary)' }}>
                    Something went wrong while generating your AI dashboard. This can happen due to a temporary API error or an unexpected data format.
                </p>
                <p className="mb-8 max-w-md mx-auto text-sm" style={{ color: 'var(--text-muted)' }}>
                    Click <strong style={{ color: 'var(--text-secondary)' }}>Redesign</strong> to try again — no data has been lost.
                </p>
                {onRegenerate && (
                    <Button
                        onClick={onRegenerate}
                        className="text-white px-6 py-3"
                        style={{ background: 'var(--accent-primary)' }}
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Redesign Dashboard
                    </Button>
                )}
            </div>
        );
    }

    if (type === 'preparing-dashboard') {
        return (
            <div className="text-center py-20 rounded-xl border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)' }}>
                <Loader2 className="w-16 h-16 mx-auto mb-6 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                <h3 className="text-2xl font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Preparing AI Dashboard</h3>
                <p className="mb-4 max-w-2xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
                    Your dataset is processed. We are now assembling the dashboard design and narrative artifacts in the background so the page opens fully prepared.
                </p>
                <p className="mb-8 max-w-md mx-auto text-sm" style={{ color: 'var(--text-muted)' }}>
                    Dataset: <span style={{ color: 'var(--text-secondary)' }}>{selectedDataset?.name || 'Current dataset'}</span>
                </p>
                <p className="text-sm mb-2" style={{ color: 'var(--accent-primary)' }}>Dataset processing: {processingProgress}%</p>
                <div className="flex gap-4 justify-center">
                    <Button
                        onClick={onNavigateToDatasets}
                        className="text-white px-6 py-3"
                        style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                    >
                        <Database className="w-5 h-5 mr-2" />
                        View All Datasets
                    </Button>
                </div>
            </div>
        );
    }
    if (type === 'pipeline-processing') {
        const uploadProgress = activeUpload?.progress || 0;
        const isUploading = activeUpload?.fileName && !activeUpload?.isComplete;
        const isProcessing = selectedDataset && selectedDataset.is_processed === false;

        // Define stages
        const stages = [
            {
                id: 'upload',
                label: 'Transferring Data',
                description: activeUpload?.fileName || 'Uploading file...',
                progress: uploadProgress,
                active: isUploading,
                complete: activeUpload?.isComplete || !isUploading
            },
            {
                id: 'process',
                label: 'Structural Analysis',
                description: processingStatus.replace(/_/g, ' '),
                progress: processingProgress,
                active: !isUploading && isProcessing,
                complete: selectedDataset?.is_processed === true
            },
            {
                id: 'design',
                label: 'AI Insights Synthesis',
                description: 'Assembling dashboard design...',
                progress: 0,
                active: !isUploading && !isProcessing,
                complete: false
            }
        ];

        return (
            <div className="max-w-3xl mx-auto py-12 px-8 rounded-2xl border border-ui-border bg-base-bg/50 backdrop-blur-md shadow-2xl">
                <div className="text-center mb-12">
                    <h2 className="text-3xl font-bold text-text-primary mb-3">Data Intelligence Pipeline</h2>
                    <p className="text-text-secondary">We are transforming your raw data into actionable insights through our AI engine.</p>
                </div>

                <div className="space-y-8 relative">
                    {/* Visual Line connecting stages */}
                    <div className="absolute left-[23px] top-6 bottom-6 w-0.5 bg-ui-border -z-10" />

                    {stages.map((stage, i) => (
                        <div key={stage.id} className={`flex gap-6 transition-all duration-500 ${stage.active ? 'opacity-100' : 'opacity-60'}`}>
                            <div className="relative flex-shrink-0">
                                {stage.complete ? (
                                    <div className="w-12 h-12 rounded-full bg-accent-success/20 flex items-center justify-center border-2 border-accent-success/50">
                                        <CheckCircle2 className="w-6 h-6 text-accent-success" />
                                    </div>
                                ) : stage.active ? (
                                    <div className="w-12 h-12 rounded-full bg-accent-primary/20 flex items-center justify-center border-2 border-accent-primary animate-pulse">
                                        <Loader2 className="w-6 h-6 text-accent-primary animate-spin" />
                                    </div>
                                ) : (
                                    <div className="w-12 h-12 rounded-full bg-ui-border flex items-center justify-center border-2 border-transparent">
                                        <div className="w-2 h-2 rounded-full bg-text-muted" />
                                    </div>
                                )}
                            </div>

                            <div className="flex-1 pt-1">
                                <div className="flex justify-between items-end mb-2">
                                    <h4 className={`text-lg transition-colors font-bold ${stage.active ? 'text-accent-primary' : 'text-text-primary'}`}>
                                        {stage.label}
                                    </h4>
                                    {stage.active && (
                                        <span className="text-sm font-mono text-accent-primary">{stage.progress}%</span>
                                    )}
                                </div>
                                <p className="text-sm text-text-secondary mb-3">{stage.description}</p>

                                {stage.active && (
                                    <div className="w-full h-1.5 bg-ui-border rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-accent-primary transition-all duration-300"
                                            style={{ width: `${stage.progress}%` }}
                                        />
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                <div className="mt-12 text-center p-4 rounded-xl bg-accent-primary/5 border border-accent-primary/10">
                    <p className="text-sm text-text-secondary flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-accent-primary" />
                        This process is fully automated. You can browse other datasets while this completes.
                    </p>
                </div>
            </div>
        );
    }

    if (type === 'server-offline') {
        return (
            <div className="text-center py-20 rounded-xl border border-ui-border bg-base-bg/50 backdrop-blur-sm">
                <div className="relative inline-block mb-6">
                    <Database className="w-16 h-16 mx-auto opacity-20" style={{ color: 'var(--text-muted)' }} />
                    <AlertTriangle className="w-8 h-8 absolute -bottom-1 -right-1 text-accent-warning animate-pulse" />
                </div>
                <h3 className="text-2xl font-semibold mb-3 text-text-primary">Server Connection Lost</h3>
                <p className="mb-8 max-w-md mx-auto text-text-secondary">
                    We can't reach the DataSage backend. Please check your internet connection or ensure the server is running.
                </p>
                <div className="flex gap-4 justify-center">
                    <Button
                        onClick={() => window.location.reload()}
                        className="text-white px-6 py-3"
                        style={{ background: 'var(--accent-primary)' }}
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Retry Connection
                    </Button>
                </div>
            </div>
        );
    }

    return null;
};

export default EmptyStates;
