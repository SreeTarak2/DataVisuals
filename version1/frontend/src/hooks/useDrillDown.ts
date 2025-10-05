import { useState, useCallback } from 'react'
import axios from 'axios'
import toast from 'react-hot-toast'

interface DrillDownState {
  currentPath: string[]
  currentLevel: number
  data: any[]
  isLoading: boolean
  canDrillDown: boolean
  canDrillUp: boolean
}

interface HierarchyLevel {
  level: number
  name: string
  field: string
  parent?: string
  children?: HierarchyLevel[]
  chartType: 'bar' | 'pie' | 'line' | 'scatter'
}

interface UseDrillDownProps {
  datasetId: string
  initialData: any[]
  hierarchies: HierarchyLevel[]
  onDataChange?: (data: any[]) => void
}

export const useDrillDown = ({ 
  datasetId, 
  initialData, 
  hierarchies, 
  onDataChange 
}: UseDrillDownProps) => {
  const [state, setState] = useState<DrillDownState>({
    currentPath: [],
    currentLevel: 0,
    data: initialData,
    isLoading: false,
    canDrillDown: hierarchies.length > 0,
    canDrillUp: false
  })

  // Drill down to next level
  const drillDown = useCallback(async (clickedValue: string) => {
    if (state.isLoading || !state.canDrillDown) return

    const nextLevel = state.currentLevel + 1
    const hierarchy = hierarchies.find(h => h.level === nextLevel)
    
    if (!hierarchy) {
      toast.error('No more levels to drill down')
      return
    }

    setState(prev => ({ ...prev, isLoading: true }))

    try {
      // Build filter object for current drill-down path
      const filters: Record<string, any> = {}
      state.currentPath.forEach((value, index) => {
        const parentHierarchy = hierarchies.find(h => h.level === index + 1)
        if (parentHierarchy?.parent) {
          filters[parentHierarchy.parent] = value
        }
      })
      
      // Add current clicked value
      if (hierarchy.parent) {
        filters[hierarchy.parent] = clickedValue
      }

      const response = await axios.post('/api/drilldown', {
        datasetId,
        hierarchy: hierarchy.field,
        filters,
        level: nextLevel,
        path: [...state.currentPath, clickedValue]
      })

      const newData = response.data.data || []
      const newPath = [...state.currentPath, clickedValue]

      setState(prev => ({
        ...prev,
        currentPath: newPath,
        currentLevel: nextLevel,
        data: newData,
        isLoading: false,
        canDrillDown: nextLevel < hierarchies.length - 1,
        canDrillUp: true
      }))

      onDataChange?.(newData)
      toast.success(`Drilled down to ${clickedValue}`)

    } catch (error) {
      console.error('Drill-down failed:', error)
      toast.error('Failed to drill down')
      setState(prev => ({ ...prev, isLoading: false }))
    }
  }, [datasetId, state.currentPath, state.currentLevel, hierarchies, onDataChange])

  // Drill up to previous level
  const drillUp = useCallback(async () => {
    if (state.isLoading || !state.canDrillUp) return

    const prevLevel = state.currentLevel - 1
    const newPath = state.currentPath.slice(0, -1)

    setState(prev => ({ ...prev, isLoading: true }))

    try {
      // Build filter object for previous level
      const filters: Record<string, any> = {}
      newPath.forEach((value, index) => {
        const parentHierarchy = hierarchies.find(h => h.level === index + 1)
        if (parentHierarchy?.parent) {
          filters[parentHierarchy.parent] = value
        }
      })

      const response = await axios.post('/api/drilldown', {
        datasetId,
        hierarchy: hierarchies.find(h => h.level === prevLevel)?.field,
        filters,
        level: prevLevel,
        path: newPath
      })

      const newData = response.data.data || []

      setState(prev => ({
        ...prev,
        currentPath: newPath,
        currentLevel: prevLevel,
        data: newData,
        isLoading: false,
        canDrillDown: prevLevel < hierarchies.length - 1,
        canDrillUp: newPath.length > 0
      }))

      onDataChange?.(newData)
      toast.success('Drilled up to previous level')

    } catch (error) {
      console.error('Drill-up failed:', error)
      toast.error('Failed to drill up')
      setState(prev => ({ ...prev, isLoading: false }))
    }
  }, [datasetId, state.currentPath, state.currentLevel, hierarchies, onDataChange])

  // Reset to initial state
  const reset = useCallback(() => {
    setState(prev => ({
      ...prev,
      currentPath: [],
      currentLevel: 0,
      data: initialData,
      canDrillDown: hierarchies.length > 0,
      canDrillUp: false
    }))
    onDataChange?.(initialData)
  }, [initialData, hierarchies, onDataChange])

  // Get breadcrumb trail
  const getBreadcrumbTrail = useCallback(() => {
    return state.currentPath.map((value, index) => ({
      label: value,
      level: index + 1,
      hierarchy: hierarchies.find(h => h.level === index + 1)
    }))
  }, [state.currentPath, hierarchies])

  // Get current hierarchy info
  const getCurrentHierarchy = useCallback(() => {
    return hierarchies.find(h => h.level === state.currentLevel)
  }, [hierarchies, state.currentLevel])

  return {
    ...state,
    drillDown,
    drillUp,
    reset,
    getBreadcrumbTrail,
    getCurrentHierarchy
  }
}


