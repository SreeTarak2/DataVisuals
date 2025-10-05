import React, { useState, useEffect } from 'react'
import { 
  ChevronUp, 
  ChevronDown, 
  Filter, 
  RotateCcw,
  Eye,
  Download
} from 'lucide-react'
import { useDrillDown } from '../hooks/useDrillDown'
import { usePersona } from '../contexts/PersonaContext'
import toast from 'react-hot-toast'

interface DrillDownChartProps {
  datasetId: string
  initialData: any[]
  hierarchies: any[]
  chartType: 'bar' | 'pie' | 'line' | 'scatter'
  title: string
  fields: string[]
  onDataChange?: (data: any[]) => void
  showControls?: boolean
}

const DrillDownChart: React.FC<DrillDownChartProps> = ({
  datasetId,
  initialData,
  hierarchies,
  chartType,
  title,
  fields,
  onDataChange,
  showControls = true
}) => {
  const { isNormal } = usePersona()
  const [selectedValue, setSelectedValue] = useState<string | null>(null)
  
  const {
    currentPath,
    currentLevel,
    data,
    isLoading,
    canDrillDown,
    canDrillUp,
    drillDown,
    drillUp,
    reset,
    getBreadcrumbTrail,
    getCurrentHierarchy
  } = useDrillDown({
    datasetId,
    initialData,
    hierarchies,
    onDataChange
  })

  // Handle chart element clicks for drill-down
  const handleChartClick = (clickedValue: string) => {
    if (!canDrillDown || isLoading) return
    
    setSelectedValue(clickedValue)
    drillDown(clickedValue)
  }

  // Handle drill-up
  const handleDrillUp = () => {
    if (!canDrillUp || isLoading) return
    drillUp()
    setSelectedValue(null)
  }

  // Handle reset
  const handleReset = () => {
    reset()
    setSelectedValue(null)
  }

  // Render breadcrumb navigation
  const renderBreadcrumb = () => {
    const trail = getBreadcrumbTrail()
    if (trail.length === 0) return null

    return (
      <div className="flex items-center space-x-1 mb-3 text-sm">
        <button
          onClick={handleDrillUp}
          disabled={!canDrillUp || isLoading}
          className={`
            flex items-center px-2 py-1 rounded text-xs font-medium transition-colors
            ${canDrillUp && !isLoading
              ? 'text-blue-600 hover:text-blue-800 hover:bg-blue-50'
              : 'text-gray-400 cursor-not-allowed'
            }
          `}
        >
          <ChevronUp className="h-3 w-3 mr-1" />
          Back
        </button>
        
        <span className="text-gray-400">|</span>
        
        {trail.map((item, index) => (
          <React.Fragment key={index}>
            <span className={`
              px-2 py-1 rounded text-xs font-medium
              ${index === trail.length - 1
                ? 'bg-blue-100 text-blue-800'
                : 'text-gray-600'
              }
            `}>
              {item.label}
            </span>
            {index < trail.length - 1 && (
              <span className="text-gray-400">›</span>
            )}
          </React.Fragment>
        ))}
      </div>
    )
  }

  // Render chart controls
  const renderControls = () => {
    if (!showControls) return null

    return (
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <button
            onClick={handleDrillUp}
            disabled={!canDrillUp || isLoading}
            className={`
              flex items-center px-3 py-1 rounded-md text-sm font-medium transition-colors
              ${canDrillUp && !isLoading
                ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }
            `}
          >
            <ChevronUp className="h-4 w-4 mr-1" />
            Drill Up
          </button>
          
          <button
            onClick={handleReset}
            disabled={currentPath.length === 0 || isLoading}
            className={`
              flex items-center px-3 py-1 rounded-md text-sm font-medium transition-colors
              ${currentPath.length > 0 && !isLoading
                ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }
            `}
          >
            <RotateCcw className="h-4 w-4 mr-1" />
            Reset
          </button>
        </div>

        <div className="flex items-center space-x-2">
          <button className="p-1 text-gray-400 hover:text-gray-600">
            <Filter className="h-4 w-4" />
          </button>
          <button className="p-1 text-gray-400 hover:text-gray-600">
            <Download className="h-4 w-4" />
          </button>
          <button className="p-1 text-gray-400 hover:text-gray-600">
            <Eye className="h-4 w-4" />
          </button>
        </div>
      </div>
    )
  }

  // Render chart based on type
  const renderChart = () => {
    if (isLoading) {
      return (
        <div className="h-64 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )
    }

    if (!data || data.length === 0) {
      return (
        <div className="h-64 flex items-center justify-center text-gray-500">
          No data available for this level
        </div>
      )
    }

    // This would integrate with your existing chart components
    // For now, showing a placeholder
    return (
      <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600 mb-2">{chartType.toUpperCase()} Chart</p>
          <p className="text-sm text-gray-500">
            {data.length} data points
          </p>
          {canDrillDown && (
            <p className="text-xs text-blue-600 mt-2">
              Click on any element to drill down
            </p>
          )}
        </div>
      </div>
    )
  }

  // Get current hierarchy info
  const currentHierarchy = getCurrentHierarchy()

  return (
    <div className={`
      rounded-lg border-2 p-4 transition-all
      ${isNormal 
        ? 'bg-white border-gray-200 hover:border-blue-300' 
        : 'backdrop-blur-xl bg-white/10 border-white/20 hover:border-cyan-300'
      }
    `}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className={`font-medium ${
            isNormal ? 'text-gray-900' : 'text-white'
          }`}>
            {title}
          </h3>
          {currentHierarchy && (
            <p className={`text-sm ${
              isNormal ? 'text-gray-600' : 'text-slate-400'
            }`}>
              Level {currentLevel + 1}: {currentHierarchy.name}
            </p>
          )}
        </div>
        
        <div className="flex items-center space-x-2 text-sm">
          <span className={`
            px-2 py-1 rounded-full text-xs font-medium
            ${canDrillDown
              ? 'bg-green-100 text-green-800'
              : 'bg-gray-100 text-gray-600'
            }
          `}>
            {canDrillDown ? 'Drillable' : 'Max Depth'}
          </span>
        </div>
      </div>

      {/* Breadcrumb */}
      {renderBreadcrumb()}

      {/* Controls */}
      {renderControls()}

      {/* Chart */}
      <div className="relative">
        {renderChart()}
        
        {/* Loading overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-white/80 flex items-center justify-center rounded-lg">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          </div>
        )}
      </div>

      {/* Chart Info */}
      <div className="mt-4 pt-3 border-t border-gray-200">
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>
            {data.length} records
            {currentPath.length > 0 && ` • Level ${currentLevel + 1}`}
          </span>
          <span>
            {chartType} • {fields.join(', ')}
          </span>
        </div>
      </div>
    </div>
  )
}

export default DrillDownChart


