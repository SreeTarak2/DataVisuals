/**
 * useDashboardData Hook
 * 
 * Custom hook for fetching and managing dashboard data (overview, charts, insights).
 * Extracted from Dashboard.jsx to separate data fetching concerns.
 */

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'react-hot-toast';
import useDatasetStore from '../../../store/datasetStore';
import { getAuthToken } from '../../../services/api';

export const useDashboardData = (selectedDataset) => {
    const { fetchDatasets } = useDatasetStore();

    // State
    const [loading, setLoading] = useState(true);
    const [kpiData, setKpiData] = useState([]);
    const [chartData, setChartData] = useState({});
    const [insights, setInsights] = useState([]);
    const [datasetInfo, setDatasetInfo] = useState(null);
    const [datasetData, setDatasetData] = useState([]);

    // Enhanced v4.0 metadata
    const [domainInfo, setDomainInfo] = useState(null);
    const [qualityMetrics, setQualityMetrics] = useState(null);
    const [chartIntelligence, setChartIntelligence] = useState({});

    const loadDashboardData = useCallback(async () => {
        if (!selectedDataset || !selectedDataset.id) {
            setLoading(false);
            return;
        }

        setLoading(true);

        // Safety timeout to prevent infinite loading (5 seconds max)
        const safetyTimeout = setTimeout(() => {
            console.warn('Dashboard loading took too long, forcing completion');
            toast.error('Dashboard loading timed out. Please try refreshing.');
            setLoading(false);
        }, 5000);

        try {
            // Clear cached data
            setKpiData([]);
            setInsights([]);
            setChartData({});

            // Fetch fresh dataset data
            const freshDatasets = await fetchDatasets(true);

            // Check if dataset is empty
            const currentDataset = freshDatasets.find(
                d => d.id === selectedDataset.id || d._id === selectedDataset.id
            );

            if (currentDataset && (currentDataset.row_count === 0 || currentDataset.column_count === 0)) {
                console.warn('Dataset is empty (0 rows or 0 columns)');
                toast.error('Dataset is empty or failed to process. Please upload a valid dataset.');
                setLoading(false);
                clearTimeout(safetyTimeout);
                return;
            }

            // Check if still processing
            if (currentDataset && !currentDataset.is_processed && currentDataset.processing_status !== 'failed') {
                // Set up polling
                const pollInterval = setInterval(async () => {
                    try {
                        const updatedDatasets = await fetchDatasets(true);
                        const updatedDataset = updatedDatasets.find(
                            d => d.id === selectedDataset.id || d._id === selectedDataset.id
                        );
                        if (updatedDataset && updatedDataset.is_processed) {
                            clearInterval(pollInterval);
                            loadDashboardData();
                        }
                    } catch (error) {
                        console.error('Error polling for dataset updates:', error);
                    }
                }, 3000);

                return () => clearInterval(pollInterval);
            }

            const token = getAuthToken();

            // Load actual dataset data
            const dataResponse = await fetch(
                `/api/datasets/${selectedDataset.id}/data?page=1&page_size=1000`,
                { headers: { 'Authorization': `Bearer ${token}` } }
            );

            if (dataResponse.ok) {
                const dataResult = await dataResponse.json();
                setDatasetData(dataResult.data || []);
                console.log('Loaded dataset data for charts:', dataResult.data?.length || 0, 'rows');
            } else {
                console.error('Failed to load dataset data:', dataResponse.status);
                setDatasetData([]);
            }

            // Load dashboard components sequentially
            const overviewRes = await fetch(
                `/api/dashboard/${selectedDataset.id}/overview`,
                { headers: { 'Authorization': `Bearer ${token}` } }
            );

            const chartsRes = await fetch(
                `/api/dashboard/${selectedDataset.id}/charts`,
                { headers: { 'Authorization': `Bearer ${token}` } }
            );

            // Delay before heavy AI calls
            await new Promise(resolve => setTimeout(resolve, 1000));

            // Insights with timeout
            const insightsController = new AbortController();
            const insightsTimeout = setTimeout(() => insightsController.abort(), 10000);

            let insightsRes;
            try {
                insightsRes = await fetch(
                    `/api/dashboard/${selectedDataset.id}/insights`,
                    {
                        headers: { 'Authorization': `Bearer ${token}` },
                        signal: insightsController.signal
                    }
                );
                clearTimeout(insightsTimeout);
            } catch (fetchError) {
                clearTimeout(insightsTimeout);
                if (fetchError.name === 'AbortError') {
                    console.warn('Insights request timed out after 10s - using cached data');
                    insightsRes = { ok: false, status: 408 };
                } else {
                    throw fetchError;
                }
            }

            // Process overview data
            if (overviewRes.ok) {
                const overviewData = await overviewRes.json();
                console.log('Dashboard overview data:', overviewData);
                setKpiData(overviewData.kpis || []);

                const datasetInfo = overviewData.dataset || {};
                setDatasetInfo(datasetInfo);

                // Extract v4.0 enhanced metadata
                if (selectedDataset.metadata) {
                    const metadata = selectedDataset.metadata;

                    if (metadata.dataset_overview) {
                        setDomainInfo({
                            domain: metadata.dataset_overview.domain,
                            confidence: metadata.dataset_overview.domain_confidence,
                            method: metadata.dataset_overview.domain_detection_method
                        });
                    }

                    if (metadata.data_quality) {
                        setQualityMetrics(metadata.data_quality);
                    }
                }
            } else {
                console.error('Failed to load overview data:', overviewRes.status);
                setKpiData([]);
                setDatasetInfo({
                    name: selectedDataset.name,
                    row_count: selectedDataset.row_count || 0,
                    column_count: selectedDataset.column_count || 0
                });
                setDomainInfo(null);
                setQualityMetrics(null);
            }

            // Process charts data
            if (chartsRes.ok) {
                const chartsData = await chartsRes.json();
                console.log('Dashboard charts data:', chartsData);

                const charts = chartsData.charts || {};
                setChartData(charts);

                // Extract intelligence and insights from charts
                const intelligenceMap = {};
                if (Array.isArray(charts)) {
                    charts.forEach((chart, index) => {
                        if (chart.intelligence) {
                            intelligenceMap[`chart_${index}`] = {
                                intelligence: chart.intelligence,
                                insights: chart.insights
                            };
                        }
                    });
                } else if (typeof charts === 'object') {
                    Object.keys(charts).forEach(key => {
                        const chart = charts[key];
                        if (chart.intelligence) {
                            intelligenceMap[key] = {
                                intelligence: chart.intelligence,
                                insights: chart.insights
                            };
                        }
                    });
                }
                setChartIntelligence(intelligenceMap);
            } else {
                console.error('Failed to load charts data:', chartsRes.status);
                setChartData({});
                setChartIntelligence({});
            }

            // Process insights data
            if (insightsRes.ok) {
                try {
                    const insightsData = await insightsRes.json();
                    console.log('Dashboard insights data:', insightsData);

                    // Filter out hardcoded insights
                    const realInsights = (insightsData.insights || []).filter(insight =>
                        !insight.title?.toLowerCase().includes('pearson correlation') &&
                        !insight.title?.toLowerCase().includes('strong correlation') &&
                        insight.title && insight.description
                    );
                    setInsights(realInsights);
                } catch (parseError) {
                    console.error('Failed to parse insights data:', parseError);
                    setInsights([]);
                }
            } else {
                console.warn('Insights not loaded (status:', insightsRes.status, ')');
                setInsights([]);
            }

        } catch (err) {
            console.error('Dashboard load failed:', err);
            setKpiData([]);
            setChartData({});
            setInsights([]);
            setDatasetInfo({
                name: selectedDataset.name,
                row_count: selectedDataset.row_count || 0,
                column_count: selectedDataset.column_count || 0
            });
            toast.error('Failed to load dashboard data');
        } finally {
            clearTimeout(safetyTimeout);
            setLoading(false);
        }
    }, [selectedDataset, fetchDatasets]);

    useEffect(() => {
        loadDashboardData();
    }, [selectedDataset, loadDashboardData]);

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
        refreshDashboard: loadDashboardData
    };
};
