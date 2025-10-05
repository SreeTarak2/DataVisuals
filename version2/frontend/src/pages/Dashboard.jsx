import React, { useState, useEffect } from 'react'
import { Database, Upload, BarChart3, TrendingUp, Lightbulb, Loader2, ChevronDown, MessageSquare } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import toast from 'react-hot-toast'
import PlotlyChart from '../components/PlotlyChart'
import UploadModal from '../components/UploadModal'

const Dashboard = () => {
  const [selectedDataset, setSelectedDataset] = useState(null)
  const [datasets, setDatasets] = useState([])
  const [loading, setLoading] = useState(true)
  const [chartLoading, setChartLoading] = useState(false)
  const [aiInsights, setAiInsights] = useState([])
  const [dataInsights, setDataInsights] = useState({})
  const [mainChart, setMainChart] = useState(null)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const { user } = useAuth()

  // Load datasets on mount
  useEffect(() => {
    loadDatasets()
  }, [])

  // Load dashboard data when dataset changes
  useEffect(() => {
    if (selectedDataset) {
      loadDashboardData(selectedDataset)
    }
  }, [selectedDataset])

  const loadDatasets = async () => {
    try {
      setLoading(true)
      const response = await axios.get('/api/datasets')
      const datasetsData = response.data.datasets || []
      setDatasets(datasetsData)
      
      // Set first dataset as default if available
      if (datasetsData.length > 0) {
        setSelectedDataset(datasetsData[0])
      }
    } catch (error) {
      console.error('Error loading datasets:', error)
      toast.error('Failed to load datasets')
    } finally {
      setLoading(false)
    }
  }

  const loadDashboardData = async (dataset) => {
    try {
      setChartLoading(true)
      
      // Generate AI chart
      await generateAIChart(dataset)
      
      // Calculate data insights
      calculateDataInsights(dataset)
      
      // Generate AI insights
      await generateAIInsights(dataset)
      
    } catch (error) {
      console.error('Error loading dashboard data:', error)
      toast.error('Failed to load dashboard data')
    } finally {
      setChartLoading(false)
    }
  }

  const generateAIChart = async (dataset) => {
    // This will call your LLM to analyze and generate the best chart
    try {
      const response = await axios.post('/api/ai/generate-chart', {
        dataset_id: dataset.id,
        columns: dataset.columns,
        data_sample: dataset.preview_data
      })
      
      setMainChart(response.data)
    } catch (error) {
      console.error('Error generating AI chart:', error)
    }
  }

  const calculateDataInsights = (dataset) => {
    // Calculate real statistical insights from the data
    const insights = {
      totalRecords: dataset.row_count || 0,
      totalColumns: dataset.column_count || 0,
      missingData: calculateMissingData(dataset),
      dataRange: calculateDataRange(dataset),
      uniqueValues: calculateUniqueValues(dataset),
      dataFreshness: calculateDataFreshness(dataset)
    }
    
    setDataInsights(insights)
  }

  const generateAIInsights = async (dataset) => {
    // This will call your LLM to generate QUIS insights
    try {
      const response = await axios.post('/api/ai/generate-insights', {
        dataset_metadata: dataset.metadata || {},
        dataset_name: dataset.name || 'Unknown Dataset'
      })
      
      // Handle new QUIS format
      if (response.data.insight_cards) {
        setAiInsights(response.data.insight_cards)
      } else {
        // Fallback for old format
        setAiInsights(response.data.insights || [])
      }
    } catch (error) {
      console.error('Error generating AI insights:', error)
    }
  }

  // Helper functions for data insights
  const calculateMissingData = (dataset) => {
    // Calculate percentage of missing data
    const totalCells = (dataset.row_count || 0) * (dataset.column_count || 0)
    const missingCells = dataset.metadata?.dataset_overview?.missing_values || 0
    return totalCells > 0 ? Math.round((missingCells / totalCells) * 100) : 0
  }

  const calculateDataRange = (dataset) => {
    // Calculate min/max values for numeric columns
    const numericCols = dataset.metadata?.column_metadata?.filter(col => 
      col.type === 'int64' || col.type === 'float64'
    ) || []
    
    if (numericCols.length === 0) return { min: 0, max: 0 }
    
    // This would be calculated from actual data
    return { min: 0, max: 100 } // Placeholder
  }

  const calculateUniqueValues = (dataset) => {
    // Calculate average unique values across columns
    const columns = dataset.metadata?.column_metadata || []
    if (columns.length === 0) return 0
    
    const totalUnique = columns.reduce((sum, col) => sum + (col.unique_count || 0), 0)
    return Math.round(totalUnique / columns.length)
  }

  const calculateDataFreshness = (dataset) => {
    // Calculate days since upload
    const uploadDate = new Date(dataset.uploaded_at)
    const now = new Date()
    const diffTime = Math.abs(now - uploadDate)
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    return diffDays
  }

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  // Statistical calculation functions
  const calculateMean = (dataset) => {
    if (!dataset.preview_data || dataset.preview_data.length === 0) return null
    
    const numericValues = []
    dataset.preview_data.forEach(row => {
      Object.values(row).forEach(value => {
        if (typeof value === 'number' && !isNaN(value)) {
          numericValues.push(value)
        }
      })
    })
    
    if (numericValues.length === 0) return null
    const sum = numericValues.reduce((acc, val) => acc + val, 0)
    return (sum / numericValues.length).toFixed(2)
  }

  const calculateMedian = (dataset) => {
    if (!dataset.preview_data || dataset.preview_data.length === 0) return null
    
    const numericValues = []
    dataset.preview_data.forEach(row => {
      Object.values(row).forEach(value => {
        if (typeof value === 'number' && !isNaN(value)) {
          numericValues.push(value)
        }
      })
    })
    
    if (numericValues.length === 0) return null
    
    numericValues.sort((a, b) => a - b)
    const mid = Math.floor(numericValues.length / 2)
    
    if (numericValues.length % 2 === 0) {
      return ((numericValues[mid - 1] + numericValues[mid]) / 2).toFixed(2)
    } else {
      return numericValues[mid].toFixed(2)
    }
  }

  const calculateStdDev = (dataset) => {
    if (!dataset.preview_data || dataset.preview_data.length === 0) return null
    
    const numericValues = []
    dataset.preview_data.forEach(row => {
      Object.values(row).forEach(value => {
        if (typeof value === 'number' && !isNaN(value)) {
          numericValues.push(value)
        }
      })
    })
    
    if (numericValues.length === 0) return null
    
    const mean = numericValues.reduce((acc, val) => acc + val, 0) / numericValues.length
    const variance = numericValues.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / numericValues.length
    return Math.sqrt(variance).toFixed(2)
  }

  const calculateRange = (dataset) => {
    if (!dataset.preview_data || dataset.preview_data.length === 0) return null
    
    const numericValues = []
    dataset.preview_data.forEach(row => {
      Object.values(row).forEach(value => {
        if (typeof value === 'number' && !isNaN(value)) {
          numericValues.push(value)
        }
      })
    })
    
    if (numericValues.length === 0) return null
    
    const min = Math.min(...numericValues)
    const max = Math.max(...numericValues)
    return `${min.toFixed(2)} - ${max.toFixed(2)}`
  }

  const calculateMin = (dataset) => {
    if (!dataset.preview_data || dataset.preview_data.length === 0) return null
    
    const numericValues = []
    dataset.preview_data.forEach(row => {
      Object.values(row).forEach(value => {
        if (typeof value === 'number' && !isNaN(value)) {
          numericValues.push(value)
        }
      })
    })
    
    if (numericValues.length === 0) return null
    return Math.min(...numericValues).toFixed(2)
  }

  const calculateMax = (dataset) => {
    if (!dataset.preview_data || dataset.preview_data.length === 0) return null
    
    const numericValues = []
    dataset.preview_data.forEach(row => {
      Object.values(row).forEach(value => {
        if (typeof value === 'number' && !isNaN(value)) {
          numericValues.push(value)
        }
      })
    })
    
    if (numericValues.length === 0) return null
    return Math.max(...numericValues).toFixed(2)
  }

  const calculateSum = (dataset) => {
    if (!dataset.preview_data || dataset.preview_data.length === 0) return null
    
    const numericValues = []
    dataset.preview_data.forEach(row => {
      Object.values(row).forEach(value => {
        if (typeof value === 'number' && !isNaN(value)) {
          numericValues.push(value)
        }
      })
    })
    
    if (numericValues.length === 0) return null
    return numericValues.reduce((acc, val) => acc + val, 0).toFixed(2)
  }

  const calculateCount = (dataset) => {
    if (!dataset.preview_data || dataset.preview_data.length === 0) return 0
    
    let count = 0
    dataset.preview_data.forEach(row => {
      Object.values(row).forEach(value => {
        if (typeof value === 'number' && !isNaN(value)) {
          count++
        }
      })
    })
    
    return count
  }

  // Chart explanation functions
  const getChartExplanation = (chartType, dataset) => {
    const numericCols = dataset?.metadata?.column_metadata?.filter(col => 
      col.type === 'int64' || col.type === 'float64'
    ) || []
    const categoricalCols = dataset?.metadata?.column_metadata?.filter(col => 
      col.type === 'object' || col.type === 'category'
    ) || []

    switch (chartType) {
      case 'scatter':
        return `AI detected ${numericCols.length} numeric columns and created a scatter plot to reveal correlations between variables. This helps identify relationships and patterns in your data.`
      case 'bar':
        return `AI found ${categoricalCols.length} categorical columns and created a bar chart to show the distribution of categories. This reveals the most common values and frequency patterns.`
      case 'pie':
        return `AI detected a categorical column with few unique values and created a pie chart to show proportional relationships. This helps visualize parts of a whole.`
      default:
        return `AI analyzed your data structure and selected the most appropriate visualization to reveal key insights and patterns.`
    }
  }

  const getChartTypeDescription = (chartType) => {
    switch (chartType) {
      case 'scatter':
        return 'Scatter plots show the relationship between two numerical variables. Each point represents one data record.'
      case 'bar':
        return 'Bar charts display categorical data with rectangular bars. The height of each bar represents the count or frequency.'
      case 'pie':
        return 'Pie charts show proportional data as slices of a circle. Each slice represents a category\'s percentage of the total.'
      default:
        return 'This chart type is optimized for your specific data structure and analysis needs.'
    }
  }

  const getChartUseCase = (chartType) => {
    switch (chartType) {
      case 'scatter':
        return 'Perfect for finding correlations, identifying outliers, and detecting trends between two variables.'
      case 'bar':
        return 'Ideal for comparing categories, showing rankings, and displaying frequency distributions.'
      case 'pie':
        return 'Best for showing proportions, market share, and percentage breakdowns of categorical data.'
      default:
        return 'Optimized for your specific data analysis requirements.'
    }
  }


  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-gray-900 to-slate-800">
      <div className="space-y-6 p-6">
        <style jsx>{`
          .glow-text {
            text-shadow: 0 0 10px rgba(255, 255, 255, 0.3), 0 0 20px rgba(255, 255, 255, 0.2);
          }
          .glow-text:hover {
            text-shadow: 0 0 15px rgba(255, 255, 255, 0.4), 0 0 25px rgba(255, 255, 255, 0.3);
          }
        `}</style>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white glow-text">Dashboard</h1>
            <p className="text-slate-300 mt-1">
              Welcome back{user?.full_name ? `, ${user.full_name}` : ''}! AI-powered insights and visualizations
            </p>
          </div>
        
        {/* Dataset Selector and Upload Button */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-3">
            <label className="text-sm font-medium text-slate-300">Select Dataset:</label>
            <div className="relative">
              <select
                value={selectedDataset?.id || ''}
                onChange={(e) => {
                  const dataset = datasets.find(d => d.id === e.target.value)
                  setSelectedDataset(dataset)
                }}
                className="appearance-none bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 pr-8 focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-white"
              >
                {datasets.map(dataset => (
                  <option key={dataset.id} value={dataset.id} className="bg-slate-800 text-white">
                    {dataset.name || 'Unnamed Dataset'}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            </div>
          </div>
          <button 
            onClick={() => setShowUploadModal(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
          >
            <Upload className="w-4 h-4" />
            <span>Upload</span>
          </button>
          <button 
            onClick={() => window.location.href = '/analysis'}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            <span>AI Chat</span>
          </button>
        </div>
      </div>

      {/* Statistical Insights KPI Cards - Dark Theme */}
      {selectedDataset && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200/80 font-medium">Mean Value</p>
                <p className="text-3xl font-bold text-white glow-text">
                  {calculateMean(selectedDataset) || 'N/A'}
                </p>
                <p className="text-xs text-slate-300/70 mt-1">Average</p>
              </div>
              <div className="p-3 bg-emerald-500/20 rounded-lg">
                <TrendingUp className="w-8 h-8 text-emerald-300" />
              </div>
            </div>
            <div className="absolute top-2 right-2 w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
          </div>

          <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200/80 font-medium">Median Value</p>
                <p className="text-3xl font-bold text-white glow-text">
                  {calculateMedian(selectedDataset) || 'N/A'}
                </p>
                <p className="text-xs text-slate-300/70 mt-1">Middle Value</p>
              </div>
              <div className="p-3 bg-teal-500/20 rounded-lg">
                <BarChart3 className="w-8 h-8 text-teal-300" />
              </div>
            </div>
            <div className="absolute top-2 right-2 w-2 h-2 bg-teal-400 rounded-full animate-pulse"></div>
          </div>

          <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200/80 font-medium">Standard Deviation</p>
                <p className="text-3xl font-bold text-white glow-text">
                  {calculateStdDev(selectedDataset) || 'N/A'}
                </p>
                <p className="text-xs text-slate-300/70 mt-1">Data Spread</p>
              </div>
              <div className="p-3 bg-cyan-500/20 rounded-lg">
                <Database className="w-8 h-8 text-cyan-300" />
              </div>
            </div>
            <div className="absolute top-2 right-2 w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
          </div>

          <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200/80 font-medium">Range</p>
                <p className="text-3xl font-bold text-white glow-text">
                  {calculateRange(selectedDataset) || 'N/A'}
                </p>
                <p className="text-xs text-slate-300/70 mt-1">Min to Max</p>
              </div>
              <div className="p-3 bg-amber-500/20 rounded-lg">
                <Lightbulb className="w-8 h-8 text-amber-300" />
              </div>
            </div>
            <div className="absolute top-2 right-2 w-2 h-2 bg-amber-400 rounded-full animate-pulse"></div>
          </div>
        </div>
      )}

      {/* Additional Statistical Insights - Dark Theme */}
      {selectedDataset && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200/80 font-medium">Min Value</p>
                <p className="text-2xl font-bold text-white glow-text">
                  {calculateMin(selectedDataset) || 'N/A'}
                </p>
                <p className="text-xs text-slate-300/70 mt-1">Lowest</p>
              </div>
              <div className="p-3 bg-indigo-500/20 rounded-lg">
                <TrendingUp className="w-8 h-8 text-indigo-300" />
              </div>
            </div>
            <div className="absolute top-2 right-2 w-2 h-2 bg-indigo-400 rounded-full animate-pulse"></div>
          </div>

          <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200/80 font-medium">Max Value</p>
                <p className="text-2xl font-bold text-white glow-text">
                  {calculateMax(selectedDataset) || 'N/A'}
                </p>
                <p className="text-xs text-slate-300/70 mt-1">Highest</p>
              </div>
              <div className="p-3 bg-rose-500/20 rounded-lg">
                <BarChart3 className="w-8 h-8 text-rose-300" />
              </div>
            </div>
            <div className="absolute top-2 right-2 w-2 h-2 bg-rose-400 rounded-full animate-pulse"></div>
          </div>

          <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200/80 font-medium">Sum</p>
                <p className="text-2xl font-bold text-white glow-text">
                  {calculateSum(selectedDataset) || 'N/A'}
                </p>
                <p className="text-xs text-slate-300/70 mt-1">Total</p>
              </div>
              <div className="p-3 bg-violet-500/20 rounded-lg">
                <Database className="w-8 h-8 text-violet-300" />
              </div>
            </div>
            <div className="absolute top-2 right-2 w-2 h-2 bg-violet-400 rounded-full animate-pulse"></div>
          </div>

          <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200/80 font-medium">Count</p>
                <p className="text-2xl font-bold text-white glow-text">
                  {calculateCount(selectedDataset) || 0}
                </p>
                <p className="text-xs text-slate-300/70 mt-1">Numeric Values</p>
              </div>
              <div className="p-3 bg-pink-500/20 rounded-lg">
                <Lightbulb className="w-8 h-8 text-pink-300" />
              </div>
            </div>
            <div className="absolute top-2 right-2 w-2 h-2 bg-pink-400 rounded-full animate-pulse"></div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chart Area - Dark Theme */}
        <div className="lg:col-span-2">
          <div className="relative bg-gradient-to-br from-slate-900/90 to-gray-900/90 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10">
            <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-500/5 rounded-xl"></div>
            <div className="relative flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white glow-text">AI-Generated Chart</h2>
              {mainChart && (
                <div className="flex items-center space-x-3">
                  <span className="px-3 py-1 bg-slate-600/20 text-slate-200 text-xs font-medium rounded-full border border-slate-500/30">
                    {mainChart.chart_type?.toUpperCase()}
                  </span>
                  <span className="px-3 py-1 bg-emerald-500/20 text-emerald-200 text-xs font-medium rounded-full border border-emerald-400/30">
                    AI Recommended
                  </span>
                </div>
              )}
            </div>
            
            {chartLoading ? (
              <div className="relative flex items-center justify-center h-96">
                <div className="text-center">
                  <div className="relative">
                    <Loader2 className="h-16 w-16 animate-spin text-emerald-400 mx-auto mb-6" />
                    <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20"></div>
                  </div>
                  <p className="text-xl text-white mb-2 glow-text">AI is analyzing your data...</p>
                  <p className="text-sm text-slate-300 mb-6">Analyzing data patterns and relationships...</p>
                  <div className="w-80 bg-slate-800/50 rounded-full h-3 border border-emerald-500/20">
                    <div className="bg-gradient-to-r from-emerald-500 to-teal-500 h-3 rounded-full animate-pulse shadow-lg shadow-emerald-500/50" style={{width: '60%'}}></div>
                  </div>
                </div>
              </div>
            ) : mainChart ? (
              <div className="space-y-6">
                {/* Chart Explanation */}
                <div className="relative bg-gradient-to-r from-slate-800/30 to-gray-800/30 backdrop-blur-sm border border-slate-600/20 rounded-xl p-5">
                  <div className="absolute inset-0 bg-gradient-to-r from-slate-600/5 to-gray-600/5 rounded-xl"></div>
                  <div className="relative flex items-start space-x-4">
                    <div className="p-2 bg-emerald-500/20 rounded-lg">
                      <Lightbulb className="w-6 h-6 text-emerald-300" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-200 mb-2">Why this chart?</h3>
                      <p className="text-sm text-slate-300/90 leading-relaxed">
                        {getChartExplanation(mainChart.chart_type, selectedDataset)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Chart */}
                <div className="h-96">
                  <PlotlyChart
                    data={mainChart.chart_data}
                    layout={{
                      title: mainChart.title,
                      ...mainChart.chart_config,
                      height: 350,
                      margin: { t: 40, r: 20, b: 40, l: 40 },
                      showlegend: true,
                      legend: { x: 0, y: 1 }
                    }}
                    config={{
                      ...mainChart.chart_config,
                      displayModeBar: true,
                      displaylogo: false,
                      modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
                    }}
                    className="w-full h-full"
                  />
                </div>

                {/* Chart Insights */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="relative bg-gradient-to-br from-slate-800/50 to-slate-700/50 backdrop-blur-sm border border-slate-600/20 rounded-xl p-4">
                    <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-slate-500/5 rounded-xl"></div>
                    <div className="relative">
                      <h4 className="text-sm font-bold text-slate-200 mb-2">Chart Type</h4>
                      <p className="text-sm text-slate-300/90">
                        {getChartTypeDescription(mainChart.chart_type)}
                      </p>
                    </div>
                  </div>
                  <div className="relative bg-gradient-to-br from-slate-800/50 to-slate-700/50 backdrop-blur-sm border border-slate-600/20 rounded-xl p-4">
                    <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-slate-500/5 rounded-xl"></div>
                    <div className="relative">
                      <h4 className="text-sm font-bold text-slate-200 mb-2">Best For</h4>
                      <p className="text-sm text-slate-300/90">
                        {getChartUseCase(mainChart.chart_type)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="relative h-96 bg-gradient-to-br from-slate-800/30 to-slate-700/30 backdrop-blur-sm rounded-xl border border-slate-600/20 flex items-center justify-center">
                <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-slate-500/5 rounded-xl"></div>
                <div className="relative text-center">
                  <div className="p-4 bg-slate-700/50 rounded-full w-20 h-20 mx-auto mb-4 flex items-center justify-center">
                    <BarChart3 className="h-10 w-10 text-slate-400" />
                  </div>
                  <p className="text-slate-200 text-lg mb-2">No chart available</p>
                  <p className="text-slate-400 text-sm">Select a dataset to generate AI insights</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Dataset Overview - Dark Theme */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white">Dataset Overview</h3>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-4 shadow-2xl shadow-slate-500/10">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
              <div className="relative flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-300">Total Records</p>
                  <p className="text-2xl font-bold text-white glow-text">{selectedDataset?.row_count?.toLocaleString() || 0}</p>
                </div>
                <Database className="w-8 h-8 text-emerald-400" />
              </div>
            </div>

            <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-4 shadow-2xl shadow-slate-500/10">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
              <div className="relative flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-300">Total Columns</p>
                  <p className="text-2xl font-bold text-white glow-text">{selectedDataset?.column_count || 0}</p>
                </div>
                <BarChart3 className="w-8 h-8 text-teal-400" />
              </div>
            </div>

            <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-4 shadow-2xl shadow-slate-500/10">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
              <div className="relative flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-300">File Size</p>
                  <p className="text-2xl font-bold text-white glow-text">
                    {formatFileSize(selectedDataset?.file_size || 0)}
                  </p>
                </div>
                <Upload className="w-8 h-8 text-cyan-400" />
              </div>
            </div>

            <div className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-4 shadow-2xl shadow-slate-500/10">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
              <div className="relative flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-300">Processing Status</p>
                  <p className="text-2xl font-bold text-white glow-text">
                    {selectedDataset?.is_processed ? 'Complete' : 'Processing'}
                  </p>
                </div>
                <Lightbulb className="w-8 h-8 text-amber-400" />
              </div>
            </div>
          </div>
        </div>
      </div>

      
      {/* AI Insights Section - QUIS Methodology - Dark Theme */}
      <div className="relative bg-gradient-to-br from-slate-900/90 to-gray-900/90 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
        <div className="relative">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white glow-text">AI Insights (QUIS Methodology)</h2>
            <div className="flex items-center space-x-2">
              <span className="px-2 py-1 bg-emerald-500/20 text-emerald-300 text-xs font-medium rounded-full border border-emerald-400/30">
                Research-Based
              </span>
            </div>
          </div>
          
          {aiInsights.length > 0 ? (
            <div className="space-y-4">
              {aiInsights.map((insight, index) => (
                <div key={index} className="relative bg-gradient-to-r from-slate-800/30 to-gray-800/30 backdrop-blur-sm border border-slate-600/20 rounded-xl p-5">
                  <div className="absolute inset-0 bg-gradient-to-r from-slate-600/5 to-gray-600/5 rounded-xl"></div>
                  <div className="relative">
                    {/* Question */}
                    <div className="flex items-start space-x-3 mb-3">
                      <div className="p-2 bg-emerald-500/20 rounded-lg">
                        <Lightbulb className="w-5 h-5 text-emerald-300" />
                      </div>
                      <div className="flex-1">
                        <h3 className="text-slate-200 font-medium mb-2">{insight.question}</h3>
                        <p className="text-slate-300 text-sm mb-2">{insight.answer}</p>
                        <p className="text-slate-400 text-xs italic">{insight.reason}</p>
                      </div>
                    </div>
                    
                    {/* Analysis Details */}
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <div className="flex items-center space-x-4">
                        <span>Type: {insight.analysis_type?.replace('_', ' ')}</span>
                        <span>Breakdown: {insight.breakdown}</span>
                        <span>Measure: {insight.measure}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-1 bg-slate-600/30 rounded">
                          Confidence: {Math.round(insight.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                    
                    {/* Actionable Insights */}
                    {insight.actionable_insights && insight.actionable_insights.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-600/20">
                        <p className="text-slate-400 text-xs font-medium mb-2">Recommended Actions:</p>
                        <ul className="space-y-1">
                          {insight.actionable_insights.map((action, actionIndex) => (
                            <li key={actionIndex} className="text-slate-300 text-xs flex items-start space-x-2">
                              <span className="text-emerald-400 mt-1">•</span>
                              <span>{action}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <div className="p-4 bg-slate-700/50 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <Lightbulb className="h-8 w-8 text-slate-400" />
              </div>
              <p className="text-slate-300">AI insights will appear here after analysis</p>
              <p className="text-slate-400 text-sm mt-1">Using QUIS (Question-based User Insight System) methodology</p>
            </div>
          )}
        </div>
      </div>

      {/* Data Preview Section - Dark Theme */}
      {selectedDataset && (
        <div className="relative bg-gradient-to-br from-slate-900/90 to-gray-900/90 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10">
          <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white glow-text">Data Preview</h2>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-slate-300">
                  Showing {Math.min(10, selectedDataset.preview_data?.length || 0)} of {selectedDataset.row_count?.toLocaleString() || 0} records
                </span>
              </div>
            </div>
          
            {selectedDataset.preview_data && selectedDataset.preview_data.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-600">
                  <thead className="bg-slate-800/50">
                    <tr>
                      {Object.keys(selectedDataset.preview_data[0]).map((column, index) => (
                        <th
                          key={index}
                          className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider"
                        >
                          <div className="flex items-center space-x-2">
                            <span>{column}</span>
                            <span className="text-xs text-slate-400">
                              ({selectedDataset.metadata?.column_metadata?.[index]?.type || 'unknown'})
                            </span>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-slate-900/50 divide-y divide-slate-600">
                    {selectedDataset.preview_data.slice(0, 10).map((row, rowIndex) => (
                      <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-slate-900/30' : 'bg-slate-800/30'}>
                        {Object.values(row).map((value, colIndex) => (
                          <td
                            key={colIndex}
                            className="px-6 py-4 whitespace-nowrap text-sm text-slate-200"
                          >
                            <div className="max-w-xs truncate" title={String(value)}>
                              {value === null || value === undefined ? (
                                <span className="text-slate-400 italic">null</span>
                              ) : typeof value === 'number' ? (
                                value.toLocaleString()
                              ) : (
                                String(value)
                              )}
                            </div>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                
                {selectedDataset.preview_data.length > 10 && (
                  <div className="mt-4 text-center">
                    <span className="text-sm text-slate-400">
                      ... and {selectedDataset.row_count - 10} more records
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="p-4 bg-slate-700/50 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                  <Database className="h-8 w-8 text-slate-400" />
                </div>
                <h3 className="text-lg font-medium text-slate-200 mb-2">No Preview Data</h3>
                <p className="text-slate-400">Preview data is not available for this dataset</p>
              </div>
            )}
          </div>
        </div>
      )}
      {/* Recent Datasets - Dark Theme */}
      <div className="relative bg-gradient-to-br from-slate-900/90 to-gray-900/90 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
        <div className="relative">
          <h2 className="text-lg font-semibold text-white mb-4 glow-text">Recent Datasets</h2>
          
          {datasets.length > 0 ? (
            <div className="space-y-3">
              {datasets.slice(0, 5).map((dataset) => (
                <div key={dataset.id} className="relative bg-gradient-to-r from-slate-800/30 to-gray-800/30 backdrop-blur-sm border border-slate-600/20 rounded-xl p-3 hover:bg-slate-700/30 transition-colors">
                  <div className="absolute inset-0 bg-gradient-to-r from-slate-600/5 to-gray-600/5 rounded-xl"></div>
                  <div className="relative flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-emerald-500/20 rounded-lg">
                        <Database className="w-5 h-5 text-emerald-300" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-200">{dataset.name || 'Unnamed Dataset'}</p>
                        <p className="text-sm text-slate-400">
                          {dataset.row_count?.toLocaleString() || 0} records • 
                          {new Date(dataset.uploaded_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                      dataset.is_processed 
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30' 
                        : 'bg-amber-500/20 text-amber-300 border border-amber-400/30'
                    }`}>
                      {dataset.is_processed ? 'Processed' : 'Processing'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <div className="p-4 bg-slate-700/50 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <Database className="h-8 w-8 text-slate-400" />
              </div>
              <p className="text-slate-300">No datasets available</p>
            </div>
          )}
        </div>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <UploadModal
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          onUploadSuccess={() => {
            setShowUploadModal(false)
            loadDatasets() // Refresh datasets after upload
          }}
        />
      )}
      </div>
    </div>
  )
}

export default Dashboard
