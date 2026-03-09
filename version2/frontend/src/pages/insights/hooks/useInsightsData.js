/**
 * useInsightsData Hook
 *
 * Fetches comprehensive insights data for the dedicated Insights page.
 * Manages loading states, error handling, data refresh, per-dataset caching,
 * and subset filtering via ?filters= query parameter.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'react-hot-toast';
import { insightsAPI } from '../../../services/api';

// Simple in-memory cache keyed by datasetId + filters
const insightsCache = new Map();
const cacheKey = (id, filters) => `${id}__${filters || ''}`;

export const useInsightsData = (selectedDataset) => {
    const datasetId = selectedDataset?.id || selectedDataset?._id || null;

    const cachedData = datasetId ? insightsCache.get(cacheKey(datasetId, null)) : null;
    const [loading, setLoading] = useState(!cachedData && !!datasetId);
    const [error, setError] = useState(null);
    const [filters, setFilters] = useState(null); // e.g. "col1:val1,col2:val2"
    const [data, setData] = useState(() => cachedData || null);
    const abortRef = useRef(null);

    const fetchInsights = useCallback(async (forceRefresh = false, activeFilters = filters) => {
        if (!datasetId) {
            setData(null);
            setLoading(false);
            return;
        }

        const key = cacheKey(datasetId, activeFilters);

        // Serve from cache if not forcing refresh
        if (!forceRefresh && insightsCache.has(key)) {
            setData(insightsCache.get(key));
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
            insightsCache.set(key, result);
            setData(result);
            setLoading(false);
        } catch (err) {
            if (err.name === 'CanceledError' || err.name === 'AbortError') return;
            console.error('Failed to load insights:', err);
            setError(err.response?.data?.detail || 'Failed to load insights');
            toast.error('Failed to load insights. Please try again.');
            setLoading(false);
        }
    }, [datasetId, filters]);

    // Apply filters — triggers a fresh fetch
    const applyFilters = useCallback((filterStr) => {
        setFilters(filterStr || null);
    }, []);

    // Clear all filters
    const clearFilters = useCallback(() => {
        setFilters(null);
    }, []);

    useEffect(() => {
        fetchInsights(false, filters);
        return () => {
            if (abortRef.current) abortRef.current.abort();
        };
    }, [fetchInsights, filters]);

    return {
        loading,
        error,
        data,
        filters,
        refresh: () => fetchInsights(true, filters),
        applyFilters,
        clearFilters,
    };
};

