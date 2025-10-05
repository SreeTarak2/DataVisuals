import React, { useEffect, useRef } from 'react'
import Plot from 'react-plotly.js'

interface PlotlyChartProps {
  data: any[]
  chartType: string
  fields: string[]
  title?: string
  isNormal?: boolean
  showStatistics?: boolean
  onDataClick?: (data: any) => void
  onHover?: (data: any) => void
  className?: string
}

const PlotlyChart: React.FC<PlotlyChartProps> = ({
  data,
  chartType,
  fields,
  title,
  isNormal = false,
  showStatistics = false,
  onDataClick,
  onHover,
  className = ''
}) => {
  const plotRef = useRef<Plot>(null)

  const getLayout = () => {
    const baseLayout = {
      title: title || `${chartType.charAt(0).toUpperCase() + chartType.slice(1)} Chart`,
      font: {
        family: 'Inter, system-ui, sans-serif',
        size: isNormal ? 12 : 11,
        color: isNormal ? '#374151' : '#e2e8f0'
      },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      margin: { l: 50, r: 50, t: 50, b: 50 },
      showlegend: true,
      legend: {
        orientation: 'h',
        y: -0.2,
        x: 0.5,
        xanchor: 'center',
        font: {
          color: isNormal ? '#6b7280' : '#94a3b8'
        }
      },
      xaxis: {
        gridcolor: isNormal ? '#e5e7eb' : '#374151',
        color: isNormal ? '#6b7280' : '#94a3b8',
        titlefont: {
          color: isNormal ? '#374151' : '#e2e8f0'
        }
      },
      yaxis: {
        gridcolor: isNormal ? '#e5e7eb' : '#374151',
        color: isNormal ? '#6b7280' : '#94a3b8',
        titlefont: {
          color: isNormal ? '#374151' : '#e2e8f0'
        }
      }
    }

    if (showStatistics && !isNormal) {
      return {
        ...baseLayout,
        annotations: [
          {
            x: 0.02,
            y: 0.98,
            xref: 'paper',
            yref: 'paper',
            text: `n=${data.length} | σ=${calculateStdDev(data, fields[1])?.toFixed(2)}`,
            showarrow: false,
            font: {
              size: 10,
              color: '#94a3b8'
            },
            bgcolor: 'rgba(0,0,0,0.5)',
            bordercolor: '#374151',
            borderwidth: 1
          }
        ]
      }
    }

    return baseLayout
  }

  const calculateStdDev = (data: any[], field: string) => {
    if (!field || data.length === 0) return 0
    const values = data.map(d => d[field]).filter(v => typeof v === 'number')
    if (values.length === 0) return 0
    
    const mean = values.reduce((a, b) => a + b, 0) / values.length
    const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length
    return Math.sqrt(variance)
  }

  const getPlotData = () => {
    if (!data || data.length === 0) return []

    switch (chartType) {
      case 'bar_chart':
        return getBarChartData()
      case 'line_chart':
        return getLineChartData()
      case 'scatter_plot':
        return getScatterPlotData()
      case 'pie_chart':
        return getPieChartData()
      case 'histogram':
        return getHistogramData()
      case 'box_plot':
        return getBoxPlotData()
      case 'heatmap':
        return getHeatmapData()
      default:
        return getBarChartData()
    }
  }

  const getBarChartData = () => {
    const xField = fields[0] || 'category'
    const yField = fields[1] || 'value'
    
    const xData = data.map(d => d[xField])
    const yData = data.map(d => d[yField])

    return [{
      x: xData,
      y: yData,
      type: 'bar',
      name: yField,
      marker: {
        color: isNormal 
          ? ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
          : ['#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'],
        line: {
          color: isNormal ? '#1e40af' : '#0891b2',
          width: 1
        }
      },
      hovertemplate: `<b>%{x}</b><br>${yField}: %{y}<br><extra></extra>`,
      showlegend: false
    }]
  }

  const getLineChartData = () => {
    const xField = fields[0] || 'index'
    const yField = fields[1] || 'value'
    
    const xData = data.map(d => d[xField])
    const yData = data.map(d => d[yField])

    return [{
      x: xData,
      y: yData,
      type: 'scatter',
      mode: 'lines+markers',
      name: yField,
      line: {
        color: isNormal ? '#3b82f6' : '#06b6d4',
        width: 3
      },
      marker: {
        color: isNormal ? '#1e40af' : '#0891b2',
        size: 6
      },
      hovertemplate: `<b>${xField}: %{x}</b><br>${yField}: %{y}<br><extra></extra>`,
      showlegend: false
    }]
  }

  const getScatterPlotData = () => {
    const xField = fields[0] || 'x'
    const yField = fields[1] || 'y'
    
    const xData = data.map(d => d[xField])
    const yData = data.map(d => d[yField])

    // Calculate correlation coefficient
    const correlation = calculateCorrelation(xData, yData)

    return [{
      x: xData,
      y: yData,
      type: 'scatter',
      mode: 'markers',
      name: `${xField} vs ${yField}`,
      marker: {
        color: isNormal ? '#3b82f6' : '#06b6d4',
        size: 8,
        opacity: 0.7
      },
      hovertemplate: `<b>${xField}: %{x}</b><br>${yField}: %{y}<br>r=${correlation.toFixed(3)}<br><extra></extra>`,
      showlegend: false
    }]
  }

  const getPieChartData = () => {
    const labelField = fields[0] || 'category'
    const valueField = fields[1] || 'value'
    
    const labels = data.map(d => d[labelField])
    const values = data.map(d => d[valueField])

    return [{
      labels,
      values,
      type: 'pie',
      hole: isNormal ? 0 : 0.3,
      marker: {
        colors: isNormal 
          ? ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
          : ['#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444']
      },
      hovertemplate: '<b>%{label}</b><br>Value: %{value}<br>Percentage: %{percent}<br><extra></extra>',
      textinfo: 'label+percent',
      textposition: 'outside'
    }]
  }

  const getHistogramData = () => {
    const field = fields[0] || 'value'
    const values = data.map(d => d[field]).filter(v => typeof v === 'number')

    return [{
      x: values,
      type: 'histogram',
      name: field,
      marker: {
        color: isNormal ? '#3b82f6' : '#06b6d4',
        opacity: 0.7
      },
      hovertemplate: `<b>${field}</b><br>Count: %{y}<br>Range: %{x}<br><extra></extra>`,
      showlegend: false
    }]
  }

  const getBoxPlotData = () => {
    const categoryField = fields[0] || 'category'
    const valueField = fields[1] || 'value'
    
    const categories = [...new Set(data.map(d => d[categoryField]))]
    const boxData = categories.map(category => {
      const values = data.filter(d => d[categoryField] === category).map(d => d[valueField])
      return {
        y: values,
        name: category,
        type: 'box',
        boxpoints: 'outliers',
        marker: {
          color: isNormal ? '#3b82f6' : '#06b6d4',
          opacity: 0.7
        }
      }
    })

    return boxData
  }

  const getHeatmapData = () => {
    // Create correlation matrix for numeric fields
    const numericFields = fields.filter(field => 
      data.some(d => typeof d[field] === 'number')
    ).slice(0, 5) // Limit to 5 fields for readability

    if (numericFields.length < 2) return []

    const correlationMatrix = calculateCorrelationMatrix(data, numericFields)

    return [{
      z: correlationMatrix,
      x: numericFields,
      y: numericFields,
      type: 'heatmap',
      colorscale: isNormal ? 'Blues' : 'Viridis',
      hovertemplate: '<b>%{x} vs %{y}</b><br>Correlation: %{z:.3f}<br><extra></extra>',
      showscale: true
    }]
  }

  const calculateCorrelation = (x: number[], y: number[]) => {
    if (x.length !== y.length || x.length === 0) return 0
    
    const n = x.length
    const sumX = x.reduce((a, b) => a + b, 0)
    const sumY = y.reduce((a, b) => a + b, 0)
    const sumXY = x.reduce((acc, xi, i) => acc + xi * y[i], 0)
    const sumX2 = x.reduce((acc, xi) => acc + xi * xi, 0)
    const sumY2 = y.reduce((acc, yi) => acc + yi * yi, 0)
    
    const numerator = n * sumXY - sumX * sumY
    const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY))
    
    return denominator === 0 ? 0 : numerator / denominator
  }

  const calculateCorrelationMatrix = (data: any[], fields: string[]) => {
    const matrix = fields.map(() => fields.map(() => 0))
    
    for (let i = 0; i < fields.length; i++) {
      for (let j = 0; j < fields.length; j++) {
        if (i === j) {
          matrix[i][j] = 1
        } else {
          const x = data.map(d => d[fields[i]]).filter(v => typeof v === 'number')
          const y = data.map(d => d[fields[j]]).filter(v => typeof v === 'number')
          matrix[i][j] = calculateCorrelation(x, y)
        }
      }
    }
    
    return matrix
  }

  const handlePlotClick = (event: any) => {
    if (onDataClick && event.points && event.points.length > 0) {
      onDataClick(event.points[0])
    }
  }

  const handlePlotHover = (event: any) => {
    if (onHover && event.points && event.points.length > 0) {
      onHover(event.points[0])
    }
  }

  return (
    <div className={`w-full h-full ${className}`}>
      <Plot
        ref={plotRef}
        data={getPlotData()}
        layout={getLayout()}
        config={{
          displayModeBar: !isNormal,
          displaylogo: false,
          modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
          responsive: true
        }}
        style={{ width: '100%', height: '100%' }}
        onClick={handlePlotClick}
        onHover={handlePlotHover}
      />
    </div>
  )
}

export default PlotlyChart

