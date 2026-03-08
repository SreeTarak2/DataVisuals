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

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [filters, setFilters] = useState(null); // e.g. "col1:val1,col2:val2"
    const [data, setData] = useState(() => {
        return datasetId ? (insightsCache.get(cacheKey(datasetId, null)) || null) : null;
    });
    const abortRef = useRef(null);

    const fetchInsights = useCallback(async (forceRefresh = false, activeFilters = filters) => {
        if (!datasetId) {
            setData(null);
            return;
        }

        const key = cacheKey(datasetId, activeFilters);

        // Serve from cache if not forcing refresh
        if (!forceRefresh && insightsCache.has(key)) {
            setData(insightsCache.get(key));
            return;
        }

        // Cancel any in-flight request
        if (abortRef.current) {
            abortRef.current.abort();
        }
        abortRef.current = new AbortController();

        setLoading(true);
        setError(null);

        try {
            const res = await insightsAPI.getComprehensiveInsights(
                datasetId,
                forceRefresh,
                { signal: abortRef.current.signal },
                activeFilters
            );
            const result = res.data;
            insightsCache.set(key, result);
            setData(result);
        } catch (err) {
            if (err.name === 'CanceledError' || err.name === 'AbortError') return;
            console.error('Failed to load insights:', err);
            setError(err.response?.data?.detail || 'Failed to load insights');
            toast.error('Failed to load insights. Please try again.');
        } finally {
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

