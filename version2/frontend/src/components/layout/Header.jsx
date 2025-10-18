import React, { useState, useEffect } from 'react';
import { Menu, Bell, User, Database } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ThemeToggle from '../common/ThemeToggle';
import GlassCard from '../common/GlassCard';
import GlobalUploadButton from '../GlobalUploadButton';
import { useAuth } from '../../contexts/AuthContext';
import useDatasetStore from '../../store/datasetStore';
import { toast } from 'react-hot-toast';
import { cn } from '../../lib/utils';

const Header = ({ toggleSidebar }) => {
  const { user, logout } = useAuth();
  const { selectedDataset, setSelectedDataset, fetchDatasets, datasets } = useDatasetStore();
  const [showUserDropdown, setShowUserDropdown] = useState(false);
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
                {selectedDataset ? (selectedDataset.name || selectedDataset.filename || 'Unnamed Dataset') : 'Select Dataset'}
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
                        No datasets yet. <button onClick={() => window.location.href = '/datasets'} className="text-primary underline">Upload one</button>
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
          
          {/* <motion.div 
            className="relative"
            onMouseEnter={() => setShowUserDropdown(true)}
            onMouseLeave={() => setShowUserDropdown(false)}
          >
            <motion.button 
              className="p-2 rounded-lg glass-effect focus-visible-ring transition-all duration-200 hover:bg-white/10" 
              aria-label="User menu"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <User className="w-5 h-5 text-foreground" />
            </motion.button>
            <AnimatePresence>
              {showUserDropdown && (
                <motion.div
                  initial={{ opacity: 0, y: -10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.95 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  className="absolute right-0 mt-2 w-48 z-50"
                >
                  <GlassCard className="py-2 shadow-2xl bg-card/95 backdrop-blur-md border border-white/20">
                    <div className="px-4 py-2 text-sm text-muted-foreground border-b border-border/20">
                      {user?.username || user?.full_name || 'User'}<br />
                      <span className="text-xs">{user?.email}</span>
                    </div>
                    <motion.button 
                      className="w-full px-4 py-2 text-left hover:bg-accent/50 focus-visible-ring transition-all duration-200 flex items-center gap-2"
                      whileHover={{ x: 4 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <User className="w-4 h-4" />
                      Profile
                    </motion.button>
                    <motion.button 
                      onClick={logout}
                      className="w-full px-4 py-2 text-left hover:bg-red-500/20 hover:text-red-400 focus-visible-ring rounded-b-lg transition-all duration-200 flex items-center gap-2 group"
                      whileHover={{ x: 4 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <motion.div
                        className="w-4 h-4 flex items-center justify-center"
                        whileHover={{ rotate: 180 }}
                        transition={{ duration: 0.3 }}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                        </svg>
                      </motion.div>
                      <span className="group-hover:text-red-400 transition-colors duration-200">Logout</span>
                    </motion.button>
                  </GlassCard>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div> */}
        </div>
      </div>
    </motion.header>
  );
};

export default Header;
