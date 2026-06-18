import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Database,
  Target,
  Layers,
  Link2,
  PieChart,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  BarChart3,
  Users,
  Loader2,
  Clock,
  Info,
  Eye,
  Shield,
} from 'lucide-react';
import { datasetAPI } from '../../services/api';
import { useTheme } from '../../store/themeStore';
import { cn } from '../../lib/utils';

/* ═══════════════════════════════════════════════════════════════════════════════
   SIGNAL PRODUCT DESIGN: DATA UNDERSTANDING REPORT
   Aesthetics: Adaptable Theme (Light / Dark)
   ═══════════════════════════════════════════════════════════════════════════════ */

const AMBIGUITY_COLORS = {
  low: { bg: 'rgba(16,185,129,0.08)', text: '#10b981', border: 'rgba(16,185,129,0.15)', label: 'Stable Classification' },
  medium: { bg: 'rgba(245,158,11,0.08)', text: '#d97706', border: 'rgba(245,158,11,0.15)', label: 'Moderate Ambiguity' },
  high: { bg: 'rgba(239,68,68,0.08)', text: '#dc2626', border: 'rgba(239,68,68,0.15)', label: 'High Ambiguity' },
};

const STRENGTH_COLORS = {
  strong: { bg: 'rgba(249,115,22,0.1)', text: '#e05a00', border: 'rgba(249,115,22,0.2)' },
  moderate: { bg: 'rgba(249,115,22,0.06)', text: '#f97316', border: 'rgba(249,115,22,0.12)' },
  weak: { bg: 'rgba(115,115,115,0.08)', text: '#737373', border: 'rgba(115,115,115,0.15)' },
  minimal: { bg: 'rgba(239,68,68,0.08)', text: '#dc2626', border: 'rgba(239,68,68,0.15)' },
};

const ROLE_BADGE_COLORS = {
  IDENTIFIER: { bg: 'rgba(249,115,22,0.1)', text: '#f97316', border: 'rgba(249,115,22,0.2)' },
  NAME: { bg: 'rgba(167,139,250,0.1)', text: '#8b5cf6', border: 'rgba(167,139,250,0.2)' },
  AMOUNT: { bg: 'rgba(16,185,129,0.1)', text: '#10b981', border: 'rgba(16,185,129,0.2)' },
  DATE: { bg: 'rgba(236,72,153,0.1)', text: '#ec4899', border: 'rgba(236,72,153,0.2)' },
  STATUS: { bg: 'rgba(245,158,11,0.1)', text: '#f59e0b', border: 'rgba(245,158,11,0.2)' },
  ATTRIBUTE: { bg: 'rgba(115,115,115,0.1)', text: '#737373', border: 'rgba(115,115,115,0.2)' },
};

function getStrengthLevel(score) {
  if (score >= 0.70) return 'strong';
  if (score >= 0.50) return 'moderate';
  if (score >= 0.30) return 'weak';
  return 'minimal';
}

function getStrengthLabel(score) {
  if (score >= 0.70) return 'Highly Confident';
  if (score >= 0.50) return 'Moderately Confident';
  if (score >= 0.30) return 'Low Confidence';
  return 'Inconclusive Schema';
}

function timeAgo(dateStr) {
  if (!dateStr) return null;
  const diff = Date.now() - new Date(dateStr).getTime();
  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}

function formatNumber(n) {
  if (n == null || Number.isNaN(n)) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(2);
}

/* ═══════════════════════════════════════════════════════════════════════════════
   Helper UI Sub-Components
   ═══════════════════════════════════════════════════════════════════════════════ */

function StrengthGauge({ score, size = 80 }) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const level = getStrengthLevel(score);
  const colors = STRENGTH_COLORS[level] || STRENGTH_COLORS.strong;
  const radius = size / 2 - 6;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={isDark ? "rgba(255, 255, 255, 0.03)" : "rgba(0, 0, 0, 0.05)"}
          strokeWidth={6}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors.text}
          strokeWidth={6}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700 ease-out"
          style={{
            filter: `drop-shadow(0 0 6px ${colors.text}40)`
          }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className={cn("text-2xl font-extrabold tracking-tight tabular-nums", isDark ? "text-white" : "text-gray-900")}>
          {(score * 100).toFixed(0)}%
        </span>
        <span className={cn("text-[9px] uppercase tracking-widest font-semibold mt-0.5", isDark ? "text-gray-500" : "text-gray-405")}>
          Match
        </span>
      </div>
    </div>
  );
}

function EvidenceBar({ column_name, role, contribution, maxContribution }) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const pct = maxContribution > 0 ? (contribution / maxContribution) * 100 : 0;
  const roleColor = ROLE_BADGE_COLORS[role] || ROLE_BADGE_COLORS.ATTRIBUTE;

  return (
    <div className={cn(
      "flex items-center gap-3 px-4 py-2.5 rounded-lg border transition-colors",
      isDark ? "bg-[#0D0D0F] border-white/[0.03]" : "bg-gray-50 border-gray-200"
    )}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2 min-w-0">
            <span className={cn("font-mono text-sm font-semibold truncate", isDark ? "text-white" : "text-gray-900")}>
              {column_name}
            </span>
            <span
              className="px-1.5 py-0.5 rounded text-[9px] font-semibold tracking-wider uppercase"
              style={{ background: roleColor.bg, color: roleColor.text, border: `1px solid ${roleColor.border}` }}
            >
              {role}
            </span>
          </div>
          <span className={cn("text-xs font-mono tabular-nums", isDark ? "text-gray-500" : "text-gray-600")}>
            {(contribution * 100).toFixed(1)}%
          </span>
        </div>
        <div className={cn("w-full h-1.5 rounded-full overflow-hidden", isDark ? "bg-white/[0.04]" : "bg-gray-200")}>
          <motion.div
            className="h-full rounded-full bg-orange-600"
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
      </div>
    </div>
  );
}

function AlternativeCard({ alt, index }) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  return (
    <div className={cn(
      "rounded-lg p-3.5 border text-xs",
      isDark ? "bg-[#0D0D0F] border-white/[0.04]" : "bg-gray-50 border-gray-200"
    )}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold bg-orange-500/10 text-orange-500">
            {index + 1}
          </span>
          <span className={cn("font-semibold capitalize", isDark ? "text-white" : "text-gray-900")}>{alt.label}</span>
        </div>
        <span className={cn("px-2 py-0.5 rounded text-[10px] font-semibold tabular-nums", isDark ? "bg-white/[0.03] text-gray-400" : "bg-gray-200/50 text-gray-600")}>
          {(alt.confidence * 100).toFixed(0)}% match
        </span>
      </div>
      <div className={cn("grid grid-cols-3 gap-2 text-[10px]", isDark ? "text-gray-500" : "text-gray-600")}>
        <div>
          <span>Name Alignment: </span>
          <span className={cn("font-mono", isDark ? "text-gray-300" : "text-gray-800")}>{(alt.table_name_score * 100).toFixed(0)}%</span>
        </div>
        <div>
          <span>Column Match: </span>
          <span className={cn("font-mono", isDark ? "text-gray-300" : "text-gray-800")}>{(alt.column_dominance_score * 100).toFixed(0)}%</span>
        </div>
        <div>
          <span>Pattern Verification: </span>
          <span className={cn("font-mono", isDark ? "text-gray-300" : "text-gray-800")}>{(alt.entity_confidence_score * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
}

function ParticipantCard({ participant }) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  return (
    <div className={cn(
      "rounded-lg px-4 py-3 border flex items-center justify-between transition-colors",
      isDark ? "bg-[#0D0D0F] border-white/[0.04]" : "bg-gray-50 border-gray-200"
    )}>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-orange-500/10 border border-orange-500/20">
          <Users className="w-4 h-4 text-orange-500" />
        </div>
        <div>
          <span className={cn("text-sm font-semibold", isDark ? "text-white" : "text-gray-900")}>
            {participant.label}
          </span>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={cn("text-xs font-mono", isDark ? "text-gray-500" : "text-gray-605")}>
              via {participant.identifier_column}
            </span>
            {!participant.is_valid && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-450 border border-rose-500/10">
                Below threshold
              </span>
            )}
          </div>
        </div>
      </div>
      <div className={cn("flex items-center gap-4 text-xs", isDark ? "text-gray-400" : "text-gray-600")}>
        <div className="text-right">
          <span className="font-mono tabular-nums font-semibold text-orange-600">
            {(participant.participation_score * 100).toFixed(0)}%
          </span>
          <p className={cn("text-[9px]", isDark ? "text-gray-500" : "text-gray-600")}>Participation</p>
        </div>
        <div className="text-right">
          <span className={cn("font-mono tabular-nums", isDark ? "text-white" : "text-gray-900")}>{(participant.entity_confidence * 100).toFixed(0)}%</span>
          <p className={cn("text-[9px]", isDark ? "text-gray-500" : "text-gray-600")}>Confidence</p>
        </div>
      </div>
    </div>
  );
}

function ReferenceSignalCard({ signal }) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const cardinalityColors = {
    many_to_one: { bg: 'rgba(249,115,22,0.1)', text: '#f97316' },
    one_to_one: { bg: 'rgba(16,185,129,0.1)', text: '#10b981' },
    one_to_many: { bg: 'rgba(167,139,250,0.1)', text: '#8b5cf6' },
  };
  const cardColor = cardinalityColors[signal.cardinality] || cardinalityColors.many_to_one;

  return (
    <div className={cn(
      "rounded-lg px-4 py-3 border transition-colors",
      isDark ? "bg-[#0D0D0F] border-white/[0.04]" : "bg-gray-50 border-gray-200"
    )}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={cn("text-sm font-semibold capitalize", isDark ? "text-white" : "text-gray-900")}>
            {signal.source_entity}
          </span>
          <span className={isDark ? "text-gray-600" : "text-gray-400"}>→</span>
          <span className={cn("text-sm font-semibold capitalize", isDark ? "text-white" : "text-gray-900")}>
            {signal.target_entity}
          </span>
        </div>
        <span
          className="px-2 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider"
          style={{ background: cardColor.bg, color: cardColor.text }}
        >
          {signal.cardinality.replace(/_/g, ' ')}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span className={cn("text-xs font-mono", isDark ? "text-gray-500" : "text-gray-605")}>
          Key: {signal.reference_column}
        </span>
        <div className={cn("flex items-center gap-3 text-xs", isDark ? "text-gray-400" : "text-gray-600")}>
          <span>Confidence: <span className={cn("font-mono font-semibold", isDark ? "text-white" : "text-gray-900")}>{(signal.confidence * 100).toFixed(0)}%</span></span>
          {signal.value_overlap > 0 && (
            <span>Overlap: <span className={cn("font-mono font-semibold", isDark ? "text-white" : "text-gray-900")}>{(signal.value_overlap * 100).toFixed(0)}%</span></span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   Main Page Component
   ═══════════════════════════════════════════════════════════════════════════════ */

const UnderstandingReport = () => {
  const { id: datasetId } = useParams();
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const fetchReport = useCallback(async () => {
    if (!datasetId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await datasetAPI.getUnderstanding(datasetId);
      const result = res.data;
      if (result.legacy) {
        setData({ legacy: true, message: result.message });
      } else if (!result.understanding) {
        setData({ noData: true });
      } else {
        setData(result);
      }
    } catch (err) {
      if (err.response?.status === 202) {
        setData({ processing: true });
      } else if (err.response?.status === 404) {
        setError('Dataset not found in database registry.');
      } else {
        setError(err.response?.data?.detail || 'Failed to load data understanding report.');
      }
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  useEffect(() => {
    if (data?.processing) {
      const interval = setInterval(fetchReport, 5000);
      return () => clearInterval(interval);
    }
  }, [data?.processing, fetchReport]);

  const { understanding } = data || {};
  const primary = understanding?.primary_object;
  const alternatives = primary?.alternatives || [];
  const ambiguity = primary?.ambiguity;
  const evidenceTrace = primary?.evidence_trace || [];
  const entities = understanding?.entities || [];
  const participants = understanding?.participants || [];
  const referenceSignals = understanding?.reference_signals?.signals || [];

  const maxContribution = useMemo(() => {
    if (evidenceTrace.length === 0) return 0;
    return Math.max(...evidenceTrace.map((t) => t.contribution));
  }, [evidenceTrace]);

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

  /* ── Loading State ─────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div className={cn("flex items-center justify-center min-h-[70vh] transition-colors duration-300", isDark ? "bg-[#0D0D0F]" : "bg-gray-50")}>
        <div className="flex flex-col items-center gap-4 text-center">
          <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
          <p className={cn("text-sm", isDark ? "text-gray-400" : "text-gray-600")}>Analyzing dataset structure and schema...</p>
        </div>
      </div>
    );
  }

  /* ── Error State ───────────────────────────────────────────────────────── */
  if (error) {
    return (
      <div className={cn("flex items-center justify-center min-h-[70vh] transition-colors duration-300", isDark ? "bg-[#0D0D0F]" : "bg-gray-50")}>
        <div className={cn("max-w-md text-center p-6 border rounded-xl shadow-lg", isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200")}>
          <div className="w-12 h-12 mx-auto mb-4 rounded-xl flex items-center justify-center bg-rose-500/10 border border-rose-500/20">
            <AlertTriangle className="w-6 h-6 text-rose-400" />
          </div>
          <h2 className={cn("text-lg font-semibold mb-2", isDark ? "text-white" : "text-gray-900")}>Could not load report</h2>
          <p className={cn("text-sm mb-6", isDark ? "text-gray-400" : "text-gray-600")}>{error}</p>
          <button 
            type="button"
            onClick={() => navigate('/app/workspace')} 
            className={cn(
              "px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 mx-auto transition-all cursor-pointer border",
              isDark 
                ? "bg-white/[0.03] border-white/[0.06] text-white hover:bg-white/[0.08]" 
                : "bg-gray-100 border-gray-300 text-gray-700 hover:bg-gray-250"
            )}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Assets
          </button>
        </div>
      </div>
    );
  }

  /* ── Processing State ──────────────────────────────────────────────────── */
  if (data?.processing) {
    return (
      <div className={cn("flex items-center justify-center min-h-[70vh] transition-colors duration-300", isDark ? "bg-[#0D0D0F]" : "bg-gray-50")}>
        <div className={cn("max-w-md text-center p-6 border rounded-xl shadow-lg", isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200")}>
          <div className="w-14 h-14 mx-auto mb-5 rounded-full flex items-center justify-center bg-orange-500/10 border border-orange-500/20">
            <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
          </div>
          <h2 className={cn("text-lg font-semibold mb-2", isDark ? "text-white" : "text-gray-900")}>Analyzing in progress</h2>
          <p className={cn("text-sm mb-6", isDark ? "text-gray-400" : "text-gray-600")}>
            The understanding pipeline is analyzing columns and references. This page will update automatically.
          </p>
          <button 
            type="button"
            onClick={() => navigate('/app/workspace')} 
            className={cn(
              "px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 mx-auto transition-all cursor-pointer border",
              isDark 
                ? "bg-white/[0.03] border-white/[0.06] text-white hover:bg-white/[0.08]" 
                : "bg-gray-100 border-gray-300 text-gray-750 hover:bg-gray-250"
            )}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Assets
          </button>
        </div>
      </div>
    );
  }

  /* ── Legacy / Empty State ──────────────────────────────────────────────── */
  if (data?.legacy || data?.noData) {
    return (
      <div className={cn("flex items-center justify-center min-h-[70vh] transition-colors duration-300", isDark ? "bg-[#0D0D0F]" : "bg-gray-50")}>
        <div className={cn("max-w-md text-center p-6 border rounded-xl shadow-lg", isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200")}>
          <div className="w-12 h-12 mx-auto mb-4 rounded-xl flex items-center justify-center bg-orange-500/10 border border-orange-500/20">
            <Info className="w-6 h-6 text-orange-500" />
          </div>
          <h2 className={cn("text-lg font-semibold mb-2", isDark ? "text-white" : "text-gray-900")}>Report not available</h2>
          <p className={cn("text-sm mb-6 font-normal", isDark ? "text-gray-400" : "text-gray-650")}>
            {data?.message || 'This dataset was processed before the understanding engine was added. Please reprocess the dataset.'}
          </p>
          <button 
            type="button"
            onClick={() => navigate('/app/workspace')} 
            className="bg-orange-600 hover:bg-orange-500 active:bg-orange-700 text-white px-5 py-2.5 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 mx-auto transition-all cursor-pointer shadow-lg shadow-orange-950/20"
          >
            Go to Assets
          </button>
        </div>
      </div>
    );
  }

  const ambiguityInfo = ambiguity ? AMBIGUITY_COLORS[ambiguity.level] || AMBIGUITY_COLORS.low : AMBIGUITY_COLORS.low;
  const strengthLevel = getStrengthLevel(primary?.evidence_strength || 0);
  const strengthColors = STRENGTH_COLORS[strengthLevel];

  return (
    <motion.div
      className={cn("min-h-full relative overflow-hidden transition-colors duration-300", isDark ? "bg-[#0D0D0F]" : "bg-gray-50")}
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Background ambient lighting */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-orange-500/[0.02] blur-[150px] pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-orange-500/[0.01] blur-[150px] pointer-events-none" />

      <div className="max-w-6xl mx-auto px-6 py-10 relative z-10">

        {/* ── Navigation ── */}
        <motion.div variants={itemVariants} className="mb-6">
          <button
            type="button"
            onClick={() => navigate('/app/workspace')}
            className={cn(
              "inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider transition-colors cursor-pointer",
              isDark ? "text-gray-500 hover:text-white" : "text-gray-500 hover:text-gray-900"
            )}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Assets
          </button>
        </motion.div>

        {/* ── Header ── */}
        <motion.div variants={itemVariants} className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                <span className="text-xs font-semibold uppercase tracking-wider text-orange-500/80">AI Discovery Agent</span>
              </div>
              
              <h1 className={cn("text-3xl font-semibold tracking-tight mb-2", isDark ? "text-white" : "text-gray-900")}>
                Dataset Understanding Report
              </h1>

              <div className={cn("flex flex-wrap items-center gap-3 text-xs", isDark ? "text-gray-400" : "text-gray-600")}>
                <span className={cn("font-semibold", isDark ? "text-white" : "text-gray-900")}>
                  {understanding?.dataset_name || 'Unknown Dataset'}
                </span>
                <span className="w-1 h-1 rounded-full bg-gray-400/50" />
                <span>{formatNumber(understanding?.row_count)} rows</span>
                <span className="w-1 h-1 rounded-full bg-gray-400/50" />
                <span>{understanding?.column_count} columns</span>
                {understanding?.generated_at && (
                  <>
                    <span className="w-1 h-1 rounded-full bg-gray-400/50" />
                    <Clock className="w-3.5 h-3.5 text-gray-450" />
                    <span>Processed {timeAgo(understanding.generated_at)}</span>
                  </>
                )}
              </div>
            </div>
            
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => navigate(`/app/datasets/${datasetId}/profile`)}
                className={cn(
                  "px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition-all cursor-pointer h-[38px] border",
                  isDark 
                    ? "bg-white/[0.03] border-white/[0.06] text-white hover:bg-white/[0.08]" 
                    : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
                )}
              >
                <BarChart3 className="w-3.5 h-3.5" />
                Data Profile
              </button>
              <button
                type="button"
                onClick={() => navigate(`/app/chat?dataset=${datasetId}`)}
                className="bg-orange-600 hover:bg-orange-500 active:bg-orange-700 text-white px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition-all cursor-pointer h-[38px]"
              >
                Chat Analytics
              </button>
            </div>
          </div>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* PRIMARY OBJECT SELECTION */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        <motion.div variants={itemVariants} className="mb-10 space-y-6">
          
          {/* Section Header */}
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-orange-500/10 text-orange-500">
              <Target className="w-4 h-4" />
            </div>
            <span className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
              Primary Schema Classification
            </span>
          </div>

          {/* Unified Hero Banner */}
          <div className={cn(
            "border rounded-2xl p-8 relative overflow-hidden shadow-2xl transition-colors duration-300",
            isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
          )}>
            {/* Subtle glow background */}
            <div className="absolute top-0 right-0 w-80 h-80 bg-orange-500/[0.02] blur-[80px] pointer-events-none" />

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              
              {/* Left Column: Typography & Confidence */}
              <div className="lg:col-span-5 space-y-4">
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-orange-500/80 bg-orange-500/5 px-2.5 py-1 rounded-md border border-orange-500/10">
                    Primary Entity Type
                  </span>
                  {primary && (
                    <span
                      className="px-2.5 py-1 rounded-md text-[9px] font-bold uppercase tracking-widest border"
                      style={{ background: strengthColors.bg, color: strengthColors.text, borderColor: strengthColors.border }}
                    >
                      {getStrengthLabel(primary.evidence_strength)}
                    </span>
                  )}
                </div>
                
                <div>
                  <h2 className={cn("text-4xl font-extrabold tracking-tight capitalize", isDark ? "text-white" : "text-gray-900")}>
                    {primary?.label || 'Unidentified'}
                  </h2>
                  <p className={cn("text-xs mt-1", isDark ? "text-gray-400" : "text-gray-500")}>Detected Schema Structure</p>
                </div>

                <div className={cn("p-4 border rounded-xl", isDark ? "bg-white/[0.015] border-white/[0.04]" : "bg-gray-50 border-gray-200")}>
                  <p className={cn("text-xs leading-relaxed", isDark ? "text-gray-300" : "text-gray-700")}>
                    <strong className={isDark ? "text-white" : "text-gray-950"}>AI Summary:</strong> Signal analyzed your database attributes, naming tags, and patterns to match this dataset structure as <strong className={isDark ? "text-white" : "text-gray-950"}>{primary?.label}</strong>.
                  </p>
                </div>
              </div>

              {/* Center Column: Verification Stats */}
              {primary && (
                <div className={cn(
                  "lg:col-span-4 space-y-4 border-y lg:border-y-0 lg:border-x py-6 lg:py-0 lg:px-8",
                  isDark ? "border-white/[0.04]" : "border-gray-250"
                )}>
                  <h3 className={cn("text-[10px] font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-650")}>
                    Verification Dimensions
                  </h3>
                  
                  <div className="space-y-3">
                    {/* Name Alignment */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className={isDark ? "text-gray-400" : "text-gray-600"}>Name Alignment</span>
                        <span className={cn("font-mono font-semibold", isDark ? "text-white" : "text-gray-900")}>{(primary.table_name_score * 100).toFixed(0)}%</span>
                      </div>
                      <div className={cn("h-1.5 w-full rounded-full overflow-hidden", isDark ? "bg-white/[0.04]" : "bg-gray-200")}>
                        <div className="h-full bg-orange-600" style={{ width: `${(primary.table_name_score * 100).toFixed(0)}%` }} />
                      </div>
                    </div>

                    {/* Key Columns Match */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className={isDark ? "text-gray-400" : "text-gray-600"}>Key Columns Match</span>
                        <span className={cn("font-mono font-semibold", isDark ? "text-white" : "text-gray-900")}>{(primary.column_dominance_score * 100).toFixed(0)}%</span>
                      </div>
                      <div className={cn("h-1.5 w-full rounded-full overflow-hidden", isDark ? "bg-white/[0.04]" : "bg-gray-200")}>
                        <div className="h-full bg-orange-600" style={{ width: `${(primary.column_dominance_score * 100).toFixed(0)}%` }} />
                      </div>
                    </div>

                    {/* Data Pattern Verification */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className={isDark ? "text-gray-400" : "text-gray-600"}>Data Pattern Verification</span>
                        <span className={cn("font-mono font-semibold", isDark ? "text-white" : "text-gray-900")}>{(primary.entity_confidence_score * 100).toFixed(0)}%</span>
                      </div>
                      <div className={cn("h-1.5 w-full rounded-full overflow-hidden", isDark ? "bg-white/[0.04]" : "bg-gray-200")}>
                        <div className="h-full bg-orange-600" style={{ width: `${(primary.entity_confidence_score * 100).toFixed(0)}%` }} />
                      </div>
                    </div>
                  </div>

                  {/* Weight breakdowns */}
                  <div className="space-y-1.5 pt-2">
                    <div className={cn("h-1.5 rounded-full overflow-hidden flex", isDark ? "bg-white/[0.04]" : "bg-gray-200")}>
                      <div style={{ width: '10%', background: '#f97316' }} title="Name Alignment (10%)" />
                      <div style={{ width: '45%', background: '#8b5cf6' }} title="Columns Match (45%)" />
                      <div style={{ width: '45%', background: '#10b981' }} title="Pattern Verification (45%)" />
                    </div>
                    
                    <div className={cn("flex justify-between text-[9px] font-mono", isDark ? "text-gray-500" : "text-gray-600")}>
                      <span>Name (10%)</span>
                      <span>Columns (45%)</span>
                      <span>Patterns (45%)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Right Column: Large Circular Gauge */}
              <div className="lg:col-span-3 flex flex-col items-center justify-center">
                <StrengthGauge score={primary?.evidence_strength || 0} size={110} />
                <span className={cn("text-[10px] font-bold uppercase tracking-wider mt-3", isDark ? "text-gray-400" : "text-gray-600")}>
                  Overall Match Score
                </span>
              </div>

            </div>
          </div>

          {/* Supporting Details Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* Columns & Roles (Left) */}
            <div className={cn(
              "border rounded-xl p-6 flex flex-col justify-between transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                    Detected Columns &amp; Roles
                  </span>
                  <span className={cn("text-[10px] font-mono border px-2 py-0.5 rounded", isDark ? "bg-white/[0.02] border-white/[0.04] text-gray-500" : "bg-gray-100 border-gray-250 text-gray-600")}>
                    {evidenceTrace.length} key columns
                  </span>
                </div>
                
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                  {evidenceTrace.map((trace) => (
                    <EvidenceBar
                      key={trace.column_name}
                      column_name={trace.column_name}
                      role={trace.role}
                      contribution={trace.contribution}
                      maxContribution={maxContribution}
                    />
                  ))}
                </div>
              </div>
              
              <div className={cn("border-t pt-4 mt-4 text-[11px] leading-relaxed", isDark ? "border-white/[0.03] text-gray-500" : "border-gray-200 text-gray-600")}>
                This lists the specific columns that matched standard business entities, outlining their detected role and weight contribution to the schema classification model.
              </div>
            </div>

            {/* Stability & Competing Schemas (Right) */}
            <div className={cn(
              "border rounded-xl p-6 flex flex-col justify-between transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <div className="space-y-5">
                <div className="flex items-center justify-between">
                  <span className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                    Classification Stability
                  </span>
                  {ambiguity && (
                    <span
                      className="px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest border"
                      style={{ background: ambiguityInfo.bg, color: ambiguityInfo.text, borderColor: ambiguityInfo.border }}
                    >
                      {ambiguityInfo.label}
                    </span>
                  )}
                </div>

                {ambiguity && (
                  <div className="p-4 rounded-lg text-xs leading-relaxed" style={{ background: ambiguityInfo.bg, color: ambiguityInfo.text, border: `1px solid ${ambiguityInfo.border}` }}>
                    {ambiguity.level === 'low' 
                      ? 'Signal verified this classification is highly stable. No competing datasets matched this schema.'
                      : ambiguity.level === 'medium'
                      ? 'Minor classification conflict. Check alternative schemas listed below.'
                      : 'High conflict. Multiple alternative schemas closely fit this dataset.'
                    }
                  </div>
                )}

                {ambiguity && (
                  <div className={cn("grid grid-cols-2 gap-4 border rounded-xl p-4 text-xs", isDark ? "bg-white/[0.015] border-white/[0.04]" : "bg-gray-50 border-gray-200")}>
                    <div>
                      <span className={isDark ? "text-gray-400" : "text-gray-650"}>Confidence Margin</span>
                      <p className={cn("text-xl font-bold font-mono mt-1", isDark ? "text-white" : "text-gray-900")}>
                        {(ambiguity.top_gap * 100).toFixed(0)}%
                      </p>
                    </div>
                    <div>
                      <span className={isDark ? "text-gray-400" : "text-gray-650"}>Alternative Options</span>
                      <p className={cn("text-xl font-bold font-mono mt-1", isDark ? "text-white" : "text-gray-900")}>
                        {ambiguity.alternative_count} schemas
                      </p>
                    </div>
                  </div>
                )}

                {/* Alternatives List */}
                {alternatives.length > 0 && (
                  <div className="space-y-3">
                    <h4 className={cn("text-[10px] font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                      Competing Match Candidates
                    </h4>
                    <div className="space-y-2 max-h-[120px] overflow-y-auto pr-1">
                      {alternatives.map((alt, idx) => (
                        <AlternativeCard key={alt.label} alt={alt} index={idx} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

          </div>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* ENTITIES & PARTICIPANTS */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        <motion.div variants={itemVariants} className="mb-8">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="p-1.5 rounded-lg bg-orange-500/10 text-orange-500">
              <Layers className="w-4 h-4" />
            </div>
            <span className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
              Discovered Entities &amp; Relationships
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Participants */}
            <div className={cn(
              "border rounded-xl p-5 transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <div className="flex items-center justify-between mb-4">
                <span className={cn("text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                  Secondary Participants
                </span>
                {participants.length > 0 && (
                  <span className={cn("text-[10px]", isDark ? "text-gray-500" : "text-gray-600")}>
                    {participants.filter(p => p.is_valid).length} valid relationships
                  </span>
                )}
              </div>
              {participants.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Users className={cn("w-8 h-8 mb-2", isDark ? "text-gray-600" : "text-gray-400")} />
                  <p className={cn("text-xs max-w-xs leading-relaxed", isDark ? "text-gray-400" : "text-gray-600")}>
                    {primary?.is_valid ? 'No secondary participating entities detected. This dataset represents a standalone business entity.' : 'No primary object detected.'}
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                  {participants.map((p) => (
                    <ParticipantCard key={p.label} participant={p} />
                  ))}
                </div>
              )}
            </div>

            {/* All Discovered Schemas */}
            <div className={cn(
              "border rounded-xl p-5 transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <div className="flex items-center justify-between mb-4">
                <span className={cn("text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                  All Discovered Schemas
                </span>
                <span className={cn("text-[10px] font-mono", isDark ? "text-gray-550" : "text-gray-600")}>
                  {entities.length} detected
                </span>
              </div>
              {entities.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Database className={cn("w-8 h-8 mb-2", isDark ? "text-gray-600" : "text-gray-400")} />
                  <p className={cn("text-xs", isDark ? "text-gray-400" : "text-gray-600")}>No entities discovered in dataset layout.</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                  {entities.map((e) => (
                    <div
                      key={e.label}
                      className={cn(
                        "flex items-center justify-between px-3.5 py-3 rounded-lg border",
                        isDark ? "bg-[#0D0D0F] border-white/[0.04]" : "bg-gray-50 border-gray-200"
                      )}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        {e.label === primary?.label && (
                          <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                        )}
                        <span className={cn("text-sm font-semibold capitalize", isDark ? "text-white" : "text-gray-900")}>
                          {e.label}
                        </span>
                        <span className={cn("text-[10px] font-mono", isDark ? "text-gray-500" : "text-gray-600")}>
                          {e.columns?.length || 0} columns
                        </span>
                      </div>
                      <div className={cn("flex items-center gap-3 text-xs", isDark ? "text-gray-400" : "text-gray-600")}>
                        {e.identifier_column && (
                          <span className="font-mono text-[10px] text-orange-600/80">
                            Key: {e.identifier_column}
                          </span>
                        )}
                        <span className={cn("font-mono tabular-nums font-semibold", isDark ? "text-white" : "text-gray-900")}>{(e.entity_confidence * 100).toFixed(0)}% match</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </motion.div>

        {/* ── Reference Signals ── */}
        {referenceSignals.length > 0 && (
          <motion.div variants={itemVariants} className="mb-8">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="p-1.5 rounded-lg bg-orange-500/10 text-orange-500">
                <Link2 className="w-4 h-4" />
              </div>
              <span className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                Foreign Reference Connections
              </span>
            </div>

            <div className={cn(
              "border rounded-xl p-5 transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <div className="space-y-2">
                {referenceSignals.map((s, idx) => (
                  <ReferenceSignalCard key={`${s.reference_column}-${idx}`} signal={s} />
                ))}
              </div>
              {understanding?.reference_signals?.precision != null && (
                <div className={cn("flex items-center gap-4 mt-4 pt-3 border-t text-xs", isDark ? "border-white/[0.03] text-gray-500" : "border-gray-200 text-gray-600")}>
                  <span>Reference Precision: <span className={cn("font-mono font-semibold", isDark ? "text-white" : "text-gray-900")}>{(understanding.reference_signals.precision * 100).toFixed(0)}%</span></span>
                  <span>Total Keys Validated: <span className={cn("font-mono font-semibold", isDark ? "text-white" : "text-gray-900")}>{understanding.reference_signals.reference_count}</span></span>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* ── Data Quality ── */}
        <motion.div variants={itemVariants} className="mb-12">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="p-1.5 rounded-lg bg-orange-500/10 text-orange-500">
              <PieChart className="w-4 h-4" />
            </div>
            <span className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
              Data Quality &amp; Schema Health
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className={cn(
              "border rounded-xl p-5 text-center transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <span className="text-3xl font-bold tabular-nums text-emerald-600">
                {understanding?.data_quality_score != null ? `${understanding.data_quality_score.toFixed(0)}%` : '—'}
              </span>
              <p className="text-xs text-gray-500 mt-1.5 uppercase tracking-wider font-semibold">Column Coverage</p>
            </div>
            <div className={cn(
              "border rounded-xl p-5 text-center transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <span className="text-3xl font-bold tabular-nums text-emerald-600">
                {understanding?.trust_score != null ? `${understanding.trust_score.toFixed(0)}%` : '—'}
              </span>
              <p className="text-xs text-gray-500 mt-1.5 uppercase tracking-wider font-semibold">System Trust Score</p>
            </div>
            <div className={cn(
              "border rounded-xl p-5 text-center transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <span className={cn("text-3xl font-bold tabular-nums", isDark ? "text-white" : "text-gray-900")}>
                {understanding?.quality_summary?.missing_values != null ? formatNumber(understanding.quality_summary.missing_values) : '—'}
              </span>
              <p className="text-xs text-gray-500 mt-1.5 uppercase tracking-wider font-semibold">Missing Cell Values</p>
            </div>
            <div className={cn(
              "border rounded-xl p-5 text-center transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200 shadow-sm"
            )}>
              <span className={cn("text-3xl font-bold tabular-nums", isDark ? "text-white" : "text-gray-900")}>
                {understanding?.quality_summary?.duplicate_rows != null ? formatNumber(understanding.quality_summary.duplicate_rows) : '—'}
              </span>
              <p className="text-xs text-gray-500 mt-1.5 uppercase tracking-wider font-semibold">Duplicate Records</p>
            </div>
          </div>
        </motion.div>

      </div>
    </motion.div>
  );
};

export default UnderstandingReport;
