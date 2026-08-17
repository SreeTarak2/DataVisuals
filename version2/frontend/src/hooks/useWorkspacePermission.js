import { useMemo } from 'react';
import useWorkspaceStore from '../store/workspaceStore';

/**
 * Role hierarchy: owner > admin > member > viewer
 * Each role inherits permissions from roles below it.
 *
 * ⚠️ KEEP IN SYNC with backend/core/permissions.py
 * The backend is the SOURCE OF TRUTH for permission enforcement.
 * This frontend mirror is for UX only (hiding/showing UI elements).
 * Backend permissions must be updated first, then mirror here.
 */
const ROLE_HIERARCHY = ['owner', 'admin', 'member', 'viewer'];

const PERMISSIONS = {
  // ── Workspace management ──
  'workspace:delete':         ['owner'],
  'workspace:update':         ['owner', 'admin'],
  'workspace:transfer_owner': ['owner'],

  // ── Membership ──
  'workspace:invite':         ['owner', 'admin'],
  'workspace:remove_member':  ['owner', 'admin'],
  'workspace:change_role':    ['owner', 'admin'],

  // ── Datasets ──
  'dataset:upload':           ['owner', 'admin', 'member'],
  'dataset:delete':           ['owner', 'admin'],

  // ── Charts ──
  'chart:create':             ['owner', 'admin', 'member'],
  'chart:delete_any':         ['owner', 'admin'],

  // ── Dashboards ──
  'dashboard:create':         ['owner', 'admin', 'member'],
  'dashboard:delete':         ['owner', 'admin'],

  // ── Settings ──
  'settings:edit':            ['owner', 'admin'],

  // ── Billing ──
  'billing:view':             ['owner', 'admin'],
  'billing:edit':             ['owner'],

  // ── View ──
  'data:view':                ['owner', 'admin', 'member', 'viewer'],
  'data:export':              ['owner', 'admin', 'member'],
};

function roleIndex(role) {
  const idx = ROLE_HIERARCHY.indexOf(role);
  return idx === -1 ? ROLE_HIERARCHY.length : idx;
}

function checkPermission(userRole, action) {
  const allowed = PERMISSIONS[action];
  if (!allowed) return false;
  const userIdx = roleIndex(userRole);
  return allowed.some((allowedRole) => userIdx <= roleIndex(allowedRole));
}

/**
 * Hook providing granular permission checks based on workspace role.
 *
 * Usage:
 *   const { canInvite, canDeleteWorkspace, isOwner } = useWorkspacePermission();
 *
 *   {canInvite && <InviteButton />}
 */
export function useWorkspacePermission() {
  const role = useWorkspaceStore((s) => s.workspaceRole);
  const workspaceId = useWorkspaceStore((s) => s.workspaceId);

  return useMemo(() => {
    const all = {};
    for (const action of Object.keys(PERMISSIONS)) {
      all[action] = checkPermission(role, action);
    }

    return {
      // ── Derived convenience booleans ──
      role,
      workspaceId,
      isOwner: role === 'owner',
      isAdmin: role === 'admin' || role === 'owner',
      isMember: role === 'member' || role === 'admin' || role === 'owner',
      isViewer: role === 'viewer',

      // ── Granular action checks ──
      canDeleteWorkspace:      all['workspace:delete'],
      canUpdateWorkspace:      all['workspace:update'],
      canInvite:               all['workspace:invite'],
      canRemoveMember:         all['workspace:remove_member'],
      canChangeRole:           all['workspace:change_role'],
      canUploadDataset:        all['dataset:upload'],
      canDeleteDataset:        all['dataset:delete'],
      canCreateChart:          all['chart:create'],
      canDeleteAnyChart:       all['chart:delete_any'],
      canCreateDashboard:      all['dashboard:create'],
      canDeleteDashboard:      all['dashboard:delete'],
      canEditSettings:         all['settings:edit'],
      canViewBilling:          all['billing:view'],
      canEditBilling:          all['billing:edit'],
      canViewData:             all['data:view'],
      canExportData:           all['data:export'],

      // ── Raw check function (for dynamic use) ──
      hasPermission: (action) => checkPermission(role, action),
    };
  }, [role, workspaceId]);
}

/**
 * Check if the current user can manage another user with a given target role.
 * You can only manage users with roles lower than yours.
 */
export function canManageRole(currentRole, targetRole) {
  return roleIndex(currentRole) < roleIndex(targetRole);
}
