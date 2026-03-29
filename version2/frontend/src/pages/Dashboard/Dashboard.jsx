import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, Target, BarChart3, Zap, ArrowRight } from 'lucide-react';
import useDatasetStore from '../../store/datasetStore';
import useDashboardActionStore from '../../store/dashboardActionStore';

// Custom hooks
import { useDashboardData } from './hooks/useDashboardData';
import { useDashboardGeneration } from './hooks/useDashboardGeneration';
import { useKpiHydration } from './hooks/useKpiHydration';
import { useDataPreview } from './hooks/useDataPreview';

// Components
import DashboardHeader from './components/DashboardHeader';
import EmptyStates from './components/EmptyStates';
import DataPreviewTable from './components/DataPreviewTable';
import RedesignLimitModal from './components/RedesignLimitModal';
import LoadingState from './components/LoadingState';
import DashboardComponent from '../../components/DashboardComponent';
import UploadModal from '../../components/UploadModal';
import PowerBIInsightCards from '../insights/components/PowerBIInsightCards';

// Utils
import { getDatasetColumns, firstNumericColumn, firstCategoricalColumn } from './utils/columnHelpers';
import { sanitizeTransformedComponents } from './utils/dashboardSanitizer';

const MotionDiv = motion.div;

// Dashboard API insight types → PowerBIInsightCards type names
const DASHBOARD_TYPE_MAP = { success: 'summary', info: 'summary', warning: 'anomaly', subspace: 'hidden_pattern' };

// ── Bento Layout Engine ──────────────────────────────────────────────────────
// Creates visually varied grid patterns instead of a monotonous straight grid.
// Smart-assigns column spans based on chart type + repeating asymmetric patterns.

const SPAN_CLASSES = {
    12: 'col-span-12 lg:col-span-12',
    10: 'col-span-12 lg:col-span-10',
    8: 'col-span-12 lg:col-span-8',
    7: 'col-span-12 lg:col-span-7',
    6: 'col-span-12 lg:col-span-6',
    5: 'col-span-12 lg:col-span-5',
    4: 'col-span-12 lg:col-span-4',
    3: 'col-span-12 lg:col-span-3',
};

const createBentoLayout = (charts) => {
    if (!charts || charts.length === 0) return [];

    const result = [];
    let i = 0;

    const getWidthScore = (chart) => {
        const type = chart.config?.chart_type?.toLowerCase() || '';
        if (['line', 'line_chart', 'area', 'multi_bar'].includes(type)) return 10;
        if (['bar', 'bar_chart', 'histogram', 'grouped_bar'].includes(type)) return 7;
        if (['scatter', 'scatter_plot', 'heatmap'].includes(type)) return 6;
        if (['box', 'box_plot', 'violin'].includes(type)) return 5;
        if (['pie', 'pie_chart', 'donut'].includes(type)) return 3;
        return 5;
    };

    const rowPatterns = [
        [7, 5], [4, 4, 4], [5, 7], [8, 4],
        [6, 6], [4, 8], [5, 4, 3], [3, 5, 4],
    ];

    const getAdaptivePattern = (remainingCharts, rowIndex) => {
        const hasPieDonut = remainingCharts.some(c =>
            ['pie', 'pie_chart', 'donut'].includes(c.config?.chart_type?.toLowerCase())
        );
        if (remainingCharts.length === 1) return [12];
        if (remainingCharts.length === 2) {
            if (hasPieDonut) return [8, 4];
            return [7, 5];
        }
        if (remainingCharts.length >= 3 && hasPieDonut) {
            const pieIndex = remainingCharts.findIndex(c =>
                ['pie', 'pie_chart', 'donut'].includes(c.config?.chart_type?.toLowerCase())
            );
            if (pieIndex === 0) return [3, 5, 4];
            if (pieIndex === remainingCharts.length - 1) return [5, 4, 3];
            return [5, 3, 4];
        }
        return rowPatterns[rowIndex % rowPatterns.length];
    };

    let patternIdx = 0;

    while (i < charts.length) {
        if (i === 0) {
            result.push({ chart: charts[i], span: 12, variant: 'hero' });
            i++;
            continue;
        }

        const remaining = charts.length - i;
        const pattern = getAdaptivePattern(charts.slice(i), patternIdx);
        const slots = Math.min(pattern.length, remaining);
        const rowCharts = charts.slice(i, i + slots);

        if (slots === pattern.length) {
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
            const scores = rowCharts.map(c => getWidthScore(c));
            if (scores[0] >= scores[1]) {
                result.push({ chart: rowCharts[0], span: 7, variant: 'standard' });
                result.push({ chart: rowCharts[1], span: 5, variant: 'compact' });
            } else {
                result.push({ chart: rowCharts[0], span: 5, variant: 'compact' });
                result.push({ chart: rowCharts[1], span: 7, variant: 'standard' });
            }
        } else {
            result.push({ chart: rowCharts[0], span: 12, variant: 'featured' });
        }

        i += slots;
        patternIdx++;
    }

    return result;
};

const KPI_LIMIT = 4;

const scoreKpiForDecisionUse = (component) => {
    const title = (component?.title || '').toLowerCase();
    let score = 0;

    if (/\b(avg|average|total|count|rate|ratio|score|revenue|sales|profit|users?|customers?|completion)\b/.test(title)) {
        score += 4;
    }
    if (/\b(by|impact|correlation|relationship|distribution|comparison|versus|vs|gap)\b/.test(title)) {
        score -= 5;
    }
    if ((component?.benchmarkText || component?.deltaPercent !== null && component?.deltaPercent !== undefined)) {
        score += 2;
    }
    if (component?.aiSuggestion) {
        score += 1;
    }
    if (title.length > 42) {
        score -= 1;
    }

    return score;
};

const curateKpiComponents = (components = []) => {
    if (!Array.isArray(components) || components.length === 0) {
        return [];
    }

    const ranked = [...components].sort((left, right) => scoreKpiForDecisionUse(right) - scoreKpiForDecisionUse(left));
    return ranked.slice(0, Math.min(KPI_LIMIT, ranked.length));
};

const Dashboard = () => {
    const { selectedDataset, activeUpload, isBackendOffline } = useDatasetStore();
    const navigate = useNavigate();

    // Local UI state
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [showRedesignLimitModal, setShowRedesignLimitModal] = useState(false);

    // Custom hooks for data and state management
    const {
        loading,
        insights,
        datasetData,
        domainInfo,
        qualityMetrics,
        lastUpdatedAt,
        insightsSummary,
        chartIntelligence: dashboardChartIntelligence,
    } = useDashboardData(selectedDataset);

    const { dataPreview, previewLoading, totalRows, loadDataPreview } = useDataPreview(selectedDataset);

    const {
        aiDashboardConfig,
        dashboardLoading,
        redesignLoading,
        artifactPreparing,
        redesignCount,
        dashboardArtifactStatus,
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

    // Handle redesign with limit check (memoized to prevent infinite loops)
    const onRegenerateClick = useCallback(() => {
        const success = handleRegenerate();
        if (!success) {
            setShowRedesignLimitModal(true);
        }
    }, [handleRegenerate, setShowRedesignLimitModal]);

    // Sync redesign state to dashboard action store for Header access
    const { setRedesigning, setRedesignAttempts, setOnRegenerate, setMaxRedesigns, crossFilter, setCrossFilter } = useDashboardActionStore();

    useEffect(() => {
        setRedesigning(redesignLoading);
        setRedesignAttempts(redesignCount);
    }, [redesignLoading, redesignCount]);

    // Set callbacks in store for Header access (Zustand setters are stable, don't need to depend on them)
    useEffect(() => {
        setOnRegenerate(onRegenerateClick);
        setMaxRedesigns(MAX_REDESIGNS);
    }, [onRegenerateClick, MAX_REDESIGNS]);

    // Pre-compute bento layout for chart section
    // Only AI-generated charts are shown — no fallback basic-API charts.
    // Showing overview charts while AI is computing (or after it fails) is misleading.
    const finalChartItems = useMemo(
        () => aiDashboardConfig?.components?.filter(c => c?.type === 'chart') || [],
        [aiDashboardConfig]
    );

    const hydratedKpis = useMemo(() => {
        const rawKpis = aiDashboardConfig?.components?.filter((component) => component?.type === 'kpi') || [];
        return hydrateComponents(rawKpis);
    }, [aiDashboardConfig, hydrateComponents]);
    const curatedKpis = useMemo(() => curateKpiComponents(hydratedKpis), [hydratedKpis]);

    // Show AI-designer KPIs only — no fast-path fallback KPIs.
    // Fast-path KPIs from the overview API produce low-quality cards (e.g. "Unique Gender: 3")
    // because they use count_unique on any non-numeric column with no business filtering.
    const visibleKpis = curatedKpis;

    const bentoLayout = useMemo(() => createBentoLayout(finalChartItems), [finalChartItems]);

    // Create chart intelligence map for passing to components
    const chartIntelligenceMap = useMemo(() => {
        const map = {};
        finalChartItems.forEach((chart, idx) => {
            const key = chart.title || `chart_${idx}`;
            map[key] = dashboardChartIntelligence?.[key] || dashboardChartIntelligence?.[`chart_${idx}`] || null;
        });
        return map;
    }, [finalChartItems, dashboardChartIntelligence]);

    const hasChartSection = finalChartItems.length > 0;

    // Normalise dashboard insight types → PowerBIInsightCards type names
    const pbiInsights = useMemo(() =>
        (insights || [])
            .filter(i => i.id !== 'executive_summary')
            .map((ins, idx) => ({
                ...ins,
                id: ins.id || `dash-${idx}`,
                type: DASHBOARD_TYPE_MAP[ins.type] || ins.type || 'summary',
                // PowerBIInsightCards reads plain_english first, then description
                plain_english: ins.description || '',
            })),
        [insights]
    );

    const handleInvestigate = useCallback((insight) => {
        const title = insight.title || '';
        const desc = insight.plain_english || insight.description || '';
        const cols = (insight.columns || []).join(', ');
        const pVal = insight.p_value != null ? `p=${Number(insight.p_value).toFixed(4)}` : null;
        const ef = insight.effect_size != null ? `effect size=${Math.abs(Number(insight.effect_size)).toFixed(3)}` : null;
        const conf = insight.confidence != null ? `${insight.confidence}% confidence` : null;
        const impact = insight.business_impact || '';
        const action = insight.recommended_action || '';

        const statsLine = [pVal, ef, conf].filter(Boolean).join(', ');
        const colsLine = cols ? `Columns involved: ${cols}.` : '';
        const statsBlock = statsLine ? `Statistical evidence: ${statsLine}.` : '';
        const impactLine = impact ? `Known business impact: ${impact}` : '';
        const actionLine = action ? `Suggested action: ${action}` : '';

        const query = [
            `I'm looking at this insight from my dataset: "${title}".`,
            desc,
            colsLine,
            statsBlock,
            impactLine,
            actionLine,
            `Please explain WHY this is happening, what is driving it in the data, how significant it is, and what I should do about it. Be specific and actionable.`,
        ].filter(Boolean).join('\n');

        window.dispatchEvent(new CustomEvent('open-chat-with-query', { detail: { query } }));
    }, []);

    // Loading state
    if (loading) {
        return <LoadingState />;
    }

    // 1. Unified Pipeline — Prioritize ongoing upload or processing
    const isUploading = activeUpload?.fileName && !activeUpload?.isComplete;
    const isProcessing = selectedDataset && selectedDataset.is_processed === false;

    if (isUploading || isProcessing) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="pipeline-processing"
                    selectedDataset={selectedDataset}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                />
            </div>
        );
    }

    // No dataset selected
    if (!selectedDataset) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
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

    // Server offline state — PRIORITIZE showing this if backend is unreachable
    if (isBackendOffline && !aiDashboardConfig) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="server-offline"
                    selectedDataset={selectedDataset}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                />
            </div>
        );
    }

    // Empty dataset (0 rows or columns)
    if (selectedDataset.row_count === 0 || selectedDataset.column_count === 0) {

        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
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

    // Generation failed and no cached config — show a full-page error with redesign CTA
    if (!aiDashboardConfig && dashboardArtifactStatus === 'failed' && !dashboardLoading && !artifactPreparing) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="generation-failed"
                    selectedDataset={selectedDataset}
                    onRegenerate={onRegenerateClick}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                />
            </div>
        );
    }

    // AI is generating — show full-page preparing state, nothing else
    if (!aiDashboardConfig && (dashboardLoading || artifactPreparing || dashboardArtifactStatus === 'pending' || dashboardArtifactStatus === 'generating')) {
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="preparing-dashboard"
                    selectedDataset={selectedDataset}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
                />
            </div>
        );
    }

    // Main dashboard render
    return (
        <div className="min-h-full px-4 py-6 sm:px-6 sm:py-8 lg:px-8 space-y-8 sm:space-y-10" style={{ backgroundColor: 'var(--bg-primary)' }}>
            {/* Header with metadata */}
            <DashboardHeader
                selectedDataset={selectedDataset}
                domainInfo={domainInfo}
                qualityMetrics={qualityMetrics}
                dashboardLoading={dashboardLoading}
                artifactPreparing={artifactPreparing}
                dashboardArtifactStatus={dashboardArtifactStatus}
                MAX_REDESIGNS={MAX_REDESIGNS}
                lastUpdatedAt={lastUpdatedAt}
                insightsSummary={insightsSummary}
            />

            {/* AI Analysis Summary — only when AI designer result is available */}
            {aiDashboardConfig?.summary && (
                <MotionDiv
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{ background: 'var(--accent-primary-light)', border: '1px solid var(--border)' }}
                    className="rounded-xl p-4 sm:p-5"
                >
                    <div className="flex items-start gap-3">
                        <div className="p-2 rounded-lg mt-0.5" style={{ background: 'var(--accent-primary-light)' }}>
                            <Sparkles className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                        </div>
                        <div>
                            <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>AI Analysis</h3>
                            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{aiDashboardConfig.summary}</p>
                        </div>
                    </div>
                </MotionDiv>
            )}

            {/* KPI Cards — AI-generated only */}
            {visibleKpis.length > 0 && (
                <div className="space-y-4">
                    <div className="mb-3 flex items-center gap-3">
                        <div className="flex items-center gap-2">
                            <div className="p-1.5 rounded-lg" style={{ background: 'var(--accent-success)', opacity: 0.1, border: '1px solid var(--accent-success)', borderColor: 'rgba(63, 185, 80, 0.15)' }}>
                                <Target className="w-3.5 h-3.5" style={{ color: 'var(--accent-success)' }} />
                            </div>
                            <span className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>Key Metrics</span>
                            <span className="px-1.5 py-0.5 rounded-md text-xs font-medium tabular-nums" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                                {visibleKpis.length}
                            </span>
                        </div>
                    </div>
                    <MotionDiv
                        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
                        initial="hidden"
                        animate="visible"
                    >
                        {visibleKpis.map((component, index) => (
                            <MotionDiv
                                key={`kpi-${index}`}
                                variants={{ hidden: { y: 20, opacity: 0 }, visible: { y: 0, opacity: 1 } }}
                            >
                                <DashboardComponent component={component} datasetData={datasetData} />
                            </MotionDiv>
                        ))}
                    </MotionDiv>
                </div>
            )}

            {hasChartSection && (
                <div className="space-y-4">
                    <div className="mt-12 mb-4 flex items-center gap-3">
                        <div className="flex items-center gap-2.5">
                            <div className="p-1.5 rounded-lg" style={{ background: 'var(--accent-primary-light)', border: '1px solid var(--border)' }}>
                                <BarChart3 className="w-3.5 h-3.5" style={{ color: 'var(--accent-primary)' }} />
                            </div>
                            <span className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>Visual Analytics</span>
                            <span className="px-1.5 py-0.5 rounded-md text-xs font-medium tabular-nums" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                                {finalChartItems.length}
                            </span>
                        </div>

                        {/* Active Filter Badge */}
                        {crossFilter && (
                            <div className="flex items-center ml-2 pl-3 border-l border-border/50">
                                <span className="text-[11px] text-muted mr-2">Filtering:</span>
                                <div className="flex items-center gap-1.5 px-2 py-0.5 bg-accent-primary/10 border border-accent-primary/20 rounded-md">
                                    <span className="text-[11px] font-bold text-header">{crossFilter}</span>
                                    <button
                                        onClick={() => setCrossFilter(null)}
                                        className="text-muted hover:text-header ml-1 transition-colors"
                                    >
                                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                    </button>
                                </div>
                            </div>
                        )}

                        <div className="h-px flex-1" style={{ background: 'linear-gradient(to right, var(--border), transparent)' }} />
                    </div>

                    <MotionDiv
                        className="grid grid-cols-1 lg:grid-cols-12 gap-4"
                        variants={{
                            hidden: {},
                            visible: { transition: { staggerChildren: 0.07 } }
                        }}
                        initial="hidden"
                        animate="visible"
                    >
                        {bentoLayout.map(({ chart, span, variant }, index) => (
                            <MotionDiv
                                key={`chart-${index}`}
                                className={SPAN_CLASSES[span] || 'col-span-12'}
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
                                    chartIntelligence={chartIntelligenceMap[chart.title] || chartIntelligenceMap[`chart_${index}`]}
                                    colorOffset={index}
                                />
                            </MotionDiv>
                        ))}
                    </MotionDiv>
                </div>
            )}

            {/* AI Insight Cards — Power BI style */}
            {(pbiInsights.length > 0 || loading) && (
                <MotionDiv initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
                    {/* Section header */}
                    <div className="mb-4 flex items-center gap-3">
                        <div className="flex items-center gap-2.5">
                            <div className="p-1.5 rounded-lg" style={{ background: 'var(--accent-primary-light)', border: '1px solid var(--border)' }}>
                                <Zap className="w-3.5 h-3.5" style={{ color: 'var(--accent-primary)' }} />
                            </div>
                            <span className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                                AI Insights
                            </span>
                            {pbiInsights.length > 0 && (
                                <span className="px-1.5 py-0.5 rounded-md text-xs font-medium tabular-nums"
                                    style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                                    {pbiInsights.length}
                                </span>
                            )}
                        </div>
                        <div className="h-px flex-1" style={{ background: 'linear-gradient(to right, var(--border), transparent)' }} />
                        <button onClick={() => navigate('/app/analysis')}
                            className="flex items-center gap-1.5 text-xs font-medium transition-colors"
                            style={{ color: 'var(--accent-primary)' }}>
                            Full Analysis <ArrowRight className="w-3 h-3" />
                        </button>
                    </div>

                    {/* Cards panel */}
                    <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                        {loading && pbiInsights.length === 0 ? (
                            <div className="flex items-center gap-3 px-5 py-4">
                                <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                                    style={{ background: 'var(--accent-primary-light)', border: '1px solid var(--accent-primary)' }}>
                                    <Sparkles className="w-4 h-4 animate-pulse" style={{ color: 'var(--accent-primary)' }} />
                                </div>
                                <div>
                                    <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Analyzing your data…</p>
                                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>Finding the most important patterns</p>
                                </div>
                            </div>
                        ) : (
                            <div className="px-4 py-3">
                                <PowerBIInsightCards
                                    insights={pbiInsights}
                                    onInvestigate={handleInvestigate}
                                />
                            </div>
                        )}
                    </div>
                </MotionDiv>
            )}

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
