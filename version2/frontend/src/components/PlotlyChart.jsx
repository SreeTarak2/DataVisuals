import React, { useEffect, useRef } from 'react';

const PlotlyChart = ({ data, layout = {}, style = {}, config = {}, chartType = 'bar' }) => {
  const plotRef = useRef(null);

  useEffect(() => {
    const loadPlotly = async () => {
      try {
        // Dynamically import Plotly to avoid SSR issues
        const Plotly = (await import('plotly.js-dist-min')).default;
        
        if (plotRef.current && data) {
          // Process data based on chart type
          let processedData = data;
          
          if (chartType === 'pie' && data.length > 0 && data[0].labels && data[0].values) {
            // Convert pie chart data to Plotly format
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
            // Convert donut chart data to Plotly format
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
              zeroline: false
            },
            yaxis: {
              color: '#64748b',
              gridcolor: 'rgba(100, 116, 139, 0.2)',
              showgrid: true,
              zeroline: false
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