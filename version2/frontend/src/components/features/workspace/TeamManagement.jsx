import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users, UserPlus, Shield, ShieldCheck, ShieldAlert,
  Crown, Trash2, Mail, Loader2,
  UserCog,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '../../../lib/utils';
import { workspaceAPI } from '../../../services/api';
import useWorkspaceStore from '../../../store/workspaceStore';
import { useAuth } from '../../../store/authStore';
import { useWorkspacePermission, canManageRole } from '../../../hooks/useWorkspacePermission';

/* ─── Constants ─── */
const ROLE_CONFIG = {
  owner: {
    label: 'Owner',
    icon: Crown,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    description: 'Full control over workspace, billing, and members.',
  },
  admin: {
    label: 'Admin',
    icon: ShieldCheck,
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    description: 'Can manage members, datasets, and workspace settings.',
  },
  member: {
    label: 'Member',
    icon: Shield,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    description: 'Can upload data, create charts, and use AI analysis.',
  },
  viewer: {
    label: 'Viewer',
    icon: ShieldAlert,
    color: 'text-slate-500',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/20',
    description: 'Can view data and dashboards but not make changes.',
  },
};

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin', description: 'Manage members, datasets, and settings' },
  { value: 'member', label: 'Member', description: 'Upload data, create charts, use AI' },
  { value: 'viewer', label: 'Viewer', description: 'View-only access to data and dashboards' },
];

/* ─── Styling ─── */
const inputCls =
  'h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/50 px-3.5 text-[14px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none transition-all focus:border-[var(--accent-primary)] focus:bg-[var(--bg-elevated)] focus:ring-1 focus:ring-[var(--accent-primary)]';

const btnCls =
  'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-[13px] font-medium transition-all h-9';

/* ─── Member Row ─── */
function MemberRow({ member, currentUserId, canManage, onRoleChange, onRemove }) {
  const RoleIcon = ROLE_CONFIG[member.role]?.icon || Shield;
  const roleCfg = ROLE_CONFIG[member.role] || ROLE_CONFIG.member;
  const [changing, setChanging] = useState(false);
  const [removing, setRemoving] = useState(false);
  const isSelf = member.user_id === currentUserId;

  const handleRoleChange = async (newRole) => {
    if (newRole === member.role) return;
    setChanging(true);
    const result = await onRoleChange(member.user_id, newRole);
    if (!result.success) {
      toast.error(result.error || 'Failed to change role');
    }
    setChanging(false);
  };

  const handleRemove = async () => {
    if (!window.confirm(`Remove ${member.username || member.email || 'this user'} from the workspace?`)) return;
    setRemoving(true);
    const result = await onRemove(member.user_id);
    if (!result.success) {
      toast.error(result.error || 'Failed to remove member');
    }
    setRemoving(false);
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -20, height: 0 }}
      className="flex items-center gap-4 p-4 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/30 hover:bg-[var(--bg-elevated)]/50 transition-colors group"
    >
      {/* Avatar */}
      <div className="shrink-0">
        {member.avatar ? (
          <img src={member.avatar} alt="" className="w-9 h-9 rounded-full object-cover" />
        ) : (
          <div className="w-9 h-9 rounded-full bg-[var(--bg-secondary)] border border-[var(--border)] flex items-center justify-center">
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              {(member.username || member.email || '?')[0].toUpperCase()}
            </span>
          </div>
        )}
      </div>

      {/* Name & Email */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[14px] font-medium text-[var(--text-primary)] truncate">
            {member.username || 'Unknown'}
          </span>
          {isSelf && (
            <span className="text-[10px] font-medium text-[var(--text-muted)] bg-[var(--bg-secondary)] px-1.5 py-0.5 rounded">
              You
            </span>
          )}
        </div>
        <p className="text-[12px] text-[var(--text-secondary)] truncate">
          {member.email || ''}
        </p>
      </div>

      {/* Role Badge */}
      <div className="shrink-0">
        {member.role === 'owner' ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/20">
            <Crown className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-[12px] font-medium text-amber-500">Owner</span>
          </div>
        ) : canManage ? (
          <div className="relative">
            <select
              value={member.role}
              onChange={(e) => handleRoleChange(e.target.value)}
              disabled={changing}
              className="appearance-none h-8 rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] px-2.5 pr-7 text-[12px] font-medium text-[var(--text-primary)] outline-none cursor-pointer hover:border-[var(--accent-primary)] transition-colors disabled:opacity-50"
            >
              {ROLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            {changing ? (
              <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 animate-spin text-[var(--text-muted)]" />
            ) : (
              <UserCog className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[var(--text-muted)] pointer-events-none" />
            )}
          </div>
        ) : (
          <div className={cn(
            'flex items-center gap-1.5 px-2.5 py-1 rounded-md border',
            roleCfg.bg, roleCfg.border
          )}>
            <RoleIcon className={cn('w-3.5 h-3.5', roleCfg.color)} />
            <span className={cn('text-[12px] font-medium', roleCfg.color)}>
              {roleCfg.label}
            </span>
          </div>
        )}
      </div>

      {/* Remove Button */}
      {canManage && member.role !== 'owner' && (
        <button
          onClick={handleRemove}
          disabled={removing}
          className="shrink-0 p-2 rounded-lg opacity-0 group-hover:opacity-100 transition-all hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-400 disabled:opacity-30"
          title="Remove from workspace"
        >
          {removing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4" />
          )}
        </button>
      )}
    </motion.div>
  );
}

/* ─── Invite Form ─── */
function InviteForm({ onInvite }) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('member');
  const [inviting, setInviting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) {
      toast.error('Please enter an email address');
      return;
    }

    setInviting(true);
    const result = await onInvite(email.trim(), role);
    if (result.success) {
      toast.success(`Invitation sent to ${email}`);
      setEmail('');
    } else {
      toast.error(result.error || 'Failed to invite user');
    }
    setInviting(false);
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-3">
      <div className="flex-1 space-y-1.5">
        <label className="block text-[13px] font-medium text-[var(--text-primary)]">
          Email address
        </label>
        <div className="relative">
          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="colleague@company.com"
            className={cn(inputCls, 'pl-10')}
            disabled={inviting}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <label className="block text-[13px] font-medium text-[var(--text-primary)]">
          Role
        </label>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className={cn(inputCls, 'min-w-[130px]')}
          disabled={inviting}
        >
          {ROLE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>
      <button
        type="submit"
        disabled={inviting}
        className={cn(btnCls, 'bg-[var(--accent-primary)] text-white hover:opacity-90 disabled:opacity-50')}
      >
        {inviting ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <UserPlus className="w-4 h-4" />
        )}
        {inviting ? 'Inviting...' : 'Invite'}
      </button>
    </form>
  );
}

/* ─── Role Info Cards ─── */
function RoleInfoCards() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {Object.entries(ROLE_CONFIG).map(([key, cfg]) => {
        const Icon = cfg.icon;
        return (
          <div
            key={key}
            className={cn(
              'rounded-lg border p-3.5 transition-colors',
              cfg.bg, cfg.border
            )}
          >
            <div className="flex items-center gap-2 mb-1.5">
              <Icon className={cn('w-4 h-4', cfg.color)} />
              <span className={cn('text-[13px] font-semibold', cfg.color)}>
                {cfg.label}
              </span>
            </div>
            <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
              {cfg.description}
            </p>
          </div>
        );
      })}
    </div>
  );
}

/* ─── Main Component ─── */
export default function TeamManagement() {
  const {
    members, membersLoading,
    fetchMembers, updateMemberRole, removeMember,
    workspaceId, workspaceRole,
  } = useWorkspaceStore();
  const { user } = useAuth();
  const { canInvite, canChangeRole } = useWorkspacePermission();

  const currentUserId = user?.id;

  useEffect(() => {
    if (workspaceId) {
      fetchMembers();
    }
  }, [workspaceId, fetchMembers]);

  const handleInvite = useCallback(async (email, role) => {
    // The backend add_member endpoint now supports email-based lookup.
    // It looks up the user by email and adds them to the workspace.
    // The user must already be registered.
    try {
      await workspaceAPI.addMember(workspaceId, { user_id: email, role });
      await fetchMembers();
      return { success: true };
    } catch (err) {
      return {
        success: false,
        error: err.response?.data?.detail || 'Failed to add member. Make sure this user has already registered.',
      };
    }
  }, [workspaceId, fetchMembers]);

  const handleRoleChange = useCallback(async (userId, newRole) => {
    return await updateMemberRole(userId, newRole);
  }, [updateMemberRole]);

  const handleRemove = useCallback(async (userId) => {
    return await removeMember(userId);
  }, [removeMember]);

  // ── Ensure framer-motion is recognized as used ──
  // The linter doesn't detect `motion.div` as a usage of `motion`
  // because it's a member expression. This reference makes it explicit.
  void motion;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">Team Members</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">
          Manage who has access to this workspace and what they can do.
        </p>
      </div>

      {/* Role Reference */}
      <div>
        <h4 className="text-[14px] font-medium text-[var(--text-primary)] mb-3">Role Overview</h4>
        <RoleInfoCards />
      </div>

      {/* Invite Form */}
      {canInvite && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/30 p-5">
          <h4 className="text-[14px] font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
            <UserPlus className="w-4 h-4" />
            Invite Team Member
          </h4>
          <InviteForm onInvite={handleInvite} />
        </div>
      )}

      {/* Members List */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-[14px] font-medium text-[var(--text-primary)]">
            Members ({members.length})
          </h4>
          {membersLoading && (
            <Loader2 className="w-4 h-4 animate-spin text-[var(--text-muted)]" />
          )}
        </div>

        {membersLoading && members.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="animate-pulse flex items-center gap-4 p-4 rounded-lg border border-[var(--border)]"
              >
                <div className="w-9 h-9 rounded-full bg-[var(--bg-secondary)]" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 bg-[var(--bg-secondary)] rounded w-1/3" />
                  <div className="h-2.5 bg-[var(--bg-secondary)] rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : members.length === 0 ? (
          <div className="text-center py-12 border border-dashed border-[var(--border)] rounded-lg bg-[var(--bg-secondary)]/30">
            <Users className="w-10 h-10 mx-auto mb-3 text-[var(--text-muted)]" />
            <p className="text-[14px] font-medium text-[var(--text-primary)]">No members found</p>
            <p className="text-[13px] text-[var(--text-secondary)] mt-1">
              Invite team members to collaborate on this workspace.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {members.map((member) => (
                <MemberRow
                  key={member.user_id}
                  member={member}
                  currentUserId={currentUserId}
                  canManage={
                    canChangeRole &&
                    member.role !== 'owner' &&
                    canManageRole(workspaceRole, member.role)
                  }
                  onRoleChange={handleRoleChange}
                  onRemove={handleRemove}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}


