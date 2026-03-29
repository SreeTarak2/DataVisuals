import React, { useState, useEffect, useCallback } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from './Sidebar';
import Header from './Header';
import ChatPanel from '../features/chat/ChatPanel';
import ProcessingModal from '../features/datasets/ProcessingModal';
import { cn } from '../../lib/utils';
import { AiBotIcon } from '../svg/icons';
import useDatasetStore from '../../store/datasetStore';
import { agenticAPI } from '../../services/api';

const SHOW_FAB_ROUTES = ['/app/dashboard', '/app/datasets', '/app/charts', '/app/analysis'];
const DashboardLayout = () => {
  const location = useLocation();
  const [chatOpen, setChatOpen] = useState(false);
  const [chartContext, setChartContext] = useState(null);
  const [initialQuery, setInitialQuery] = useState(null);
  const [insightContext, setInsightContext] = useState(null);

  const { processingDatasetId, clearProcessingState } = useDatasetStore();

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
    // Use a stable reference for the handler to prevent duplicate listeners in StrictMode
    const handleQueryEvent = (e) => {
      const query = e.detail?.query || null;
      const ctx = e.detail?.insightContext || null;

      setInitialQuery(query);
      setInsightContext(ctx);
      setChartContext(null); // clear any chart context
      setChatOpen(true);

      // --- IMPLICIT FEEDBACK / PASSIVE LEARNING ---
      // If the user clicks to investigate a chart point or insight, we treat it as an implicit "Useful" signal
      // so the AI learns their preferences passively without requiring explicit feedback clicks.
      if (query) {
        try {
          agenticAPI.submitFeedback({
            insight_text: `User implicitly investigated: "${query.substring(0, 100)}..."`,
            feedback_type: 'useful',
            dataset_id: ctx?.dataset_id || null
          }).catch(err => console.debug('Implicit feedback saved successfully.'));
        } catch (error) {
          console.warn('Failed to log implicit belief:', error);
        }
      }
    };

    // Remove any existing listeners before adding new ones (prevents duplicates in StrictMode)
    window.removeEventListener('open-chat-with-query', handleQueryEvent);
    window.addEventListener('open-chat-with-query', handleQueryEvent, { once: false });
    
    return () => window.removeEventListener('open-chat-with-query', handleQueryEvent);
  }, []);

  const handleCloseChat = useCallback(() => {
    setChatOpen(false);
    setChartContext(null);
    setInitialQuery(null);
    setInsightContext(null);
  }, []);

  const handleClearChartContext = useCallback(() => setChartContext(null), []);
  const handleClearInitialQuery = useCallback(() => {
    setInitialQuery(null);
    setInsightContext(null);
  }, []);

  const showFab = SHOW_FAB_ROUTES.some((r) => location.pathname.startsWith(r));
  const showButton = showFab && !chatOpen;

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg-primary)]">
      {/* Sidebar — self-manages width */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header />

        <div className="flex-1 flex overflow-hidden relative">
          <main className="flex-1 overflow-y-auto p-0 relative bg-[var(--bg-primary)]">
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
            insightContext={insightContext}
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
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            drag
            dragMomentum={false}
            dragConstraints={{ top: -window.innerHeight + 80, bottom: 0, left: -window.innerWidth + 80, right: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            onClick={() => setChatOpen(true)}
            className={cn(
              "fixed bottom-6 right-6 z-50",
              "w-13 h-13 rounded-full flex items-center justify-center cursor-grab active:cursor-grabbing transition-shadow duration-300",
              "text-white shadow-premium hover:shadow-xl"
            )}
            style={{
              backgroundColor: 'var(--accent-primary)',
            }}
            title="Ask AI (Drag to move)"
          >
            <AiBotIcon className="w-10 h-10 pointer-events-none" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Processing Modal */}
      <ProcessingModal
        isOpen={!!processingDatasetId}
        datasetId={processingDatasetId}
        onClose={clearProcessingState}
      />
    </div>
  );
};

export default DashboardLayout;
