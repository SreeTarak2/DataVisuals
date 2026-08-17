import React, { useRef, useCallback, useEffect, useState } from 'react';
import { Stage, Layer, Shape } from 'react-konva';
import useCanvasStore from '../../../store/canvasStore';
import CanvasCard from './CanvasCard';

/* ─── Dot grid spacing (world-space) ─── */
const GRID_SPACING = 36;
const DOT_RADIUS = 1.5;
const DOT_COLOR = 'rgba(255, 255, 255, 0.08)';
const MIN_ZOOM = 0.15;
const MAX_ZOOM = 4;

function PlaygroundCanvas({ containerRef }) {
  const stageRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  const cards = useCanvasStore((s) => s.cards);
  const zoom = useCanvasStore((s) => s.zoom);
  const stagePosition = useCanvasStore((s) => s.stagePosition);
  const selectedCardId = useCanvasStore((s) => s.selectedCardId);
  const setZoom = useCanvasStore((s) => s.setZoom);
  const setStagePosition = useCanvasStore((s) => s.setStagePosition);
  const setSelectedCardId = useCanvasStore((s) => s.setSelectedCardId);

  /* ─── Sync dimensions with container ─── */
  useEffect(() => {
    const el = containerRef?.current || document.body;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width, height });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [containerRef]);

  /* ─── Zoom handler (centered on cursor) ─── */
  const handleWheel = useCallback(
    (e) => {
      e.evt.preventDefault();
      const stage = stageRef.current;
      if (!stage) return;

      const pointer = stage.getPointerPosition();
      if (!pointer) return;

      const oldScale = stage.scaleX();
      const mousePointTo = {
        x: (pointer.x - stage.x()) / oldScale,
        y: (pointer.y - stage.y()) / oldScale,
      };

      const direction = e.evt.deltaY > 0 ? -1 : 1;
      const factor = 1.1;
      const newScale = Math.min(
        MAX_ZOOM,
        Math.max(MIN_ZOOM, direction > 0 ? oldScale * factor : oldScale / factor),
      );

      const newPos = {
        x: pointer.x - mousePointTo.x * newScale,
        y: pointer.y - mousePointTo.y * newScale,
      };

      stage.scaleX(newScale);
      stage.scaleY(newScale);
      stage.position(newPos);
      stage.batchDraw();

      setZoom(newScale);
      setStagePosition(newPos);
    },
    [setZoom, setStagePosition],
  );

  /* ─── Pan handlers ─── */
  const handleDragMove = useCallback(
    (e) => {
      const stage = e.target;
      setStagePosition({ x: stage.x(), y: stage.y() });
    },
    [setStagePosition],
  );

  const handleDragEnd = useCallback(
    (e) => {
      const stage = e.target;
      setStagePosition({ x: stage.x(), y: stage.y() });
    },
    [setStagePosition],
  );

  /* ─── Click on empty space = deselect ─── */
  const handleStageClick = useCallback(
    (e) => {
      if (e.target === e.target.getStage()) {
        setSelectedCardId(null);
      }
    },
    [setSelectedCardId],
  );

  /* ─── Dot grid renderer ─── */
  const renderGrid = useCallback(
    (context, shape) => {
      const stage = shape.getStage();
      if (!stage) return;

      const scale = stage.scaleX();
      const stageX = stage.x();
      const stageY = stage.y();
      const { width, height } = dimensions;

      const startX = -stageX / scale;
      const startY = -stageY / scale;
      const endX = startX + width / scale;
      const endY = startY + height / scale;

      const gridStartX = Math.floor(startX / GRID_SPACING) * GRID_SPACING;
      const gridStartY = Math.floor(startY / GRID_SPACING) * GRID_SPACING;

      context.beginPath();
      context.fillStyle = DOT_COLOR;

      for (let wx = gridStartX; wx <= endX; wx += GRID_SPACING) {
        for (let wy = gridStartY; wy <= endY; wy += GRID_SPACING) {
          const sx = wx * scale + stageX;
          const sy = wy * scale + stageY;
          context.moveTo(sx, sy);
          context.arc(sx, sy, DOT_RADIUS, 0, Math.PI * 2);
        }
      }
      context.fill();
    },
    [dimensions],
  );

  return (
    <div className="absolute inset-0">
      {/* ─── Konva Stage (dot grid + pan/zoom) ─── */}
      <Stage
        ref={stageRef}
        width={dimensions.width}
        height={dimensions.height}
        scaleX={zoom}
        scaleY={zoom}
        draggable
        onWheel={handleWheel}
        onDragMove={handleDragMove}
        onDragEnd={handleDragEnd}
        onClick={handleStageClick}
        onTap={handleStageClick}
        style={{ background: 'var(--bg-primary)' }}
      >
        <Layer listening={false}>
          <Shape sceneFunc={renderGrid} />
        </Layer>
      </Stage>

      {/* ─── HTML Card Overlay ─── */}
      <div className="absolute inset-0 pointer-events-none" style={{ overflow: 'hidden' }}>
        <div
          className="pointer-events-auto"          style={{
                    transform: `scale(${zoom}) translate(${stagePosition.x / zoom}px, ${stagePosition.y / zoom}px)`,
                    transformOrigin: '0 0',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                  }}
        >
          {cards.map((card) => (
            <CanvasCard
              key={card.id}
              card={card}
              isSelected={card.id === selectedCardId}
              onSelect={setSelectedCardId}
              containerRef={containerRef}
              zoom={zoom}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default React.memo(PlaygroundCanvas);
