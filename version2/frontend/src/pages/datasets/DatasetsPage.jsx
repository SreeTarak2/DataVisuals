import React, { useEffect, useMemo, useState, useRef } from "react";
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
  ChevronRight,
  MoreVertical,
  Filter,
  Plus,
  Share2,
  History,
  FileText,
  PieChart,
  HardDrive,
  Folder,
  ArrowRight,
  ExternalLink,
  Table,
  Tag,
  Hash,
  Activity,
  Layers
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
  return d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
};

const getFileExt = (name) => (name?.split(".").pop() || "").toLowerCase();

const FILE_EXT_COLORS = {
  csv: "from-emerald-400/20 to-teal-500/20 text-emerald-400 border-emerald-500/30",
  xls: "from-emerald-400/20 to-teal-500/20 text-emerald-400 border-emerald-500/30",
  xlsx: "from-emerald-400/20 to-teal-500/20 text-emerald-400 border-emerald-500/30",
  json: "from-sky-400/20 to-blue-500/20 text-sky-400 border-sky-500/30",
  xml: "from-sky-400/20 to-blue-500/20 text-sky-400 border-sky-500/30",
  parquet: "from-sky-400/20 to-blue-500/20 text-sky-400 border-sky-500/30",
  txt: "from-amber-400/20 to-orange-500/20 text-amber-400 border-orange-500/30",
  pdf: "from-rose-400/20 to-pink-500/20 text-rose-400 border-pink-500/30",
};

const getFileBadgeClass = (name) =>
  FILE_EXT_COLORS[getFileExt(name)] || "from-granite/20 to-granite/10 text-muted border-border";

const getStatusConfig = (statusRaw, isProcessed) => {
  const status = (statusRaw || "").toLowerCase();
  if (isProcessed || status === "completed") {
    return { label: "Ready", dot: "bg-emerald-400", text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" };
  }
  if (["pending", "loading", "cleaning", "processing", "profiling", "quality", "saving", "artifact_generation", "vector_indexing", "consolidating"].includes(status)) {
    return { label: "Processing", dot: "bg-amber-400", text: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" };
  }
  if (status === "failed" || status === "error") {
    return { label: "Failed", dot: "bg-rose-400", text: "text-rose-400", bg: "bg-rose-500/10", border: "border-rose-500/20" };
  }
  return { label: "Queued", dot: "bg-muted", text: "text-muted", bg: "bg-muted/10", border: "border-border" };
};

/* ─── Motion ─── */
const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};

const containerStagger = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 }
  },
};

const itemMotion = {
  hidden: { opacity: 0, scale: 0.97, y: 15 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};

/* ─── Sub-Component: Filter Dropdown ─── */
const FilterDropdown = ({ isOpen, onClose, activeFilters, onFilterChange }) => {
  if (!isOpen) return null;

  const [currentCategory, setCurrentCategory] = useState(null);

  const categories = [
    { id: 'date', label: 'Date', icon: Calendar, color: 'text-accent-primary', options: ['Latest', 'Oldest', 'This Month'] },
    { id: 'type', label: 'File Type', icon: Tag, color: 'text-emerald-400', options: ['all', 'csv', 'xls', 'xlsx', 'json'] },
    { id: 'status', label: 'Status', icon: Activity, color: 'text-sky-400', options: ['all', 'ready', 'processing', 'failed'] },
    { id: 'scale', label: 'Scale', icon: Layers, color: 'text-amber-400', options: ['all', '<10k', '10k-1M', '1M+'] },
  ];

  const handleOptionClick = (catId, opt) => {
    onFilterChange(catId, opt);
    setCurrentCategory(null);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.95 }}
      className="absolute top-full right-0 mt-3 z-50 w-72 p-6 rounded-[40px] bg-page-bg border border-slate-200 dark:border-white/10 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.18)] dark:shadow-[0_32px_64px_-16px_rgba(0,0,0,0.6)] backdrop-blur-3xl transition-all duration-300"
    >
      <AnimatePresence mode="wait">
        {!currentCategory ? (
          <motion.div
            key="categories"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className="space-y-4"
          >
            <h4 className="text-[12px] font-black text-header mb-1 px-1 uppercase tracking-widest flex justify-between">
              Filter Hub
              {Object.values(activeFilters).some(v => v !== 'all') && (
                <span className="text-accent-primary normal-case tracking-normal">Active</span>
              )}
            </h4>
            <div className="grid grid-cols-2 gap-3">
              {categories.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setCurrentCategory(f)}
                  className={cn(
                    "flex flex-col items-center justify-center p-4 rounded-2xl border transition-all group relative cursor-pointer",
                    activeFilters[f.id] && activeFilters[f.id] !== 'all'
                      ? "bg-accent-primary/10 border-accent-primary/40"
                      : "bg-slate-100 dark:bg-white/[0.04] border-slate-200 dark:border-white/10 hover:bg-slate-200 dark:hover:bg-white/[0.06] hover:border-slate-300 dark:hover:border-white/20"
                  )}
                >
                  <f.icon className={cn("w-6 h-6 mb-2 transition-transform group-hover:scale-110", f.color)} />
                  <span className="text-[11px] font-bold text-muted-strong group-hover:text-header transition-colors capitalize">{f.label}</span>
                  {activeFilters[f.id] && activeFilters[f.id] !== 'all' && (
                    <div className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-accent-primary shadow-[0_0_8px_rgba(124,58,237,0.5)]" />
                  )}
                </button>
              ))}
            </div>
            <button
              onClick={() => {
                onFilterChange('all', 'all');
                onClose();
              }}
              className="w-full py-2 text-[11px] font-black text-muted-strong uppercase tracking-[0.2em] hover:text-accent-primary transition-colors cursor-pointer"
            >
              Clear Workspace
            </button>
          </motion.div>
        ) : (
          <motion.div
            key="options"
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            className="space-y-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <button
                onClick={() => setCurrentCategory(null)}
                className="p-1 px-1.5 rounded-lg bg-slate-100 dark:bg-white/[0.05] text-muted hover:text-header cursor-pointer transition-colors"
              >
                <ArrowRight className="w-3.5 h-3.5 rotate-180" />
              </button>
              <h4 className="text-[12px] font-black text-header uppercase tracking-wider">{currentCategory.label} Options</h4>
            </div>
            <div className="flex flex-col gap-1">
              {currentCategory.options.map((opt) => (
                <button
                  key={opt}
                  onClick={() => handleOptionClick(currentCategory.id, opt)}
                  className={cn(
                    "flex items-center justify-between px-4 py-3 rounded-xl text-[13px] font-bold transition-all cursor-pointer",
                    activeFilters[currentCategory.id] === opt
                      ? "bg-accent-primary text-white"
                      : "bg-transparent text-muted-strong hover:bg-slate-50 dark:hover:bg-white/[0.04] hover:text-header"
                  )}
                >
                  <span className="capitalize">{opt}</span>
                  {activeFilters[currentCategory.id] === opt && <CheckCircle2 className="w-4 h-4" />}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

/* ─── Sub-Component: Premium Recent Card ─── */
const RecentCard = ({ dataset, onChat }) => {
  const name = getDatasetName(dataset);
  const date = formatDate(getDatasetDate(dataset));
  const ext = getFileExt(name).toUpperCase();

  return (
    <motion.div
      variants={itemMotion}
      whileHover={{ y: -6, scale: 1.02 }}
      className="group relative flex flex-col p-5 h-52 rounded-2xl bg-black/[0.03] dark:bg-white/[0.03] hover:bg-black/[0.05] dark:hover:bg-white/[0.06] transition-all duration-500 min-w-[220px] max-w-[260px] shadow-2xl hover:shadow-accent-primary/[0.03] cursor-pointer overflow-hidden isolate"
      onClick={() => onChat(dataset)}
    >
      {/* Abstract Background Icon */}
      <div className="absolute top-10 right-[-10px] opacity-[0.03] group-hover:opacity-[0.06] transition-opacity pointer-events-none">
        <FileText className="w-32 h-32 rotate-[-12deg]" />
      </div>

      <div className="flex items-center justify-between mb-auto">
        <div className={cn(
          "w-12 h-12 rounded-xl flex items-center justify-center bg-gradient-to-br border shadow-sm",
          getFileBadgeClass(name)
        )}>
          <Database className="w-6 h-6" />
        </div>
        <button className="p-1 px-1.5 rounded-lg hover:bg-elevated text-muted transition-colors opacity-0 group-hover:opacity-100 transition-opacity">
          <MoreVertical className="w-4 h-4" />
        </button>
      </div>

      <div>
        <h3 className="text-[16px] font-bold text-header truncate mb-1">
          {name}
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-extrabold text-accent-primary uppercase tracking-[0.1em]">{ext}</span>
          <span className="text-border text-[10px]">•</span>
          <p className="text-[11px] text-muted-strong font-semibold">
            {date}
          </p>
        </div>
      </div>

      {/* Hover Highlight */}
      <div className="absolute bottom-0 left-0 w-full h-[3px] bg-accent-primary transform scale-x-0 group-hover:scale-x-100 transition-transform origin-left" />
    </motion.div>
  );
};

/* ─── Sub-Component: Premium Table Row ─── */
const ListRow = ({ dataset, onChat, onCharts, onDelete }) => {
  const name = getDatasetName(dataset);
  const status = getStatusConfig(dataset?.processing_status || dataset?.status, dataset?.is_processed);
  const date = formatDate(getDatasetDate(dataset));
  const rowCount = dataset?.row_count?.toLocaleString() || "—";
  const colCount = dataset?.column_count || "—";
  const ext = getFileExt(name).toUpperCase() || "DATA";

  return (
    <motion.tr
      variants={itemMotion}
      className="group hover:bg-black/[0.02] dark:hover:bg-white/[0.04] transition-all duration-300"
    >
      <td className="py-5 pl-6 pr-3 min-w-[320px]">
        <div className="flex items-center gap-4">
          <div className={cn(
            "w-11 h-11 rounded-xl flex items-center justify-center bg-gradient-to-br border shadow-sm group-hover:scale-105 transition-transform",
            getFileBadgeClass(name)
          )}>
            <FileText className="w-5.5 h-5.5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p
                className="text-[15px] font-bold text-header truncate cursor-pointer hover:text-accent-primary transition-colors"
                onClick={() => onChat(dataset)}
              >
                {name}
              </p>
              <ExternalLink className="w-3.5 h-3.5 text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="flex items-center gap-2 text-[11px] text-muted-strong uppercase tracking-wider font-bold">
              <span>{ext}</span>
              <span className="text-border">•</span>
              <span>{colCount} Columns</span>
            </div>
          </div>
        </div>
      </td>
      <td className="py-5 px-3 text-[14px] text-secondary font-semibold">
        {date}
      </td>
      <td className="py-5 px-3">
        <div className={cn(
          "inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11.5px] font-bold tracking-tight shadow-sm transition-all",
          status.text, status.bg, status.border
        )}>
          <span className={cn("w-1.5 h-1.5 rounded-full shadow-[0_0_8px_currentColor]", status.dot)} />
          {status.label}
        </div>
      </td>
      <td className="py-5 px-3">
        <div className="text-[14px] text-secondary font-mono font-bold tracking-tighter">
          {rowCount} <span className="text-[10px] text-muted-strong ml-0.5 uppercase tracking-normal">rows</span>
        </div>
      </td>
      <td className="py-5 pl-3 pr-6 text-right">
        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-all transform translate-x-2 group-hover:translate-x-0">
          <button
            onClick={() => onChat(dataset)}
            className="p-2.5 rounded-xl hover:bg-accent-primary/10 text-muted hover:text-accent-primary transition-all active:scale-95 shadow-lg shadow-transparent hover:shadow-accent-primary/5"
            title="Interactive Chat"
          >
            <MessageSquare className="w-5 h-5" />
          </button>
          <button
            onClick={() => onCharts(dataset)}
            className="p-2.5 rounded-xl hover:bg-ocean/10 text-muted hover:text-ocean transition-all active:scale-95"
            title="Studio View"
          >
            <PieChart className="w-5 h-5" />
          </button>
          <button
            onClick={() => onDelete(dataset)}
            className="p-2.5 rounded-xl hover:bg-red-500/10 text-muted hover:text-red-500 transition-all active:scale-95"
            title="Delete Permanently"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </td>
    </motion.tr>
  );
};

/* ═══════════════════════════════════════════════ */
/*                 MAIN WORKSPACE PAGE             */
/* ═══════════════════════════════════════════════ */
const DatasetsPage = () => {
  const { datasets, loading, fetchDatasets, deleteDataset } = useDatasetStore();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilters, setActiveFilters] = useState({
    status: 'all',
    type: 'all',
    scale: 'all',
    date: 'Latest'
  });
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, dataset: null });
  const [showFilter, setShowFilter] = useState(false);
  const filterRef = useRef(null);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  // Close filter on click outside
  useEffect(() => {
    if (!showFilter) return;
    const handler = (e) => {
      if (filterRef.current && !filterRef.current.contains(e.target)) setShowFilter(false);
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [showFilter]);

  const sortedDatasets = useMemo(
    () => [...datasets].sort((a, b) => new Date(getDatasetDate(b) || 0) - new Date(getDatasetDate(a) || 0)),
    [datasets]
  );

  const filteredDatasets = useMemo(() => {
    let result = [...sortedDatasets];

    // ── Search Filtering ──
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      result = result.filter((d) => getDatasetName(d).toLowerCase().includes(q));
    }

    // ── Status Filtering ──
    if (activeFilters.status !== 'all') {
      result = result.filter(d => {
        const stat = getStatusConfig(d?.processing_status || d?.status, d?.is_processed).label.toLowerCase();
        return stat === activeFilters.status;
      });
    }

    // ── File Type Filtering ──
    if (activeFilters.type !== 'all') {
      result = result.filter(d => getFileExt(getDatasetName(d)) === activeFilters.type);
    }

    // ── Scale Filtering ──
    if (activeFilters.scale !== 'all') {
      result = result.filter(d => {
        const rows = d?.row_count || 0;
        if (activeFilters.scale === '<10k') return rows < 10000;
        if (activeFilters.scale === '10k-1M') return rows >= 10000 && rows < 1000000;
        if (activeFilters.scale === '1M+') return rows >= 1000000;
        return true;
      });
    }

    // ── Date Sorting (Internal Filter Change) ──
    if (activeFilters.date === 'Oldest') {
      result = result.sort((a, b) => new Date(getDatasetDate(a) || 0) - new Date(getDatasetDate(b) || 0));
    } else {
      // Default Sort: Latest
      result = result.sort((a, b) => new Date(getDatasetDate(b) || 0) - new Date(getDatasetDate(a) || 0));
    }

    return result;
  }, [searchQuery, sortedDatasets, activeFilters]);

  const recentDatasets = useMemo(() => sortedDatasets.slice(0, 5), [sortedDatasets]);

  /* ── Handlers ── */
  const handleDeleteConfirm = async () => {
    const id = getDatasetId(deleteModal.dataset);
    if (!id) return;
    const result = await deleteDataset(id);
    if (result.success) toast.success("Successfully removed from workspace");
    setDeleteModal({ isOpen: false, dataset: null });
  };

  const goChat = (d) => navigate(`/app/chat?dataset=${encodeURIComponent(getDatasetId(d))}`);
  const goCharts = (d) => navigate(`/app/charts?dataset=${encodeURIComponent(getDatasetId(d))}`);
  const askDelete = (d) => setDeleteModal({ isOpen: true, dataset: d });

  const handleFilterChange = (cat, val) => {
    if (cat === 'all') {
      setActiveFilters({ status: 'all', type: 'all', scale: 'all', date: 'Latest' });
    } else {
      setActiveFilters(prev => ({ ...prev, [cat]: val }));
    }
  };

  return (
    <div className="h-full flex flex-col bg-page-bg overflow-hidden relative selection:bg-accent-primary selection:text-white">

      {/* ─── Main Content (Scrollable) ─── */}
      <main className="flex-1 overflow-y-auto px-6 py-10 md:px-12">
        <div className="mx-auto max-w-7xl space-y-12">

          {/* ─── Header: Premium Breadcrumbs & Identity ─── */}
          <section className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-2">
            <div className="space-y-1 animate-in fade-in slide-in-from-left duration-700">
              <nav className="flex items-center gap-2 text-[14px] text-header/40 dark:text-white/40 font-bold tracking-tight mb-2">
                <div className="flex items-center gap-1.5 hover:text-header dark:hover:text-white cursor-pointer transition-colors">
                  <Folder className="w-4 h-4 text-accent-primary" />
                  <span>Workspace</span>
                </div>
                <ChevronRight className="w-3.5 h-3.5 opacity-20" />
                <span className="text-header/60 dark:text-white/60 font-medium">All Assets</span>
              </nav>
              <h1 className="text-4xl md:text-5xl font-black text-header tracking-tighter">
                Knowledge Hub
              </h1>
              <p className="text-[15px] text-zinc-500 dark:text-white/60 font-medium max-w-2xl pt-1 leading-relaxed">
                The central command for your digital intelligence. Seamlessly manage uploaded datasets and AI-generated insights in one unified space.
              </p>
            </div>

            <div className="flex items-center gap-3">
              {/* <button className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-surface border border-border text-header hover:bg-elevated transition-all text-[13.5px] font-bold shadow-sm active:scale-95 hover:shadow-md">
                <Share2 className="w-4 h-4 text-muted" /> Share Workspace
              </button> */}
              <GlobalUploadButton
                className="!bg-header !text-page-bg !border-none !rounded-2xl !px-6 !py-3 !h-auto !text-[13.5px] !font-black !flex !items-center !gap-2.5 !shadow-xl !shadow-header/10 !hover:scale-[1.03] !transition-all"
                label={<><Plus className="w-4.5 h-4.5" strokeWidth={3} /> Add New Asset</>}
              />
            </div>
          </section>

          {/* ─── Premium Search & Dynamic Feature Bar ─── */}
          <section className="relative group animate-in zoom-in duration-500 delay-100">
            <div className="absolute inset-y-0 left-5 flex items-center pointer-events-none">
              <Search className="w-6 h-6 text-muted-strong transition-colors group-focus-within:text-accent-primary" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search across datasets, analysis, and reports..."
              className="w-full h-16 pl-14 pr-32 rounded-3xl bg-primary hover:bg-surface focus:bg-surface transition-all outline-none text-[16px] font-semibold text-primary placeholder:text-muted shadow-lg shadow-transparent focus:shadow-accent-primary/10 border border-border focus:border-primary"
            />
            <div className="absolute inset-y-2.5 right-2.5 flex items-center gap-2" ref={filterRef}>
              <div className="h-8 w-px bg-border/50 mx-1 hidden sm:block" />
              <button
                onClick={() => setShowFilter(!showFilter)}
                className={cn(
                  "flex items-center gap-2 px-6 py-2.5 rounded-2xl transition-all duration-300 text-[13.5px] font-semibold active:scale-95 border",
                  showFilter
                    ? "bg-accent-primary text-primary border-accent-primary shadow-lg shadow-accent-primary/20"
                    : "bg-elevated hover:bg-active text-primary"
                )}
              >
                <Filter className="w-4 h-4 text-current" />
                Filter Hub
              </button>

              <AnimatePresence>
                {showFilter && (
                  <FilterDropdown
                    isOpen={showFilter}
                    onClose={() => setShowFilter(false)}
                    activeFilters={activeFilters}
                    onFilterChange={handleFilterChange}
                  />
                )}
              </AnimatePresence>
            </div>
          </section>

          {/* ─── Section: Recent Intelligence (Cards) ─── */}
          {!searchQuery && recentDatasets.length > 0 && (
            <motion.section
              initial="hidden"
              animate="visible"
              variants={fadeUp}
              className="space-y-6"
            >
              <div className="flex items-center justify-between px-1">
                <h2 className="text-[14px] font-black text-header uppercase tracking-widest flex items-center gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-accent-primary animate-pulse" />
                  Latest Assets
                </h2>
                <button className="text-[13px] font-black text-accent-primary hover:text-accent-primary/80 transition-colors flex items-center gap-1 group">
                  View All <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
              </div>
              <motion.div
                variants={containerStagger}
                className="flex gap-6 overflow-x-auto pb-6 pt-1 no-scrollbar sm:grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
              >
                {recentDatasets.map((d) => (
                  <RecentCard key={getDatasetId(d)} dataset={d} onChat={goChat} />
                ))}
              </motion.div>
            </motion.section>
          )}

          {/* ─── Section: All Assets (The Modern Table) ─── */}
          <motion.section
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="space-y-6 pt-4"
          >
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-3">
                <h2 className="text-[14px] font-black text-header uppercase tracking-widest flex items-center gap-2.5">
                  <HardDrive className="w-4.5 h-4.5 text-ocean" /> Workspace Assets
                </h2>
                <div className="px-3 py-1 rounded-full bg-slate-100 dark:bg-white/[0.05] border border-slate-200 dark:border-white/10 text-[11px] font-black text-header/60 dark:text-white/60 uppercase tracking-wider">
                  {filteredDatasets.length} Objects
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-2 rounded-lg hover:bg-elevated text-muted transition-colors"><Grid className="w-4 h-4" /></button>
                <button className="p-2 rounded-lg bg-surface border border-border text-header shadow-sm"><List className="w-4 h-4" /></button>
              </div>
            </div>

            <div className="bg-slate-50 dark:bg-white/[0.03] rounded-[20px] p-2 overflow-hidden shadow-2xl border border-slate-150 dark:border-white/10">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-100 dark:bg-white/[0.05] rounded-2xl overflow-hidden">
                    <th className="py-5 pl-6 pr-3 text-[11px] font-black text-header/50 dark:text-white/40 uppercase tracking-[0.1em]">Asset Description</th>
                    <th className="py-5 px-3 text-[11px] font-black text-header/50 dark:text-white/40 uppercase tracking-[0.1em]">Modification</th>
                    <th className="py-5 px-3 text-[11px] font-black text-header/50 dark:text-white/40 uppercase tracking-[0.1em]">Lifecycle</th>
                    <th className="py-5 px-3 text-[11px] font-black text-header/50 dark:text-white/40 uppercase tracking-[0.1em]">Dataset Scale</th>
                    <th className="py-5 pl-3 pr-6"></th>
                  </tr>
                </thead>
                <motion.tbody variants={containerStagger}>
                  {loading && datasets.length === 0 ? (
                    [...Array(5)].map((_, i) => (
                      <tr key={i} className="animate-pulse">
                        <td className="py-7 px-6"><div className="h-12 bg-elevated/60 rounded-2xl w-full"></div></td>
                        <td className="py-7 px-3"><div className="h-6 bg-elevated/60 rounded-lg w-28"></div></td>
                        <td className="py-7 px-3"><div className="h-8 bg-elevated/60 rounded-full w-24"></div></td>
                        <td className="py-7 px-3"><div className="h-6 bg-elevated/60 rounded-lg w-20"></div></td>
                        <td className="py-7 px-6 text-right"><div className="h-10 bg-elevated/60 rounded-xl w-32 ml-auto"></div></td>
                      </tr>
                    ))
                  ) : filteredDatasets.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="py-32 text-center">
                        <motion.div
                          initial={{ scale: 0.9, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          className="inline-block"
                        >
                          <div className="mx-auto w-24 h-24 rounded-[2.5rem] bg-surface border-2 border-dashed border-border flex items-center justify-center mb-6 shadow-xl">
                            <HardDrive className="w-10 h-10 text-muted/20" />
                          </div>
                          <h3 className="text-2xl font-black text-header tracking-tight">Vast Silence in Your Library</h3>
                          <p className="text-muted-strong font-medium mt-2 max-w-sm mx-auto">
                            No assets matched your current filters. Clear your search or deposit your first data stream to begin.
                          </p>
                          {searchQuery && (
                            <button
                              onClick={() => setSearchQuery("")}
                              className="mt-6 text-sm font-black text-accent-primary hover:underline underline-offset-4"
                            >
                              Reset All Filters
                            </button>
                          )}
                        </motion.div>
                      </td>
                    </tr>
                  ) : (
                    filteredDatasets.map((d) => (
                      <ListRow
                        key={getDatasetId(d)}
                        dataset={d}
                        onChat={goChat}
                        onCharts={goCharts}
                        onDelete={askDelete}
                      />
                    ))
                  )}
                </motion.tbody>
              </table>
            </div>
          </motion.section>

          {/* ─── Page Tip / Stats ─── */}
          <section className="flex flex-col md:flex-row items-center justify-between gap-6 pt-10 border-t border-border/30">
            <div className="flex items-center gap-4 text-muted-strong font-bold text-sm">
              <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-emerald-400" /> Active System</span>
              <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-accent-primary" /> Workspace Ready</span>
            </div>
            <p className="text-[12px] text-muted-strong font-bold uppercase tracking-widest text-center md:text-right">
              © 2026 DataSage.ai Premium Intelligence Hub
            </p>
          </section>

        </div>
      </main>

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
