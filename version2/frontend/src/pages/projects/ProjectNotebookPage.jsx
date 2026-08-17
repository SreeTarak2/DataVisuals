import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Loader2, FolderKanban } from "lucide-react";
import useProjectStore from "../../store/projectStore";
import SourceSidebar from "../../components/features/projects/SourceSidebar";

/* ═══════════════════════════════════════════════════════════════
   ProjectPage — clean shell awaiting the full redesign.
   Current: the Sources sidebar (data entry) + an empty main area.
   The Journey / Dashboard tabs were removed entirely.
   ═══════════════════════════════════════════════════════════════ */

function ProjectPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const {
    current, sources, loadingProject,
    openProject, bindSource, syncSource, uploadToProject,
  } = useProjectStore();

  const [syncingId, setSyncingId] = useState(null);

  useEffect(() => {
    if (projectId) openProject(projectId);
  }, [projectId]);

  const handleSync = useCallback(async (source) => {
    setSyncingId(source.id);
    await syncSource(projectId, source.id);
    setSyncingId(null);
  }, [projectId, syncSource]);

  const handleBind = useCallback(async (payload) => {
    if (payload.kind === "context") {
      const { addContextRule } = useProjectStore.getState();
      return addContextRule(projectId, payload.ref.document_text || "");
    }
    return bindSource(projectId, payload);
  }, [projectId, bindSource]);

  const handleUpload = useCallback(async (file, name) =>
    uploadToProject(projectId, file, name), [projectId, uploadToProject]);

  if (loadingProject && !current) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-accent-primary" />
      </div>
    );
  }

  if (!current) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 text-center px-6">
        <p className="text-sm text-muted">Project not found.</p>
        <button
          type="button"
          onClick={() => navigate("/app/projects")}
          className="px-4 py-2 rounded-lg text-xs font-semibold bg-accent-primary/90 hover:bg-accent-primary text-white transition-colors"
        >
          Back to projects
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex overflow-hidden bg-[var(--bg-primary)]">
      {/* Sources — the context binder */}
      <SourceSidebar
        sources={sources}
        onBind={handleBind}
        onSync={handleSync}
        syncingId={syncingId}
        onUpload={handleUpload}
      />

      {/* Main area — awaiting the full redesign */}
      <main className="flex-1 flex flex-col items-center justify-center text-center px-6">
        <div className="w-12 h-12 rounded-2xl bg-elevated/60 flex items-center justify-center mb-4">
          <FolderKanban size={22} className="text-muted" />
        </div>
        <p className="text-sm font-medium text-secondary">
          {current.name}
        </p>
        <p className="text-[13px] text-muted max-w-sm leading-relaxed mt-1">
          The project workspace is being redesigned. Add data sources on the left —
          the analysis experience is coming.
        </p>
      </main>
    </div>
  );
}

export default ProjectPage;
