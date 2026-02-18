import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, BarChart3, Layers3, Settings, LogOut, Sparkles
} from 'lucide-react';
import { useAuth } from '../../store/authStore';
import { cn } from '../../lib/utils';

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/app/dashboard' },
  { icon: Layers3, label: 'Datasets', path: '/app/datasets' },
  { icon: BarChart3, label: 'Charts', path: '/app/charts' },
  { icon: Settings, label: 'Settings', path: '/app/settings' },
];

const Sidebar = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="w-[60px] h-full flex flex-col items-center py-4 border-r border-white/[0.06] bg-[#0a0f1a]">
      {/* Logo */}
      <button
        onClick={() => navigate('/app/dashboard')}
        className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-cyan-500 flex items-center justify-center mb-8 hover:shadow-lg hover:shadow-primary/20 transition-all"
        title="DataSage"
      >
        <Sparkles className="w-5 h-5 text-white" />
      </button>

      {/* Navigation Icons */}
      <nav className="flex-1 flex flex-col items-center gap-1.5">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 group relative",
                isActive
                  ? "bg-primary/15 text-primary shadow-sm"
                  : "text-slate-500 hover:text-slate-200 hover:bg-white/[0.05]"
              )
            }
            title={item.label}
          >
            <item.icon className="w-5 h-5" />
            {/* Tooltip */}
            <span className="absolute left-full ml-3 px-2.5 py-1 rounded-md bg-slate-800 text-white text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity shadow-lg border border-white/10 z-50">
              {item.label}
            </span>
          </NavLink>
        ))}
      </nav>

      {/* Bottom: Logout */}
      <button
        onClick={logout}
        className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all duration-200 group relative"
        title="Logout"
      >
        <LogOut className="w-5 h-5" />
        <span className="absolute left-full ml-3 px-2.5 py-1 rounded-md bg-slate-800 text-white text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity shadow-lg border border-white/10 z-50">
          Logout
        </span>
      </button>
    </aside>
  );
};

export default Sidebar;
