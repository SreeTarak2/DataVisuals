import React, { useState, useEffect, useRef } from 'react';

/**
 * ResizableVerticalSplit
 * A reusable React component that splits content vertically and allows drag-to-resize.
 * Uses a clean state-driven listener hook to prevent stale closure bugs during drag re-renders.
 */
const ResizableVerticalSplit = ({
  topChild,
  bottomChild,
  initialTopHeight = 320,
  minTopHeight = 160,
  minBottomHeight = 120,
}) => {
  const [topHeight, setTopHeight] = useState(initialTopHeight);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  const startDrag = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newHeight = e.clientY - containerRect.top;

      // Apply min/max bounds check
      if (newHeight >= minTopHeight && (containerRect.height - newHeight) >= minBottomHeight) {
        setTopHeight(newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging, minTopHeight, minBottomHeight]);

  return (
    <div ref={containerRef} className="flex-1 flex flex-col h-full min-h-0 overflow-hidden relative w-full">
      {/* Top Partition */}
      <div style={{ height: `${topHeight}px` }} className="shrink-0 overflow-hidden w-full flex flex-col">
        {topChild}
      </div>

      {/* Resize Handle (Splitter Bar) */}
      <div
        onMouseDown={startDrag}
        className="h-1 w-full bg-border hover:bg-accent-primary/60 cursor-row-resize transition-all duration-150 relative z-25 shrink-0 flex items-center justify-center group"
        title="Drag to resize panels"
      >
        <div className="w-12 h-0.5 rounded bg-border-strong group-hover:bg-accent-primary transition-colors duration-150" />
      </div>

      {/* Bottom Partition */}
      <div className="flex-1 min-h-0 overflow-hidden w-full">
        {bottomChild}
      </div>
    </div>
  );
};

export default ResizableVerticalSplit;
