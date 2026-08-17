import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import UploadModal from '../components/features/datasets/UploadModal';
import ConnectorGrid from '../components/features/connectors/ConnectorGrid';
import { useTheme } from '../store/themeStore';
import { cn } from "../lib/utils";
import DltSetupPanel from './connectors/components/DltSetupPanel';
import { SOURCE_META, FILE_CONNECTOR_IDS } from './connectors/connectorCatalog';

const ConnectorsPage = () => {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadFileOnly, setUploadFileOnly] = useState(true);
  const [selectedDltConn, setSelectedDltConn] = useState(null);

  // ── Handle click ───────────────────────────────────────────────────
  const handleConnectorClick = useCallback((conn) => {
    if (FILE_CONNECTOR_IDS.includes(conn.id)) {
      setUploadFileOnly(true);
      setIsUploadModalOpen(true);
    } else if (conn._sourceType === 'dlt') {
      setSelectedDltConn(conn);
    } else {
      navigate(`/app/connectors/${conn.id}`);
    }
  }, [navigate]);

  return (
    <div className={cn(
      "h-full flex flex-col overflow-hidden relative selection:bg-orange-500/20 selection:text-white transition-colors duration-300",
      isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
    )}>
      {/* Background Ambient Glows */}
      <div className="absolute top-0 left-1/3 w-[500px] h-[500px] bg-orange-500/[0.02] rounded-full blur-[140px] pointer-events-none animate-pulse-soft" />

      <main className="flex-1 overflow-y-auto px-8 py-16 md:px-16 lg:px-24">
        <div className="mx-auto max-w-[1100px] space-y-16">
          
          {/* Header */}
          <header className="space-y-3 animate-in fade-in slide-in-from-top-4 duration-700">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
              <span className="text-[11px] font-semibold tracking-wider text-orange-500/80 uppercase">
                Integrations Registry
              </span>
            </div>
            <h1 className={cn(
              "text-4xl font-semibold tracking-tight transition-colors duration-300",
              isDark ? "text-white" : "text-gray-900"
            )}>
              Connectors & MCPs
            </h1>
            <p className={cn(
              "text-sm max-w-xl leading-relaxed transition-colors duration-300",
              isDark ? "text-gray-400" : "text-gray-600"
            )}>
              Connect your data sources — databases, SaaS APIs, and warehouses. Your schemas are automatically indexed into the intelligence catalog.
            </p>
          </header>

          {/* Connectors Section */}
          <section className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300">
            <ConnectorGrid onSelect={handleConnectorClick} />

            {/* Need another connection? */}
            <div className={cn(
              "mt-12 pt-12 border-t text-center transition-colors duration-300",
              isDark ? "border-white/[0.04]" : "border-gray-200"
            )}>
              <p className={cn(
                "text-sm transition-colors duration-300",
                isDark ? "text-gray-500" : "text-gray-400"
              )}>
                Need another connection? <button className="text-orange-500 hover:text-orange-400 hover:underline font-semibold transition-colors cursor-pointer">Let us know</button>
              </p>
            </div>
          </section>
        </div>
      </main>

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        fileOnly={uploadFileOnly}
      />

      {/* dlt Setup Drawer */}
      <AnimatePresence>
        {selectedDltConn && (
          <DltSetupPanel
            connector={{
              ...selectedDltConn,
              meta: SOURCE_META[selectedDltConn.id] || {},
            }}
            isDark={isDark}
            onClose={() => setSelectedDltConn(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default ConnectorsPage;
