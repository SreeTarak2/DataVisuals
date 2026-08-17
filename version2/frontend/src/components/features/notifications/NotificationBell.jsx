import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Bell, CheckCheck, Loader2, Inbox, ExternalLink, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import useNotificationStore from '@/store/notificationStore';
import useDatasetStore from '@/store/datasetStore';

const CTA_OPEN_DASHBOARD = 'open_dashboard';
const CTA_RETRY_PROCESSING = 'retry_processing';

const TYPE_ICON = {
  dataset_ready: '✅',
  dataset_failed: '⚠️',
  dataset_resumed: '🔄',
  dataset_reimported: '📥',
};

const TYPE_COLOR = {
  dataset_ready: 'var(--accent-success, #10b981)',
  dataset_failed: 'var(--accent-error, #ef4444)',
  dataset_resumed: 'var(--accent-warning, #f59e0b)',
  dataset_reimported: 'var(--accent-primary, #6366f1)',
};

const formatTime = (iso) => {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const diffMs = Date.now() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? 'yesterday' : `${days}d ago`;
};

/**
 * NotificationBell — in-app job notification inbox.
 *
 * - Bell icon with unread badge in the header
 * - Dropdown listing notifications (newest first)
 * - "Mark all read" action
 * - Clicking a notification navigates to the dataset dashboard
 *   (or surfaces a retry prompt for failed processing)
 *
 * Real-time updates arrive via the WebSocket push (dataset ready /
 * failed / resumed). A manual refresh button + refresh-on-open provide
 * the fallback for when the socket is not connected.
 */
const NotificationBell = ({ className }) => {
  const navigate = useNavigate();
  const { notifications, unreadCount, loading, fetchAll, refreshUnread, markRead, markAllRead } = useNotificationStore();
  const setSelectedDataset = useDatasetStore((s) => s.setSelectedDataset);

  const [isOpen, setIsOpen] = useState(false);
  const [lastUnreadSeen, setLastUnreadSeen] = useState(unreadCount);
  const bellRef = useRef(null);

  // Fetch on mount (covers "came back after 5h" and cross-device opens)
  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep badge visible until the user opens the dropdown (or marks read)
  useEffect(() => {
    if (isOpen) setLastUnreadSeen(unreadCount);
  }, [isOpen, unreadCount]);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (!bellRef.current?.contains(e.target)) setIsOpen(false);
    };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, [isOpen]);

  // Refresh unread count when the tab regains focus (cheap staleness guard)
  useEffect(() => {
    const onFocus = () => refreshUnread();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [refreshUnread]);

  const handleOpen = useCallback(() => {
    setIsOpen((open) => !open);
    if (!isOpen) {
      // Pull fresh data each time the bell opens
      fetchAll();
      setLastUnreadSeen(unreadCount);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, fetchAll, unreadCount]);

  const handleClick = useCallback(async (n) => {
    if (!n.read) markRead(n.id);
    setIsOpen(false);

    const action = n.cta?.action;
    const datasetId = n.dataset_id;

    if (action === CTA_OPEN_DASHBOARD && datasetId) {
      // Select the dataset so the dashboard shows it
      const store = useDatasetStore.getState();
      const dataset = store.datasets.find((d) => (d.id || d._id) === datasetId);
      if (dataset) {
        setSelectedDataset(dataset);
      } else {
        // Not in the list yet — fetch, then select by id
        try {
          const list = await store.fetchDatasets(true);
          const match = list.find((d) => (d.id || d._id) === datasetId);
          if (match) setSelectedDataset(match);
        } catch (err) {
          console.warn('Failed to locate dataset for notification:', err);
        }
      }
      navigate('/app/dashboard');
      return;
    }

    if (action === CTA_RETRY_PROCESSING && datasetId) {
      // Surface retry on the datasets/assets page
      navigate(`/app/workspace`);
      return;
    }

    if (datasetId) {
      const store = useDatasetStore.getState();
      const dataset = store.datasets.find((d) => (d.id || d._id) === datasetId);
      if (dataset) {
        setSelectedDataset(dataset);
        navigate('/app/dashboard');
      }
    }
  }, [markRead, navigate, setSelectedDataset]);

  const badgeCount = isOpen ? 0 : unreadCount;
  const hasUnseen = unreadCount > 0 && lastUnreadSeen < unreadCount;

  return (
    <div className={cn("relative", className)} ref={bellRef}>
      <button
        onClick={handleOpen}
        className="relative w-8 h-8 rounded-lg flex items-center justify-center transition-all hover:scale-[1.04] active:scale-95"
        style={{ color: isOpen ? 'var(--text-header)' : 'var(--text-secondary)' }}
        title="Notifications"
        aria-label={`Notifications${unreadCount ? ` (${unreadCount} unread)` : ''}`}
      >
        <Bell className="w-4 h-4" />
        {badgeCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full flex items-center justify-center text-[10px] font-bold tabular-nums"
            style={{
              backgroundColor: 'var(--accent-error, #ef4444)',
              color: '#fff',
              border: '2px solid var(--bg-primary, #0a0a0c)',
            }}
          >
            {badgeCount > 99 ? '99+' : badgeCount}
          </span>
        )}
        {hasUnseen && badgeCount === 0 && (
          <span
            className="absolute top-1 right-1 w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: 'var(--accent-error, #ef4444)' }}
          />
        )}
      </button>

      {isOpen && (
        <div
          className="absolute right-0 top-full mt-1.5 z-50 w-[360px] max-w-[calc(100vw-24px)] overflow-hidden rounded-lg"
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
            <span className="text-[13px] font-semibold" style={{ color: 'var(--text-header)' }}>
              Notifications
              {unreadCount > 0 && (
                <span className="ml-2 text-[11px] font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {unreadCount} unread
                </span>
              )}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => fetchAll()}
                className="p-1.5 rounded-md transition-colors hover:bg-[var(--bg-active)]/50"
                style={{ color: 'var(--text-secondary)' }}
                title="Refresh"
                disabled={loading}
              >
                <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
              </button>
              <button
                onClick={markAllRead}
                disabled={unreadCount === 0}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-colors disabled:opacity-40"
                style={{ color: 'var(--accent-primary)', background: 'var(--accent-primary-light, rgba(99,102,241,0.1))' }}
              >
                <CheckCheck className="w-3 h-3" />
                Mark all read
              </button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-[320px] overflow-y-auto">
            {loading && notifications.length === 0 ? (
              <div className="flex items-center justify-center gap-2 py-10" style={{ color: 'var(--text-secondary)' }}>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-[12px]">Loading…</span>
              </div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-10 px-4 text-center">
                <Inbox className="w-6 h-6 opacity-40" style={{ color: 'var(--text-muted)' }} />
                <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                  No notifications yet
                </span>
                <span className="text-[11px] max-w-[240px]" style={{ color: 'var(--text-muted)' }}>
                  You'll be notified here when a dataset finishes processing.
                </span>
              </div>
            ) : (
              notifications.map((n) => {
                const icon = TYPE_ICON[n.type] || '•';
                const color = TYPE_COLOR[n.type] || 'var(--text-secondary)';
                return (
                  <button
                    key={n.id}
                    onClick={() => handleClick(n)}
                    className={cn(
                      "w-full flex items-start gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-[var(--bg-active)]/40 border-b last:border-b-0",
                      !n.read && "bg-[var(--accent-primary-light, rgba(99,102,241,0.06))]"
                    )}
                    style={{ borderColor: 'var(--border)' }}
                  >
                    <span className="text-base leading-none mt-0.5 shrink-0" style={{ filter: 'saturate(0.9)' }}>
                      {icon}
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="block text-[13px] font-medium leading-snug" style={{ color: 'var(--text-header)' }}>
                        {n.title}
                      </span>
                      {n.body && (
                        <span className="block mt-0.5 text-[12px] leading-snug" style={{ color: 'var(--text-secondary)' }}>
                          {n.body}
                        </span>
                      )}
                      <span className="flex items-center gap-1 mt-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
                        <span style={{ color }}>{formatTime(n.created_at)}</span>
                        {n.cta?.text && (
                          <>
                            <span>·</span>
                            <span className="inline-flex items-center gap-0.5" style={{ color: 'var(--accent-primary)' }}>
                              {n.cta.text}
                              <ExternalLink className="w-2.5 h-2.5" />
                            </span>
                          </>
                        )}
                      </span>
                    </span>
                    {!n.read && (
                      <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: 'var(--accent-primary, #6366f1)' }} />
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
