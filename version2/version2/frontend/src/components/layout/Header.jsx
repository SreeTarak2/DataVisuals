import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Database, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ThemeToggle from '../common/ThemeToggle';
import GlassCard from '../common/GlassCard';
import GlobalUploadButton from '../GlobalUploadButton';
import ProfileCard from '../ProfileCard';
import { useAuth } from '../../store/authStore';
import useDatasetStore from '../../store/datasetStore';
import { toast } from 'react-hot-toast';
import { cn } from '../../lib/utils';

const MotionHeader = motion.header;
const MotionDiv = motion.div;

const Header = () => {
  const { user } = useAuth();
  const { selectedDataset, setSelectedDataset, fetchDatasets, datasets } = useDatasetStore();
  const [showDatasetDropdown, setShowDatasetDropdown] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [profilePosition, setProfilePosition] = useState({ top: 0, left: 0, width: 380 });
  const profileButtonRef = useRef(null);
  const profilePopoverRef = useRef(null);

  const updateProfilePosition = useCallback(() => {
    if (!profileButtonRef.current || typeof window === 'undefined') return;
    const rect = profileButtonRef.current.getBoundingClientRect();
    const maxWidth = Math.min(380, window.innerWidth - 16);
    const left = Math.min(
      Math.max(8, rect.right - maxWidth),
      window.innerWidth - maxWidth - 8
    );
    setProfilePosition({
      top: rect.bottom + 10,
      left,
      width: maxWidth,
    });
  }, []);

  useEffect(() => {
    if (datasets.length === 0) {
      fetchDatasets();
    }
  }, [datasets.length, fetchDatasets]);

  useEffect(() => {
    if (!isProfileOpen) return;
    updateProfilePosition();
    const handleScroll = () => updateProfilePosition();
    window.addEventListener('resize', updateProfilePosition);
    window.addEventListener('scroll', handleScroll, true);
    return () => {
      window.removeEventListener('resize', updateProfilePosition);
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [isProfileOpen, updateProfilePosition]);

  useEffect(() => {
    if (!isProfileOpen) return;

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setIsProfileOpen(false);
      }
    };

    const handlePointerDown = (event) => {
      const target = event.target;
      if (
        profilePopoverRef.current?.contains(target) ||
        profileButtonRef.current?.contains(target)
      ) {
        return;
      }
      setIsProfileOpen(false);
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('pointerdown', handlePointerDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('pointerdown', handlePointerDown);
    };
  }, [isProfileOpen]);

  const handleDatasetSelect = (dataset) => {
    setSelectedDataset(dataset);
    setShowDatasetDropdown(false);
    setIsProfileOpen(false);
    toast.success(`Switched to "${dataset.name}"`);
  };

  const handleDatasetDropdownToggle = () => {
    setShowDatasetDropdown((open) => {
      const next = !open;
      if (next) setIsProfileOpen(false);
      return next;
    });
  };

  const handleProfileToggle = () => {
    setIsProfileOpen((open) => {
      const next = !open;
      if (next) setShowDatasetDropdown(false);
      return next;
    });
  };

  return (
    <>
      <MotionHeader
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
                onClick={handleDatasetDropdownToggle}
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
            <ThemeToggle />

            {/* User Profile */}
            <button
              ref={profileButtonRef}
              onClick={handleProfileToggle}
              aria-label="Toggle profile card"
              aria-haspopup="dialog"
              aria-expanded={isProfileOpen}
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
      </MotionHeader>

      {typeof document !== 'undefined' &&
        createPortal(
          <AnimatePresence>
            {isProfileOpen && (
              <>
                <MotionDiv
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => setIsProfileOpen(false)}
                  className="fixed inset-0 z-[58] bg-black/50 backdrop-blur-[2px]"
                />
                <MotionDiv
                  ref={profilePopoverRef}
                  role="dialog"
                  aria-label="User profile panel"
                  initial={{ opacity: 0, y: -8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.98 }}
                  transition={{ duration: 0.18 }}
                  className="fixed z-[60]"
                  style={{
                    top: profilePosition.top,
                    left: profilePosition.left,
                    width: profilePosition.width,
                    maxWidth: 'min(92vw, 380px)',
                  }}
                >
                  <ProfileCard
                    variant="popover"
                    onAction={() => setIsProfileOpen(false)}
                  />
                </MotionDiv>
              </>
            )}
          </AnimatePresence>,
          document.body
        )}
    </>
  );
};

export default Header;
