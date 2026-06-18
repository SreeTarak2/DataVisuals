import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { Sparkles, Target, BarChart3, Zap, ArrowRight, RefreshCw, GripVertical, LayoutGrid, RotateCcw } from 'lucide-react';
import { Responsive, WidthProvider } from 'react-grid-layout/legacy';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import useDatasetStore from '../../store/datasetStore';
import useDashboardActionStore from '../../store/dashboardActionStore';

// Custom hooks
import { useDashboardData } from './hooks/useDashboardData';
import { useDashboardGeneration } from './hooks/useDashboardGeneration';
import { useKpiHydration } from './hooks/useKpiHydration';
import { useIntelligentKpis } from './hooks/useIntelligentKpis';
import { useDataPreview } from './hooks/useDataPreview';

// Components
import DashboardHeader from './components/DashboardHeader';
import EmptyStates from './components/EmptyStates';
import DataPreviewTable from './components/DataPreviewTable';
import RedesignLimitModal from './components/RedesignLimitModal';
import LoadingState from './components/LoadingState';
import DashboardComponent from '../../components/DashboardComponent';
import EnterpriseKpiCard from '../../components/ui/EnterpriseKpiCard';
import UploadModal from '../../components/features/datasets/UploadModal';
import PowerBIInsightCards from '../insights/components/PowerBIInsightCards';

// Utils
import { getDatasetColumns, firstNumericColumn, firstCategoricalColumn } from './utils/columnHelpers';
import { sanitizeTransformedComponents } from './utils/dashboardSanitizer';

const MotionDiv = motion.div;
const ResponsiveGridLayout = WidthProvider(Responsive);

// Dashboard API insight types → PowerBIInsightCards type names
const DASHBOARD_TYPE_MAP = { success: 'summary', info: 'summary', warning: 'anomaly', subspace: 'hidden_pattern' };

const getKpiItemKey = (kpi, index) => {
    const fallbackLabel = kpi?.title || kpi?.subtitle || 'kpi';
    return kpi?.id || kpi?.column || kpi?.key || `${fallbackLabel}-${index}`;
};
const getChartItemKey = (chart, index) => {
    const columns = Array.isArray(chart?.config?.columns) ? chart.config.columns.filter(Boolean).join('|') : '';
    const fallbackLabel = chart?.title || chart?.config?.chart_type || 'chart';
    return chart?.id || `${fallbackLabel}-${columns || index}`;
};

// ── Layout helpers ───────────────────────────────────────────────────────────

const KPI_LIMIT = 4;

// Per-section grid sizing so KPI and Chart areas behave independently
const KPI_ROW_HEIGHT = 10; // pixels per row for KPI grid — use small unit so h is granular
const CHART_ROW_HEIGHT = 60; // pixels per row for chart grid

const scoreKpiForDecisionUse = (component) => {
    const title = (component?.title || '').toLowerCase();
    let score = 0;
    if (/\b(avg|average|total|count|rate|ratio|score|revenue|sales|profit|users?|customers?|completion)\b/.test(title)) score += 4;
    if (/\b(by|impact|correlation|relationship|distribution|comparison|versus|vs|gap)\b/.test(title)) score -= 5;
    if ((component?.benchmarkText || component?.deltaPercent !== null && component?.deltaPercent !== undefined)) score += 2;
    if (component?.aiSuggestion) score += 1;
    if (title.length > 42) score -= 1;
    return score;
};

const curateKpiComponents = (components = []) => {
    if (!Array.isArray(components) || components.length === 0) return [];
    const ranked = [...components].sort((left, right) => scoreKpiForDecisionUse(right) - scoreKpiForDecisionUse(left));
    return ranked.slice(0, Math.min(KPI_LIMIT, ranked.length));
};

// Generate initial grid layout from components
const generateKpiLayout = (kpis, savedLayout) => {
    // Sort by priority before layout
    const priorityOrder = { P1: 0, P2: 1, P3: 2, P4: 3, null: 2 };
    const sorted = [...kpis].sort(
        (a, b) => (priorityOrder[a.priority] ?? 2) - (priorityOrder[b.priority] ?? 2)
    );

    const defaultLayout = sorted.map((kpi, i) => ({
        i: getKpiItemKey(kpi, i),
        x: (i % 4) * 1,
        y: Math.floor(i / 4) * 30,
        w: kpi.priority === 'P1' ? 2 : 1,
        h: 30,          // 30 × 10px = 300px — comfortable card height
        minW: 1,
        maxW: 4,
        minH: 20,       // 200px minimum
        maxH: 60,       // 600px maximum
        priority: kpi.priority || null,
    }));

    if (!savedLayout || savedLayout.length === 0) return defaultLayout;

    const savedById = new Map(savedLayout.map((item) => [item.i, item]));
    return defaultLayout.map((item) => {
        const saved = savedById.get(item.i);
        if (!saved) return item;
        return {
            ...item,
            x: typeof saved.x === 'number' ? saved.x : item.x,
            y: typeof saved.y === 'number' ? saved.y : item.y,
            w: typeof saved.w === 'number' ? saved.w : item.w,
            h: typeof saved.h === 'number' ? saved.h : item.h,
            priority: saved.priority || item.priority,
        };
    });
};

const generateChartLayout = (charts, savedLayout) => {
    // Sort by priority before layout
    const priorityOrder = { P1: 0, P2: 1, P3: 2, P4: 3, null: 2 };
    const sorted = [...charts].sort(
        (a, b) => (priorityOrder[a.priority] ?? 2) - (priorityOrder[b.priority] ?? 2)
    );

    // Greedy left-to-right row packing: fill each row before wrapping to next
    const COLS_LG = 12;
    let currentY = 0;
    let currentRowHeight = 0;
    let currentRowX = 0;
    const defaultLayout = sorted.map((chart, i) => {
        const type = chart.config?.chart_type?.toLowerCase() || '';
        const p = chart.priority || (i === 0 ? 'P1' : null);

        // determine column span based on priority first, then chart type
        let w;
        if (p === 'P1') {
            w = 12; // full width hero
        } else if (p === 'P2') {
            w = 8; // featured
        } else if (p === 'P4') {
            w = 4; // supplementary/compact
        } else {
            w = 6; // standard
            if (['line', 'line_chart', 'area', 'multi_bar', 'pivot_table'].includes(type)) w = 8;
            if (['choropleth'].includes(type)) w = 12;
            if (['pie', 'pie_chart', 'donut', 'radar', 'anomaly_feed'].includes(type)) w = 4;
        }

        // map visual variant -> approximate pixel height (keep in sync with DashboardComponent.getChartHeight)
        const variantHeightPx = (() => {
            if (p === 'P1') return 480;
            if (p === 'P2') return 420;
            if (p === 'P4') return 320;
            if (['line', 'line_chart', 'area', 'multi_bar', 'pivot_table'].includes(type)) return 420;
            if (['pie', 'pie_chart', 'donut', 'radar', 'anomaly_feed'].includes(type)) return 360;
            return 400;
        })();

        // compute number of grid rows needed to fit pixel height
        const rows = Math.max(3, Math.ceil(variantHeightPx / CHART_ROW_HEIGHT));

        // ensure width does not exceed columns
        const width = Math.min(w, COLS_LG);

        // if current item doesn't fit in current row, move to next row
        if (currentRowX + width > COLS_LG) {
            currentY += currentRowHeight;
            currentRowX = 0;
            currentRowHeight = 0;
        }

        const item = {
            i: getChartItemKey(chart, i),
            x: currentRowX,
            y: currentY,
            w: width,
            h: rows,
            priority: p,
            minW: 4,
            maxW: 12,
            minH: Math.max(3, Math.floor(200 / CHART_ROW_HEIGHT)),
            maxH: Math.max(rows, Math.ceil(800 / CHART_ROW_HEIGHT)),
        };

        // update row state
        currentRowX += width;
        currentRowHeight = Math.max(currentRowHeight, rows);

        return item;
    });

    if (!savedLayout || savedLayout.length === 0) return defaultLayout;

    const savedById = new Map(savedLayout.map((item) => [item.i, item]));
    return defaultLayout.map((item) => {
        const saved = savedById.get(item.i);
        if (!saved) return item;
        return {
            ...item,
            x: typeof saved.x === 'number' ? saved.x : item.x,
            y: typeof saved.y === 'number' ? saved.y : item.y,
            w: typeof saved.w === 'number' ? saved.w : item.w,
            h: typeof saved.h === 'number' ? saved.h : item.h,
            priority: saved.priority || item.priority,
        };
    });
};

const fitLayoutToColumns = (layout = [], cols = 1) => {
    // Recalculate grid positions for different column counts (pack left-to-right)
    let currentY = 0;
    let currentRowHeight = 0;
    let currentRowX = 0;

    return layout.map((item) => {
        const width = Math.max(1, Math.min(typeof item.w === 'number' ? item.w : 1, cols));

        // if item doesn't fit in current row, wrap to next
        if (currentRowX + width > cols) {
            currentY += currentRowHeight;
            currentRowX = 0;
            currentRowHeight = 0;
        }

        const fitted = {
            ...item,
            x: currentRowX,
            y: currentY,
            w: width,
        };

        currentRowX += width;
        currentRowHeight = Math.max(currentRowHeight, typeof item.h === 'number' ? item.h : 1);

        return fitted;
    });
};

// Priority badge removed — no P1/P2/P3 labels on cards

// Remove button component — cleaner, glass-style overlay
const RemoveButton = ({ onRemove }) => (
    <div className="absolute -top-1.5 -right-1.5 z-20 opacity-0 group-hover:opacity-100 transition-all duration-200" onClick={(e) => e.stopPropagation()}>
        <button
            onClick={onRemove}
            className="flex items-center justify-center w-5 h-5 rounded-full transition-all duration-200 hover:scale-110 shadow-sm"
            style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', color: 'rgba(255,255,255,0.7)', border: '1px solid rgba(255,255,255,0.1)' }}
            title="Remove from dashboard"
        >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
    </div>
);

const Dashboard = () => {
    const { selectedDataset, activeUpload, isBackendOffline, dashboardConfigs, setDashboardConfig, reprocessDataset, setProcessingDataset } = useDatasetStore();
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

    // Intelligent KPIs — data-science-grade, served from cache or generated on demand
    const {
        kpis: intelligentKpis,
        loading: kpisLoading,
        refresh: refreshKpis,
    } = useIntelligentKpis(selectedDataset?.id || selectedDataset?._id);

    // Handle redesign with limit check (memoized to prevent infinite loops)
    // Layout-only redesign does NOT need KPI refresh — KPIs are preserved from cache
    const onRegenerateClick = useCallback(() => {
        const success = handleRegenerate();
        if (!success) {
            setShowRedesignLimitModal(true);
        }
    }, [handleRegenerate, setShowRedesignLimitModal]);

    // Sync redesign state to dashboard action store for Header access
    const {
        setRedesigning, setRedesignAttempts, setOnRegenerate, setMaxRedesigns,
        crossFilter, setCrossFilter,
        kpiLayout, chartLayout, setKpiLayout, setChartLayout,
        saveLayoutToBackend, loadLayoutFromBackend, resetLayout,
    } = useDashboardActionStore();

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
        () => aiDashboardConfig?.components?.filter(c => ['chart', 'pivot_table', 'anomaly_feed'].includes(c?.type)) || [],
        [aiDashboardConfig]
    );

    const hydratedKpis = useMemo(() => {
        const rawKpis = aiDashboardConfig?.components?.filter((component) => component?.type === 'kpi') || [];
        return hydrateComponents(rawKpis);
    }, [aiDashboardConfig, hydrateComponents]);
    const curatedKpis = useMemo(() => curateKpiComponents(hydratedKpis), [hydratedKpis]);

    // KPI priority order:
    //   1. Intelligent KPIs (data-science-grade, from /api/datasets/{id}/kpis)
    //   2. Blueprint KPIs from AI dashboard designer (curated from aiDashboardConfig)
    // Intelligent KPIs win when ready — they pass the 3-gate business filter.
    const visibleKpis = intelligentKpis.length > 0 ? intelligentKpis : curatedKpis;
    const datasetId = selectedDataset?.id || selectedDataset?._id;

    // ─── Layout persistence state ───
    const [kpiGridLayout, setKpiGridLayout] = useState([]);
    const [chartGridLayout, setChartGridLayout] = useState([]);
    const [layoutHydrated, setLayoutHydrated] = useState(false);
    const kpiLayouts = useMemo(() => ({
        lg: kpiGridLayout,
        md: fitLayoutToColumns(kpiGridLayout, 3),
        sm: fitLayoutToColumns(kpiGridLayout, 2),
    }), [kpiGridLayout]);
    const chartLayouts = useMemo(() => ({
        lg: chartGridLayout,
        md: fitLayoutToColumns(chartGridLayout, 8),
        sm: fitLayoutToColumns(chartGridLayout, 4),
    }), [chartGridLayout]);

    // Load saved layout when dataset changes
    useEffect(() => {
        if (!datasetId) return;

        setLayoutHydrated(false);
        // Clear old dataset grid first to avoid stale positions while loading new layout.
        setKpiGridLayout([]);
        setChartGridLayout([]);
        setKpiLayout([]);
        setChartLayout([]);

        let active = true;
        loadLayoutFromBackend(datasetId).then((data) => {
            if (!active) return;
            setKpiLayout(data.kpis || []);
            setChartLayout(data.charts || []);
            setLayoutHydrated(true);
        }).catch(() => {
            if (active) setLayoutHydrated(true);
        });

        return () => {
            active = false;
        };
    }, [datasetId, loadLayoutFromBackend, setKpiLayout, setChartLayout]);

    // Generate layouts when components are ready
    useEffect(() => {
        if (!layoutHydrated) return;
        if (visibleKpis.length > 0) {
            setKpiGridLayout(generateKpiLayout(visibleKpis, kpiLayout));
        } else {
            setKpiGridLayout([]);
        }
    }, [layoutHydrated, visibleKpis, kpiLayout]);

    useEffect(() => {
        if (!layoutHydrated) return;
        if (finalChartItems.length > 0) {
            setChartGridLayout(generateChartLayout(finalChartItems, chartLayout));
        } else {
            setChartGridLayout([]);
        }
    }, [layoutHydrated, finalChartItems, chartLayout]);

    // Debounced layout save
    const saveTimeoutRef = useRef(null);
    const clearPendingLayoutSave = useCallback(() => {
        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
            saveTimeoutRef.current = null;
        }
    }, []);
    const debouncedSaveLayout = useCallback((_type, _layout) => {
        clearPendingLayoutSave();
        saveTimeoutRef.current = setTimeout(() => {
            if (!datasetId) return;
            if (_type === 'kpi') {
                saveLayoutToBackend(datasetId, { kpis: _layout });
            } else if (_type === 'chart') {
                saveLayoutToBackend(datasetId, { charts: _layout });
            }
        }, 1500);
    }, [datasetId, saveLayoutToBackend, clearPendingLayoutSave]);

    const handleKpiLayoutChange = useCallback((layout) => {
        setKpiGridLayout(layout);
        setKpiLayout(layout);
        debouncedSaveLayout('kpi', layout);
    }, [setKpiLayout, debouncedSaveLayout]);

    const handleChartLayoutChange = useCallback((layout) => {
        setChartGridLayout(layout);
        setChartLayout(layout);
        debouncedSaveLayout('chart', layout);
    }, [setChartLayout, debouncedSaveLayout]);

    const handleCompactLayout = useCallback((type) => {
        const { compactLayout } = useDashboardActionStore.getState();
        compactLayout(type);
        // Sync local grid state with store
        const updated = useDashboardActionStore.getState();
        const updatedLayout = type === 'kpi' ? (updated.kpiLayout || []) : (updated.chartLayout || []);
        if (type === 'kpi') {
            setKpiGridLayout(updatedLayout);
        } else {
            setChartGridLayout(updatedLayout);
        }
        // Persist the compacted layout
        debouncedSaveLayout(type, updatedLayout);
    }, [debouncedSaveLayout]);

    const handlePromoteComponent = useCallback((type, id) => {
        const { promoteComponent } = useDashboardActionStore.getState();
        const newPriority = promoteComponent(type, id, datasetId);
        if (newPriority) {
            const updated = useDashboardActionStore.getState();
            const updatedLayout = type === 'kpi' ? (updated.kpiLayout || []) : (updated.chartLayout || []);
            if (type === 'kpi') {
                setKpiGridLayout(updatedLayout);
            } else {
                setChartGridLayout(updatedLayout);
            }
            // Persist the re-compacted layout
            debouncedSaveLayout(type, updatedLayout);
            const priorityLabels = { P1: 'Hero', P2: 'Featured', P3: 'Standard', P4: 'Compact' };
            toast.success(`📊 Promoted to ${priorityLabels[newPriority]} priority`, {
                duration: 2500,
                style: { background: '#1e293b', color: '#e2e8f0', border: '1px solid rgba(245, 158, 11, 0.3)' },
            });
        }
    }, [datasetId, debouncedSaveLayout]);

    const handleDemoteComponent = useCallback((type, id) => {
        const { demoteComponent } = useDashboardActionStore.getState();
        const newPriority = demoteComponent(type, id, datasetId);
        if (newPriority) {
            const updated = useDashboardActionStore.getState();
            const updatedLayout = type === 'kpi' ? (updated.kpiLayout || []) : (updated.chartLayout || []);
            if (type === 'kpi') {
                setKpiGridLayout(updatedLayout);
            } else {
                setChartGridLayout(updatedLayout);
            }
            // Persist the re-compacted layout
            debouncedSaveLayout(type, updatedLayout);
            const priorityLabels = { P1: 'Hero', P2: 'Featured', P3: 'Standard', P4: 'Compact' };
            toast.success(`📉 Demoted to ${priorityLabels[newPriority]} priority`, {
                duration: 2500,
                style: { background: '#1e293b', color: '#e2e8f0', border: '1px solid rgba(59, 130, 246, 0.3)' },
            });
        }
    }, [datasetId, debouncedSaveLayout]);

    const handleRemoveGridItem = useCallback((type, id, componentData) => {
        const { removeGridItem } = useDashboardActionStore.getState();
        removeGridItem(type, id, componentData);
        const updated = useDashboardActionStore.getState();
        const updatedLayout = type === 'kpi' ? (updated.kpiLayout || []) : (updated.chartLayout || []);
        if (type === 'kpi') {
            setKpiGridLayout(updatedLayout);
        } else {
            setChartGridLayout(updatedLayout);
        }
        // Persist the layout after removal
        debouncedSaveLayout(type, updatedLayout);
        const label = componentData?.title || id;
        toast(`${label} removed.`, {
            duration: 4000,
            icon: '🗑️',
            style: { background: '#1e293b', color: '#e2e8f0', border: '1px solid rgba(239, 68, 68, 0.3)' },
        });
    }, [debouncedSaveLayout]);

    const handleResetLayout = useCallback(() => {
        clearPendingLayoutSave();
        resetLayout(datasetId);
        setKpiGridLayout([]);
        setChartGridLayout([]);
        setKpiLayout([]);
        setChartLayout([]);
        setLayoutHydrated(false);
    }, [datasetId, resetLayout, setKpiLayout, setChartLayout, clearPendingLayoutSave]);

    const mergeDashboardComponent = useCallback((component) => {
        if (!datasetId || !component) return;

        const currentConfig = dashboardConfigs?.[datasetId] || aiDashboardConfig || { components: [] };
        const components = Array.isArray(currentConfig.components) ? [...currentConfig.components] : [];
        const componentKey = component.id || component.key || component.title;
        const alreadyExists = components.some((item, index) => {
            const itemKey = item?.id || item?.key || item?.title || index;
            return componentKey && itemKey === componentKey;
        });

        if (!alreadyExists) {
            components.push(component);
            setDashboardConfig(datasetId, {
                ...currentConfig,
                components,
            });
        }
    }, [datasetId, dashboardConfigs, aiDashboardConfig, setDashboardConfig]);

    useEffect(() => () => clearPendingLayoutSave(), [clearPendingLayoutSave]);

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

    // ─── Listen for chat-driven component additions ───
    useEffect(() => {
        const handler = (event) => {
            const { type, component } = event.detail || {};
            if (!component) return;

            if (type === 'kpi') {
                // Add KPI to the grid
                setKpiGridLayout(prev => {
                    const newLayout = [...prev, {
                        i: getKpiItemKey(component, prev.length),
                        x: (prev.length % 4) * 1,
                        y: 0,
                        w: 1,
                        h: 4,
                        minW: 1,
                        maxW: 2,
                        minH: 3,
                        maxH: 6,
                    }];
                    mergeDashboardComponent({
                        ...component,
                        type: 'kpi',
                    });
                    // Add to visible KPIs by appending to intelligentKpis would require store change
                    // For now, the component is persisted to backend and will appear on next load
                    return newLayout;
                });
            } else if (type === 'chart') {
                setChartGridLayout(prev => {
                    const newLayout = [...prev, {
                        i: getChartItemKey(component, prev.length),
                        x: 0,
                        y: prev.length * 6,
                        w: component.span || 6,
                        h: 6,
                        minW: 4,
                        maxW: 12,
                        minH: 4,
                        maxH: 12,
                    }];
                    mergeDashboardComponent({
                        ...component,
                        type: 'chart',
                    });
                    return newLayout;
                });
            }
        };

        window.addEventListener('dashboard-component-added', handler);
        return () => window.removeEventListener('dashboard-component-added', handler);
    }, []);

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

    // 1. Dataset is uploading or processing — show appropriate state
    //    The full ProcessingModal overlay handles the detailed stage display.
    const isUploading = activeUpload?.fileName && !activeUpload?.isComplete;
    const isProcessing = selectedDataset && selectedDataset.is_processed === false;
    const hasProcessingFailed = isProcessing && (selectedDataset.processing_status === 'failed' || selectedDataset.processing_status === 'error');

    const handleRetryProcessing = useCallback(async () => {
        const id = selectedDataset?.id || selectedDataset?._id;
        if (!id) return;
        const result = await reprocessDataset(id);
        if (result?.success) {
            setProcessingDataset(id);
        }
    }, [selectedDataset, reprocessDataset, setProcessingDataset]);

    // Loading state
    if (loading) {
        return <LoadingState />;
    }

    if (isUploading || isProcessing) {
        if (hasProcessingFailed) {
            return (
                <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                    <EmptyStates
                        type="processing-failed"
                        selectedDataset={selectedDataset}
                        onRetryProcessing={handleRetryProcessing}
                        onNavigateToDatasets={() => navigate('/app/datasets')}
                    />
                </div>
            );
        }
        return (
            <div className="min-h-screen p-6" style={{ backgroundColor: 'var(--bg-primary)' }}>
                <EmptyStates
                    type="processing-dataset"
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
                    onConnectSource={() => navigate('/app/connectors')}
                    onNavigateToDatasets={() => navigate('/app/datasets')}
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

            {/* KPI Cards — draggable grid */}
            {(visibleKpis.length > 0 || kpisLoading) && (
                <div className="space-y-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                            <div className="p-1.5 rounded-lg" style={{ background: 'var(--accent-success)', opacity: 0.1, border: '1px solid var(--accent-success)', borderColor: 'rgba(63, 185, 80, 0.15)' }}>
                                <Target className="w-3.5 h-3.5" style={{ color: 'var(--accent-success)' }} />
                            </div>
                            <span className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>Key Metrics</span>
                            {visibleKpis.length > 0 && (
                                <span className="px-1.5 py-0.5 rounded-md text-xs font-medium tabular-nums" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                                    {visibleKpis.length}
                                </span>
                            )}
                            {kpisLoading && (
                                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Generating…</span>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => handleCompactLayout('kpi')}
                                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
                                style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)', background: 'transparent' }}
                                title="Compact KPI cards, removing empty spaces"
                            >
                                <LayoutGrid className="w-3 h-3" />
                                Compact
                            </button>
                            <button
                                onClick={handleResetLayout}
                                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
                                style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)', background: 'transparent' }}
                                title="Reset to AI default layout"
                            >
                                <RotateCcw className="w-3 h-3" />
                                Reset Layout
                            </button>
                            <button
                                onClick={refreshKpis}
                                disabled={kpisLoading}
                                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
                                style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)', background: 'transparent' }}
                                title="Refresh metric insights"
                            >
                                <RefreshCw className={`w-3 h-3 ${kpisLoading ? 'animate-spin' : ''}`} />
                                Refresh
                            </button>
                        </div>
                    </div>

                    {kpisLoading && visibleKpis.length === 0 ? (
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6">
                            {[0, 1, 2, 3].map((i) => (
                                <MotionDiv key={`kpi-skeleton-${i}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}>
                                    <EnterpriseKpiCard title="" value={0} state="loading" animationDelay={i * 0.08} />
                                </MotionDiv>
                            ))}
                        </div>
                    ) : (
                        <ResponsiveGridLayout
                            className="layout kpi-grid-layout"
                            layouts={kpiLayouts}
                            breakpoints={{ lg: 1200, md: 768, sm: 480 }}
                            cols={{ lg: 4, md: 3, sm: 2 }}
                            rowHeight={KPI_ROW_HEIGHT}
                            margin={[16, 16]}
                            containerPadding={[0, 0]}
                            compactType="vertical"
                            measureBeforeMount={false}
                            useCSSTransforms={true}
                            autoSize={true}
                            preventCollision={false}
                            onLayoutChange={handleKpiLayoutChange}
                            draggableHandle=".kpi-drag-handle"
                            resizeHandles={[]}
                            isDraggable={!kpisLoading}
                            isResizable={false}
                        >
                            {visibleKpis.map((component, index) => {
                                const key = getKpiItemKey(component, index);
                                return (
                                    <div key={key} className="group relative" style={{ overflow: 'visible' }}>
                                        <DashboardComponent component={component} datasetData={datasetData} variant="standard" />
                                        {/* Drag handle — rendered after card so it overlays the top-right corner */}
                                        <div
                                            className="kpi-drag-handle absolute top-3 right-10 z-20 flex items-center gap-1 opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity cursor-grab active:cursor-grabbing rounded-md px-1 py-0.5"
                                            style={{ color: 'var(--text-muted)', background: 'var(--bg-elevated)' }}
                                            title="Drag to reorder"
                                        >
                                            <GripVertical className="w-3 h-3" />
                                        </div>
                                        <RemoveButton onRemove={() => handleRemoveGridItem('kpi', key, component)} />
                                    </div>
                                );
                            })}
                        </ResponsiveGridLayout>
                    )}
                </div>
            )}

            {/* Chart Grid — draggable */}
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

                        {crossFilter && (
                            <div className="flex items-center ml-2 pl-3 border-l border-border/50">
                                <span className="text-[11px] text-muted mr-2">Filtering:</span>
                                <div className="flex items-center gap-1.5 px-2 py-0.5 bg-accent-primary/10 border border-accent-primary/20 rounded-md">
                                    <span className="text-[11px] font-bold text-header">{crossFilter}</span>
                                    <button onClick={() => setCrossFilter(null)} className="text-muted hover:text-header ml-1 transition-colors">
                                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                    </button>
                                </div>
                            </div>
                        )}

                        <button
                            onClick={() => handleCompactLayout('chart')}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
                            style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)', background: 'transparent' }}
                            title="Compact charts, removing empty spaces"
                        >
                            <LayoutGrid className="w-3.5 h-3.5" />
                            Compact
                        </button>

                        <div className="h-px flex-1" style={{ background: 'linear-gradient(to right, var(--border), transparent)' }} />
                    </div>

                    <ResponsiveGridLayout
                        className="layout chart-layout"
                        layouts={chartLayouts}
                        breakpoints={{ lg: 1200, md: 768, sm: 480 }}
                        cols={{ lg: 12, md: 8, sm: 4 }}
                        rowHeight={CHART_ROW_HEIGHT}
                        margin={[12, 16]}
                        containerPadding={[0, 0]}
                        // Chart grid: independent compaction and smoother mount
                        compactType="vertical"
                        measureBeforeMount={true}
                        useCSSTransforms={true}
                        autoSize={true}
                        preventCollision={false}
                        onLayoutChange={handleChartLayoutChange}
                        draggableHandle=".chart-drag-handle"
                        resizeHandles={['se', 'sw', 'ne', 'nw']}
                        isDraggable={true}
                        isResizable={true}
                    >
                        {finalChartItems.map((chart, index) => {
                            const key = getChartItemKey(chart, index);
                            const type = chart.config?.chart_type?.toLowerCase() || '';
                            const layoutItem = chartGridLayout.find((item) => item.i === key);
                            const priority = layoutItem?.priority || null;

                            const variant = priority === 'P1' ? 'hero'
                                : priority === 'P2' ? 'featured'
                                : priority === 'P4' ? 'compact'
                                : ['line', 'line_chart', 'area', 'multi_bar', 'pivot_table'].includes(type) ? 'featured'
                                : ['pie', 'pie_chart', 'donut', 'radar', 'anomaly_feed'].includes(type) ? 'compact'
                                : 'standard';

                            return (
                                <div key={key} className="group relative">
                                    <div className="chart-drag-handle absolute top-2 left-2 z-10 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing px-2 py-1 rounded" style={{ color: 'var(--text-secondary)', background: 'var(--bg-card)' }}>
                                        <GripVertical className="w-3.5 h-3.5" />
                                    </div>

                                    <RemoveButton onRemove={() => handleRemoveGridItem('chart', key, chart)} />
                                    <DashboardComponent
                                        component={chart}
                                        datasetData={datasetData}
                                        variant={variant}
                                        chartIntelligence={chartIntelligenceMap[chart.title] || chartIntelligenceMap[`chart_${index}`]}
                                        colorOffset={index}
                                    />
                                </div>
                            );
                        })}
                    </ResponsiveGridLayout>
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
