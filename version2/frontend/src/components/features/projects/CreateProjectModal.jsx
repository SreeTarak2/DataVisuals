import React, { useState } from "react";
import { X, Loader2, Check } from "lucide-react";
import useProjectStore from "../../../store/projectStore";

/* ═══════════════════════════════════════════════════════════════
   CreateProjectModal — the shared "New project" entry point.
   Creates a project (name + optional problem statement) through the
   project store, then fires onCreated with the created project.

   Props:
     onClose   — close the modal
     onCreated — optional callback(project) fired after successful creation
   ═══════════════════════════════════════════════════════════════ */
const CreateProjectModal = ({ onClose, onCreated }) => {
  const { createProject } = useProjectStore();
  const [name, setName] = useState("");
  const [problem, setProblem] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!name.trim() || submitting) return;
    setSubmitting(true);
    const res = await createProject(name.trim(), problem.trim());
    setSubmitting(false);
    if (res.success) {
      onCreated?.(res.project);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-[var(--bg-surface)] shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold text-header">New project</h3>
          <button type="button" onClick={onClose} className="p-1.5 rounded-lg text-muted hover:text-primary hover:bg-elevated/60 transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5 block">
              Project name
            </label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder='e.g. "Q3 Churn Investigation"'
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-border text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary/40"
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5 block">
              Problem statement <span className="normal-case font-normal">(optional — drives the journey)</span>
            </label>
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              rows={3}
              placeholder="Why did churn go up in Q3?"
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-border text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary/40 resize-y"
            />
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-medium text-muted hover:bg-elevated/60 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!name.trim() || submitting}
            className="px-5 py-2 rounded-lg text-xs font-semibold bg-accent-primary/90 hover:bg-accent-primary text-white transition-colors flex items-center gap-1.5 disabled:opacity-40"
          >
            {submitting ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
            Create project
          </button>
        </div>
      </div>
    </div>
  );
};

export default CreateProjectModal;
