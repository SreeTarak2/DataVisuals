import React, { useState, useEffect } from 'react'
import { 
  Plus, 
  Trash2, 
  Move, 
  Settings, 
  Save, 
  Share2, 
  Download,
  Eye,
  Filter,
  BarChart3,
  PieChart,
  TrendingUp,
  Scatter
} from 'lucide-react'
import { usePersona } from '../contexts/PersonaContext'
import DrillDownChart from './DrillDownChart'
import toast from 'react-hot-toast'

interface DashboardCard {
  id: string
  type: 'kpi' | 'chart' | 'insight'
  title: string
  chartType?: 'bar' | 'pie' | 'line' | 'scatter'
  data: any[]
  fields: string[]
  position: { x: number; y: number; w: number; h: number }
  filters?: Record<string, any>
  drillDownPath?: string[]
}

interface DashboardBuilderProps {
  datasetId: string
  initialCards?: DashboardCard[]
  onSave?: (cards: DashboardCard[]) => void
  onShare?: (dashboardId: string) => void
}

const DashboardBuilder: React.FC<DashboardBuilderProps> = ({
  datasetId,
  initialCards = [],
  onSave,
  onShare
}) => {
  const { isNormal } = usePersona()
  const [cards, setCards] = useState<DashboardCard[]>(initialCards)
  const [isEditMode, setIsEditMode] = useState(false)
  const [selectedCard, setSelectedCard] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const [hierarchies, setHierarchies] = useState<any[]>([])

  // Load hierarchies on mount
  useEffect(() => {
    loadHierarchies()
  }, [datasetId])

  const loadHierarchies = async () => {
    try {
      const response = await fetch(`/api/datasets/${datasetId}/hierarchies`)
      const data = await response.json()
      setHierarchies(data.hierarchies || [])
    } catch (error) {
      console.error('Failed to load hierarchies:', error)
    }
  }

  // Add new card
  const addCard = (type: 'kpi' | 'chart' | 'insight', chartType?: 'bar' | 'pie' | 'line' | 'scatter') => {
    const newCard: DashboardCard = {
      id: `card-${Date.now()}`,
      type,
      title: `${type.charAt(0).toUpperCase() + type.slice(1)} ${cards.length + 1}`,
      chartType,
      data: [],
      fields: ['name', 'value'],
      position: { x: 0, y: 0, w: 4, h: 3 }
    }
    
    setCards(prev => [...prev, newCard])
    setSelectedCard(newCard.id)
    toast.success(`${type} card added`)
  }

  // Remove card
  const removeCard = (cardId: string) => {
    setCards(prev => prev.filter(card => card.id !== cardId))
    if (selectedCard === cardId) {
      setSelectedCard(null)
    }
    toast.success('Card removed')
  }

  // Update card position
  const updateCardPosition = (cardId: string, position: { x: number; y: number; w: number; h: number }) => {
    setCards(prev => prev.map(card => 
      card.id === cardId ? { ...card, position } : card
    ))
  }

  // Update card data
  const updateCardData = (cardId: string, data: any) => {
    setCards(prev => prev.map(card => 
      card.id === cardId ? { ...card, ...data } : card
    ))
  }

  // Save dashboard
  const saveDashboard = async () => {
    try {
      // This would save to backend
      onSave?.(cards)
      toast.success('Dashboard saved successfully')
    } catch (error) {
      console.error('Failed to save dashboard:', error)
      toast.error('Failed to save dashboard')
    }
  }

  // Share dashboard
  const shareDashboard = async () => {
    try {
      // This would generate shareable link
      const dashboardId = `dashboard-${Date.now()}`
      onShare?.(dashboardId)
      toast.success('Dashboard shared successfully')
    } catch (error) {
      console.error('Failed to share dashboard:', error)
      toast.error('Failed to share dashboard')
    }
  }

  // Render card based on type
  const renderCard = (card: DashboardCard) => {
    const isSelected = selectedCard === card.id
    const isDragging = isDragging && selectedCard === card.id

    return (
      <div
        key={card.id}
        className={`
          absolute rounded-lg border-2 transition-all cursor-move
          ${isSelected
            ? 'border-blue-500 shadow-lg'
            : 'border-gray-200 hover:border-gray-300'
          }
          ${isDragging ? 'opacity-50' : ''}
          ${isEditMode ? 'hover:shadow-md' : ''}
        `}
        style={{
          left: card.position.x * 60,
          top: card.position.y * 60,
          width: card.position.w * 60,
          height: card.position.h * 60,
          zIndex: isSelected ? 10 : 1
        }}
        onClick={() => setSelectedCard(card.id)}
      >
        {/* Card Header */}
        <div className="flex items-center justify-between p-3 border-b border-gray-200">
          <h4 className="font-medium text-gray-900 truncate">{card.title}</h4>
          {isEditMode && (
            <div className="flex items-center space-x-1">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  removeCard(card.id)
                }}
                className="p-1 text-red-500 hover:text-red-700"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* Card Content */}
        <div className="p-3 h-full">
          {card.type === 'kpi' ? (
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">1,234</div>
              <div className="text-sm text-gray-500">Total Sales</div>
              <div className="text-xs text-green-600">+12.5%</div>
            </div>
          ) : card.type === 'chart' ? (
            <DrillDownChart
              datasetId={datasetId}
              initialData={card.data}
              hierarchies={hierarchies}
              chartType={card.chartType || 'bar'}
              title={card.title}
              fields={card.fields}
              showControls={false}
            />
          ) : (
            <div className="text-center text-gray-500">
              <Eye className="h-8 w-8 mx-auto mb-2" />
              <p className="text-sm">Insight Card</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Render add card menu
  const renderAddCardMenu = () => {
    if (!isEditMode) return null

    return (
      <div className="fixed top-4 right-4 z-50">
        <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-4">
          <h3 className="font-medium text-gray-900 mb-3">Add Card</h3>
          <div className="space-y-2">
            <button
              onClick={() => addCard('kpi')}
              className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
            >
              <BarChart3 className="h-4 w-4" />
              <span>KPI Card</span>
            </button>
            <button
              onClick={() => addCard('chart', 'bar')}
              className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
            >
              <BarChart3 className="h-4 w-4" />
              <span>Bar Chart</span>
            </button>
            <button
              onClick={() => addCard('chart', 'pie')}
              className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
            >
              <PieChart className="h-4 w-4" />
              <span>Pie Chart</span>
            </button>
            <button
              onClick={() => addCard('chart', 'line')}
              className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
            >
              <TrendingUp className="h-4 w-4" />
              <span>Line Chart</span>
            </button>
            <button
              onClick={() => addCard('chart', 'scatter')}
              className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
            >
              <Scatter className="h-4 w-4" />
              <span>Scatter Plot</span>
            </button>
            <button
              onClick={() => addCard('insight')}
              className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
            >
              <Eye className="h-4 w-4" />
              <span>Insight Card</span>
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen ${
      isNormal ? 'bg-gray-50' : 'bg-gradient-to-br from-slate-900 via-indigo-900 to-slate-900'
    }`}>
      {/* Header */}
      <div className={`
        sticky top-0 z-40 border-b p-4
        ${isNormal 
          ? 'bg-white border-gray-200' 
          : 'backdrop-blur-xl bg-white/10 border-white/20'
        }
      `}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className={`text-xl font-semibold ${
              isNormal ? 'text-gray-900' : 'text-white'
            }`}>
              Dashboard Builder
            </h1>
            <p className={`text-sm ${
              isNormal ? 'text-gray-600' : 'text-slate-400'
            }`}>
              {cards.length} cards • {isEditMode ? 'Edit Mode' : 'View Mode'}
            </p>
          </div>
          
          <div className="flex items-center space-x-2">
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
            
            <button
              onClick={saveDashboard}
              className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700"
            >
              <Save className="h-4 w-4 mr-2" />
              Save
            </button>
            
            <button
              onClick={shareDashboard}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
            >
              <Share2 className="h-4 w-4 mr-2" />
              Share
            </button>
          </div>
        </div>
      </div>

      {/* Dashboard Canvas */}
      <div className="relative p-4">
        <div className="relative min-h-screen">
          {cards.map(renderCard)}
          
          {/* Grid overlay for edit mode */}
          {isEditMode && (
            <div className="absolute inset-0 pointer-events-none">
              <div className="grid grid-cols-12 gap-4 h-full">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className="border border-gray-200 border-dashed opacity-30"></div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add Card Menu */}
      {renderAddCardMenu()}

      {/* Empty State */}
      {cards.length === 0 && (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <BarChart3 className="h-12 w-12 mx-auto mb-4 text-gray-400" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No cards yet</h3>
            <p className="text-gray-500 mb-4">Start building your dashboard by adding cards</p>
            <button
              onClick={() => setIsEditMode(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Your First Card
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default DashboardBuilder


