/**
 * useInsightsData Hook
 *
 * Fetches comprehensive insights data for the dedicated Insights page.
 * Manages loading states, error handling, data refresh,
 * and subset filtering via ?filters= query parameter.
 *
 * Features:
 * - Returns base data immediately (KPIs, charts, insights)
 * - Polls separately for story completion
 * - Shows "Generating story..." placeholder while story generates
 * - Caches story permanently until explicit refresh
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'react-hot-toast';
import { insightsAPI } from '../../../services/api';
import useDatasetStore from '../../../store/datasetStore';

export const clearInsightsDataCache = () => {
    // No-op retained for backwards compatibility with authStore logout flow.
};

export const useInsightsData = (selectedDataset) => {
    const { fetchDatasets, isBackendOffline } = useDatasetStore();
    const datasetId = selectedDataset?.id || selectedDataset?._id || null;
    const artifactStatus = selectedDataset?.artifact_status?.insights_report || null;
    const isDatasetProcessed = Boolean(selectedDataset?.is_processed);

    const [loading, setLoading] = useState(!!datasetId);
    const [error, setError] = useState(null);
    const [filters, setFilters] = useState(null);
    const [data, setData] = useState(null);
    const [storyStatus, setStoryStatus] = useState('not_started'); // not_started, generating, ready, failed
    const abortRef = useRef(null);
    const pollRef = useRef(null);
    const storyPollRef = useRef(null);

    const clearArtifactPoll = useCallback(() => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, []);

    const clearStoryPoll = useCallback(() => {
        if (storyPollRef.current) {
            clearInterval(storyPollRef.current);
            storyPollRef.current = null;
        }
    }, []);

    const fetchInsights = useCallback(async (forceRefresh = false, activeFilters = filters) => {
        if (!datasetId) {
            setData(null);
            setLoading(false);
            return;
        }

        // Cancel any in-flight request
        if (abortRef.current) {
            abortRef.current.abort();
        }
        const controller = new AbortController();
        abortRef.current = controller;

        setLoading(true);
        setError(null);

        try {
            const res = await insightsAPI.getComprehensiveInsights(
                datasetId,
                forceRefresh,
                { signal: controller.signal },
                activeFilters
            );
            const result = res.data;
            setData(result);

            // Track story status from response
            if (result?.story_status) {
                setStoryStatus(result.story_status);
            } else if (result?.is_story_available) {
                setStoryStatus('ready');
            } else {
                setStoryStatus('not_started');
            }

            // If story is not ready, start polling for it
            if (!result?.is_story_available && !result?.story_status) {
                // Use ref to avoid stale closure
                if (!storyPollRef.current) {
                    setStoryStatus('generating');
                    storyPollRef.current = setInterval(async () => {
                        try {
                            // Poll with force=true but manual=false to allow 5s throttling
                            const datasets = await fetchDatasets(true, false);
                            const updated = datasets.find((item) =>
                                (item.id || item._id) === datasetId
                            );
                            const narrativeStatus = updated?.artifact_status?.narrative_story;
                            if (narrativeStatus === 'ready') {
                                clearInterval(storyPollRef.current);
                                storyPollRef.current = null;
                                const r = await insightsAPI.getComprehensiveInsights(datasetId, false, {}, null);
                                setData(r.data);
                                setStoryStatus('ready');
                            } else if (narrativeStatus === 'failed') {
                                clearInterval(storyPollRef.current);
                                storyPollRef.current = null;
                                setStoryStatus('failed');
                            }
                        } catch (pollError) {
                            console.error('Failed polling story status:', pollError);
                        }
                    }, 10000);
                }
            }

            setLoading(false);
        } catch (err) {
            if (err.name === 'CanceledError' || err.name === 'AbortError') return;
            console.error('Failed to load insights:', err);
            setError(err.response?.data?.detail || 'Failed to load insights');
            toast.error('Failed to load insights. Please try again.');
            setLoading(false);
        }
    }, [datasetId, fetchDatasets, filters]);

    // Apply filters — triggers a fresh fetch
    const applyFilters = useCallback((filterStr) => {
        clearStoryPoll();
        setFilters(filterStr || null);
    }, []);

    // Clear all filters
    const clearFilters = useCallback(() => {
        clearStoryPoll();
        setFilters(null);
    }, []);

    // Gracefully handle backend offline state
    useEffect(() => {
        if (isBackendOffline) {
            clearArtifactPoll();
            clearStoryPoll();
            setLoading(false);
        }
    }, [isBackendOffline, clearArtifactPoll, clearStoryPoll]);

    useEffect(() => {
        fetchInsights(false, filters);
        return () => {
            clearArtifactPoll();
            clearStoryPoll();
            if (abortRef.current) abortRef.current.abort();
        };
    }, [fetchInsights, filters, clearArtifactPoll, clearStoryPoll]);

    const hasData = Boolean(data);
    useEffect(() => {
        if (!datasetId || filters || !isDatasetProcessed) {
            clearArtifactPoll();
            return;
        }

        if (artifactStatus === 'pending' || artifactStatus === 'generating') {
            // Keep spinner only when there is no payload yet.
            setLoading(!hasData);
            if (!pollRef.current) {
                pollRef.current = setInterval(async () => {
                    try {
                        // Poll with force=true but manual=false to allow 5s throttling
                        const datasets = await fetchDatasets(true, false);
                        const updated = datasets.find((item) =>
                            (item.id || item._id) === datasetId
                        );
                        const nextStatus = updated?.artifact_status?.insights_report;
                        if (nextStatus === 'ready') {
                            clearArtifactPoll();
                            fetchInsights(false, null);
                        } else if (nextStatus === 'failed') {
                            clearArtifactPoll();
                            setLoading(false);
                            setError('Insights preparation failed. Please refresh to retry.');
                        }
                    } catch (pollError) {
                        console.error('Failed polling insights artifact status:', pollError);
                    }
                }, 8000); // Increased polling interval to 8 seconds to reduce server load
            }
            return;
        }

        clearArtifactPoll();
    }, [
        artifactStatus,
        clearArtifactPoll,
        hasData,
        datasetId,
        fetchDatasets,
        fetchInsights,
        filters,
        isDatasetProcessed,
    ]);

    const refresh = useCallback(async () => {
        clearStoryPoll();
        // Force a fresh dataset list check as part of manual refresh
        await fetchDatasets(true, true);
        return fetchInsights(true, filters);
    }, [clearStoryPoll, fetchDatasets, fetchInsights, filters]);

    return {
        loading,
        error,
        data,
        filters,
        storyStatus,
        artifactStatus,
        refresh,
        applyFilters,
        clearFilters,
    };
};
