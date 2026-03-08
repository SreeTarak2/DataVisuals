/**
 * useDataPreview Hook
 * 
 * Custom hook for loading and managing data preview table.
 * Now fetches up to 200 rows for client-side search/sort/pagination.
 */

import { useState, useCallback, useEffect } from 'react';
import { getAuthToken } from '../../../services/api';

const PREVIEW_LIMIT = 200;

export const useDataPreview = (selectedDataset) => {
    const [dataPreview, setDataPreview] = useState([]);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [totalRows, setTotalRows] = useState(null);
    const selectedDatasetId = selectedDataset?.id || null;

    const loadDataPreview = useCallback(async () => {
        if (!selectedDatasetId) return;

        try {
            setPreviewLoading(true);
            const token = getAuthToken();

            // Try paginated data endpoint first (returns total_count)
            const response = await fetch(
                `/api/datasets/${selectedDatasetId}/data?page=1&page_size=${PREVIEW_LIMIT}`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                }
            );

            if (response.ok) {
                const result = await response.json();
                setDataPreview(result.data || []);
                setTotalRows(result.total_count ?? result.total ?? null);
            } else {
                // Fallback to preview endpoint
                const fallback = await fetch(
                    `/api/datasets/${selectedDatasetId}/preview?limit=${PREVIEW_LIMIT}`,
                    {
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        }
                    }
                );

                if (fallback.ok) {
                    const data = await fallback.json();
                    setDataPreview(data.rows || []);
                } else {
                    setDataPreview([]);
                }
            }
        } catch (err) {
            console.warn('Data preview loading error:', err);
            setDataPreview([]);
        } finally {
            setPreviewLoading(false);
        }
    }, [selectedDatasetId]);

    // Auto-load when dataset changes
    useEffect(() => {
        if (selectedDatasetId) {
            loadDataPreview();
        }
    }, [selectedDatasetId, loadDataPreview]);

    return {
        dataPreview,
        previewLoading,
        totalRows,
        loadDataPreview
    };
};
