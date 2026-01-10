import React, { useState, useEffect, useMemo } from 'react';
import {
  File, X, CheckCircle, AlertCircle, Database, BarChart3,
  MessageSquare, Calendar, Hash, Columns, Search,
  Grid, List, Trash2, RefreshCw, MoreVertical, Filter,
  ArrowUpRight, Sparkles, Layers
} from 'lucide-react';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import useDatasetStore from '../store/datasetStore';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { cn } from '../lib/utils';
import GlobalUploadButton from '../components/GlobalUploadButton';
import DeleteConfirmModal from '../components/DeleteConfirmModal';

// --- Animation Variants ---
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring", stiffness: 100, damping: 15 }
  },
  exit: {
    opacity: 0,
    scale: 0.9,
    transition: { duration: 0.2 }
  }
};

// --- Helper Components ---

const StatusBadge = ({ status }) => {
  const config = {
    completed: { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", icon: CheckCircle },
    processing: { color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", icon: AlertCircle },
    error: { color: "text-rose-400", bg: "bg-rose-500/10", border: "border-rose-500/20", icon: X },
    default: { color: "text-slate-400", bg: "bg-slate-500/10", border: "border-slate-500/20", icon: CheckCircle }
  };

  const { color, bg, border, icon: Icon } = config[status] || config.default;

  return (
    <div className={cn("flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border backdrop-blur-md", bg, border, color)}>
      <Icon className="w-3.5 h-3.5" />
      <span className="capitalize">{status || 'Unknown'}</span>
    </div>
  );
};

const FileIcon = ({ name }) => {
  const ext = name?.split('.').pop()?.toLowerCase() || '';

  let gradient = "from-slate-500 to-slate-600";
  let Icon = File;

  if (['csv', 'xls', 'xlsx'].includes(ext)) {
    gradient = "from-emerald-500 to-teal-600";
    Icon = Database;
  } else if (['json', 'xml'].includes(ext)) {
    gradient = "from-amber-500 to-orange-600";
    Icon = Layers;
  } else if (['pdf', 'txt'].includes(ext)) {
    gradient = "from-blue-500 to-indigo-600";
    Icon = File;
  }

  return (
    <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center shadow-lg bg-gradient-to-br", gradient)}>
      <Icon className="w-6 h-6 text-white drop-shadow-md" />
    </div>
  );
};

const DatasetCard = ({ dataset, viewMode, onClick, onDelete, onAnalyze, onVisualize }) => {
  const isGrid = viewMode === 'grid';

  return (
    <motion.div
      layout
      variants={itemVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl transition-colors hover:bg-white/10 hover:border-white/20 hover:shadow-2xl hover:shadow-primary/10",
        isGrid ? "p-6 flex flex-col h-full" : "p-4 flex items-center gap-6"
      )}
      onClick={onClick}
    >
      {/* Glow Effect */}
      <div className="absolute -inset-px bg-gradient-to-br from-primary/20 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />

      {/* Header / Icon */}
      <div className={cn("flex items-start justify-between", isGrid ? "w-full mb-6" : "shrink-0")}>
        <div className="flex items-center gap-4">
          <FileIcon name={dataset.name || dataset.filename} />
          {isGrid && (
            <div className="min-w-0 flex-1">
              <h3 className="font-semibold text-lg text-white truncate" title={dataset.name}>
                {dataset.name || dataset.filename || 'Unnamed Dataset'}
              </h3>
              <p className="text-xs text-slate-400 mt-1 flex items-center gap-2">
                <Calendar className="w-3 h-3" />
                {new Date(dataset.created_at).toLocaleDateString()}
              </p>
            </div>
          )}
        </div>

        {isGrid && (
          <StatusBadge status={dataset.status} />
        )}
      </div>

      {/* Content for List View */}
      {!isGrid && (
        <div className="flex-1 min-w-0 grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
          <div className="md:col-span-1">
            <h3 className="font-semibold text-lg text-white truncate">
              {dataset.name || dataset.filename}
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              {new Date(dataset.created_at).toLocaleDateString()}
            </p>
          </div>

          <div className="flex items-center gap-6 text-sm text-slate-400">
            <div className="flex items-center gap-2">
              <Hash className="w-4 h-4 text-primary" />
              <span>{dataset.row_count?.toLocaleString() || '-'} rows</span>
            </div>
            <div className="flex items-center gap-2">
              <Columns className="w-4 h-4 text-secondary" />
              <span>{dataset.column_count || '-'} cols</span>
            </div>
          </div>

          <div className="flex justify-end">
            <StatusBadge status={dataset.status} />
          </div>
        </div>
      )}

      {/* Metrics for Grid View */}
      {isGrid && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="p-3 rounded-xl bg-black/20 border border-white/5">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <Hash className="w-3 h-3" /> Rows
            </div>
            <div className="text-lg font-mono font-medium text-white">
              {dataset.row_count?.toLocaleString() || '-'}
            </div>
          </div>
          <div className="p-3 rounded-xl bg-black/20 border border-white/5">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <Columns className="w-3 h-3" /> Columns
            </div>
            <div className="text-lg font-mono font-medium text-white">
              {dataset.column_count || '-'}
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className={cn("flex items-center gap-2 mt-auto", !isGrid && "shrink-0")}>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={(e) => { e.stopPropagation(); onAnalyze(dataset); }}
          className="flex-1 px-4 py-2 rounded-lg bg-primary/10 text-primary border border-primary/20 hover:bg-primary hover:text-white transition-all text-sm font-medium flex items-center justify-center gap-2"
        >
          <MessageSquare className="w-4 h-4" />
          <span className={cn(!isGrid && "hidden lg:inline")}>Chat</span>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={(e) => { e.stopPropagation(); onVisualize(dataset); }}
          className="px-4 py-2 rounded-lg bg-secondary/10 text-secondary border border-secondary/20 hover:bg-secondary hover:text-white transition-all flex items-center justify-center"
          title="Visualize"
        >
          <BarChart3 className="w-4 h-4" />
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.05, rotate: 10 }}
          whileTap={{ scale: 0.95 }}
          onClick={(e) => { e.stopPropagation(); onDelete(dataset); }}
          className="px-3 py-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
          title="Delete"
        >
          <Trash2 className="w-4 h-4" />
        </motion.button>
      </div>
    </motion.div>
  );
};

// --- Main Component ---

const Datasets = () => {
  const { datasets, loading, fetchDatasets, deleteDataset } = useDatasetStore();
  const [viewMode, setViewMode] = useState('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, dataset: null });
  const navigate = useNavigate();

  // Initial Fetch
  useEffect(() => {
    fetchDatasets();
  }, []);

  // Filter & Sort
  const filteredDatasets = useMemo(() => {
    return datasets.filter(d =>
      (d.name || d.filename || '').toLowerCase().includes(searchQuery.toLowerCase())
    ).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [datasets, searchQuery]);

  // Stats
  const stats = useMemo(() => ({
    total: datasets.length,
    rows: datasets.reduce((acc, d) => acc + (d.row_count || 0), 0),
    processed: datasets.filter(d => d.status === 'completed').length
  }), [datasets]);

  const handleDeleteConfirm = async () => {
    if (!deleteModal.dataset) return;
    const result = await deleteDataset(deleteModal.dataset.id);
    if (result.success) toast.success('Dataset deleted');
    setDeleteModal({ isOpen: false, dataset: null });
  };

  return (
    <div className="min-h-screen w-full p-6 space-y-8 text-slate-200 bg-[#030712] relative overflow-hidden">
      {/* Ambient Background Effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/5 blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-cyan-500/5 blur-[120px]" />
        <div className="absolute top-[40%] left-[30%] w-[30%] h-[30%] rounded-full bg-purple-500/5 blur-[100px]" />
      </div>

      <div className="relative z-10 space-y-8">

        {/* Page Header */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="space-y-2"
          >
            <h1 className="text-4xl font-bold text-white tracking-tight flex items-center gap-3">
              <Database className="w-10 h-10 text-primary" />
              Data Assets
            </h1>
            <p className="text-slate-400 text-lg max-w-2xl">
              Manage, analyze, and visualize your datasets in a high-performance workspace.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-3"
          >
            <GlobalUploadButton />
          </motion.div>
        </div>

        {/* Stats Overview */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-4"
        >
          {[
            { label: 'Total Datasets', value: stats.total, icon: Layers, color: 'text-blue-400', bg: 'bg-blue-500/10' },
            { label: 'Total Rows', value: stats.rows.toLocaleString(), icon: Hash, color: 'text-purple-400', bg: 'bg-purple-500/10' },
            { label: 'Processed & Ready', value: stats.processed, icon: Sparkles, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
          ].map((stat, i) => (
            <div key={i} className="relative overflow-hidden rounded-2xl border border-white/5 bg-white/5 p-5 backdrop-blur-sm flex items-center gap-4 group hover:border-white/10 transition-colors">
              <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", stat.bg)}>
                <stat.icon className={cn("w-6 h-6", stat.color)} />
              </div>
              <div>
                <div className="text-2xl font-bold text-white font-mono">{stat.value}</div>
                <div className="text-sm text-slate-400">{stat.label}</div>
              </div>
              {/* Background decoration */}
              <div className={cn("absolute -right-4 -bottom-4 w-24 h-24 rounded-full opacity-10 blur-2xl", stat.bg.replace('/10', ''))} />
            </div>
          ))}
        </motion.div>

        {/* Toolbar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="sticky top-4 z-30 flex flex-col sm:flex-row gap-4 items-center justify-between bg-[#030712]/80 backdrop-blur-xl p-2 rounded-2xl border border-white/10 shadow-xl"
        >
          <div className="relative w-full sm:max-w-md group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-primary transition-colors" />
            <input
              type="text"
              placeholder="Search datasets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/5 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:bg-white/10 transition-all"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <button
              onClick={() => fetchDatasets(true)}
              className="p-2.5 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-5 h-5" />
            </button>

            <div className="h-6 w-px bg-white/10 mx-1" />

            <div className="flex bg-white/5 p-1 rounded-xl border border-white/5">
              <button
                onClick={() => setViewMode('grid')}
                className={cn(
                  "p-2 rounded-lg transition-all duration-200",
                  viewMode === 'grid' ? "bg-primary text-white shadow-lg" : "text-slate-400 hover:text-white"
                )}
              >
                <Grid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  "p-2 rounded-lg transition-all duration-200",
                  viewMode === 'list' ? "bg-primary text-white shadow-lg" : "text-slate-400 hover:text-white"
                )}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </motion.div>

        {/* Content Grid/List */}
        <AnimatePresence mode="wait">
          {loading && datasets.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center py-32 text-center"
            >
              <div className="w-16 h-16 border-4 border-primary/30 border-t-primary rounded-full animate-spin mb-6" />
              <p className="text-slate-400 animate-pulse">Loading your data assets...</p>
            </motion.div>
          ) : filteredDatasets.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center py-32 text-center border border-dashed border-white/10 rounded-3xl bg-white/5"
            >
              <div className="w-20 h-20 rounded-full bg-white/5 flex items-center justify-center mb-6">
                <Database className="w-10 h-10 text-slate-600" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">No datasets found</h3>
              <p className="text-slate-400 max-w-md mb-8">
                {searchQuery ? "No results match your search." : "Upload your first dataset to unlock the power of AI analytics."}
              </p>
              {!searchQuery && <GlobalUploadButton variant="default" />}
            </motion.div>
          ) : (
            <motion.div
              layout
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className={cn(
                "grid gap-6",
                viewMode === 'grid'
                  ? "grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                  : "grid-cols-1"
              )}
            >
              <AnimatePresence>
                {filteredDatasets.map((dataset) => (
                  <DatasetCard
                    key={dataset.id}
                    dataset={dataset}
                    viewMode={viewMode}
                    onClick={() => navigate(`/app/chat?dataset=${dataset.id}`)}
                    onDelete={handleDeleteConfirm} // Pass the function to open modal
                    onAnalyze={(d) => navigate(`/app/chat?dataset=${d.id}`)}
                    onVisualize={(d) => navigate(`/analytics?dataset=${d.id}`)}
                  />
                ))}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>

        <DeleteConfirmModal
          isOpen={deleteModal.isOpen}
          onClose={() => setDeleteModal({ isOpen: false, dataset: null })}
          onConfirm={handleDeleteConfirm}
          itemName={deleteModal.dataset?.name}
        />
      </div>
    </div>
  );
};

export default Datasets;