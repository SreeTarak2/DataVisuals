import React, { useRef, useState } from "react";
import { UploadCloud, X, Loader2, FileSpreadsheet, CheckCircle2 } from "lucide-react";
import { cn } from "../../../lib/utils";

/* ═══════════════════════════════════════════════════════════════
   UploadToProjectModal — "upload data INTO this project".
   One step: pick a file → existing upload pipeline → auto-bound
   as a data source (kind: data, connection_type: file). The file
   lives in the workspace's uploads; the project references it.
   ═══════════════════════════════════════════════════════════════ */

const ACCEPT = ".csv,.tsv,.xlsx,.xls,.json";

function UploadToProjectModal({ onClose, onUpload }) {
  const inputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [done, setDone] = useState(false);

  const pickFile = (f) => {
    if (!f) return;
    setFile(f);
    setDone(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    pickFile(e.dataTransfer?.files?.[0]);
  };

  const handleSubmit = async () => {
    if (!file || uploading) return;
    setUploading(true);
    const res = await onUpload(file, file.name);
    setUploading(false);
    if (res.success) {
      setDone(true);
      // Brief success state, then close so the bound source is visible.
      setTimeout(onClose, 700);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-[var(--bg-surface)] shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold text-header">Upload data into project</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted hover:text-primary hover:bg-elevated/60 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={cn(
            "rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all",
            dragActive
              ? "border-accent-primary/60 bg-accent-primary/5"
              : "border-border/70 hover:border-accent-primary/40 hover:bg-elevated/30"
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
          <div className="w-11 h-11 rounded-full bg-accent-primary/10 text-accent-primary flex items-center justify-center mx-auto mb-3">
            {done ? <CheckCircle2 size={20} /> : <UploadCloud size={20} />}
          </div>
          {file ? (
            <div className="space-y-1">
              <p className="text-sm font-semibold text-primary truncate px-4">{file.name}</p>
              <p className="text-[11px] text-muted">
                {(file.size / 1024).toFixed(0)} KB · ready to upload
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-sm font-semibold text-secondary">
                {dragActive ? "Drop it here" : "Click to upload or drag & drop"}
              </p>
              <p className="text-[11px] text-muted">CSV, TSV, XLSX, JSON</p>
            </div>
          )}
        </div>

        <p className="mt-3 text-[11px] text-muted leading-relaxed">
          The file goes through the normal pipeline (profile, PII detection, metadata) and is
          bound to this project as a data source — no separate step.
        </p>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={uploading}
            className="px-4 py-2 rounded-lg text-xs font-medium text-muted hover:bg-elevated/60 transition-colors disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!file || uploading}
            className="px-5 py-2 rounded-lg text-xs font-semibold bg-accent-primary/90 hover:bg-accent-primary text-white transition-colors flex items-center gap-1.5 disabled:opacity-40"
          >
            {uploading ? (
              <>
                <Loader2 size={13} className="animate-spin" /> Uploading…
              </>
            ) : done ? (
              <>
                <CheckCircle2 size={13} /> Bound
              </>
            ) : (
              <>
                <FileSpreadsheet size={13} /> Upload & bind
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default UploadToProjectModal;
