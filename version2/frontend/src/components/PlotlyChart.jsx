import React, { useEffect, useRef } from 'react';

const PlotlyChart = ({ data, layout = {}, style = {}, config = {}, chartType = 'bar' }) => {
  const plotRef = useRef(null);

  useEffect(() => {
    const loadPlotly = async () => {
      try {
        const Plotly = (await import('plotly.js-dist-min')).default;
        if (plotRef.current && data) {
          console.log('[PlotlyChart] Received data:', data);
          console.log('[PlotlyChart] Data type:', typeof data);
          console.log('[PlotlyChart] Is array?', Array.isArray(data));
          console.log('[PlotlyChart] First item:', data[0]);
          console.log('[PlotlyChart] First item has x/y?', data[0]?.x !== undefined, data[0]?.y !== undefined);
          console.log('[PlotlyChart] Received layout:', layout);
          console.log('[PlotlyChart] Chart type:', chartType);
          let processedData = data;
          let xKey = 'x', yKey = 'y';
          let xLabel = '', yLabel = '';
          
          // Check if data is already in Plotly format (has 'type', 'x', 'y' keys)
          const isPlotlyFormat = Array.isArray(data) && data.length > 0 && 
                                 data[0].type !== undefined && 
                                 (data[0].x !== undefined || data[0].labels !== undefined);
          
          console.log('[PlotlyChart] Is Plotly format?', isPlotlyFormat);
          
          if (isPlotlyFormat) {
            // Data is already in Plotly format, use it directly
            processedData = data;
            console.log('[PlotlyChart] Using data as-is (Plotly format)');
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
              marker: { color: '#3b82f6' },
              name: yLabel
            }];
          } else if (chartType === 'pie' && data.length > 0 && data[0].labels && data[0].values) {
            processedData = [{
              labels: data[0].labels,
              values: data[0].values,
              type: 'pie',
              textinfo: 'label+percent',
              textposition: 'outside',
              marker: {
                colors: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316']
              }
            }];
          } else if (chartType === 'donut' && data.length > 0 && data[0].labels && data[0].values) {
            processedData = [{
              labels: data[0].labels,
              values: data[0].values,
              type: 'pie',
              hole: 0.4,
              textinfo: 'label+percent',
              textposition: 'outside',
              marker: {
                colors: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#f97316']
              }
            }];
          }

          const defaultLayout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: {
              color: '#e2e8f0',
              family: 'Inter, system-ui, sans-serif'
            },
            xaxis: {
              color: '#64748b',
              gridcolor: 'rgba(100, 116, 139, 0.2)',
              showgrid: true,
              zeroline: false,
              title: { text: xLabel, font: { color: '#e2e8f0' } }
            },
            yaxis: {
              color: '#64748b',
              gridcolor: 'rgba(100, 116, 139, 0.2)',
              showgrid: true,
              zeroline: false,
              title: { text: yLabel, font: { color: '#e2e8f0' } }
            },
            margin: {
              l: 60,
              r: 30,
              t: 30,
              b: 60
            },
            showlegend: chartType !== 'pie' && chartType !== 'donut',
            legend: {
              x: 1,
              y: 1,
              bgcolor: 'rgba(0,0,0,0)',
              bordercolor: 'rgba(0,0,0,0)',
              font: {
                color: '#e2e8f0'
              }
            }
          };

          console.log('[PlotlyChart] Final processed data:', processedData);
          console.log('[PlotlyChart] Final layout:', {...defaultLayout, ...layout});
          
          Plotly.newPlot(plotRef.current, processedData, {
            ...defaultLayout,
            ...layout
          }, {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
            displaylogo: false,
            ...config
          });
          
          console.log('[PlotlyChart] Chart rendered successfully');
        }
      } catch (error) {
        console.error('[PlotlyChart] Failed to load Plotly:', error);
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
    return () => {
      if (plotRef.current) {
        plotRef.current.innerHTML = '';
      }
    };
  }, [data, layout, config, chartType]);

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