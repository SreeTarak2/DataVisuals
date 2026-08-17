/**
 * DataBriefing
 *
 * Professional High-Precision Data Studio Workbench.
 * Inspired by modern enterprise data platforms (Databricks, Snowflake, PostHog, Linear, Hex.tech).
 * Features a 2-column split canvas layout, high-density Data Dictionary Table with sample values,
 * tactile 1-click Focus Tags, automated column cleaning manifest, and floating precision command dock.
 */
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { datasetAPI, aiAPI } from '../services/api';
import { normalizeDashboardConfig } from '../utils/dashboardUtils';
import useDatasetStore from '../store/datasetStore';

// ── Icons ──────────────────────────────────────────────────────────────────
import {
  Database,
  Sparkles,
  Hash,
  Tag,
  Clock,
  EyeOff,
  Wrench,
  Check,
  XCircle,
  AlertCircle,
  ArrowRight,
  Search,
  Filter,
  Layers,
  TrendingUp,
  Activity,
  BarChart3,
  CheckCircle2,
  Loader2,
  RotateCcw,
  Sliders,
  ChevronDown,
  ChevronUp,
  Info,
  SlidersHorizontal,
  Table,
  CheckSquare,
  Square,
  Zap,
} from 'lucide-react';

// ── Role Color Systems ────────────────────────────────────────────────────
const ROLE_CONFIGS = {
  measures: {
    label: 'Measure',
    icon: Hash,
    badgeBg: 'bg-emerald-500/10',
    badgeText: 'text-emerald-400',
    badgeBorder: 'border-emerald-500/20',
    rowBgActive: 'bg-emerald-500/[0.02]',
  },
  dimensions: {
    label: 'Dimension',
    icon: Tag,
    badgeBg: 'bg-indigo-500/10',
    badgeText: 'text-indigo-400',
    badgeBorder: 'border-indigo-500/20',
    rowBgActive: 'bg-indigo-500/[0.02]',
  },
  time: {
    label: 'Time',
    icon: Clock,
    badgeBg: 'bg-amber-500/10',
    badgeText: 'text-amber-400',
    badgeBorder: 'border-amber-500/20',
    rowBgActive: 'bg-amber-500/[0.02]',
  },
  identifiers: {
    label: 'Identifier',
    icon: EyeOff,
    badgeBg: 'bg-zinc-800',
    badgeText: 'text-zinc-400',
    badgeBorder: 'border-zinc-700',
    rowBgActive: 'bg-zinc-900/30',
  },
};

// ── Focus Drivers / One-Click Presets ──────────────────────────────────────
const FOCUS_TAGS = [
  {
    id: 'drivers',
    label: 'Revenue & Sales Drivers',
    icon: TrendingUp,
    prompt: 'Identify top revenue drivers, key performance metrics, and sales volume trends over time.',
  },
  {
    id: 'segmentation',
    label: 'Cohorts & Behavior',
    icon: Activity,
    prompt: 'Analyze customer purchase frequency, cohort breakdowns, and demographic distribution.',
  },
  {
    id: 'anomalies',
    label: 'Outliers & Variance',
    icon: AlertCircle,
    prompt: 'Detect unusual data spikes, numerical variance, and statistical outliers across metrics.',
  },
  {
    id: 'basket',
    label: 'Category Product Mix',
    icon: BarChart3,
    prompt: 'Compare category revenue share, customer review ratings, and discount impact on sales.',
  },
];

// ── Classification & Helper Functions ─────────────────────────────────────

function classifyColumns(metadata) {
  const colmeta = metadata?.column_metadata || [];
  const domain = metadata?.domain_intelligence || {};
  const profile = metadata?.data_profile || {};
  const idSet = new Set(profile?.id_columns || []);
  const cardinality = profile?.cardinality || {};

  const measures = domain?.measures || [];
  const dimensions = domain?.dimensions || [];
  const timeCols = domain?.time_columns || [];

  const colMap = {};
  colmeta.forEach((c) => {
    colMap[c.name] = c;
  });

  const knownColumns = new Set([...measures, ...dimensions, ...timeCols, ...idSet]);
  const remaining = colmeta.filter((c) => !knownColumns.has(c.name));

  const heuristicMeasures = [];
  const heuristicDimensions = [];

  remaining.forEach((c) => {
    const name = c.name || '';
    const type = (c.type || '').toLowerCase();
    const unique = cardinality[name]?.unique_count ?? c.unique_count ?? 0;

    if (idSet.has(name)) return;

    if (
      type.includes('float') ||
      type.includes('int') ||
      type.includes('numeric') ||
      type.includes('number') ||
      type.includes('double')
    ) {
      if (unique > 0 && unique < 20 && !name.toLowerCase().includes('id')) {
        heuristicDimensions.push(c);
      } else {
        heuristicMeasures.push(c);
      }
    } else {
      heuristicDimensions.push(c);
    }
  });

  const measureCols = [
    ...measures.map((n) => colMap[n]).filter(Boolean),
    ...heuristicMeasures,
  ];
  const dimensionCols = [
    ...dimensions.map((n) => colMap[n]).filter(Boolean),
    ...heuristicDimensions,
  ];
  const timeColsResolved = timeCols.map((n) => colMap[n]).filter(Boolean);
  const identifierCols = [...idSet].map((n) => colMap[n]).filter(Boolean);

  const seen = new Set();
  const unique = (arr) =>
    arr.filter((c) => {
      if (!c || seen.has(c.name)) return false;
      seen.add(c.name);
      return true;
    });

  return [
    {
      id: 'measures',
      label: 'Measures',
      role: ROLE_CONFIGS.measures,
      columns: unique(measureCols),
    },
    {
      id: 'dimensions',
      label: 'Dimensions',
      role: ROLE_CONFIGS.dimensions,
      columns: unique(dimensionCols),
    },
    {
      id: 'time',
      label: 'Time Columns',
      role: ROLE_CONFIGS.time,
      columns: unique(timeColsResolved),
    },
    {
      id: 'identifiers',
      label: 'Identifiers',
      role: ROLE_CONFIGS.identifiers,
      columns: unique(identifierCols),
    },
  ];
}

function getCardinalityHint(col, cardinality) {
  const info = cardinality?.[col?.name] || {};
  const level = info?.cardinality_level || '';
  const unique = info?.unique_count ?? col?.unique_count ?? 0;

  if (level === 'low') return { label: `${unique.toLocaleString()} unique`, type: 'good' };
  if (level === 'medium') return { label: `${unique.toLocaleString()} unique`, type: 'ok' };
  if (level === 'high' || level === 'very_high')
    return { label: `${unique.toLocaleString()} unique (High)`, type: 'warn' };
  if (unique > 100) return { label: `${unique.toLocaleString()} unique (High)`, type: 'warn' };
  if (unique > 0) return { label: `${unique.toLocaleString()} unique`, type: 'good' };
  return { label: 'Single value', type: 'good' };
}

function getSampleValuesStr(col, dataset) {
  const profile = dataset?.metadata?.data_profile || {};
  const samples =
    col?.sample_values ||
    col?.samples ||
    profile?.samples?.[col?.name] ||
    profile?.sample_values?.[col?.name];

  if (Array.isArray(samples) && samples.length > 0) {
    return samples.slice(0, 3).map((v) => (typeof v === 'string' ? `"${v}"` : String(v))).join(', ');
  }
  return null;
}

function matchColumnsFromIntent(intent, columnGroups) {
  if (!intent || !intent.trim()) return new Set();
  const intentLower = intent.toLowerCase();
  const intentWords = intentLower
    .split(/[\s,;:.!?()]+/)
    .filter((w) => w.length > 1);
  const matched = new Set();

  columnGroups.forEach((group) => {
    group.columns.forEach((col) => {
      const colName = col.name.toLowerCase();
      const colParts = colName.split(/[_\-\s]+/);

      for (const word of intentWords) {
        if (colName === word || colName.includes(word) || colParts.some((p) => p === word)) {
          matched.add(col.name);
          break;
        }
        const wordParts = word.split(/[-_]+/);
        if (wordParts.length > 1 && wordParts.some((wp) => colParts.includes(wp))) {
          matched.add(col.name);
          break;
        }
      }
    });
  });

  return matched;
}

// ── Cleaning Manifest helpers ─────────────────────────────────────────────
// Mirrors the backend's entry_state() in services/cleaning/mutation_engine.py
// so the UI never lies about what the engine did to the data.

function deriveManifestState(action) {
  if (action.state) return action.state;
  const approved = action.approved;
  const isProposal = action.action_type === 'merge' || action.action_type === 'remove';
  if (approved === true) return isProposal ? 'applied' : 'confirmed';
  if (approved === false) return isProposal ? 'rejected' : 'reverted';
  return isProposal ? 'proposed' : 'applied_silently';
}

const MANIFEST_STATE_CONFIG = {
  applied_silently: { label: 'Applied', cls: 'text-zinc-400 bg-zinc-800/70 border-zinc-700' },
  proposed: { label: 'Pending', cls: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
  confirmed: { label: 'Confirmed', cls: 'text-teal-400 bg-teal-500/10 border-teal-500/30' },
  applied: { label: 'Applied', cls: 'text-teal-400 bg-teal-500/10 border-teal-500/30' },
  rejected: { label: 'Rejected', cls: 'text-red-400 bg-red-500/10 border-red-500/30' },
  reverted: { label: 'Reverted', cls: 'text-blue-400 bg-blue-500/10 border-blue-500/30' },
};

function describeManifestAction(action) {
  const cols = action.target_columns || [];
  if (action.action_type === 'remove') {
    return `Remove column${cols.length > 1 ? 's' : ''}: ${cols.join(', ') || '?'}`;
  }
  if (action.action_type === 'merge') {
    return `Merge duplicate columns: ${cols.join(', ') || '?'}`;
  }
  if (action.normalized_name && action.original_name) {
    return `${action.original_name} → ${action.normalized_name}`;
  }
  return action.reasoning || 'Cleaning action';
}

// ── Main DataBriefing Component ───────────────────────────────────────────

const DataBriefing = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { fetchDatasets, setSelectedDataset, setDashboardConfig } = useDatasetStore();

  // Core State
  const [dataset, setDataset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [autoSelect, setAutoSelect] = useState(true);
  const [userIntent, setUserIntent] = useState('');
  const [debouncedIntent, setDebouncedIntent] = useState('');
  const [generating, setGenerating] = useState(false);

  // Workbench Controls
  const [searchTerm, setSearchTerm] = useState('');
  const [activeCategoryTab, setActiveCategoryTab] = useState('all');

  // Cleaning Manifest State
  const [cleaningExpanded, setCleaningExpanded] = useState(false);
  const [cleaningApproving, setCleaningApproving] = useState(false);
  const [mutationNote, setMutationNote] = useState(null);

  // LLM State
  const [llmSuggestedColumns, setLlmSuggestedColumns] = useState(null);
  const [llmSuggesting, setLlmSuggesting] = useState(false);
  const llmSequenceRef = useRef(0);

  // Debounce intent input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedIntent(userIntent), 400);
    return () => clearTimeout(timer);
  }, [userIntent]);

  // LLM Column Suggestion
  useEffect(() => {
    if (!autoSelect || !debouncedIntent.trim()) {
      setLlmSuggestedColumns(null);
      return;
    }

    const mySeq = llmSequenceRef.current + 1;
    llmSequenceRef.current = mySeq;

    const fetchSuggestions = async () => {
      setLlmSuggesting(true);
      try {
        const res = await aiAPI.suggestColumns(id, debouncedIntent, 20);
        if (llmSequenceRef.current !== mySeq) return;
        const cols = res.data?.suggested_columns;
        if (Array.isArray(cols) && cols.length > 0) {
          setLlmSuggestedColumns(new Set(cols));
        } else {
          setLlmSuggestedColumns(null);
        }
      } catch {
        if (llmSequenceRef.current !== mySeq) return;
        setLlmSuggestedColumns(null);
      } finally {
        if (llmSequenceRef.current === mySeq) {
          setLlmSuggesting(false);
        }
      }
    };

    fetchSuggestions();
  }, [autoSelect, debouncedIntent, id]);

  // Classified Groups
  const columnGroups = useMemo(
    () => (dataset?.metadata ? classifyColumns(dataset.metadata) : []),
    [dataset]
  );

  const rawManifest = useMemo(() => {
    const raw = dataset?.cleaning_manifest || dataset?.metadata?.cleaning_manifest || [];
    return Array.isArray(raw) ? raw : [];
  }, [dataset]);

  const hasCleaningActions = rawManifest.length > 0;
  const pendingCleaning = rawManifest.filter((a) => a.approved === null).length;

  // Auto-Select Resolution
  const autoSelected = useMemo(() => {
    if (!autoSelect) return new Set();
    const cols = new Set();
    const cardinality = dataset?.metadata?.data_profile?.cardinality || {};

    if (llmSuggestedColumns && debouncedIntent.trim()) {
      llmSuggestedColumns.forEach((colName) => cols.add(colName));
    } else if (debouncedIntent.trim()) {
      const intentMatched = matchColumnsFromIntent(debouncedIntent, columnGroups);
      intentMatched.forEach((c) => cols.add(c));
    }

    columnGroups.forEach((group) => {
      group.columns.forEach((c) => {
        if (cols.has(c.name)) return;
        if (group.id === 'identifiers') return;
        if (group.id === 'measures') cols.add(c.name);
        if (group.id === 'time') cols.add(c.name);
        if (group.id === 'dimensions') {
          const info = cardinality[c.name] || {};
          const unique = info?.unique_count ?? c.unique_count ?? 0;
          if (unique <= 50) cols.add(c.name);
        }
      });
    });

    return cols;
  }, [autoSelect, columnGroups, dataset, debouncedIntent, llmSuggestedColumns]);

  // Sync Auto-Selected
  useEffect(() => {
    if (autoSelect) {
      setSelected(autoSelected);
    }
  }, [autoSelect, autoSelected]);

  // Derived Counts
  const totalColumns = useMemo(
    () => columnGroups.reduce((sum, g) => sum + g.columns.length, 0),
    [columnGroups]
  );
  const selectedCount = selected.size;

  const measuresGroup = useMemo(() => columnGroups.find((g) => g.id === 'measures'), [columnGroups]);
  const dimensionsGroup = useMemo(() => columnGroups.find((g) => g.id === 'dimensions'), [columnGroups]);
  const timeGroup = useMemo(() => columnGroups.find((g) => g.id === 'time'), [columnGroups]);
  const identifiersGroup = useMemo(() => columnGroups.find((g) => g.id === 'identifiers'), [columnGroups]);

  const selectedMeasures = useMemo(
    () => (measuresGroup?.columns || []).filter((c) => selected.has(c.name)).length,
    [measuresGroup, selected]
  );
  const selectedDimensions = useMemo(
    () => (dimensionsGroup?.columns || []).filter((c) => selected.has(c.name)).length,
    [dimensionsGroup, selected]
  );

  // Fetch Dataset
  useEffect(() => {
    if (!id) {
      setError('No dataset ID provided');
      setLoading(false);
      return;
    }

    const load = async () => {
      try {
        setLoading(true);
        const datasets = await fetchDatasets();
        const found = datasets.find((d) => d.id === id || d._id === id);

        if (!found) {
          const res = await datasetAPI.getDataset(id);
          const ds = res.data;
          if (!ds) throw new Error('Dataset not found');
          setDataset(ds);
          setSelectedDataset(ds);
        } else {
          setDataset(found);
          setSelectedDataset(found);
        }
      } catch (err) {
        console.error('Failed to load dataset:', err);
        setError(err.message || 'Failed to load dataset');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [id]);

  // ── Cleaning Handlers (execution engine) ──────────────────────────────
  const refreshDatasetAfterMutation = useCallback(async () => {
    try {
      const res = await datasetAPI.getDataset(id);
      if (res.data) setDataset(res.data);
    } catch (err) {
      console.warn('Failed to refresh dataset after cleaning action', err);
    }
  }, [id]);

  const handleApproveCleaning = useCallback(async (actionIndex, approved) => {
    setCleaningApproving(true);
    setMutationNote(null);
    try {
      const res = await datasetAPI.approveCleaningAction(id, actionIndex, approved);
      if (res.data?.actions) {
        setDataset((prev) => (prev ? { ...prev, cleaning_manifest: res.data.actions } : prev));
      }
      if (res.data?.mutation_status === 'running') {
        setMutationNote('Applying the change to your dataset in the background…');
        setTimeout(refreshDatasetAfterMutation, 3000);
      } else if (res.data?.warnings?.length) {
        setMutationNote(res.data.warnings.join(' '));
      }
      toast.success(approved ? 'Cleaning action applied' : 'Cleaning action updated');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(detail || 'Failed to update cleaning action');
      if (detail) setMutationNote(detail);
    } finally {
      setCleaningApproving(false);
    }
  }, [id, refreshDatasetAfterMutation]);

  const handleApproveAllCleaning = useCallback(async (approved) => {
    setCleaningApproving(true);
    setMutationNote(null);
    try {
      const res = await datasetAPI.applyAllCleaning(id, approved);
      if (res.data?.actions) {
        setDataset((prev) => (prev ? { ...prev, cleaning_manifest: res.data.actions } : prev));
      }
      if (res.data?.mutation_status === 'running') {
        setMutationNote('Applying changes to your dataset in the background…');
        setTimeout(refreshDatasetAfterMutation, 3000);
      } else if (res.data?.warnings?.length) {
        setMutationNote(res.data.warnings.join(' '));
      }
      toast.success(approved ? 'All pending actions applied' : 'All pending actions updated');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(detail || 'Failed to apply cleaning actions');
      if (detail) setMutationNote(detail);
    } finally {
      setCleaningApproving(false);
    }
  }, [id, refreshDatasetAfterMutation]);

  // Toggle Column Selection
  const handleToggleColumn = useCallback((colName) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(colName)) next.delete(colName);
      else next.add(colName);
      setAutoSelect(false);
      return next;
    });
  }, []);

  const handleSelectAllInView = useCallback((colsToToggle, shouldSelect) => {
    setSelected((prev) => {
      const next = new Set(prev);
      colsToToggle.forEach((col) => {
        if (shouldSelect) next.add(col.name);
        else next.delete(col.name);
      });
      setAutoSelect(false);
      return next;
    });
  }, []);

  const handleGenerate = useCallback(async () => {
    if (selectedCount === 0) return;

    try {
      setGenerating(true);
      const response = await aiAPI.designDashboardWithBriefing(id, {
        selectedColumns: Array.from(selected),
        userIntent: userIntent.trim() || undefined,
        forceRegenerate: true,
      });

      const config = response.data;
      if (config.dashboard_blueprint) {
        const normalized = normalizeDashboardConfig({
          components: config.dashboard_blueprint.components || [],
          layout_grid: config.dashboard_blueprint.layout_grid || 'repeat(4, 1fr)',
          design_pattern: config.design_pattern,
          pattern_name: config.pattern_name,
          reasoning: config.reasoning,
        });
        setDashboardConfig(id, normalized);
      }

      navigate('/app/dashboard');
    } catch (err) {
      console.error('Failed to generate dashboard:', err);
      toast.error('Failed to generate dashboard. Please try again.');
    } finally {
      setGenerating(false);
    }
  }, [id, selected, userIntent, selectedCount, navigate, setDashboardConfig]);

  // Validation
  const hasMeasure = selectedMeasures > 0;
  const hasGroupBy = selectedDimensions > 0 || (timeGroup?.columns || []).some((c) => selected.has(c.name));
  const canGenerate = selectedCount >= 2 && hasMeasure && hasGroupBy;

  // Flattened & Filtered List of Columns
  const filteredColumnsList = useMemo(() => {
    const list = [];
    columnGroups.forEach((group) => {
      if (activeCategoryTab !== 'all' && group.id !== activeCategoryTab) return;

      group.columns.forEach((col) => {
        if (searchTerm.trim()) {
          const query = searchTerm.toLowerCase();
          const sampleStr = getSampleValuesStr(col, dataset) || '';
          const matchName = col.name.toLowerCase().includes(query);
          const matchType = (col.type || '').toLowerCase().includes(query);
          const matchSample = sampleStr.toLowerCase().includes(query);
          if (!matchName && !matchType && !matchSample) return;
        }
        list.push({ ...col, groupId: group.id, role: group.role });
      });
    });
    return list;
  }, [columnGroups, activeCategoryTab, searchTerm, dataset]);

  // ── Loading Skeleton ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <main className="w-full min-h-screen bg-[#0D0E12] text-zinc-100 p-6 md:p-10 font-sans">
        <div className="max-w-[1600px] mx-auto space-y-6 animate-pulse">
          <div className="h-10 w-1/4 bg-zinc-800/50 rounded-lg" />
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-4 h-96 bg-zinc-900/40 rounded-xl border border-zinc-800" />
            <div className="lg:col-span-8 h-[600px] bg-zinc-900/40 rounded-xl border border-zinc-800" />
          </div>
        </div>
      </main>
    );
  }

  // ── Error State ───────────────────────────────────────────────────────────
  if (error) {
    return (
      <main className="w-full min-h-screen bg-[#0D0E12] flex items-center justify-center p-6 text-zinc-100 font-sans">
        <div className="text-center max-w-md space-y-4 bg-[#141620] p-8 rounded-xl border border-zinc-800 shadow-2xl">
          <div className="w-12 h-12 bg-red-500/10 border border-red-500/20 text-red-400 rounded-full flex items-center justify-center mx-auto">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h2 className="text-base font-bold">Failed to Load Dataset</h2>
          <p className="text-xs text-zinc-400">{error}</p>
          <button
            onClick={() => navigate('/app/workspace')}
            className="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-xs font-semibold transition-all"
          >
            Back to Datasets
          </button>
        </div>
      </main>
    );
  }

  const domainName = dataset?.metadata?.domain_intelligence?.domain || 'General Analysis';

  return (
    <main className="w-full min-h-screen bg-[#0D0E12] text-zinc-100 font-sans selection:bg-orange-500/30">
      
      {/* ═══════ TOP STUDIO NAVIGATION BAR ═══════ */}
      <header className="border-b border-zinc-800/80 bg-[#12141C] px-6 py-3.5 sticky top-0 z-40">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between gap-4">
          
          {/* Breadcrumb & Specs */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-400 flex items-center justify-center flex-shrink-0">
              <Database className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-zinc-400 tracking-tight truncate">
                  Workspace / Datasets /
                </span>
                <span className="px-2 py-0.2 rounded text-[10px] font-mono font-semibold uppercase bg-zinc-800 text-orange-400 border border-zinc-700">
                  {domainName}
                </span>
              </div>
              <h1 className="text-sm font-bold text-white tracking-tight truncate">
                {dataset?.name || 'Untitled Dataset'}
              </h1>
            </div>
          </div>

          {/* Quick Metrics Bar & Actions */}
          <div className="flex items-center gap-4 flex-shrink-0">
            <div className="hidden md:flex items-center gap-3 text-xs text-zinc-400 bg-zinc-900/60 px-3 py-1.5 rounded-lg border border-zinc-800 font-mono">
              <span>{dataset?.row_count ? dataset.row_count.toLocaleString() : '3,900'} rows</span>
              <span className="text-zinc-600">•</span>
              <span>{totalColumns} columns</span>
              <span className="text-zinc-600">•</span>
              <span className="text-emerald-400 font-semibold">100% Quality</span>
            </div>

            <button
              onClick={() => navigate('/app/dashboard')}
              className="text-xs font-semibold text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Skip to Dashboard
            </button>
            
            <button
              onClick={handleGenerate}
              disabled={!canGenerate || generating}
              className="px-4 py-2 rounded-lg text-xs font-bold bg-orange-500 hover:bg-orange-600 disabled:opacity-40 text-white shadow-md flex items-center gap-2 transition-all cursor-pointer"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Generate Dashboard ({selectedCount})
            </button>
          </div>

        </div>
      </header>

      {/* ═══════ 2-COLUMN STUDIO WORKSPACE ═══════ */}
      <div className="max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 pb-28">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* ── LEFT PANE: COMMAND & INTENT STUDIO (4 COLS) ── */}
          <div className="lg:col-span-4 space-y-5">
            
            {/* AI Intent & Focus Controls Card */}
            <div className="bg-[#12141C] border border-zinc-800/80 rounded-xl p-5 space-y-4 shadow-lg">
              
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-orange-400" />
                  <h2 className="text-xs font-bold text-white uppercase tracking-wider">
                    Analysis Focus & Intent
                  </h2>
                </div>
                {debouncedIntent.trim() && (
                  <span className="text-[10px] font-mono text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded border border-orange-500/20">
                    {llmSuggesting ? 'Matching...' : 'Active'}
                  </span>
                )}
              </div>

              {/* Natural Language Prompt Area */}
              <div className="relative">
                <textarea
                  value={userIntent}
                  onChange={(e) => setUserIntent(e.target.value)}
                  placeholder="Describe your target question — e.g. 'Compare purchase amount trends across categories, age groups, and review ratings'"
                  className="w-full h-28 p-3 text-xs rounded-lg bg-[#0B0C10] border border-zinc-800 text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-orange-500/60 transition-all resize-none font-sans leading-relaxed"
                />
                <div className="flex items-center justify-between mt-1.5 text-[10px] text-zinc-500 font-mono">
                  <span>Enter target intent</span>
                  {userIntent && (
                    <button
                      onClick={() => setUserIntent('')}
                      className="hover:text-zinc-300 transition-colors"
                    >
                      Clear prompt
                    </button>
                  )}
                </div>
              </div>

              {/* One-Click Focus Tags */}
              <div className="space-y-2 pt-1">
                <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                  Quick Focus Drivers
                </span>
                <div className="grid grid-cols-1 gap-1.5">
                  {FOCUS_TAGS.map((tag) => {
                    const TagIcon = tag.icon;
                    const isSelected = userIntent === tag.prompt;
                    return (
                      <button
                        key={tag.id}
                        onClick={() => setUserIntent(isSelected ? '' : tag.prompt)}
                        className={`w-full flex items-center justify-between p-2.5 rounded-lg border text-left transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-orange-500/10 border-orange-500/40 text-orange-400 font-semibold'
                            : 'bg-[#0B0C10]/60 border-zinc-800/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <TagIcon className={`w-3.5 h-3.5 flex-shrink-0 ${isSelected ? 'text-orange-400' : 'text-zinc-500'}`} />
                          <span className="text-xs truncate">{tag.label}</span>
                        </div>
                        <span className="text-[10px] font-mono opacity-50 flex-shrink-0">
                          {isSelected ? '✓ Selected' : 'Select'}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Column Cleaning Manifest (Compact Accordion) */}
            {hasCleaningActions && (
              <div className="bg-[#12141C] border border-zinc-800/80 rounded-xl overflow-hidden shadow-lg">
                <button
                  onClick={() => setCleaningExpanded(!cleaningExpanded)}
                  className="w-full p-4 flex items-center justify-between hover:bg-zinc-900/40 transition-colors text-left"
                >
                  <div className="flex items-center gap-2.5">
                    <Wrench className="w-4 h-4 text-teal-400" />
                    <div>
                      <span className="text-xs font-bold text-white block">
                        Schema Cleaning Manifest
                      </span>
                      <span className="text-[10px] text-zinc-400">
                        {rawManifest.length} transformations · {pendingCleaning} pending
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {pendingCleaning > 0 && !cleaningApproving && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleApproveAllCleaning(true);
                          }}
                          className="px-2 py-1 rounded text-[10px] font-semibold bg-teal-500/10 text-teal-400 border border-teal-500/30 hover:bg-teal-500/20 transition-all"
                        >
                          Accept All
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleApproveAllCleaning(false);
                          }}
                          className="px-2 py-1 rounded text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 transition-all"
                        >
                          Reject All
                        </button>
                      </>
                    )}
                    {cleaningApproving ? (
                      <Loader2 className="w-3.5 h-3.5 text-teal-400 animate-spin" />
                    ) : cleaningExpanded ? (
                      <ChevronUp className="w-4 h-4 text-zinc-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-zinc-500" />
                    )}
                  </div>
                </button>

                {mutationNote && (
                  <div className="border-t border-zinc-800/80 px-4 py-2 text-[10px] text-amber-400 bg-amber-500/5 font-mono">
                    {mutationNote}
                  </div>
                )}

                {cleaningExpanded && (
                  <div className="border-t border-zinc-800/80 p-3 space-y-2 bg-[#0B0C10]/60 max-h-72 overflow-y-auto font-mono text-[11px]">
                    {rawManifest.map((action, idx) => {
                      const state = deriveManifestState(action);
                      const cfg = MANIFEST_STATE_CONFIG[state] || MANIFEST_STATE_CONFIG.applied_silently;
                      const isProposal = action.action_type === 'merge' || action.action_type === 'remove';
                      // Structural fixers (header shift / TOTAL row drop) applied
                      // silently at ingest — not individually revertable.
                      const isStructural = action.action_type === 'shift_header' || action.action_type === 'drop_row';
                      const description = describeManifestAction(action);
                      return (
                        <div key={idx} className="p-2 rounded bg-zinc-900/60 border border-zinc-800/60">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-zinc-300 truncate min-w-0" title={description}>
                              {description}
                            </span>
                            <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded border font-bold whitespace-nowrap ${cfg.cls}`}>
                              {cfg.label}
                            </span>
                          </div>
                          {action.reasoning && (
                            <p className="mt-1 text-[10px] text-zinc-500 leading-snug">
                              {action.reasoning}
                            </p>
                          )}
                          {!isProposal && action.applied_steps?.length > 0 && (
                            <p className="mt-1 text-[9px] text-zinc-600">
                              rules: {action.applied_steps.join(', ')}
                            </p>
                          )}
                          <div className="mt-1.5 flex items-center gap-1.5">
                            {isProposal && state === 'proposed' && (
                              <>
                                <button
                                  onClick={() => handleApproveCleaning(idx, true)}
                                  disabled={cleaningApproving}
                                  className="px-2 py-0.5 rounded text-[10px] font-semibold bg-teal-500/10 text-teal-400 border border-teal-500/30 hover:bg-teal-500/20 transition-all disabled:opacity-40"
                                >
                                  ✓ Apply
                                </button>
                                <button
                                  onClick={() => handleApproveCleaning(idx, false)}
                                  disabled={cleaningApproving}
                                  className="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 transition-all disabled:opacity-40"
                                >
                                  ✕ Reject
                                </button>
                              </>
                            )}
                            {isProposal && state === 'rejected' && (
                              <button
                                onClick={() => handleApproveCleaning(idx, true)}
                                disabled={cleaningApproving}
                                className="px-2 py-0.5 rounded text-[10px] font-semibold bg-teal-500/10 text-teal-400 border border-teal-500/30 hover:bg-teal-500/20 transition-all disabled:opacity-40"
                              >
                                ✓ Apply now
                              </button>
                            )}
                            {isProposal && state === 'applied' && (
                              <span className="text-[9px] text-zinc-500">
                                Applied to dataset — re-process to restore
                              </span>
                            )}
                            {isStructural && (
                              <span className="text-[9px] text-zinc-500">
                                Applied at ingest — re-process to restore
                              </span>
                            )}
                            {!isProposal && !isStructural &&
                              (state === 'applied_silently' ||
                                state === 'confirmed' ||
                                state === 'applied') && (
                                <>
                                  {state === 'applied_silently' && (
                                    <button
                                      onClick={() => handleApproveCleaning(idx, true)}
                                      disabled={cleaningApproving}
                                      className="px-2 py-0.5 rounded text-[10px] font-semibold bg-teal-500/10 text-teal-400 border border-teal-500/30 hover:bg-teal-500/20 transition-all disabled:opacity-40"
                                    >
                                      ✓ Keep
                                    </button>
                                  )}
                                  <button
                                    onClick={() => handleApproveCleaning(idx, false)}
                                    disabled={cleaningApproving}
                                    className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30 hover:bg-blue-500/20 transition-all disabled:opacity-40"
                                  >
                                    ↩ Revert
                                  </button>
                                </>
                              )}
                            {!isProposal && state === 'reverted' && (
                              <button
                                onClick={() => handleApproveCleaning(idx, true)}
                                disabled={cleaningApproving}
                                className="px-2 py-0.5 rounded text-[10px] font-semibold bg-teal-500/10 text-teal-400 border border-teal-500/30 hover:bg-teal-500/20 transition-all disabled:opacity-40"
                              >
                                ✓ Restore
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── RIGHT PANE: DATA SCHEMA WORKBENCH (8 COLS) ── */}
          <div className="lg:col-span-8 space-y-4">
            
            {/* Workbench Control Toolbar */}
            <div className="bg-[#12141C] border border-zinc-800/80 p-3.5 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-md">
              
              {/* Search Bar */}
              <div className="relative flex-1 max-w-md">
                <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Filter columns by name, data type, or sample data..."
                  className="w-full pl-9 pr-3 py-1.5 bg-[#0B0C10] border border-zinc-800 rounded-lg text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-orange-500/50 transition-all font-sans"
                />
              </div>

              {/* Role Filter Tabs */}
              <div className="flex items-center gap-1 bg-[#0B0C10] p-1 rounded-lg border border-zinc-800/80 overflow-x-auto">
                {[
                  { id: 'all', label: `All (${totalColumns})` },
                  { id: 'measures', label: `Measures (${measuresGroup?.columns?.length || 0})` },
                  { id: 'dimensions', label: `Dimensions (${dimensionsGroup?.columns?.length || 0})` },
                  { id: 'time', label: `Time (${timeGroup?.columns?.length || 0})` },
                  { id: 'identifiers', label: `IDs (${identifiersGroup?.columns?.length || 0})` },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveCategoryTab(tab.id)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all whitespace-nowrap cursor-pointer ${
                      activeCategoryTab === tab.id
                        ? 'bg-zinc-800 text-white shadow-sm'
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Selection Controls */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={() => setAutoSelect(!autoSelect)}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-semibold border transition-all flex items-center gap-1 cursor-pointer ${
                    autoSelect
                      ? 'bg-orange-500/10 text-orange-400 border-orange-500/30'
                      : 'bg-[#0B0C10] text-zinc-400 border-zinc-800 hover:text-zinc-200'
                  }`}
                >
                  <Sparkles className="w-3 h-3" />
                  Auto-Select
                </button>

                <button
                  onClick={() => handleSelectAllInView(filteredColumnsList, true)}
                  className="px-2 py-1 text-[11px] text-zinc-400 hover:text-zinc-200 bg-[#0B0C10] border border-zinc-800 rounded-md transition-colors cursor-pointer"
                >
                  All
                </button>
                <button
                  onClick={() => handleSelectAllInView(filteredColumnsList, false)}
                  className="px-2 py-1 text-[11px] text-zinc-400 hover:text-zinc-200 bg-[#0B0C10] border border-zinc-800 rounded-md transition-colors cursor-pointer"
                >
                  None
                </button>
              </div>
            </div>

            {/* High-Density Data Dictionary Table */}
            <div className="bg-[#12141C] border border-zinc-800/80 rounded-xl overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  
                  {/* Table Header */}
                  <thead>
                    <tr className="border-b border-zinc-800 bg-[#0B0C10]/80 text-[10px] font-mono uppercase text-zinc-400 tracking-wider">
                      <th className="py-3 px-4 w-12 text-center">Active</th>
                      <th className="py-3 px-4 min-w-[180px]">Column Name & Role</th>
                      <th className="py-3 px-4 w-28">Data Type</th>
                      <th className="py-3 px-4 w-44">Cardinality Metrics</th>
                      <th className="py-3 px-4 min-w-[200px]">Sample Values Preview</th>
                    </tr>
                  </thead>

                  {/* Table Body */}
                  <tbody className="divide-y divide-zinc-800/60 font-sans">
                    {filteredColumnsList.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-zinc-500 text-xs font-mono">
                          No matching schema columns found for "{searchTerm}"
                        </td>
                      </tr>
                    ) : (
                      filteredColumnsList.map((col) => {
                        const isSelected = selected.has(col.name);
                        const hint = getCardinalityHint(col, dataset?.metadata?.data_profile?.cardinality);
                        const sampleStr = getSampleValuesStr(col, dataset);
                        const RoleIcon = col.role.icon;

                        return (
                          <tr
                            key={col.name}
                            onClick={() => handleToggleColumn(col.name)}
                            className={`transition-colors cursor-pointer ${
                              isSelected ? col.role.rowBgActive : 'hover:bg-zinc-900/40'
                            }`}
                          >
                            {/* Checkbox */}
                            <td className="py-3 px-4 text-center">
                              <div className="inline-flex items-center justify-center">
                                {isSelected ? (
                                  <CheckSquare className="w-4 h-4 text-orange-400" />
                                ) : (
                                  <Square className="w-4 h-4 text-zinc-600 hover:text-zinc-400" />
                                )}
                              </div>
                            </td>

                            {/* Name & Role */}
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2.5">
                                <div className={`w-5 h-5 rounded flex items-center justify-center ${col.role.badgeBg} ${col.role.badgeText}`}>
                                  <RoleIcon className="w-3 h-3" />
                                </div>
                                <span className={`font-semibold ${isSelected ? 'text-white' : 'text-zinc-300'}`}>
                                  {col.name}
                                </span>
                                <span className={`px-1.5 py-0.2 rounded text-[9px] font-mono uppercase font-bold border ${col.role.badgeBg} ${col.role.badgeText} ${col.role.badgeBorder}`}>
                                  {col.role.label}
                                </span>
                              </div>
                            </td>

                            {/* Data Type */}
                            <td className="py-3 px-4">
                              <span className="px-2 py-0.5 rounded font-mono text-[10px] uppercase bg-[#0B0C10] text-zinc-400 border border-zinc-800">
                                {col.type || 'VARCHAR'}
                              </span>
                            </td>

                            {/* Cardinality */}
                            <td className="py-3 px-4 font-mono text-[11px]">
                              <span className={hint?.type === 'warn' ? 'text-amber-400' : 'text-zinc-400'}>
                                {hint?.label}
                              </span>
                            </td>

                            {/* Sample Data */}
                            <td className="py-3 px-4 font-mono text-[11px] text-zinc-400 min-w-0">
                              {sampleStr ? (
                                <span className="truncate block max-w-xs text-zinc-400" title={sampleStr}>
                                  {sampleStr}
                                </span>
                              ) : (
                                <span className="text-zinc-600 font-sans italic">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

          </div>

        </div>
      </div>

      {/* ═══════ FLOATING PRECISION CONTROL DOCK ═══════ */}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-full max-w-4xl px-4">
        <div className="bg-[#12141C]/90 backdrop-blur-xl border border-zinc-800 rounded-xl p-3 shadow-2xl flex items-center justify-between gap-4">
          
          {/* Active Counters */}
          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-white font-bold">
              {selectedCount} of {totalColumns} Columns Active
            </span>
            <span className="text-zinc-500 font-sans">
              ({selectedMeasures} Measures • {selectedDimensions} Dimensions)
            </span>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            {!canGenerate && (
              <span className="text-[11px] text-amber-400 font-sans mr-2">
                {!hasMeasure ? 'Select 1 measure' : 'Select 1 dimension/time'}
              </span>
            )}

            <button
              onClick={() => setSelected(new Set())}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold text-zinc-400 hover:text-zinc-200 bg-[#0B0C10] border border-zinc-800 transition-colors cursor-pointer"
            >
              Reset
            </button>

            <button
              onClick={handleGenerate}
              disabled={!canGenerate || generating}
              className="px-5 py-2 rounded-lg text-xs font-bold bg-orange-500 hover:bg-orange-600 disabled:opacity-40 text-white shadow-lg flex items-center gap-2 transition-all cursor-pointer"
            >
              {generating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating Dashboard...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Generate Dashboard
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>

        </div>
      </div>

    </main>
  );
};

export default DataBriefing;
