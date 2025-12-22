/**
 * Dashboard Component - Refactored
 * 
 * Main dashboard page for DataSage AI.
 * Refactored from 1,669 lines to ~250 lines by extracting:
 * - Custom hooks for data fetching and state management
 * - Utility functions for data processing
 * - UI components for better organization
 * 
 * This component now acts as an orchestrator, composing hooks and components.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../../store/authStore';
import useDatasetStore from '../../store/datasetStore';

// Custom hooks
import { useDashboardData } from './hooks/useDashboardData';
import { useDashboardGeneration } from './hooks/useDashboardGeneration';
import { useKpiHydration } from './hooks/useKpiHydration';
import { useDataPreview } from './hooks/useDataPreview';

// Components
import DashboardHeader from './components/DashboardHeader';
import EmptyStates from './components/EmptyStates';
import DataPreviewTable from './components/DataPreviewTable';
import InsightsSection from './components/InsightsSection';
import RedesignLimitModal from './components/RedesignLimitModal';
import LoadingState from './components/LoadingState';
import DashboardComponent from '../../components/DashboardComponent';
import InsightsPanel from '../../components/InsightsPanel';
import ExecutiveSummary from '../../components/ExecutiveSummary';
import UploadModal from '../../components/UploadModal';

// Utils
import { getDatasetColumns, firstNumericColumn, firstCategoricalColumn } from './utils/columnHelpers';
import { sanitizeTransformedComponents } from './utils/dashboardSanitizer';

const Dashboard = () => {
    const { user } = useAuth();
    const { datasets, selectedDataset, fetchDatasets } = useDatasetStore();
    const navigate = useNavigate();

    // Local UI state
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [showRedesignLimitModal, setShowRedesignLimitModal] = useState(false);

    // Custom hooks for data and state management
    const {
        loading,
        kpiData,
        chartData,
        insights,
        datasetInfo,
        datasetData,
        domainInfo,
        qualityMetrics,
        chartIntelligence,
        refreshDashboard
    } = useDashboardData(selectedDataset);

    const { dataPreview, previewLoading, loadDataPreview } = useDataPreview(selectedDataset);

    const {
        aiDashboardConfig,
        layoutLoading,
        redesignCount,
        handleRegenerate,
        MAX_REDESIGNS
    } = useDashboardGeneration(selectedDataset, datasetData, {
        getDatasetColumns: () => getDatasetColumns(datasetData, dataPreview),
        firstNumericColumn: () => firstNumericColumn(datasetData, dataPreview),
        firstCategoricalColumn: () => firstCategoricalColumn(datasetData, dataPreview),
        sanitizeTransformedComponents: (components) => sanitizeTransformedComponents(components, { datasetData, dataPreview }),
        loadDataPreview
    });

    const { hydrateComponents } = useKpiHydration(datasetData);

    // Handle redesign with limit check
    const onRegenerateClick = () => {
        const success = handleRegenerate();
        if (!success) {
            setShowRedesignLimitModal(true);
        }
    };

    // Loading state
    if (loading) {
        return <LoadingState />;
    }

    // No dataset selected
    if (!selectedDataset) {
        return (
            <div className="min-h-screen bg-slate-950 p-6">
                <EmptyStates
                    type="no-dataset"
                    onUpload={() => setShowUploadModal(true)}
                />
                <UploadModal
                    isOpen={showUploadModal}
                    onClose={() => setShowUploadModal(false)}
                />
            </div>
        );
    }

    // Empty dataset (0 rows or columns)
    if (selectedDataset.row_count === 0 || selectedDataset.column_count === 0) {
        return (
            <div className="min-h-screen bg-slate-950 p-6">
                <EmptyStates
                    type="empty-dataset"
                    selectedDataset={selectedDataset}
                    onUpload={() => setShowUploadModal(true)}
                    onNavigateToDatasets={() => navigate('/datasets')}
                />
                <UploadModal
                    isOpen={showUploadModal}
                    onClose={() => setShowUploadModal(false)}
                />
            </div>
        );
    }

    // Main dashboard render
    return (
        <div className="min-h-screen bg-slate-950 p-6 space-y-8">
            {/* Header with metadata and redesign button */}
            <DashboardHeader
                selectedDataset={selectedDataset}
                domainInfo={domainInfo}
                qualityMetrics={qualityMetrics}
                redesignCount={redesignCount}
                layoutLoading={layoutLoading}
                onRegenerate={onRegenerateClick}
                MAX_REDESIGNS={MAX_REDESIGNS}
            />

            {/* AI-Generated Dashboard */}
            {aiDashboardConfig && aiDashboardConfig.components && aiDashboardConfig.components.length > 0 && (
                <div className="space-y-6">
                    {/* KPI Cards Section */}
                    <motion.div
                        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
                        variants={{
                            hidden: {},
                            visible: { transition: { staggerChildren: 0.1 } }
                        }}
                        initial="hidden"
                        animate="visible"
                    >
                        {aiDashboardConfig.components
                            .filter(component => component && component.type === 'kpi')
                            .map((component, index) => {
                                const hydratedComponents = hydrateComponents([component]);
                                const hydrated = hydratedComponents[0];
                                return (
                                    <motion.div
                                        key={`kpi-${index}`}
                                        variants={{
                                            hidden: { y: 20, opacity: 0 },
                                            visible: { y: 0, opacity: 1 }
                                        }}
                                    >
                                        <DashboardComponent
                                            component={hydrated}
                                            datasetData={datasetData}
                                        />
                                    </motion.div>
                                );
                            })}
                    </motion.div>

                    {/* Charts Section */}
                    <motion.div
                        className="space-y-6"
                        variants={{
                            hidden: {},
                            visible: { transition: { staggerChildren: 0.1 } }
                        }}
                        initial="hidden"
                        animate="visible"
                    >
                        {aiDashboardConfig.components
                            .filter(component => component && component.type === 'chart')
                            .map((component, index) => (
                                <motion.div
                                    key={`chart-${index}`}
                                    variants={{
                                        hidden: { y: 20, opacity: 0 },
                                        visible: { y: 0, opacity: 1 }
                                    }}
                                >
                                    <DashboardComponent
                                        component={component}
                                        datasetData={datasetData}
                                    />
                                </motion.div>
                            ))}
                    </motion.div>
                </div>
            )}

            {/* Insights Panel */}
            <InsightsPanel
                insights={insights}
                prioritizedColumns={[]}
                datasetInfo={datasetInfo}
            />

            {/* Executive Summary */}
            <ExecutiveSummary
                datasetId={selectedDataset?.id}
                insights={insights}
                prioritizedColumns={[]}
            />

            {/* AI Insights Section */}
            <InsightsSection
                insights={insights}
                loading={loading}
            />

            {/* Data Preview Table */}
            <DataPreviewTable
                dataPreview={dataPreview}
                loading={previewLoading}
                onReload={loadDataPreview}
            />

            {/* Upload Modal */}
            <UploadModal
                isOpen={showUploadModal}
                onClose={() => setShowUploadModal(false)}
            />

            {/* Redesign Limit Modal */}
            <RedesignLimitModal
                isOpen={showRedesignLimitModal}
                onClose={() => setShowRedesignLimitModal(false)}
                onRefresh={() => window.location.reload()}
                MAX_REDESIGNS={MAX_REDESIGNS}
            />
        </div>
    );
};

export default Dashboard;
