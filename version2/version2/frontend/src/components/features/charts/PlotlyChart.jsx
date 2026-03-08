import React, { useEffect, useRef, memo, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';

const MotionDiv = motion.div;

const buildConicGradient = (items, total) => {
  let cursor = 0;
  return items
    .map((item) => {
      const start = cursor;
      cursor += (item.rawValue / Math.max(total, 1)) * 360;
      return `${item.color} ${start}deg ${cursor}deg`;
    })
    .join(', ');
};

const resolvePointColor = (point) => {
  if (!point || !point.fullData) return '#8FA6D8';

  const marker = point.fullData.marker;
  const line = point.fullData.line;

  if (Array.isArray(marker?.colors)) {
    const pointIndex = typeof point.pointNumber === 'number' ? point.pointNumber : 0;
    return marker.colors[pointIndex] || marker.colors[0] || '#8FA6D8';
  }

  if (Array.isArray(marker?.color)) {
    const pointIndex = typeof point.pointNumber === 'number' ? point.pointNumber : 0;
    return marker.color[pointIndex] || marker.color[0] || '#8FA6D8';
  }

  return marker?.color || line?.color || point.color || '#8FA6D8';
};

const CustomTooltip = ({ visible, x, y, data }) => {
  if (!visible || !data || !Array.isArray(data.items) || data.items.length === 0) return null;

  const { title, items, total } = data;
  const conicGradient = buildConicGradient(items, total);

  // Calculate position to keep tooltip within viewport
  // Default to top-right of cursor, but flip if near edges
  const tooltipStyle = {
    left: x + 20,
    top: y - 20,
  };

  // Adjust if too close to right edge
  if (x > window.innerWidth - 320) {
    tooltipStyle.left = x - 300;
  }

  // Adjust if too close to bottom edge
  if (y > window.innerHeight - 220) {
    tooltipStyle.top = y - 190;
  }

  return createPortal(
    <AnimatePresence>
      <MotionDiv
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        style={{
          position: 'fixed',
          ...tooltipStyle,
          zIndex: 9999,
          pointerEvents: 'none', // Allow clicking through
        }}
        className="w-[290px] rounded-2xl overflow-hidden border border-[#95ADE14D] bg-[#0C1526EB] backdrop-blur-xl shadow-[0_16px_32px_rgba(9,17,33,0.45)]"
      >
        {/* Header */}
        <div className="px-3 py-2 border-b border-[#99AFDB33] bg-white/5">
          <span className="text-xs font-semibold text-[#EBF1FF]">{title} breakdown</span>
        </div>

        {/* Body */}
        <div className="flex gap-3 p-3">
          <div className="shrink-0">
            <div
              className="w-[76px] h-[76px] rounded-full flex items-center justify-center"
              style={{ background: `conic-gradient(${conicGradient})` }}
            >
              <div className="w-[50px] h-[50px] rounded-full bg-[#101A2BF2] flex items-center justify-center text-[11px] font-bold text-[#F1F5FF]">
                {Number.isFinite(total) ? Math.round(total).toLocaleString() : '--'}
              </div>
            </div>
          </div>
          <div className="w-full space-y-1">
            {items.map((item, index) => (
              <div key={`${item.name}-${index}`} className="flex items-center gap-2 text-xs">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-[#BCC9E7] truncate">{item.name}</span>
                <span className="ml-auto text-[#F4F8FF] font-semibold tabular-nums">
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </MotionDiv>
    </AnimatePresence>,
    document.body
  );
};

const PlotlyChart = memo(({ data, layout = {}, style = {}, config = {}, chartType = 'bar' }) => {
  const plotRef = useRef(null);
  const dataHashRef = useRef(null);
  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, data: null });

  // Helper to format numbers
  const formatValue = (val) => {
    if (typeof val === 'number') {
      if (val >= 1000000000) return (val / 1000000000).toFixed(1) + 'B';
      if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
      if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
      return val.toLocaleString(); // Add commas
    }
    return val;
  };

  useEffect(() => {
    // Create a simple hash of the data to avoid unnecessary re-renders
    const dataHash = JSON.stringify(data);
    if (dataHash === dataHashRef.current) {
      return; // Data hasn't changed, skip re-render
    }
    dataHashRef.current = dataHash;

    const loadPlotly = async () => {
      try {
        const Plotly = (await import('plotly.js-dist-min')).default;
        if (plotRef.current && data) {
          let processedData = data;
          let xKey = 'x', yKey = 'y';
          let xLabel = '', yLabel = '';

          // Check if data is already in Plotly format (has 'type', 'x', 'y' keys)
          const isPlotlyFormat = Array.isArray(data) && data.length > 0 &&
            data[0].type !== undefined &&
            (data[0].x !== undefined || data[0].labels !== undefined);

          if (isPlotlyFormat) {
            // Data is already in Plotly format, use it directly
            processedData = data.map(trace => ({
              ...trace,
              hoverinfo: 'none', // Disable default tooltip
            }));
          }
          // Handle histogram data (bin/count format)
          else if (chartType === 'histogram' && Array.isArray(data) && data.length > 0) {
            const first = data[0];
            const keys = Object.keys(first);

            // Histogram usually has 'bin' and 'count' fields
            if (keys.includes('bin') && keys.includes('count')) {
              const binValues = data.map(row => parseFloat(row.bin) || row.bin);
              xLabel = 'Bin Range';
              yLabel = 'Frequency';

              processedData = [{
                x: binValues,
                y: data.map(row => row.count),
                type: 'bar',
                marker: {
                  color: '#a78bfa',
                  line: { width: 0 }
                },
                name: 'Frequency',
                hoverinfo: 'none'
              }];
            } else {
              // Fallback to first two keys
              xKey = keys[0];
              yKey = keys[1];
              xLabel = xKey;
              yLabel = yKey;

              processedData = [{
                x: data.map(row => row[xKey]),
                y: data.map(row => row[yKey]),
                type: 'bar',
                marker: {
                  color: '#a78bfa',
                  line: { width: 0 }
                },
                name: yKey,
                hoverinfo: 'none'
              }];
            }
          }
          // Use config.columns if available (for raw data arrays)
          else if ((chartType === 'line' || chartType === 'line_chart' || chartType === 'bar' || chartType === 'bar_chart') && Array.isArray(data) && data.length > 0) {
            if (config && Array.isArray(config.columns) && config.columns.length >= 2) {
              xKey = config.columns[0];
              yKey = config.columns[1];
              xLabel = config.columns[0];
              yLabel = config.columns[1];
            } else {
              const first = data[0];
              const keys = Object.keys(first);
              if (keys.includes('x') && keys.includes('y')) {
                xKey = 'x';
                yKey = 'y';
                xLabel = 'x';
                yLabel = 'y';
              } else if (keys.length >= 2) {
                xKey = keys[0];
                yKey = keys[1];
                xLabel = keys[0];
                yLabel = keys[1];
              }
            }
            processedData = [{
              x: data.map(row => row[xKey]),
              y: data.map(row => row[yKey]),
              type: (chartType === 'bar' || chartType === 'bar_chart') ? 'bar' : 'scatter',
              mode: (chartType === 'line' || chartType === 'line_chart') ? 'lines+markers' : undefined,
              line: (chartType === 'line' || chartType === 'line_chart') ? {
                color: '#06b6d4',
                width: 3,
                shape: 'spline'
              } : undefined,
              marker: {
                color: (chartType === 'bar' || chartType === 'bar_chart') ? '#06b6d4' : '#06b6d4',
                size: 8,
                line: (chartType === 'line' || chartType === 'line_chart') ? {
                  color: '#0d1117',
                  width: 2
                } : { width: 0 }
              },
              name: yLabel,
              hoverinfo: 'none'
            }];
          } else if ((chartType === 'pie' || chartType === 'pie_chart') && Array.isArray(data) && data.length > 0) {
            // Check if data is in Plotly format with labels/values
            if (data[0].labels && data[0].values) {
              processedData = [{
                labels: data[0].labels,
                values: data[0].values,
                type: 'pie',
                textinfo: 'label+percent',
                textposition: 'outside',
                textfont: {
                  color: '#e6edf3',
                  size: 13
                },
                marker: {
                  colors: ['#06b6d4', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#fb923c', '#84cc16', '#ec4899'],
                  line: {
                    color: '#0d1117',
                    width: 2
                  }
                },
                hoverinfo: 'none'
              }];
            } else {
              // Data is in array format with name/value or similar keys
              const first = data[0];
              const keys = Object.keys(first);
              const nameKey = keys.includes('name') ? 'name' : keys[0];
              const valueKey = keys.includes('value') ? 'value' : keys[1];

              processedData = [{
                labels: data.map(row => row[nameKey]),
                values: data.map(row => row[valueKey]),
                type: 'pie',
                textinfo: 'label+percent',
                textposition: 'outside',
                textfont: {
                  color: '#e6edf3',
                  size: 13
                },
                marker: {
                  colors: ['#06b6d4', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#fb923c', '#84cc16', '#ec4899'],
                  line: {
                    color: '#0d1117',
                    width: 2
                  }
                },
                hoverinfo: 'none'
              }];
            }
          } else if (chartType === 'donut' && data.length > 0 && data[0].labels && data[0].values) {
            processedData = [{
              labels: data[0].labels,
              values: data[0].values,
              type: 'pie',
              hole: 0.4,
              textinfo: 'label+percent',
              textposition: 'outside',
              textfont: {
                color: '#e6edf3',
                size: 13
              },
              marker: {
                colors: ['#06b6d4', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#fb923c', '#84cc16', '#ec4899'],
                line: {
                  color: '#0d1117',
                  width: 2
                }
              },
              hoverinfo: 'none'
            }];
          } else if (Array.isArray(data) && data.length > 0) {
            // Generic fallback for any unhandled chart types
            const first = data[0];
            const keys = Object.keys(first);

            // Try to intelligently pick x and y keys
            xKey = keys.includes('x') ? 'x' : keys[0];
            yKey = keys.includes('y') ? 'y' : (keys.includes('value') ? 'value' : (keys.includes('count') ? 'count' : keys[1]));
            xLabel = xKey;
            yLabel = yKey;

            const plotType = chartType === 'scatter' || chartType === 'scatter_plot' ? 'scatter' : 'bar';

            processedData = [{
              x: data.map(row => row[xKey]),
              y: data.map(row => row[yKey]),
              type: plotType,
              mode: plotType === 'scatter' ? 'markers' : undefined,
              marker: {
                color: '#06b6d4',
                size: plotType === 'scatter' ? 10 : undefined,
                line: { width: 0 }
              },
              name: yLabel,
              hoverinfo: 'none'
            }];
          }

          const defaultLayout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {
              color: '#8b949e',
              family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
              size: 13
            },
            xaxis: {
              color: '#8b949e',
              gridcolor: 'rgba(0,0,0,0)',
              showgrid: false,
              showline: false,
              zeroline: false,
              tickfont: { size: 12, color: '#8b949e' },
              title: { text: xLabel, font: { color: '#8b949e', size: 13 } },
              tickmode: chartType === 'histogram' ? 'linear' : 'auto',
              tickangle: chartType === 'histogram' ? 0 : -45,
              automargin: true
            },
            yaxis: {
              color: '#8b949e',
              gridcolor: 'rgba(0,0,0,0)',
              showgrid: false,
              showline: false,
              zeroline: false,
              tickfont: { size: 11, color: '#8b949e' },
              title: { text: yLabel, font: { color: '#8b949e', size: 13 } }
            },
            margin: {
              l: 60,
              r: 40,
              t: 40,
              b: 60
            },
            hovermode: 'x unified', // Keep 'x unified' to get all points at the same x
            showlegend: chartType !== 'pie' && chartType !== 'donut',
            legend: {
              orientation: 'h',
              yanchor: 'bottom',
              y: 1.02,
              xanchor: 'right',
              x: 1,
              bgcolor: 'rgba(0,0,0,0)',
              bordercolor: 'rgba(0,0,0,0)',
              font: {
                color: '#8b949e',
                size: 12
              }
            }
          };

          await Plotly.newPlot(plotRef.current, processedData, {
            ...defaultLayout,
            ...layout
          }, {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
            displaylogo: false,
            dragmode: 'pan',
            toImageButtonOptions: {
              format: 'png',
              filename: 'chart',
              height: 1080,
              width: 1920,
              scale: 2
            },
            ...config
          });

          // Attach hover event
          plotRef.current.on('plotly_hover', (eventData) => {
            if (!eventData || !eventData.points || eventData.points.length === 0) return;

            const points = eventData.points;
            const xVal = points[0].x; // Assuming shared X
            
            // Calculate Total
            let total = 0;
            const items = points.map(pt => {
              const rawValue = Number(pt.y ?? pt.value ?? 0) || 0; // Handle bar/line (y) and pie (value)
              total += rawValue;
              
              return {
                name: pt.data.name || pt.fullData.name || 'Series',
                value: formatValue(rawValue),
                rawValue,
                color: resolvePointColor(pt)
              };
            });

            // For Pie charts, we might want to show just the hovered slice
            if (chartType === 'pie' || chartType === 'donut') {
               const pt = points[0];
               const pieTotal = Array.isArray(pt?.data?.values)
                 ? pt.data.values.reduce((sum, value) => sum + (Number(value) || 0), 0)
                 : total;
               setTooltip({
                 visible: true,
                 x: eventData.event.clientX,
                 y: eventData.event.clientY,
                 data: {
                   title: pt.label,
                   items: [{
                     name: pt.label,
                     value: formatValue(Number(pt.value) || 0),
                     rawValue: Number(pt.value) || 0,
                     color: resolvePointColor(pt)
                   }],
                   total: pieTotal
                 }
               });
            } else {
              const filteredItems = items.filter(item => item.rawValue > 0);
              setTooltip({
                visible: true,
                x: eventData.event.clientX,
                y: eventData.event.clientY,
                data: {
                  title: xVal,
                  items: filteredItems.length > 0 ? filteredItems : items,
                  total
                }
              });
            }
          });

          // Attach unhover event
          plotRef.current.on('plotly_unhover', () => {
             setTooltip(prev => ({ ...prev, visible: false }));
          });

        }
      } catch (error) {
        console.error("Plotly load error:", error);
        // Chart failed to render - show fallback UI
        if (plotRef.current) {
          plotRef.current.innerHTML = `
            <div style="
              display: flex; 
              align-items: center; 
              justify-content: center; 
              height: 100%; 
              color: #64748b; 
              font-size: 14px;
              text-align: center;
              padding: 20px;
            ">
              <div>
                <div style="margin-bottom: 8px;">📊</div>
                <div>Chart visualization</div>
                <div style="font-size: 12px; margin-top: 4px; opacity: 0.7;">
                  Interactive chart would appear here
                </div>
              </div>
            </div>
          `;
        }
      }
    };
    loadPlotly();
    const cleanupPlotElement = plotRef.current;
    return () => {
      if (cleanupPlotElement) {
        // Plotly.purge(plotRef.current); // Ideally purge, but might need to import Plotly again
        cleanupPlotElement.innerHTML = '';
      }
    };
  }, [data, layout, config, chartType]);

  return (
    <>
      <div
        ref={plotRef}
        style={{
          width: '100%',
          height: '100%',
          minHeight: '200px',
          ...style
        }}
      />
      <CustomTooltip {...tooltip} />
    </>
  );
}, (prevProps, nextProps) => {
  // Custom comparison - only re-render if data or layout actually changed
  return (
    JSON.stringify(prevProps.data) === JSON.stringify(nextProps.data) &&
    JSON.stringify(prevProps.layout) === JSON.stringify(nextProps.layout) &&
    prevProps.chartType === nextProps.chartType
  );
});

export default PlotlyChart;
