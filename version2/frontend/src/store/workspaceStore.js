import { create } from 'zustand';
import { workspaceAPI } from '../services/api';

/**
 * Workspace Store
 *
 * Tracks the current workspace context (id, role), member list,
 * and provides actions to manage members & roles.
 */
const useWorkspaceStore = create((set, get) => ({
  // ── Current workspace context ──
  workspaceId: null,
  workspaceRole: null,   // "owner" | "admin" | "member" | "viewer"
  workspaceName: null,
  workspaceLoaded: false,

  // ── Members ──
  members: [],
  membersLoading: false,

  // ── Actions ──

  /**
   * Set the workspace context (called after login / workspace switch).
   */
  setWorkspaceContext: (workspaceId, role, name = null) =>
    set({ workspaceId, workspaceRole: role, workspaceName: name, workspaceLoaded: true }),

  /**
   * Fetch the user's first workspace from the API and set it as the current context.
   * Called by authStore after login, rehydration, and token verification.
   */
  fetchAndSetContext: async () => {
    try {
      const res = await workspaceAPI.listWorkspaces();
      const workspaces = res.data?.workspaces || [];
      if (workspaces.length > 0) {
        const ws = workspaces[0];
        set({ workspaceId: ws.id, workspaceRole: ws.role, workspaceName: ws.name, workspaceLoaded: true });
      }
    } catch (err) {
      console.warn('Failed to init workspace context:', err);
    }
  },

  /**
   * Fetch members for the current workspace.
   */
  fetchMembers: async () => {
    const { workspaceId } = get();
    if (!workspaceId) return;

    set({ membersLoading: true });
    try {
      const res = await workspaceAPI.listMembers(workspaceId);
      const members = res.data?.members || [];
      // Sort: owners first, then admins, then members, then viewers
      const ROLE_ORDER = { owner: 0, admin: 1, member: 2, viewer: 3 };
      members.sort((a, b) => (ROLE_ORDER[a.role] ?? 99) - (ROLE_ORDER[b.role] ?? 99));
      set({ members, membersLoading: false });
    } catch (err) {
      console.error('Failed to fetch workspace members:', err);
      set({ membersLoading: false });
    }
  },

  /**
   * Invite a new member to the workspace.
   */
  addMember: async (userId, role = 'member') => {
    try {
      await workspaceAPI.addMember(get().workspaceId, { user_id: userId, role });
      // Refetch members to get the updated list
      await get().fetchMembers();
      return { success: true };
    } catch (err) {
      return {
        success: false,
        error: err.response?.data?.detail || 'Failed to add member',
      };
    }
  },

  /**
   * Update a member's role.
   */
  updateMemberRole: async (userId, newRole) => {
    try {
      await workspaceAPI.updateMemberRole(get().workspaceId, userId, newRole);
      // Update locally without refetching
      set((state) => ({
        members: state.members.map((m) =>
          m.user_id === userId ? { ...m, role: newRole } : m
        ),
      }));
      return { success: true };
    } catch (err) {
      return {
        success: false,
        error: err.response?.data?.detail || 'Failed to update role',
      };
    }
  },

  /**
   * Remove a member from the workspace.
   */
  removeMember: async (userId) => {
    try {
      await workspaceAPI.removeMember(get().workspaceId, userId);
      set((state) => ({
        members: state.members.filter((m) => m.user_id !== userId),
      }));
      return { success: true };
    } catch (err) {
      return {
        success: false,
        error: err.response?.data?.detail || 'Failed to remove member',
      };
    }
  },

  /**
   * Reset store (used on logout).
   */
  reset: () =>
    set({
      workspaceId: null,
      workspaceRole: null,
      workspaceName: null,
      workspaceLoaded: false,
      members: [],
      membersLoading: false,
    }),
}));

export default useWorkspaceStore;
