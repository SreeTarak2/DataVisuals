import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Table2,
  Database,
  Hash,
  Calendar,
  Tag,
  MapPin,
  Link2,
  Layers,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Search,
  BarChart3,
  Users,
  Sparkles,
  Loader2,
  Clock,
  Info,
  Eye,
} from 'lucide-react';
import { datasetAPI } from '../../services/api';
import SearchInput from '../../components/ui/SearchInput';


/* ═══════════════════════════════════════════════════════════════════════════════
   Color / Role Helpers
   ═══════════════════════════════════════════════════════════════════════════════ */

const SEMANTIC_COLORS = {
  measure: { bg: 'rgba(47,128,237,0.1)', text: '#60a5fa', border: 'rgba(47,128,237,0.2)' },
  rate: { bg: 'rgba(139,92,246,0.1)', text: '#a78bfa', border: 'rgba(139,92,246,0.2)' },
  count: { bg: 'rgba(16,185,129,0.1)', text: '#34d399', border: 'rgba(16,185,129,0.2)' },
  dimension: { bg: 'rgba(245,158,11,0.1)', text: '#fbbf24', border: 'rgba(245,158,11,0.2)' },
  time: { bg: 'rgba(236,72,153,0.1)', text: '#f472b6', border: 'rgba(236,72,153,0.2)' },
  identity: { bg: 'rgba(107,114,128,0.1)', text: '#9ca3af', border: 'rgba(107,114,128,0.2)' },
};

const ROLE_ICONS = {
  measure: BarChart3,
  rate: BarChart3,
  count: Hash,
  dimension: Tag,
  time: Calendar,
  identity: Database,
};

const RELATIONSHIP_TYPES = {
  foreign_key: { label: 'ID → Name', color: 'rgba(16,185,129,0.15)' },
  derived: { label: 'Derived', color: 'rgba(139,92,246,0.15)' },
  hierarchy: { label: 'Hierarchy', color: 'rgba(47,128,237,0.15)' },
};

/* ═══════════════════════════════════════════════════════════════════════════════
   Utility
   ═══════════════════════════════════════════════════════════════════════════════ */

function formatNumber(n) {
  if (n == null || Number.isNaN(n)) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(2);
}

function formatCurrency(n, currency = '$') {
  if (n == null || Number.isNaN(n)) return '—';
  if (Math.abs(n) >= 1_000_000) return `${currency}${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${currency}${(n / 1_000).toFixed(1)}K`;
  return `${currency}${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function timeAgo(dateStr) {
  if (!dateStr) return null;
  const diff = Date.now() - new Date(dateStr).getTime();
  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}

function getConfidenceColor(score) {
  if (score >= 0.8) return 'rgba(16,185,129,0.15)';
  if (score >= 0.5) return 'rgba(245,158,11,0.15)';
  return 'rgba(239,68,68,0.15)';
}

function getConfidenceTextColor(score) {
  if (score >= 0.8) return '#34d399';
  if (score >= 0.5) return '#fbbf24';
  return '#f87171';
}

/* ═══════════════════════════════════════════════════════════════════════════════
   Inline Styles
   ═══════════════════════════════════════════════════════════════════════════════ */

const styleSheet = `
  .dp-columns-table-wrapper {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,0.06) transparent;
  }
  .dp-columns-table-wrapper::-webkit-scrollbar {
    height: 4px;
  }
  .dp-columns-table-wrapper::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
  }
  .dp-entry {
    animation: dp-fade-in 0.3s ease-out both;
  }
  @keyframes dp-fade-in {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Table styling and custom sticky col interactions */
  .dp-columns-table-wrapper table tbody tr {
    transition: background-color 0.15s ease;
  }
  .dp-columns-table-wrapper table tbody tr:hover {
    background-color: rgba(255, 255, 255, 0.02) !important;
  }
  .dp-columns-table-wrapper table tbody tr:hover td.sticky-col {
    background-color: #1a1a1e !important;
  }
  .dp-columns-table-wrapper table tbody tr.needs-review {
    background-color: rgba(245, 158, 11, 0.02) !important;
  }
  .dp-columns-table-wrapper table tbody tr.needs-review td.sticky-col {
    background-color: #1b1916 !important;
  }
  .dp-columns-table-wrapper table tbody tr.needs-review:hover {
    background-color: rgba(245, 158, 11, 0.04) !important;
  }
  .dp-columns-table-wrapper table tbody tr.needs-review:hover td.sticky-col {
    background-color: #211c14 !important;
  }
  .dp-columns-table-wrapper table th {
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
`;

/* ═══════════════════════════════════════════════════════════════════════════════
   DataProfile Component
   ═══════════════════════════════════════════════════════════════════════════════ */

const DataProfile = () => {
  const { id: datasetId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [profileData, setProfileData] = useState(null);

  // Sort state
  const [sortField, setSortField] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch profile data
  const fetchProfile = useCallback(async () => {
    if (!datasetId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await datasetAPI.getProfile(datasetId);
      const data = res.data;
      if (data.legacy) {
        setProfileData({ legacy: true, message: data.message });
      } else if (!data.profile) {
        setProfileData({ noProfile: true });
      } else {
        setProfileData(data);
      }
    } catch (err) {
      if (err.response?.status === 202) {
        setProfileData({ processing: true });
      } else if (err.response?.status === 404) {
        setError('Dataset not found.');
      } else {
        setError(err.response?.data?.detail || 'Failed to load profile data.');
      }
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  // Poll for completion if still processing
  useEffect(() => {
    if (profileData?.processing) {
      const interval = setInterval(fetchProfile, 5000);
      return () => clearInterval(interval);
    }
  }, [profileData?.processing, fetchProfile]);

  // Merge profile columns with intelligence columns
  const mergedColumns = useMemo(() => {
    if (!profileData?.profile?.columns) return [];
    const profileCols = profileData.profile.columns;
    const intelCols = profileData.intelligence?.columns || [];
    const intelMap = {};
    intelCols.forEach((c) => { intelMap[c.name] = c; });

    return profileCols.map((pc) => ({
      ...pc,
      intelligence: intelMap[pc.name] || null,
    }));
  }, [profileData]);

  // Sort + filter columns
  const sortedColumns = useMemo(() => {
    let cols = [...mergedColumns];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      cols = cols.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.dtype.toLowerCase().includes(q) ||
          (c.intelligence?.semantic_role || '').toLowerCase().includes(q)
      );
    }
    cols.sort((a, b) => {
      let va, vb;
      switch (sortField) {
        case 'name':
          va = a.name.toLowerCase();
          vb = b.name.toLowerCase();
          break;
        case 'role':
          va = a.intelligence?.semantic_role || '';
          vb = b.intelligence?.semantic_role || '';
          break;
        case 'dtype':
          va = a.dtype;
          vb = b.dtype;
          break;
        case 'confidence':
          va = a.intelligence?.classification_confidence ?? 0;
          vb = b.intelligence?.classification_confidence ?? 0;
          break;
        case 'nulls':
          va = a.cardinality?.null_count ?? 0;
          vb = b.cardinality?.null_count ?? 0;
          break;
        default:
          va = a.name;
          vb = b.name;
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return cols;
  }, [mergedColumns, sortField, sortDir, searchQuery]);

  // Quality issues — computed from merged columns.
  // IMPORTANT: must be declared BEFORE any early return so hook order is stable.
  const qualityIssues = useMemo(() => {
    const issues = [];
    const cols = mergedColumns;
    cols.forEach((c) => {
      const nullPct = c.cardinality?.null_pct ?? 0;
      if (nullPct > 20) {
        issues.push({ column: c.name, type: 'high_nulls', detail: `${nullPct.toFixed(0)}% null`, severity: nullPct > 40 ? 'high' : 'medium' });
      }
      if (c.patterns?.length > 0) {
        issues.push({ column: c.name, type: 'pattern', detail: c.patterns.map((p) => p.pattern).join(', '), severity: 'low' });
      }
      if (c.intelligence?.needs_review) {
        issues.push({ column: c.name, type: 'low_confidence', detail: `Classification: ${(c.intelligence.classification_confidence * 100).toFixed(0)}%`, severity: 'medium' });
      }
    });
    return issues;
  }, [mergedColumns]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return (
      <span style={{ color: 'var(--accent-primary)', marginLeft: 4, fontSize: 10 }}>
        {sortDir === 'asc' ? '▲' : '▼'}
      </span>
    );
  };

  const renderStatsSummary = (col) => {
    if (col.stats && col.stats.col_min != null) {
      const min = col.stats.col_min;
      const max = col.stats.col_max;
      const mean = col.stats.col_mean;
      const isPrice = col.name.toLowerCase().includes('price') || col.name.toLowerCase().includes('revenue') || col.name.toLowerCase().includes('salary') || col.name.toLowerCase().includes('cost');
      if (isPrice) {
        return `${formatCurrency(min)} – ${formatCurrency(max)}`;
      }
      if (Math.abs(min) >= 1000 || Math.abs(max) >= 1000) {
        return `${formatNumber(min)} – ${formatNumber(max)}`;
      }
      return `${Number(min).toLocaleString()} – ${Number(max).toLocaleString()}`;
    }
    if (col.cardinality) {
      return `${col.cardinality.unique_count} unique`;
    }
    return '—';
  };

  const renderStatsMean = (col) => {
    if (col.stats?.col_mean != null) {
      const isPrice = col.name.toLowerCase().includes('price') || col.name.toLowerCase().includes('revenue') || col.name.toLowerCase().includes('salary') || col.name.toLowerCase().includes('cost');
      if (isPrice) return formatCurrency(col.stats.col_mean);
      return formatNumber(col.stats.col_mean);
    }
    return null;
  };

  /* ── Loading State ─────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--accent-primary)' }} />
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Loading profile data…</p>
        </div>
      </div>
    );
  }

  /* ── Error State ───────────────────────────────────────────────────────── */
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="max-w-md text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-xl flex items-center justify-center" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}>
            <AlertTriangle className="w-6 h-6" style={{ color: '#f87171' }} />
          </div>
          <h2 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-header)' }}>Could not load profile</h2>
          <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>{error}</p>
          <button onClick={() => navigate('/app/dashboard')} className="btn btn-sm btn-secondary">
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  /* ── Processing State ──────────────────────────────────────────────────── */
  if (profileData?.processing) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="max-w-md text-center">
          <div className="w-14 h-14 mx-auto mb-5 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-primary-light)' }}>
            <Loader2 className="w-7 h-7 animate-spin" style={{ color: 'var(--accent-primary)' }} />
          </div>
          <h2 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-header)' }}>Processing in progress</h2>
          <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
            The profiling pipeline is still running. This page will update automatically when complete.
          </p>
          <button onClick={() => navigate('/app/dashboard')} className="btn btn-sm btn-secondary">
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  /* ── Legacy / No Profile State ─────────────────────────────────────────── */
  if (profileData?.legacy || profileData?.noProfile) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="max-w-md text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-xl flex items-center justify-center" style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)' }}>
            <Info className="w-6 h-6" style={{ color: '#fbbf24' }} />
          </div>
          <h2 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-header)' }}>Profile not available</h2>
          <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
            {profileData?.message || 'This dataset was processed before the profiling engine was added. Re-process to generate the profile.'}
          </p>
          <button onClick={() => navigate('/app/dashboard')} className="btn btn-sm btn-primary">
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  /* ── Extract data for rendering ────────────────────────────────────────── */
  const { profile, intelligence } = profileData;
  const dataset = profile?.dataset;
  const domain = intelligence?.domain;
  const topCandidate = domain?.top_candidate;
  const llmVerdict = domain?.llm_verdict;
  const entities = intelligence?.entities || [];
  const relationships = intelligence?.relationships || [];
  const hierarchies = intelligence?.hierarchies || [];
  const geo = intelligence?.geo;
  const hasGeo = geo && (geo.latitude || geo.country || geo.city);
  const columnsNeedingReview = intelligence?.columns_needing_review || [];
  const activeStructureCardsCount = [
    entities.length > 0,
    relationships.length > 0,
    hierarchies.length > 0,
    hasGeo
  ].filter(Boolean).length;

  /* ── Render ────────────────────────────────────────────────────────────── */
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.04 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 12 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.35, ease: [0.23, 1, 0.32, 1] },
    },
  };

  return (
    <motion.div
      className="min-h-full"
      style={{ backgroundColor: 'var(--bg-primary)' }}
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      <style>{styleSheet}</style>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10">

        {/* ── Top Navigation ── */}
        <motion.div variants={itemVariants} className="mb-6">
          <button
            onClick={() => navigate('/app/workspace')}
            className="inline-flex items-center gap-2 text-[10px] font-bold tracking-wider uppercase text-orange-500 hover:text-orange-400 transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Assets
          </button>
        </motion.div>

        {/* ── Header Section ── */}
        <motion.div variants={itemVariants} className="mb-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/[0.06] pb-6">
            <div>
              <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-orange-500 mb-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />
                Profiling Engine
              </span>
              <h1 className="text-3xl font-extrabold tracking-tight text-white">
                Dataset Data Profile
              </h1>
              <p className="text-xs text-gray-400 mt-1">
                Deep structural profile for <span className="font-semibold text-gray-300">{profileData?.profile?.dataset?.file_name || 'dataset'}</span>
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate(`/app/datasets/${datasetId}/understanding`)}
                className="bg-white/[0.03] border border-white/[0.06] text-white hover:bg-white/[0.08] px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition-all cursor-pointer h-[38px]"
              >
                <Eye className="w-3.5 h-3.5" />
                Understanding
              </button>
              <button
                onClick={() => navigate(`/app/chat?dataset=${datasetId}`)}
                className="bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition-all cursor-pointer h-[38px]"
              >
                Chat Analytics
              </button>
            </div>
          </div>
        </motion.div>

        {/* ── Domain Section ── */}
        {(topCandidate || llmVerdict) && (
          <motion.div variants={itemVariants} className="mb-8">
            <div
              className="rounded-xl p-6 relative overflow-hidden"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
              }}
            >
              {/* Ambient background glow */}
              <div className="absolute top-0 right-0 w-80 h-80 bg-orange-500/5 rounded-full blur-[100px] pointer-events-none" />
              
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start relative z-10">
                {/* Left Block - 7 cols */}
                <div className="lg:col-span-7 space-y-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2 mb-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-orange-500/10 text-orange-400 border border-orange-500/20">
                        Detected Domain
                      </span>
                      {topCandidate && (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider"
                          style={{
                            background: getConfidenceColor(topCandidate.score / 100),
                            color: getConfidenceTextColor(topCandidate.score / 100),
                          }}
                        >
                          {topCandidate.score}% match
                        </span>
                      )}
                      {llmVerdict && (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider"
                          style={{
                            background: getConfidenceColor(llmVerdict.confidence),
                            color: getConfidenceTextColor(llmVerdict.confidence),
                          }}
                        >
                          <Sparkles className="w-3 h-3" />
                          {Math.round(llmVerdict.confidence * 100)}% confidence
                        </span>
                      )}
                    </div>
                    <h2 className="text-2xl font-bold tracking-tight text-white">
                      {llmVerdict?.domain || topCandidate?.domain_name || 'Unknown Domain'}
                    </h2>
                    <p className="text-xs text-gray-500 mt-1">Detected Schema Structure</p>
                  </div>

                  {llmVerdict?.reasoning && (
                    <div className="bg-black/20 border border-white/[0.04] rounded-lg p-4">
                      <p className="text-xs text-gray-400 font-medium leading-normal mb-1">AI Verdict Reasoning:</p>
                      <p className="text-xs text-gray-300 leading-relaxed">
                        {llmVerdict.reasoning}
                      </p>
                    </div>
                  )}
                </div>

                {/* Right Block - 5 cols */}
                <div className="lg:col-span-5 space-y-4">
                  <div className="bg-black/20 border border-white/[0.04] rounded-lg p-4 space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">Dataset Overview</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                        <span className="text-xs text-gray-500 block">Row Count</span>
                        <span className="text-lg font-bold text-white tabular-nums">{dataset?.row_count?.toLocaleString() || '—'}</span>
                      </div>
                      <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                        <span className="text-xs text-gray-500 block">Column Count</span>
                        <span className="text-lg font-bold text-white tabular-nums">{dataset?.column_count || '—'}</span>
                      </div>
                      <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                        <span className="text-xs text-gray-500 block">File Format</span>
                        <span className="text-lg font-bold text-white">{dataset?.file_type?.toUpperCase() || '—'}</span>
                      </div>
                      <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                        <span className="text-xs text-gray-500 block">Processed</span>
                        <span className="text-sm font-semibold text-white truncate block">
                          {profileData?.profile?.processed_at ? timeAgo(profileData.profile.processed_at) : '—'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── Columns Table ── */}
        <motion.div variants={itemVariants} className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <div
                className="p-1.5 rounded-lg flex items-center justify-center bg-orange-500/10 text-orange-500 border border-orange-500/20"
              >
                <Table2 className="w-4 h-4" />
              </div>
              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
                Columns
              </span>
              <span
                className="px-1.5 py-0.5 rounded-md text-xs font-medium bg-white/[0.03] text-gray-300 border border-white/[0.06] tabular-nums"
              >
                {mergedColumns.length}
              </span>
            </div>

            {/* Search */}
            <SearchInput
              placeholder="Search columns…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="hidden sm:block"
              width={240}
            />
          </div>

          <div
            className="rounded-xl overflow-hidden"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            <div className="dp-columns-table-wrapper">
              <table className="w-full text-sm" style={{ borderCollapse: 'collapse', minWidth: 700 }}>
                <thead>
                  <tr
                    className="text-xs font-medium select-none"
                    style={{ color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}
                  >
                    <th
                      className="px-4 py-3 text-left cursor-pointer hover:text-header transition-colors sticky left-0 bg-[var(--bg-surface)] z-10"
                      onClick={() => handleSort('name')}
                      style={{ minWidth: 160 }}
                    >
                      Column <SortIcon field="name" />
                    </th>
                    <th
                      className="px-4 py-3 text-left cursor-pointer hover:text-header transition-colors"
                      onClick={() => handleSort('dtype')}
                      style={{ minWidth: 90 }}
                    >
                      Type <SortIcon field="dtype" />
                    </th>
                    <th
                      className="px-4 py-3 text-left cursor-pointer hover:text-header transition-colors"
                      onClick={() => handleSort('role')}
                      style={{ minWidth: 100 }}
                    >
                      Role <SortIcon field="role" />
                    </th>
                    <th className="px-4 py-3 text-left" style={{ minWidth: 100 }}>
                      Behavior
                    </th>
                    <th className="px-4 py-3 text-left" style={{ minWidth: 120 }}>
                      Range / Values
                    </th>
                    <th
                      className="px-4 py-3 text-right cursor-pointer hover:text-header transition-colors"
                      onClick={() => handleSort('nulls')}
                      style={{ minWidth: 80 }}
                    >
                      Quality <SortIcon field="nulls" />
                    </th>
                    <th
                      className="px-4 py-3 text-right cursor-pointer hover:text-header transition-colors"
                      onClick={() => handleSort('confidence')}
                      style={{ minWidth: 90 }}
                    >
                      Confidence <SortIcon field="confidence" />
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedColumns.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
                        {searchQuery ? 'No columns match your search.' : 'No columns found.'}
                      </td>
                    </tr>
                  ) : (
                    sortedColumns.map((col, idx) => {
                      const intel = col.intelligence;
                      const role = intel?.semantic_role || 'dimension';
                      const RoleIcon = ROLE_ICONS[role] || Tag;
                      const colorInfo = SEMANTIC_COLORS[role] || SEMANTIC_COLORS.dimension;
                      const behavior = intel?.behavioral_role || '—';
                      const behaviorLabel = behavior === 'unknown' ? '—' : behavior.replace(/_/g, ' ');
                      const agg = intel?.aggregation_suitability;
                      const confidence = intel?.classification_confidence ?? null;
                      const needsReview = intel?.needs_review || false;
                      const nullPct = col.cardinality?.null_pct ?? 0;

                      return (
                        <tr
                          key={col.name}
                          className={`transition-colors ${needsReview ? 'needs-review' : ''}`}
                          style={{
                            borderBottom: '1px solid var(--border)',
                          }}
                        >
                          {/* Column Name */}
                          <td
                            className="px-4 py-3 sticky left-0 z-[5] sticky-col"
                            style={{
                              background: 'rgba(19, 19, 22, 1)',
                              borderRight: '1px solid var(--border)',
                            }}
                          >
                            <div className="flex items-center gap-2">
                              <div
                                className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
                                style={{ background: colorInfo.bg, border: `1px solid ${colorInfo.border}` }}
                              >
                                <RoleIcon className="w-3 h-3" style={{ color: colorInfo.text }} />
                              </div>
                              <div className="min-w-0">
                                <span className="text-sm font-medium truncate block" style={{ color: 'var(--text-header)' }}>
                                  {col.name}
                                </span>
                              </div>
                            </div>
                          </td>

                          {/* Type */}
                          <td className="px-4 py-3">
                            <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                              {col.dtype?.replace('Int64', 'int').replace('Float64', 'float').replace('Utf8', 'string').replace('Categorical', 'category') || '—'}
                            </span>
                          </td>

                          {/* Role */}
                          <td className="px-4 py-3">
                            <span
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium capitalize"
                              style={{ background: colorInfo.bg, color: colorInfo.text, border: `1px solid ${colorInfo.border}` }}
                            >
                              {role}
                            </span>
                          </td>

                          {/* Behavior */}
                          <td className="px-4 py-3">
                            <span className="text-xs capitalize" style={{ color: 'var(--text-secondary)' }}>
                              {behaviorLabel}
                            </span>
                            {agg && (
                              <span className="text-[10px] ml-1.5" style={{ color: 'var(--text-muted)' }}>
                                {agg.additive_type === 'additive' ? '⊕' : agg.additive_type === 'non_additive' ? '⊘' : '⊖'}
                              </span>
                            )}
                          </td>

                          {/* Range / Values */}
                          <td className="px-4 py-3">
                            <div>
                              <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                                {renderStatsSummary(col)}
                              </span>
                              {renderStatsMean(col) && (
                                <span className="text-[10px] ml-2" style={{ color: 'var(--text-muted)' }}>
                                  avg {renderStatsMean(col)}
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Quality */}
                          <td className="px-4 py-3 text-right">
                            {nullPct > 0 ? (
                              <span
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium"
                                style={{
                                  background: nullPct > 20 ? 'rgba(239,68,68,0.1)' : nullPct > 5 ? 'rgba(245,158,11,0.1)' : 'rgba(16,185,129,0.1)',
                                  color: nullPct > 20 ? '#f87171' : nullPct > 5 ? '#fbbf24' : '#34d399',
                                }}
                              >
                                {nullPct > 0 ? `${nullPct.toFixed(0)}% null` : '100%'}
                              </span>
                            ) : (
                              <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                                —
                              </span>
                            )}
                          </td>

                          {/* Confidence */}
                          <td className="px-4 py-3 text-right">
                            {confidence != null ? (
                              <span
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium"
                                style={{
                                  background: getConfidenceColor(confidence),
                                  color: getConfidenceTextColor(confidence),
                                }}
                              >
                                {needsReview && <AlertTriangle className="w-2.5 h-2.5" />}
                                {Math.round(confidence * 100)}%
                              </span>
                            ) : (
                              <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                                —
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* Mobile search (always visible on small screens) */}
            <div className="sm:hidden px-4 py-3 border-t border-white/[0.04]">
              <SearchInput
                placeholder="Search columns…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                width="100%"
                style={{
                  paddingTop: '8px',
                  paddingBottom: '8px',
                }}
              />
            </div>
          </div>
        </motion.div>

        {/* ── Structure Section (Entities, Relationships, Hierarchies) ── */}
        {(entities.length > 0 || relationships.length > 0 || hierarchies.length > 0 || hasGeo) && (
          <motion.div variants={itemVariants} className="mb-8">
            <div className="flex items-center gap-2.5 mb-4">
              <div
                className="p-1.5 rounded-lg flex items-center justify-center bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
              >
                <Layers className="w-4 h-4" />
              </div>
              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
                Structure
              </span>
            </div>

            <div className={`grid grid-cols-1 ${activeStructureCardsCount > 1 ? 'md:grid-cols-2' : ''} gap-4`}>

              {/* Entities */}
              {entities.length > 0 && (
                <div
                  className="rounded-xl p-4"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center gap-2 mb-3 border-b border-white/[0.04] pb-2">
                    <Users className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                      Entities
                    </span>
                    <span
                      className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium bg-white/[0.03] text-gray-400 border border-white/[0.06]"
                    >
                      {entities.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {entities.map((e) => (
                      <div
                        key={e.entity_column}
                        className="flex items-center justify-between px-3 py-2 rounded-lg text-sm bg-white/[0.02] border border-white/[0.04]"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white">
                            {e.entity_type || e.entity_column}
                          </span>
                          <span className="text-[10px] font-mono text-gray-500 px-1 bg-white/[0.03] border border-white/[0.06] rounded">
                            {e.entity_column}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-gray-400">
                          <span>{e.unique_count?.toLocaleString()} unique</span>
                          {e.avg_records_per_entity > 0 && (
                            <span>{e.avg_records_per_entity.toFixed(1)} avg/entity</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Relationships */}
              {relationships.length > 0 && (
                <div
                  className="rounded-xl p-4"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center gap-2 mb-3 border-b border-white/[0.04] pb-2">
                    <Link2 className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                      Relationships
                    </span>
                    <span
                      className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium bg-white/[0.03] text-gray-400 border border-white/[0.06]"
                    >
                      {relationships.length}
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {relationships.map((r, idx) => {
                      const relType = RELATIONSHIP_TYPES[r.relationship_type] || { label: r.relationship_type, color: 'rgba(107,114,128,0.1)' };
                      return (
                        <div
                          key={`${r.source_column}-${r.target_column}-${idx}`}
                          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-white/[0.02] border border-white/[0.04]"
                        >
                          <span className="font-mono text-xs font-semibold text-white">
                            {r.source_column}
                          </span>
                          <span className="text-gray-500">→</span>
                          <span className="font-mono text-xs font-semibold text-white">
                            {r.target_column}
                          </span>
                          <span
                            className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium"
                            style={{ background: relType.color, color: 'var(--text-secondary)' }}
                          >
                            {relType.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Hierarchies */}
              {hierarchies.length > 0 && (
                <div
                  className="rounded-xl p-4"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center gap-2 mb-3 border-b border-white/[0.04] pb-2">
                    <Layers className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                      Hierarchies
                    </span>
                    <span
                      className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium bg-white/[0.03] text-gray-400 border border-white/[0.06]"
                    >
                      {hierarchies.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {hierarchies.map((h, idx) => (
                      <div
                        key={`${h.hierarchy_type}-${idx}`}
                        className="px-3 py-2.5 rounded-lg text-sm bg-white/[0.02] border border-white/[0.04]"
                      >
                        <div className="flex items-center gap-1.5 mb-2">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                            {h.hierarchy_type}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {h.columns.map((col, ci) => (
                            <React.Fragment key={col}>
                              {ci > 0 && (
                                <span className="text-gray-500">
                                  <ChevronRight className="w-3 h-3" />
                                </span>
                              )}
                              <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20">
                                {col}
                              </span>
                            </React.Fragment>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Geo */}
              {hasGeo && (
                <div
                  className="rounded-xl p-4"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center gap-2 mb-3 border-b border-white/[0.04] pb-2">
                    <MapPin className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                      Geographic
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {geo.latitude && geo.longitude && (
                      <div
                        className="flex items-center justify-between px-3 py-2 rounded-lg text-sm bg-white/[0.02] border border-white/[0.04]"
                      >
                        <span className="text-gray-400 text-xs">Coordinates</span>
                        <span className="font-mono text-xs text-white">
                          {geo.latitude}, {geo.longitude}
                        </span>
                      </div>
                    )}
                    {geo.country && (
                      <div
                        className="flex items-center justify-between px-3 py-2 rounded-lg text-sm bg-white/[0.02] border border-white/[0.04]"
                      >
                        <span className="text-gray-400 text-xs">Country</span>
                        <span className="font-mono text-xs text-white">
                          {geo.country}
                        </span>
                      </div>
                    )}
                    {geo.state && (
                      <div
                        className="flex items-center justify-between px-3 py-2 rounded-lg text-sm bg-white/[0.02] border border-white/[0.04]"
                      >
                        <span className="text-gray-400 text-xs">State</span>
                        <span className="font-mono text-xs text-white">
                          {geo.state}
                        </span>
                      </div>
                    )}
                    {geo.city && (
                      <div
                        className="flex items-center justify-between px-3 py-2 rounded-lg text-sm bg-white/[0.02] border border-white/[0.04]"
                      >
                        <span className="text-gray-400 text-xs">City</span>
                        <span className="font-mono text-xs text-white">
                          {geo.city}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* ── Quality Section ── */}
        <motion.div variants={itemVariants} className="mb-12">
          <div className="flex items-center gap-2.5 mb-4">
            <div
              className="p-1.5 rounded-lg flex items-center justify-center bg-yellow-500/10 text-yellow-500 border border-yellow-500/20"
            >
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
              Data Quality
            </span>
            {qualityIssues.length > 0 && (
              <span
                className="px-1.5 py-0.5 rounded-md text-xs font-medium tabular-nums"
                style={{ background: qualityIssues.filter((i) => i.severity === 'high').length > 0 ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)', color: qualityIssues.filter((i) => i.severity === 'high').length > 0 ? '#f87171' : '#fbbf24', border: '1px solid rgba(245,158,11,0.2)' }}
              >
                {qualityIssues.length} issue{qualityIssues.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Quality Summary */}
            <div
              className="rounded-xl p-4"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-2 mb-4 border-b border-white/[0.04] pb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                  Summary Overview
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {(() => {
                  const totalRows = dataset?.row_count || 0;
                  const totalCols = mergedColumns.length;
                  const colsWithNulls = mergedColumns.filter((c) => (c.cardinality?.null_pct ?? 0) > 0).length;
                  const avgCompleteness = totalCols > 0
                    ? mergedColumns.reduce((s, c) => s + (c.quality?.completeness ?? 1), 0) / totalCols
                    : 1;
                  return (
                    <>
                      <div className="bg-white/[0.02] border border-white/[0.04] p-3 rounded-lg">
                        <span className="text-2xl font-bold tabular-nums text-white">
                          {(avgCompleteness * 100).toFixed(0)}%
                        </span>
                        <p className="text-[10px] mt-0.5 text-gray-500 uppercase tracking-wider">Avg completeness</p>
                      </div>
                      <div className="bg-white/[0.02] border border-white/[0.04] p-3 rounded-lg">
                        <span className="text-lg font-bold tabular-nums text-white">
                          {totalCols - colsWithNulls}/{totalCols}
                        </span>
                        <p className="text-[10px] mt-0.5 text-gray-500 uppercase tracking-wider">Complete columns</p>
                      </div>
                      <div className="bg-white/[0.02] border border-white/[0.04] p-3 rounded-lg">
                        <span className="text-lg font-bold tabular-nums" style={{ color: colsWithNulls > 0 ? '#fbbf24' : 'white' }}>
                          {colsWithNulls}
                        </span>
                        <p className="text-[10px] mt-0.5 text-gray-500 uppercase tracking-wider">Columns with nulls</p>
                      </div>
                      <div className="bg-white/[0.02] border border-white/[0.04] p-3 rounded-lg">
                        <span className="text-lg font-bold tabular-nums" style={{ color: columnsNeedingReview.length > 0 ? '#fbbf24' : 'white' }}>
                          {columnsNeedingReview.length}
                        </span>
                        <p className="text-[10px] mt-0.5 text-gray-500 uppercase tracking-wider">Need review</p>
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>

            {/* Issues List */}
            <div
              className="rounded-xl p-4"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-2 mb-4 border-b border-white/[0.04] pb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                  Observations & Issues
                </span>
              </div>
              {qualityIssues.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-6 text-center">
                  <CheckCircle2 className="w-8 h-8 mb-2 text-emerald-500/30" />
                  <p className="text-sm text-gray-500">No quality issues detected</p>
                </div>
              ) : (
                <div className="space-y-1.5 max-h-[174px] overflow-y-auto pr-1">
                  {qualityIssues.slice(0, 8).map((issue) => (
                    <div
                      key={`${issue.column}-${issue.type}`}
                      className="flex items-center justify-between px-3 py-2 rounded-lg text-sm bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                          style={{
                            background: issue.severity === 'high'
                              ? '#f87171'
                              : issue.severity === 'medium'
                                ? '#fbbf24'
                                : '#60a5fa',
                          }}
                        />
                        <span className="font-mono text-xs truncate text-white">
                          {issue.column}
                        </span>
                        <span className="text-xs text-gray-400 truncate">{issue.detail}</span>
                      </div>
                      <span
                        className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded flex-shrink-0 border"
                        style={{
                          background: issue.severity === 'high'
                            ? 'rgba(239,68,68,0.1)'
                            : issue.severity === 'medium'
                              ? 'rgba(245,158,11,0.1)'
                              : 'rgba(59,130,246,0.1)',
                          borderColor: issue.severity === 'high'
                            ? 'rgba(239,68,68,0.2)'
                            : issue.severity === 'medium'
                              ? 'rgba(245,158,11,0.2)'
                              : 'rgba(59,130,246,0.2)',
                          color: issue.severity === 'high'
                            ? '#f87171'
                            : issue.severity === 'medium'
                              ? '#fbbf24'
                              : '#60a5fa',
                        }}
                      >
                        {issue.severity === 'high' ? 'High' : issue.severity === 'medium' ? 'Med' : 'Low'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </motion.div>

      </div>
    </motion.div>
  );
};

export default DataProfile;
