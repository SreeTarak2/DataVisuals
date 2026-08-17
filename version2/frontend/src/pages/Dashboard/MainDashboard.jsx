import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  FolderKanban, Database, Plus, ArrowRight, AlertTriangle, CheckCircle2,
  Loader2, Compass, RefreshCw, Activity, Bell, FolderPlus,
  FileText, CircleDashed
} from "lucide-react";
import { toast } from "react-hot-toast";
import useProjectStore from "../../store/projectStore";
import CreateProjectModal from "../../components/features/projects/CreateProjectModal";
import useDatasetStore from "../../store/datasetStore";
import { notificationAPI, projectAPI } from "../../services/api";
import { cn } from "../../lib/utils";
import { useTheme } from "../../store/themeStore";

/* ═══════════════════════════════════════════════════════════════
   MainDashboard — the Signal-side home.
   Answers: "What's going on with MY work?"
   - Projects: open / recent / their health
   - Needs attention: pending questions, failed syncs, failed datasets
   - Recent activity: notifications + dataset events
   The analytical dashboard lives INSIDE each project (data side);
   this page is the work overview.
   ═══════════════════════════════════════════════════════════════ */

function StatusDot({ tone }) {
  const tones = {
    ok: "bg-emerald-500",
    warn: "bg-amber-500",
    err: "bg-rose-500",
    idle: "bg-gray-500",
  };
  return <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", tones[tone] || tones.idle)} />;
}

function NeedsAttentionCard({ icon: Icon, tone, title, detail, action, onAction }) {
  const tones = {
    err: { chip: "bg-rose-500/10 text-rose-400 border-rose-500/20", hover: "hover:border-rose-500/30" },
    warn: { chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", hover: "hover:border-amber-500/30" },
    info: { chip: "bg-blue-500/10 text-blue-400 border-blue-500/20", hover: "hover:border-blue-500/30" },
  };
  const t = tones[tone] || tones.info;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("rounded-xl border border-border/70 bg-[var(--bg-surface)] p-4 transition-all", t.hover)}
    >
      <div className="flex items-start gap-3">
        <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border", t.chip)}>
          <Icon size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-header truncate">{title}</p>
          <p className="text-[12px] text-muted leading-relaxed mt-0.5 line-clamp-2">{detail}</p>
          {action && (
            <button
              type="button"
              onClick={onAction}
              className="mt-2 flex items-center gap-1 text-[11px] font-semibold text-accent-primary hover:text-accent-primary/80 transition-colors"
            >
              {action} <ArrowRight size={11} />
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function MainDashboard() {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const { projects, fetchProjects } = useProjectStore();
  const { datasets, fetchDatasets } = useDatasetStore();
  const [notifications, setNotifications] = useState([]);
  const [showCreateProjectModal, setShowCreateProjectModal] = useState(false);
  const [projectHealth, setProjectHealth] = useState({}); // projectId -> {failedSyncs, pendingQuestions, syncOk}
  const [loading, setLoading] = useState(true);

  // ── Load everything on mount ──
  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const [projRes, dsRes, notifRes] = await Promise.allSettled([
        fetchProjects(true),
        fetchDatasets(true),
        notificationAPI.getNotifications(20),
      ]);
      if (notifRes.status === "fulfilled") setNotifications(notifRes.value?.data?.notifications || []);
      setLoading(false);
    };
    load();
  }, []);

  // Fetch health per project: source sync failures + answered/pending questions
  const loadHealth = useCallback(async (projectId) => {
    try {
      const [srcRes, cellRes] = await Promise.all([
        projectAPI.listSources(projectId),
        projectAPI.listCells(projectId),
      ]);
      const sources = srcRes.data || [];
      const cells = cellRes.data || [];
      const failedSyncs = sources.filter((s) => s.sync?.status === "error").length;
      const pendingQuestions = cells.filter(
        (c) => c.kind === "question" && c.status === "pending"
      ).length;
      setProjectHealth((prev) => ({
        ...prev,
        [projectId]: { failedSyncs, pendingQuestions, syncOk: sources.length - failedSyncs },
      }));
    } catch { /* non-fatal */ }
  }, []);

  useEffect(() => {
    projects.forEach((p) => loadHealth(p.id));
  }, [projects]);

  // ── Derived ──
  const attentionItems = useMemo(() => {
    const items = [];
    projects.forEach((p) => {
      const h = projectHealth[p.id];
      if (h?.failedSyncs > 0) {
        items.push({
          key: `sync-${p.id}`,
          tone: "err",
          icon: RefreshCw,
          title: `Sync failed on "${p.name}"`,
          detail: `${h.failedSyncs} source${h.failedSyncs > 1 ? "s" : ""} failed — the project is using last good snapshots.`,
          action: "Open project",
          onAction: () => navigate(`/app/projects/${p.id}`),
        });
      }
      if (h?.pendingQuestions > 0) {
        items.push({
          key: `q-${p.id}`,
          tone: "warn",
          icon: Compass,
          title: `${h.pendingQuestions} unanswered question${h.pendingQuestions > 1 ? "s" : ""} in "${p.name}"`,
          detail: "The journey is waiting — continue where you left off.",
          action: "Continue journey",
          onAction: () => navigate(`/app/projects/${p.id}`),
        });
      }
    });
    datasets.forEach((d) => {
      const s = (d.processing_status || d.status || "").toLowerCase();
      if (s === "failed" || s === "error") {
        items.push({
          key: `ds-${d.id || d._id}`,
          tone: "err",
          icon: AlertTriangle,
          title: `Processing failed: ${d.name || d.original_filename || "dataset"}`,
          detail: "The pipeline errored. Reprocess to retry.",
          action: "Retry",
          onAction: () => navigate("/app/workspace"),
        });
      }
    });
    return items;
  }, [projects, projectHealth, datasets]);

  const recentProjects = useMemo(
    () => [...projects].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at)).slice(0, 6),
    [projects]
  );

  const stats = [
    { label: "Projects", value: projects.length, icon: FolderKanban, tone: "accent" },
    { label: "Datasets", value: datasets.length, icon: FileText, tone: "blue" },
    { label: "Needs attention", value: attentionItems.length, icon: AlertTriangle, tone: attentionItems.length > 0 ? "rose" : "emerald" },
    { label: "Notifications", value: notifications.filter((n) => !n.read).length, icon: Bell, tone: "amber" },
  ];

  const STAT_TONES = {
    accent: "bg-accent-primary/10 text-accent-primary",
    blue: "bg-blue-500/10 text-blue-400",
    rose: "bg-rose-500/10 text-rose-400",
    emerald: "bg-emerald-500/10 text-emerald-400",
    amber: "bg-amber-500/10 text-amber-400",
  };

  return (
    <div className={cn(
      "h-full flex flex-col overflow-hidden relative transition-colors duration-300",
      isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
    )}>
      <main className="flex-1 overflow-y-auto px-4 py-8 md:px-8 relative z-10">
        <div className="mx-auto max-w-[1200px] space-y-10">
          {/* Header */}
          <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 animate-in fade-in slide-in-from-top-4 duration-500">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent-primary/80">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-primary" />
                Signal Home
              </div>
              <h1 className={cn("text-4xl font-semibold tracking-tight leading-none", isDark ? "text-white" : "text-gray-900")}>
                Your work
              </h1>
              <p className={cn("text-sm max-w-xl leading-relaxed", isDark ? "text-gray-400" : "text-gray-650")}>
                What's happening across your projects, sources, and datasets — and what needs your attention.
              </p>
            </div>
            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={() => setShowCreateProjectModal(true)}
                className="px-4 py-2.5 rounded-lg text-xs font-semibold border border-border/70 text-secondary hover:bg-elevated/50 transition-colors flex items-center gap-2"
              >
                <FolderPlus size={14} /> New project
              </button>
              <button
                type="button"
                onClick={() => navigate("/app/connectors")}
                className="bg-accent-primary hover:bg-accent-primary/90 text-white px-4 py-2.5 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition-all active:scale-95 shadow-lg shadow-accent-primary/20"
              >
                <Database size={14} /> Connect Source
              </button>
            </div>
          </header>

          {/* Stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
            {stats.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className={cn(
                  "p-5 rounded-xl border transition-all",
                  isDark ? "bg-[#131316] border-white/[0.05]" : "bg-white border-gray-200 shadow-sm"
                )}
              >
                <div className="flex items-center gap-4">
                  <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", STAT_TONES[s.tone])}>
                    <s.icon size={18} />
                  </div>
                  <div>
                    <p className={cn("text-[10px] font-bold uppercase tracking-wider mb-0.5", isDark ? "text-gray-500" : "text-gray-400")}>
                      {s.label}
                    </p>
                    <p className={cn("text-2xl font-semibold tracking-tight tabular-nums", isDark ? "text-white" : "text-gray-900")}>
                      {loading ? <Loader2 size={16} className="animate-spin" /> : s.value}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left 2/3: recent projects */}
            <section className="lg:col-span-2 space-y-5">
              <div className="flex items-center justify-between">
                <h3 className={cn("text-xs font-bold uppercase tracking-wider flex items-center gap-2", isDark ? "text-gray-400" : "text-gray-500")}>
                  <FolderKanban size={14} className="text-accent-primary" /> Recent Projects
                </h3>
                <button
                  type="button"
                  onClick={() => navigate("/app/projects")}
                  className="text-[11px] font-semibold text-accent-primary hover:text-accent-primary/80 transition-colors flex items-center gap-1"
                >
                  View all <ArrowRight size={11} />
                </button>
              </div>

              {loading && projects.length === 0 ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 size={20} className="animate-spin text-accent-primary" />
                </div>
              ) : recentProjects.length === 0 ? (
                <div className={cn(
                  "py-16 text-center space-y-3 border rounded-xl",
                  isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
                )}>
                  <FolderKanban size={26} className="mx-auto text-muted" />
                  <p className={cn("text-sm font-semibold", isDark ? "text-white" : "text-gray-900")}>
                    No projects yet
                  </p>
                  <p className={cn("text-xs max-w-xs mx-auto", isDark ? "text-gray-500" : "text-gray-400")}>
                    Create a project to start a problem-driven analysis.
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate("/app/projects")}
                    className="mt-1 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-accent-primary/90 hover:bg-accent-primary text-white transition-colors"
                  >
                    <Plus size={14} /> Create your first project
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <AnimatePresence>
                    {recentProjects.map((p, i) => {
                      const h = projectHealth[p.id];
                      const attention = (h?.failedSyncs || 0) + (h?.pendingQuestions || 0);
                      return (
                        <motion.div
                          key={p.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.04 }}
                          className={cn(
                            "group rounded-xl border p-4 cursor-pointer transition-all hover:-translate-y-0.5",
                            isDark
                              ? "bg-[#131316] border-white/[0.05] hover:border-accent-primary/30"
                              : "bg-white border-gray-200 hover:border-accent-primary/40 shadow-sm"
                          )}
                          onClick={() => navigate(`/app/projects/${p.id}`)}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className={cn(
                              "w-9 h-9 rounded-lg flex items-center justify-center",
                              isDark ? "bg-accent-primary/10 text-accent-primary" : "bg-accent-primary/10 text-accent-primary"
                            )}>
                              <FolderKanban size={16} />
                            </div>
                            {attention > 0 && (
                              <span className="flex items-center gap-1 text-[10px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                                <AlertTriangle size={10} /> {attention}
                              </span>
                            )}
                          </div>
                          <p className={cn("text-[14px] font-semibold truncate", isDark ? "text-white" : "text-gray-900")}>
                            {p.name}
                          </p>
                          <p className={cn("text-[12px] leading-relaxed line-clamp-2 mt-1 min-h-[32px]", isDark ? "text-gray-500" : "text-gray-500")}>
                            {p.problem_statement || "No problem statement yet."}
                          </p>
                          <div className="mt-3 flex items-center justify-between">
                            <div className="flex items-center gap-3 text-[11px] text-muted">
                              <span className="flex items-center gap-1"><Database size={11} /> {p.source_count} src</span>
                              <span className="flex items-center gap-1"><Activity size={11} /> {p.cell_count} cells</span>
                            </div>
                            <ArrowRight size={14} className={cn("transition-transform group-hover:translate-x-0.5", isDark ? "text-gray-600" : "text-gray-400")} />
                          </div>
                        </motion.div>
                      );
                    })}
                  </AnimatePresence>
                </div>
              )}
            </section>

            {/* Right 1/3: needs attention + activity */}
            <section className="space-y-8">
              {/* Needs attention */}
              <div className="space-y-3">
                <h3 className={cn("text-xs font-bold uppercase tracking-wider flex items-center gap-2", isDark ? "text-gray-400" : "text-gray-500")}>
                  <AlertTriangle size={14} className={attentionItems.length ? "text-amber-400" : "text-emerald-500"} />
                  Needs attention
                </h3>
                {attentionItems.length === 0 ? (
                  <div className={cn(
                    "flex items-center gap-3 px-4 py-3.5 rounded-xl border",
                    isDark ? "bg-[#131316] border-emerald-500/15" : "bg-white border-emerald-200"
                  )}>
                    <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
                    <p className="text-[12.5px] text-secondary">
                      Everything looks healthy. Nothing needs your attention right now.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {attentionItems.slice(0, 4).map((item) => (
                      <NeedsAttentionCard key={item.key} {...item} />
                    ))}
                  </div>
                )}
              </div>

              {/* Recent activity */}
              <div className="space-y-3">
                <h3 className={cn("text-xs font-bold uppercase tracking-wider flex items-center gap-2", isDark ? "text-gray-400" : "text-gray-500")}>
                  <Bell size={14} className="text-amber-400" /> Recent activity
                </h3>
                {notifications.length === 0 ? (
                  <p className={cn("text-[12.5px] px-1", isDark ? "text-gray-500" : "text-gray-400")}>
                    No recent activity yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {notifications.slice(0, 6).map((n) => (
                      <div
                        key={n.id}
                        className={cn(
                          "flex items-start gap-2.5 px-3 py-2.5 rounded-lg border transition-colors cursor-pointer",
                          isDark ? "bg-[#131316] border-white/[0.04] hover:border-white/[0.1]" : "bg-white border-gray-200 hover:border-gray-300",
                          !n.read && (isDark ? "border-accent-primary/30" : "border-accent-primary/40")
                        )}
                        onClick={() => n.dataset_id && navigate("/app/workspace")}
                      >
                        <StatusDot tone={n.read ? "idle" : "warn"} />
                        <div className="min-w-0 flex-1">
                          <p className={cn("text-[12.5px] font-medium truncate", isDark ? "text-white" : "text-gray-900")}>{n.title}</p>
                          {n.body && (
                            <p className="text-[11.5px] text-muted leading-relaxed line-clamp-1">{n.body}</p>
                          )}
                          <p className="text-[10px] text-muted mt-0.5">
                            {n.created_at ? new Date(n.created_at).toLocaleString() : ""}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      </main>

      {showCreateProjectModal && (
        <CreateProjectModal
          onClose={() => setShowCreateProjectModal(false)}
          onCreated={(project) => navigate(`/app/projects/${project.id}`)}
        />
      )}
    </div>
  );
}

export default MainDashboard;
