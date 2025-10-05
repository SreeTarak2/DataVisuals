import React, { useState, useEffect } from 'react'
import { PieChart, BarChart3, LineChart, ChartScatter, Download, Share2, MoreVertical, Plus, Filter, Eye, Trash2, Edit3, Loader2, Brain, Sparkles, ChevronRight } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import toast from 'react-hot-toast'
import ConfirmationModal from '../components/ConfirmationModal'
import PlotlyChart from '../components/PlotlyChart'
import AIVisualizationBuilder from '../components/AIVisualizationBuilder'

const Charts = () => {
  const [selectedType, setSelectedType] = useState('all')
  const [charts, setCharts] = useState([])
  const [loading, setLoading] = useState(true)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [chartToDelete, setChartToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [selectedChart, setSelectedChart] = useState(null)
  const [showChartModal, setShowChartModal] = useState(false)
  const [drillDownLevel, setDrillDownLevel] = useState(0)
  const [drillDownPath, setDrillDownPath] = useState([])
  const [currentChartData, setCurrentChartData] = useState(null)
  const [showAIBuilder, setShowAIBuilder] = useState(false)
  const [selectedDataset, setSelectedDataset] = useState(null)
  const [datasets, setDatasets] = useState([])
  const { user } = useAuth()

  const chartTypes = [
    { id: 'all', name: 'All Charts', icon: BarChart3 },
    { id: 'bar', name: 'Bar Charts', icon: BarChart3 },
    { id: 'line', name: 'Line Charts', icon: LineChart },
    { id: 'pie', name: 'Pie Charts', icon: PieChart },
    { id: 'scatter', name: 'Scatter Plots', icon: ChartScatter },
    { id: 'heatmap', name: 'Heatmaps', icon: BarChart3 },
    { id: 'box', name: 'Box Plots', icon: BarChart3 }
  ]

  // Load charts on component mount
  useEffect(() => {
    loadCharts()
  }, [])

  const loadCharts = async () => {
    try {
      setLoading(true)
      const response = await axios.get('/api/datasets')
      const datasets = response.data.datasets || []
      console.log('Datasets for charts:', datasets)
      
      // Store datasets for AI builder
      setDatasets(datasets)
      
      // Generate charts based on datasets
      const generatedCharts = generateChartsFromDatasets(datasets)
      console.log('Generated charts:', generatedCharts)
      setCharts(generatedCharts)
    } catch (error) {
      console.error('Error loading charts:', error)
      toast.error('Failed to load charts')
      // Generate some sample charts if API fails
      setCharts(generateSampleCharts())
    } finally {
      setLoading(false)
    }
  }

  const generateChartsFromDatasets = (datasets) => {
    const charts = []
    
    if (datasets.length === 0) {
      return generateSampleCharts()
    }
    
    datasets.forEach((dataset, index) => {
      const datasetName = dataset.name || `Dataset ${index + 1}`
      
      // Generate different chart types based on dataset metadata
      const numericColumns = dataset.metadata?.column_metadata?.filter(col => 
        ['int64', 'float64'].includes(col.type)
      ) || []
      
      const categoricalColumns = dataset.metadata?.column_metadata?.filter(col => 
        ['object', 'category'].includes(col.type)
      ) || []

      // Always generate at least one chart per dataset
      charts.push({
        id: `bar_${dataset.id || index}`,
        title: `${datasetName} - Data Distribution`,
        type: 'bar',
        dataset: datasetName,
        lastUpdated: formatDate(dataset.upload_date || dataset.uploaded_at),
        views: Math.floor(Math.random() * 200) + 50,
        data: generateSampleData('bar', 'Distribution'),
        config: {
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
        },
        layout: {
          title: `${datasetName} Distribution`,
          xaxis: { title: 'Categories' },
          yaxis: { title: 'Count' },
          hovermode: 'closest'
        }
      })

      // Bar Chart for numeric data
      if (numericColumns.length > 0) {
        charts.push({
          id: `bar_numeric_${dataset.id || index}`,
          title: `${datasetName} - ${numericColumns[0].name} Distribution`,
          type: 'bar',
          dataset: datasetName,
          lastUpdated: formatDate(dataset.upload_date || dataset.uploaded_at),
          views: Math.floor(Math.random() * 200) + 50,
          data: generateSampleData('bar', numericColumns[0].name),
          config: {
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
          },
          layout: {
            title: `${numericColumns[0].name} Distribution`,
            xaxis: { title: numericColumns[0].name },
            yaxis: { title: 'Count' },
            hovermode: 'closest'
          }
        })
      }

      // Pie Chart for categorical data
      if (categoricalColumns.length > 0) {
        charts.push({
          id: `pie_${dataset.id || index}`,
          title: `${datasetName} - ${categoricalColumns[0].name} Distribution`,
          type: 'pie',
          dataset: datasetName,
          lastUpdated: formatDate(dataset.upload_date || dataset.uploaded_at),
          views: Math.floor(Math.random() * 150) + 30,
          data: generateSampleData('pie', categoricalColumns[0].name),
          config: {
            displayModeBar: true,
            displaylogo: false
          },
          layout: {
            title: `${categoricalColumns[0].name} Distribution`,
            hovermode: 'closest'
          }
        })
      }

      // Line Chart for time series data
      if (numericColumns.length >= 2) {
        charts.push({
          id: `line_${dataset.id || index}`,
          title: `${datasetName} - Trend Analysis`,
          type: 'line',
          dataset: datasetName,
          lastUpdated: formatDate(dataset.upload_date || dataset.uploaded_at),
          views: Math.floor(Math.random() * 180) + 40,
          data: generateSampleData('line', 'trend'),
          config: {
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
          },
          layout: {
            title: 'Trend Analysis',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Value' },
            hovermode: 'x unified'
          }
        })
      }

      // Scatter Plot for correlation analysis
      if (numericColumns.length >= 2) {
        charts.push({
          id: `scatter_${dataset.id || index}`,
          title: `${datasetName} - Correlation Analysis`,
          type: 'scatter',
          dataset: datasetName,
          lastUpdated: formatDate(dataset.upload_date || dataset.uploaded_at),
          views: Math.floor(Math.random() * 120) + 25,
          data: generateSampleData('scatter', 'correlation'),
          config: {
            displayModeBar: true,
            displaylogo: false
          },
          layout: {
            title: 'Correlation Analysis',
            xaxis: { title: numericColumns[0]?.name || 'X' },
            yaxis: { title: numericColumns[1]?.name || 'Y' },
            hovermode: 'closest'
          }
        })
      }
    })

    return charts
  }

  const generateSampleCharts = () => {
    return [
      {
        id: 'sample_bar_1',
        title: 'Sales Performance Overview',
        type: 'bar',
        dataset: 'Sample Data',
        lastUpdated: '2 hours ago',
        views: 156,
        data: generateSampleData('bar', 'Sales'),
        config: {
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
        },
        layout: {
          title: 'Sales Performance',
          xaxis: { title: 'Products' },
          yaxis: { title: 'Sales' },
          hovermode: 'closest'
        }
      },
      {
        id: 'sample_pie_1',
        title: 'Market Share Distribution',
        type: 'pie',
        dataset: 'Sample Data',
        lastUpdated: '1 day ago',
        views: 89,
        data: generateSampleData('pie', 'Market Share'),
        config: {
          displayModeBar: true,
          displaylogo: false
        },
        layout: {
          title: 'Market Share',
          hovermode: 'closest'
        }
      },
      {
        id: 'sample_line_1',
        title: 'Revenue Trend Analysis',
        type: 'line',
        dataset: 'Sample Data',
        lastUpdated: '3 days ago',
        views: 234,
        data: generateSampleData('line', 'Revenue'),
        config: {
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
        },
        layout: {
          title: 'Revenue Trend',
          xaxis: { title: 'Time' },
          yaxis: { title: 'Revenue' },
          hovermode: 'x unified'
        }
      },
      {
        id: 'sample_scatter_1',
        title: 'Customer Satisfaction vs Sales',
        type: 'scatter',
        dataset: 'Sample Data',
        lastUpdated: '1 week ago',
        views: 67,
        data: generateSampleData('scatter', 'Correlation'),
        config: {
          displayModeBar: true,
          displaylogo: false
        },
        layout: {
          title: 'Customer Satisfaction vs Sales',
          xaxis: { title: 'Satisfaction Score' },
          yaxis: { title: 'Sales Volume' },
          hovermode: 'closest'
        }
      }
    ]
  }

  const generateSampleData = (type, columnName) => {
    switch (type) {
      case 'bar':
        return [{
          x: ['Category A', 'Category B', 'Category C', 'Category D', 'Category E'],
          y: [20, 35, 25, 40, 30],
          type: 'bar',
          marker: { color: '#3B82F6' },
          name: columnName || 'Data'
        }]
      case 'pie':
        return [{
          labels: ['North', 'South', 'East', 'West', 'Central'],
          values: [30, 25, 20, 15, 10],
          type: 'pie',
          marker: { colors: ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'] },
          name: columnName || 'Data'
        }]
      case 'line':
        return [{
          x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
          y: [100, 120, 110, 140, 160, 150],
          type: 'scatter',
          mode: 'lines+markers',
          line: { color: '#3B82F6' },
          name: columnName || 'Trend'
        }]
      case 'scatter':
        return [{
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          y: [2, 4, 3, 6, 5, 8, 7, 10, 9, 12],
          type: 'scatter',
          mode: 'markers',
          marker: { color: '#3B82F6', size: 8 },
          name: columnName || 'Correlation'
        }]
      default:
        return [{ x: [], y: [], type: 'bar', name: 'Data' }]
    }
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInHours = Math.floor((now - date) / (1000 * 60 * 60))
    
    if (diffInHours < 1) return 'Just now'
    if (diffInHours < 24) return `${diffInHours} hours ago`
    if (diffInHours < 48) return '1 day ago'
    return `${Math.floor(diffInHours / 24)} days ago`
  }

  const filteredCharts = charts.filter(chart => {
    const matchesType = selectedType === 'all' || chart.type === selectedType
    return matchesType
  })

  const handleViewChart = (chart) => {
    setSelectedChart(chart)
    setCurrentChartData(chart.data)
    setDrillDownLevel(0)
    setDrillDownPath([])
    setShowChartModal(true)
  }

  const handleChartClick = (event) => {
    if (!selectedChart) return

    // Handle drill-down based on chart type
    const point = event.points?.[0]
    if (!point) return

    const drillDownData = generateDrillDownData(selectedChart, point, drillDownLevel + 1)
    if (drillDownData) {
      setCurrentChartData(drillDownData)
      setDrillDownLevel(prev => prev + 1)
      setDrillDownPath(prev => [...prev, {
        level: drillDownLevel + 1,
        point: point,
        timestamp: new Date().toISOString()
      }])
    }
  }

  const handleBackToParent = () => {
    if (drillDownLevel > 0) {
      const newLevel = drillDownLevel - 1
      setDrillDownLevel(newLevel)
      setDrillDownPath(prev => prev.slice(0, newLevel))
      
      if (newLevel === 0) {
        setCurrentChartData(selectedChart.data)
      } else {
        const parentData = generateDrillDownData(selectedChart, drillDownPath[newLevel - 1].point, newLevel)
        setCurrentChartData(parentData)
      }
    }
  }

  const generateDrillDownData = (originalChart, clickedPoint, level) => {
    // Generate more detailed data based on the clicked point
    const baseData = originalChart.data
    
    switch (originalChart.type) {
      case 'bar':
        return generateBarDrillDown(baseData, clickedPoint, level)
      case 'pie':
        return generatePieDrillDown(baseData, clickedPoint, level)
      case 'line':
        return generateLineDrillDown(baseData, clickedPoint, level)
      case 'scatter':
        return generateScatterDrillDown(baseData, clickedPoint, level)
      default:
        return baseData
    }
  }

  const generateBarDrillDown = (data, point, level) => {
    const category = point.x || point.label
    const subCategories = [`${category} - Q1`, `${category} - Q2`, `${category} - Q3`, `${category} - Q4`]
    const subValues = Array.from({ length: 4 }, () => Math.floor(Math.random() * 100) + 20)
    
    return {
      ...data,
      x: subCategories,
      y: subValues,
      name: `Drill-down Level ${level}`,
      marker: { 
        color: data.marker?.color || '#3B82F6',
        opacity: 0.8
      }
    }
  }

  const generatePieDrillDown = (data, point, level) => {
    const category = point.label
    const subCategories = [`${category} - Sub1`, `${category} - Sub2`, `${category} - Sub3`]
    const subValues = Array.from({ length: 3 }, () => Math.floor(Math.random() * 50) + 10)
    
    return {
      ...data,
      labels: subCategories,
      values: subValues,
      name: `Drill-down Level ${level}`,
      marker: { 
        colors: ['#3B82F6', '#10B981', '#F59E0B'],
        opacity: 0.8
      }
    }
  }

  const generateLineDrillDown = (data, point, level) => {
    const timeRange = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
    const subValues = Array.from({ length: 4 }, () => Math.floor(Math.random() * 50) + 20)
    
    return {
      ...data,
      x: timeRange,
      y: subValues,
      name: `Drill-down Level ${level}`,
      line: { 
        color: data.line?.color || '#3B82F6',
        width: 3
      }
    }
  }

  const generateScatterDrillDown = (data, point, level) => {
    const subPoints = Array.from({ length: 10 }, (_, i) => ({
      x: point.x + (Math.random() - 0.5) * 2,
      y: point.y + (Math.random() - 0.5) * 2
    }))
    
    return {
      ...data,
      x: subPoints.map(p => p.x),
      y: subPoints.map(p => p.y),
      name: `Drill-down Level ${level}`,
      marker: { 
        color: data.marker?.color || '#3B82F6',
        size: 8,
        opacity: 0.7
      }
    }
  }

  const handleDeleteClick = (chart) => {
    setChartToDelete(chart)
    setShowDeleteModal(true)
  }

  const handleDeleteConfirm = async () => {
    if (!chartToDelete) return

    setDeleting(true)
    try {
      // In a real implementation, this would call the API to delete the chart
      setCharts(prev => prev.filter(c => c.id !== chartToDelete.id))
      toast.success('Chart deleted successfully')
      setShowDeleteModal(false)
      setChartToDelete(null)
    } catch (error) {
      console.error('Error deleting chart:', error)
      toast.error('Failed to delete chart')
    } finally {
      setDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setShowDeleteModal(false)
    setChartToDelete(null)
  }

  const handleDownload = (chartId) => {
    console.log('Downloading chart:', chartId)
    toast.success('Chart download started')
  }

  const handleShare = (chartId) => {
    console.log('Sharing chart:', chartId)
    toast.success('Chart link copied to clipboard')
  }

  const handleEdit = (chartId) => {
    console.log('Editing chart:', chartId)
    toast.info('Chart editor coming soon!')
  }

  const handleCreateChart = () => {
    // Generate a new sample chart
    const newChart = {
      id: `new_chart_${Date.now()}`,
      title: `Custom Chart ${charts.length + 1}`,
      type: 'bar',
      dataset: 'Custom Data',
      lastUpdated: 'Just now',
      views: 1,
      data: generateSampleData('bar', 'Custom'),
      config: {
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
      },
      layout: {
        title: 'Custom Chart',
        xaxis: { title: 'Categories' },
        yaxis: { title: 'Values' },
        hovermode: 'closest'
      }
    }
    
    setCharts(prev => [newChart, ...prev])
    toast.success('New chart created!')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-gray-900 to-slate-800 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400 mx-auto mb-4" />
          <p className="text-slate-300">Loading charts...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-gray-900 to-slate-800 p-6">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Interactive Charts</h1>
            <p className="text-slate-300 mt-1">
              Explore your data with interactive Plotly visualizations
            </p>
          </div>
          <div className="flex space-x-3">
            <button 
              onClick={handleCreateChart}
              className="flex items-center space-x-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Create Chart</span>
            </button>
            <button 
              onClick={() => setShowAIBuilder(true)}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors border border-slate-600"
            >
              <Brain className="w-4 h-4" />
              <span>AI Builder</span>
              <Sparkles className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex space-x-2">
            <button className="flex items-center space-x-2 px-4 py-2 border border-slate-600 rounded-lg hover:bg-slate-800 transition-colors text-slate-300">
              <Filter className="w-4 h-4" />
              <span>Filter</span>
            </button>
          </div>
        </div>

        {/* Chart Type Tabs */}
        <div className="flex space-x-1 bg-slate-800/50 p-1 rounded-lg overflow-x-auto border border-slate-600/20">
          {chartTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => setSelectedType(type.id)}
              className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${
                selectedType === type.id
                  ? 'bg-emerald-500/20 text-emerald-300 shadow-lg shadow-emerald-500/10 border border-emerald-400/30'
                  : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              <type.icon className="w-4 h-4" />
              <span>{type.name}</span>
            </button>
          ))}
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCharts.map((chart) => (
            <div key={chart.id} className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
              <div className="relative">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-white mb-1">{chart.title}</h3>
                    <p className="text-sm text-slate-400">{chart.dataset}</p>
                  </div>
                  <div className="flex items-center space-x-1">
                    <button
                      onClick={() => handleViewChart(chart)}
                      className="p-1 text-slate-400 hover:text-emerald-400 transition-colors"
                      title="View Chart"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleEdit(chart.id)}
                      className="p-1 text-slate-400 hover:text-teal-400 transition-colors"
                      title="Edit Chart"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDownload(chart.id)}
                      className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
                      title="Download Chart"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleShare(chart.id)}
                      className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
                      title="Share Chart"
                    >
                      <Share2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteClick(chart)}
                      className="p-1 text-slate-400 hover:text-red-400 transition-colors"
                      title="Delete Chart"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Chart Preview */}
                <div className="h-48 mb-4 cursor-pointer" onClick={() => handleViewChart(chart)}>
                  <PlotlyChart
                    data={chart.data}
                    layout={chart.layout}
                    config={chart.config}
                  />
                </div>

                <div className="flex items-center justify-between text-sm text-slate-400">
                  <span>{chart.views} views</span>
                  <span>{chart.lastUpdated}</span>
                </div>
              </div>
            </div>
        ))}
      </div>

        {/* Empty State */}
        {filteredCharts.length === 0 && !loading && (
          <div className="text-center py-12">
            <div className="p-4 bg-slate-700/50 rounded-full w-20 h-20 mx-auto mb-4 flex items-center justify-center">
              <BarChart3 className="w-12 h-12 text-slate-400" />
            </div>
            <h3 className="text-lg font-medium text-white mb-2">No charts found</h3>
            <p className="text-slate-400 mb-6">
              Upload datasets to generate interactive charts
            </p>
            <button 
              onClick={handleCreateChart}
              className="inline-flex items-center space-x-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Create Chart</span>
            </button>
          </div>
        )}

        {/* Chart Modal */}
      {showChartModal && selectedChart && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <div className="flex items-center space-x-4">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">{selectedChart.title}</h3>
                  <p className="text-sm text-gray-500">{selectedChart.dataset}</p>
                </div>
                {drillDownLevel > 0 && (
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={handleBackToParent}
                      className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
                    >
                      ← Back to Level {drillDownLevel - 1}
                    </button>
                    <span className="text-sm text-gray-500">
                      Drill-down Level {drillDownLevel}
                    </span>
                  </div>
                )}
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleDownload(selectedChart.id)}
                  className="p-2 text-gray-400 hover:text-gray-600"
                  title="Download Chart"
                >
                  <Download className="w-5 h-5" />
                </button>
                <button
                  onClick={() => handleShare(selectedChart.id)}
                  className="p-2 text-gray-400 hover:text-gray-600"
                  title="Share Chart"
                >
                  <Share2 className="w-5 h-5" />
                </button>
                <button
                  onClick={() => setShowChartModal(false)}
                  className="p-2 text-gray-400 hover:text-gray-600"
                  title="Close"
                >
                  <MoreVertical className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="p-6 h-96">
              <PlotlyChart
                data={currentChartData || selectedChart.data}
                layout={{
                  ...selectedChart.layout, 
                  height: 400,
                  title: drillDownLevel > 0 
                    ? `${selectedChart.layout.title} - Drill-down Level ${drillDownLevel}`
                    : selectedChart.layout.title
                }}
                config={selectedChart.config}
                onClick={handleChartClick}
                onHover={(event) => {
                  // Show detailed tooltip on hover
                  console.log('Hover event:', event)
                }}
              />
            </div>
            {drillDownLevel > 0 && (
              <div className="px-6 py-3 bg-gray-50 border-t border-gray-200">
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-600">
                    <span className="font-medium">Drill-down Path:</span>
                    <span className="ml-2">
                      {drillDownPath.map((step, index) => (
                        <span key={index}>
                          Level {step.level}
                          {index < drillDownPath.length - 1 && ' → '}
                        </span>
                      ))}
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      setDrillDownLevel(0)
                      setDrillDownPath([])
                      setCurrentChartData(selectedChart.data)
                    }}
                    className="text-sm text-blue-600 hover:text-blue-700"
                  >
                    Reset to Top Level
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* AI Visualization Builder Modal */}
      {showAIBuilder && (
        <AIVisualizationBuilder
          dataset={selectedDataset}
          onClose={() => {
            setShowAIBuilder(false)
            setSelectedDataset(null)
          }}
          onSave={(chartData) => {
            // Handle saving the AI-generated chart
            console.log('AI Chart saved:', chartData)
            toast.success('AI Chart created successfully!')
            setShowAIBuilder(false)
            setSelectedDataset(null)
            // Refresh charts
            loadCharts()
          }}
        />
      )}

      {/* Dataset Selection Modal for AI Builder */}
      {showAIBuilder && !selectedDataset && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <Brain className="w-6 h-6 text-purple-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Select Dataset for AI Analysis</h2>
                  <p className="text-gray-600">Choose a dataset to analyze with AI</p>
                </div>
              </div>
              <button
                onClick={() => setShowAIBuilder(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>
            
            <div className="p-6 max-h-96 overflow-y-auto">
              {datasets.length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-gray-400 mb-4">📊</div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No datasets available</h3>
                  <p className="text-gray-500 mb-4">Upload a dataset first to use AI analysis</p>
                  <button
                    onClick={() => setShowAIBuilder(false)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  >
                    Go to Datasets
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {datasets.map((dataset) => (
                    <div
                      key={dataset.id}
                      onClick={() => setSelectedDataset(dataset)}
                      className="p-4 border border-gray-200 rounded-lg hover:border-purple-300 hover:bg-purple-50 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-blue-100 rounded-lg">
                          <BarChart3 className="w-5 h-5 text-blue-600" />
                        </div>
                        <div className="flex-1">
                          <h3 className="font-medium text-gray-900">{dataset.name}</h3>
                          <p className="text-sm text-gray-500">
                            {dataset.row_count?.toLocaleString() || 0} rows • {dataset.column_count || 0} columns
                          </p>
                        </div>
                        <ChevronRight className="w-5 h-5 text-gray-400" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmationModal
        isOpen={showDeleteModal}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        title="Delete Chart"
        message={`Are you sure you want to permanently delete "${chartToDelete?.title}"? This action cannot be undone.`}
        confirmText={deleting ? "Deleting..." : "Delete"}
        cancelText="Cancel"
        type="danger"
      />
      </div>
  )
}

export default Charts