import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  BarChart3, Target, FileText, Table,
  ZoomIn, ZoomOut, Maximize2, Trash2,
  Database, ChevronDown, Plus, Layers,
  Check, Loader2, RefreshCw, X, ArrowLeft,
  Sparkles,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import useCanvasStore, { CARD_TYPES } from '../../../store/canvasStore';
import useDatasetStore from '../../../store/datasetStore';
import { datasetAPI } from '../../../services/api';
import { cn } from '../../../lib/utils';
import Logo from '../../common/Logo';

/* ─── Tooltip ─── */
function Tooltip({ children, label }) {
  return (
    <div className="relative group">
      {children}
      <span
        className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-md text-[10px] font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50"
        style={{
          background: 'var(--bg-elevated)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border)',
        }}
      >
        {label}
      </span>
    </div>
  );
}

/* ─── Add Card Button ─── */
function AddCardButton({ type, onClick, isActive }) {
  const meta = CARD_TYPES[type] || CARD_TYPES.text;
  const IconMap = { BarChart3, Target, FileText, Table };
  const Icon = IconMap[meta.icon] || FileText;

  return (
    <Tooltip label={`Add ${meta.label}`}>
      <button
        onClick={() => onClick(type)}
        className={cn(
          "relative flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150",
          "hover:scale-[1.02] active:scale-[0.98] select-none",
          isActive ? 'ring-2' : ''
        )}
        style={{
          background: isActive ? `${meta.accent}20` : 'var(--bg-elevated)',
          color: isActive ? meta.accent : 'var(--text-secondary)',
          border: `1px solid ${isActive ? meta.accent : 'var(--border)'}`,
          ringColor: meta.accent,
        }}
      >
        <Icon className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">{meta.label}</span>
      </button>
    </Tooltip>
  );
}

/* ─── Dataset Selector ─── */
function DatasetSelector({ selectedDataset, datasets, onSelectDataset, onRefreshDatasets, loading }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150"
        style={{
          background: open ? 'var(--bg-elevated)' : 'transparent',
          color: 'var(--text-secondary)',
          border: '1px solid var(--border)',
        }}
      >
        <Database className="w-3.5 h-3.5" style={{ color: selectedDataset ? 'var(--accent-primary)' : 'var(--text-muted)' }} />
        <span className="max-w-[120px] truncate">
          {selectedDataset?.name || selectedDataset?.filename || 'No dataset'}
        </span>
        <ChevronDown className={cn("w-3 h-3 transition-transform duration-150", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.96 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 top-full mt-1.5 z-50 min-w-[200px]"
          >
            <div
              className="rounded-lg overflow-hidden"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-lg)',
              }}
            >
              <div className="px-3 pt-3 pb-2 flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>
                  Datasets
                </span>
                <button
                  onClick={() => { onRefreshDatasets?.(); }}
                  disabled={loading}
                  className="p-1 rounded hover:bg-[var(--bg-elevated)] transition-colors"
                >
                  <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} style={{ color: 'var(--text-muted)' }} />
                </button>
              </div>

              <div className="max-h-48 overflow-y-auto px-1.5 pb-1.5">
                {datasets.length === 0 ? (
                  <div className="px-3 py-6 text-center">
                    <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>No datasets found</p>
                  </div>
                ) : (
                  datasets.map((ds) => {
                    const dsId = ds.id || ds._id;
                    const isSelected = selectedDataset && (selectedDataset.id || selectedDataset._id) === dsId;
                    return (
                      <button
                        key={dsId}
                        onClick={() => { onSelectDataset(ds); setOpen(false); }}
                        className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-left transition-all"
                        style={{
                          background: isSelected ? 'var(--bg-elevated)' : 'transparent',
                          color: isSelected ? 'var(--text-header)' : 'var(--text-secondary)',
                        }}
                      >
                        <Database className="w-3 h-3 shrink-0" style={{ color: isSelected ? 'var(--accent-primary)' : 'var(--text-muted)' }} />
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-medium truncate">
                            {ds.name || ds.filename || 'Unnamed'}
                          </div>
                        </div>
                        {isSelected && <Check className="w-3 h-3" style={{ color: 'var(--accent-primary)' }} />}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ═══════════════════════════════════════════
   PlaygroundToolbar — Main Component
   ═══════════════════════════════════════════ */
export default function PlaygroundToolbar({ containerRef, isChatOpen = false, onToggleChat }) {
  const navigate = useNavigate();

  const cards = useCanvasStore((s) => s.cards);
  const addCard = useCanvasStore((s) => s.addCard);
  const deleteCard = useCanvasStore((s) => s.deleteCard);
  const clearAllCards = useCanvasStore((s) => s.clearAllCards);
  const zoom = useCanvasStore((s) => s.zoom);
  const setZoom = useCanvasStore((s) => s.setZoom);
  const selectedCardId = useCanvasStore((s) => s.selectedCardId);
  const linkedDatasetId = useCanvasStore((s) => s.linkedDatasetId);
  const setLinkedDataset = useCanvasStore((s) => s.setLinkedDataset);

  const datasets = useDatasetStore((s) => s.datasets);
  const fetchDatasets = useDatasetStore((s) => s.fetchDatasets);
  const dsLoading = useDatasetStore((s) => s.loading);

  const selectedDataset = datasets.find(d => (d.id || d._id) === linkedDatasetId) || null;

  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const zoomPercent = Math.round(zoom * 100);
  const selectedCard = cards.find((c) => c.id === selectedCardId);
  const cardCount = cards.length;

  const handleZoomIn = useCallback(() => {
    setZoom(Math.min(4, zoom * 1.2));
  }, [zoom, setZoom]);

  const handleZoomOut = useCallback(() => {
    setZoom(Math.max(0.15, zoom / 1.2));
  }, [zoom, setZoom]);

  const handleZoomReset = useCallback(() => {
    setZoom(1);
  }, [setZoom]);

  const handleSelectDataset = useCallback((ds) => {
    const dsId = ds.id || ds._id;
    const store = useCanvasStore.getState();
    setLinkedDataset(dsId, []);

    // Fetch a preview of the data for the playground
    if (dsId) {
      datasetAPI.getDatasetPreview(dsId, { limit: 50 })
        .then((res) => {
          const data = res.data?.data || res.data?.rows || res.data?.preview || [];
          setLinkedDataset(dsId, data);
        })
        .catch(() => {
          // Silently fail — cards will show "link a dataset"
        });
    }

    // Update all existing cards to use this dataset
    const currentCards = store.cards;
    currentCards.forEach((card) => {
      if (['chart', 'kpi', 'table'].includes(card.type)) {
        store.updateCardConfig(card.id, { datasetId: dsId });
      }
    });
  }, [setLinkedDataset]);

  // Fetch datasets on mount
  React.useEffect(() => {
    if (datasets.length === 0) {
      fetchDatasets();
    }
  }, [datasets.length, fetchDatasets]);

  // Re-fetch dataset preview on page load when linkedDatasetId is restored
  // from localStorage but preview data is empty (cards survive refresh)
  const linkedDatasetData = useCanvasStore((s) => s.linkedDatasetData);
  React.useEffect(() => {
    if (linkedDatasetId && linkedDatasetData.length === 0) {
      datasetAPI.getDatasetPreview(linkedDatasetId, { limit: 50 })
        .then((res) => {
          const data = res.data?.data || res.data?.rows || res.data?.preview || [];
          setLinkedDataset(linkedDatasetId, data);
        })
        .catch(() => {
          // Silently fail — cards will show "link a dataset"
        });
    }
  }, [linkedDatasetId, linkedDatasetData]);

  return (
    <>
      <div
        className="flex items-center justify-between px-4 shrink-0 select-none z-20"
        style={{
          height: 52,
          borderBottom: '1px solid var(--border)',
          background: 'rgba(24, 24, 26, 0.90)',
          backdropFilter: 'blur(12px)',
        }}
      >
        {/* ─── Left: Branding + Stats ─── */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate('/app/dashboard')}
            className="p-1.5 rounded-lg transition-all hover:bg-[rgba(255,255,255,0.06)] active:scale-95 text-[rgba(255,255,255,0.6)] hover:text-white flex items-center justify-center mr-1 cursor-pointer"
            title="Exit Playground"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>

          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-accent-primary/10">
              <Layers className="w-3.5 h-3.5 text-accent-primary" />
            </div>
            <span className="text-sm font-semibold tracking-tight hidden sm:inline text-header">
              Playground
            </span>
          </div>

          {cardCount > 0 && (
            <div
              className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium tabular-nums"
              style={{ background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.4)' }}
            >
              <Layers className="w-3 h-3" />
              {cardCount} card{cardCount !== 1 ? 's' : ''}
            </div>
          )}
        </div>

        {/* ─── Center: Add Card tools ─── */}
        <div className="flex items-center gap-1.5">
          {Object.keys(CARD_TYPES).map((type) => (
            <AddCardButton
              key={type}
              type={type}
              onClick={addCard}
              isActive={false}
            />
          ))}
        </div>

        {/* ─── Right: Dataset + Zoom + Actions ─── */}
        <div className="flex items-center gap-2">
          {/* AI Assistant Drawer Toggle Button */}
          <button
            onClick={onToggleChat}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all duration-150 cursor-pointer border shadow-sm",
              isChatOpen
                ? "bg-orange-500/20 text-orange-400 border-orange-500/40 shadow-orange-500/10"
                : "bg-white/5 text-slate-200 border-white/10 hover:border-white/25 hover:text-white"
            )}
            title="Toggle AI Assistant Sidebar"
          >
            <Logo size={18} />
            <span className="hidden sm:inline">AI Assistant</span>
          </button>

          {/* Dataset selector */}
          <DatasetSelector
            selectedDataset={selectedDataset}
            datasets={datasets}
            onSelectDataset={handleSelectDataset}
            onRefreshDatasets={fetchDatasets}
            loading={dsLoading}
          />

          <div className="w-px h-5" style={{ background: 'rgba(255,255,255,0.06)' }} />

          {/* Zoom controls */}
          <div className="flex items-center gap-0.5">
            <Tooltip label="Zoom out">
              <button
                onClick={handleZoomOut}
                className="p-1.5 rounded-lg transition-all hover:bg-[rgba(255,255,255,0.06)] active:scale-90"
              >
                <ZoomOut className="w-3.5 h-3.5" style={{ color: 'rgba(255,255,255,0.5)' }} />
              </button>
            </Tooltip>

            <button
              onClick={handleZoomReset}
              className="px-2 py-1 rounded-md text-[11px] font-medium tabular-nums transition-all hover:bg-[rgba(255,255,255,0.06)]"
              style={{ color: 'rgba(255,255,255,0.4)' }}
            >
              {zoomPercent}%
            </button>

            <Tooltip label="Zoom in">
              <button
                onClick={handleZoomIn}
                className="p-1.5 rounded-lg transition-all hover:bg-[rgba(255,255,255,0.06)] active:scale-90"
              >
                <ZoomIn className="w-3.5 h-3.5" style={{ color: 'rgba(255,255,255,0.5)' }} />
              </button>
            </Tooltip>
          </div>

          <div className="w-px h-5" style={{ background: 'rgba(255,255,255,0.06)' }} />

          {/* Delete selected card */}
          {selectedCard && (
            <Tooltip label="Delete card">
              <button
                onClick={() => deleteCard(selectedCardId)}
                className="p-1.5 rounded-lg transition-all hover:bg-red-500/15 active:scale-90"
              >
                <Trash2 className="w-3.5 h-3.5" style={{ color: 'rgba(239,68,68,0.7)' }} />
              </button>
            </Tooltip>
          )}

          {/* Clear all */}
          {cardCount > 0 && (
            <Tooltip label="Clear canvas">
              <button
                onClick={() => setShowClearConfirm(true)}
                className="p-1.5 rounded-lg transition-all hover:bg-[rgba(255,255,255,0.06)] active:scale-90"
              >
                <X className="w-3.5 h-3.5" style={{ color: 'rgba(255,255,255,0.4)' }} />
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      {/* ═══ Clear Confirmation Modal ═══ */}
      <AnimatePresence>
        {showClearConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center"
            style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
            onClick={() => setShowClearConfirm(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="rounded-xl p-6 max-w-sm w-full mx-4"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-lg)',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                Clear canvas?
              </h3>
              <p className="text-xs mb-5" style={{ color: 'var(--text-secondary)' }}>
                This will remove all {cardCount} card{cardCount !== 1 ? 's' : ''} from the playground. This action cannot be undone.
              </p>
              <div className="flex items-center justify-end gap-2">
                <button
                  onClick={() => setShowClearConfirm(false)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                  style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => { clearAllCards(); setShowClearConfirm(false); }}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                  style={{ background: '#ef4444', color: '#fff' }}
                >
                  Clear all
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
