import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Database, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ThemeToggle from '../common/ThemeToggle';
import GlassCard from '../common/GlassCard';
import GlobalUploadButton from '../GlobalUploadButton';
import { useAuth } from '../../store/authStore';
import useDatasetStore from '../../store/datasetStore';
import { toast } from 'react-hot-toast';
import { cn } from '../../lib/utils';

const Header = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
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
      <div className="flex items-center justify-between px-4 md:px-6 py-3">
        <div className="flex items-center gap-3 flex-1">
          {/* Dataset Selector */}
          <div className="relative">
            <button
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg glass-effect border border-border/50 text-foreground hover:bg-accent/50 focus-visible-ring transition-all"
              aria-label="Select dataset"
              aria-expanded={showDatasetDropdown}
              onClick={() => setShowDatasetDropdown((open) => !open)}
              type="button"
            >
              <Database className="w-4 h-4" />
              <span className="hidden sm:inline truncate max-w-32 text-sm">
                {selectedDataset ? (selectedDataset.name || 'Unnamed Dataset') : 'Select Dataset'}
              </span>
              <ChevronDown
                className={cn(
                  'w-4 h-4 text-foreground transform transition-transform',
                  showDatasetDropdown && 'rotate-180'
                )}
              />
            </button>
            <AnimatePresence>
              {showDatasetDropdown && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.12 }}
                  className="absolute left-0 mt-2 w-64 max-h-60 overflow-y-auto z-50"
                >
                  <GlassCard className="py-2 shadow-2xl bg-black">
                    {datasets.length === 0 ? (
                      <div className="px-4 py-2 text-sm text-muted-foreground">
                        No datasets found, please upload one
                      </div>
                    ) : (
                      datasets.map((dataset) => (
                        <button
                          key={dataset.id}
                          onClick={() => handleDatasetSelect(dataset)}
                          className="w-full px-4 py-2 text-left hover:bg-white/5 focus-visible-ring rounded text-sm"
                        >
                          <div className="truncate text-foreground">{dataset.name || dataset.filename || 'Unnamed Dataset'}</div>
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

        <div className="flex items-center gap-2 md:gap-3">
          <GlobalUploadButton variant="outline" className="hidden sm:inline-flex" />

          {/* <motion.button
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
          </motion.button> */}

          <ThemeToggle />

          {/* User Profile */}
          <button
            onClick={() => navigate('/app/profile')}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] transition-all ml-1 cursor-pointer border border-white/[0.04]"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#CAD2FD] to-[#C7BC92] flex items-center justify-center text-[#020203] font-semibold text-xs">
              {(user?.username?.[0] || user?.full_name?.[0] || 'U').toUpperCase()}
            </div>
            <div className="flex-col min-w-0 text-left hidden md:flex">
              <span className="text-sm font-medium text-foreground truncate max-w-[120px]">{user?.username || user?.full_name || 'User'}</span>
              <span className="text-[11px] text-muted-foreground truncate max-w-[120px]">{user?.email}</span>
            </div>
          </button>
        </div>
      </div>
    </motion.header>
  );
};

export default Header;
