import React, { useState, useEffect } from 'react'
import { 
  BarChart3, 
  TrendingUp, 
  PieChart, 
  Activity,
  Target,
  Zap,
  Filter,
  Download,
  Share2,
  Settings,
  Eye,
  ChevronDown,
  ChevronUp
} from 'lucide-react'
import { usePersona } from '../contexts/PersonaContext'
import axios from 'axios'
import toast from 'react-hot-toast'

interface DashboardCard {
  id: string
  type: 'kpi' | 'chart' | 'insight'
  title: string
  data: any
  position: { x: number; y: number; w: number; h: number }
  chartType?: string
  filters?: string[]
  drillDownPath?: string[]
}

interface HierarchyLevel {
  level: number
  name: string
  field: string
  parent?: string
  children?: HierarchyLevel[]
}

const AdaptiveDashboard: React.FC = () => {
  const { persona, isNormal } = usePersona()
  const [dashboardCards, setDashboardCards] = useState<DashboardCard[]>([])
  const [selectedDataset, setSelectedDataset] = useState<any>(null)
  const [hierarchies, setHierarchies] = useState<HierarchyLevel[]>([])
  const [activeFilters, setActiveFilters] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(false)
  const [isEditMode, setIsEditMode] = useState(false)

  // SQLBI Principle 1: Clarity > Complexity
  const getCardSize = (dataLength: number) => {
    if (dataLength <= 5) return { w: 3, h: 2 }
    if (dataLength <= 10) return { w: 4, h: 3 }
    return { w: 6, h: 4 }
  }

  // SQLBI Principle 2: Highlight What Matters
  const getHighlightColor = (value: number, threshold: number) => {
    if (value > threshold * 1.2) return 'text-green-600'
    if (value < threshold * 0.8) return 'text-red-600'
    return 'text-gray-600'
  }

  // SQLBI Principle 3: Avoid Data Overload
  const limitDataForDisplay = (data: any[], maxItems: number = 10) => {
    return data.slice(0, maxItems)
  }

  // SQLBI Principle 4: Consistent Layout
  const gridLayout = {
    cols: 12,
    rowHeight: 60,
    margin: [10, 10]
  }

  // SQLBI Principle 5: Right Chart for Right Data
  const getOptimalChartType = (data: any[], field: string) => {
    const uniqueValues = new Set(data.map(item => item[field]))
    const isNumeric = data.every(item => typeof item[field] === 'number')
    
    if (uniqueValues.size <= 5) return 'pie_chart'
    if (isNumeric && data.length > 20) return 'histogram'
    if (isNumeric) return 'bar_chart'
    return 'bar_chart'
  }

  // SQLBI Principle 6: Balance Text & Graphics
  const KPICard: React.FC<{ card: DashboardCard }> = ({ card }) => {
    const value = card.data.value || 0
    const change = card.data.change || 0
    const threshold = card.data.threshold || 1000

    return (
      <div className={`
        p-4 rounded-lg border-2 transition-all
        ${isNormal 
          ? 'bg-white border-gray-200 hover:border-blue-300' 
          : 'backdrop-blur-xl bg-white/10 border-white/20 hover:border-cyan-300'
        }
      `}>
        <div className="flex items-center justify-between mb-2">
          <h3 className={`font-medium ${
            isNormal ? 'text-gray-900' : 'text-white'
          }`}>
            {card.title}
          </h3>
          <Activity className={`h-4 w-4 ${
            isNormal ? 'text-gray-400' : 'text-slate-400'
          }`} />
        </div>
        
        <div className="space-y-1">
          <p className={`text-2xl font-bold ${
            getHighlightColor(value, threshold)
          }`}>
            {value.toLocaleString()}
          </p>
          <p className={`text-sm flex items-center ${
            change >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            <TrendingUp className={`h-3 w-3 mr-1 ${
              change >= 0 ? 'rotate-0' : 'rotate-180'
            }`} />
            {Math.abs(change)}% vs last period
          </p>
        </div>
      </div>
    )
  }

  // SQLBI Principle 7: Logical Grouping
  const ChartCard: React.FC<{ card: DashboardCard }> = ({ card }) => {
    const [drillDownPath, setDrillDownPath] = useState<string[]>(card.drillDownPath || [])
    const [chartData, setChartData] = useState(card.data)

    // SQLBI Principle 10: Drill Down, Don't Drill Through
    const handleDrillDown = async (clickedValue: string) => {
      if (!selectedDataset) return

      setLoading(true)
      try {
        const newPath = [...drillDownPath, clickedValue]
        setDrillDownPath(newPath)

        // Find next hierarchy level
        const currentLevel = hierarchies.find(h => h.level === newPath.length)
        if (!currentLevel) return

        // Call backend for drill-down data
        const response = await axios.post('/api/drilldown', {
          datasetId: selectedDataset.id,
          hierarchy: currentLevel.field,
          filters: { ...activeFilters, [currentLevel.parent || '']: clickedValue },
          level: newPath.length
        })

        setChartData(response.data)
        toast.success(`Drilled down to ${clickedValue}`)
      } catch (error) {
        console.error('Drill-down failed:', error)
        toast.error('Failed to drill down')
      } finally {
        setLoading(false)
      }
    }

    const handleDrillUp = () => {
      if (drillDownPath.length === 0) return
      
      const newPath = drillDownPath.slice(0, -1)
      setDrillDownPath(newPath)
      
      // Reload data for previous level
      // Implementation would reload data based on newPath
    }

    return (
      <div className={`
        p-4 rounded-lg border-2 transition-all
        ${isNormal 
          ? 'bg-white border-gray-200 hover:border-blue-300' 
          : 'backdrop-blur-xl bg-white/10 border-white/20 hover:border-cyan-300'
        }
      `}>
        {/* Breadcrumb Navigation */}
        {drillDownPath.length > 0 && (
          <div className="flex items-center space-x-1 mb-3 text-sm">
            <button
              onClick={handleDrillUp}
              className="text-blue-600 hover:text-blue-800 flex items-center"
            >
              <ChevronUp className="h-3 w-3 mr-1" />
              Back
            </button>
            <span className="text-gray-400">|</span>
            {drillDownPath.map((level, index) => (
              <span key={index} className="text-gray-600">
                {level} {index < drillDownPath.length - 1 && '>'}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between mb-4">
          <h3 className={`font-medium ${
            isNormal ? 'text-gray-900' : 'text-white'
          }`}>
            {card.title}
          </h3>
          <div className="flex items-center space-x-2">
            <Filter className={`h-4 w-4 ${
              isNormal ? 'text-gray-400' : 'text-slate-400'
            }`} />
            <Settings className={`h-4 w-4 ${
              isNormal ? 'text-gray-400' : 'text-slate-400'
            }`} />
          </div>
        </div>

        {/* Chart Content */}
        <div className="h-48">
          {/* This would render the actual chart component */}
          <div className="w-full h-full bg-gray-100 rounded flex items-center justify-center">
            <p className="text-gray-500">Chart: {card.chartType}</p>
          </div>
        </div>

        {/* Chart Actions */}
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
          <div className="flex items-center space-x-2">
            <button className="text-blue-600 hover:text-blue-800 text-sm">
              <Download className="h-3 w-3 mr-1" />
              Export
            </button>
            <button className="text-blue-600 hover:text-blue-800 text-sm">
              <Share2 className="h-3 w-3 mr-1" />
              Share
            </button>
          </div>
          <button className="text-gray-400 hover:text-gray-600 text-sm">
            <Eye className="h-3 w-3" />
          </button>
        </div>
      </div>
    )
  }

  // SQLBI Principle 8: Scannability
  const renderDashboard = () => {
    return (
      <div className="grid grid-cols-12 gap-4">
        {/* Top Row: KPIs (SQLBI Principle 8) */}
        <div className="col-span-12 grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {dashboardCards
            .filter(card => card.type === 'kpi')
            .map(card => (
              <div key={card.id} className="col-span-1">
                <KPICard card={card} />
              </div>
            ))}
        </div>

        {/* Middle Row: Main Charts */}
        <div className="col-span-12 grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {dashboardCards
            .filter(card => card.type === 'chart')
            .map(card => (
              <div 
                key={card.id} 
                className={`col-span-${card.position.w}`}
                style={{ gridColumn: `span ${card.position.w}` }}
              >
                <ChartCard card={card} />
              </div>
            ))}
        </div>

        {/* Bottom Row: Details & Insights */}
        <div className="col-span-12 grid grid-cols-1 lg:grid-cols-2 gap-4">
          {dashboardCards
            .filter(card => card.type === 'insight')
            .map(card => (
              <div key={card.id} className="col-span-1">
                <ChartCard card={card} />
              </div>
            ))}
        </div>
      </div>
    )
  }

  // SQLBI Principle 11: Fast Rendering
  const loadDashboardData = async (dataset: any) => {
    setLoading(true)
    try {
      // Load KPIs
      const kpiResponse = await axios.get(`/api/datasets/${dataset.id}/kpis`)
      
      // Load chart suggestions
      const chartsResponse = await axios.get(`/api/datasets/${dataset.id}/charts`)
      
      // Load hierarchies
      const hierarchiesResponse = await axios.get(`/api/datasets/${dataset.id}/hierarchies`)

      setDashboardCards([
        ...kpiResponse.data.map((kpi: any, index: number) => ({
          id: `kpi-${index}`,
          type: 'kpi' as const,
          title: kpi.title,
          data: kpi.data,
          position: { x: index * 3, y: 0, w: 3, h: 2 }
        })),
        ...chartsResponse.data.map((chart: any, index: number) => ({
          id: `chart-${index}`,
          type: 'chart' as const,
          title: chart.title,
          data: chart.data,
          chartType: chart.type,
          position: { x: (index % 3) * 4, y: 2, w: 4, h: 3 },
          drillDownPath: []
        }))
      ])

      setHierarchies(hierarchiesResponse.data)
      setSelectedDataset(dataset)
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
      toast.error('Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`min-h-screen ${
      isNormal ? 'bg-gray-50' : 'bg-gradient-to-br from-slate-900 via-indigo-900 to-slate-900'
    }`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className={`
          rounded-lg shadow-sm border p-6 mb-8
          ${isNormal 
            ? 'bg-white border-gray-200' 
            : 'backdrop-blur-xl bg-white/10 border-white/20'
          }
        `}>
          <div className="flex items-center justify-between">
            <div>
              <h1 className={`text-2xl font-semibold ${
                isNormal ? 'text-gray-900' : 'text-white'
              }`}>
                {isNormal ? 'Smart Dashboard' : 'AI-Powered Analytics Dashboard'}
              </h1>
              <p className={`mt-1 text-sm ${
                isNormal ? 'text-gray-600' : 'text-slate-400'
              }`}>
                {isNormal 
                  ? 'Your data, intelligently visualized'
                  : 'Adaptive dashboard with AI-driven insights and drill-down capabilities'
                }
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setIsEditMode(!isEditMode)}
                className={`
                  px-4 py-2 rounded-md text-sm font-medium transition-colors
                  ${isEditMode
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }
                `}
              >
                {isEditMode ? 'Exit Edit' : 'Edit Layout'}
              </button>
              <button className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700">
                <Share2 className="h-4 w-4 mr-2" />
                Share Dashboard
              </button>
            </div>
          </div>
        </div>

        {/* Dashboard Content */}
        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-gray-600">Loading dashboard...</p>
          </div>
        ) : (
          renderDashboard()
        )}
      </div>
    </div>
  )
}

export default AdaptiveDashboard


