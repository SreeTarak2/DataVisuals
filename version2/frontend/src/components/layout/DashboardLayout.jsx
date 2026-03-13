import React, { useState, useEffect, useCallback } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from './Sidebar';
import Header from './Header';
import ChatPanel from '../features/chat/ChatPanel';
import { cn } from '../../lib/utils';
import { AiBotIcon } from '../svg/icons';


const SHOW_FAB_ROUTES = ['/app/dashboard', '/app/datasets', '/app/charts', '/app/insights'];
const DashboardLayout = () => {
  const location = useLocation();
  const [chatOpen, setChatOpen] = useState(false);
  const [chartContext, setChartContext] = useState(null);
  const [initialQuery, setInitialQuery] = useState(null);

  useEffect(() => {
    const handler = (e) => {
      setChartContext(e.detail || null);
      setChatOpen(true);
    };
    window.addEventListener('open-chat-with-context', handler);
    return () => window.removeEventListener('open-chat-with-context', handler);
  }, []);

  // Listen for investigate / query events from KPI cards & Insights
  useEffect(() => {
    const handler = (e) => {
      setInitialQuery(e.detail?.query || null);
      setChartContext(null); // clear any chart context
      setChatOpen(true);
    };
    window.addEventListener('open-chat-with-query', handler);
    return () => window.removeEventListener('open-chat-with-query', handler);
  }, []);

  const handleCloseChat = useCallback(() => {
    setChatOpen(false);
    setChartContext(null);
    setInitialQuery(null);
  }, []);

  const handleClearChartContext = useCallback(() => setChartContext(null), []);
  const handleClearInitialQuery = useCallback(() => setInitialQuery(null), []);

  const showFab = SHOW_FAB_ROUTES.some((r) => location.pathname.startsWith(r));
  const showButton = showFab && !chatOpen;

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--page-bg)]">
      {/* Sidebar — self-manages width */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header />

        <div className="flex-1 flex overflow-hidden relative">
          <main className="flex-1 overflow-y-auto p-0 relative">
            <Outlet />
          </main>

          {/* ═══ Slide-in Chat Panel ═══ */}
          <ChatPanel
            isOpen={chatOpen}
            onClose={handleCloseChat}
            chartContext={chartContext}
            onClearChartContext={handleClearChartContext}
            initialQuery={initialQuery}
            onClearInitialQuery={handleClearInitialQuery}
          />
        </div>
      </div>

      {/* ═══ Floating AI Chat Button ═══ */}
      <AnimatePresence>
        {showButton && (
          <motion.button
            key="chat-fab"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            onClick={() => setChatOpen(true)}
            className={cn(
              "fixed bottom-6 right-6 z-50",
              "w-13 h-13 rounded-full",
              "bg-ocean hover:bg-ocean/90 shadow-lg shadow-ocean/25",
              "flex items-center justify-center",
              "text-white cursor-pointer",
              "transition-colors duration-150",
              "hover:shadow-xl hover:shadow-ocean/30",
              "active:scale-95"
            )}
            title="Ask AI"
          >
            <AiBotIcon className="w-15 h-15" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
};

export default DashboardLayout;
