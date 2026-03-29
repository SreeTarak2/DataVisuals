/**
 * useDashboardGeneration Hook
 * 
 * Custom hook for AI-powered dashboard generation.
 * Handles dashboard design API calls, component transformation, and redesign counting.
 * Extracted from Dashboard.jsx to separate AI dashboard generation concerns.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'react-hot-toast';
import { normalizeDashboardConfig } from '../../../utils/dashboardUtils';
import { getAuthToken } from '../../../services/api';
import useDatasetStore from '../../../store/datasetStore';

const MAX_REDESIGNS = 3;
const NETWORK_ERROR_TOAST_ID = 'dashboard-generation-network-error';
const GENERATION_ERROR_TOAST_ID = 'dashboard-generation-error';

// Helper to generate meaningful chart titles from columns
const _generateChartTitle = (chartType, chartTypeLabel, xCol, yCol, index) => {
    if (!chartType) {
        return `Chart ${index + 1}`;
    }

    // Format column names (remove underscores, capitalize)
    const formatCol = (col) => {
        if (!col) return 'Value';
        // Handle common abbreviations and formatting
        return col.replace(/_/g, ' ')
            .replace(/\b(id|pk|fk)\b/gi, '')
            .replace(/\b\w/g, c => c.toUpperCase())
            .trim() || 'Value';
    };

    // Chart type templates for meaningful titles
    const titleTemplates = {
        'bar': `Total ${formatCol(yCol)} by ${formatCol(xCol)}`,
        'bar_chart': `Total ${formatCol(yCol)} by ${formatCol(xCol)}`,
        'line': `${formatCol(yCol)} Over ${formatCol(xCol)}`,
        'line_chart': `${formatCol(yCol)} Over ${formatCol(xCol)}`,
        'pie': `${formatCol(xCol)} Distribution`,
        'pie_chart': `${formatCol(xCol)} Distribution`,
        'donut': `${formatCol(xCol)} Breakdown`,
        'scatter': `${formatCol(xCol)} vs ${formatCol(yCol)}`,
        'scatter_plot': `${formatCol(xCol)} vs ${formatCol(yCol)}`,
        'histogram': `Distribution of ${formatCol(xCol)}`,
        'heatmap': `${formatCol(yCol)} by ${formatCol(xCol)}`,
        'area': `${formatCol(yCol)} Trend`,
        'grouped_bar': `Comparison: ${formatCol(yCol)} by ${formatCol(xCol)}`,
        'multi_bar': `Comparison: ${formatCol(yCol)} by ${formatCol(xCol)}`,
        'box': `${formatCol(xCol)} Range`,
        'box_plot': `${formatCol(xCol)} Range`,
        'violin': `${formatCol(xCol)} Distribution`,
        'funnel': `${formatCol(xCol)} Funnel`,
    };

    const template = titleTemplates[chartType?.toLowerCase()];
    if (template) {
        return template;
    }

    // Fallback: use type label with columns
    if (xCol && yCol) {
        return `${formatCol(yCol)} by ${formatCol(xCol)}`;
    }

    // Last resort
    return `${chartTypeLabel} ${index + 1}`;
};

export const useDashboardGeneration = (selectedDataset, datasetData, helpers) => {
    const { fetchDatasets, isBackendOffline, dashboardConfigs, setDashboardConfig } = useDatasetStore();
    const selectedDatasetId = selectedDataset?.id || selectedDataset?._id || null;
    const cachedConfig = selectedDatasetId ? dashboardConfigs[selectedDatasetId] : null;
    const [aiDashboardConfig, setAiDashboardConfig] = useState(cachedConfig);
    const [dashboardLoading, setDashboardLoading] = useState(false);
    const [redesignLoading, setRedesignLoading] = useState(false);
    const [artifactPreparing, setArtifactPreparing] = useState(false);
    const [redesignCount, setRedesignCount] = useState(0);
    const isProcessed = Boolean(selectedDataset?.is_processed);
    const dashboardArtifactStatus = selectedDataset?.artifact_status?.dashboard_design || null;

    // Deduplication: track in-flight requests and allow cancellation
    const abortControllerRef = useRef(null);
    const isGeneratingRef = useRef(false);
    const artifactPollRef = useRef(null);
    const selectedDatasetRef = useRef(selectedDataset);
    const helpersRef = useRef(helpers);
    const lastFailureAtRef = useRef(0);
    // Ref mirror of dashboardArtifactStatus so the polling interval can read
    // the latest value without being listed as a useEffect dependency.
    const artifactStatusRef = useRef(dashboardArtifactStatus);

    useEffect(() => {
        selectedDatasetRef.current = selectedDataset;
    }, [selectedDataset]);

    useEffect(() => {
        helpersRef.current = helpers;
    }, [helpers]);

    // Keep artifactStatusRef in sync so interval callbacks always read fresh value.
    useEffect(() => {
        artifactStatusRef.current = dashboardArtifactStatus;
    }, [dashboardArtifactStatus]);

    // Sync local state with cached store config when dataset changes
    useEffect(() => {
        if (selectedDatasetId && dashboardConfigs[selectedDatasetId]) {
            setAiDashboardConfig(dashboardConfigs[selectedDatasetId]);
        } else {
            setAiDashboardConfig(null);
        }
    }, [selectedDatasetId, dashboardConfigs]);

    const clearArtifactPoll = useCallback(() => {
        if (artifactPollRef.current) {
            clearInterval(artifactPollRef.current);
            artifactPollRef.current = null;
        }
    }, []);

    // Gracefully handle backend offline state
    useEffect(() => {
        if (isBackendOffline) {
            clearArtifactPoll();
            setArtifactPreparing(false);
            setDashboardLoading(false);
            setRedesignLoading(false);
        }
    }, [isBackendOffline, clearArtifactPoll]);

    const resetGenerationState = useCallback(() => {
        // We no longer clear aiDashboardConfig here to prevent flicker
        // The sync useEffect handles updating it from the store
        setDashboardLoading(false);
        setRedesignLoading(false);
        setRedesignCount(0);
    }, []);

    const loadExistingDashboard = useCallback(async () => {
        const currentDataset = selectedDatasetRef.current;
        const {
            getDatasetColumns,
            firstNumericColumn,
            firstCategoricalColumn,
            sanitizeTransformedComponents
        } = helpersRef.current;

        if (!currentDataset || !selectedDatasetId) {
            console.log('No dataset selected, skipping AI dashboard generation');
            setAiDashboardConfig(null);
            return;
        }

        if (!currentDataset.is_processed) {
            console.log('Dataset not processed yet, skipping AI dashboard generation');
            setAiDashboardConfig(null);
            return;
        }

        if (isGeneratingRef.current) {
            console.log('Dashboard load already in-flight, skipping duplicate call');
            return;
        }

        // Cancel any previous in-flight request
        if (abortControllerRef.current) {
            console.log('Aborting previous dashboard generation request');
            abortControllerRef.current.abort();
        }

        const controller = new AbortController();
        abortControllerRef.current = controller;
        isGeneratingRef.current = true;

        const showGenerationError = (message, toastId = GENERATION_ERROR_TOAST_ID) => {
            const now = Date.now();
            if (now - lastFailureAtRef.current < 3000) {
                return;
            }
            lastFailureAtRef.current = now;
            toast.error(message, { id: toastId });
        };

        try {
            setDashboardLoading(true);
            const token = getAuthToken();
            console.log('Loading cached AI dashboard for dataset:', selectedDatasetId);
            const response = await fetch(`/api/ai/${selectedDatasetId}/dashboard`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                signal: controller.signal
            });

            if (response.status === 404) {
                console.log('No cached dashboard found for dataset');
                setAiDashboardConfig(null);
                return;
            }

            if (!response.ok) {
                throw new Error('Failed to load cached dashboard');
            }

            const dashboardConfig = await response.json();
            console.log('Cached AI dashboard response:', dashboardConfig);

            if (dashboardConfig.dashboard_blueprint && dashboardConfig.dashboard_blueprint.components) {
                const normalized = normalizeDashboardConfig({
                    components: dashboardConfig.dashboard_blueprint.components || [],
                    layout_grid: dashboardConfig.dashboard_blueprint.layout_grid || "repeat(4, 1fr)",
                    design_pattern: dashboardConfig.design_pattern,
                    pattern_name: dashboardConfig.pattern_name,
                    reasoning: dashboardConfig.reasoning
                });
                setAiDashboardConfig(normalized);
                setDashboardConfig(selectedDatasetId, normalized);
                return;
            }

            const componentsArray = dashboardConfig.dashboard?.components || dashboardConfig.components;
            if (componentsArray) {
                const transformed = transformComponents(componentsArray, {
                    firstNumericColumn,
                    firstCategoricalColumn,
                    getDatasetColumns
                });

                if (transformed.length > 0) {
                    const sanitized = sanitizeTransformedComponents(transformed);
                    const normalized = normalizeDashboardConfig({
                        components: sanitized,
                        layout_grid: dashboardConfig.dashboard?.layout_grid || dashboardConfig.layout_grid || "repeat(4, 1fr)"
                    });
                    setAiDashboardConfig(normalized);
                    setDashboardConfig(selectedDatasetId, normalized);
                } else {
                    console.log('Cached dashboard response had no usable components; preserving current dashboard');
                }
            } else {
                console.log('No cached dashboard components found; preserving current dashboard');
            }
        } catch (error) {
            // Don't show error for intentionally aborted requests
            if (error.name === 'AbortError') {
                console.log('Dashboard load aborted (superseded by new request)');
                return;
            }
            console.error('Cached AI dashboard load failed:', error);
            if (error instanceof TypeError) {
                showGenerationError('Backend is unavailable. Showing the last dashboard snapshot.', NETWORK_ERROR_TOAST_ID);
                return;
            }
            showGenerationError('Failed to load AI dashboard');
        } finally {
            if (abortControllerRef.current === controller) {
                isGeneratingRef.current = false;
                setDashboardLoading(false);
            }
        }
    }, [selectedDatasetId]);

    const generateAiDashboard = useCallback(async (forceRegenerate = false) => {
        const currentDataset = selectedDatasetRef.current;
        const {
            getDatasetColumns,
            firstNumericColumn,
            firstCategoricalColumn,
            sanitizeTransformedComponents
        } = helpersRef.current;

        if (!currentDataset || !selectedDatasetId) {
            console.log('No dataset selected, skipping AI dashboard generation');
            setAiDashboardConfig(null);
            return;
        }

        if (!currentDataset.is_processed) {
            console.log('Dataset not processed yet, skipping AI dashboard generation');
            setAiDashboardConfig(null);
            return;
        }

        if (isGeneratingRef.current && !forceRegenerate) {
            console.log('Dashboard generation already in-flight, skipping duplicate call');
            return;
        }

        if (abortControllerRef.current) {
            console.log('Aborting previous dashboard request');
            abortControllerRef.current.abort();
        }

        const controller = new AbortController();
        abortControllerRef.current = controller;
        isGeneratingRef.current = true;
        let generatedSuccessfully = false;

        const showGenerationError = (message, toastId = GENERATION_ERROR_TOAST_ID) => {
            const now = Date.now();
            if (now - lastFailureAtRef.current < 3000) {
                return;
            }
            lastFailureAtRef.current = now;
            toast.error(message, { id: toastId });
        };

        try {
            setDashboardLoading(true);
            setRedesignLoading(Boolean(forceRegenerate));
            const token = getAuthToken();
            console.log('Starting AI dashboard generation for dataset:', selectedDatasetId);

            try {
                console.log('Trying AI Designer service...');
                const response = await fetch(`/api/ai/${selectedDatasetId}/design-dashboard`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ force_regenerate: !!forceRegenerate }),
                    signal: controller.signal
                });

                if (response.ok) {
                    const dashboardConfig = await response.json();
                    console.log('AI Designer response:', dashboardConfig);

                    if (dashboardConfig.dashboard_blueprint && dashboardConfig.dashboard_blueprint.components) {
                        const normalized = normalizeDashboardConfig({
                            components: dashboardConfig.dashboard_blueprint.components || [],
                            layout_grid: dashboardConfig.dashboard_blueprint.layout_grid || "repeat(4, 1fr)",
                            design_pattern: dashboardConfig.design_pattern,
                            pattern_name: dashboardConfig.pattern_name,
                            reasoning: dashboardConfig.reasoning
                        });
                        setAiDashboardConfig(normalized);
                        setDashboardConfig(selectedDatasetId, normalized);
                        generatedSuccessfully = true;
                        return;
                    } else if (dashboardConfig.dashboard && dashboardConfig.dashboard.components) {
                        const transformed = transformComponents(dashboardConfig.dashboard.components, {
                            firstNumericColumn,
                            firstCategoricalColumn,
                            getDatasetColumns
                        });

                        if (transformed.length > 0) {
                            const sanitized = sanitizeTransformedComponents(transformed);
                            const normalized = normalizeDashboardConfig({
                                components: sanitized,
                                layout_grid: dashboardConfig.dashboard.layout_grid || "repeat(4, 1fr)"
                            });
                            setAiDashboardConfig(normalized);
                            setDashboardConfig(selectedDatasetId, normalized);
                            generatedSuccessfully = true;
                            return;
                        }
                    }
                }
            } catch (designError) {
                if (designError?.name === 'AbortError') {
                    throw designError;
                }

                if (designError instanceof TypeError) {
                    console.log('AI Designer service network failure, skipping legacy fallback:', designError);
                    throw designError;
                }

                console.log('AI Designer service failed, falling back to legacy:', designError);
            }

            console.log('Trying legacy AI dashboard generation...');
            const response = await fetch(
                `/api/ai/${selectedDatasetId}/generate-dashboard?force_regenerate=${forceRegenerate}`,
                {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                    signal: controller.signal
                }
            );

            if (response.ok) {
                const dashboardConfig = await response.json();
                console.log('Legacy dashboard response:', dashboardConfig);

                const componentsArray = dashboardConfig.dashboard?.components || dashboardConfig.components;
                if (componentsArray) {
                    const transformed = transformComponents(componentsArray, {
                        firstNumericColumn,
                        firstCategoricalColumn,
                        getDatasetColumns
                    });

                    if (transformed.length > 0) {
                        const sanitized = sanitizeTransformedComponents(transformed);
                        const normalized = normalizeDashboardConfig({
                            components: sanitized,
                            layout_grid: dashboardConfig.dashboard?.layout_grid || dashboardConfig.layout_grid || "repeat(4, 1fr)"
                        });
                        setAiDashboardConfig(normalized);
                        setDashboardConfig(selectedDatasetId, normalized);
                        generatedSuccessfully = true;
                    } else {
                        console.log('Legacy dashboard response had no usable components; preserving current dashboard');
                    }
                } else {
                    console.log('No dashboard components found in response; preserving current dashboard');
                }
            } else {
                console.error('Legacy AI dashboard generation failed:', response.status);
                throw new Error('Failed to generate AI dashboard');
            }
        } catch (error) {
            // Don't show error for intentionally aborted requests
            if (error.name === 'AbortError') {
                console.log('Dashboard generation aborted (superseded by new request)');
                return;
            }
            console.error('AI Dashboard generation failed:', error);
            if (error instanceof TypeError) {
                showGenerationError('Backend is unavailable. Showing the last dashboard snapshot.', NETWORK_ERROR_TOAST_ID);
                return;
            }
            showGenerationError('Failed to generate AI dashboard');
        } finally {
            // Only reset loading if this is still the active request (not aborted)
            if (abortControllerRef.current === controller) {
                isGeneratingRef.current = false;
                setDashboardLoading(false);
                setRedesignLoading(false);
            }

            if (generatedSuccessfully) {
                setTimeout(() => {
                    toast.success('✨ AI Dashboard generated successfully!', {
                        id: 'dashboard-generated',
                        duration: 3000,
                    });
                }, 100);
            }
        }
    }, [selectedDatasetId]);

    const handleRegenerate = useCallback(() => {
        if (redesignCount >= MAX_REDESIGNS) {
            toast.error(`Redesign limit reached (${MAX_REDESIGNS}/${MAX_REDESIGNS}). Please refresh the page to reset.`);
            return false;
        }
        setRedesignCount(prev => prev + 1);
        generateAiDashboard(true);
        return true;
    }, [generateAiDashboard, redesignCount]);

    useEffect(() => {
        resetGenerationState();
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        isGeneratingRef.current = false;
        clearArtifactPoll();
    }, [selectedDatasetId, resetGenerationState, clearArtifactPoll]);

    const lastAutoGenerationKeyRef = useRef(null);

    useEffect(() => {
        if (!selectedDatasetId || !isProcessed) {
            lastAutoGenerationKeyRef.current = null;
            return;
        }

        const autoGenerationKey = `${selectedDatasetId}:${dashboardArtifactStatus || 'missing'}`;
        if (lastAutoGenerationKeyRef.current === autoGenerationKey) {
            return;
        }

        // If the artifact is already ready, load it once for this dataset/status pair.
        if (dashboardArtifactStatus === 'ready') {
            lastAutoGenerationKeyRef.current = autoGenerationKey;
            loadExistingDashboard();
            return;
        }

        // If artifact generation failed or was never recorded, actively recover
        // instead of leaving the dashboard blank.
        if (!dashboardArtifactStatus || dashboardArtifactStatus === 'failed') {
            lastAutoGenerationKeyRef.current = autoGenerationKey;
            generateAiDashboard(dashboardArtifactStatus === 'failed');
        }
    }, [selectedDatasetId, isProcessed, dashboardArtifactStatus, loadExistingDashboard, generateAiDashboard]);

    useEffect(() => {
        if (!selectedDatasetId || !isProcessed) {
            clearArtifactPoll();
            setArtifactPreparing(false);
            return;
        }

        const currentStatus = artifactStatusRef.current;
        if (currentStatus === 'pending' || currentStatus === 'generating') {
            setArtifactPreparing(true);
            if (!artifactPollRef.current) {
                artifactPollRef.current = setInterval(async () => {
                    try {
                        // Poll with force=true but manual=false to allow 5s throttling
                        const datasets = await fetchDatasets(true, false);
                        const updated = datasets.find((item) => (item.id || item._id) === selectedDatasetId);
                        const nextStatus = updated?.artifact_status?.dashboard_design;
                        // Update the ref so subsequent interval ticks see the latest value
                        // without triggering a re-render or effect re-run.
                        artifactStatusRef.current = nextStatus ?? artifactStatusRef.current;
                        if (nextStatus === 'ready') {
                            clearArtifactPoll();
                            setArtifactPreparing(false);
                            loadExistingDashboard();
                        } else if (nextStatus === 'failed') {
                            clearArtifactPoll();
                            setArtifactPreparing(false);
                        }
                    } catch (pollError) {
                        console.error('Dashboard artifact polling failed:', pollError);
                    }
                }, 8000); // Increased polling interval to 8 seconds to reduce server load
            }
            return;
        }

        clearArtifactPoll();
        setArtifactPreparing(false);
        // dashboardArtifactStatus intentionally excluded: it is read via artifactStatusRef
        // to avoid tearing down and recreating the interval on every poll cycle.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedDatasetId, isProcessed, fetchDatasets, clearArtifactPoll, loadExistingDashboard]);

    // Cleanup: abort in-flight request on unmount or dataset change
    useEffect(() => {
        return () => {
            clearArtifactPoll();
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
                isGeneratingRef.current = false;
            }
        };
    }, [selectedDatasetId, clearArtifactPoll]);

    return {
        aiDashboardConfig,
        dashboardLoading,
        redesignLoading,
        artifactPreparing,
        redesignCount,
        dashboardArtifactStatus,
        generateAiDashboard,
        handleRegenerate,
        MAX_REDESIGNS
    };
};

/**
 * Transform API components to frontend format
 */
function transformComponents(components, helpers) {
    const { firstNumericColumn, firstCategoricalColumn, getDatasetColumns } = helpers;
    const transformedComponents = [];

    components.forEach((component, index) => {
        // Handle KPI cards
        if (component.kpi_cards) {
            component.kpi_cards.forEach((kpi, kpiIndex) => {
                transformedComponents.push({
                    type: 'kpi',
                    title: kpi.title || `KPI ${kpiIndex + 1}`,
                    span: 1,
                    config: {
                        column: kpi.sum || kpi.mean || kpi.count || firstNumericColumn(),
                        aggregation: kpi.sum ? 'sum' : kpi.mean ? 'mean' : 'count',
                        color: ['emerald', 'blue', 'teal', 'purple'][kpiIndex % 4]
                    }
                });
            });
        }

        // Handle charts
        if (component.charts) {
            component.charts.forEach((chart, chartIndex) => {
                // Generate meaningful title from columns and chart type
                const chartTypeLabel = chart.chart_type?.replace('_', ' ').toUpperCase() || 'CHART';
                const xCol = chart.x || firstCategoricalColumn() || 'Category';
                const yCol = chart.y || firstNumericColumn() || 'Value';
                const generatedTitle = _generateChartTitle(chart.chart_type, chartTypeLabel, xCol, yCol, chartIndex);

                // If the backend provided title is generic "Chart X", use our generated one
                const finalTitle = (chart.title && !/^Chart \d+$/i.test(chart.title))
                    ? chart.title
                    : generatedTitle;

                transformedComponents.push({
                    type: 'chart',
                    title: finalTitle,
                    span: 2,
                    config: {
                        chart_type: chart.chart_type || chart.type || 'bar_chart',
                        columns: chart.data ?
                            chart.data.map(d => d.x || d.y).filter(Boolean) :
                            [xCol, yCol],
                        aggregation: 'mean',
                        group_by: chart.data?.[0]?.x || xCol
                    }
                });
            });
        }

        // Handle table
        if (component.table) {
            transformedComponents.push({
                type: 'table',
                title: 'Data Table',
                span: 4,
                config: {
                    columns: component.table.columns || getDatasetColumns()
                }
            });
        }

        // Handle legacy format
        if (component.kpi && component.chart_type) {
            transformedComponents.push({
                type: 'kpi',
                title: component.kpi,
                span: 1,
                config: {
                    column: component.data_columns?.[0] || firstNumericColumn(),
                    aggregation: component.kpi.includes('Total') ? 'count' : 'mean',
                    color: ['emerald', 'blue', 'teal', 'purple'][index % 4]
                }
            });
        } else if (component.chart_type && component.title && !component.kpi) {
            transformedComponents.push({
                type: 'chart',
                title: component.title,
                span: 2,
                config: {
                    chart_type: component.chart_type,
                    columns: component.data_columns || [firstNumericColumn(), firstCategoricalColumn()],
                    aggregation: 'mean',
                    group_by: component.data_columns?.[0] || firstCategoricalColumn()
                }
            });
        }
    });

    return transformedComponents;
}
