import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  FolderKanban, Plus, ArrowRight, Trash2, Loader2,
  Compass
} from "lucide-react";
import { toast } from "react-hot-toast";
import useProjectStore from "../../store/projectStore";
import CreateProjectModal from "../../components/features/projects/CreateProjectModal";
import { cn } from "../../lib/utils";
import { useTheme } from "../../store/themeStore";

/* ═══════════════════════════════════════════════════════════════
   ProjectsPage — the launcher.
   "Open a different project" replaces "switch dataset". Each
   project is one problem / one journey; datasets are materials
   inside it. Uploading auto-creates a project (Phase B wiring).
   ═══════════════════════════════════════════════════════════════ */

function ProjectsPage() {
  const navigate = useNavigate();
  const { projects, loading, fetchProjects, deleteProject } = useProjectStore();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const [showCreate, setShowCreate] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleDelete = async (project) => {
    if (!window.confirm(`Delete project "${project.name}" and its sources + cells?`)) return;
    setDeletingId(project.id);
    const res = await deleteProject(project.id);
    setDeletingId(null);
    if (!res.success) toast.error(res.error);
  };

  return (
    <div className={cn(
      "h-full flex flex-col overflow-hidden relative",
      isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
    )}>
      <main className="flex-1 overflow-y-auto px-4 py-10 md:px-8 relative z-10">
        <div className="mx-auto max-w-[1100px] space-y-10">
          {/* Header */}
          <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 animate-in fade-in slide-in-from-top-4 duration-500">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent-primary/80">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-primary" />
                Project Workspace
              </div>
              <h1 className={cn("text-4xl font-semibold tracking-tight leading-none", isDark ? "text-white" : "text-gray-900")}>
                Projects
              </h1>
              <p className={cn("text-sm max-w-xl leading-relaxed", isDark ? "text-gray-400" : "text-gray-650")}>
                One project = one problem. Datasets, connections, and context are the materials
                inside it — the journey (questions, findings, corrections) survives across all of them.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="bg-accent-primary hover:bg-accent-primary/90 text-white px-5 py-2.5 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition-all active:scale-95 shadow-lg shadow-accent-primary/20 whitespace-nowrap"
            >
              <Plus size={16} /> New project
            </button>
          </header>

          {/* Project cards */}
          {loading && projects.length === 0 ? (
            <div className="flex items-center justify-center py-24">
              <Loader2 size={22} className="animate-spin text-accent-primary" />
            </div>
          ) : projects.length === 0 ? (
            <div className={cn(
              "py-24 text-center space-y-4 border rounded-xl",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
            )}>
              <div className={cn(
                "w-16 h-16 rounded-full flex items-center justify-center mx-auto border",
                isDark ? "bg-white/[0.02] border-white/[0.04] text-gray-500" : "bg-gray-50 border-gray-200 text-gray-400"
              )}>
                <FolderKanban size={24} />
              </div>
              <div className="space-y-1">
                <p className={cn("font-semibold text-sm", isDark ? "text-white" : "text-gray-900")}>
                  No projects yet
                </p>
                <p className={cn("text-xs max-w-sm mx-auto", isDark ? "text-gray-500" : "text-gray-400")}>
                  Create a project to start a problem-driven analysis. Bind data sources and
                  let the AI surface the pivotal questions along the way.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowCreate(true)}
                className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-accent-primary/90 hover:bg-accent-primary text-white transition-colors"
              >
                <Plus size={14} /> Create your first project
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <AnimatePresence>
                {projects.map((project) => (
                  <motion.div
                    key={project.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className={cn(
                      "group rounded-xl border p-5 cursor-pointer transition-all hover:-translate-y-0.5",
                      isDark
                        ? "bg-[#131316] border-white/[0.05] hover:border-accent-primary/30 hover:shadow-xl hover:shadow-accent-primary/[0.04]"
                        : "bg-white border-gray-200 hover:border-accent-primary/40 hover:shadow-xl"
                    )}
                    onClick={() => navigate(`/app/projects/${project.id}`)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className={cn(
                        "w-10 h-10 rounded-xl flex items-center justify-center",
                        isDark ? "bg-accent-primary/10 text-accent-primary" : "bg-accent-primary/10 text-accent-primary"
                      )}>
                        <FolderKanban size={18} />
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(project);
                        }}
                        disabled={deletingId === project.id}
                        className={cn(
                          "p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-all",
                          isDark ? "text-gray-500 hover:text-rose-400 hover:bg-rose-500/10" : "text-gray-400 hover:text-rose-500 hover:bg-rose-50"
                        )}
                        title="Delete project"
                      >
                        {deletingId === project.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      </button>
                    </div>

                    <h3 className={cn("text-[15px] font-semibold mb-1.5 truncate", isDark ? "text-white" : "text-gray-900")}>
                      {project.name}
                    </h3>
                    <p className={cn("text-[12.5px] leading-relaxed line-clamp-2 min-h-[36px]", isDark ? "text-gray-500" : "text-gray-500")}>
                      {project.problem_statement || "No problem statement yet — set one to start the journey."}
                    </p>

                    <div className="mt-4 flex items-center justify-between">
                      <div className="flex items-center gap-3 text-[11px]">
                        <span className={cn("flex items-center gap-1", isDark ? "text-gray-500" : "text-gray-400")}>
                          <Compass size={11} /> {project.source_count} sources
                        </span>
                        <span className={cn("flex items-center gap-1", isDark ? "text-gray-500" : "text-gray-400")}>
                          <FolderKanban size={11} /> {project.cell_count} cells
                        </span>
                      </div>
                      <ArrowRight size={15} className={cn("transition-transform group-hover:translate-x-0.5", isDark ? "text-gray-600 group-hover:text-accent-primary" : "text-gray-400 group-hover:text-accent-primary")} />
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      </main>

      {showCreate && (
        <CreateProjectModal onClose={() => setShowCreate(false)} />
      )}
    </div>
  );
}

export default ProjectsPage;
