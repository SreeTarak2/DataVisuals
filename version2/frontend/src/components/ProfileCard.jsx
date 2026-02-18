import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Database, MessageSquare, BarChart3, Calendar, Clock,
  Shield, KeyRound, LogOut, Settings, ChevronRight, Sparkles
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../store/authStore';
import useDatasetStore from '../store/datasetStore';
import useChatStore from '../store/chatStore';

const ProfileCard = () => {
  const { user, logout } = useAuth();
  const datasets = useDatasetStore((s) => s.datasets);
  const conversations = useChatStore((s) => s.conversations);
  const navigate = useNavigate();

  // Compute real usage stats
  const stats = useMemo(() => {
    const datasetCount = datasets?.length || 0;
    const conversationCount = Object.keys(conversations || {}).length;
    const totalMessages = Object.values(conversations || {}).reduce(
      (sum, conv) => sum + (conv?.messages?.length || 0), 0
    );
    return { datasetCount, conversationCount, totalMessages };
  }, [datasets, conversations]);

  // Format dates from user object
  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
    : 'N/A';

  const lastLogin = user?.last_login
    ? new Date(user.last_login).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Just now';

  // Avatar initials
  const initials = (user?.username || user?.email || 'U').slice(0, 2).toUpperCase();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const statItems = [
    { label: 'Datasets', value: stats.datasetCount, icon: Database, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { label: 'Conversations', value: stats.conversationCount, icon: MessageSquare, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    { label: 'AI Queries', value: stats.totalMessages, icon: Sparkles, color: 'text-purple-400', bg: 'bg-purple-500/10' },
  ];

  const quickActions = [
    { label: 'Settings', icon: Settings, onClick: () => navigate('/app/settings'), desc: 'API keys, preferences' },
    { label: 'Change Password', icon: KeyRound, onClick: () => navigate('/app/settings'), desc: 'Update credentials' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full max-w-lg mx-auto"
    >
      <div className="relative overflow-hidden rounded-2xl bg-[#1A191C] border border-white/[0.06] shadow-2xl">

        {/* Header Banner */}
        <div className="h-24 bg-gradient-to-br from-[#1A191C] via-[#2a2830] to-[#1A191C] relative">
          <div className="absolute inset-0 opacity-30"
            style={{ backgroundImage: 'radial-gradient(rgba(202, 210, 253, 0.08) 1px, transparent 1px)', backgroundSize: '24px 24px' }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#1A191C] to-transparent" />
        </div>

        <div className="px-6 pb-6 relative">
          {/* Avatar + Identity */}
          <div className="relative -mt-12 mb-5 flex items-end justify-between">
            <div className="relative">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#CAD2FD] to-[#C7BC92] p-[2px] shadow-lg shadow-[#CAD2FD]/10">
                <div className="w-full h-full rounded-[14px] bg-[#020203] flex items-center justify-center">
                  <span className="text-2xl font-bold text-[#CAD2FD] tracking-tight">{initials}</span>
                </div>
              </div>
              {/* Online dot */}
              <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 border-[3px] border-[#1A191C] shadow-[0_0_8px_#22c55e]" />
            </div>

            {/* Account badge */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#CAD2FD]/10 border border-[#CAD2FD]/20">
              <Shield size={12} className="text-[#CAD2FD]" />
              <span className="text-[11px] font-medium text-[#CAD2FD]">
                {user?.is_verified ? 'Verified' : 'Free Tier'}
              </span>
            </div>
          </div>

          {/* User Info */}
          <div className="space-y-1 mb-5">
            <h2 className="text-xl font-bold text-white tracking-tight">
              {user?.username || user?.full_name || 'User'}
            </h2>
            <p className="text-sm text-[#6C6E79]">{user?.email}</p>
            <div className="flex items-center gap-4 mt-2 text-xs text-[#6C6E79]">
              <span className="flex items-center gap-1.5">
                <Calendar size={12} />
                Member since {memberSince}
              </span>
              <span className="flex items-center gap-1.5">
                <Clock size={12} />
                Last login {lastLogin}
              </span>
            </div>
          </div>

          {/* Usage Stats */}
          <div className="grid grid-cols-3 gap-2 mb-5">
            {statItems.map((stat) => (
              <motion.div
                key={stat.label}
                whileHover={{ scale: 1.02 }}
                className={`p-3 rounded-xl ${stat.bg} border border-white/[0.04] text-center transition-colors`}
              >
                <stat.icon className={`w-4 h-4 mx-auto mb-1.5 ${stat.color}`} />
                <div className="text-lg font-bold text-white tabular-nums">{stat.value}</div>
                <div className="text-[10px] text-[#6C6E79] uppercase tracking-wider font-medium">{stat.label}</div>
              </motion.div>
            ))}
          </div>

          {/* Quick Actions */}
          <div className="space-y-1 mb-4">
            {quickActions.map((action) => (
              <motion.button
                key={action.label}
                onClick={action.onClick}
                whileHover={{ x: 2 }}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/[0.04] transition-colors group text-left"
              >
                <div className="w-8 h-8 rounded-lg bg-[#39373D] flex items-center justify-center flex-shrink-0">
                  <action.icon size={14} className="text-[#CAD2FD]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white">{action.label}</div>
                  <div className="text-[11px] text-[#6C6E79]">{action.desc}</div>
                </div>
                <ChevronRight size={14} className="text-[#6C6E79] opacity-0 group-hover:opacity-100 transition-opacity" />
              </motion.button>
            ))}
          </div>

          {/* Logout */}
          <div className="pt-4 border-t border-white/[0.06]">
            <motion.button
              onClick={handleLogout}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-sm font-medium transition-all"
            >
              <LogOut size={14} />
              Sign Out
            </motion.button>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ProfileCard;
