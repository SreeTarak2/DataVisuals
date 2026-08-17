import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { BarChart3 } from 'lucide-react';
import useDatasetStore from '../../store/datasetStore';
import useDashboardActionStore from '../../store/dashboardActionStore';
import { useWorkspacePermission } from '../../hooks/useWorkspacePermission';
import { drilldownAPI } from '../../services/api';
import { restoreDrilledCharts } from '../../utils/hierarchyDrill';

// Custom hooks
import { useDashboardData } from './hooks/useDashboardData';
import { useDashboardGeneration } from './hooks/useDashboardGeneration';
import { useBulkChartHydration } from './hooks/useBulkChartHydration';
import { useCrossFilterHydration } from './hooks/useCrossFilterHydration';
import { useUrlDashboardState } from './hooks/useUrlDashboardState';
import { useMetrics } from '../../hooks/useMetrics';
import { useDataPreview } from './hooks/useDataPreview';

// Components
import EmptyStates from './components/EmptyStates';
import DataPreviewTable from './components/DataPreviewTable';
import LoadingState from './components/LoadingState';
import { MetricStrip } from '../../components/kpi';
import DashboardComponent from '../../components/DashboardComponent';
import CreateProjectModal from '../../components/features/projects/CreateProjectModal';

// Utils
import { getDatasetColumns, firstNumericColumn, firstCategoricalColumn } from './utils/columnHelpers';
import { sanitizeTransformedComponents } from './utils/dashboardSanitizer';

// Dashboard API insight types → PowerBIInsightCards type names
const PERIOD_LABELS = {
    all: 'All time',
    last_30d: 'Last 30 days',
    last_quarter: 'Last quarter',
    last_year: 'Last year',
    this_month: 'This month',
    last_month: 'Last month',
    this_quarter: 'This quarter',
    this_year: 'This year',
};

const MotionDiv = motion.div;

// ── Bento Layout Engine ──────────────────────────────────────────────────────
// Creates visually varied grid patterns instead of a monotonous straight grid.
// Smart-assigns column spans based on chart type + repeating asymmetric patterns.

const SPAN_CLASSES = {
    12: 'col-span-12 lg:col-span-12',
    10: 'col-span-12 lg:col-span-10',
    8: 'col-span-12 lg:col-span-8',
    7: 'col-span-12 lg:col-span-7',
    6: 'col-span-12 lg:col-span-6',
    5: 'col-span-12 lg:col-span-5',
    4: 'col-span-12 lg:col-span-4',
    3: 'col-span-12 lg:col-span-3',
};

const createBentoLayout = (charts) => {
    if (!charts || charts.length === 0) return [];

    const result = [];
    let i = 0;

    const getWidthScore = (chart) => {
        const type = chart.config?.chart_type?.toLowerCase() || '';
        if (['line', 'line_chart', 'area', 'multi_bar'].includes(type)) return 10;
        if (['bar', 'bar_chart', 'histogram', 'grouped_bar'].includes(type)) return 7;
        if (['scatter', 'scatter_plot', 'heatmap'].includes(type)) return 6;
        if (['box', 'box_plot', 'violin'].includes(type)) return 5;
        if (['pie', 'pie_chart', 'donut'].includes(type)) return 3;
        return 5;
    };

    const rowPatterns = [
        [7, 5], [4, 4, 4], [5, 7], [8, 4],
        [6, 6], [4, 8], [5, 4, 3], [3, 5, 4],
    ];

    const getAdaptivePattern = (remainingCharts, rowIndex) => {
        const hasPieDonut = remainingCharts.some(c =>
            ['pie', 'pie_chart', 'donut'].includes(c.config?.chart_type?.toLowerCase())
        );
        if (remainingCharts.length === 1) return [12];
        if (remainingCharts.length === 2) {
            if (hasPieDonut) return [8, 4];
            return [7, 5];
        }
        if (remainingCharts.length >= 3 && hasPieDonut) {
            const pieIndex = remainingCharts.findIndex(c =>
                ['pie', 'pie_chart', 'donut'].includes(c.config?.chart_type?.toLowerCase())
            );
            if (pieIndex === 0) return [3, 5, 4];
            if (pieIndex === remainingCharts.length - 1) return [5, 4, 3];
            return [5, 3, 4];
        }
        return rowPatterns[rowIndex % rowPatterns.length];
    };

    let patternIdx = 0;

    while (i < charts.length) {
        if (i === 0) {
            result.push({ chart: charts[i], span: 12, variant: 'hero' });
            i++;
            continue;
        }

        const remaining = charts.length - i;
        const pattern = getAdaptivePattern(charts.slice(i), patternIdx);
        const slots = Math.min(pattern.length, remaining);
        const rowCharts = charts.slice(i, i + slots);

        if (slots === pattern.length) {
            const spans = [...pattern];
            const sortedSpanIndices = spans
                .map((s, idx) => ({ span: s, idx }))
                .sort((a, b) => b.span - a.span);
            const scored = rowCharts
                .map((c, idx) => ({ chart: c, score: getWidthScore(c), origIdx: idx }))
                .sort((a, b) => b.score - a.score);
            const assignments = new Array(slots);
            scored.forEach((s, rankIdx) => {
                assignments[s.origIdx] = sortedSpanIndices[rankIdx].span;
            });
            rowCharts.forEach((chart, idx) => {
                const span = assignments[idx];
                result.push({
                    chart,
                    span,
                    variant: span >= 8 ? 'featured' : span >= 6 ? 'standard' : 'compact',
                });
            });
        } else if (slots === 2) {
            const scores = rowCharts.map(c => getWidthScore(c));
            if (scores[0] >= scores[1]) {
                result.push({ chart: rowCharts[0], span: 7, variant: 'standard' });
                result.push({ chart: rowCharts[1], span: 5, variant: 'compact' });
            } else {
                result.push({ chart: rowCharts[0], span: 5, variant: 'compact' });
                result.push({ chart: rowCharts[1], span: 7, variant: 'standard' });
            }
        } else {
            result.push({ chart: rowCharts[0], span: 12, variant: 'featured' });
        }

        i += slots;
        patternIdx++;
    }

    return result;
};

const Dashboard = () => {
    const { selectedDataset, activeUpload, isBackendOffline, dashboardConfigs, setDashboardConfig, reprocessDataset, setProcessingDataset, fetchDatasets } = useDatasetStore();
    const { canUploadDataset } = useWorkspacePermission();
    const navigate = useNavigate();

    // Local UI state
    const [showCreateProjectModal, setShowCreateProjectModal] = useState(false);

    // Custom hooks for data and state management
    const {
        loading,
        datasetData,
        selectedPeriod,
        setSelectedPeriod,
        availablePeriods,
    } = useDashboardData(selectedDataset);

    const { dataPreview, previewLoading, totalRows, loadDataPreview } = useDataPreview(selectedDataset);

    const {
        aiDashboardConfig,
        dashboardLoading,
        artifactPreparing,
        dashboardArtifactStatus,
        handleRegenerate,
    } = useDashboardGeneration(selectedDataset, datasetData, {
        getDatasetColumns: () => getDatasetColumns(datasetData, dataPreview),
        firstNumericColumn: () => firstNumericColumn(datasetData, dataPreview),
        firstCategoricalColumn: () => firstCategoricalColumn(datasetData, dataPreview),
        sanitizeTransformedComponents: (components) => sanitizeTransformedComponents(components, { datasetData, dataPreview }),
        loadDataPreview
    });

    // Bulk-hydrate all config-only chart components in ONE request instead of
    // firing N per-chart `retry-chart` calls. Exposes bulkHydrating so chart
    // cards can show a loading state while the batch renders.
    const { bulkHydrating } = useBulkChartHydration(selectedDataset, aiDashboardConfig);

    // Real cross-filtering: re-hydrates charts sharing the active filter field
    // with a server-side filter, restores the baseline when the filter clears.
    useCrossFilterHydration(selectedDataset, aiDashboardConfig);

    // Persist cross-filter + drill-down in the URL (encoded, validated, scoped
    // per dataset) so reloads and shared links restore the exact view.
    useUrlDashboardState(selectedDataset);

    // Dynamic Dashboard Briefing — refreshes when period changes (Power BI Smart Narrative style)
    // Metrics — data-science-grade KPI cards from backend
    const datasetId = selectedDataset?.id || selectedDataset?._id;
    const {
        metrics,
        loading: metricsLoading,
        error: metricsError,
        refresh: refreshMetrics,
    } = useMetrics(datasetId);

    // Cross-chart filtering and drill-down state (shared with DashboardComponent via the action store)
    const { crossFilters, removeFiltersForField, clearCrossFilter, clearDrillDown, setHierarchies } = useDashboardActionStore();

    // Group the filter context by field for the badge — "Region: West, North"
    // plus "Product: A" chips, one per filtered dimension (multi-field).
    const groupedFilters = useMemo(() => {
        const byField = {};
        (crossFilters || []).forEach((f) => {
            const key = f?.field || '__value__';
            if (!byField[key]) byField[key] = [];
            byField[key].push(String(f?.value));
        });
        return byField;
    }, [crossFilters]);

    // ── Fetch validated hierarchy paths (ontology) so double-click drill-down
    // follows country → state → city instead of only filtering. Provisional
    // hierarchies are included but flagged in the UI (Act-then-Validate).
    useEffect(() => {
        if (!datasetId) return;
        drilldownAPI.getHierarchies(datasetId)
            .then((res) => setHierarchies(res.data?.hierarchies || []))
            .catch(() => setHierarchies([]));
    }, [datasetId, setHierarchies]);

    // ── Chart section computations (re-enabled) ─────────────────────────────────
    // Charts render from the AI blueprint components. DashboardComponent handles
    // cross-filtering (brush + click → store → dim effect on all other charts)
    // and drill-down breadcrumbs out of the box.
    const finalChartItems = useMemo(
        () => aiDashboardConfig?.components?.filter(c => c?.type === 'chart') || [],
        [aiDashboardConfig]
    );

    const bentoLayout = useMemo(() => createBentoLayout(finalChartItems), [finalChartItems]);

    const hasChartSection = finalChartItems.length > 0;

    const mergeDashboardComponent = useCallback((component) => {
        if (!datasetId || !component) return;

        const currentConfig = dashboardConfigs?.[datasetId] || aiDashboardConfig || { components: [] };
        const components = Array.isArray(currentConfig.components) ? [...currentConfig.components] : [];
        const componentKey = component.id || component.key || component.title;
        const alreadyExists = components.some((item, index) => {
            const itemKey = item?.id || item?.key || item?.title || index;
            return componentKey && itemKey === componentKey;
        });

        if (!alreadyExists) {
            components.push(component);
            setDashboardConfig(datasetId, {
                ...currentConfig,
                components,
            });
        }
    }, [datasetId, dashboardConfigs, aiDashboardConfig, setDashboardConfig]);

    // ─── Listen for chat-driven component additions ───
    useEffect(() => {
        const handler = (event) => {
            const { component } = event.detail || {};
            if (!component) return;
            mergeDashboardComponent(component);
        };

        window.addEventListener('dashboard-component-added', handler);
        return () => window.removeEventListener('dashboard-component-added', handler);
    }, [mergeDashboardComponent]);

    // 1. Dataset is uploading or processing — show appropriate state
    //    The full ProcessingModal overlay handles the detailed stage display.
    const isUploading = activeUpload?.fileName && !activeUpload?.isComplete;
    const isProcessing = selectedDataset && selectedDataset.is_processed === false;
    const hasProcessingFailed = isProcessing && (selectedDataset.processing_status === 'failed' || selectedDataset.processing_status === 'error');

    const handleRetryProcessing = useCallback(async () => {
        const id = selectedDataset?.id || selectedDataset?._id;
        if (!id) return;
        const result = await reprocessDataset(id);
        if (result?.success) {
            setProcessingDataset(id);
        }
    }, [selectedDataset, reprocessDataset, setProcessingDataset]);

    // Loading state
    if (loading) {
        return <LoadingState />;
    }

    if (isUploading || isProcessing) {
        if (hasProcessingFailed) {
            return (
                <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                    <EmptyStates
                        type="processing-failed"
                        selectedDataset={selectedDataset}
                        onRetryProcessing={handleRetryProcessing}
                        onNavigateToDatasets={() => navigate('/app/datasets')}
                    />
                </div>
            );
        }
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="processing-dataset"
                    selectedDataset={selectedDataset}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                    onRefreshStatus={async () => {
                        await fetchDatasets(true, true);
                        window.dispatchEvent(new Event('dashboard-refresh'));
                    }}
                />
            </div>
        );
    }

    // No dataset selected
    if (!selectedDataset) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="no-dataset"
                    onUpload={() => setShowCreateProjectModal(true)}
                    onConnectSource={() => navigate('/app/connectors')}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                    canUpload={canUploadDataset}
                />
                {showCreateProjectModal && (
                    <CreateProjectModal
                        onClose={() => setShowCreateProjectModal(false)}
                        onCreated={(project) => navigate(`/app/projects/${project.id}`)}
                    />
                )}
            </div>
        );
    }

    // Server offline state — PRIORITIZE showing this if backend is unreachable
    if (isBackendOffline && !aiDashboardConfig) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="server-offline"
                    selectedDataset={selectedDataset}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                />
            </div>
        );
    }

    // Empty dataset (0 rows or columns)
    if (selectedDataset.row_count === 0 || selectedDataset.column_count === 0) {

        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="empty-dataset"
                    selectedDataset={selectedDataset}
                    onUpload={() => setShowCreateProjectModal(true)}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                    canUpload={canUploadDataset}
                />
                {showCreateProjectModal && (
                    <CreateProjectModal
                        onClose={() => setShowCreateProjectModal(false)}
                        onCreated={(project) => navigate(`/app/projects/${project.id}`)}
                    />
                )}
            </div>
        );
    }

    // Generation failed and no cached config — show a full-page error with redesign CTA
    if (!aiDashboardConfig && dashboardArtifactStatus === 'failed' && !dashboardLoading && !artifactPreparing) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="generation-failed"
                    selectedDataset={selectedDataset}
                    onRegenerate={handleRegenerate}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                />
            </div>
        );
    }

    // AI is generating — show full-page preparing state, nothing else
    if (!aiDashboardConfig && (dashboardLoading || artifactPreparing || dashboardArtifactStatus === 'pending' || dashboardArtifactStatus === 'generating')) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="preparing-dashboard"
                    selectedDataset={selectedDataset}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                />
            </div>
        );
    }

    // Main dashboard render
    return (
        <div className="min-h-full px-4 py-6 sm:px-6 sm:py-8 lg:px-8 space-y-8 sm:space-y-10" style={{ backgroundColor: 'var(--bg-primary)' }}>
            {/* Period selector */}
            {availablePeriods.length > 1 && (
                <select
                    value={selectedPeriod}
                    onChange={(e) => setSelectedPeriod(e.target.value)}
                    className="text-xs rounded-md px-2.5 py-1.5 cursor-pointer transition-colors"
                    style={{
                        background: 'var(--bg-elevated)',
                        color: 'var(--text-secondary)',
                        border: '1px solid var(--border)',
                    }}
                >
                    {availablePeriods.map(p => (
                        <option key={p} value={p}>
                            {PERIOD_LABELS[p] || p}
                        </option>
                    ))}
                </select>
            )}

            {/* Metrics Strip — KPI cards */}
            <MetricStrip
                metrics={metrics}
                loading={metricsLoading}
                error={metricsError}
                onRefresh={refreshMetrics}
                onMetricClick={(metric) => {
                    // Drill-down: open copilot with context about this metric
                    window.dispatchEvent(new CustomEvent('open-chat-with-query', {
                        detail: {
                            query: `Tell me more about ${metric.title} (${metric.value}). What's driving this trend?`
                        }
                    }));
                }}
                maxCards={6}
                title="Key Metrics"
            />

            {/* ─── Chart Grid — Visual Analytics (cross-filtering enabled) ─── */}
            {hasChartSection && (
                <div className="space-y-4">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2.5">
                            <div className="p-1.5 rounded-lg" style={{ background: 'var(--accent-primary-light)', border: '1px solid var(--border)' }}>
                                <BarChart3 className="w-3.5 h-3.5" style={{ color: 'var(--accent-primary)' }} />
                            </div>
                            <span className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>Visual Analytics</span>
                            <span className="px-1.5 py-0.5 rounded-md text-xs font-medium tabular-nums" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                                {finalChartItems.length}
                            </span>
                        </div>

                        {/* Active Cross-filter Badges — one chip per field, multi-select values inside:
                            "Region: West, North ✕" + "Product: A ✕", plus a Clear all */}
                        {Object.keys(groupedFilters).length > 0 && (
                            <div className="flex items-center ml-2 pl-3 border-l gap-1.5 flex-wrap" style={{ borderColor: 'var(--border)' }}>
                                <span className="text-[11px] mr-1" style={{ color: 'var(--text-secondary)' }}>Filtering:</span>
                                {Object.entries(groupedFilters).map(([field, values]) => (
                                    <div
                                        key={field}
                                        className="flex items-center gap-1.5 px-2 py-0.5 rounded-md"
                                        style={{ background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.2)' }}
                                    >
                                        <span className="text-[11px] font-bold" style={{ color: 'var(--text-primary)' }}>
                                            {field !== '__value__' ? `${field}: ` : ''}{values.join(', ')}
                                        </span>
                                        <button
                                            onClick={() => removeFiltersForField(field)}
                                            className="transition-colors ml-1"
                                            style={{ color: 'var(--text-secondary)' }}
                                            title={`Clear ${field} filter`}
                                        >
                                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                        </button>
                                    </div>
                                ))}
                                <button
                                    onClick={() => {
                                        // Restore any hierarchy-drilled chart to its baseline
                                        // granularity before clearing the whole filter context.
                                        restoreDrilledCharts();
                                        clearCrossFilter();
                                        clearDrillDown();
                                    }}
                                    className="text-[11px] px-2 py-0.5 rounded-md transition-colors hover:bg-white/5"
                                    style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                                    title="Clear all filters"
                                >
                                    Clear all
                                </button>
                            </div>
                        )}

                        <div className="h-px flex-1" style={{ background: 'linear-gradient(to right, var(--border), transparent)' }} />
                    </div>

                    <MotionDiv
                        className="grid grid-cols-1 lg:grid-cols-12 gap-4"
                        variants={{
                            hidden: {},
                            visible: { transition: { staggerChildren: 0.07 } }
                        }}
                        initial="hidden"
                        animate="visible"
                    >
                        {bentoLayout.map(({ chart, span, variant }, index) => (
                            <MotionDiv
                                key={`chart-${index}`}
                                className={SPAN_CLASSES[span] || 'col-span-12'}
                                variants={{
                                    hidden: { y: 24, opacity: 0, scale: 0.98 },
                                    visible: {
                                        y: 0,
                                        opacity: 1,
                                        scale: 1,
                                        transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }
                                    }
                                }}
                            >
                                <DashboardComponent
                                    component={chart}
                                    datasetData={datasetData}
                                    variant={variant}
                                    bulkHydrating={bulkHydrating}
                                />
                            </MotionDiv>
                        ))}
                    </MotionDiv>
                </div>
            )}

            {/* Data Preview Table */}
            <DataPreviewTable
                dataPreview={dataPreview}
                loading={previewLoading}
                onReload={loadDataPreview}
                totalRows={totalRows}
            />

            {/* New Project Modal */}
            {showCreateProjectModal && (
                <CreateProjectModal
                    onClose={() => setShowCreateProjectModal(false)}
                    onCreated={(project) => navigate(`/app/projects/${project.id}`)}
                />
            )}

        </div>
    );
};

export default Dashboard;
