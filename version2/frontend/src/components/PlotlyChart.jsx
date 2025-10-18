import React, { useEffect, useRef } from 'react';

const PlotlyChart = ({ data, layout = {}, style = {}, config = {} }) => {
  const plotRef = useRef(null);

  useEffect(() => {
    const loadPlotly = async () => {
      try {
        // Dynamically import Plotly to avoid SSR issues
        const Plotly = (await import('plotly.js-dist-min')).default;
        
        if (plotRef.current && data) {
          Plotly.newPlot(plotRef.current, data, {
            ...layout,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {
              color: '#e2e8f0'
            },
            xaxis: {
              color: '#64748b',
              gridcolor: 'rgba(100, 116, 139, 0.2)',
              ...layout.xaxis
            },
            yaxis: {
              color: '#64748b',
              gridcolor: 'rgba(100, 116, 139, 0.2)',
              ...layout.yaxis
            }
          }, {
            responsive: true,
            displayModeBar: false,
            ...config
          });
        }
      } catch (error) {
        console.error('Failed to load Plotly:', error);
        // Fallback: show a simple message
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

    // Cleanup function
    return () => {
      if (plotRef.current) {
        plotRef.current.innerHTML = '';
      }
    };
  }, [data, layout, config]);

  return (
    <div 
      ref={plotRef} 
      style={{ 
        width: '100%', 
        height: '100%',
        minHeight: '200px',
        ...style 
      }} 
    />
  );
};

export default PlotlyChart;