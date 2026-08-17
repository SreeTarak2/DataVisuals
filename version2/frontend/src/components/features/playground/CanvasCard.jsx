import React, { useRef, useCallback, useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { GripVertical, X, Copy, Expand } from 'lucide-react';
import useCanvasStore, { CARD_TYPES } from '../../../store/canvasStore';
import CanvasCardContent from './CanvasCardContent';
import CardVerticalConfig from './CardVerticalConfig';
import { cn } from '../../../lib/utils';

const MIN_WIDTH = 160;
const MIN_HEIGHT = 100;
const HANDLE_SIZE = 12;

function CanvasCard({ card, isSelected, onSelect, containerRef, zoom }) {
  const updateCard = useCanvasStore((s) => s.updateCard);
  const deleteCard = useCanvasStore((s) => s.deleteCard);
  const duplicateCard = useCanvasStore((s) => s.duplicateCard);
  const linkedDatasetData = useCanvasStore((s) => s.linkedDatasetData);
  const linkedDatasetId = useCanvasStore((s) => s.linkedDatasetId);
  const getLinkedColumns = useCanvasStore((s) => s.getLinkedColumns);

  const linkedColumns = getLinkedColumns() || [];

  const cardRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0, cardX: 0, cardY: 0 });
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(card.title);

  const meta = CARD_TYPES[card.type] || CARD_TYPES.text;

  const handleUpdateConfig = useCallback((patch) => {
    useCanvasStore.getState().updateCardConfig(card.id, patch);
  }, [card.id]);

  useEffect(() => {
    setEditTitle(card.title);
  }, [card.title]);

  /* ─── Click to select ─── */
  const handleMouseDown = useCallback((e) => {
    e.stopPropagation();
    onSelect(card.id);
  }, [card.id, onSelect]);

  /* ─── Drag ─── */
  const handleDragStart = useCallback((e) => {
    e.stopPropagation();
    e.preventDefault();
    setIsDragging(true);
    setDragStart({
      x: e.clientX,
      y: e.clientY,
      cardX: card.x,
      cardY: card.y,
    });
  }, [card.x, card.y]);

  useEffect(() => {
    if (!isDragging) return;
    const handleMouseMove = (e) => {
      const dx = (e.clientX - dragStart.x) / (zoom || 1);
      const dy = (e.clientY - dragStart.y) / (zoom || 1);
      updateCard(card.id, {
        x: dragStart.cardX + dx,
        y: dragStart.cardY + dy,
      });
    };
    const handleMouseUp = () => setIsDragging(false);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragStart, updateCard, card.id, zoom]);

  /* ─── Resize ─── */
  const handleResizeStart = useCallback((e) => {
    e.stopPropagation();
    e.preventDefault();
    setIsResizing(true);
    setResizeStart({
      x: e.clientX,
      y: e.clientY,
      width: card.width,
      height: card.height,
    });
  }, [card.width, card.height]);

  useEffect(() => {
    if (!isResizing) return;
    const handleMouseMove = (e) => {
      const dx = (e.clientX - resizeStart.x) / (zoom || 1);
      const dy = (e.clientY - resizeStart.y) / (zoom || 1);
      updateCard(card.id, {
        width: Math.max(MIN_WIDTH, resizeStart.width + dx),
        height: Math.max(MIN_HEIGHT, resizeStart.height + dy),
      });
    };
    const handleMouseUp = () => setIsResizing(false);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, resizeStart, updateCard, card.id, zoom]);

  /* ─── Double-click to edit title ─── */
  const handleDoubleClick = useCallback(() => {
    setIsEditing(true);
    setEditTitle(card.title);
  }, [card.title]);

  const handleTitleSave = useCallback(() => {
    setIsEditing(false);
    if (editTitle.trim() && editTitle !== card.title) {
      updateCard(card.id, { title: editTitle.trim() });
    }
  }, [editTitle, card.title, updateCard, card.id]);

  const handleTitleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleTitleSave();
    if (e.key === 'Escape') { setIsEditing(false); setEditTitle(card.title); }
  }, [handleTitleSave, card.title]);

  /* ─── Type indicator ─── */
  const accentColor = meta.accent;

  return (
    <motion.div
      ref={cardRef}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{
        opacity: 1,
        scale: 1,
        boxShadow: isSelected
          ? `0 0 0 2px ${accentColor}, 0 8px 32px rgba(0,0,0,0.4)`
          : '0 4px 16px rgba(0,0,0,0.25)',
      }}
      transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "absolute rounded-xl transition-shadow duration-150 group",
        isDragging && "cursor-grabbing",
        isSelected ? "overflow-visible" : "overflow-hidden"
      )}
      style={{
        left: card.x,
        top: card.y,
        width: card.width,
        height: card.height,
        background: '#000000',
        border: `1px solid ${isSelected ? accentColor : 'rgba(255,255,255,0.08)'}`,
        backdropFilter: 'blur(12px)',
        zIndex: isSelected ? 10 : 1,
        cursor: isDragging ? 'grabbing' : isResizing ? 'nwse-resize' : 'default',
      }}
      onMouseDown={handleMouseDown}
    >
      {/* ─── Top bar: drag handle + title + actions ─── */}
      <div
        className={cn(
          "flex items-center gap-1.5 px-2 h-8 shrink-0 select-none transition-colors rounded-t-xl",
          isDragging ? 'cursor-grabbing' : 'cursor-grab',
        )}
        style={{
          borderBottom: `1px solid ${isSelected ? `${accentColor}30` : 'rgba(255,255,255,0.04)'}`,
          background: isSelected ? `${accentColor}08` : 'transparent',
        }}
        onMouseDown={handleDragStart}
        onDoubleClick={handleDoubleClick}
      >
        <div className="opacity-0 group-hover:opacity-40 transition-opacity">
          <GripVertical className="w-3 h-3" style={{ color: 'rgba(255,255,255,0.5)' }} />
        </div>

        {/* Type dot */}
        <div
          className="w-2 h-2 rounded-full shrink-0"
          style={{ background: accentColor }}
        />

        {/* Title */}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <input
              autoFocus
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onBlur={handleTitleSave}
              onKeyDown={handleTitleKeyDown}
              className="w-full bg-transparent text-xs font-medium outline-none px-1 py-0.5 rounded"
              style={{
                color: '#f0f2f5',
                border: `1px solid ${accentColor}50`,
              }}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span
              className="block text-xs font-medium truncate"
              style={{ color: '#d1d5db' }}
              title={card.title}
            >
              {card.title}
            </span>
          )}
        </div>

        {/* Action buttons */}
        <div className={cn("flex items-center gap-1 transition-opacity", isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100")}>
          <button
            onClick={(e) => { e.stopPropagation(); duplicateCard(card.id); }}
            className="p-1 rounded-md border border-white/10 bg-white/5 hover:bg-white/20 transition-all text-slate-200 hover:text-white"
            title="Duplicate Card"
          >
            <Copy className="w-3.5 h-3.5 text-slate-200" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); deleteCard(card.id); }}
            className="p-1 rounded-md border border-red-500/30 bg-red-500/15 hover:bg-red-500/30 transition-all text-red-400 hover:text-red-300"
            title="Delete Card"
          >
            <X className="w-3.5 h-3.5 text-red-400" />
          </button>
        </div>
      </div>

      {/* ─── Card content area ─── */}
      <div
        className="overflow-hidden rounded-b-xl"
        style={{
          height: `calc(100% - 32px)`,
          width: '100%',
        }}
      >
        <CanvasCardContent 
          card={card} 
          isSelected={isSelected} 
          datasetData={linkedDatasetData} 
        />
      </div>

      {/* ─── Resize handle (bottom-right) ─── */}
      <div
        className={cn(
          "absolute bottom-0 right-0 cursor-nwse-resize",
          "transition-opacity flex items-center justify-center",
          isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
        )}
        style={{ width: HANDLE_SIZE + 4, height: HANDLE_SIZE + 4 }}
        onMouseDown={handleResizeStart}
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path
            d="M1 9L9 1M4 9L9 4M7 9L9 7"
            stroke={accentColor}
            strokeWidth="1.5"
            strokeLinecap="round"
            opacity={0.6}
          />
        </svg>
      </div>

      {/* ─── Floating Vertical Config Bar ─── */}
      {isSelected && (card.type === 'chart' || card.type === 'kpi') && (
        <CardVerticalConfig
          card={card}
          onUpdateConfig={handleUpdateConfig}
          linkedColumns={linkedColumns}
          linkedDatasetId={linkedDatasetId}
          accentColor={accentColor}
          side={card.x < 64 ? 'right' : 'left'}
        />
      )}
    </motion.div>
  );
}

export default React.memo(CanvasCard);
