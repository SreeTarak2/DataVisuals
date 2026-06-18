/**
 * AgenticPanel
 * ============
 * Right-side panel that runs the 6-agent EDA pipeline and streams
 * live progress via Server-Sent Events.
 *
 * Tabs:
 *  1. Analyse  — triggers /agentic/analyze, streams agent progress,
 *                shows univariate findings + bivariate relationships
 *  2. Charts   — chart config cards from the visualization agent
 *  3. Belief   — stored beliefs (unchanged from prior implementation)
 */

import React, { useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, BarChart3, X, ChevronDown, ChevronUp,
  Trash2, RefreshCw, Sparkles, CheckCircle2, Loader2,
  AlertCircle, TrendingUp, Activity, Eye, DatabaseZap,
  ArrowRightLeft, Lightbulb, PieChart, ScatterChart,
  LineChart, BarChart2,
} from 'lucide-react';
import { agenticAPI } from '@/services/api';
import { toast } from 'react-hot-toast';

// ─── constants ────────────────────────────────────────────────────────────────

const AGENTS = [
  { id: 'planner',           label: 'Planner',           desc: 'Planning analysis…' },
  { id: 'data_understanding',label: 'Data Understanding',desc: 'Understanding your data…' },
  { id: 'univariate',        label: 'Univariate',        desc: 'Exploring each column…' },
  { id: 'bivariate',         label: 'Bivariate',         desc: 'Finding relationships…' },
  { id: 'visualization',     label: 'Visualization',     desc: 'Selecting best charts…' },
  { id: 'critic',            label: 'Critic / QA',       desc: 'Validating results…' },
];

const CHART_ICONS = {
  bar: BarChart2, line: LineChart, scatter: ScatterChart,
  histogram: Activity, box: Activity, heatmap: PieChart, pie: PieChart,
};

// ─── helpers ──────────────────────────────────────────────────────────────────

const strengthColor = (s) => {
  if (s === 'strong')   return 'text-green-700 bg-green-50 border-green-200';
  if (s === 'moderate') return 'text-yellow-700 bg-yellow-50 border-yellow-200';
  return                       'text-gray-700 bg-gray-50 border-gray-200';
};

const directionIcon = (d) => {
  if (!d) return null;
  if (d === 'positive')    return <TrendingUp size={11} className="text-green-700" />;
  if (d === 'negative')    return <TrendingUp size={11} className="rotate-180 text-red-700" />;
  if (d === 'non-linear')  return <Activity size={11} className="text-orange-700" />;
  return <ArrowRightLeft size={11} className="text-blue-700" />;
};

// parse SSE lines from a text chunk
function* parseSseChunk(text, buffer) {
  const lines = (buffer + text).split('\n');
  for (let i = 0; i < lines.length - 1; i++) {
    const line = lines[i].trim();
    if (line.startsWith('data: ')) {
      try { yield JSON.parse(line.slice(6)); } catch { /* skip malformed */ }
    }
  }
  return lines[lines.length - 1]; // leftover for next chunk
}

// ─── sub-components ──────────────────────────────────────────────────────────

const AgentRow = ({ agent, status, label }) => {
  const statusIcon = {
    idle:    <span className="w-2 h-2 rounded-full bg-border/60 shrink-0" />,
    running: <Loader2 size={13} className="text-orange-700 animate-spin shrink-0" />,
    done:    <CheckCircle2 size={13} className="text-green-700 shrink-0" />,
    error:   <AlertCircle size={13} className="text-red-700 shrink-0" />,
  }[status] || null;

  return (
    <motion.div
      initial={{ opacity: 0.4 }}
      animate={{ opacity: status === 'idle' ? 0.45 : 1 }}
      className="flex items-center gap-2.5 py-1.5"
    >
      {statusIcon}
      <div className="flex-1 min-w-0">
        <span className={`text-[12px] font-medium ${
          status === 'done'    ? 'text-secondary' :
          status === 'running' ? 'text-orange-700' :
          status === 'error'   ? 'text-red-700'  : 'text-muted'
        }`}>
          {agent.label}
        </span>
        {status === 'running' && label && (
          <p className="text-[10px] text-muted mt-0.5">{label}</p>
        )}
      </div>
    </motion.div>
  );
};

const FindingCard = ({ finding }) => (
  <motion.div
    initial={{ opacity: 0, y: 4 }}
    animate={{ opacity: 1, y: 0 }}
    className="rounded-xl border border-border bg-elevated/40 p-3 mb-2"
  >
    <div className="flex items-center gap-1.5 mb-1">
      <Activity size={11} className="text-blue-700 shrink-0" />
      <span className="text-[10px] font-semibold text-muted uppercase tracking-wider">
        {finding.column}
      </span>
      {finding.dtype && (
        <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface border border-border text-muted font-mono">
          {finding.dtype}
        </span>
      )}
    </div>
    <p className="text-[12px] text-header leading-[1.5]">{finding.finding}</p>
  </motion.div>
);

const RelationshipCard = ({ rel, index }) => {
  const cols = (rel.columns || []).join(' ↔ ');
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className="rounded-xl border border-border bg-elevated/40 p-3 mb-2"
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          {directionIcon(rel.direction)}
          <span className="text-[11px] font-semibold text-sky-300 truncate font-mono">{cols}</span>
        </div>
        {rel.strength && (
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border shrink-0 ${strengthColor(rel.strength)}`}>
            {rel.strength}
          </span>
        )}
      </div>
      <p className="text-[12px] text-header leading-[1.5]">{rel.relationship}</p>
      {rel.business_implication && (
        <p className="text-[11px] text-muted mt-1 leading-[1.4]">{rel.business_implication}</p>
      )}
    </motion.div>
  );
};

const ChartConfigCard = ({ cfg, index }) => {
  const [expanded, setExpanded] = useState(false);
  const Icon = CHART_ICONS[cfg.chart_type] || BarChart3;
  const cols = [cfg.x, cfg.y, cfg.color].filter(Boolean);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="rounded-xl border border-border bg-elevated/40 p-3 mb-2"
    >
      <div className="flex items-start gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center shrink-0">
          <Icon size={15} className="text-orange-700" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[12px] font-semibold text-header leading-snug">{cfg.title || 'Chart'}</p>
          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            <span className="text-[10px] font-mono text-orange-300 bg-orange-500/10 px-1.5 py-0.5 rounded">
              {cfg.chart_type}
            </span>
            {cols.map(c => (
              <span key={c} className="text-[10px] font-mono text-slate-400 bg-surface border border-border px-1.5 py-0.5 rounded">
                {c}
              </span>
            ))}
            {cfg.aggregation && cfg.aggregation !== 'none' && (
              <span className="text-[10px] text-muted">agg:{cfg.aggregation}</span>
            )}
          </div>
        </div>
        <button
          onClick={() => setExpanded(e => !e)}
          className="p-0.5 text-muted hover:text-secondary transition-colors shrink-0"
        >
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
      </div>

      <AnimatePresence>
        {expanded && cfg.rationale && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 pt-2 border-t border-border/40 flex items-start gap-1.5">
              <Lightbulb size={11} className="text-yellow-700 mt-0.5 shrink-0" />
              <p className="text-[11px] text-muted leading-[1.5]">{cfg.rationale}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

const BeliefGraphTab = () => {
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

  React.useEffect(() => { if (!loadedRef.current) load(); }, []);

  const handleDelete = async (id) => {
    try {
      await agenticAPI.deleteBelief(id);
      setBeliefs(b => b.filter(x => x.id !== id));
      toast.success('Belief removed');
    } catch {
      toast.error('Could not delete belief');
    }
  };

  if (loading) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted">
      <Loader2 size={22} className="animate-spin" />
      <span className="text-sm">Loading beliefs…</span>
    </div>
  );

  if (!beliefs) return null;

  if (beliefs.length === 0) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted text-center px-6">
      <Brain size={28} className="opacity-30" />
      <p className="text-sm">No beliefs stored yet.</p>
    </div>
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-muted">{beliefs.length} belief{beliefs.length !== 1 ? 's' : ''}</span>
        <button onClick={load} className="flex items-center gap-1 text-[11px] text-muted hover:text-secondary transition-colors">
          <RefreshCw size={11} /> Refresh
        </button>
      </div>
      {beliefs.map((b, i) => {
        const conf = typeof b.confidence === 'number' ? b.confidence : (b.metadata?.confidence ?? 0.8);
        return (
          <div key={b.id || i} className="rounded-xl border border-border bg-elevated/40 p-3">
            <div className="flex items-start gap-2">
              <p className="flex-1 text-[12px] text-header leading-[1.5]">{b.document || b.text || '—'}</p>
              <button
                onClick={() => handleDelete(b.id)}
                className="shrink-0 p-1 text-muted hover:text-red-700 transition-colors"
              >
                <Trash2 size={13} />
              </button>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <div className="flex-1 h-1 rounded-full bg-border/60">
                <div
                  className={`h-1 rounded-full ${conf >= 0.7 ? 'bg-emerald-500' : conf >= 0.4 ? 'bg-amber-500' : 'bg-muted'}`}
                  style={{ width: `${Math.min(100, conf * 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-muted tabular-nums w-7 text-right">{(conf * 100).toFixed(0)}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ─── main component ───────────────────────────────────────────────────────────

const INITIAL_AGENT_STATUS = Object.fromEntries(AGENTS.map(a => [a.id, 'idle']));
const TABS = [
  { id: 'analyse', label: 'Analyse',     icon: Brain },
  { id: 'charts',  label: 'Charts',      icon: BarChart3 },
  { id: 'beliefs', label: 'Belief Graph',icon: DatabaseZap },
];

const AgenticPanel = ({ datasetId, onClose }) => {
  const [activeTab, setActiveTab] = useState('analyse');
  const [running, setRunning]     = useState(false);
  const [agentStatus, setAgentStatus] = useState(INITIAL_AGENT_STATUS);
  const [agentLabels, setAgentLabels] = useState({});
  const [edaResult, setEdaResult]     = useState(null);
  const [error, setError]             = useState(null);
  const [question, setQuestion]       = useState('');
  const abortRef = useRef(null);

  const runPipeline = async () => {
    if (!datasetId) { toast.error('Select a dataset first'); return; }
    setRunning(true);
    setEdaResult(null);
    setError(null);
    setAgentStatus(INITIAL_AGENT_STATUS);
    setAgentLabels({});

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const response = await agenticAPI.streamAnalysis(
        datasetId,
        question.trim() || 'Give me a full exploratory analysis of this dataset',
      );

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let   buf     = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = (buf + chunk).split('\n');
        buf = lines.pop(); // keep incomplete last line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let event;
          try { event = JSON.parse(line.slice(6)); } catch { continue; }

          if (event.type === 'agent_start') {
            setAgentStatus(s => ({ ...s, [event.agent]: 'running' }));
            setAgentLabels(l => ({ ...l, [event.agent]: event.label }));
          } else if (event.type === 'agent_done') {
            setAgentStatus(s => ({ ...s, [event.agent]: 'done' }));
          } else if (event.type === 'agent_error') {
            setAgentStatus(s => ({ ...s, [event.agent]: 'error' }));
          } else if (event.type === 'pipeline_done') {
            setEdaResult(event.data);
            setActiveTab('analyse');
          } else if (event.type === 'pipeline_error') {
            setError(event.error);
            toast.error(event.error || 'Pipeline failed');
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        const msg = e.message || 'Analysis failed';
        setError(msg);
        toast.error(msg);
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  };

  const cancel = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  const charts = edaResult?.charts || [];
  const univariateFindings = edaResult?.univariate?.key_findings || [];
  const relationships      = edaResult?.bivariate?.key_relationships || [];
  const drivers            = edaResult?.bivariate?.primary_drivers || [];
  const plannerIntent      = edaResult?.planner?.intent;
  const validation         = edaResult?.validation;
  const pipelineErrors     = edaResult?.errors || [];
  const partialFailure     = edaResult?.partial_failure || false;
  const timings            = edaResult?.timings || {};
  const totalTime          = Object.values(timings).reduce((a, b) => a + b, 0);
  const hasResult          = !!edaResult;
  const anyRunning         = Object.values(agentStatus).some(s => s === 'running');

  return (
    <motion.div
      initial={{ x: 380, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 380, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 340, damping: 32 }}
      className="fixed top-0 right-0 h-full w-[380px] z-50 flex flex-col bg-surface border-l border-border shadow-2xl shadow-black/20"
    >
      {/* header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-orange-700" />
          <span className="text-sm font-semibold text-header">EDA Pipeline</span>
          {hasResult && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold ${
              partialFailure
                ? 'bg-yellow-50 border-yellow-200 text-yellow-700'
                : 'bg-green-50 border-green-200 text-green-700'
            }`}>
              {partialFailure ? 'Partial' : 'Done'}
              {totalTime > 0 && ` · ${totalTime.toFixed(1)}s`}
            </span>
          )}
        </div>
        <button onClick={onClose} className="p-1 text-muted hover:text-secondary transition-colors rounded">
          <X size={16} />
        </button>
      </div>

      {/* tabs */}
      <div className="flex border-b border-border shrink-0">
        {TABS.map(t => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[11px] font-semibold transition-colors
                ${active
                  ? 'text-orange-700 border-b-2 border-orange-700'
                  : 'text-muted hover:text-secondary border-b-2 border-transparent'
                }`}
            >
              <Icon size={13} />
              {t.label}
              {t.id === 'charts' && charts.length > 0 && (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-orange-500/20 text-orange-300 font-bold ml-0.5">
                  {charts.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* body */}
      <div className="flex-1 overflow-y-auto px-4 py-3 scrollbar-thin scrollbar-thumb-muted/30 scrollbar-track-transparent">

        {/* ╔═ ANALYSE TAB ══════════════════════════════════════╗ */}
        {activeTab === 'analyse' && (
          <div>
            {/* question input */}
            <div className="mb-3">
              <input
                type="text"
                placeholder="What do you want to learn? (optional)"
                value={question}
                onChange={e => setQuestion(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !running && runPipeline()}
                disabled={running}
                className="w-full text-[12px] bg-elevated border border-border rounded-lg px-3 py-2 text-header placeholder:text-muted/60 focus:outline-none focus:border-orange-500/60 transition-colors"
              />
            </div>

            {/* run / cancel button */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={running ? cancel : runPipeline}
                disabled={!datasetId}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-semibold transition-colors disabled:opacity-40
                  ${running
                    ? 'bg-rose-600/80 hover:bg-rose-600 text-white'
                    : 'bg-orange-600 hover:bg-orange-500 text-white'
                  }`}
              >
                {running
                  ? <><X size={13} /> Cancel</>
                  : <><Sparkles size={13} /> Run EDA</>
                }
              </button>
              {hasResult && (
                <button
                  onClick={() => { setEdaResult(null); setAgentStatus(INITIAL_AGENT_STATUS); setError(null); }}
                  className="px-3 py-2 rounded-lg text-[12px] text-muted hover:text-secondary border border-border transition-colors"
                  title="Clear results"
                >
                  <RefreshCw size={13} />
                </button>
              )}
            </div>

            {/* agent progress list — show when running or done */}
            {(running || hasResult || Object.values(agentStatus).some(s => s !== 'idle')) && (
              <div className="mb-4 p-3 rounded-xl border border-border bg-elevated/40">
                <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">Pipeline Progress</p>
                {AGENTS.map(a => (
                  <AgentRow
                    key={a.id}
                    agent={a}
                    status={agentStatus[a.id]}
                    label={agentLabels[a.id]}
                  />
                ))}
              </div>
            )}

            {/* error banner */}
            {error && (
              <div className="mb-3 p-3 rounded-xl border border-rose-500/30 bg-rose-500/5 flex items-start gap-2">
                <AlertCircle size={14} className="text-red-700 mt-0.5 shrink-0" />
                <p className="text-[12px] text-rose-300 leading-[1.5]">{error}</p>
              </div>
            )}

            {/* pipeline errors (non-fatal) */}
            {pipelineErrors.length > 0 && (
              <div className="mb-3 p-2.5 rounded-xl border border-amber-500/20 bg-amber-500/5">
                <p className="text-[10px] font-semibold text-yellow-700 mb-1">Warnings</p>
                {pipelineErrors.map((e, i) => (
                  <p key={i} className="text-[11px] text-amber-300/70">{e}</p>
                ))}
              </div>
            )}

            {/* results */}
            {hasResult && (
              <>
                {/* planner intent */}
                {plannerIntent && (
                  <div className="mb-4 p-3 rounded-xl border border-orange-500/20 bg-orange-500/5">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Eye size={12} className="text-orange-700" />
                      <span className="text-[10px] font-semibold text-orange-300 uppercase tracking-wider">Intent</span>
                    </div>
                    <p className="text-[12px] text-secondary leading-[1.5]">{plannerIntent}</p>
                    {drivers.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {drivers.map(d => (
                          <span key={d} className="text-[10px] font-mono text-sky-300 bg-sky-500/10 border border-sky-500/20 px-1.5 py-0.5 rounded">
                            {d}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* validation badge */}
                {validation && (
                  <div className={`mb-4 p-2.5 rounded-xl border flex items-center gap-2
                    ${validation.passed
                      ? 'border-emerald-500/20 bg-emerald-500/5'
                      : 'border-amber-500/20 bg-amber-500/5'
                    }`}
                  >
                    <CheckCircle2 size={13} className={validation.passed ? 'text-green-700' : 'text-yellow-700'} />
                    <span className="text-[11px] text-secondary">
                      QA {validation.passed ? 'passed' : 'found issues'} · confidence {((validation.confidence_score || 0) * 100).toFixed(0)}%
                    </span>
                    {(validation.issues || []).length > 0 && (
                      <span className="ml-auto text-[10px] text-yellow-700">{validation.issues.length} issue{validation.issues.length !== 1 ? 's' : ''}</span>
                    )}
                  </div>
                )}

                {/* univariate findings */}
                {univariateFindings.length > 0 && (
                  <section className="mb-4">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <Activity size={11} /> Column Findings ({univariateFindings.length})
                    </p>
                    {univariateFindings.map((f, i) => <FindingCard key={i} finding={f} />)}
                  </section>
                )}

                {/* bivariate relationships */}
                {relationships.length > 0 && (
                  <section className="mb-4">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <ArrowRightLeft size={11} /> Relationships ({relationships.length})
                    </p>
                    {relationships.map((r, i) => <RelationshipCard key={i} rel={r} index={i} />)}
                  </section>
                )}

                {/* charts hint */}
                {charts.length > 0 && (
                  <button
                    onClick={() => setActiveTab('charts')}
                    className="w-full text-[12px] text-orange-300 bg-orange-500/10 border border-orange-500/20 rounded-xl py-2.5 hover:bg-orange-500/15 transition-colors flex items-center justify-center gap-1.5"
                  >
                    <BarChart3 size={13} />
                    View {charts.length} chart recommendation{charts.length !== 1 ? 's' : ''}
                  </button>
                )}
              </>
            )}

            {/* empty state */}
            {!running && !hasResult && !error && (
              <div className="flex flex-col items-center justify-center py-14 gap-3 text-muted text-center">
                <Brain size={32} className="opacity-20" />
                <p className="text-sm">Run the 6-agent EDA pipeline to surface insights, relationships, and chart recommendations.</p>
              </div>
            )}
          </div>
        )}

        {/* ╔═ CHARTS TAB ════════════════════════════════════════╗ */}
        {activeTab === 'charts' && (
          <div>
            {charts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted text-center px-6">
                <BarChart3 size={28} className="opacity-30" />
                <p className="text-sm">No chart recommendations yet.</p>
                <p className="text-xs">Run an analysis to get visualisation suggestions from the pipeline.</p>
              </div>
            ) : (
              <>
                <p className="text-[11px] text-muted mb-3">
                  {charts.length} chart recommendation{charts.length !== 1 ? 's' : ''} from the Visualization + Critic agents
                </p>
                {charts.map((cfg, i) => <ChartConfigCard key={i} cfg={cfg} index={i} />)}
              </>
            )}
          </div>
        )}

        {/* ╔═ BELIEFS TAB ═══════════════════════════════════════╗ */}
        {activeTab === 'beliefs' && <BeliefGraphTab />}
      </div>

      {/* footer */}
      <div className="px-4 py-2 border-t border-border flex items-center gap-1.5 shrink-0">
        <Sparkles size={11} className="text-orange-500/50" />
        <span className="text-[10px] text-slate-600">6-agent EDA · Planner → Data → Uni → Bi → Viz → QA</span>
      </div>
    </motion.div>
  );
};

export default AgenticPanel;
