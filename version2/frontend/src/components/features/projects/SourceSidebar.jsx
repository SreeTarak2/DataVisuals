import React, { useState, useEffect } from "react";
import {
  Database, Plug, RefreshCw, CheckCircle2, AlertCircle, Loader2,
  FileSpreadsheet, FileText, Slack, X, Plus, BookOpen, UploadCloud
} from "lucide-react";
import { cn } from "../../../lib/utils";
import { toast } from "react-hot-toast";
import UploadToProjectModal from "./UploadToProjectModal";

/* ═══════════════════════════════════════════════════════════════
   SourceSidebar — the context binder's visible face.
   Shows each bound source with its freshness (sync status,
   last_sync, watermark) — the ETL health as a product feature.
   "One failing source degrades, never blocks the project."
   ═══════════════════════════════════════════════════════════════ */

const SOURCE_ICONS = {
  database: Database,
  dlt: Slack,
  google_sheets: FileSpreadsheet,
  file: FileText,
  document: BookOpen,
};

const SOURCE_LABELS = {
  database: "Database",
  dlt: "SaaS / API",
  google_sheets: "Google Sheets",
  file: "File",
  document: "Document / Rule",
};

function SyncBadge({ sync }) {
  const status = sync?.status || "idle";
  if (status === "syncing") {
    return (
      <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-amber-400">
        <Loader2 size={11} className="animate-spin" /> Syncing
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-rose-400">
        <AlertCircle size={11} /> Sync failed
      </span>
    );
  }
  if (status === "ok") {
    return (
      <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
        <CheckCircle2 size={11} /> Synced
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-500" /> Not synced
    </span>
  );
}

function SourceRow({ source, onSync, syncingId }) {
  const Icon = SOURCE_ICONS[source.ref?.connection_type] || Database;
  const isSyncing = syncingId === source.id;
  const lastSync = source.sync?.last_sync_at
    ? new Date(source.sync.last_sync_at).toLocaleDateString()
    : null;

  return (
    <div className="px-3 py-2.5 rounded-lg border border-border/60 bg-[var(--bg-primary)]/40 hover:border-border/80 transition-colors">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-elevated/60 flex items-center justify-center shrink-0">
          <Icon size={13} className="text-muted" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[12.5px] font-medium text-primary truncate">
            {source.ref?.conn_id
              ? source.ref.conn_id.slice(0, 8)
              : source.ref?.dataset_id
                ? source.ref.dataset_id.slice(0, 8)
                : SOURCE_LABELS[source.ref?.connection_type] || "Source"}
          </p>
          <p className="text-[10px] text-muted capitalize">
            {SOURCE_LABELS[source.ref?.connection_type] || source.ref?.connection_type}
            {source.ref?.table ? ` · ${source.ref.table}` : ""}
            {source.ref?.source_type ? ` · ${source.ref.source_type}` : ""}
          </p>
        </div>
        {source.kind === "context" ? (
          <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
            Context
          </span>
        ) : (
          <button
            type="button"
            onClick={() => onSync(source)}
            disabled={isSyncing}
            className="p-1.5 rounded-lg text-muted hover:text-accent-primary hover:bg-accent-primary/10 transition-all disabled:opacity-40 shrink-0"
            title="Sync now"
          >
            {isSyncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          </button>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <SyncBadge sync={source.sync} />
        {lastSync && (
          <span className="text-[10px] text-muted tabular-nums">{lastSync}</span>
        )}
      </div>
      {source.sync?.watermark && (
        <p className="mt-1 text-[10px] font-mono text-muted truncate" title={source.sync.watermark}>
          watermark: {source.sync.watermark}
        </p>
      )}
      {source.sync?.error && (
        <p className="mt-1 text-[10px] text-rose-400/80 line-clamp-2" title={source.sync.error}>
          {source.sync.error}
        </p>
      )}
    </div>
  );
}

function BindSourceModal({ onClose, onBind }) {
  const [kind, setKind] = useState("data");
  const [connectionType, setConnectionType] = useState("database");
  const [connId, setConnId] = useState("");
  const [table, setTable] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [ruleText, setRuleText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    let ref;
    if (connectionType === "document") {
      ref = { connection_type: "document", document_text: ruleText };
    } else if (connectionType === "file" || connectionType === "google_sheets") {
      ref = { connection_type: connectionType, dataset_id: datasetId };
    } else {
      ref = { connection_type: connectionType, conn_id: connId, table: table || null, source_type: sourceType || null };
    }
    const res = await onBind({ kind, ref });
    setSubmitting(false);
    if (res.success) onClose();
  };

  const types = ["database", "dlt", "google_sheets", "file", "document"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-[var(--bg-surface)] shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold text-header">Bind a source</h3>
          <button type="button" onClick={onClose} className="p-1.5 rounded-lg text-muted hover:text-primary hover:bg-elevated/60 transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Kind toggle */}
        <div className="flex gap-1.5 mb-4 p-1 rounded-lg bg-elevated/50 border border-border/50">
          {["data", "context"].map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={cn(
                "flex-1 px-3 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider transition-all",
                kind === k ? "bg-accent-primary/90 text-white" : "text-muted hover:text-secondary"
              )}
            >
              {k === "data" ? "Data source" : "Context"}
            </button>
          ))}
        </div>

        <div className="space-y-3.5">
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5 block">
              Connection type
            </label>
            <div className="flex flex-wrap gap-1.5">
              {types.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setConnectionType(t)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-[11px] font-medium border transition-all capitalize",
                    connectionType === t
                      ? "bg-accent-primary/10 text-accent-primary border-accent-primary/30"
                      : "text-muted border-border/60 hover:text-secondary"
                  )}
                >
                  {SOURCE_LABELS[t] || t}
                </button>
              ))}
            </div>
          </div>

          {connectionType === "document" ? (
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5 block">
                Business rule / context text
              </label>
              <textarea
                value={ruleText}
                onChange={(e) => setRuleText(e.target.value)}
                rows={3}
                placeholder='e.g. "Churn = cancelled + failed renewal, not free trials"'
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-border text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary/40 resize-y"
              />
            </div>
          ) : connectionType === "file" || connectionType === "google_sheets" ? (
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5 block">
                Dataset ID (existing upload in this workspace)
              </label>
              <input
                value={datasetId}
                onChange={(e) => setDatasetId(e.target.value)}
                placeholder="dataset_id"
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-border text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary/40"
              />
            </div>
          ) : (
            <>
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5 block">
                  Connection ID (from Data Connectors)
                </label>
                <input
                  value={connId}
                  onChange={(e) => setConnId(e.target.value)}
                  placeholder="conn_id"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-border text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary/40"
                />
              </div>
              {connectionType === "dlt" && (
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5 block">
                    Source type (slack, salesforce, …)
                  </label>
                  <input
                    value={sourceType}
                    onChange={(e) => setSourceType(e.target.value)}
                    placeholder="slack"
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-border text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary/40"
                  />
                </div>
              )}
              {connectionType === "database" && (
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5 block">
                    Table (optional)
                  </label>
                  <input
                    value={table}
                    onChange={(e) => setTable(e.target.value)}
                    placeholder="users"
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-border text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary/40"
                  />
                </div>
              )}
            </>
          )}
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
            disabled={submitting}
            className="px-5 py-2 rounded-lg text-xs font-semibold bg-accent-primary/90 hover:bg-accent-primary text-white transition-colors flex items-center gap-1.5 disabled:opacity-40"
          >
            {submitting ? <Loader2 size={13} className="animate-spin" /> : <Plug size={13} />}
            Bind source
          </button>
        </div>
      </div>
    </div>
  );
}

function SourceSidebar({ sources, onBind, onSync, syncingId, onUpload }) {
  const [showBind, setShowBind] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [ruleDraft, setRuleDraft] = useState("");
  const [addingRule, setAddingRule] = useState(false);

  const dataSources = sources.filter((s) => s.kind === "data");
  const contextSources = sources.filter((s) => s.kind === "context");

  const handleRuleSubmit = async () => {
    if (!ruleDraft.trim()) return;
    setAddingRule(true);
    // Context rules are bound as document sources by the store
    const res = await onBind({
      kind: "context",
      ref: { connection_type: "document", document_text: ruleDraft.trim() },
    });
    setAddingRule(false);
    if (res.success) {
      setRuleDraft("");
      toast.success("Rule added — will inform future answers");
    }
  };

  return (
    <aside className="w-72 shrink-0 border-r border-border bg-[var(--bg-surface)]/60 flex flex-col overflow-hidden">
      <div className="px-4 pt-4 pb-2 flex items-center justify-between">
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted">
          Sources
        </h3>
        <div className="flex items-center gap-1">
          {onUpload && (
            <button
              type="button"
              onClick={() => setShowUpload(true)}
              title="Upload a file into this project"
              className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold text-accent-primary hover:bg-accent-primary/10 transition-colors"
            >
              <UploadCloud size={12} /> Upload
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowBind(true)}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold text-accent-primary hover:bg-accent-primary/10 transition-colors"
          >
            <Plus size={12} /> Bind
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-4">
        {/* Data sources */}
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted/70">Data</p>
          {dataSources.length === 0 ? (
            <p className="text-[11px] text-muted px-1">
              No data sources yet. Upload a file or bind a connection to analyze it here.
            </p>
          ) : (
            dataSources.map((s) => (
              <SourceRow key={s.id} source={s} onSync={onSync} syncingId={syncingId} />
            ))
          )}
        </div>

        {/* Context sources */}
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted/70">Context</p>
          {contextSources.length > 0 && (
            <div className="space-y-2">
              {contextSources.map((s) => (
                <SourceRow key={s.id} source={s} onSync={() => {}} syncingId={null} />
              ))}
            </div>
          )}

          {/* Quick rule adder */}
          <div className="rounded-lg border border-dashed border-border/70 p-2.5 space-y-2">
            <p className="text-[10px] text-muted leading-relaxed">
              Add a business rule the AI must honor:
            </p>
            <textarea
              value={ruleDraft}
              onChange={(e) => setRuleDraft(e.target.value)}
              rows={2}
              placeholder='"Churn = cancelled + failed renewal"'
              className="w-full px-2.5 py-1.5 rounded-md bg-[var(--bg-primary)] border border-border/60 text-[11.5px] text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent-primary/40 resize-none"
            />
            <button
              type="button"
              onClick={handleRuleSubmit}
              disabled={!ruleDraft.trim() || addingRule}
              className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/20 hover:bg-amber-500/25 transition-colors disabled:opacity-40"
            >
              {addingRule ? <Loader2 size={12} className="animate-spin" /> : <BookOpen size={12} />}
              Add rule
            </button>
          </div>
        </div>
      </div>

      {showBind && (
        <BindSourceModal
          onClose={() => setShowBind(false)}
          onBind={onBind}
        />
      )}

      {showUpload && onUpload && (
        <UploadToProjectModal
          onClose={() => setShowUpload(false)}
          onUpload={onUpload}
        />
      )}
    </aside>
  );
}

export default SourceSidebar;
