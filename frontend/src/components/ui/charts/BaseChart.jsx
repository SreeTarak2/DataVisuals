import React, { memo, useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * BaseChart - The core Plotly wrapper engine used by all UI chart components.
 * It handles Plotly lazy-loading, basic React integration, and resizing,
 * but leaves ALL styling (grids, margins, colors) to the config passed by wrappers.
 */
export const BaseChart = memo(({ 
  data, 
  layout = {}, 
  config = {}, 
  style = { width: '100%', height: '100%' },
  className = '',
  onPointClick,
  children // Important: Allows React overlays (like center text in Donuts)
}) => {
  const plotRef = useRef(null);
  const dataHashRef = useRef(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Avoid re-renders if data hasn't changed
    const dataHash = JSON.stringify(data);
    if (dataHash === dataHashRef.current) return;
    dataHashRef.current = dataHash;

    let resizeObserver = null;

    const loadPlotly = async () => {
      try {
        setLoading(true);
        const Plotly = (await import('plotly.js-dist-min')).default;
        
        if (plotRef.current && data) {
          // Merge default minimal layout with provided layout
          const finalLayout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: { t: 0, b: 0, l: 0, r: 0, pad: 0 },
            showlegend: false, // Default off to encourage custom React legends
            autosize: true,
            font: { family: 'Inter, sans-serif' },
            ...layout,
          };

          // Merge default responsive config with provided config
          const finalConfig = {
            responsive: true,
            displayModeBar: false, // Default hide for clean UI
            ...config
          };

          await Plotly.newPlot(plotRef.current, data, finalLayout, finalConfig);
          setLoading(false);

          // Handle clicks
          if (onPointClick) {
            plotRef.current.removeAllListeners('plotly_click');
            plotRef.current.on('plotly_click', (data) => {
              if (data.points && data.points.length > 0) {
                const pt = data.points[0];
                onPointClick({
                  x: pt.x,
                  y: pt.y,
                  raw: pt,
                  seriesName: pt.data.name
                });
              }
            });
          }

          // Robust resizing
          resizeObserver = new ResizeObserver(() => {
            if (plotRef.current) {
              Plotly.Plots.resize(plotRef.current);
            }
          });
          resizeObserver.observe(plotRef.current.parentElement);
        }
      } catch (error) {
        console.error('BaseChart: Error loading Plotly', error);
        setLoading(false);
      }
    };

    loadPlotly();

    return () => {
      if (resizeObserver) resizeObserver.disconnect();
      if (plotRef.current && plotRef.current.purge) {
        // eslint-disable-next-line
        plotRef.current.purge(); 
      }
    };
  }, [data, layout, config, onPointClick]);

  return (
    <div className={`relative w-full h-full ${className}`} style={style}>
      {/* Plotly canvas container */}
      <div 
        ref={plotRef} 
        className="absolute inset-0 z-0 transition-opacity duration-500"
        style={{ opacity: loading ? 0 : 1 }}
      />
      
      {/* Loading state */}
      <AnimatePresence>
        {loading && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 flex items-center justify-center z-10"
          >
            <div className="w-5 h-5 rounded-full border-2 border-slate-700 border-t-slate-400 animate-spin" />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Custom React Overlays (Tooltips, Center Text, Footers) */}
      <div className="absolute inset-0 z-20 pointer-events-none">
        {/* pointer-events-none ensures Plotly still receives hover events, but children can override this via pointer-events-auto if needed */}
        {children}
      </div>
    </div>
  );
});

export default BaseChart;
