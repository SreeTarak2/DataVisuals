/**
 * useDashboardGeneration Hook
 * 
 * Custom hook for AI-powered dashboard generation.
 * Handles dashboard design API calls, component transformation, and redesign counting.
 * Extracted from Dashboard.jsx to separate AI dashboard generation concerns.
 */

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'react-hot-toast';
import { normalizeDashboardConfig } from '../../../utils/dashboardUtils';
import { getAuthToken } from '../../../services/api';

const MAX_REDESIGNS = 3;

export const useDashboardGeneration = (selectedDataset, datasetData, helpers) => {
    const {
        getDatasetColumns,
        firstNumericColumn,
        firstCategoricalColumn,
        sanitizeTransformedComponents,
        loadDataPreview
    } = helpers;

    const [aiDashboardConfig, setAiDashboardConfig] = useState(null);
    const [layoutLoading, setLayoutLoading] = useState(false);
    const [redesignCount, setRedesignCount] = useState(0);

    const generateAiDashboard = useCallback(async (forceRegenerate = false) => {
        if (!selectedDataset || !selectedDataset.id) {
            console.log('No dataset selected, skipping AI dashboard generation');
            setAiDashboardConfig(null);
            return;
        }

        if (!selectedDataset.is_processed) {
            console.log('Dataset not processed yet, skipping AI dashboard generation');
            setAiDashboardConfig(null);
            return;
        }

        try {
            setLayoutLoading(true);
            const token = getAuthToken();
            console.log('Starting AI dashboard generation for dataset:', selectedDataset.id);

            // Delay before AI dashboard generation
            await new Promise(resolve => setTimeout(resolve, 2000));

            // Try AI Designer service first
            try {
                console.log('Trying AI Designer service...');
                const response = await fetch(`/api/ai/${selectedDataset.id}/design-dashboard`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ force_regenerate: !!forceRegenerate })
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
                            return;
                        }
                    }
                }
            } catch (designError) {
                console.log('AI Designer service failed, falling back to legacy:', designError);
            }

            // Fallback to legacy AI dashboard generation
            console.log('Trying legacy AI dashboard generation...');
            const response = await fetch(
                `/api/ai/${selectedDataset.id}/generate-dashboard?force_regenerate=${forceRegenerate}`,
                {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
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
                    } else {
                        setAiDashboardConfig(null);
                    }
                } else {
                    console.log('No dashboard components found in response');
                    setAiDashboardConfig(null);
                }
            } else {
                console.error('Legacy AI dashboard generation failed:', response.status);
                setAiDashboardConfig(null);
                throw new Error('Failed to generate AI dashboard');
            }
        } catch (error) {
            console.error('AI Dashboard generation failed:', error);
            setAiDashboardConfig(null);
            toast.error('Failed to generate AI dashboard');
        } finally {
            setLayoutLoading(false);

            if (aiDashboardConfig !== null) {
                setTimeout(() => {
                    toast.success('✨ AI Dashboard generated successfully!', {
                        id: 'dashboard-generated',
                        duration: 3000,
                    });
                }, 100);
            }
        }
    }, [selectedDataset, helpers, sanitizeTransformedComponents]);

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
        if (selectedDataset?.id) {
            generateAiDashboard();
        }
    }, [selectedDataset?.id]);

    return {
        aiDashboardConfig,
        layoutLoading,
        redesignCount,
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
                transformedComponents.push({
                    type: 'chart',
                    title: chart.chart_type ?
                        `${chart.chart_type.replace('_', ' ').toUpperCase()} Chart` :
                        `Chart ${chartIndex + 1}`,
                    span: 2,
                    config: {
                        chart_type: chart.chart_type || chart.type || 'bar_chart',
                        columns: chart.data ?
                            chart.data.map(d => d.x || d.y).filter(Boolean) :
                            [firstNumericColumn(), firstCategoricalColumn()],
                        aggregation: 'mean',
                        group_by: chart.data?.[0]?.x || firstCategoricalColumn()
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
