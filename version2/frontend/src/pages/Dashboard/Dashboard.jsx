import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, Target, BarChart3 } from 'lucide-react';
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
import InsightsBar from './components/InsightsBar';
import RedesignLimitModal from './components/RedesignLimitModal';
import LoadingState from './components/LoadingState';
import DashboardComponent from '../../components/DashboardComponent';
import UploadModal from '../../components/UploadModal';

// Utils
import { getDatasetColumns, firstNumericColumn, firstCategoricalColumn } from './utils/columnHelpers';
import { sanitizeTransformedComponents } from './utils/dashboardSanitizer';

// ── Bento Layout Engine ──────────────────────────────────────────────────────
// Creates visually varied grid patterns instead of a monotonous straight grid.
// Smart-assigns column spans based on chart type + repeating asymmetric patterns.
const SPAN_CLASSES = {
    4: 'col-span-1 lg:col-span-4',
    5: 'col-span-1 lg:col-span-5',
    6: 'col-span-1 lg:col-span-6',
    7: 'col-span-1 lg:col-span-7',
    8: 'col-span-1 lg:col-span-8',
    12: 'col-span-1 lg:col-span-12',
};

const createBentoLayout = (charts) => {
    if (!charts || charts.length === 0) return [];

    const result = [];
    let i = 0;

    // How much horizontal space does this chart type ideally want?
    const getWidthScore = (chart) => {
        const type = chart.config?.chart_type?.toLowerCase() || '';
        if (['line', 'line_chart', 'area', 'multi_bar'].includes(type)) return 10;
        if (['bar', 'bar_chart', 'histogram', 'grouped_bar'].includes(type)) return 7;
        if (['scatter', 'scatter_plot', 'heatmap'].includes(type)) return 6;
        if (['box', 'box_plot', 'violin'].includes(type)) return 5;
        if (['pie', 'pie_chart', 'donut'].includes(type)) return 3;
        return 5;
    };

    // Row patterns — each array sums to 12 (grid columns)
    // Cycling through these creates visual rhythm and variety.
    const rowPatterns = [
        [7, 5],    // Asymmetric pair — wider left
        [4, 4, 4], // Even thirds
        [5, 7],    // Asymmetric pair — wider right
        [8, 4],    // Major + minor
        [6, 6],    // Even halves
        [4, 8],    // Minor + major
    ];

    let patternIdx = 0;

    while (i < charts.length) {
        // First chart always gets hero treatment — full width, tallest
        if (i === 0) {
            result.push({ chart: charts[i], span: 12, variant: 'hero' });
            i++;
            continue;
        }

        const remaining = charts.length - i;
        const pattern = rowPatterns[patternIdx % rowPatterns.length];
        const slots = Math.min(pattern.length, remaining);
        const rowCharts = charts.slice(i, i + slots);

        if (slots === pattern.length) {
            // Full pattern — smart-assign wider spans to charts that need more room
            const spans = [...pattern];
            const sortedSpanIndices = spans
                .map((s, idx) => ({ span: s, idx }))
                .sort((a, b) => b.span - a.span);
            const scored = rowCharts
                .map((c, idx) => ({ chart: c, score: getWidthScore(c), origIdx: idx }))
                .sort((a, b) => b.score - a.score);

            const assignments = new Array(slots);
            scored.forEach((s, rankIdx) => {
                assignments[s.origIdx] = sortedSpanIndices[rankIdx].span;
            });

            rowCharts.forEach((chart, idx) => {
                const span = assignments[idx];
                result.push({
                    chart,
                    span,
                    variant: span >= 8 ? 'featured' : span >= 6 ? 'standard' : 'compact',
                });
            });
        } else if (slots === 2) {
            // Two remaining — asymmetric pair based on width needs
            const scores = rowCharts.map(c => getWidthScore(c));
            if (scores[0] >= scores[1]) {
                result.push({ chart: rowCharts[0], span: 7, variant: 'standard' });
                result.push({ chart: rowCharts[1], span: 5, variant: 'compact' });
            } else {
                result.push({ chart: rowCharts[0], span: 5, variant: 'compact' });
                result.push({ chart: rowCharts[1], span: 7, variant: 'standard' });
            }
        } else {
            // Single remaining chart — featured width
            result.push({ chart: rowCharts[0], span: 12, variant: 'featured' });
        }

        i += slots;
        patternIdx++;
    }

    return result;
};

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

    const { dataPreview, previewLoading, totalRows, loadDataPreview } = useDataPreview(selectedDataset);

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

    // Pre-compute bento layout for chart section
    const chartItems = useMemo(
        () => aiDashboardConfig?.components?.filter(c => c?.type === 'chart') || [],
        [aiDashboardConfig]
    );
    const bentoLayout = useMemo(() => createBentoLayout(chartItems), [chartItems]);

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
        // If dataset is still processing, show processing state instead of empty state
        if (selectedDataset.is_processed === false) {
            return (
                <div className="min-h-screen bg-slate-950 p-6">
                    <EmptyStates
                        type="processing-dataset"
                        onNavigateToDatasets={() => navigate('/app/datasets')}
                    />
                </div>
            );
        }

        return (
            <div className="min-h-screen bg-slate-950 p-6">
                <EmptyStates
                    type="empty-dataset"
                    selectedDataset={selectedDataset}
                    onUpload={() => setShowUploadModal(true)}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
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
        <div className="min-h-full bg-slate-950 px-4 py-6 sm:px-6 sm:py-8 lg:px-8 space-y-8 sm:space-y-10">
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
                    {/* AI Analysis Summary */}
                    {aiDashboardConfig.summary && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="bg-gradient-to-r from-ocean/10 via-purple-500/5 to-transparent border border-ocean/20 rounded-xl p-4 sm:p-5"
                        >
                            <div className="flex items-start gap-3">
                                <div className="p-2 rounded-lg bg-ocean/20 mt-0.5">
                                    <Sparkles className="w-4 h-4 text-ocean" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-gray-200 mb-1">AI Analysis</h3>
                                    <p className="text-xs text-gray-400 leading-relaxed">{aiDashboardConfig.summary}</p>
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {/* KPI Cards Section */}
                    {/* Add a subtle visual divider or section header if we want, but tightening the gap and grid is enough for hierarchy */}
                    <div className="mb-3 flex items-center gap-3">
                        <div className="flex items-center gap-2">
                            <div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/15">
                                <Target className="w-3.5 h-3.5 text-emerald-400" />
                            </div>
                            <span className="text-sm font-semibold text-slate-200 tracking-tight">Key Metrics</span>
                            <span className="px-1.5 py-0.5 rounded-md text-[11px] font-medium bg-slate-800/60 text-slate-400 border border-slate-700/40 tabular-nums">
                                {aiDashboardConfig.components.filter(c => c?.type === 'kpi').length}
                            </span>
                        </div>
                        <div className="h-px bg-slate-800/60 flex-1" />
                    </div>
                    <motion.div
                        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6"
                        variants={{
                            hidden: {},
                            visible: { transition: { staggerChildren: 0.08 } }
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

                    {/* ── Visual Analytics — Bento Grid ── */}
                    <div className="mt-12 mb-4 flex items-center gap-3">
                        <div className="flex items-center gap-2.5">
                            <div className="p-1.5 rounded-lg bg-violet-500/10 border border-violet-500/15">
                                <BarChart3 className="w-3.5 h-3.5 text-violet-400" />
                            </div>
                            <span className="text-sm font-semibold text-slate-200 tracking-tight">Visual Analytics</span>
                            <span className="px-1.5 py-0.5 rounded-md text-[11px] font-medium bg-slate-800/60 text-slate-400 border border-slate-700/40 tabular-nums">
                                {chartItems.length}
                            </span>
                        </div>
                        <div className="h-px bg-gradient-to-r from-slate-800/60 to-transparent flex-1" />
                    </div>
                    <motion.div
                        className="grid grid-cols-1 lg:grid-cols-12 gap-5"
                        variants={{
                            hidden: {},
                            visible: { transition: { staggerChildren: 0.07 } }
                        }}
                        initial="hidden"
                        animate="visible"
                    >
                        {bentoLayout.map(({ chart, span, variant }, index) => (
                            <motion.div
                                key={`chart-${index}`}
                                className={SPAN_CLASSES[span] || SPAN_CLASSES[6]}
                                variants={{
                                    hidden: { y: 24, opacity: 0, scale: 0.98 },
                                    visible: {
                                        y: 0,
                                        opacity: 1,
                                        scale: 1,
                                        transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }
                                    }
                                }}
                            >
                                <DashboardComponent
                                    component={chart}
                                    datasetData={datasetData}
                                    variant={variant}
                                />
                            </motion.div>
                        ))}
                    </motion.div>


                </div>
            )}

            {/* Statistical Insights */}
            <InsightsBar
                insights={insights}
                loading={loading}
            />

            {/* Data Preview Table */}
            <DataPreviewTable
                dataPreview={dataPreview}
                loading={previewLoading}
                onReload={loadDataPreview}
                totalRows={totalRows}
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
