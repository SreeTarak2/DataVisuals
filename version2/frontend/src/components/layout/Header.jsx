import React, { useState, useEffect } from 'react';
import { Menu, Bell, User, Database } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ThemeToggle from '../common/ThemeToggle';
import GlassCard from '../common/GlassCard';
import GlobalUploadButton from '../GlobalUploadButton';
import UploadModal from '../UploadModal';
import { useAuth } from '../../contexts/AuthContext';
import useDatasetStore from '../../store/datasetStore';
import { toast } from 'react-hot-toast';
import { cn } from '../../lib/utils';

const Header = ({ toggleSidebar }) => {
  const { user, logout } = useAuth();
  const { selectedDataset, setSelectedDataset, fetchDatasets, datasets } = useDatasetStore();
  const [showDatasetDropdown, setShowDatasetDropdown] = useState(false);
  const notificationCount = 3; // Stub

  useEffect(() => {
    if (datasets.length === 0) {
      fetchDatasets();
    }
  }, [datasets.length, fetchDatasets]);

  const handleDatasetSelect = (dataset) => {
    setSelectedDataset(dataset);
    setShowDatasetDropdown(false);
    toast.success(`Switched to "${dataset.name}"`);
  };

  return (
    <motion.header
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      className="sticky top-0 z-40 glass-effect border-b border-border/50"
    >
      <div className="flex items-center justify-between px-4 md:px-6 py-4">
        <div className="flex items-center gap-4 flex-1">
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-lg glass-effect focus-visible-ring transition-all lg:hidden"
            aria-label="Toggle sidebar"
          >
            <Menu className="w-5 h-5 text-foreground" />
          </button>

          {/* Dataset Selector */}
          <div className="relative" onMouseEnter={() => setShowDatasetDropdown(true)} onMouseLeave={() => setShowDatasetDropdown(false)}>
            <button
              className="flex items-center gap-2 px-3 py-2 rounded-lg glass-effect border border-border/50 text-foreground hover:bg-accent/50 focus-visible-ring transition-all"
              aria-label="Select dataset"
            >
              <Database className="w-4 h-4" />
              <span className="hidden sm:inline truncate max-w-32">
                {selectedDataset ? (selectedDataset.name || 'Unnamed Dataset') : 'Select Dataset'}
              </span>
            </button>
            <AnimatePresence>
              {showDatasetDropdown && (
                <motion.div
                  initial={{ opacity: 1, y: 0 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 1, y: 0 }}
                  className="absolute left-0 mt-2 w-64 max-h-60 overflow-y-auto"
                >
                  <GlassCard className="py-2 shadow-2xl bg-black">
                    {datasets.length === 0 ? (
                      <div className="px-4 py-2 text-sm text-muted-foreground">
                        No datasets found please upload one
                      </div>
                    ) : (
                      datasets.map((dataset) => (
                        <button
                          key={dataset.id}
                          onClick={() => handleDatasetSelect(dataset)}
                          className="w-full px-4 py-2 text-left hover:bg-black/50 focus-visible-ring rounded"
                        >
                          <div className="truncate">{dataset.name || dataset.filename || 'Unnamed Dataset'}</div>
                          <div className="text-xs text-muted-foreground">{dataset.row_count} rows</div>
                        </button>
                      ))
                    )}
                  </GlassCard>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <div className="flex items-center gap-2 md:gap-4">
          <GlobalUploadButton variant="outline" className="hidden sm:inline-flex" />

          <motion.button
            whileTap={{ scale: 0.95 }}
            className="relative p-2 rounded-lg glass-effect focus-visible-ring"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5 text-foreground" />
            {notificationCount > 0 && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="absolute -top-1 -right-1 w-5 h-5 bg-destructive rounded-full flex items-center justify-center text-xs font-bold text-destructive-foreground"
              >
                {notificationCount}
              </motion.span>
            )}
          </motion.button>

          <ThemeToggle />
        </div>
      </div>
    </motion.header>
  );
};

export default Header;
