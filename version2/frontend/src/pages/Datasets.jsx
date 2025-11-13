import React, { useState, useEffect } from 'react';
import { 
  File, X, CheckCircle, AlertCircle, Database, BarChart3, 
  MessageSquare, Eye, Calendar, Hash, Columns, Upload,
  Search, Filter, Grid, List, MoreVertical, Trash2, Edit3, RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import GlassCard from '../components/common/GlassCard';
import DeleteConfirmModal from '../components/DeleteConfirmModal';
import GlobalUploadButton from '../components/GlobalUploadButton';
import useDatasetStore from '../store/datasetStore';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { cn } from '../lib/utils';

const Datasets = () => {
  const { 
    datasets, 
    loading, 
    error, 
    fetchDatasets, 
    deleteDataset 
  } = useDatasetStore();
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, dataset: null });
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // grid or list
  const [sortBy, setSortBy] = useState('created_at'); // created_at, name, size
  const navigate = useNavigate();

  useEffect(() => {
    fetchDatasets();
    
    const interval = setInterval(() => {
      fetchDatasets(true); // Force refresh
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  const handleDeleteClick = (dataset) => {
    setDeleteModal({ isOpen: true, dataset });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteModal.dataset) return;

    try {
      const result = await deleteDataset(deleteModal.dataset.id);
      if (result.success) {
        toast.success('Dataset deleted successfully');
      } else {
        toast.error('Failed to delete dataset');
      }
    } catch (error) {
      toast.error('Failed to delete dataset');
    } finally {
      setDeleteModal({ isOpen: false, dataset: null });
    }
  };

  const handleDatasetClick = (dataset) => {
    navigate(`/app/chat?dataset=${dataset.id}`);
  };

  const filteredDatasets = datasets.filter(dataset =>
    (dataset.name || dataset.filename || 'Unnamed Dataset').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sortedDatasets = [...filteredDatasets].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        const nameA = a.name || a.filename || 'Unnamed Dataset';
        const nameB = b.name || b.filename || 'Unnamed Dataset';
        return nameA.localeCompare(nameB);
      case 'size':
        return (b.row_count || 0) - (a.row_count || 0);
      case 'created_at':
      default:
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    }
  });

  const getFileIcon = (dataset) => {
    const name = (dataset.name || dataset.filename || '').toLowerCase();
    if (name.includes('csv')) return '📊';
    if (name.includes('json')) return '📋';
    if (name.includes('xlsx') || name.includes('excel')) return '📈';
    return '📄';
  };

  const getStatusColor = (dataset) => {
    if (dataset.status === 'processing') return 'text-yellow-400';
    if (dataset.status === 'error') return 'text-red-400';
    return 'text-green-400';
  };

  const getStatusIcon = (dataset) => {
    if (dataset.status === 'processing') return AlertCircle;
    if (dataset.status === 'error') return X;
    return CheckCircle;
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col lg:flex-row lg:items-center justify-between gap-4"
      >
        <div>
          <h1 className="text-3xl font-bold text-foreground">Datasets</h1>
          <p className="text-muted-foreground mt-2">
            Manage and analyze your data files
          </p>
        </div>
      </motion.div>

      {/* Controls */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex flex-col sm:flex-row gap-4 items-center justify-between"
      >
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search datasets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg glass-effect border border-border/50 text-foreground focus:ring-primary focus:border-primary transition-all"
          />
      </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {/* Sort */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-2 rounded-lg glass-effect border border-border/50 text-foreground focus:ring-primary"
          >
            <option value="created_at">Sort by Date</option>
            <option value="name">Sort by Name</option>
            <option value="size">Sort by Size</option>
          </select>

          {/* Refresh Button */}
          <button
            onClick={() => fetchDatasets(true)}
            className="p-2 rounded-lg glass-effect border border-border/50 transition-all text-muted-foreground hover:text-foreground hover:bg-black/20"
            title="Refresh datasets"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {/* View Mode */}
          <div className="flex rounded-lg glass-effect border border-border/50 p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                "p-2 rounded-md transition-all",
                viewMode === 'grid' 
                  ? "bg-primary text-primary-foreground" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Grid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "p-2 rounded-md transition-all",
                viewMode === 'list' 
                  ? "bg-primary text-primary-foreground" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </motion.div>

      {/* Stats Cards */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-1 md:grid-cols-4 gap-4"
      >
        <GlassCard className="p-4" elevated>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-cyan-500 flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{datasets.length}</p>
              <p className="text-sm text-muted-foreground">Total Datasets</p>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4" elevated>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">
                {datasets.filter(d => d.status === 'completed').length}
              </p>
              <p className="text-sm text-muted-foreground">Processed</p>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4" elevated>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
              <Hash className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">
                {datasets.reduce((sum, d) => sum + (d.row_count || 0), 0).toLocaleString()}
              </p>
              <p className="text-sm text-muted-foreground">Total Rows</p>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4" elevated>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <Columns className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">
                {datasets.reduce((sum, d) => sum + (d.column_count || 0), 0)}
              </p>
              <p className="text-sm text-muted-foreground">Total Columns</p>
            </div>
          </div>
        </GlassCard>
      </motion.div>


      {/* Datasets List */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        {loading ? (
          <GlassCard className="p-12 text-center" elevated>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4"
            />
            <p className="text-muted-foreground">Loading datasets...</p>
          </GlassCard>
        ) : sortedDatasets.length === 0 ? (
          <GlassCard className="p-12 text-center" elevated>
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            >
              <Database className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
              <h3 className="text-lg font-semibold text-foreground mb-2">No datasets found</h3>
              <p className="text-muted-foreground mb-4">
                {searchQuery ? 'No datasets match your search.' : 'Upload your first dataset to get started!'}
              </p>
              {!searchQuery && (
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <GlobalUploadButton variant="outline" />
                </motion.div>
              )}
            </motion.div>
          </GlassCard>
        ) : (
          <div className={cn(
            "gap-6",
            viewMode === 'grid' 
              ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3" 
              : "space-y-4"
          )}>
            <AnimatePresence>
              {sortedDatasets.map((dataset, index) => (
                <motion.div
                  key={dataset.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ delay: index * 0.05 }}
                  layout
                >
                  <GlassCard 
                    className={cn(
                      "group cursor-pointer transition-all duration-300 hover:scale-[1.02] hover:shadow-xl",
                      viewMode === 'list' ? "p-4" : "p-6"
                    )}
                    elevated
                    hover
                    onClick={() => handleDatasetClick(dataset)}
                  >
                    {viewMode === 'grid' ? (
                      // Grid View
                      <>
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex items-center gap-3">
                            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-cyan-500 flex items-center justify-center text-2xl">
                              {getFileIcon(dataset)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <h3 className="text-lg font-semibold text-foreground truncate">
                                {dataset.name || dataset.filename || 'Unnamed Dataset'}
                              </h3>
                              <div className="flex items-center gap-2 mt-1">
                                <div className={cn("flex items-center gap-1 text-xs", getStatusColor(dataset))}>
                                  {React.createElement(getStatusIcon(dataset), { className: "w-3 h-3" })}
                                  {dataset.status || 'completed'}
                                </div>
                              </div>
                            </div>
                          </div>
                          <motion.button 
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteClick(dataset);
                            }}
                            className="opacity-0 group-hover:opacity-100 p-2 rounded-lg hover:bg-red-500/20 hover:text-red-400 transition-all"
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                          >
                            <Trash2 className="w-4 h-4" />
                          </motion.button>
                        </div>

                        <div className="space-y-2 text-sm text-muted-foreground mb-4">
                          <div className="flex items-center gap-2">
                            <Hash className="w-4 h-4" />
                            <span>{dataset.row_count?.toLocaleString() || 'N/A'} rows</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Columns className="w-4 h-4" />
                            <span>{dataset.column_count || 'N/A'} columns</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4" />
                            <span>{dataset.created_at ? new Date(dataset.created_at).toLocaleDateString() : 'Unknown'}</span>
                          </div>
                        </div>

                        <div className="flex gap-2">
                          <motion.button 
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDatasetClick(dataset);
                            }}
                            className="flex-1 py-2 px-4 rounded-lg bg-gradient-to-r from-primary to-cyan-500 text-primary-foreground text-sm font-medium hover:from-primary/90 hover:to-cyan-500/90 transition-all flex items-center justify-center gap-2"
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            <MessageSquare className="w-4 h-4" />
                            Analyze
                          </motion.button>
                          <motion.button 
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/analytics?dataset=${dataset.id}`);
                            }}
                            className="px-4 py-2 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/90 transition-all flex items-center justify-center"
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            <BarChart3 className="w-4 h-4" />
                          </motion.button>
                        </div>
                      </>
                    ) : (
                      // List View
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-cyan-500 flex items-center justify-center text-lg">
                          {getFileIcon(dataset)}
                </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-lg font-semibold text-foreground truncate">
                            {dataset.name || dataset.filename || 'Unnamed Dataset'}
                </h3>
                          <div className="flex items-center gap-4 text-sm text-muted-foreground">
                            <span>{dataset.row_count?.toLocaleString() || 'N/A'} rows</span>
                            <span>{dataset.column_count || 'N/A'} columns</span>
                            <span>{dataset.created_at ? new Date(dataset.created_at).toLocaleDateString() : 'Unknown'}</span>
                          </div>
                </div>
                        <div className="flex items-center gap-2">
                          <motion.button 
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDatasetClick(dataset);
                            }}
                            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-all flex items-center gap-2"
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            <MessageSquare className="w-4 h-4" />
                            Analyze
                          </motion.button>
                          <motion.button 
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/analytics?dataset=${dataset.id}`);
                            }}
                            className="px-4 py-2 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/90 transition-all"
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            <BarChart3 className="w-4 h-4" />
                          </motion.button>
                          <motion.button 
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteClick(dataset);
                            }}
                            className="p-2 rounded-lg hover:bg-red-500/20 hover:text-red-400 transition-all"
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                          >
                            <Trash2 className="w-4 h-4" />
                          </motion.button>
                        </div>
                </div>
                    )}
              </GlassCard>
                </motion.div>
            ))}
            </AnimatePresence>
          </div>
        )}
      </motion.div>

      {/* Delete Confirmation Modal */}
      <DeleteConfirmModal
        isOpen={deleteModal.isOpen}
        onClose={() => setDeleteModal({ isOpen: false, dataset: null })}
        onConfirm={handleDeleteConfirm}
        title="Delete Dataset"
        message="Are you sure you want to delete this dataset? This action cannot be undone and will remove all associated data and insights."
        itemName={deleteModal.dataset?.name || deleteModal.dataset?.filename}
        isLoading={loading}
      />
    </div>
  );
};

export default Datasets;