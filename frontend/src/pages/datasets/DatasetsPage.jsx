import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Calendar,
  CheckCircle2,
  Clock,
  Columns3,
  Database,
  File,
  Grid,
  List,
  MessageSquare,
  RefreshCw,
  Rows3,
  Search,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { toast } from "react-hot-toast";
import useDatasetStore from "../../store/datasetStore";
import GlobalUploadButton from "../../components/GlobalUploadButton";
import DeleteConfirmModal from "../../components/common/DeleteConfirmModal";
import { cn } from "../../lib/utils";

/* ─── Helpers ─── */
const getDatasetId = (d) => d?.id || d?.dataset_id || d?._id || "";
const getDatasetName = (d) => d?.name || d?.original_filename || d?.file_name || "Untitled";
const getDatasetDate = (d) => d?.created_at || d?.uploaded_at || d?.createdAt || "";

const formatDate = (value) => {
  if (!value) return "\u2014";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "\u2014";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
};

const getFileExt = (name) => (name?.split(".").pop() || "").toLowerCase();

const FILE_EXT_COLORS = {
  csv: "from-emerald-400/80 to-teal-500/80",
  xls: "from-emerald-400/80 to-teal-500/80",
  xlsx: "from-emerald-400/80 to-teal-500/80",
  json: "from-sky-400/80 to-blue-500/80",
  xml: "from-sky-400/80 to-blue-500/80",
  parquet: "from-sky-400/80 to-blue-500/80",
  txt: "from-amber-400/80 to-orange-500/80",
  pdf: "from-amber-400/80 to-orange-500/80",
};

const getFileBadgeClass = (name) =>
  FILE_EXT_COLORS[getFileExt(name)] || "from-granite/60 to-granite/40";

const getStatusConfig = (dataset) => {
  const status = (dataset?.status || "").toLowerCase();
  if (dataset?.is_processed || status === "completed") {
    return { label: "Ready", icon: CheckCircle2, dot: "bg-emerald-400", text: "text-emerald-300" };
  }
  if (status === "processing") {
    return { label: "Processing", icon: Clock, dot: "bg-gold", text: "text-gold" };
  }
  if (status === "failed" || status === "error") {
    return { label: "Failed", icon: XCircle, dot: "bg-rose-400", text: "text-rose-300" };
  }
  return { label: "Queued", icon: AlertTriangle, dot: "bg-granite", text: "text-granite" };
};

/* ─── Motion ─── */
const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.28, ease: "easeOut" } },
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
};

const cardMotion = {
  hidden: { opacity: 0, y: 16, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.3, ease: "easeOut" } },
};

/* ─── Stat Pill ─── */
const StatPill = ({ icon: Icon, value, label }) => (
  <div className="flex items-center gap-3 rounded-2xl border border-[var(--surface-border)] bg-[var(--surface-1)] px-5 py-4 backdrop-blur-sm">
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-pearl/[0.07]">
      <Icon className="h-5 w-5 text-pearl/60" />
    </div>
    <div>
      <p className="text-xl font-semibold text-pearl">{value}</p>
      <p className="text-[13px] text-granite">{label}</p>
    </div>
  </div>
);

/* ─── Grid Card ─── */
const GridCard = ({ dataset, onChat, onCharts, onDelete }) => {
  const id = getDatasetId(dataset);
  const name = getDatasetName(dataset);
  const ext = getFileExt(name);
  const status = getStatusConfig(dataset);
  const date = formatDate(getDatasetDate(dataset));
  const rows = dataset?.row_count || 0;
  const cols = dataset?.column_count || 0;

  if (!id) return null;

  return (
    <motion.article
      layout
      variants={cardMotion}
      className="group relative flex flex-col rounded-2xl border border-[var(--surface-border)] bg-[var(--surface-1)] p-5 transition-all duration-200 hover:border-[var(--surface-border-hover)] hover:bg-[var(--surface-2)]"
    >
      {/* top: icon + status */}
      <div className="flex items-start justify-between gap-3">
        <div
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow-sm",
            getFileBadgeClass(name)
          )}
        >
          <File className="h-5 w-5" />
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border border-[var(--surface-border)] bg-[var(--surface-2)] px-2.5 py-1 text-[13px]",
            status.text
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", status.dot)} />
          {status.label}
        </span>
      </div>

      {/* name + meta */}
      <button onClick={() => onChat(dataset)} className="mt-4 text-left">
        <h3 className="truncate text-[17px] font-semibold text-pearl">{name}</h3>
        <div className="mt-1.5 flex items-center gap-2 text-[13px] text-granite">
          <Calendar className="h-3.5 w-3.5" />
          <span>{date}</span>
          <span className="text-avocado">·</span>
          <span className="uppercase tracking-wider">{ext || "file"}</span>
        </div>
      </button>

      {/* row/col stats */}
      <div className="mt-4 grid grid-cols-2 gap-2.5">
        <div className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface-2)] px-3 py-2.5">
          <p className="flex items-center gap-1.5 text-[12px] uppercase tracking-wider text-granite">
            <Rows3 className="h-3.5 w-3.5" /> Rows
          </p>
          <p className="mt-0.5 text-[15px] font-semibold text-pearl/90">{rows.toLocaleString()}</p>
        </div>
        <div className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface-2)] px-3 py-2.5">
          <p className="flex items-center gap-1.5 text-[12px] uppercase tracking-wider text-granite">
            <Columns3 className="h-3.5 w-3.5" /> Cols
          </p>
          <p className="mt-0.5 text-[15px] font-semibold text-pearl/90">{cols.toLocaleString()}</p>
        </div>
      </div>

      {/* action footer */}
      <div className="mt-4 flex items-center gap-2 border-t border-[var(--surface-border)] pt-4">
        <button
          onClick={() => onChat(dataset)}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-pearl/[0.07] px-3 py-2.5 text-[14px] font-medium text-pearl transition-colors hover:bg-pearl/[0.13]"
        >
          <MessageSquare className="h-4 w-4" /> Chat
        </button>
        <button
          onClick={() => onCharts(dataset)}
          className="rounded-xl bg-ocean/[0.12] px-3 py-2.5 text-ocean transition-colors hover:bg-ocean/[0.22]"
          title="Visualize"
        >
          <BarChart3 className="h-4 w-4" />
        </button>
        <button
          onClick={() => onDelete(dataset)}
          className="rounded-xl bg-rose-500/[0.1] px-3 py-2.5 text-rose-300 transition-colors hover:bg-rose-500/[0.2]"
          title="Delete"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </motion.article>
  );
};

/* ─── List Row ─── */
const ListRow = ({ dataset, onChat, onCharts, onDelete }) => {
  const id = getDatasetId(dataset);
  const name = getDatasetName(dataset);
  const ext = getFileExt(name);
  const status = getStatusConfig(dataset);
  const date = formatDate(getDatasetDate(dataset));
  const rows = dataset?.row_count || 0;
  const cols = dataset?.column_count || 0;

  if (!id) return null;

  return (
    <motion.article
      layout
      variants={cardMotion}
      className="group flex flex-col gap-4 rounded-2xl border border-[var(--surface-border)] bg-midnight/50 px-5 py-4 transition-all duration-200 hover:border-pearl/[0.12] hover:bg-midnight/70 lg:flex-row lg:items-center"
    >
      {/* left: icon + name */}
      <button
        onClick={() => onChat(dataset)}
        className="flex flex-1 items-center gap-3.5 text-left"
      >
        <div
          className={cn(
            "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm",
            getFileBadgeClass(name)
          )}
        >
          <File className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h3 className="truncate text-[16px] font-semibold text-pearl">{name}</h3>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[13px] text-granite">
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" /> {date}
            </span>
            <span className="text-avocado">·</span>
            <span className="uppercase tracking-wider">{ext || "file"}</span>
          </div>
        </div>
      </button>

      {/* center: row/col pills */}
      <div className="flex gap-2 lg:min-w-[200px]">
        <div className="rounded-lg border border-[var(--surface-border)] bg-noir/40 px-3 py-2">
          <p className="text-[12px] text-granite">Rows</p>
          <p className="text-[14px] font-semibold text-pearl/90">{rows.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-[var(--surface-border)] bg-noir/40 px-3 py-2">
          <p className="text-[12px] text-granite">Columns</p>
          <p className="text-[14px] font-semibold text-pearl/90">{cols.toLocaleString()}</p>
        </div>
      </div>

      {/* status badge */}
      <span
        className={cn(
          "inline-flex w-fit items-center gap-1.5 rounded-full border border-[var(--surface-border)] bg-noir/50 px-2.5 py-1 text-[13px]",
          status.text
        )}
      >
        <span className={cn("h-1.5 w-1.5 rounded-full", status.dot)} />
        {status.label}
      </span>

      {/* actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => onChat(dataset)}
          className="rounded-xl bg-pearl/[0.07] px-3 py-2.5 text-pearl transition-colors hover:bg-pearl/[0.13]"
          title="Chat"
        >
          <MessageSquare className="h-4 w-4" />
        </button>
        <button
          onClick={() => onCharts(dataset)}
          className="rounded-xl bg-ocean/[0.12] px-3 py-2.5 text-ocean transition-colors hover:bg-ocean/[0.22]"
          title="Visualize"
        >
          <BarChart3 className="h-4 w-4" />
        </button>
        <button
          onClick={() => onDelete(dataset)}
          className="rounded-xl bg-rose-500/[0.1] px-3 py-2.5 text-rose-300 transition-colors hover:bg-rose-500/[0.2]"
          title="Delete"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </motion.article>
  );
};

/* ═══════════════════════════════════════════════ */
/*                  MAIN COMPONENT                 */
/* ═══════════════════════════════════════════════ */
const DatasetsPage = () => {
  const { datasets, loading, fetchDatasets, deleteDataset } = useDatasetStore();
  const navigate = useNavigate();

  const [viewMode, setViewMode] = useState("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, dataset: null });

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  /* ── Derived data ── */
  const sortedDatasets = useMemo(
    () => [...datasets].sort((a, b) => new Date(getDatasetDate(b) || 0) - new Date(getDatasetDate(a) || 0)),
    [datasets]
  );

  const filteredDatasets = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return sortedDatasets;
    return sortedDatasets.filter((d) => getDatasetName(d).toLowerCase().includes(q));
  }, [searchQuery, sortedDatasets]);

  const stats = useMemo(() => {
    const total = datasets.length;
    const ready = datasets.filter((d) => {
      const s = (d?.status || "").toLowerCase();
      return d?.is_processed || s === "completed";
    }).length;
    const rows = datasets.reduce((sum, d) => sum + (d?.row_count || 0), 0);
    const avgCols = total
      ? Math.round(datasets.reduce((sum, d) => sum + (d?.column_count || 0), 0) / total)
      : 0;
    return { total, ready, rows, avgCols };
  }, [datasets]);

  /* ── Handlers ── */
  const handleDeleteConfirm = async () => {
    const id = getDatasetId(deleteModal.dataset);
    if (!id) return;
    const result = await deleteDataset(id);
    if (result.success) toast.success("Dataset deleted");
    setDeleteModal({ isOpen: false, dataset: null });
  };

  const goChat = (d) => navigate(`/app/chat?dataset=${encodeURIComponent(getDatasetId(d))}`);
  const goCharts = (d) => navigate(`/app/charts?dataset=${encodeURIComponent(getDatasetId(d))}`);
  const askDelete = (d) => setDeleteModal({ isOpen: true, dataset: d });

  /* ── Render ── */
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[1440px] space-y-6 p-5 md:p-8">

          {/* ─── Header banner removed ─── */}

          {/* ─── Stats row ─── */}
          <motion.section
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="grid grid-cols-2 gap-3 lg:grid-cols-4"
          >
            <StatPill icon={Database} value={stats.total} label="Total datasets" />
            <StatPill icon={CheckCircle2} value={stats.ready} label="Ready to query" />
            <StatPill icon={Rows3} value={stats.rows.toLocaleString()} label="Total rows" />
            <StatPill icon={Columns3} value={stats.avgCols} label="Avg columns" />
          </motion.section>

          {/* ─── Search & controls ─── */}
          <motion.section
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="rounded-2xl border border-[var(--surface-border)] bg-midnight/40 p-3 md:p-4"
          >
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              {/* Search */}
              <label className="relative block w-full md:max-w-md">
                <Search className="pointer-events-none absolute left-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-granite/60" />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by dataset name..."
                  className="h-12 w-full rounded-xl border border-[var(--surface-border)] bg-noir/60 pl-11 pr-4 text-[15px] text-pearl/90 placeholder:text-granite/50 outline-none transition-all focus:border-pearl/25 focus:ring-2 focus:ring-pearl/10"
                />
              </label>

              {/* Right controls */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => fetchDatasets(true)}
                  className="inline-flex h-11 items-center gap-2 rounded-xl border border-[var(--surface-border)] bg-[var(--surface-2)] px-4 text-[14px] text-pearl/70 transition-colors hover:bg-[var(--surface-2)] hover:text-pearl"
                >
                  <RefreshCw className="h-4 w-4" /> Refresh
                </button>

                <div className="inline-flex rounded-xl border border-[var(--surface-border)] bg-noir/40 p-1">
                  <button
                    onClick={() => setViewMode("grid")}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[14px] font-medium transition-colors",
                      viewMode === "grid"
                        ? "bg-pearl text-noir shadow-sm"
                        : "text-granite hover:text-pearl hover:bg-[var(--surface-2)]"
                    )}
                  >
                    <Grid className="h-4 w-4" /> Grid
                  </button>
                  <button
                    onClick={() => setViewMode("list")}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[14px] font-medium transition-colors",
                      viewMode === "list"
                        ? "bg-pearl text-noir shadow-sm"
                        : "text-granite hover:text-pearl hover:bg-[var(--surface-2)]"
                    )}
                  >
                    <List className="h-4 w-4" /> List
                  </button>
                </div>

                <div className="h-6 w-px bg-white/[0.08] mx-1" />

                <GlobalUploadButton className="!bg-pearl !text-noir !border-none !hover:bg-pearl/90 !hover:scale-100 !shadow-none h-11 rounded-xl px-5 text-[14px] font-semibold transition-colors" />
              </div>
            </div>
          </motion.section>

          {/* ─── Dataset list ─── */}
          <AnimatePresence mode="wait">
            {loading && datasets.length === 0 ? (
              /* skeleton loading */
              <motion.section
                key="skeleton"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className={cn(
                  "grid gap-4",
                  viewMode === "grid" ? "grid-cols-1 md:grid-cols-2 xl:grid-cols-3" : "grid-cols-1"
                )}
              >
                {Array.from({ length: viewMode === "grid" ? 6 : 4 }).map((_, i) => (
                  <div
                    key={`sk-${i}`}
                    className="h-56 animate-pulse rounded-2xl border border-[var(--surface-border)] bg-midnight/30"
                  />
                ))}
              </motion.section>
            ) : filteredDatasets.length === 0 ? (
              /* empty state */
              <motion.section
                key="empty"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-2xl border border-dashed border-[var(--surface-border)] bg-midnight/30 px-6 py-20 text-center"
              >
                <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-ocean/30 bg-gradient-to-br from-ocean/20 to-cyan-500/10 shadow-[0_0_25px_rgba(91,136,178,0.2)]">
                  <Database className="h-8 w-8 text-ocean" />
                </div>
                <h3 className="text-xl font-semibold text-pearl">
                  {searchQuery ? "No matching datasets" : "No datasets yet"}
                </h3>
                <p className="mx-auto mt-2 max-w-md text-[15px] leading-relaxed text-granite">
                  {searchQuery
                    ? "Try a different keyword or clear your search."
                    : "Upload your first dataset to start generating charts and AI conversations."}
                </p>
                {!searchQuery && (
                  <div className="mt-8 inline-flex">
                    <GlobalUploadButton className="!h-auto !px-8 !py-3.5 !rounded-xl !bg-gradient-to-r !from-ocean !to-cyan-600 !text-white !font-bold !shadow-[0_4px_20px_rgba(91,136,178,0.3)] !hover:shadow-[0_6px_25px_rgba(91,136,178,0.5)] !transition-all !active:scale-[0.98]" />
                  </div>
                )}
              </motion.section>
            ) : (
              /* dataset cards */
              <motion.section
                key={`${viewMode}-${filteredDatasets.length}`}
                variants={stagger}
                initial="hidden"
                animate="visible"
                className={cn(
                  "grid gap-4",
                  viewMode === "grid" ? "grid-cols-1 md:grid-cols-2 xl:grid-cols-3" : "grid-cols-1"
                )}
              >
                <AnimatePresence>
                  {filteredDatasets.map((d) =>
                    viewMode === "grid" ? (
                      <GridCard
                        key={getDatasetId(d)}
                        dataset={d}
                        onChat={goChat}
                        onCharts={goCharts}
                        onDelete={askDelete}
                      />
                    ) : (
                      <ListRow
                        key={getDatasetId(d)}
                        dataset={d}
                        onChat={goChat}
                        onCharts={goCharts}
                        onDelete={askDelete}
                      />
                    )
                  )}
                </AnimatePresence>
              </motion.section>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Delete modal */}
      <DeleteConfirmModal
        isOpen={deleteModal.isOpen}
        onClose={() => setDeleteModal({ isOpen: false, dataset: null })}
        onConfirm={handleDeleteConfirm}
        itemName={getDatasetName(deleteModal.dataset)}
      />
    </div>
  );
};

export default DatasetsPage;
