import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  ChevronRight, Database, ChevronDown, FolderPlus, FolderKanban, Search,
  Moon, Sun, Check, LogOut, Settings, User,
  Command, Activity, Clock, Sparkles, RefreshCw, Loader2
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import CreateProjectModal from '../features/projects/CreateProjectModal';
import ProcessingIndicator from '../features/datasets/ProcessingIndicator';
import NotificationBell from '../features/notifications/NotificationBell';
import { useAuth } from '../../store/authStore';
import useProjectStore from '../../store/projectStore';
import { useTheme } from '../../store/themeStore';
import useDashboardActionStore from '../../store/dashboardActionStore';
import { useWorkspacePermission } from '../../hooks/useWorkspacePermission';
import { cn } from '../../lib/utils';

/* ─── Route → breadcrumb label map ─── */
const ROUTE_LABELS = {
  app: null,
  dashboard: 'Dashboard',
  workspace: 'Assets',
  datasets: 'Assets',
  chat: 'AI Chat',
  settings: 'Settings',
  analysis: 'Analysis',
};

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

/* ─── Compact project indicator ─── */
const ProjectIndicator = ({ project, onClick, isOpen }) => {
  if (!project) {
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
        <FolderKanban className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)' }} />
        <span className="hidden sm:inline font-semibold">No project</span>
        <ChevronDown className={cn("w-3.5 h-3.5 transition-transform duration-300", isOpen && "rotate-180")} />
      </button>
    );
  }

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
        style={{ backgroundColor: 'var(--accent-orange-light)' }}
      >
        <FolderKanban className="w-3.5 h-3.5" style={{ color: 'var(--accent-purple)' }} />
      </div>
      <span
        className="font-semibold truncate max-w-[160px] hidden sm:inline"
        style={{ color: 'var(--text-header)' }}
      >
        {project.name || 'Unnamed project'}
      </span>
      <span
        className="hidden md:flex items-center gap-2 text-[11px] font-bold tabular-nums"
        style={{ color: 'var(--text-secondary)' }}
      >
        <div className="flex items-center gap-1 opacity-80">
          <Database className="w-3.5 h-3.5" />{project.source_count || 0}
        </div>
        <span className="opacity-40">|</span>
        <div className="flex items-center gap-1 opacity-80">
          <Activity className="w-3.5 h-3.5" />{project.cell_count || 0}
        </div>
      </span>
      <ChevronDown
        className={cn("w-3.5 h-3.5 transition-transform duration-300", isOpen && "rotate-180")}
        style={{ color: 'var(--text-muted)' }}
      />
    </button>
  );
};

/* ─── Project dropdown panel ─── */
const ProjectDropdown = ({ projects, selectedId, onSelect, onNewProject }) => {
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
            Projects
          </div>
        </div>

        <div className="max-h-56 overflow-y-auto px-1.5 pb-1.5">
          {projects.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <FolderKanban className="w-5 h-5 mx-auto mb-2" style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
              <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>No projects yet</p>
            </div>
          ) : (
            projects.map((project) => {
              const isSelected = project.id === selectedId;
              return (
                <button
                  key={project.id}
                  onClick={() => onSelect(project)}
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
                    <FolderKanban
                      className="w-3 h-3"
                      style={{ color: isSelected ? 'var(--accent-primary)' : 'var(--text-muted)' }}
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium truncate">
                      {project.name || 'Unnamed project'}
                    </div>
                    <div
                      className="flex items-center gap-2 text-[11px] font-mono tabular-nums"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      <span>{project.source_count || 0} sources</span>
                      <span>·</span>
                      <span>{project.cell_count || 0} cells</span>
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
            onClick={onNewProject}
            className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-[13px] transition-all"
            style={{ color: 'var(--accent-warning)' }}
          >
            <FolderPlus className="w-3.5 h-3.5" />
            <span>New project</span>
          </button>
        </div>
      </div>
    </motion.div>
  );
};

/* ─── Theme Toggle — single icon click, no dropdown ─── */
const ThemeSwitcher = () => {
  const { resolvedTheme, toggleTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  return (
    <button
      onClick={toggleTheme}
      className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-150 hover:bg-elevated/60"
      style={{ color: 'var(--text-secondary)' }}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {isDark ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
    </button>
  );
};

/* ═══════════════════════════════════════════
   HEADER — Main Component
   ═══════════════════════════════════════════ */
const Header = () => {
  const { user } = useAuth();
  const { canUploadDataset } = useWorkspacePermission();
  const { projects, current, fetchProjects } = useProjectStore();
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const [showCreateProjectModal, setShowCreateProjectModal] = useState(false);
  const projectRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();

  // Get insights refresh state from store (synced from Insights page)
  const { onInsightsRefresh, insightsLoading } = useDashboardActionStore();

  // Check if on dashboard or insights page
  const isDashboardPage = location.pathname.includes('/dashboard');
  const isInsightsPage = location.pathname.includes('/insights');

  // Action button shows only on the insights page (refresh)
  const showActionButton = isInsightsPage;
  const actionButtonClick = onInsightsRefresh;
  const isLoading = insightsLoading;
  const buttonLabel = 'Refresh';
  const buttonLabelLoading = 'Refreshing...';

  useEffect(() => {
    if (projects.length === 0) fetchProjects();
  }, [projects.length, fetchProjects]);

  useEffect(() => {
    if (!showProjectDropdown) return;
    const handler = (e) => {
      if (!projectRef.current?.contains(e.target)) setShowProjectDropdown(false);
    };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, [showProjectDropdown]);

  // The project currently open in the URL (or null on other pages)
  const activeProject = useMemo(() => {
    const match = location.pathname.match(/\/app\/projects\/([^/]+)/);
    const projectId = match?.[1];
    if (!projectId) return null;
    return (
      projects.find((p) => p.id === projectId) ||
      (current?.id === projectId ? current : null) ||
      null
    );
  }, [location.pathname, projects, current]);

  const handleProjectSelect = (project) => {
    setShowProjectDropdown(false);
    navigate(`/app/projects/${project.id}`);
  };

  const isSettingsPage = location.pathname.includes('/settings');

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
          <Breadcrumbs />

          {!isSettingsPage && (
            <>
              <div
                className="w-0.5 h-3.5 rounded-full hidden sm:block shrink-0"
                style={{ backgroundColor: 'var(--border)' }}
              />

              <div className="relative hidden sm:block" ref={projectRef}>
                <ProjectIndicator
                  project={activeProject}
                  isOpen={showProjectDropdown}
                  onClick={() => setShowProjectDropdown(!showProjectDropdown)}
                />
                <AnimatePresence>
                  {showProjectDropdown && (
                    <ProjectDropdown
                      projects={projects}
                      selectedId={activeProject?.id}
                      onSelect={handleProjectSelect}
                      onNewProject={() => { setShowProjectDropdown(false); setShowCreateProjectModal(true); }}
                    />
                  )}
                </AnimatePresence>
              </div>
            </>
          )}
        </div>

        <div className="flex items-center gap-2 px-3">
          {/* Action button - show on insights page (refresh) */}
          {showActionButton && actionButtonClick && activeProject && (
            <>
              <button
                onClick={actionButtonClick}
                disabled={isLoading}
                className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all"
                style={{
                  backgroundColor: 'var(--bg-elevated)',
                  color: 'var(--text-header)',
                  border: '1px solid var(--border)',
                  cursor: 'pointer',
                }}
                title="Refresh insights"
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
                disabled={isLoading}
                className="sm:hidden w-8 h-8 rounded-lg flex items-center justify-center transition-all"
                style={{ color: 'var(--text-header)' }}
                title="Refresh"
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

          {canUploadDataset && (
            <button
              onClick={() => setShowCreateProjectModal(true)}
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all"
              style={{
                backgroundColor: "var(--accent-primary)",
                color: "white",
                border: "1px solid var(--accent-primary)",
              }}
            >
              <FolderPlus className="w-3.5 h-3.5" />
              <span>New project</span>
            </button>
          )}

          {canUploadDataset && (
            <button
              onClick={() => setShowCreateProjectModal(true)}
              className="sm:hidden w-8 h-8 rounded-lg flex items-center justify-center transition-all"
              style={{ color: 'var(--text-secondary)' }}
              title="New project"
            >
              <FolderPlus className="w-4 h-4" />
            </button>
          )}

          <div className="w-px h-4 mx-1" style={{ backgroundColor: 'var(--border)' }} />

          {isDashboardPage && <ProcessingIndicator />}
          <NotificationBell />
          <ThemeSwitcher />
        </div>
      </header>

      {showCreateProjectModal && (
        <CreateProjectModal
          onClose={() => setShowCreateProjectModal(false)}
          onCreated={(project) => navigate(`/app/projects/${project.id}`)}
        />
      )}
    </>
  );
};

export default Header;
