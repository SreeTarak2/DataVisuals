import React, { useRef, useEffect } from 'react'
import Plot from 'react-plotly.js'

const PlotlyChart = ({ 
  data, 
  layout = {}, 
  config = {}, 
  onHover, 
  onClick, 
  onSelected,
  style = { width: '100%', height: '100%' },
  className = '',
  ...props 
}) => {
  const plotRef = useRef(null)

  // Default layout configuration
  const defaultLayout = {
    autosize: true,
    margin: { l: 50, r: 50, t: 50, b: 50 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter, system-ui, sans-serif' },
    ...layout
  }

  // Default config for better UX
  const defaultConfig = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
    responsive: true,
    ...config
  }

  // Event handlers for Plotly
  const handlePlotlyClick = (event) => {
    if (onClick) {
      onClick(event)
    }
  }

  const handlePlotlyHover = (event) => {
    if (onHover) {
      onHover(event)
    }
  }

  const handlePlotlySelected = (event) => {
    if (onSelected) {
      onSelected(event)
    }
  }


  // Add error handling for missing data
  if (!data || (Array.isArray(data) && data.length === 0)) {
    return (
      <div className={`w-full h-full flex items-center justify-center bg-gray-50 rounded-lg ${className}`} style={style}>
        <div className="text-center p-4">
          <div className="text-gray-400 mb-2">📊</div>
          <p className="text-sm text-gray-500">No data available</p>
        </div>
      </div>
    )
  }

  return (
    <Plot
      ref={plotRef}
      data={data}
      layout={defaultLayout}
      config={defaultConfig}
      style={style}
      className={className}
      onInitialized={(figure, graphDiv) => {
        // Initialize chart
        console.log('Plotly chart initialized')
      }}
      onUpdate={(figure, graphDiv) => {
        // Handle chart updates
        console.log('Plotly chart updated')
      }}
      onPurge={(figure, graphDiv) => {
        // Handle chart cleanup
        console.log('Plotly chart purged')
      }}
      onClick={handlePlotlyClick}
      onHover={handlePlotlyHover}
      onSelected={handlePlotlySelected}
      {...props}
    />
  )
}

export default PlotlyChart

