import React, { useState, useEffect, useRef } from 'react';
import { Menu, Bell, Database, ChevronDown, LogOut, Settings, User } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ThemeToggle from '../common/ThemeToggle';
import GlassCard from '../common/GlassCard';
import GlobalUploadButton from '../GlobalUploadButton';
import { useAuth } from '../../store/authStore';
import useDatasetStore from '../../store/datasetStore';
import { toast } from 'react-hot-toast';
import { cn } from '../../lib/utils';
import { useNavigate } from 'react-router-dom';

const Header = ({ toggleSidebar }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { selectedDataset, setSelectedDataset, fetchDatasets, datasets } = useDatasetStore();
  const [showDatasetDropdown, setShowDatasetDropdown] = useState(false);
  const [showProfileCard, setShowProfileCard] = useState(false);
  const profileRef = useRef(null);
  const notificationCount = 3; // Stub

  useEffect(() => {
    if (datasets.length === 0) {
      fetchDatasets();
    }
  }, [datasets.length, fetchDatasets]);

  // Close profile card when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setShowProfileCard(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleDatasetSelect = (dataset) => {
    setSelectedDataset(dataset);
    setShowDatasetDropdown(false);
    toast.success(`Switched to "${dataset.name}"`);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
    toast.success('Logged out successfully');
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
          <div className="relative">
            <button
              className="flex items-center gap-2 px-3 py-2 rounded-lg glass-effect border border-border/50 text-foreground hover:bg-accent/50 focus-visible-ring transition-all"
              aria-label="Select dataset"
              aria-expanded={showDatasetDropdown}
              onClick={() => setShowDatasetDropdown((open) => !open)}
              type="button"
            >
              <Database className="w-4 h-4" />
              <span className="hidden sm:inline truncate max-w-32">
                {selectedDataset ? (selectedDataset.name || 'Unnamed Dataset') : 'Select Dataset'}
              </span>
              {/* Dropdown chevron */}
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

          {/* User Avatar with ProfileCard Dropdown */}
          <div className="relative" ref={profileRef}>
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={() => setShowProfileCard(!showProfileCard)}
              className="relative w-10 h-10 rounded-full bg-gradient-to-br from-primary to-cyan-500 flex items-center justify-center text-primary-foreground font-semibold text-lg shadow-lg shadow-primary/30 hover:shadow-primary/50 transition-all ring-2 ring-white/10 hover:ring-white/30"
              aria-label="Open profile menu"
            >
              {user?.username?.[0]?.toUpperCase() || user?.full_name?.[0]?.toUpperCase() || 'U'}
              {/* Online indicator */}
              <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 rounded-full border-2 border-slate-900" />
            </motion.button>

            <AnimatePresence>
              {showProfileCard && (
                <motion.div
                  initial={{ opacity: 0, y: 10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.95 }}
                  transition={{ duration: 0.2, ease: 'easeOut' }}
                  className="absolute right-0 mt-3 w-80 z-50"
                >
                  <div className="relative overflow-hidden rounded-2xl bg-slate-900/95 border border-white/10 shadow-2xl backdrop-blur-xl">
                    {/* Profile Header */}
                    <div className="h-20 bg-gradient-to-br from-slate-800 to-slate-900 relative">
                      <div className="absolute inset-0 bg-gradient-to-t from-slate-900/90 to-transparent" />
                    </div>

                    <div className="px-5 pb-5 relative">
                      {/* Avatar */}
                      <div className="relative -mt-10 mb-3">
                        <div className="w-20 h-20 rounded-xl p-0.5 bg-gradient-to-br from-cyan-400 to-purple-500 shadow-lg">
                          <div className="w-full h-full rounded-[10px] bg-gradient-to-br from-primary to-cyan-500 flex items-center justify-center text-primary-foreground font-bold text-2xl">
                            {user?.username?.[0]?.toUpperCase() || user?.full_name?.[0]?.toUpperCase() || 'U'}
                          </div>
                        </div>
                        <div className="absolute -bottom-1 -right-1 bg-slate-900 rounded-full p-1 border border-white/10">
                          <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
                        </div>
                      </div>

                      {/* User Info */}
                      <div className="space-y-1 mb-4">
                        <h3 className="text-lg font-bold text-white">
                          {user?.full_name || user?.username || 'User'}
                        </h3>
                        <p className="text-sm text-cyan-400">{user?.email}</p>
                      </div>

                      {/* Quick Stats */}
                      <div className="grid grid-cols-3 gap-2 mb-4">
                        <div className="p-2 rounded-lg bg-white/5 text-center">
                          <div className="text-base font-bold text-white">{datasets.length}</div>
                          <div className="text-xs text-slate-400">Datasets</div>
                        </div>
                        <div className="p-2 rounded-lg bg-white/5 text-center">
                          <div className="text-base font-bold text-white">12</div>
                          <div className="text-xs text-slate-400">Charts</div>
                        </div>
                        <div className="p-2 rounded-lg bg-white/5 text-center">
                          <div className="text-base font-bold text-white">5</div>
                          <div className="text-xs text-slate-400">Insights</div>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="space-y-2">
                        <button
                          onClick={() => {
                            navigate('/app/settings');
                            setShowProfileCard(false);
                          }}
                          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-all text-sm"
                        >
                          <Settings className="w-4 h-4" />
                          Settings
                        </button>
                        <button
                          onClick={handleLogout}
                          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 transition-all text-sm"
                        >
                          <LogOut className="w-4 h-4" />
                          Sign Out
                        </button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </motion.header>
  );
};

export default Header;
