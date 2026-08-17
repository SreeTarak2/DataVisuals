import React, { useRef, useCallback, useState, useEffect } from 'react';
import PlaygroundCanvas from '../../components/features/playground/PlaygroundCanvas';
import PlaygroundToolbar from '../../components/features/playground/PlaygroundToolbar';
import SideChatPanel from '../../components/features/chat/SideChatPanel';
import useCanvasStore, { CARD_TYPES } from '../../store/canvasStore';
import useDatasetStore from '../../store/datasetStore';
import { motion } from 'framer-motion';
import { Layers, Plus } from 'lucide-react';
import { toast } from 'react-hot-toast';

function PlaygroundPage() {
  const containerRef = useRef(null);
  const cards = useCanvasStore((s) => s.cards);
  const addCard = useCanvasStore((s) => s.addCard);
  const clearAllCards = useCanvasStore((s) => s.clearAllCards);
  const updateCardConfig = useCanvasStore((s) => s.updateCardConfig);
  const updateCard = useCanvasStore((s) => s.updateCard);
  const linkedDatasetId = useCanvasStore((s) => s.linkedDatasetId);

  const datasets = useDatasetStore((s) => s.datasets);
  const setSelectedDataset = useDatasetStore((s) => s.setSelectedDataset);
  const fetchDatasets = useDatasetStore((s) => s.fetchDatasets);

  const [isChatOpen, setIsChatOpen] = useState(false);

  const isEmpty = cards.length === 0;

  const handleAddFirstCard = useCallback((type) => {
    addCard(type);
  }, [addCard]);

  /* ─── Sync canvasStore linkedDataset → datasetStore selectedDataset ─── */
  useEffect(() => {
    if (linkedDatasetId) {
      const matched = datasets.find((d) => (d.id || d._id) === linkedDatasetId);
      if (matched) {
        setSelectedDataset(matched);
      }
    }
  }, [linkedDatasetId, datasets, setSelectedDataset]);

  /* ─── Fetch datasets on mount ─── */
  useEffect(() => {
    if (datasets.length === 0) {
      fetchDatasets();
    }
  }, [datasets.length, fetchDatasets]);

  /* ─── Pin to Canvas Handler ─── */
  const handlePinToCanvas = useCallback((msg, cardType) => {
    addCard(cardType);
    setTimeout(() => {
      const state = useCanvasStore.getState();
      const newCardId = state.selectedCardId;
      if (!newCardId) return;

      // Derive a good title from the message content or use a fallback
      const msgPreview = msg.content ? msg.content.split(/\n/)[0].replace(/[*#]/g, '').trim().slice(0, 60) : '';
      const defaultTitle = msgPreview || `AI ${cardType.charAt(0).toUpperCase() + cardType.slice(1)}`;
      let configPatch = {};

      if (cardType === 'chart' && msg.chart_config) {
        // Backend returns chart_config with {data, layout} — extract what we can
        const layoutTitle =
          msg.chart_config.layout?.title?.text ||
          msg.chart_config.layout?.title ||
          '';
        // Use exact field names from the backend chart_config for xColumn/yColumn
        // The backend stores these in chart_config.columns or chart_config.fields
        const backendColumns =
          msg.chart_config.columns ||
          msg.chart_config.fields ||
          [];
        const xColumn = Array.isArray(backendColumns) && backendColumns.length > 0
          ? backendColumns[0]
          : (msg.chart_config.xfield ||
             msg.chart_config.layout?.xaxis?.title?.text ||
             msg.chart_config.layout?.xaxis?.title ||
             '');
        // Support multi-series: extract all Y columns (all fields after index 0)
        const allYColumns = Array.isArray(backendColumns) && backendColumns.length > 1
          ? backendColumns.slice(1)
          : [];
        const yColumn = allYColumns.length > 0
          ? allYColumns[0]
          : (msg.chart_config.yfield ||
             msg.chart_config.layout?.yaxis?.title?.text ||
             msg.chart_config.layout?.yaxis?.title ||
             '');
        const yColumns = allYColumns.length > 0
          ? allYColumns
          : (yColumn ? [yColumn] : []);

        // Detect chart type from first trace or use backend-provided type
        const firstTrace = Array.isArray(msg.chart_config.data) ? msg.chart_config.data[0] : null;
        const backendChartType = msg.chart_config.chart_type || msg.chart_config.type || '';
        const detectedType = backendChartType || firstTrace?.type || 'bar';

        // Extract groupBy from backend response if present
        const groupBy = msg.chart_config.group_by || msg.chart_config.groupBy || null;

        configPatch = {
          chart_type: detectedType,
          xColumn,
          yColumn,
          yColumns,
          groupBy,
          aggregation: msg.chart_config.aggregation || 'sum',
          datasetId: linkedDatasetId,
          title: layoutTitle || defaultTitle,
          chartData: msg.chart_config.data || [],
          chartLayout: msg.chart_config.layout || {},
        };
      } else if (cardType === 'table' && msg.result_table) {
        const cols = msg.result_table.columns || [];
        const rowCount = msg.result_table.rows?.length || 0;
        configPatch = {
          columns: cols,
          limit: 50,
          datasetId: linkedDatasetId,
        };
        // Use row count in title
        const tableTitle = `${rowCount} rows`;
        updateCard(newCardId, { title: msgPreview || tableTitle });
        updateCardConfig(newCardId, configPatch);
        toast.success(`Added ${cardType.toUpperCase()} to canvas`);
        return;
      } else if (cardType === 'text') {
        configPatch = {
          content: msg.content || '',
        };
      }

      updateCardConfig(newCardId, configPatch);
      updateCard(newCardId, { title: defaultTitle });
      toast.success(`Added ${cardType.toUpperCase()} to canvas`);
    }, 120);
  }, [addCard, updateCardConfig, updateCard, linkedDatasetId]);

  return (
    <div className="h-full w-full flex flex-col overflow-hidden bg-[var(--bg-primary)]">
      {/* ─── Toolbar ─── */}
      <PlaygroundToolbar
        containerRef={containerRef}
        isChatOpen={isChatOpen}
        onToggleChat={() => setIsChatOpen((prev) => !prev)}
      />

      {/* ─── Canvas Area ─── */}
      <div ref={containerRef} className="flex-1 relative overflow-hidden flex">
        <div className="flex-1 relative">
          <PlaygroundCanvas containerRef={containerRef} />

          {/* ─── Empty state ─── */}
          {isEmpty && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="flex flex-col items-center gap-6 pointer-events-auto max-w-lg text-center px-6"
              >
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center bg-accent-primary/10">
                  <Layers className="w-7 h-7 text-accent-primary" />
                </div>

                <div className="space-y-2">
                  <h2 className="text-lg font-semibold tracking-tight text-header">
                    Welcome to the Playground
                  </h2>
                  <p className="text-sm leading-relaxed text-secondary">
                    A creative space to explore your data. Add charts, KPIs, notes, and data tables to build visual narratives.
                  </p>
                </div>

                <div className="flex items-center gap-2 flex-wrap justify-center">
                  {Object.entries(CARD_TYPES).map(([type, meta]) => (
                    <button
                      key={type}
                      onClick={() => handleAddFirstCard(type)}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-[1.03] active:scale-[0.97]"
                      style={{
                        background: `${meta.accent}15`,
                        color: meta.accent,
                        border: `1px solid ${meta.accent}30`,
                      }}
                    >
                      <Plus className="w-3.5 h-3.5" />
                      {meta.label}
                    </button>
                  ))}
                </div>

                <p className="text-[11px]" style={{ color: 'rgba(255,255,255,0.2)' }}>
                  Tip: Link a dataset from the toolbar above or click AI Assistant to start chatting
                </p>
              </motion.div>
            </div>
          )}
        </div>

        {/* ─── Right-Side Slide-Out AI Chat Panel ─── */}
        <SideChatPanel
          isOpen={isChatOpen}
          onClose={() => setIsChatOpen(false)}
          onPinToCanvas={handlePinToCanvas}
          mode="analyst"
        />
      </div>
    </div>
  );
}

export default PlaygroundPage;
