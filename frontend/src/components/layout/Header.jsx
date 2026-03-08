import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  ChevronRight, Database, ChevronDown, Upload, Search,
  Moon, Sun, Monitor, Check, LogOut, Settings, User,
  Command, Rows3, Columns3, Clock, Sparkles
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import UploadModal from '../features/datasets/UploadModal';
import { useAuth } from '../../store/authStore';
import useDatasetStore from '../../store/datasetStore';
import { useTheme } from '../../store/themeStore';
import { toast } from 'react-hot-toast';
import { cn } from '../../lib/utils';

/* ─── Route → breadcrumb label map ─── */
const ROUTE_LABELS = {
  app: null,
  dashboard: 'Dashboard',
  datasets: 'Datasets',
  chat: 'AI Chat',
  charts: 'Charts Studio',
  settings: 'Settings',
};

/* ─── Theme options ─── */
const THEME_OPTIONS = [
  { value: 'dark', icon: Moon, label: 'Dark' },
  { value: 'light', icon: Sun, label: 'Light' },
  { value: 'system', icon: Monitor, label: 'System' },
];

/* ─── Breadcrumbs ─── */
const Breadcrumbs = () => {
  const location = useLocation();

  const crumbs = useMemo(() => {
    const segments = location.pathname.split('/').filter(Boolean);
    const result = [];
    let pathAccum = '';

    for (const seg of segments) {
      pathAccum += `/${seg}`;
      const label = ROUTE_LABELS[seg];
      if (label === null) continue;
      if (label) {
        result.push({ label, path: pathAccum });
      } else {
        result.push({ label: seg.charAt(0).toUpperCase() + seg.slice(1), path: pathAccum });
      }
    }
    return result;
  }, [location.pathname]);

  if (crumbs.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-[13px] min-w-0">
      {crumbs.map((crumb, idx) => {
        const isLast = idx === crumbs.length - 1;
        return (
          <React.Fragment key={crumb.path}>
            {idx > 0 && (
              <ChevronRight className="w-3 h-3 text-granite/60 shrink-0" />
            )}
            {isLast ? (
              <span className="text-pearl font-medium truncate">{crumb.label}</span>
            ) : (
              <Link
                to={crumb.path}
                className="text-granite hover:text-pearl/80 transition-colors truncate"
              >
                {crumb.label}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
};

/* ─── Compact dataset indicator ─── */
const DatasetIndicator = ({ dataset, onClick, isOpen }) => {
  if (!dataset) {
    return (
      <button
        onClick={onClick}
        className={cn(
          "flex items-center gap-2 px-2.5 py-1.5 rounded-lg transition-all duration-150",
          "text-granite hover:text-pearl/80 hover:bg-white/[0.04]",
          "border border-transparent hover:border-white/[0.06]",
          "text-[13px]"
        )}
      >
        <Database className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">No dataset</span>
        <ChevronDown className={cn("w-3 h-3 transition-transform", isOpen && "rotate-180")} />
      </button>
    );
  }

  const rowCount = dataset.row_count ? Number(dataset.row_count).toLocaleString() : '—';
  const colCount = dataset.column_count || dataset.columns?.length || '—';

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-2.5 py-1.5 rounded-lg transition-all duration-150",
        "hover:bg-white/[0.04] border border-white/[0.04] hover:border-white/[0.08]",
        "text-[13px] group",
        isOpen && "bg-white/[0.04] border-white/[0.08]"
      )}
    >
      <div className="w-5 h-5 rounded bg-ocean/15 flex items-center justify-center shrink-0">
        <Database className="w-3 h-3 text-ocean" />
      </div>
      <span className="text-pearl/90 font-medium truncate max-w-[140px] hidden sm:inline">
        {dataset.name || dataset.filename || 'Unnamed'}
      </span>
      <span className="hidden md:flex items-center gap-1.5 text-granite/70 text-[11px] font-mono tabular-nums">
        <Rows3 className="w-3 h-3" />{rowCount}
        <span className="text-white/10">·</span>
        <Columns3 className="w-3 h-3" />{colCount}
      </span>
      <ChevronDown className={cn("w-3 h-3 text-granite/50 transition-transform", isOpen && "rotate-180")} />
    </button>
  );
};

/* ─── Dataset dropdown panel ─── */
const DatasetDropdown = ({ datasets, selectedDataset, onSelect, onUpload }) => {
  const selectedId = selectedDataset?.id || selectedDataset?._id;

  return (
    <motion.div
      initial={{ opacity: 0, y: -6, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -6, scale: 0.98 }}
      transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
      className="absolute left-0 top-full mt-1.5 z-50 w-72"
    >
      <div className="bg-[#141419] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/60 overflow-hidden">
        {/* Section label */}
        <div className="px-3 pt-3 pb-2">
          <div className="text-[10px] uppercase tracking-[0.08em] text-granite/60 font-medium mb-2">
            Datasets
          </div>
        </div>

        {/* Dataset list */}
        <div className="max-h-56 overflow-y-auto px-1.5 pb-1.5">
          {datasets.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <Database className="w-5 h-5 text-granite/40 mx-auto mb-2" />
              <p className="text-[12px] text-granite/60">No datasets uploaded</p>
            </div>
          ) : (
            datasets.map((ds) => {
              const dsId = ds.id || ds._id;
              const isSelected = dsId === selectedId;
              return (
                <button
                  key={dsId}
                  onClick={() => onSelect(ds)}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left transition-all duration-100",
                    isSelected
                      ? "bg-ocean/10 text-pearl"
                      : "text-pearl/70 hover:bg-white/[0.04] hover:text-pearl"
                  )}
                >
                  <div className={cn(
                    "w-6 h-6 rounded flex items-center justify-center shrink-0",
                    isSelected ? "bg-ocean/20" : "bg-white/[0.04]"
                  )}>
                    <Database className={cn("w-3 h-3", isSelected ? "text-ocean" : "text-granite/60")} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium truncate">
                      {ds.name || ds.filename || 'Unnamed'}
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-granite/60 font-mono tabular-nums">
                      <span>{ds.row_count ? Number(ds.row_count).toLocaleString() : '—'} rows</span>
                      <span className="text-white/10">·</span>
                      <span>{ds.column_count || '—'} cols</span>
                    </div>
                  </div>
                  {isSelected && (
                    <Check className="w-3.5 h-3.5 text-ocean shrink-0" />
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Upload action */}
        <div className="border-t border-white/[0.06] px-1.5 py-1.5">
          <button
            onClick={onUpload}
            className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-[13px] text-gold/80 hover:text-gold hover:bg-gold/[0.06] transition-all"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload new dataset</span>
          </button>
        </div>
      </div>
    </motion.div>
  );
};

/* ─── Theme Switcher ─── */
const ThemeSwitcher = () => {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (!ref.current?.contains(e.target)) setIsOpen(false);
    };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, [isOpen]);

  const ActiveIcon = resolvedTheme === 'dark' ? Moon : Sun;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-150",
          "text-granite hover:text-pearl/80 hover:bg-white/[0.05]",
          isOpen && "bg-white/[0.05] text-pearl/80"
        )}
        aria-label="Theme"
        title="Toggle theme"
      >
        <ActiveIcon className="w-4 h-4" />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.96 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 top-full mt-1.5 z-50"
          >
            <div className="bg-[#141419] border border-white/[0.08] rounded-lg shadow-xl shadow-black/40 p-1 min-w-[130px]">
              {THEME_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => { setTheme(opt.value); setIsOpen(false); }}
                  className={cn(
                    "w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[13px] transition-all",
                    theme === opt.value
                      ? "text-pearl bg-white/[0.06]"
                      : "text-granite hover:text-pearl/80 hover:bg-white/[0.04]"
                  )}
                >
                  <opt.icon className="w-3.5 h-3.5" />
                  <span>{opt.label}</span>
                  {theme === opt.value && <Check className="w-3 h-3 ml-auto text-ocean" />}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

/* ─── User display ─── */
const UserDisplay = ({ user }) => {
  const initials = (user?.username?.[0] || user?.full_name?.[0] || 'U').toUpperCase();

  return (
    <div className="flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-lg border border-transparent">
      {/* Avatar */}
      <div className="w-6 h-6 rounded-md bg-gradient-to-br from-pearl/80 to-gold/60 flex items-center justify-center text-noir text-[11px] font-bold shrink-0">
        {initials}
      </div>
      <span className="hidden md:block text-[13px] text-pearl/80 font-medium truncate max-w-[100px]">
        {user?.username || user?.full_name || 'User'}
      </span>
    </div>
  );
};

/* ═══════════════════════════════════════════
   HEADER — Main Component
   ═══════════════════════════════════════════ */
const Header = () => {
  const { user } = useAuth();
  const { selectedDataset, setSelectedDataset, fetchDatasets, datasets } = useDatasetStore();
  const [showDatasetDropdown, setShowDatasetDropdown] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const datasetRef = useRef(null);

  useEffect(() => {
    if (datasets.length === 0) fetchDatasets();
  }, [datasets.length, fetchDatasets]);

  // Close dataset dropdown on outside click
  useEffect(() => {
    if (!showDatasetDropdown) return;
    const handler = (e) => {
      if (!datasetRef.current?.contains(e.target)) setShowDatasetDropdown(false);
    };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, [showDatasetDropdown]);

  const handleDatasetSelect = (dataset) => {
    setSelectedDataset(dataset);
    setShowDatasetDropdown(false);
    toast.success(`Switched to "${dataset.name || dataset.filename}"`);
  };

  const handleUploadSuccess = () => {
    fetchDatasets();
    setShowUploadModal(false);
    setShowDatasetDropdown(false);
  };

  return (
    <>
      <header className="sticky top-0 z-40 h-14 flex items-center border-b border-white/[0.04] bg-noir/90 backdrop-blur-xl">
        {/* ── Left: Breadcrumbs ── */}
        <div className="flex items-center gap-3 px-4 min-w-0 flex-1">
          <Breadcrumbs />

          {/* Separator dot */}
          <div className="w-0.5 h-3.5 rounded-full bg-white/[0.06] hidden sm:block shrink-0" />

          {/* Dataset context */}
          <div className="relative hidden sm:block" ref={datasetRef}>
            <DatasetIndicator
              dataset={selectedDataset}
              isOpen={showDatasetDropdown}
              onClick={() => setShowDatasetDropdown(!showDatasetDropdown)}
            />
            <AnimatePresence>
              {showDatasetDropdown && (
                <DatasetDropdown
                  datasets={datasets}
                  selectedDataset={selectedDataset}
                  onSelect={handleDatasetSelect}
                  onUpload={() => { setShowDatasetDropdown(false); setShowUploadModal(true); }}
                />
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* ── Right: Actions ── */}
        <div className="flex items-center gap-2 px-3">
          {/* Global Upload Action */}
          <button
            onClick={() => setShowUploadModal(true)}
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-pearl/10 hover:bg-pearl/20 text-pearl text-[13px] font-medium transition-all border border-white/5"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload</span>
          </button>

          {/* Mobile Upload Icon */}
          <button
            onClick={() => setShowUploadModal(true)}
            className="sm:hidden w-8 h-8 rounded-lg flex items-center justify-center text-granite hover:text-pearl hover:bg-white/[0.05] transition-all"
          >
            <Upload className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-white/[0.06] mx-1" />

          {/* Theme switcher */}
          <ThemeSwitcher />

          {/* Separator */}
          <div className="w-px h-4 bg-white/[0.06] mx-1.5" />

          {/* User Display */}
          <UserDisplay user={user} />
        </div>
      </header>

      {/* Upload modal */}
      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onUploadSuccess={handleUploadSuccess}
      />
    </>
  );
};

export default Header;
