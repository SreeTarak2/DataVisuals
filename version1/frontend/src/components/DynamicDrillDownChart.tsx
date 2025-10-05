import React, { useState, useEffect } from 'react'
import { 
  ChevronUp, 
  ChevronDown, 
  Filter, 
  RotateCcw,
  Eye,
  Download,
  BarChart3,
  TrendingUp,
  PieChart,
  Scatter
} from 'lucide-react'
import { usePersona } from '../contexts/PersonaContext'
import axios from 'axios'
import toast from 'react-hot-toast'

interface DynamicDrillDownChartProps {
  datasetId: string
  initialData: any[]
  onDataChange?: (data: any[]) => void
  showControls?: boolean
}

interface Hierarchy {
  type: string
  field: string
  name: string
  levels: HierarchyLevel[]
  confidence: number
  drillable: boolean
}

interface HierarchyLevel {
  level: number
  name: string
  field: string
  parent?: string
  aggregation: string
  description: string
}

interface DrillDownState {
  currentHierarchy: Hierarchy | null
  currentLevel: number
  currentPath: string[]
  data: any[]
  isLoading: boolean
  canDrillDown: boolean
  canDrillUp: boolean
  availableHierarchies: Hierarchy[]
}

const DynamicDrillDownChart: React.FC<DynamicDrillDownChartProps> = ({
  datasetId,
  initialData,
  onDataChange,
  showControls = true
}) => {
  const { isNormal } = usePersona()
  const [state, setState] = useState<DrillDownState>({
    currentHierarchy: null,
    currentLevel: 0,
    currentPath: [],
    data: initialData,
    isLoading: false,
    canDrillDown: false,
    canDrillUp: false,
    availableHierarchies: []
  })

  // Load dataset analysis on mount
  useEffect(() => {
    loadDatasetAnalysis()
  }, [datasetId])

  const loadDatasetAnalysis = async () => {
    try {
      setState(prev => ({ ...prev, isLoading: true }))
      
      const response = await axios.get(`/api/datasets/${datasetId}/dynamic-analysis`)
      const analysis = response.data.analysis
      
      setState(prev => ({
        ...prev,
        availableHierarchies: analysis.hierarchies || [],
        isLoading: false
      }))
      
      // Auto-select first hierarchy if available
      if (analysis.hierarchies && analysis.hierarchies.length > 0) {
        selectHierarchy(analysis.hierarchies[0])
      }
      
    } catch (error) {
      console.error('Failed to load dataset analysis:', error)
      toast.error('Failed to load dataset analysis')
      setState(prev => ({ ...prev, isLoading: false }))
    }
  }

  const selectHierarchy = async (hierarchy: Hierarchy) => {
    if (!hierarchy.drillable) return
    
    setState(prev => ({ ...prev, isLoading: true }))
    
    try {
      // Start drill-down at level 1
      const result = await executeDrillDown(hierarchy, 1, {})
      
      setState(prev => ({
        ...prev,
        currentHierarchy: hierarchy,
        currentLevel: 1,
        currentPath: [],
        data: result.data || [],
        canDrillDown: result.can_drill_down || false,
        canDrillUp: false,
        isLoading: false
      }))
      
      onDataChange?.(result.data || [])
      
    } catch (error) {
      console.error('Failed to select hierarchy:', error)
      toast.error('Failed to select hierarchy')
      setState(prev => ({ ...prev, isLoading: false }))
    }
  }

  const executeDrillDown = async (hierarchy: Hierarchy, level: number, filters: Record<string, any>) => {
    const response = await axios.post(`/api/datasets/${datasetId}/dynamic-drilldown`, {
      hierarchy,
      current_level: level,
      filters
    })
    
    return response.data.drilldown_result
  }

  const handleDrillDown = async (clickedValue: string) => {
    if (!state.currentHierarchy || !state.canDrillDown || state.isLoading) return
    
    const nextLevel = state.currentLevel + 1
    const newPath = [...state.currentPath, clickedValue]
    
    setState(prev => ({ ...prev, isLoading: true }))
    
    try {
      // Build filters for current drill-down path
      const filters: Record<string, any> = {}
      newPath.forEach((value, index) => {
        const levelInfo = state.currentHierarchy!.levels[index]
        if (levelInfo) {
          filters[levelInfo.field] = value
        }
      })
      
      const result = await executeDrillDown(state.currentHierarchy, nextLevel, filters)
      
      setState(prev => ({
        ...prev,
        currentLevel: nextLevel,
        currentPath: newPath,
        data: result.data || [],
        canDrillDown: result.can_drill_down || false,
        canDrillUp: true,
        isLoading: false
      }))
      
      onDataChange?.(result.data || [])
      toast.success(`Drilled down to ${clickedValue}`)
      
    } catch (error) {
      console.error('Drill-down failed:', error)
      toast.error('Failed to drill down')
      setState(prev => ({ ...prev, isLoading: false }))
    }
  }

  const handleDrillUp = async () => {
    if (!state.currentHierarchy || !state.canDrillUp || state.isLoading) return
    
    const prevLevel = state.currentLevel - 1
    const newPath = state.currentPath.slice(0, -1)
    
    setState(prev => ({ ...prev, isLoading: true }))
    
    try {
      // Build filters for previous level
      const filters: Record<string, any> = {}
      newPath.forEach((value, index) => {
        const levelInfo = state.currentHierarchy!.levels[index]
        if (levelInfo) {
          filters[levelInfo.field] = value
        }
      })
      
      const result = await executeDrillDown(state.currentHierarchy, prevLevel, filters)
      
      setState(prev => ({
        ...prev,
        currentLevel: prevLevel,
        currentPath: newPath,
        data: result.data || [],
        canDrillDown: result.can_drill_down || false,
        canDrillUp: newPath.length > 0,
        isLoading: false
      }))
      
      onDataChange?.(result.data || [])
      toast.success('Drilled up to previous level')
      
    } catch (error) {
      console.error('Drill-up failed:', error)
      toast.error('Failed to drill up')
      setState(prev => ({ ...prev, isLoading: false }))
    }
  }

  const handleReset = async () => {
    if (!state.currentHierarchy || state.isLoading) return
    
    setState(prev => ({ ...prev, isLoading: true }))
    
    try {
      const result = await executeDrillDown(state.currentHierarchy, 1, {})
      
      setState(prev => ({
        ...prev,
        currentLevel: 1,
        currentPath: [],
        data: result.data || [],
        canDrillDown: result.can_drill_down || false,
        canDrillUp: false,
        isLoading: false
      }))
      
      onDataChange?.(result.data || [])
      toast.success('Reset to top level')
      
    } catch (error) {
      console.error('Reset failed:', error)
      toast.error('Failed to reset')
      setState(prev => ({ ...prev, isLoading: false }))
    }
  }

  const getChartIcon = (hierarchyType: string) => {
    switch (hierarchyType) {
      case 'temporal': return <TrendingUp className="h-4 w-4" />
      case 'geographic': return <BarChart3 className="h-4 w-4" />
      case 'categorical': return <PieChart className="h-4 w-4" />
      default: return <Scatter className="h-4 w-4" />
    }
  }

  const renderBreadcrumb = () => {
    if (state.currentPath.length === 0) return null

    return (
      <div className="flex items-center space-x-1 mb-3 text-sm">
        <button
          onClick={handleDrillUp}
          disabled={!state.canDrillUp || state.isLoading}
          className={`
            flex items-center px-2 py-1 rounded text-xs font-medium transition-colors
            ${state.canDrillUp && !state.isLoading
              ? 'text-blue-600 hover:text-blue-800 hover:bg-blue-50'
              : 'text-gray-400 cursor-not-allowed'
            }
          `}
        >
          <ChevronUp className="h-3 w-3 mr-1" />
          Back
        </button>
        
        <span className="text-gray-400">|</span>
        
        {state.currentPath.map((level, index) => (
          <span key={index} className="text-gray-600">
            {level} {index < state.currentPath.length - 1 && '>'}
          </span>
        ))}
      </div>
    )
  }

  const renderHierarchySelector = () => {
    if (state.availableHierarchies.length === 0) return null

    return (
      <div className="mb-4">
        <label className={`block text-sm font-medium mb-2 ${
          isNormal ? 'text-gray-700' : 'text-white'
        }`}>
          Select Drill-Down Hierarchy:
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {state.availableHierarchies.map((hierarchy, index) => (
            <button
              key={index}
              onClick={() => selectHierarchy(hierarchy)}
              disabled={!hierarchy.drillable || state.isLoading}
              className={`
                flex items-center space-x-2 p-3 rounded-lg border-2 transition-all
                ${state.currentHierarchy?.field === hierarchy.field
                  ? 'border-blue-500 bg-blue-50'
                  : hierarchy.drillable
                    ? 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                    : 'border-gray-200 bg-gray-100 cursor-not-allowed'
                }
              `}
            >
              {getChartIcon(hierarchy.type)}
              <div className="text-left">
                <div className="font-medium text-sm">{hierarchy.name}</div>
                <div className="text-xs text-gray-500">
                  {hierarchy.type} • {hierarchy.levels.length} levels
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    )
  }

  const renderControls = () => {
    if (!showControls || !state.currentHierarchy) return null

    return (
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <button
            onClick={handleDrillUp}
            disabled={!state.canDrillUp || state.isLoading}
            className={`
              flex items-center px-3 py-1 rounded-md text-sm font-medium transition-colors
              ${state.canDrillUp && !state.isLoading
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
            disabled={state.currentLevel === 1 || state.isLoading}
            className={`
              flex items-center px-3 py-1 rounded-md text-sm font-medium transition-colors
              ${state.currentLevel > 1 && !state.isLoading
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

  const renderChart = () => {
    if (state.isLoading) {
      return (
        <div className="h-64 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )
    }

    if (!state.data || state.data.length === 0) {
      return (
        <div className="h-64 flex items-center justify-center text-gray-500">
          No data available for this level
        </div>
      )
    }

    // This would integrate with your existing chart components
    return (
      <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600 mb-2">
            {state.currentHierarchy?.type.toUpperCase()} Chart
          </p>
          <p className="text-sm text-gray-500">
            {state.data.length} data points
          </p>
          {state.canDrillDown && (
            <p className="text-xs text-blue-600 mt-2">
              Click on any element to drill down
            </p>
          )}
        </div>
      </div>
    )
  }

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
            Dynamic Drill-Down Chart
          </h3>
          {state.currentHierarchy && (
            <p className={`text-sm ${
              isNormal ? 'text-gray-600' : 'text-slate-400'
            }`}>
              {state.currentHierarchy.name} • Level {state.currentLevel}
            </p>
          )}
        </div>
        
        <div className="flex items-center space-x-2 text-sm">
          <span className={`
            px-2 py-1 rounded-full text-xs font-medium
            ${state.canDrillDown
              ? 'bg-green-100 text-green-800'
              : 'bg-gray-100 text-gray-600'
            }
          `}>
            {state.canDrillDown ? 'Drillable' : 'Max Depth'}
          </span>
        </div>
      </div>

      {/* Hierarchy Selector */}
      {renderHierarchySelector()}

      {/* Breadcrumb */}
      {renderBreadcrumb()}

      {/* Controls */}
      {renderControls()}

      {/* Chart */}
      <div className="relative">
        {renderChart()}
        
        {/* Loading overlay */}
        {state.isLoading && (
          <div className="absolute inset-0 bg-white/80 flex items-center justify-center rounded-lg">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          </div>
        )}
      </div>

      {/* Chart Info */}
      <div className="mt-4 pt-3 border-t border-gray-200">
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>
            {state.data.length} records
            {state.currentPath.length > 0 && ` • Level ${state.currentLevel}`}
          </span>
          <span>
            {state.currentHierarchy?.type} • {state.availableHierarchies.length} hierarchies available
          </span>
        </div>
      </div>
    </div>
  )
}

export default DynamicDrillDownChart

