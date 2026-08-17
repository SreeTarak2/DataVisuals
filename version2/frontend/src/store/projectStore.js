import { create } from "zustand";
import { datasetAPI, projectAPI } from "../services/api";
import { toast } from "react-hot-toast";

/**
 * Project Store — the analysis container (one problem / one journey).
 *
 * Server-backed (unlike the localStorage-only canvasStore). Every action
 * hits /api/projects and keeps a single source of truth in memory:
 *   projects  — list of ProjectSummary
 *   current   — the open Project (with sources + cells)
 *   sources   — bound sources (context binder) with sync state
 *   cells     — journey cells in order
 */
const useProjectStore = create((set, get) => ({
  // ── State ──
  projects: [],
  current: null,       // Project
  sources: [],         // ProjectSource[]
  cells: [],           // ProjectCell[] (ordered)
  loading: false,
  loadingProject: false,
  error: null,
  nextQuestion: null,  // { question, rationale, component, priority, confidence }
  journeyLoading: false,

  // ── Project CRUD ──
  fetchProjects: async (force = false) => {
    const { projects, loading } = get();
    if (projects.length > 0 && !force) return projects;
    if (loading) return projects;
    set({ loading: true, error: null });
    try {
      const res = await projectAPI.list();
      const list = res.data || [];
      set({ projects: list, loading: false });
      return list;
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to load projects";
      set({ loading: false, error: msg });
      return [];
    }
  },

  createProject: async (name, problemStatement = "") => {
    try {
      const res = await projectAPI.create({
        name,
        problem_statement: problemStatement,
      });
      const project = res.data;
      set((s) => ({ projects: [project, ...s.projects], current: project, sources: [], cells: [] }));
      toast.success(`Project "${name}" created`);
      return { success: true, project };
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to create project";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  openProject: async (projectId) => {
    set({ loadingProject: true, error: null, current: null });
    try {
      const res = await projectAPI.get(projectId);
      const project = res.data;
      set({ current: project, loadingProject: false });
      // Load sources + cells in parallel
      await Promise.all([
        get().fetchSources(projectId),
        get().fetchCells(projectId),
      ]);
      return { success: true, project };
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to open project";
      set({ loadingProject: false, error: msg });
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  updateProject: async (projectId, patch) => {
    try {
      const res = await projectAPI.update(projectId, patch);
      const updated = res.data;
      set((s) => ({
        current: s.current && s.current.id === projectId ? updated : s.current,
        projects: s.projects.map((p) => (p.id === projectId ? { ...p, ...patch } : p)),
      }));
      return { success: true, project: updated };
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to update project";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  deleteProject: async (projectId) => {
    try {
      await projectAPI.remove(projectId);
      set((s) => ({
        projects: s.projects.filter((p) => p.id !== projectId),
        current: s.current && s.current.id === projectId ? null : s.current,
      }));
      toast.success("Project deleted");
      return { success: true };
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to delete project";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  // ── Sources (context binder) ──
  fetchSources: async (projectId) => {
    try {
      const res = await projectAPI.listSources(projectId);
      set({ sources: res.data || [] });
      return res.data || [];
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to load sources";
      toast.error(msg);
      return [];
    }
  },

  bindSource: async (projectId, payload) => {
    try {
      const res = await projectAPI.bindSource(projectId, payload);
      set((s) => ({ sources: [...s.sources, res.data] }));
      toast.success("Source bound to project");
      return { success: true, source: res.data };
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to bind source";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  syncSource: async (projectId, sourceId) => {
    try {
      const res = await projectAPI.syncSource(projectId, sourceId);
      set((s) => ({
        sources: s.sources.map((src) =>
          src.id === sourceId ? { ...src, sync: res.data.sync } : src
        ),
      }));
      toast.success("Sync complete");
      return { success: true, source: res.data };
    } catch (err) {
      const msg = err.response?.data?.detail || "Sync failed";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  /**
   * Upload a file INTO the project — the missing entry point.
   *
   * Runs the file through the EXISTING upload pipeline (same endpoint as the
   * global upload), then auto-binds the materialized dataset as a data source
   * (kind: data, connection_type: file). One step instead of two.
   *
   * Duplicates: if the backend reports the file was already uploaded, bind the
   * existing dataset instead of failing — the project still gets its source.
   */
  uploadToProject: async (projectId, file, name = "") => {
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (name) formData.append("name", name);

      const res = await datasetAPI.uploadDataset(formData);
      const data = res.data || {};

      // Duplicate — the file exists in this workspace already.
      if (data.is_duplicate) {
        const existing =
          data.existing_dataset?.id ||
          data.existing_dataset?._id ||
          data.existing_dataset?.dataset_id;
        if (!existing) {
          throw new Error("File already uploaded, but no existing dataset id was returned");
        }
        const bindRes = await projectAPI.bindSource(projectId, {
          kind: "data",
          ref: { connection_type: "file", dataset_id: existing },
        });
        set((s) => ({ sources: [...s.sources, bindRes.data] }));
        toast.success("Already uploaded — bound the existing dataset to this project");
        return { success: true, source: bindRes.data, duplicate: true };
      }

      const datasetId = data.dataset_id;
      if (!datasetId) throw new Error("Upload did not return a dataset_id");

      const bindRes = await projectAPI.bindSource(projectId, {
        kind: "data",
        ref: { connection_type: "file", dataset_id: datasetId },
      });
      set((s) => ({ sources: [...s.sources, bindRes.data] }));
      toast.success("Uploaded and bound to project");
      return { success: true, source: bindRes.data };
    } catch (err) {
      const msg =
        err.response?.data?.detail || err.message || "Upload failed";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  // ── Cells (journey) ──
  fetchCells: async (projectId) => {
    try {
      const res = await projectAPI.listCells(projectId);
      set({ cells: res.data || [] });
      return res.data || [];
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to load cells";
      toast.error(msg);
      return [];
    }
  },

  addCell: async (projectId, payload) => {
    try {
      const res = await projectAPI.addCell(projectId, payload);
      set((s) => ({ cells: [...s.cells, res.data] }));
      return { success: true, cell: res.data };
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to add cell";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  updateCell: async (projectId, cellId, patch) => {
    try {
      const res = await projectAPI.updateCell(projectId, cellId, patch);
      set((s) => ({
        cells: s.cells.map((c) => (c.id === cellId ? res.data : c)),
      }));
      return { success: true, cell: res.data };
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to update cell";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  // ── Journey — next pivotal question ──
  fetchNextQuestion: async (projectId, problemStatement = null) => {
    set({ journeyLoading: true });
    try {
      const res = await projectAPI.nextQuestion(projectId, problemStatement);
      set({ nextQuestion: res.data?.next_question || null, journeyLoading: false });
      return { success: true, data: res.data };
    } catch (err) {
      const msg = err.response?.data?.detail || "Could not derive next question";
      set({ nextQuestion: null, journeyLoading: false });
      return { success: false, error: msg };
    }
  },

  // ── Context rules ──
  addContextRule: async (projectId, ruleText) => {
    try {
      const res = await projectAPI.addContextRule(projectId, ruleText);
      toast.success("Business rule added — it will inform future answers");
      return { success: true, beliefId: res.data?.belief_id };
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to add rule";
      toast.error(msg);
      return { success: false, error: msg };
    }
  },

  reset: () =>
    set({
      projects: [],
      current: null,
      sources: [],
      cells: [],
      loading: false,
      loadingProject: false,
      error: null,
      nextQuestion: null,
      journeyLoading: false,
    }),
}));

export default useProjectStore;
