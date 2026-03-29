/**
 * AgenticPanel
 * ============
 * Right-side slide-in panel for the Chat page that exposes the full
 * Subjective Novelty Detection + dashboard generation pipeline.
 *
 * Panels (tab-switched):
 *  1. "Analyse"      – triggers /agentic/analyze, shows novelty-scored
 *                      insight cards + filtered cards in audit mode
 *  2. "Belief Graph" – calls GET /agentic/beliefs, lists all beliefs
 *                      with confidence bars, source tags, delete control
 *  3. "Charts"       – renders viz_configs returned by the pipeline
 *                      as Plotly charts in a bento grid
 */

import React, { useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Plot from 'react-plotly.js';
import {
  Brain, DatabaseZap, BarChart3, X, ChevronDown, ChevronUp,
  ThumbsUp, EyeOff, Trash2, RefreshCw, Filter, Sparkles,
  Shield, AlertTriangle, CheckCircle2, Loader2, Info,
} from 'lucide-react';
import { agenticAPI } from '@/services/api';
import { toast } from 'react-hot-toast';

// ─── helpers ─────────────────────────────────────────────────────────────────

const scoreColor = (n) => {
  if (n >= 0.70) return { bg: 'bg-emerald-500/15', border: 'border-emerald-500/40', text: 'text-emerald-400', dot: 'bg-emerald-400' };
  if (n >= 0.35) return { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', dot: 'bg-amber-400' };
  return { bg: 'bg-elevated/60', border: 'border-border/30', text: 'text-muted', dot: 'bg-muted' };
};

const sourceLabel = {
  user_dismissed: { label: 'Already knew', color: 'text-amber-300 bg-amber-500/10 border-amber-500/20' },
  user_accepted: { label: 'Useful', color: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20' },
  document_ingested: { label: 'Document', color: 'text-sky-300 bg-sky-500/10 border-sky-500/20' },
};

const insightTypeIcon = (type) => {
  const t = (type || '').toLowerCase();
  if (t.includes('anom')) return <AlertTriangle size={13} className="text-rose-400" />;
  if (t.includes('corr')) return <BarChart3 size={13} className="text-violet-400" />;
  return <Sparkles size={13} className="text-sky-400" />;
};

// theme-aware plotly template
const getChartLayout = (title = '') => {
  const isDark = document.documentElement.classList.contains('dark');
  const palette = isDark ? {
    grid: 'rgba(255,255,255,0.06)',
    tick: '#64748b',
    title: '#e2e8f0',
    font: '#94a3b8'
  } : {
    grid: '#e2e8f0',
    tick: '#94a3b8',
    title: '#334155',
    font: '#64748b'
  };

  return {
    title: { text: title, font: { color: palette.title, size: 13 } },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: palette.font, size: 11 },
    margin: { t: 36, b: 40, l: 44, r: 12 },
    xaxis: { gridcolor: palette.grid, color: palette.tick, tickfont: { size: 10 } },
    yaxis: { gridcolor: palette.grid, color: palette.tick, tickfont: { size: 10 } },
    showlegend: false,
  };
};

// ─── sub-components ──────────────────────────────────────────────────────────

/** A single insight card (presented or filtered) */
const InsightCard = ({ insight, filtered = false, onFeedback }) => {
  const [expanded, setExpanded] = useState(false);
  const score = insight.novelty_score ?? 0;
  const { bg, border, text, dot } = scoreColor(score);
  const pVal = insight.p_value != null ? insight.p_value.toFixed(3) : null;
  const eff = insight.effect_size != null ? insight.effect_size.toFixed(2) : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: filtered ? 0.48 : 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`rounded-xl border ${border} ${bg} p-3 mb-2 ${filtered ? 'grayscale-[30%]' : ''}`}
    >
      {/* header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          {insightTypeIcon(insight.type)}
          <span className={`text-[11px] font-semibold uppercase tracking-wider ${filtered ? 'text-muted' : 'text-secondary'}`}>
            {insight.type || 'insight'}
          </span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {/* novelty badge */}
          <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border ${border} ${text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
            {score.toFixed(2)}
          </span>
          <button onClick={() => setExpanded(e => !e)} className="text-slate-500 hover:text-slate-300 p-0.5 transition-colors">
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>
      </div>

      {/* description */}
      <p className={`text-[13px] leading-[1.55] mt-1.5 ${filtered ? 'text-muted' : 'text-header'}`}>
        {insight.description || insight.summary || '—'}
      </p>

      {/* filtered: show matched belief */}
      {filtered && insight.similar_to && (
        <div className="mt-1.5 flex items-start gap-1.5 text-[11px] text-muted">
          <Info size={11} className="mt-0.5 shrink-0" />
          <span>Matched: <em className="text-secondary">"{insight.similar_to.slice(0, 80)}…"</em></span>
        </div>
      )}

      {/* expandable sub-scores */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 pt-2 border-t border-border/40 space-y-1">
              {pVal != null && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted">p-value</span>
                  <span className="text-secondary font-mono">{pVal}</span>
                </div>
              )}
              {eff != null && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted">Effect size</span>
                  <span className="text-secondary font-mono">{eff}</span>
                </div>
              )}
              {insight.semantic_surprisal != null && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted">Semantic surprisal</span>
                  <span className="text-secondary font-mono">{insight.semantic_surprisal.toFixed(2)}</span>
                </div>
              )}
              {insight.bayesian_surprise != null && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted">Bayesian surprise</span>
                  <span className="text-secondary font-mono">{insight.bayesian_surprise.toFixed(2)}</span>
                </div>
              )}
            </div>

            {/* feedback — only on presented cards */}
            {!filtered && onFeedback && (
              <div className="mt-2 flex items-center gap-3 pt-1">
                <button
                  onClick={() => onFeedback('useful', insight)}
                  title="Useful"
                  className="flex items-center gap-1 text-[11px] text-muted hover:text-emerald-400 transition-colors"
                >
                  <ThumbsUp size={13} /> Useful
                </button>
                <button
                  onClick={() => onFeedback('known', insight)}
                  title="Already knew this"
                  className="flex items-center gap-1 text-[11px] text-muted hover:text-amber-400 transition-colors"
                >
                  <EyeOff size={13} /> Already knew
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

/** Belief Graph panel listing all stored beliefs */
const BeliefGraphTab = ({ userId }) => {
  const [beliefs, setBeliefs] = useState(null);
  const [loading, setLoading] = useState(false);
  const loadedRef = useRef(false);

  const load = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await agenticAPI.listBeliefs();
      setBeliefs(res.data?.beliefs || []);
      loadedRef.current = true;
    } catch {
      toast.error('Could not load beliefs');
    } finally {
      setLoading(false);
    }
  }, [loading]);

  // auto-load on first render
  React.useEffect(() => {
    if (!loadedRef.current) load();
  }, []);

  const handleDelete = async (id) => {
    try {
      await agenticAPI.deleteBelief(id);
      setBeliefs(b => b.filter(x => x.id !== id));
      toast.success('Belief removed');
    } catch {
      toast.error('Could not delete belief');
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted">
        <Loader2 size={22} className="animate-spin" />
        <span className="text-sm">Loading beliefs…</span>
      </div>
    );
  }

  if (!beliefs) return null;

  if (beliefs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted text-center px-6">
        <Brain size={28} className="opacity-30" />
        <p className="text-sm">No beliefs yet.</p>
        <p className="text-xs leading-relaxed">
          Click <strong className="text-amber-400">Already knew</strong> or <strong className="text-emerald-400">Useful</strong> on any insight card to start building your Belief Graph.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-muted">{beliefs.length} belief{beliefs.length !== 1 ? 's' : ''} stored</span>
        <button onClick={load} className="flex items-center gap-1 text-[11px] text-muted hover:text-secondary transition-colors">
          <RefreshCw size={11} /> Refresh
        </button>
      </div>

      {beliefs.map((b, i) => {
        const conf = typeof b.confidence === 'number' ? b.confidence : (b.metadata?.confidence ?? 0.8);
        const confDecayed = typeof b.confidence_decayed === 'number' ? b.confidence_decayed : conf;
        const src = b.metadata?.source || b.source || 'user_confirmed';
        const tag = sourceLabel[src] || { label: src, color: 'text-slate-400 bg-slate-800 border-slate-700' };
        const stale = confDecayed < 0.3;

        return (
          <motion.div
            key={b.id || i}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: stale ? 0.4 : 1, y: 0 }}
            transition={{ delay: i * 0.03 }}
            className={`rounded-xl border p-3 ${stale ? 'border-border bg-surface/40' : 'border-border bg-elevated/40'}`}
          >
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <p className={`text-[12px] leading-[1.5] ${stale ? 'text-muted' : 'text-header'}`}>
                  {b.document || b.text || '—'}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${tag.color}`}>
                    {tag.label}
                  </span>
                  {stale && (
                    <span className="text-[10px] text-muted italic">Stale</span>
                  )}
                </div>

                {/* confidence bar */}
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex-1 h-1 rounded-full bg-border/60">
                    <div
                      className={`h-1 rounded-full transition-all ${confDecayed >= 0.7 ? 'bg-emerald-500' : confDecayed >= 0.4 ? 'bg-amber-500' : 'bg-muted'}`}
                      style={{ width: `${Math.min(100, confDecayed * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-muted tabular-nums w-7 text-right">
                    {(confDecayed * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              <button
                onClick={() => handleDelete(b.id)}
                className="shrink-0 p-1 text-muted hover:text-rose-400 transition-colors rounded"
                title="Remove belief"
              >
                <Trash2 size={13} />
              </button>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
};

/** Render viz_configs as plotly charts */
const ChartsTab = ({ vizConfigs }) => {
  if (!vizConfigs || vizConfigs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted text-center px-6">
        <BarChart3 size={28} className="opacity-30" />
        <p className="text-sm">No charts yet.</p>
        <p className="text-xs">Run an analysis to generate visualisations from the pipeline.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {vizConfigs.map((cfg, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.06 }}
          className="rounded-xl border border-border bg-surface/60 overflow-hidden"
        >
          <Plot
            data={cfg.data || []}
            layout={{
              ...getChartLayout(cfg.layout?.title?.text || cfg.title || `Chart ${i + 1}`),
              ...(cfg.layout || {}),
              paper_bgcolor: 'rgba(0,0,0,0)',
              plot_bgcolor: 'rgba(0,0,0,0)',
              height: 220,
              margin: { t: 36, b: 40, l: 44, r: 12 },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%' }}
          />
        </motion.div>
      ))}
    </div>
  );
};

// ─── main component ───────────────────────────────────────────────────────────

const TABS = [
  { id: 'analyse', label: 'Analyse', icon: Brain },
  { id: 'beliefs', label: 'Belief Graph', icon: DatabaseZap },
  { id: 'charts', label: 'Charts', icon: BarChart3 },
];

const AgenticPanel = ({ datasetId, onClose }) => {
  const [activeTab, setActiveTab] = useState('analyse');

  // analysis state
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);   // { novel, filtered, stats, vizConfigs }
  const [showFiltered, setShowFiltered] = useState(false);
  const [noveltyThreshold, setNoveltyThreshold] = useState(0.35);

  const runAnalysis = async () => {
    if (!datasetId) { toast.error('Select a dataset first'); return; }
    setRunning(true);
    setResult(null);
    try {
      const res = await agenticAPI.runAnalysis(datasetId, { novelty_threshold: noveltyThreshold });
      const d = res.data;
      setResult({
        novel: d.novel_insights || [],
        filtered: d.filtered_insights || [],
        stats: d.stats || {},
        vizConfigs: d.viz_configs || [],
        response: d.final_response || '',
      });
      toast.success(`Analysis complete — ${d.novel_insights?.length ?? 0} novel insights found`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Analysis failed');
    } finally {
      setRunning(false);
    }
  };

  const handleFeedback = async (type, insight) => {
    try {
      await agenticAPI.submitFeedback({
        insight_text: insight.description || insight.summary || '',
        feedback_type: type,
        dataset_id: datasetId,
      });
      const opt = type === 'useful' ? 'Noted as valuable' : "Won't repeat similar insights";
      toast.success(opt, { duration: 2200 });
    } catch {
      toast.error('Feedback failed');
    }
  };

  return (
    <motion.div
      initial={{ x: 380, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 380, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 340, damping: 32 }}
      className="fixed top-0 right-0 h-full w-[370px] z-50 flex flex-col bg-surface border-l border-border shadow-2xl shadow-black/20"
    >
      {/* ── header ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-violet-400" />
          <span className="text-sm font-semibold text-header">DataSage SND</span>
        </div>
        <button onClick={onClose} className="p-1 text-muted hover:text-secondary transition-colors rounded">
          <X size={16} />
        </button>
      </div>

      {/* ── tabs ── */}
      <div className="flex border-b border-border">
        {TABS.map(t => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[11px] font-semibold transition-colors
                ${active
                  ? 'text-violet-300 border-b-2 border-violet-400'
                  : 'text-muted hover:text-secondary border-b-2 border-transparent'
                }`}
            >
              <Icon size={13} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* ── body ── */}
      <div className="flex-1 overflow-y-auto px-4 py-3 scrollbar-thin scrollbar-thumb-muted/30 scrollbar-track-transparent">

        {/* ╔═ ANALYSE TAB ══════════════════════════════════════════════════╗ */}
        {activeTab === 'analyse' && (
          <div>
            {/* controls */}
            <div className="flex items-center gap-2 mb-3">
              <div className="flex-1">
                <label className="text-[10px] text-muted mb-1 block">Novelty threshold: <strong className="text-secondary">{noveltyThreshold.toFixed(2)}</strong></label>
                <input
                  type="range" min="0.10" max="0.90" step="0.05"
                  value={noveltyThreshold}
                  onChange={e => setNoveltyThreshold(Number(e.target.value))}
                  className="w-full accent-violet-500 h-1"
                />
              </div>
              <button
                onClick={runAnalysis}
                disabled={running || !datasetId}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-semibold bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white transition-colors shrink-0"
              >
                {running
                  ? <><Loader2 size={13} className="animate-spin" /> Running…</>
                  : <><Sparkles size={13} /> Analyse</>
                }
              </button>
            </div>

            {/* stats banner */}
            {result && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="mb-3 p-2.5 rounded-xl bg-elevated/60 border border-border grid grid-cols-3 gap-2 text-center"
              >
                {[
                  { label: 'Generated', val: result.stats.total_questions ?? (result.novel.length + result.filtered.length) },
                  { label: 'Presented', val: result.novel.length, color: 'text-emerald-400' },
                  { label: 'Filtered', val: result.filtered.length, color: 'text-amber-400' },
                ].map(s => (
                  <div key={s.label}>
                    <div className={`text-lg font-bold ${s.color || 'text-header'}`}>{s.val}</div>
                    <div className="text-[10px] text-muted">{s.label}</div>
                  </div>
                ))}
              </motion.div>
            )}

            {/* running skeleton */}
            {running && (
              <div className="space-y-2 mt-2">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-16 rounded-xl bg-elevated animate-pulse border border-border" />
                ))}
                <p className="text-center text-xs text-muted mt-3">Running QUIS pipeline…</p>
              </div>
            )}

            {/* insight cards */}
            {result && !running && (
              <>
                {result.novel.length === 0 && result.filtered.length === 0 && (
                  <p className="text-sm text-muted text-center py-8">No insights generated — try a larger dataset.</p>
                )}

                {result.novel.map((ins, i) => (
                  <InsightCard key={i} insight={ins} onFeedback={handleFeedback} />
                ))}

                {/* filtered toggle */}
                {result.filtered.length > 0 && (
                  <>
                    <button
                      onClick={() => setShowFiltered(f => !f)}
                      className="flex items-center gap-1.5 text-[11px] text-muted hover:text-secondary transition-colors mt-1 mb-2"
                    >
                      <Filter size={12} />
                      {showFiltered ? 'Hide' : 'Show'} {result.filtered.length} filtered insight{result.filtered.length !== 1 ? 's' : ''}
                      {showFiltered ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    </button>

                    <AnimatePresence>
                      {showFiltered && result.filtered.map((ins, i) => (
                        <InsightCard key={`f-${i}`} insight={ins} filtered />
                      ))}
                    </AnimatePresence>
                  </>
                )}
              </>
            )}

            {/* empty pre-run state */}
            {!result && !running && (
              <div className="flex flex-col items-center justify-center py-14 gap-3 text-muted text-center">
                <Brain size={32} className="opacity-20" />
                <p className="text-sm">Run an analysis to surface novel insights filtered against your Belief Graph.</p>
              </div>
            )}
          </div>
        )}

        {/* ╔═ BELIEF GRAPH TAB ═════════════════════════════════════════════╗ */}
        {activeTab === 'beliefs' && <BeliefGraphTab />}

        {/* ╔═ CHARTS TAB ═══════════════════════════════════════════════════╗ */}
        {activeTab === 'charts' && (
          <ChartsTab vizConfigs={result?.vizConfigs} />
        )}
      </div>

      {/* ── footer credit ── */}
      <div className="px-4 py-2 border-t border-border flex items-center gap-1.5">
        <CheckCircle2 size={12} className="text-emerald-500/60" />
        <span className="text-[10px] text-slate-600">Powered by ChromaDB · BGE-large-en-v1.5 · LangGraph</span>
      </div>
    </motion.div>
  );
};

export default AgenticPanel;
