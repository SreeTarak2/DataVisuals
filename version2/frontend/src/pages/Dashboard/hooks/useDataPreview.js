/**
 * useDataPreview Hook
 * 
 * Custom hook for loading and managing data preview table.
 * Extracted from Dashboard.jsx to separate data preview concerns.
 */

import { useState, useCallback, useEffect } from 'react';
import { getAuthToken } from '../../../services/api';

export const useDataPreview = (selectedDataset) => {
    const [dataPreview, setDataPreview] = useState([]);
    const [previewLoading, setPreviewLoading] = useState(false);
    const selectedDatasetId = selectedDataset?.id || null;

    const loadDataPreview = useCallback(async () => {
        if (!selectedDatasetId) {
            console.warn('loadDataPreview: No dataset ID provided');
            return;
        }

        try {
            setPreviewLoading(true);
            console.log('Loading data preview for dataset:', selectedDatasetId);

            const token = getAuthToken();
            const response = await fetch(
                `/api/datasets/${selectedDatasetId}/preview?limit=10`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                }
            );

            console.log('Data preview response status:', response.status);

            if (response.ok) {
                const data = await response.json();
                console.log('Data preview response:', data);
                setDataPreview(data.rows || []);
            } else {
                console.warn('Could not load data preview, response status:', response.status);

                // Fallback to regular data endpoint
                console.log('Trying fallback to regular data endpoint...');
                try {
                    const fallbackResponse = await fetch(
                        `/api/datasets/${selectedDatasetId}/data?page=1&page_size=10`,
                        {
                            headers: {
                                'Authorization': `Bearer ${token}`,
                                'Content-Type': 'application/json'
                            }
                        }
                    );

                    if (fallbackResponse.ok) {
                        const fallbackData = await fallbackResponse.json();
                        console.log('Fallback data response:', fallbackData);
                        setDataPreview(fallbackData.data || []);
                    } else {
                        console.warn('Fallback also failed, status:', fallbackResponse.status);
                        setDataPreview([]);
                    }
                } catch (fallbackErr) {
                    console.warn('Fallback error:', fallbackErr);
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
        loadDataPreview
    };
};
