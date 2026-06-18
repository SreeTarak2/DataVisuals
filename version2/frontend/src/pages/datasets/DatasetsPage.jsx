import React, { useState, useMemo, useEffect } from 'react';
import { 
  Search, 
  Plus, 
  Database, 
  FileText, 
  Trash2, 
  Clock, 
  Activity,
  HardDrive,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Shield,
  Filter,
  RefreshCw,
  Eye
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import useDatasetStore from "../../store/datasetStore";
import { useTheme } from "../../store/themeStore";
import { datasetAPI } from "../../services/api";
import DeleteConfirmModal from '../../components/common/DeleteConfirmModal';
import UploadModal from '../../components/features/datasets/UploadModal';
import SearchInput from '../../components/ui/SearchInput';
import { cn } from "../../lib/utils";

/* ═══════════════════════════════════════════════
   SIGNAL PRODUCT DESIGN: WORKSPACE INVENTORY
   Palette: Adaptable Theme (Light / Dark)
   Typography: Clean, Human-Readable
   ═══════════════════════════════════════════════ */

const DatasetsPage = () => {
  const { datasets, loading, fetchDatasets, deleteDataset, reprocessDataset, setProcessingDataset } = useDatasetStore();
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const [searchQuery, setSearchQuery] = useState('');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, dataset: null });

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  // --- LOGIC ---
  const filteredDatasets = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return datasets.filter(d => 
      (d.name || d.original_filename || '').toLowerCase().includes(q)
    );
  }, [datasets, searchQuery]);

  const formatBytes = (bytes, decimals = 2) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  const totalSize = useMemo(() => 
    datasets.reduce((acc, curr) => acc + (Number(curr.file_size || curr.size) || 0), 0), 
    [datasets]
  );

  const stats = [
    { label: 'Total Datasets', value: datasets.length, icon: Database },
    { label: 'Total Scale', value: totalSize > 0 ? formatBytes(totalSize) : '0 Bytes', icon: HardDrive },
    { label: 'Catalog Health', value: '99.9%', icon: Activity },
  ];

  const handleDeleteConfirm = async () => {
    if (deleteModal.dataset) {
      const id = deleteModal.dataset.id || deleteModal.dataset.dataset_id;
      const result = await deleteDataset(id);
      if (result.success) toast.success("Dataset removed from catalog");
      setDeleteModal({ isOpen: false, dataset: null });
    }
  };

  const handleRetryDataset = async (datasetId) => {
    const result = await reprocessDataset(datasetId);
    if (result.success) {
      setProcessingDataset(datasetId);
      toast.success('Reprocessing started');
    }
  };

  const handleRefreshSheet = async (datasetId) => {
    const refreshToast = toast.loading('Refreshing Google Sheet...');
    try {
      await datasetAPI.reimportGoogleSheets(datasetId);
      toast.success('Sheet refresh started — data will update shortly', { id: refreshToast });
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to refresh sheet';
      toast.error(msg, { id: refreshToast });
    }
  };

  const isFailedDataset = (dataset) => {
    const s = (dataset.status || dataset.processing_status || '').toLowerCase();
    return s === 'failed' || s === 'error';
  };

  // --- SUB-COMPONENTS ---
  const KpiCard = ({ label, value, icon: Icon }) => (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "p-5 rounded-xl transition-all border",
        isDark 
          ? "bg-[#131316] border-white/[0.04] hover:border-white/[0.08]" 
          : "bg-white border-gray-200 hover:border-gray-300 shadow-sm"
      )}
    >
      <div className="flex items-center gap-4">
        <div className="p-2.5 rounded-lg bg-orange-500/10 text-orange-500/80">
          <Icon size={18} />
        </div>
        <div>
          <p className={cn("text-[10px] font-bold uppercase tracking-wider mb-0.5", isDark ? "text-gray-500" : "text-gray-400")}>{label}</p>
          <p className={cn("text-xl font-semibold tracking-tight", isDark ? "text-white" : "text-gray-900")}>{value}</p>
        </div>
      </div>
    </motion.div>
  );

  const StatusBadge = ({ status, isProcessed }) => {
    const s = (status || '').toLowerCase();
    const isSuccess = isProcessed || s === 'completed' || s === 'active' || s === 'ready';
    const isWarning = s === 'warning' || s === 'processing' || s === 'in-progress';
    
    let colorClass = isDark ? 'bg-gray-500/10 text-gray-400' : 'bg-gray-100 text-gray-600';
    let dotClass = 'bg-gray-500';
    
    if (isSuccess) {
      colorClass = isDark ? 'bg-emerald-500/10 text-emerald-400' : 'bg-emerald-50 text-emerald-700';
      dotClass = 'bg-emerald-500';
    } else if (isWarning) {
      colorClass = isDark ? 'bg-amber-500/10 text-amber-400' : 'bg-amber-50 text-amber-700';
      dotClass = 'bg-amber-500';
    } else if (s === 'failed' || s === 'error') {
      colorClass = isDark ? 'bg-rose-500/10 text-rose-400' : 'bg-rose-50 text-rose-700';
      dotClass = 'bg-rose-500';
    }

    return (
      <span className={cn("px-2.5 py-1 rounded text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 w-fit", colorClass)}>
        <span className={cn("w-1.5 h-1.5 rounded-full", dotClass)} />
        {status || 'Queued'}
      </span>
    );
  };

  return (
    <div className={cn(
      "h-full flex flex-col overflow-hidden relative selection:bg-orange-500/30 selection:text-white transition-colors duration-300",
      isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
    )}>
      
      {/* Background ambient lighting */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-orange-500/[0.02] blur-[150px] pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-orange-500/[0.01] blur-[150px] pointer-events-none" />

      {/* Scrollable Workspace */}
      <main className="flex-1 overflow-y-auto px-4 py-10 md:px-8 relative z-10">
        <div className="mx-auto max-w-[1200px] space-y-12">
          
          {/* Header */}
          <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 animate-in fade-in slide-in-from-top-4 duration-500">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-orange-500/80">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                Data Catalog
              </div>
              <h1 className={cn("text-4xl font-semibold tracking-tight leading-none", isDark ? "text-white" : "text-gray-900")}>
                Assets Inventory
              </h1>
              <p className={cn("text-sm max-w-xl leading-relaxed", isDark ? "text-gray-400" : "text-gray-650")}>
                Explore, manage, and analyze your connected datasets. Launch AI analytics and data understanding reports.
              </p>
            </div>
            
            <div className="flex items-center gap-4 w-full md:w-auto">
              <SearchInput 
                placeholder="Search datasets..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                width="100%"
                className="w-full md:w-80"
                style={{
                  paddingTop: '10px',
                  paddingBottom: '10px',
                }}
              />
              <button 
                type="button"
                onClick={() => setIsUploadModalOpen(true)}
                className="bg-orange-600 hover:bg-orange-500 active:bg-orange-700 text-white px-5 py-2.5 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition-all active:scale-95 shadow-lg shadow-orange-950/20 whitespace-nowrap h-[40px] cursor-pointer"
              >
                <Plus size={16} />
                Add Dataset
              </button>
            </div>
          </header>

          {/* KPI Dashboard */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {stats.map((stat, idx) => <KpiCard key={idx} {...stat} />)}
          </div>

          {/* Table Section */}
          <section className="space-y-6">
            <div className="flex items-center justify-between px-2">
              <h3 className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-500")}>
                Connected Datasets <span className="ml-2 text-orange-500/80 font-normal">/ {filteredDatasets.length} total</span>
              </h3>
            </div>

            <div className={cn(
              "overflow-x-auto rounded-xl border shadow-2xl transition-colors duration-300",
              isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
            )}>
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className={cn(
                    "border-b transition-colors",
                    isDark ? "bg-white/[0.01] border-white/[0.04]" : "bg-gray-50 border-gray-200"
                  )}>
                    <th className={cn("py-4 px-4 text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-500")}>Dataset Name</th>
                    <th className={cn("py-4 px-4 text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-500")}>Source Type</th>
                    <th className={cn("py-4 px-4 text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-500")}>Record Count</th>
                    <th className={cn("py-4 px-4 text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-500")}>Processing Status</th>
                    <th className={cn("py-4 px-4 text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-500")}>Uploaded Date</th>
                    <th className="py-4 px-4"></th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence mode="popLayout">
                    {filteredDatasets.map((dataset) => (
                      <motion.tr 
                        key={dataset.id || dataset.dataset_id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className={cn(
                          "group border-b last:border-b-0 transition-colors cursor-default",
                          isDark 
                            ? "border-white/[0.03] hover:bg-white/[0.015]" 
                            : "border-gray-200 hover:bg-gray-50/50"
                        )}
                      >
                        <td className="py-4 px-4">
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              "w-9 h-9 rounded-lg flex items-center justify-center transition-all group-hover:text-orange-500 group-hover:border-orange-500/30 group-hover:bg-orange-500/5",
                              isDark 
                                ? "bg-white/[0.03] border border-white/[0.04] text-gray-400" 
                                : "bg-gray-50 border border-gray-200 text-gray-550"
                            )}>
                              {dataset.type === 'Database' || dataset.source_type === 'database' ? <Database size={16} /> : <FileText size={16} />}
                            </div>
                            <div>
                              <p className={cn("text-sm font-semibold group-hover:text-orange-500 transition-colors", isDark ? "text-white" : "text-gray-900")}>
                                {dataset.name || dataset.original_filename || 'Untitled Dataset'}
                              </p>
                              <p className={cn("text-[10px] mt-0.5", isDark ? "text-gray-500" : "text-gray-400")}>
                                {dataset.column_count || '—'} Columns Detected
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className={cn("py-4 px-4 text-xs font-medium capitalize", isDark ? "text-gray-400" : "text-gray-600")}>
                          {dataset.type || dataset.source_type || 'File'}
                        </td>
                        <td className={cn("py-4 px-4 text-xs font-semibold tabular-nums", isDark ? "text-white" : "text-gray-900")}>
                          {dataset.row_count?.toLocaleString() || '—'} <span className={cn("text-[10px] ml-1 uppercase font-normal", isDark ? "text-gray-500" : "text-gray-450")}>Rows</span>
                        </td>
                        <td className="py-4 px-4">
                          <StatusBadge 
                            status={dataset.status || dataset.processing_status} 
                            isProcessed={dataset.is_processed} 
                          />
                        </td>
                        <td className={cn("py-4 px-4 text-xs tabular-nums", isDark ? "text-gray-400" : "text-gray-600")}>
                          {dataset.created_at ? new Date(dataset.created_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="py-4 px-4 text-right">
                          <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-all translate-x-2 group-hover:translate-x-0">
                            <button 
                              type="button"
                              onClick={() => navigate(`/app/datasets/${dataset.id || dataset.dataset_id}/understanding`)}
                              className={cn(
                                "p-2 rounded-lg transition-all cursor-pointer hover:text-orange-400 hover:bg-orange-500/10",
                                isDark ? "text-gray-400" : "text-gray-500"
                              )}
                              title="Dataset Understanding Report"
                            >
                              <Eye size={16} />
                            </button>
                            <button 
                              type="button"
                              onClick={() => navigate(`/app/chat?dataset=${dataset.id || dataset.dataset_id}`)}
                              className={cn(
                                "p-2 rounded-lg transition-all cursor-pointer hover:text-orange-400 hover:bg-orange-500/10",
                                isDark ? "text-gray-400" : "text-gray-500"
                              )}
                              title="Chat with this dataset"
                            >
                              <ArrowRight size={16} />
                            </button>
                            {isFailedDataset(dataset) && (
                              <button
                                type="button"
                                onClick={() => handleRetryDataset(dataset.id || dataset.dataset_id)}
                                className="p-2 text-amber-500 hover:text-amber-400 hover:bg-amber-500/10 rounded-lg transition-all cursor-pointer"
                                title="Retry processing"
                              >
                                <RefreshCw size={16} />
                              </button>
                            )}
                            {dataset.source_type === 'google_sheets' && (
                              <button
                                type="button"
                                onClick={() => handleRefreshSheet(dataset.id || dataset.dataset_id)}
                                className="p-2 text-emerald-500 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-all cursor-pointer"
                                title="Refresh Google Sheet data"
                              >
                                <RefreshCw size={16} />
                              </button>
                            )}
                            <button 
                              type="button"
                              onClick={() => setDeleteModal({ isOpen: true, dataset })}
                              className={cn(
                                "p-2 rounded-lg transition-all cursor-pointer hover:text-rose-500 hover:bg-rose-500/10",
                                isDark ? "text-gray-400" : "text-gray-550"
                              )}
                              title="Delete"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>

            {/* Empty State */}
            {filteredDatasets.length === 0 && !loading && (
              <div className={cn(
                "py-24 text-center space-y-4 border rounded-xl",
                isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
              )}>
                <div className={cn(
                  "w-16 h-16 rounded-full flex items-center justify-center mx-auto border",
                  isDark ? "bg-white/[0.02] border-white/[0.04] text-gray-500" : "bg-gray-50 border-gray-200 text-gray-400"
                )}>
                  <Database size={24} />
                </div>
                <div className="space-y-1">
                  <p className={cn("font-semibold text-sm", isDark ? "text-white" : "text-gray-900")}>No datasets found</p>
                  <p className={cn("text-xs max-w-xs mx-auto", isDark ? "text-gray-500" : "text-gray-400")}>Upload a file or connect a database source to begin analysis.</p>
                </div>
              </div>
            )}
          </section>

          {/* Studio Footer */}
          <footer className={cn(
            "pt-12 pb-6 flex flex-col md:flex-row justify-between items-center gap-4 border-t opacity-60",
            isDark ? "border-white/[0.02]" : "border-gray-200"
          )}>
            <div className="flex items-center gap-6 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
              <span className="flex items-center gap-1.5"><Shield size={12} className="text-orange-500/80" /> Encrypted Vault</span>
              <span>v3.2.0 Stable</span>
            </div>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
              Built with Signal
            </p>
          </footer>
        </div>
      </main>

      {/* Production Modals */}
      <DeleteConfirmModal
        isOpen={deleteModal.isOpen}
        onClose={() => setDeleteModal({ isOpen: false, dataset: null })}
        onConfirm={handleDeleteConfirm}
        itemName={deleteModal.dataset?.name || deleteModal.dataset?.original_filename}
      />

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onProcessingStart={() => setIsUploadModalOpen(false)}
      />
    </div>
  );
};

export default DatasetsPage;
