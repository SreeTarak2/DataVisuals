import { create } from 'zustand';
import { notificationAPI } from '../services/api';

/**
 * Notification store — in-app job notification inbox (bell).
 *
 * - fetchAll(): pull the inbox + unread count from the backend
 * - markRead / markAllRead: update read state locally + on the server
 * - handlePush(): called by the WebSocket layer when a `notification`
 *   event arrives in real time (dataset ready / failed / resumed)
 */
const useNotificationStore = create((set, get) => ({
  notifications: [],
  unreadCount: 0,
  loading: false,
  lastFetchedAt: 0,

  fetchAll: async () => {
    set({ loading: true });
    try {
      const [listRes, unreadRes] = await Promise.all([
        notificationAPI.getNotifications(50),
        notificationAPI.getUnreadCount(),
      ]);
      const notifications = listRes.data?.notifications || [];
      const unreadCount = unreadRes.data?.unread_count ?? 0;
      set({
        notifications,
        unreadCount,
        loading: false,
        lastFetchedAt: Date.now(),
      });
      return { notifications, unreadCount };
    } catch (err) {
      console.warn('Failed to fetch notifications:', err?.message || err);
      set({ loading: false });
      return { notifications: get().notifications, unreadCount: get().unreadCount };
    }
  },

  refreshUnread: async () => {
    try {
      const res = await notificationAPI.getUnreadCount();
      set({ unreadCount: res.data?.unread_count ?? 0 });
      return res.data?.unread_count ?? 0;
    } catch (err) {
      console.warn('Failed to refresh unread count:', err?.message || err);
      return get().unreadCount;
    }
  },

  markRead: async (id) => {
    // Optimistic update
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
      unreadCount: Math.max(0, state.unreadCount - (state.notifications.find((n) => n.id === id && !n.read) ? 1 : 0)),
    }));
    try {
      await notificationAPI.markRead(id);
    } catch (err) {
      console.warn('Failed to mark notification read:', err?.message || err);
    }
  },

  markAllRead: async () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }));
    try {
      await notificationAPI.markAllRead();
    } catch (err) {
      console.warn('Failed to mark all read:', err?.message || err);
    }
  },

  /**
   * Handle a real-time push from the WebSocket.
   * Dedupes by id so a repeated push doesn't double-count.
   */
  handlePush: (notification) => {
    if (!notification || !notification.id) return;
    const state = get();
    if (state.notifications.some((n) => n.id === notification.id)) return;
    set({
      notifications: [notification, ...state.notifications].slice(0, 100),
      unreadCount: state.unreadCount + (notification.read ? 0 : 1),
    });
  },
}));

export default useNotificationStore;
