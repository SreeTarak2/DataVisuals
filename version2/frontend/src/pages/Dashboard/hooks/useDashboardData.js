/**
 * useDashboardData Hook
 * 
 * Custom hook for fetching and managing dashboard data (overview, charts, insights).
 * Extracted from Dashboard.jsx to separate data fetching concerns.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'react-hot-toast';
import useDatasetStore from '../../../store/datasetStore';


const getDatasetId = (dataset) => dataset?.id || dataset?._id || null;
const DASHBOARD_DATA_ERROR_TOAST_ID = 'dashboard-data-error';
const TERMINAL_STATUSES = ['completed', 'success', 'failed'];

export const useDashboardData = (selectedDataset) => {
    const { fetchDatasets } = useDatasetStore();
    const selectedDatasetId = getDatasetId(selectedDataset);

    // State
    const [loading, setLoading] = useState(true);
    const [kpiData, setKpiData] = useState([]);
    const [chartData, setChartData] = useState({});
    const [insights, setInsights] = useState([]);
    const [datasetInfo, setDatasetInfo] = useState(null);
    const [datasetData, setDatasetData] = useState([]);
    const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
    const [insightsSummary, setInsightsSummary] = useState(null);

    // Period selection for KPIs
    const [selectedPeriod, setSelectedPeriod] = useState('all');
    const [availablePeriods, setAvailablePeriods] = useState([]);

    // Enhanced v4.0 metadata
    const [domainInfo, setDomainInfo] = useState(null);
    const [qualityMetrics, setQualityMetrics] = useState(null);
    const [chartIntelligence, setChartIntelligence] = useState({});
    const selectedDatasetRef = useRef(selectedDataset);
    const pollIntervalRef = useRef(null);
    const activeRequestIdRef = useRef(0);
    const lastFailureAtRef = useRef(0);

    const resetDashboardState = useCallback(() => {
        setKpiData([]);
        setChartData({});
        setInsights([]);
        setDatasetInfo(null);
        setDatasetData([]);
        setLastUpdatedAt(null);
        setInsightsSummary(null);
        setDomainInfo(null);
        setQualityMetrics(null);
        setChartIntelligence({});
        setSelectedPeriod('all');
    }, []);

    useEffect(() => {
        selectedDatasetRef.current = selectedDataset;
    }, [selectedDataset]);

    const clearProcessingPoll = useCallback(() => {
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
        }
    }, []);

    const loadDashboardData = useCallback(async () => {
        if (!selectedDatasetId) {
            clearProcessingPoll();
            activeRequestIdRef.current += 1;
            resetDashboardState();
            setLoading(false);
            return;
        }

        const currentSelectedDataset = selectedDatasetRef.current;
        const requestId = activeRequestIdRef.current + 1;
        activeRequestIdRef.current = requestId;
        setLoading(true);

        const showDataError = (message) => {
            const now = Date.now();
            if (now - lastFailureAtRef.current < 3000) {
                return;
            }
            lastFailureAtRef.current = now;
            toast.error(message, { id: DASHBOARD_DATA_ERROR_TOAST_ID });
        };

        // Safety timeout to prevent silent hanging without punishing normal API latency.
        const safetyTimeout = setTimeout(() => {
            console.warn('Dashboard loading took too long, forcing completion');
            setLoading(false);
        }, 20000);

        try {
            // Preserve the current dashboard during transient failures for the same dataset.
            setLastUpdatedAt(currentSelectedDataset?.updated_at || currentSelectedDataset?.created_at || null);

   
            // Use the already-available selectedDataset from the ref (avoids a redundant API call)
            const currentDataset = selectedDatasetRef.current;
            if (activeRequestIdRef.current !== requestId) return;

            if (currentDataset && (currentDataset.row_count === 0 || currentDataset.column_count === 0)) {
                console.warn('Dataset is empty (0 rows or 0 columns)');
                resetDashboardState();
                showDataError('Dataset is empty or failed to process. Please upload a valid dataset.');
                setLoading(false);
                clearTimeout(safetyTimeout);
                return;
            }

            if (!currentDataset) {
                clearProcessingPoll();
                resetDashboardState();
                setLoading(false);
                clearTimeout(safetyTimeout);
                return;
            }

            // Check if still processing
            if (currentDataset && !currentDataset.is_processed && currentDataset.processing_status !== 'failed') {
                // Set up a single polling loop. The backend pipeline has its own
                // size-aware timeout (it will eventually mark the dataset
                // completed or failed), so this loop is only a UI refresher.
                // Safety cap: give up after 30 min so a stuck dataset (e.g.
                // pipeline task died without a restart) doesn't poll forever.
                const MAX_POLL_MS = 30 * 60 * 1000;
                if (!pollIntervalRef.current) {
                    const pollStart = Date.now();
                    pollIntervalRef.current = setInterval(async () => {
                        try {
                            if (Date.now() - pollStart > MAX_POLL_MS) {
                                clearProcessingPoll();
                                console.warn('Stopped polling for dataset processing (30 min cap)');
                                return;
                            }
                            const updatedDatasets = await fetchDatasets(true);
                            const updatedDataset = updatedDatasets.find(
                                d => d.id === selectedDatasetId || d._id === selectedDatasetId
                            );
                            if (
                                updatedDataset &&
                                (updatedDataset.is_processed || updatedDataset.processing_status === 'failed')
                            ) {
                                clearProcessingPoll();
                                // Manual force refresh once processing completes to get final artifacts
                                await fetchDatasets(true, true);
                                loadDashboardData();
                            }
                        } catch (error) {
                            console.error('Error polling for dataset updates:', error);
                        }
                    }, 8000);
                }

                clearTimeout(safetyTimeout);
                setLoading(false);
                return;
            }

            clearProcessingPoll();

            // Fire dataset data fetch in parallel (raw data, not AI generation)
            const dataFetch = fetch(`/api/datasets/${selectedDatasetId}/data?page=1&page_size=1000`, { credentials: 'include' });

            // ── Step 1: KPIs (overview) ──────────────────────────────────────
            try {
                const overviewRes = await fetch(`/api/dashboard/${selectedDatasetId}/overview?period=${selectedPeriod}`, { credentials: 'include' });
                if (activeRequestIdRef.current !== requestId) return;
                if (overviewRes.ok) {
                    const overviewData = await overviewRes.json();
                    if (activeRequestIdRef.current !== requestId) return;
                    setKpiData(overviewData.kpis || []);
                    if (overviewData.available_periods) setAvailablePeriods(overviewData.available_periods);
                    setDatasetInfo(overviewData.dataset || {});
                    if (currentSelectedDataset?.metadata) {
                        const metadata = currentSelectedDataset.metadata;
                        if (metadata.dataset_overview) {
                            setDomainInfo({
                                domain: metadata.dataset_overview.domain,
                                confidence: metadata.dataset_overview.domain_confidence,
                                method: metadata.dataset_overview.domain_detection_method
                            });
                        }
                        if (metadata.data_quality) setQualityMetrics(metadata.data_quality);
                    }
                } else {
                    setKpiData([]);
                    setDatasetInfo({ name: currentSelectedDataset?.name, row_count: currentSelectedDataset?.row_count || 0, column_count: currentSelectedDataset?.column_count || 0 });
                }
            } catch (e) {
                console.error('Failed to load KPI/overview data:', e);
                setKpiData([]);
            }

            // KPIs are ready — unblock the page render now
            if (activeRequestIdRef.current === requestId) setLoading(false);

            // ── Step 2: Charts — DISABLED ───────────────────────────────────
            // Chart data fetching is disabled as part of the KPI-first refactor.
            // Original code retained below.
            //
            // try {
            //     const chartsRes = await fetch(`/api/dashboard/${selectedDatasetId}/charts`);
            //     ...
            // } catch (e) { ... }

            // ── Step 3: Insights ─────────────────────────────────────────────
            if (activeRequestIdRef.current !== requestId) return;
            try {
                const insightsController = new AbortController();
                const insightsTimeout = setTimeout(() => insightsController.abort(), 12000);
                const insightsRes = await fetch(`/api/dashboard/${selectedDatasetId}/insights`, { credentials: 'include', signal: insightsController.signal });
                clearTimeout(insightsTimeout);
                if (activeRequestIdRef.current !== requestId) return;
                if (insightsRes.ok) {
                    const insightsData = await insightsRes.json();
                    if (activeRequestIdRef.current !== requestId) return;
                    const realInsights = (insightsData.insights || []).filter(i => i.title && i.description);
                    setInsights(realInsights);
                    setInsightsSummary(insightsData.summary || null);
                    setLastUpdatedAt(insightsData.generated_at || currentSelectedDataset?.updated_at || currentSelectedDataset?.created_at || null);
                } else {
                    setInsights([]);
                    setInsightsSummary(null);
                }
            } catch (e) {
                if (e?.name === 'AbortError') {
                    console.warn('Insights request timed out after 12s - continuing without insights');
                } else {
                    console.error('Failed to load insights:', e);
                }
                setInsights([]);
                setInsightsSummary(null);
            }

            // ── Resolve dataset data (was fetched in parallel from step 1) ──
            if (activeRequestIdRef.current !== requestId) return;
            try {
                const dataRes = await dataFetch;
                if (dataRes.ok) {
                    const parsedData = await dataRes.json();
                    if (activeRequestIdRef.current !== requestId) return;
                    setDatasetData(parsedData.data || []);
                }
            } catch (e) {
                console.error('Failed to load dataset data:', e);
                setDatasetData([]);
            }

        } catch (err) {
            console.error('Dashboard load failed:', err);
            if (activeRequestIdRef.current !== requestId) return;
            if (!(err instanceof TypeError)) {
                setDatasetInfo({
                    name: currentSelectedDataset?.name,
                    row_count: currentSelectedDataset?.row_count || 0,
                    column_count: currentSelectedDataset?.column_count || 0
                });
            }
            showDataError(
                err instanceof TypeError
                    ? 'Backend is unavailable. Showing the last dashboard snapshot.'
                    : 'Failed to load dashboard data'
            );
        } finally {
            clearTimeout(safetyTimeout);
            if (activeRequestIdRef.current === requestId) {
                setLoading(false);
            }
        }
    }, [selectedDatasetId, fetchDatasets, clearProcessingPoll, resetDashboardState]);

    // ── Instant completion via WebSocket ────────────────────────────────
    // When the backend pushes a terminal status (completed/failed) for the
    // selected dataset, `applyProcessingUpdate` patches it in the store. This
    // watcher detects the active → terminal *transition* (ignoring mount and
    // dataset switches, which the main effect handles) and refreshes + reloads
    // immediately instead of waiting for the next 8s poll tick.
    const prevStatusRef = useRef(null);
    const prevIdRef = useRef(null);

    useEffect(() => {
        const ds = selectedDatasetRef.current;
        const id = getDatasetId(ds);
        if (!ds || !id) return;

        const status = String(ds.processing_status || ds.status || '').toLowerCase();
        const isTerminal = TERMINAL_STATUSES.includes(status);

        // Dataset switched (or first observation) — reset tracking and let
        // the main effect handle the load.
        if (prevIdRef.current !== id) {
            prevIdRef.current = id;
            prevStatusRef.current = status;
            return;
        }

        const prevStatus = prevStatusRef.current;
        prevStatusRef.current = status;

        const wasActive = prevStatus && !TERMINAL_STATUSES.includes(prevStatus);
        if (wasActive && isTerminal) {
            // Mirror the poll's completion path: pull final artifacts first,
            // then reload the dashboard.
            (async () => {
                try {
                    await fetchDatasets(true, true);
                    loadDashboardData();
                } catch (err) {
                    console.warn('Failed to refresh after processing completed:', err);
                }
            })();
        }
    }, [selectedDataset, fetchDatasets, loadDashboardData]);

    useEffect(() => {
        loadDashboardData();
        return () => {
            clearProcessingPoll();
            activeRequestIdRef.current += 1;
        };
    }, [selectedDatasetId, selectedPeriod, loadDashboardData, clearProcessingPoll]);

    return {
        loading,
        kpiData,
        chartData,
        insights,
        datasetInfo,
        datasetData,
        domainInfo,
        qualityMetrics,
        chartIntelligence,
        lastUpdatedAt,
        insightsSummary,
        refreshDashboard: loadDashboardData,
        // Period selection
        selectedPeriod,
        setSelectedPeriod,
        availablePeriods
    };
};
