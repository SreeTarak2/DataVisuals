import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Bot, X, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from './Sidebar';
import Header from './Header';
import ChatPanel from '../features/chat/ChatPanel';
import { cn } from '../../lib/utils';

const DashboardLayout = () => {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-slate-50 via-blue-50 to-slate-50 dark:from-slate-900 dark:via-blue-900 dark:to-slate-900">
      {/* Icon Rail Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />

        <div className="flex-1 flex overflow-hidden relative">
          <main className="flex-1 overflow-y-auto p-0 relative">
            <Outlet />
          </main>
        </div>
      </div>

      {/* ── AI Chat Panel (fixed overlay) ── */}
      <ChatPanel
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />

      {/* ── Floating AI Chat FAB ── */}
      <AnimatePresence>
        {!chatOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.92 }}
            onClick={() => setChatOpen(true)}
            className={cn(
              "fixed bottom-6 right-6 z-[60]",
              "w-14 h-14 rounded-full",
              "bg-gradient-to-br from-indigo-500 to-purple-600",
              "text-white shadow-lg shadow-indigo-500/30",
              "flex items-center justify-center",
              "border border-indigo-400/30",
              "hover:shadow-xl hover:shadow-indigo-500/40",
              "transition-shadow duration-200",
              "cursor-pointer"
            )}
            title="Open AI Assistant"
          >
            <Sparkles className="w-6 h-6" />
            {/* Online pulse */}
            <span className="absolute top-0 right-0 w-3 h-3 bg-green-400 rounded-full border-2 border-[#0f172a] shadow-[0_0_6px_#22c55e]" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
};

export default DashboardLayout;
