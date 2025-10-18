import React from 'react';
import { User, Bell, Lock, Database } from 'lucide-react';
import GlassCard from '../components/common/GlassCard';
import { useAuth } from '../contexts/AuthContext';

const Settings = () => {
  const { user } = useAuth();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-800 dark:text-white">Settings</h1>
        <p className="text-slate-600 dark:text-slate-300 mt-2">
          Manage your account and preferences
        </p>
      </div>

      {/* Profile Settings */}
      <GlassCard className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <User className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold text-white">Profile Information</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Full Name</label>
            <input
              type="text"
              defaultValue={user?.full_name}
              className="w-full px-4 py-3 rounded-lg bg-white/10 backdrop-blur-md border border-white/20 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
            <input
              type="email"
              defaultValue={user?.email}
              className="w-full px-4 py-3 rounded-lg bg-white/10 backdrop-blur-md border border-white/20 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
              disabled
            />
          </div>
        </div>
      </GlassCard>

      {/* Notification Settings */}
      <GlassCard className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <Bell className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold text-white">Notifications</h2>
        </div>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-white font-medium">Email Notifications</p>
              <p className="text-sm text-slate-400">Receive email about your account activity</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-white/20 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-purple-500/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-500"></div>
            </label>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-white font-medium">AI Insights</p>
              <p className="text-sm text-slate-400">Get notified about new insights</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-white/20 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-purple-500/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-500"></div>
            </label>
          </div>
        </div>
      </GlassCard>

      {/* Security Settings */}
      <GlassCard className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <Lock className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold text-white">Security</h2>
        </div>
        <button className="px-6 py-3 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold hover:from-purple-600 hover:to-pink-600 transition-all">
          Change Password
        </button>
      </GlassCard>

      {/* Data Settings */}
      <GlassCard className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <Database className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold text-white">Data Management</h2>
        </div>
        <div className="space-y-3">
          <button className="w-full px-6 py-3 rounded-lg bg-white/10 hover:bg-white/20 text-white font-medium transition-all text-left">
            Export All Data
          </button>
          <button className="w-full px-6 py-3 rounded-lg bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-300 font-medium transition-all text-left">
            Delete Account
          </button>
        </div>
      </GlassCard>
    </div>
  );
};

export default Settings;
