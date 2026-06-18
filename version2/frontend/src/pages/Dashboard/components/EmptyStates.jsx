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
import {
    AlertTriangle,
    ArrowRight,
    BarChart3,
    Bot,
    CheckCircle2,
    Database,
    FileSpreadsheet,
    MessageSquare,
    Plug,
    RefreshCw,
    Sparkles,
    Upload,
} from 'lucide-react';
import { Button } from '../../../components/common/Button';
import { Loader2 } from 'lucide-react';

const EmptyStates = ({ type, selectedDataset, onUpload, onConnectSource, onNavigateToDatasets, onRegenerate, onRetryProcessing }) => {
    const processingProgress = selectedDataset?.processing_progress || 0;
    const processingStatus = selectedDataset?.processing_status || 'processing';
    if (type === 'no-dataset') {
        return (
            <div className="min-h-[calc(100vh-136px)] rounded-2xl border bg-[#111114] overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                <div className="grid min-h-[660px] grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px]">
                    <section className="flex items-center justify-center px-6 py-12 md:px-10">
                        <div className="w-full max-w-3xl">
                            <div className="mx-auto mb-5 flex w-fit items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.035] px-3 py-1.5">
                                <Sparkles className="h-3.5 w-3.5 text-orange-400" />
                                <span className="text-xs font-semibold text-gray-400">Signal workspace</span>
                            </div>

                            <div className="text-center">
                                <h2 className="text-3xl font-semibold tracking-tight text-white md:text-4xl">
                                    What data should Signal understand first?
                                </h2>
                                <p className="mx-auto mt-4 max-w-2xl text-sm leading-6 text-gray-400">
                                    Connect a database or upload a file. Signal profiles the source, builds metadata, and prepares dashboards, charts, and AI chat from the same context.
                                </p>
                            </div>

                            <div className="mx-auto mt-8 max-w-2xl rounded-2xl border border-white/[0.08] bg-[#1B1B1E] p-4 shadow-[0_18px_60px_rgba(0,0,0,0.24)]">
                                <div className="min-h-20 rounded-xl bg-[#121214] px-4 py-3 ring-1 ring-white/[0.06]">
                                    <p className="text-sm text-gray-500">Ask a question after connecting data...</p>
                                    <div className="mt-6 flex items-center justify-between">
                                        <div className="flex items-center gap-2 text-xs text-gray-600">
                                            <MessageSquare className="h-4 w-4" />
                                            <span>Context-aware analysis</span>
                                        </div>
                                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-gray-500">
                                            <ArrowRight className="h-4 w-4" />
                                        </span>
                                    </div>
                                </div>

                                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                                    <button
                                        type="button"
                                        onClick={onUpload}
                                        className="flex min-h-14 items-center justify-between rounded-xl bg-orange-600 px-4 text-left text-sm font-semibold text-white transition-colors hover:bg-orange-500"
                                    >
                                        <span className="flex items-center gap-3">
                                            <Upload className="h-4 w-4" />
                                            Upload file
                                        </span>
                                        <ArrowRight className="h-4 w-4" />
                                    </button>
                                    <button
                                        type="button"
                                        onClick={onConnectSource}
                                        className="flex min-h-14 items-center justify-between rounded-xl bg-white/[0.065] px-4 text-left text-sm font-semibold text-gray-100 ring-1 ring-white/[0.08] transition-colors hover:bg-white/[0.1]"
                                    >
                                        <span className="flex items-center gap-3">
                                            <Plug className="h-4 w-4" />
                                            Connect source
                                        </span>
                                        <ArrowRight className="h-4 w-4" />
                                    </button>
                                </div>
                            </div>

                            <div className="mx-auto mt-5 flex max-w-2xl flex-wrap items-center justify-center gap-2">
                                <button
                                    type="button"
                                    onClick={onConnectSource}
                                    className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] px-3 py-2 text-xs font-semibold text-gray-400 transition-colors hover:bg-white/[0.05] hover:text-gray-200"
                                >
                                    <Database className="h-3.5 w-3.5" />
                                    PostgreSQL
                                </button>
                                <button
                                    type="button"
                                    onClick={onConnectSource}
                                    className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] px-3 py-2 text-xs font-semibold text-gray-400 transition-colors hover:bg-white/[0.05] hover:text-gray-200"
                                >
                                    <FileSpreadsheet className="h-3.5 w-3.5" />
                                    Google Sheets
                                </button>
                                <button
                                    type="button"
                                    onClick={onNavigateToDatasets}
                                    className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] px-3 py-2 text-xs font-semibold text-gray-400 transition-colors hover:bg-white/[0.05] hover:text-gray-200"
                                >
                                    <BarChart3 className="h-3.5 w-3.5" />
                                    Existing datasets
                                </button>
                            </div>
                        </div>
                    </section>

                    <aside className="border-t border-white/[0.06] bg-[#0B0B0D] p-6 lg:border-l lg:border-t-0">
                        <div className="flex h-full flex-col">
                            <div>
                                <p className="text-xs font-semibold text-gray-500">First run</p>
                                <h3 className="mt-2 text-xl font-semibold text-white">Your first useful result</h3>
                                <p className="mt-2 text-sm leading-6 text-gray-400">
                                    The fastest path is to give Signal one trusted source, then let it produce a dashboard and chat context automatically.
                                </p>
                            </div>

                            <div className="mt-8 space-y-3">
                                {[
                                    ['Connect data', 'Upload CSV, Excel, or connect PostgreSQL.'],
                                    ['Profile structure', 'Detect columns, types, quality, and relationships.'],
                                    ['Generate workspace', 'Create dashboards, charts, and semantic context.'],
                                    ['Ask questions', 'Use AI chat with source-aware answers.'],
                                ].map(([title, text]) => (
                                    <div key={title} className="flex gap-3 rounded-xl bg-white/[0.025] p-4 ring-1 ring-white/[0.05]">
                                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                                        <div>
                                            <p className="text-sm font-semibold text-gray-200">{title}</p>
                                            <p className="mt-1 text-xs leading-relaxed text-gray-500">{text}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="mt-auto rounded-xl bg-orange-500/[0.07] p-4 ring-1 ring-orange-500/15">
                                <div className="flex items-center gap-2">
                                    <Bot className="h-4 w-4 text-orange-300" />
                                    <p className="text-sm font-semibold text-orange-100">Why start with data?</p>
                                </div>
                                <p className="mt-2 text-xs leading-relaxed text-orange-100/65">
                                    Signal is strongest when the AI can see schema, metadata, and relationships before it answers.
                                </p>
                            </div>
                        </div>
                    </aside>
                </div>
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

    if (type === 'processing-failed') {
        return (
            <div className="text-center py-20 rounded-xl border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)' }}>
                <AlertTriangle className="w-16 h-16 mx-auto mb-6" style={{ color: 'var(--accent-error)' }} />
                <h3 className="text-2xl font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Processing Failed</h3>
                <p className="mb-2 max-w-lg mx-auto" style={{ color: 'var(--text-secondary)' }}>
                    The pipeline encountered an error while analyzing your dataset.
                    This can happen due to data format issues or temporary server errors.
                </p>
                <p className="mb-8 max-w-md mx-auto text-sm" style={{ color: 'var(--text-muted)' }}>
                    Stage: <span style={{ color: 'var(--accent-error)' }}>{processingStatus.replace(/_/g, ' ')}</span>
                    {selectedDataset?.processing_error && (
                        <> &middot; {selectedDataset.processing_error}</>
                    )}
                </p>
                <div className="flex gap-4 justify-center">
                    {onRetryProcessing && (
                        <Button
                            onClick={onRetryProcessing}
                            className="text-white px-6 py-3"
                            style={{ background: 'var(--accent-primary)' }}
                        >
                            <RefreshCw className="w-4 h-4 mr-2" />
                            Retry Processing
                        </Button>
                    )}
                    <Button
                        onClick={onNavigateToDatasets}
                        className="text-white px-6 py-3"
                        style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                    >
                        <Database className="w-5 h-5 mr-2" />
                        View Datasets
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
    if (type === 'server-offline') {
        return (
            <div className="text-center py-20 rounded-xl border border-ui-border bg-base-bg/50 backdrop-blur-sm">
                <div className="relative inline-block mb-6">
                    <Database className="w-16 h-16 mx-auto opacity-20" style={{ color: 'var(--text-muted)' }} />
                    <AlertTriangle className="w-8 h-8 absolute -bottom-1 -right-1 text-accent-warning animate-pulse" />
                </div>
                <h3 className="text-2xl font-semibold mb-3 text-text-primary">Server Connection Lost</h3>
                <p className="mb-8 max-w-md mx-auto text-text-secondary">
                    We can't reach the Signal backend. Please check your internet connection or ensure the server is running.
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
