import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Calendar,
  CheckCircle2,
  Columns3,
  Database,
  File,
  Grid,
  Hash,
  List,
  MessageSquare,
  RefreshCw,
  Search,
  Trash2,
  XCircle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { toast } from "react-hot-toast";
import useDatasetStore from "../../store/datasetStore";
import { cn } from "../../lib/utils";
import GlobalUploadButton from "../../components/GlobalUploadButton";
import DeleteConfirmModal from "../../components/common/DeleteConfirmModal";

const MotionSection = motion.section;
const MotionArticle = motion.article;

const surfaceVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.32, ease: "easeOut" },
  },
};

const listVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.22, ease: "easeOut" },
  },
  exit: { opacity: 0, scale: 0.97, transition: { duration: 0.16 } },
};

const getDatasetId = (dataset) => dataset?.id || dataset?._id;
const getDatasetName = (dataset) =>
  dataset?.name || dataset?.filename || "Untitled Dataset";

const getDatasetDate = (dataset) =>
  dataset?.created_at ||
  dataset?.uploaded_at ||
  dataset?.upload_date ||
  dataset?.createdAt;

const formatDate = (value) => {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const getStatusConfig = (dataset) => {
  const status = (dataset?.status || "").toLowerCase();
  if (status === "completed" || dataset?.is_processed) {
    return {
      label: "Ready",
      icon: CheckCircle2,
      className:
        "border-emerald-400/30 bg-emerald-500/10 text-emerald-200 shadow-[0_0_24px_rgba(16,185,129,0.16)]",
    };
  }
  if (status === "processing") {
    return {
      label: "Processing",
      icon: RefreshCw,
      className:
        "border-amber-400/30 bg-amber-500/10 text-amber-100 shadow-[0_0_24px_rgba(245,158,11,0.14)]",
    };
  }
  if (status === "error") {
    return {
      label: "Error",
      icon: XCircle,
      className:
        "border-rose-400/30 bg-rose-500/10 text-rose-100 shadow-[0_0_24px_rgba(244,63,94,0.14)]",
    };
  }
  return {
    label: "Queued",
    icon: AlertTriangle,
    className: "border-slate-500/30 bg-slate-500/10 text-slate-200",
  };
};

const getFileTone = (name) => {
  const ext = (name?.split(".").pop() || "").toLowerCase();
  if (["csv", "xls", "xlsx"].includes(ext)) {
    return {
      label: ext || "table",
      className: "from-emerald-400 to-teal-500",
    };
  }
  if (["json", "xml", "parquet"].includes(ext)) {
    return {
      label: ext || "data",
      className: "from-sky-400 to-blue-500",
    };
  }
  if (["txt", "pdf"].includes(ext)) {
    return {
      label: ext || "file",
      className: "from-amber-400 to-orange-500",
    };
  }
  return {
    label: ext || "file",
    className: "from-slate-400 to-slate-500",
  };
};

const StatCard = ({ label, value, hint }) => (
  <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-4 backdrop-blur-md">
    <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">{label}</p>
    <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    <p className="mt-1 text-xs text-slate-500">{hint}</p>
  </div>
);

const DatasetCard = ({ dataset, viewMode, onChat, onCharts, onDelete }) => {
  const id = getDatasetId(dataset);
  const name = getDatasetName(dataset);
  const statusConfig = getStatusConfig(dataset);
  const fileTone = getFileTone(name);
  const createdLabel = formatDate(getDatasetDate(dataset));
  const isGrid = viewMode === "grid";
  const rowCount = dataset?.row_count || 0;
  const columnCount = dataset?.column_count || 0;
  const StatusIcon = statusConfig.icon;

  if (!id) return null;

  if (!isGrid) {
    return (
      <MotionArticle
        layout
        variants={cardVariants}
        className="group rounded-2xl border border-white/10 bg-[#0a0e17]/90 px-4 py-4 backdrop-blur-md transition-all hover:border-white/20 hover:bg-[#111827]/95"
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
          <button
            onClick={() => onChat(dataset)}
            className="flex flex-1 items-start gap-3 text-left"
          >
            <div
              className={cn(
                "mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-lg",
                fileTone.className
              )}
            >
              <File className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-base font-semibold text-white">{name}</h3>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" />
                  {createdLabel}
                </span>
                <span className="text-slate-600">•</span>
                <span className="uppercase tracking-wider">{fileTone.label}</span>
              </div>
            </div>
          </button>

          <div className="grid grid-cols-2 gap-2 lg:min-w-56">
            <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
              <p className="text-[11px] text-slate-500">Rows</p>
              <p className="text-sm font-semibold text-slate-100">
                {rowCount.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
              <p className="text-[11px] text-slate-500">Columns</p>
              <p className="text-sm font-semibold text-slate-100">
                {columnCount.toLocaleString()}
              </p>
            </div>
          </div>

          <div
            className={cn(
              "inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs",
              statusConfig.className
            )}
          >
            <StatusIcon className="h-3.5 w-3.5" />
            {statusConfig.label}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onChat(dataset)}
              className="rounded-lg border border-slate-500/30 bg-slate-500/10 px-3 py-2 text-sm text-slate-100 transition-colors hover:bg-slate-500/20"
            >
              <MessageSquare className="h-4 w-4" />
            </button>
            <button
              onClick={() => onCharts(dataset)}
              className="rounded-lg border border-cyan-400/35 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100 transition-colors hover:bg-cyan-500/20"
            >
              <BarChart3 className="h-4 w-4" />
            </button>
            <button
              onClick={() => onDelete(dataset)}
              className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100 transition-colors hover:bg-rose-500/20"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </MotionArticle>
    );
  }

  return (
    <MotionArticle
      layout
      variants={cardVariants}
      className="group relative overflow-hidden rounded-3xl border border-white/10 bg-[#090d16]/90 p-5 backdrop-blur-md transition-all hover:-translate-y-1 hover:border-white/20 hover:shadow-[0_20px_40px_-24px_rgba(202,210,253,0.35)]"
    >
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-transparent via-[#cad2fd] to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

      <button onClick={() => onChat(dataset)} className="w-full text-left">
        <div className="flex items-start justify-between gap-3">
          <div
            className={cn(
              "flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow-lg",
              fileTone.className
            )}
          >
            <File className="h-5 w-5" />
          </div>
          <div
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs",
              statusConfig.className
            )}
          >
            <StatusIcon className="h-3.5 w-3.5" />
            {statusConfig.label}
          </div>
        </div>

        <h3 className="mt-4 truncate text-lg font-semibold text-white">{name}</h3>
        <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
          <Calendar className="h-3.5 w-3.5" />
          {createdLabel}
          <span className="text-slate-600">•</span>
          <span className="uppercase tracking-[0.14em] text-slate-500">
            {fileTone.label}
          </span>
        </div>
      </button>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-white/10 bg-black/25 p-3">
          <p className="flex items-center gap-1 text-[11px] uppercase tracking-wider text-slate-500">
            <Hash className="h-3 w-3" />
            Rows
          </p>
          <p className="mt-1 text-base font-semibold text-slate-100">
            {rowCount.toLocaleString()}
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/25 p-3">
          <p className="flex items-center gap-1 text-[11px] uppercase tracking-wider text-slate-500">
            <Columns3 className="h-3 w-3" />
            Columns
          </p>
          <p className="mt-1 text-base font-semibold text-slate-100">
            {columnCount.toLocaleString()}
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={() => onChat(dataset)}
          className="flex-1 rounded-xl border border-slate-500/30 bg-slate-500/10 px-3 py-2 text-sm font-medium text-slate-100 transition-colors hover:bg-slate-500/20"
        >
          <span className="inline-flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Chat
          </span>
        </button>
        <button
          onClick={() => onCharts(dataset)}
          className="rounded-xl border border-cyan-400/35 bg-cyan-500/10 px-3 py-2 text-sm font-medium text-cyan-100 transition-colors hover:bg-cyan-500/20"
          title="Visualize"
        >
          <BarChart3 className="h-4 w-4" />
        </button>
        <button
          onClick={() => onDelete(dataset)}
          className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-100 transition-colors hover:bg-rose-500/20"
          title="Delete"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </MotionArticle>
  );
};

const DatasetsPage = () => {
  const { datasets, loading, fetchDatasets, deleteDataset } = useDatasetStore();
  const navigate = useNavigate();

  const [viewMode, setViewMode] = useState("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, dataset: null });

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  const sortedDatasets = useMemo(() => {
    return [...datasets].sort(
      (a, b) => new Date(getDatasetDate(b) || 0) - new Date(getDatasetDate(a) || 0)
    );
  }, [datasets]);

  const filteredDatasets = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return sortedDatasets;
    return sortedDatasets.filter((dataset) =>
      getDatasetName(dataset).toLowerCase().includes(q)
    );
  }, [searchQuery, sortedDatasets]);

  const stats = useMemo(() => {
    const total = datasets.length;
    const ready = datasets.filter((d) => {
      const status = (d?.status || "").toLowerCase();
      return d?.is_processed || status === "completed";
    }).length;
    const rows = datasets.reduce((sum, d) => sum + (d?.row_count || 0), 0);
    const avgColumns = total
      ? Math.round(
          datasets.reduce((sum, d) => sum + (d?.column_count || 0), 0) / total
        )
      : 0;
    return { total, ready, rows, avgColumns };
  }, [datasets]);

  const handleDeleteConfirm = async () => {
    const id = getDatasetId(deleteModal.dataset);
    if (!id) return;
    const result = await deleteDataset(id);
    if (result.success) {
      toast.success("Dataset deleted");
    }
    setDeleteModal({ isOpen: false, dataset: null });
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#05070d] text-slate-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-28 -top-36 h-96 w-96 rounded-full bg-[#cad2fd]/12 blur-[120px]" />
        <div className="absolute -bottom-40 right-[-80px] h-[26rem] w-[26rem] rounded-full bg-[#c7bc92]/15 blur-[130px]" />
        <div
          className="absolute inset-0 opacity-[0.16]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-[1440px] space-y-6 p-4 md:p-6 lg:p-8">
        <MotionSection
          initial="hidden"
          animate="visible"
          variants={surfaceVariants}
          className="overflow-hidden rounded-3xl border border-white/10 bg-[linear-gradient(120deg,rgba(202,210,253,0.20),rgba(5,7,13,0.80)_42%,rgba(199,188,146,0.22))] p-6 shadow-[0_30px_80px_-45px_rgba(0,0,0,0.9)] md:p-8"
        >
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-300/80">
                Data Workspace
              </p>
              <h1 className="mt-3 text-3xl font-semibold leading-tight text-white md:text-5xl">
                Datasets built for fast analysis
              </h1>
              <p className="mt-3 max-w-2xl text-sm text-slate-300 md:text-base">
                Upload, inspect, and launch analysis flows from one place with
                a cleaner operating surface.
              </p>
            </div>
            <div className="w-full max-w-xs">
              <GlobalUploadButton className="w-full justify-center rounded-xl py-3 font-semibold" />
            </div>
          </div>
        </MotionSection>

        <MotionSection
          initial="hidden"
          animate="visible"
          variants={surfaceVariants}
          className="grid grid-cols-2 gap-3 md:grid-cols-4"
        >
          <StatCard
            label="Total Datasets"
            value={stats.total.toLocaleString()}
            hint="Assets in your workspace"
          />
          <StatCard
            label="Ready"
            value={stats.ready.toLocaleString()}
            hint="Processed and queryable"
          />
          <StatCard
            label="Total Rows"
            value={stats.rows.toLocaleString()}
            hint="Across all datasets"
          />
          <StatCard
            label="Avg Columns"
            value={stats.avgColumns.toLocaleString()}
            hint="Typical schema width"
          />
        </MotionSection>

        <MotionSection
          initial="hidden"
          animate="visible"
          variants={surfaceVariants}
          className="rounded-2xl border border-white/10 bg-[#070b12]/88 p-3 backdrop-blur-md md:p-4"
        >
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <label className="relative block w-full md:max-w-md">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search by dataset name"
                className="h-11 w-full rounded-xl border border-white/10 bg-black/30 pl-10 pr-4 text-sm text-slate-100 outline-none transition-all placeholder:text-slate-500 focus:border-[#cad2fd]/40 focus:ring-2 focus:ring-[#cad2fd]/20"
              />
            </label>

            <div className="flex items-center justify-between gap-2">
              <button
                onClick={() => fetchDatasets(true)}
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-slate-200 transition-colors hover:bg-white/10"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>

              <div className="inline-flex rounded-xl border border-white/10 bg-white/5 p-1">
                <button
                  onClick={() => setViewMode("grid")}
                  className={cn(
                    "rounded-lg px-3 py-2 text-sm transition-colors",
                    viewMode === "grid"
                      ? "bg-[#cad2fd] text-[#020203]"
                      : "text-slate-300 hover:bg-white/10"
                  )}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <Grid className="h-4 w-4" />
                    Grid
                  </span>
                </button>
                <button
                  onClick={() => setViewMode("list")}
                  className={cn(
                    "rounded-lg px-3 py-2 text-sm transition-colors",
                    viewMode === "list"
                      ? "bg-[#cad2fd] text-[#020203]"
                      : "text-slate-300 hover:bg-white/10"
                  )}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <List className="h-4 w-4" />
                    List
                  </span>
                </button>
              </div>
            </div>
          </div>
        </MotionSection>

        <AnimatePresence mode="wait">
          {loading && datasets.length === 0 ? (
            <MotionSection
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className={cn(
                "grid gap-4",
                viewMode === "grid"
                  ? "grid-cols-1 md:grid-cols-2 xl:grid-cols-3"
                  : "grid-cols-1"
              )}
            >
              {Array.from({ length: viewMode === "grid" ? 6 : 4 }).map((_, index) => (
                <div
                  key={`skeleton-${index}`}
                  className="h-56 animate-pulse rounded-3xl border border-white/10 bg-white/[0.04]"
                />
              ))}
            </MotionSection>
          ) : filteredDatasets.length === 0 ? (
            <MotionSection
              key="empty"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-3xl border border-dashed border-white/15 bg-black/20 px-6 py-16 text-center"
            >
              <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                <Database className="h-8 w-8 text-slate-500" />
              </div>
              <h3 className="text-xl font-semibold text-white">
                {searchQuery ? "No matching datasets" : "No datasets yet"}
              </h3>
              <p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">
                {searchQuery
                  ? "Try a different keyword or clear search to see all datasets."
                  : "Upload your first dataset to start generating charts and conversations."}
              </p>
              {!searchQuery && (
                <div className="mt-6 inline-flex">
                  <GlobalUploadButton />
                </div>
              )}
            </MotionSection>
          ) : (
            <MotionSection
              key={`${viewMode}-${filteredDatasets.length}`}
              variants={listVariants}
              initial="hidden"
              animate="visible"
              className={cn(
                "grid gap-4",
                viewMode === "grid"
                  ? "grid-cols-1 md:grid-cols-2 xl:grid-cols-3"
                  : "grid-cols-1"
              )}
            >
              <AnimatePresence>
                {filteredDatasets.map((dataset) => (
                  <DatasetCard
                    key={getDatasetId(dataset)}
                    dataset={dataset}
                    viewMode={viewMode}
                    onChat={(item) =>
                      navigate(`/app/chat?dataset=${encodeURIComponent(getDatasetId(item))}`)
                    }
                    onCharts={(item) =>
                      navigate(`/app/charts?dataset=${encodeURIComponent(getDatasetId(item))}`)
                    }
                    onDelete={(item) => setDeleteModal({ isOpen: true, dataset: item })}
                  />
                ))}
              </AnimatePresence>
            </MotionSection>
          )}
        </AnimatePresence>

        <DeleteConfirmModal
          isOpen={deleteModal.isOpen}
          onClose={() => setDeleteModal({ isOpen: false, dataset: null })}
          onConfirm={handleDeleteConfirm}
          itemName={getDatasetName(deleteModal.dataset)}
        />
      </div>
    </div>
  );
};

export default DatasetsPage;
