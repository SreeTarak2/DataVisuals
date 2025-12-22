import React, { useEffect, useRef, memo } from 'react';

const PlotlyChart = memo(({ data, layout = {}, style = {}, config = {}, chartType = 'bar' }) => {
  const plotRef = useRef(null);
  const dataHashRef = useRef(null);

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
                hovertemplate: '<b>%{x}</b><br>Count: %{y:,.0f}<extra></extra>'
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
                hovertemplate: '<b>%{x}</b><br>' + yKey + ': %{y:,.0f}<extra></extra>'
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
              hovertemplate: (chartType === 'bar' || chartType === 'bar_chart') 
                ? '<b>%{x}</b><br>' + yLabel + ': %{y:,.2f}<extra></extra>'
                : '<b>%{x}</b><br>' + yLabel + ': %{y:,.2f}<extra></extra>'
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
                hovertemplate: '<b>%{label}</b><br>%{value}<br>%{percent}<extra></extra>'
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
                hovertemplate: '<b>%{label}</b><br>%{value}<br>%{percent}<extra></extra>'
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
              hovertemplate: '<b>%{label}</b><br>%{value}<br>%{percent}<extra></extra>'
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
              hovertemplate: '<b>%{x}</b><br>' + yLabel + ': %{y:,.2f}<extra></extra>'
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
            hovermode: 'closest',
            hoverlabel: {
              bgcolor: '#161b22',
              bordercolor: '#30363d',
              font: {
                family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                size: 13,
                color: '#e6edf3'
              }
            },
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

          console.log('[PlotlyChart] Final processed data:', processedData);
          console.log('[PlotlyChart] Final layout:', {...defaultLayout, ...layout});
          
          Plotly.newPlot(plotRef.current, processedData, {
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
}, (prevProps, nextProps) => {
  // Custom comparison - only re-render if data or layout actually changed
  return (
    JSON.stringify(prevProps.data) === JSON.stringify(nextProps.data) &&
    JSON.stringify(prevProps.layout) === JSON.stringify(nextProps.layout) &&
    prevProps.chartType === nextProps.chartType
  );
});

export default PlotlyChart;