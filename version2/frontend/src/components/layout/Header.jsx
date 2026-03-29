import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useLocation, Link } from 'react-router-dom';
import {
  ChevronRight, Database, ChevronDown, Upload, Search,
  Moon, Sun, Monitor, Check, LogOut, Settings, User,
  Command, Rows3, Columns3, Clock, Sparkles, RefreshCw, Loader2
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import UploadModal from '../features/datasets/UploadModal';
import { useAuth } from '../../store/authStore';
import useDatasetStore from '../../store/datasetStore';
import { useTheme } from '../../store/themeStore';
import useDashboardActionStore from '../../store/dashboardActionStore';
import { toast } from 'react-hot-toast';
import useSidebarStore from '../../store/sidebarStore';
import { PanelLeft } from 'lucide-react';
import { cn } from '../../lib/utils';

/* ─── Route → breadcrumb label map ─── */
const ROUTE_LABELS = {
  app: null,
  dashboard: 'Dashboard',
  workspace: 'Workspace',
  datasets: 'Workspace',
  chat: 'AI Chat',
  charts: 'Charts Studio',
  settings: 'Settings',
  analysis: 'Analysis',
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
      let label = ROUTE_LABELS[seg];
      if (label === null) continue;
      if (!label) {
        label = seg.charAt(0).toUpperCase() + seg.slice(1);
      }
      result.push({ label, path: pathAccum, segment: seg });
    }
    return result;
  }, [location.pathname]);

  if (crumbs.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-3 text-[13px] min-w-0">
      {crumbs.map((crumb, idx) => {
        const isLast = idx === crumbs.length - 1;
        const isInsights = crumb.label === 'Insights' || crumb.segment === 'insights';

        return (
          <React.Fragment key={crumb.path}>
            {idx > 0 && (
              <div className="w-px h-3 opacity-20 bg-current shrink-0" style={{ color: 'var(--text-muted)' }} />
            )}
            <div className="flex items-center gap-1.5 min-w-0">
              {isLast ? (
                <span className="font-semibold truncate tracking-tight" style={{ color: 'var(--text-header)' }}>{crumb.label}</span>
              ) : (
                <Link
                  to={crumb.path}
                  className="transition-colors truncate font-medium hover:opacity-80"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {crumb.label}
                </Link>
              )}
            </div>
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
          "flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 text-[13px] group",
          "hover:scale-[1.02] active:scale-[0.98]"
        )}
        style={{
          color: 'var(--text-header)',
          backgroundColor: isOpen ? 'var(--bg-elevated)' : 'var(--bg-surface)',
          border: '1px solid',
          borderColor: isOpen ? 'var(--accent-primary)' : 'var(--border)',
          boxShadow: isOpen ? 'var(--shadow-lg)' : 'var(--shadow-md)',
        }}
      >
        <Database className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)' }} />
        <span className="hidden sm:inline font-semibold">No dataset</span>
        <ChevronDown className={cn("w-3.5 h-3.5 transition-transform duration-300", isOpen && "rotate-180")} />
      </button>
    );
  }

  const rowCount = dataset.row_count ? Number(dataset.row_count).toLocaleString() : '—';
  const colCount = dataset.column_count || dataset.columns?.length || '—';

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 px-3 py-1.5 rounded-xl transition-all duration-200 text-[13px] group",
        "hover:scale-[1.02] active:scale-[0.98]"
      )}
      style={{
        backgroundColor: isOpen ? 'var(--bg-elevated)' : 'var(--bg-surface)',
        border: '1px solid',
        borderColor: isOpen ? 'var(--accent-primary)' : 'var(--border)',
        boxShadow: isOpen ? 'var(--shadow-lg)' : 'var(--shadow-md)',
      }}
    >
      <div
        className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0 shadow-sm"
        style={{ backgroundColor: 'var(--accent-purple-light)' }}
      >
        <Database className="w-3.5 h-3.5" style={{ color: 'var(--accent-purple)' }} />
      </div>
      <span
        className="font-semibold truncate max-w-[140px] hidden sm:inline"
        style={{ color: 'var(--text-header)' }}
      >
        {dataset.name || dataset.filename || 'Unnamed'}
      </span>
      <span
        className="hidden md:flex items-center gap-2 text-[11px] font-bold tabular-nums"
        style={{ color: 'var(--text-secondary)' }}
      >
        <div className="flex items-center gap-1 opacity-80">
          <Rows3 className="w-3.5 h-3.5" />{rowCount}
        </div>
        <span className="opacity-40">|</span>
        <div className="flex items-center gap-1 opacity-80">
          <Columns3 className="w-3.5 h-3.5" />{colCount}
        </div>
      </span>
      <ChevronDown
        className={cn("w-3.5 h-3.5 transition-transform duration-300", isOpen && "rotate-180")}
        style={{ color: 'var(--text-muted)' }}
      />
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
      <div
        className="rounded-xl overflow-hidden"
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        <div className="px-3 pt-3 pb-2">
          <div
            className="text-[10px] uppercase tracking-[0.08em] font-medium mb-2"
            style={{ color: 'var(--text-muted)' }}
          >
            Datasets
          </div>
        </div>

        <div className="max-h-56 overflow-y-auto px-1.5 pb-1.5">
          {datasets.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <Database className="w-5 h-5 mx-auto mb-2" style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
              <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>No datasets uploaded</p>
            </div>
          ) : (
            datasets.map((ds) => {
              const dsId = ds.id || ds._id;
              const isSelected = dsId === selectedId;
              return (
                <button
                  key={dsId}
                  onClick={() => onSelect(ds)}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left transition-all duration-100"
                  style={{
                    color: isSelected ? 'var(--text-header)' : 'var(--text-secondary)',
                    backgroundColor: isSelected ? 'var(--accent-primary-light)' : 'transparent',
                  }}
                >
                  <div
                    className="w-6 h-6 rounded flex items-center justify-center shrink-0"
                    style={{ backgroundColor: isSelected ? 'var(--accent-primary-light)' : 'var(--bg-elevated)' }}
                  >
                    <Database
                      className="w-3 h-3"
                      style={{ color: isSelected ? 'var(--accent-primary)' : 'var(--text-muted)' }}
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium truncate">
                      {ds.name || ds.filename || 'Unnamed'}
                    </div>
                    <div
                      className="flex items-center gap-2 text-[11px] font-mono tabular-nums"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      <span>{ds.row_count ? Number(ds.row_count).toLocaleString() : '—'} rows</span>
                      <span>·</span>
                      <span>{ds.column_count || '—'} cols</span>
                    </div>
                  </div>
                  {isSelected && (
                    <Check className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--accent-primary)' }} />
                  )}
                </button>
              );
            })
          )}
        </div>

        <div
          className="px-1.5 py-1.5"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <button
            onClick={onUpload}
            className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-[13px] transition-all"
            style={{ color: 'var(--accent-warning)' }}
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
        className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-150"
        style={{
          color: 'var(--text-secondary)',
          backgroundColor: isOpen ? 'var(--bg-elevated)' : 'transparent',
        }}
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
            <div
              className="rounded-lg p-1 min-w-[130px]"
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-lg)',
              }}
            >
              {THEME_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => { setTheme(opt.value); setIsOpen(false); }}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[13px] transition-all"
                  style={{
                    color: theme === opt.value ? 'var(--text-header)' : 'var(--text-secondary)',
                    backgroundColor: theme === opt.value ? 'var(--bg-elevated)' : 'transparent',
                  }}
                >
                  <opt.icon className="w-3.5 h-3.5" />
                  <span>{opt.label}</span>
                  {theme === opt.value && (
                    <Check className="w-3 h-3 ml-auto" style={{ color: 'var(--accent-primary)' }} />
                  )}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

/* ═══════════════════════════════════════════
   HEADER — Main Component
   ═══════════════════════════════════════════ */
const Header = () => {
  const { user } = useAuth();
  const { selectedDataset, setSelectedDataset, fetchDatasets, datasets } = useDatasetStore();
  const { toggle } = useSidebarStore();
  const [showDatasetDropdown, setShowDatasetDropdown] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const datasetRef = useRef(null);
  const location = useLocation();

  // Get redesign state and callbacks from store (synced from Dashboard component)
  const { isRedesigning, redesignAttempts, onRegenerate, MAX_REDESIGNS, onInsightsRefresh, insightsLoading } = useDashboardActionStore();

  // Check if on dashboard or insights page
  const isDashboardPage = location.pathname.includes('/dashboard');
  const isInsightsPage = location.pathname.includes('/insights');
  const showActionButton = isDashboardPage || isInsightsPage;

  // Choose the appropriate action based on current page
  const actionButtonClick = isDashboardPage ? onRegenerate : onInsightsRefresh;
  const isLoading = isDashboardPage ? isRedesigning : insightsLoading;
  const buttonLabel = isDashboardPage ? 'Redesign' : 'Refresh';
  const buttonLabelLoading = isDashboardPage ? 'Redesigning...' : 'Refreshing...';

  useEffect(() => {
    if (datasets.length === 0) fetchDatasets();
  }, [datasets.length, fetchDatasets]);

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

  return (
    <>
      <header
        className="sticky top-0 z-40 h-14 flex items-center"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div className="flex items-center gap-3 px-4 min-w-0 flex-1">
          <button
            onClick={toggle}
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-all hover:bg-elevated text-muted hover:text-header shrink-0"
            title="Toggle Sidebar"
          >
            <PanelLeft className="w-4.5 h-4.5" />
          </button>

          <div className="w-px h-4 opacity-50 bg-current shrink-0" style={{ color: 'var(--border)' }} />

          <Breadcrumbs />

          <div
            className="w-0.5 h-3.5 rounded-full hidden sm:block shrink-0"
            style={{ backgroundColor: 'var(--border)' }}
          />

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

        <div className="flex items-center gap-2 px-3">
          {/* Action button - show on dashboard (redesign) or insights (refresh) pages */}
          {showActionButton && actionButtonClick && selectedDataset && (
            <>
              <button
                onClick={actionButtonClick}
                disabled={isLoading || !selectedDataset?.is_processed || (isDashboardPage && (redesignAttempts ?? 0) >= (MAX_REDESIGNS ?? 5))}
                className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all"
                style={{
                  backgroundColor: (isDashboardPage && (redesignAttempts ?? 0) >= (MAX_REDESIGNS ?? 5)) ? 'var(--bg-elevated)' : 'var(--bg-elevated)',
                  color: (isDashboardPage && (redesignAttempts ?? 0) >= (MAX_REDESIGNS ?? 5)) ? 'var(--text-secondary)' : 'var(--text-header)',
                  border: '1px solid var(--border)',
                  cursor: (isDashboardPage && (redesignAttempts ?? 0) >= (MAX_REDESIGNS ?? 5)) ? 'not-allowed' : 'pointer',
                  opacity: (isDashboardPage && (redesignAttempts ?? 0) >= (MAX_REDESIGNS ?? 5)) ? 0.5 : 1,
                }}
                title={isDashboardPage ? `Redesign this dashboard (${redesignAttempts ?? 0}/${MAX_REDESIGNS ?? 5} used)` : 'Refresh insights'}
              >
                {isLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="w-3.5 h-3.5" />
                )}
                <span>{isLoading ? buttonLabelLoading : buttonLabel}</span>
              </button>

              <button
                onClick={actionButtonClick}
                disabled={isLoading || !selectedDataset?.is_processed || (isDashboardPage && (redesignAttempts ?? 0) >= (MAX_REDESIGNS ?? 5))}
                className="sm:hidden w-8 h-8 rounded-lg flex items-center justify-center transition-all"
                style={{
                  color: (isDashboardPage && (redesignAttempts ?? 0) >= (MAX_REDESIGNS ?? 5)) ? 'var(--text-secondary)' : 'var(--text-header)',
                  opacity: (isDashboardPage && (redesignAttempts ?? 0) >= (MAX_REDESIGNS ?? 5)) ? 0.5 : 1,
                }}
                title={isDashboardPage ? `Redesign (${redesignAttempts ?? 0}/${MAX_REDESIGNS ?? 5})` : 'Refresh'}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
              </button>

              <div className="w-px h-4 mx-1" style={{ backgroundColor: 'var(--border)' }} />
            </>
          )}

          <button
            onClick={() => setShowUploadModal(true)}
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all"
            style={{
              backgroundColor: 'var(--accent-primary-light)',
              color: 'var(--accent-primary)',
              border: '1px solid var(--border)',
            }}
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload</span>
          </button>

          <button
            onClick={() => setShowUploadModal(true)}
            className="sm:hidden w-8 h-8 rounded-lg flex items-center justify-center transition-all"
            style={{ color: 'var(--text-secondary)' }}
          >
            <Upload className="w-4 h-4" />
          </button>

          <div className="w-px h-4 mx-1" style={{ backgroundColor: 'var(--border)' }} />

          <ThemeSwitcher />
        </div>
      </header>

      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
      />
    </>
  );
};

export default Header;
