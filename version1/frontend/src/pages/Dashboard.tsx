import React, { useState, useEffect } from 'react'
import { 
  BarChart3, 
  Database, 
  Brain, 
  TrendingUp,
  ArrowUpRight, 
  ArrowDownRight, 
  RefreshCw, 
  Maximize2, 
  Eye, 
  Upload,
  PieChart,
  Activity,
  CloudUpload,
  Sparkles,
  Cpu,
  Zap,
  Shield,
  BarChart
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTheme } from '../contexts/ThemeContext'
import axios from 'axios'
import UploadModal from '../components/UploadModal'
import DatasetSelector from '../components/DatasetSelector'
import DataVisualization from '../components/DataVisualization'
import DataPreview from '../components/DataPreview'
import StatisticalSummaryCard from '../components/StatisticalSummaryCard'
import ModernChartContainer from '../components/ModernChartContainer'
import DataQualityPanel from '../components/DataQualityPanel'
import QuickActionsPanel from '../components/QuickActionsPanel'
import AdvancedAnalytics from '../components/AdvancedAnalytics'
import ExportModal from '../components/ExportModal'
import { processDatasetForCharts, generateAnalysisSummary } from '../utils/chartDataProcessor'

interface Dataset {
  id: string
  filename: string
  size: number
  row_count: number
  column_count: number
  upload_date: string
  columns?: string[]
  data?: any[]
}

interface MetricCard {
  title: string
  value: string
  change: number
  changeType: 'positive' | 'negative'
  icon: React.ComponentType<any>
  color: string
}

const Dashboard: React.FC = () => {
  const { isDarkTheme } = useTheme()
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [loading, setLoading] = useState(true)
  const [timeFilter, setTimeFilter] = useState('month')
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null)
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const [visualizationRecommendations, setVisualizationRecommendations] = useState<any[]>([])
  const [aiRecommendedCharts, setAiRecommendedCharts] = useState<any[]>([])
  const [datasetData, setDatasetData] = useState<any[]>([])
  const [analyzing, setAnalyzing] = useState(false)
  const [showAIRecommendations, setShowAIRecommendations] = useState(false)
  const [previewDataset, setPreviewDataset] = useState<Dataset | null>(null)
  const [previewData, setPreviewData] = useState<any[]>([])
  const [isPreviewOpen, setIsPreviewOpen] = useState(false)
  const [isExportModalOpen, setIsExportModalOpen] = useState(false)

  // Load datasets on component mount
  useEffect(() => {
    loadDatasets()
  }, [])

  // Auto-analyze when a dataset is selected
  useEffect(() => {
    if (selectedDataset) {
      console.log('Dataset selected, starting analysis:', selectedDataset.filename)

      // Check if we already have data for this dataset
      const storedData = localStorage.getItem(`dataset-${selectedDataset.id}`)
      if (storedData) {
        try {
          const parsedData = JSON.parse(storedData)
          setVisualizationRecommendations(parsedData.recommendations || [])
          setDatasetData(parsedData.data || [])
          setAnalysisResult(parsedData.analysis || null)
          console.log('Loaded stored data for dataset:', selectedDataset.filename)
        } catch (error) {
          console.error('Error loading stored data:', error)
          analyzeDataset(selectedDataset)
        }
      } else {
        analyzeDataset(selectedDataset)
      }
    }
  }, [selectedDataset])

  const handleUploadSuccess = (newDataset: Dataset) => {
    setDatasets(prev => [newDataset, ...prev])
    // Auto-select the newly uploaded dataset
    setSelectedDataset(newDataset)
    analyzeDataset(newDataset)
  }

  const handleDatasetSelect = async (dataset: Dataset) => {
    setSelectedDataset(dataset)
    setShowAIRecommendations(false)
    await analyzeDataset(dataset)
  }

  const handlePreviewDataset = async (dataset: Dataset) => {
    setPreviewDataset(dataset)
    setIsPreviewOpen(true)
    
    try {
      // Fetch the actual data for preview
      const response = await axios.get(`http://localhost:8000/datasets/${dataset.id}`)
      const rawData = response.data.data || []
      setPreviewData(rawData)
    } catch (error) {
      console.error('Failed to load preview data:', error)
      // Generate sample data for preview
      const sampleData = generateSampleDataFromColumns(dataset)
      setPreviewData(sampleData)
    }
  }

  const handlePreviewClose = () => {
    setIsPreviewOpen(false)
    setPreviewDataset(null)
    setPreviewData([])
  }

  const handleAIRecommendation = async () => {
    if (!selectedDataset) return

    setAnalyzing(true)
    try {
      // Call backend for AI recommendations
      const response = await axios.post(`http://localhost:8000/visualization/ai-recommendations`, {
        dataset_id: selectedDataset.id,
        current_charts: visualizationRecommendations.map(rec => rec.chart_type)
      })

      const aiCharts = response.data.recommendations || []
      setAiRecommendedCharts(aiCharts)
      setShowAIRecommendations(true)

      // Generate enhanced sample data for AI charts
      const enhancedData = generateEnhancedSampleData(selectedDataset)
      setDatasetData(enhancedData)

      // Store AI recommendations in localStorage
      const aiDataToStore = {
        recommendations: aiCharts,
        data: enhancedData,
        analysis: analysisResult,
        timestamp: Date.now(),
        isAIRecommended: true
      }
      localStorage.setItem(`dataset-${selectedDataset.id}-ai`, JSON.stringify(aiDataToStore))
      console.log('Stored AI recommendations for dataset:', selectedDataset.filename)
    } catch (error) {
      console.error('Failed to get AI recommendations, using enhanced frontend charts:', error)
      // Fallback to enhanced frontend charts
      const enhancedCharts = processDatasetForCharts(selectedDataset, datasetData)
      setAiRecommendedCharts(enhancedCharts)
      setShowAIRecommendations(true)
    } finally {
      setAnalyzing(false)
    }
  }

  const generateEnhancedSampleData = (dataset: Dataset) => {
    const sampleData: any[] = []
    for (let i = 0; i < Math.min(15, dataset.row_count); i++) {
      sampleData.push({
        category: ['Category A', 'Category B', 'Category C', 'Category D'][i % 4],
        value: Math.floor(Math.random() * 100) + 10,
        index: i,
        count: Math.floor(Math.random() * 50) + 5,
        x: Math.floor(Math.random() * 100),
        y: Math.floor(Math.random() * 100),
        range: `${i * 10}-${(i + 1) * 10}`
      })
    }
    return sampleData
  }

  const analyzeDataset = async (dataset: Dataset) => {
    console.log('Starting frontend analysis for dataset:', dataset.filename)
    setAnalyzing(true)
    setAnalysisResult(null)
    setVisualizationRecommendations([])
    setDatasetData([])

    try {
      // Get actual dataset data from backend
      const datasetResponse = await axios.get(`http://localhost:8000/datasets/${dataset.id}`)
      const rawData = datasetResponse.data.data || []
      
      console.log('Retrieved dataset data:', rawData.length, 'rows')
      
      // Process data for charts using frontend logic
      const charts = processDatasetForCharts(dataset, rawData)
      const chartData = rawData.length > 0 ? rawData : generateSampleDataFromColumns(dataset)
      
      console.log('Generated charts:', charts.length)
      console.log('Chart data:', chartData.length, 'rows')
      console.log('Sample chart data:', charts[0]?.data?.slice(0, 3))
      
      setVisualizationRecommendations(charts)
      setDatasetData(chartData)
      
      // Generate analysis summary
      const analysisResult = generateAnalysisSummary(dataset, charts)
      setAnalysisResult(analysisResult)
      
      // Store data in localStorage for persistence
      const dataToStore = {
        recommendations: charts,
        data: chartData,
        analysis: analysisResult,
        timestamp: Date.now()
      }
      localStorage.setItem(`dataset-${dataset.id}`, JSON.stringify(dataToStore))
      console.log('Stored data for dataset:', dataset.filename)
      
    } catch (error) {
      console.error('Failed to load dataset data, using fallback:', error)
      
      // Fallback to sample data generation
      const sampleData = generateSampleDataFromColumns(dataset)
      const charts = processDatasetForCharts(dataset, sampleData)
      
      console.log('Fallback charts generated:', charts.length)
      console.log('Fallback sample data:', sampleData.slice(0, 3))
      
      setVisualizationRecommendations(charts)
      setDatasetData(sampleData)
      
      const analysisResult = generateAnalysisSummary(dataset, charts)
      setAnalysisResult(analysisResult)
      
      // Store fallback data
      const dataToStore = {
        recommendations: charts,
        data: sampleData,
        analysis: analysisResult,
        timestamp: Date.now()
      }
      localStorage.setItem(`dataset-${dataset.id}`, JSON.stringify(dataToStore))
    } finally {
      setAnalyzing(false)
    }
  }

  const generateSampleDataFromColumns = (dataset: Dataset): any[] => {
    const sampleData: any[] = []
    const columns = dataset.columns || ['category', 'value', 'date', 'score']
    
    for (let i = 0; i < Math.min(20, dataset.row_count); i++) {
      const row: any = {}
      
      columns.forEach((col, index) => {
        if (col.toLowerCase().includes('date') || col.toLowerCase().includes('time')) {
          row[col] = new Date(2024, 0, i + 1).toISOString().split('T')[0]
        } else if (col.toLowerCase().includes('category') || col.toLowerCase().includes('type')) {
          const categories = ['Category A', 'Category B', 'Category C', 'Category D']
          row[col] = categories[i % categories.length]
        } else if (col.toLowerCase().includes('value') || col.toLowerCase().includes('amount') || col.toLowerCase().includes('score')) {
          row[col] = Math.floor(Math.random() * 100) + 20
        } else {
          row[col] = `Item ${i + 1}`
        }
      })
      
      sampleData.push(row)
    }
    
    return sampleData
  }

  const generateSampleChartData = (datasetInfo: any) => {
    const columns = datasetInfo.columns || []
    const sampleData: any[] = []

    for (let i = 0; i < Math.min(10, datasetInfo.row_count); i++) {
      const row: any = {}
      columns.forEach((col: any) => {
        if (col.is_numeric) {
          const min = col.min || 0
          const max = col.max || 100
          row[col.name] = Math.floor(Math.random() * (max - min + 1)) + min
        } else if (col.is_categorical) {
          const values = col.sample_values || ['A', 'B', 'C']
          row[col.name] = values[Math.floor(Math.random() * values.length)]
        } else {
          const values = col.sample_values || ['Sample']
          row[col.name] = values[Math.floor(Math.random() * values.length)]
        }
      })
      sampleData.push(row)
    }

    return sampleData
  }

  const generateBasicCharts = (dataset: Dataset) => {
    // Business User - Simple, understandable language
      return [
        {
          chart_type: "bar_chart",
          title: "Top Categories",
          description: "See which categories have the most data",
          fields: ["category", "value"],
          isInitial: true,
          size: "large"
        },
        {
          chart_type: "pie_chart",
          title: "Data Split",
          description: "How your data is divided across different groups",
          fields: ["category", "count"],
          isInitial: true,
          size: "medium"
        },
        {
          chart_type: "line_chart",
          title: "Trend Over Time",
          description: "Watch how your data changes over time",
          fields: ["index", "value"],
          isInitial: true,
          size: "large"
        },
        {
          chart_type: "bar_chart",
          title: "Quick Summary",
          description: "A simple overview of your main data points",
          fields: ["category", "value"],
          isInitial: true,
          size: "small"
        }
      ]
    }
  }

  const generateAIRecommendedCharts = (dataset: Dataset) => {
    // Business User - Simple AI recommendations
      return [
        {
          chart_type: "scatter_plot",
          title: "Smart Insights",
          description: "AI found interesting connections in your data",
          fields: ["x", "y"],
          isAIRecommended: true,
          size: "large"
        },
        {
          chart_type: "bar_chart",
          title: "Hidden Patterns",
          description: "AI discovered patterns you might have missed",
          fields: ["category", "value"],
          isAIRecommended: true,
          size: "medium"
        },
        {
          chart_type: "line_chart",
          title: "Future Trends",
          description: "AI predicts where your data is heading",
          fields: ["index", "value"],
          isAIRecommended: true,
          size: "large"
        },
        {
          chart_type: "pie_chart",
          title: "Key Segments",
          description: "AI identified the most important data groups",
          fields: ["category", "count"],
          isAIRecommended: true,
          size: "small"
        }
      ]
    }

  const generateSampleData = (dataset: Dataset) => {
    // Use dataset ID as seed for consistent data generation
    const seed = dataset.id.charCodeAt(0) + dataset.id.charCodeAt(1)
    const sampleData: any[] = []

    for (let i = 0; i < Math.min(15, dataset.row_count); i++) {
      // Use seeded random for consistent data
      const seededRandom = (seed + i) % 100 / 100
      const categories = ['Category A', 'Category B', 'Category C', 'Category D']

      sampleData.push({
        category: categories[i % categories.length],
        value: Math.floor(seededRandom * 80) + 20, // 20-100 range
        index: i,
        count: Math.floor(seededRandom * 40) + 10, // 10-50 range
        x: Math.floor(seededRandom * 100),
        y: Math.floor(seededRandom * 100),
        range: `${i * 10}-${(i + 1) * 10}`
      })
    }
    return sampleData
  }

  const loadDatasets = async () => {
    try {
      const response = await axios.get('http://localhost:8000/datasets')
      const datasets = response.data
      console.log('Loaded datasets:', datasets)
      setDatasets(datasets)

      // Auto-select the first dataset if available
      if (datasets.length > 0 && !selectedDataset) {
        console.log('Auto-selecting first dataset:', datasets[0])
        setSelectedDataset(datasets[0])
      } else if (datasets.length > 0) {
        console.log('Dataset already selected:', selectedDataset?.filename)
      } else {
        console.log('No datasets available')
      }
    } catch (error) {
      console.error('Failed to load datasets:', error)
    } finally {
      setLoading(false)
    }
  }

  // Calculate metrics from selected dataset or overall
  const totalDatasets = datasets.length
  const totalRows = selectedDataset ? selectedDataset.row_count : datasets.reduce((sum, dataset) => sum + dataset.row_count, 0)
  const totalSize = selectedDataset ? selectedDataset.size : datasets.reduce((sum, dataset) => sum + dataset.size, 0)
  const recentUploads = datasets.filter(dataset => {
    const uploadDate = new Date(dataset.upload_date)
    const thirtyDaysAgo = new Date()
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
    return uploadDate > thirtyDaysAgo
  }).length

  const metrics: MetricCard[] = selectedDataset ? [
      title: 'Dataset Rows',
      value: totalRows.toLocaleString(),
      change: 0,
      changeType: 'positive',
      icon: BarChart3,
      color: 'primary'
    },
      title: 'Columns',
      value: selectedDataset.column_count.toString(),
      change: 0,
      changeType: 'positive',
      icon: Database,
      color: 'success'
    },
      title: 'File Size',
      value: `${(totalSize / 1024 / 1024).toFixed(1)} MB`,
      change: 0,
      changeType: 'positive',
      icon: Activity,
      color: 'warning'
    },
      title: 'Data Quality',
      value: '85%',
      change: 0,
      changeType: 'positive',
      icon: PieChart,
      color: 'accent'
    }
  ] : [
      title: 'Total Datasets',
      value: totalDatasets.toLocaleString(),
      change: 12.5,
      changeType: 'positive',
      icon: Database,
      color: 'primary'
    },
      title: 'Total Rows',
      value: totalRows.toLocaleString(),
      change: 8.3,
      changeType: 'positive',
      icon: BarChart3,
      color: 'success'
    },
      title: 'Data Size',
      value: `${(totalSize / 1024 / 1024).toFixed(1)} MB`,
      change: -2.1,
      changeType: 'negative',
      icon: Activity,
      color: 'warning'
    },
      title: 'Recent Uploads',
      value: recentUploads.toString(),
      change: 15.7,
      changeType: 'positive',
      icon: Upload,
      color: 'accent'
    }
  ]

  const recentDatasets = datasets.slice(0, 5)

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const getMetricIcon = (metric: MetricCard) => {
    const IconComponent = metric.icon
    return (
      <div className={`p-3 rounded-lg bg-${metric.color}-100`}>
        <IconComponent className={`h-6 w-6 text-${metric.color}-600`} />
      </div>
    )
  }

  const getChangeIcon = (changeType: 'positive' | 'negative') => {
    return changeType === 'positive' ? (
      <ArrowUpRight className="h-4 w-4 text-success-600" />
    ) : (
      <ArrowDownRight className="h-4 w-4 text-error-600" />
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
/* Header */}
        <div className="rounded-lg shadow-sm border p-6 mb-8 bg-white border-gray-200">
        <div className="flex items-center justify-between">
          <div>
              <h1 className="text-2xl font-semibold text-gray-900">
                Data Analysis Dashboard
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                Analyze your datasets with AI-powered insights and visualizations
        </p>
      </div>
              <div className="flex items-center space-x-4">
              <DatasetSelector
                datasets={datasets}
                selectedDataset={selectedDataset}
                onDatasetSelect={handleDatasetSelect}
                onPreviewDataset={handlePreviewDataset}
              />
              <button
                onClick={() => setIsUploadModalOpen(true)}
                className={`
                  inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white transition-colors duration-200
                  ${true 
                    ? 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500' 
                    : 'bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-600 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500'
                  }
                `}
              >
                <CloudUpload className="h-4 w-4 mr-2" />
                Upload Dataset
              </button>
          </div>
        </div>
      </div>

/* Metrics Overview */}
selectedDataset && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <StatisticalSummaryCard
              title="Dataset Rows"
              value={totalRows.toLocaleString()}
              change="+12.5%"
              trend="up"
              icon={BarChart3}
              description="Total data points"
              true={true}
            />
            <StatisticalSummaryCard
              title="Columns"
              value={selectedDataset.column_count.toString()}
              change="+2"
              trend="up"
              icon={Database}
              description="Data dimensions"
              true={true}
            />
            <StatisticalSummaryCard
              title="File Size"
              value={`${(totalSize / 1024 / 1024).toFixed(1)} MB`}
              change="-2.1%"
              trend="down"
              icon={Activity}
              description="Storage used"
              true={true}
            />
            <StatisticalSummaryCard
              title="Data Quality"
              value="85%"
              change="+5.2%"
              trend="up"
              icon={Shield}
              description="Overall quality score"
              true={true}
            />
          </div>
        )}

/* Main Content */}
        <div className="space-y-6">
selectedDataset ? (
            <>
/* Expert Layout with Side Panels */}
!true && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
/* Main Content Area */}
                  <div className="lg:col-span-2 space-y-6">
/* Data Quality Panel */}
                    <DataQualityPanel
                      score={85}
                      issues={[
 type: 'warning', message: 'Missing values detected', count: 12 },
 type: 'info', message: 'Outliers found in numeric columns', count: 3 },
 type: 'error', message: 'Inconsistent date formats', count: 5 }
                      ]}
                      true={true}
                    />
                    
/* Advanced Analytics */}
                    <AdvancedAnalytics
                      data={datasetData}
                      fields={selectedDataset?.columns || ['category', 'value', 'x', 'y']}
                      true={true}
                      onExport={() => setIsExportModalOpen(true)}
                      onShare={() => setIsExportModalOpen(true)}
                    />
                  </div>
                  
/* Side Panel */}
                  <div className="space-y-6">
                    <QuickActionsPanel
                      true={true}
                      onUpload={() => setIsUploadModalOpen(true)}
                      onExport={() => setIsExportModalOpen(true)}
                      onRefresh={() => selectedDataset && analyzeDataset(selectedDataset)}
                      onSettings={() => console.log('Settings clicked')}
                      onAnalyze={() => console.log('Analyze clicked')}
                      onVisualize={() => console.log('Visualize clicked')}
                      onExportCode={() => console.log('Export code clicked')}
                      onShare={() => console.log('Share clicked')}
                    />
                  </div>
                </div>
              )}

/* Data Visualizations */}
visualizationRecommendations.length > 0 ? (
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">
showAIRecommendations ? 'AI Recommended Visualizations' : 'Data Visualizations'}
                      </h3>
                      <p className="text-sm text-gray-600 mt-1">
showAIRecommendations 
                          ? 'AI-powered insights tailored to your data patterns'
                          : 'Key insights and patterns from your dataset'
                        }
                      </p>
                    </div>
                    <div className="flex items-center space-x-3">
!showAIRecommendations && (
                        <button
                          onClick={handleAIRecommendation}
                          disabled={analyzing}
                          className={`inline-flex items-center px-4 py-2 rounded-md text-sm font-medium transition-colors duration-200 ${
                            analyzing
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              : 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm hover:shadow-md'
                          }`}
                        >
analyzing ? (
                            <>
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-400 mr-2"></div>
                              Analyzing...
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-4 w-4 mr-2" />
                              Get AI Insights
                            </>
                          )}
                        </button>
                      )}
                      <Link
                        to="/charts"
                        className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors duration-200"
                      >
                        View All Charts
                        <ArrowUpRight className="h-4 w-4 ml-2" />
                      </Link>
                    </div>
                  </div>

/* Charts Grid */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
((showAIRecommendations ? aiRecommendedCharts : visualizationRecommendations) || []).length > 0 ? 
                      (showAIRecommendations ? aiRecommendedCharts : visualizationRecommendations).map((rec, index) => {
                      console.log(`Rendering chart ${index}:`, {
                        chartType: rec.chartType || rec.chart_type,
                        dataLength: rec.data?.length || 0,
                        fields: rec.fields,
                        sampleData: rec.data?.slice(0, 2)
                      })

                      return (
                        <ModernChartContainer
                          key={`${rec.chartType || rec.chart_type}-${index}`}
                          title={rec.title || `${rec.chartType || rec.chart_type} Chart`}
                          chartType={rec.chartType || rec.chart_type}
                          true={true}
                          onExport={() => console.log('Export chart')}
                          onSettings={() => console.log('Chart settings')}
                          onMaximize={() => console.log('Maximize chart')}
                        >
                          <div className="h-80">
                            <DataVisualization
                              chartType={rec.chartType || rec.chart_type}
                              data={rec.data || datasetData}
                              fields={rec.fields}
                              showChat={true}
                              showRecommendations={false}
                              datasetContext={`Dataset: ${selectedDataset?.filename}, Rows: ${selectedDataset?.row_count}`}
                            />
                          </div>
                        </ModernChartContainer>
                      )
                    }) : (
                      <div className="col-span-full flex items-center justify-center h-64">
                        <div className="text-center">
                          <BarChart3 className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                          <p className="text-gray-500">No charts available. Please select a dataset or try again.</p>
                        </div>
                      </div>
                    )}
                  </div>

showAIRecommendations && (
                    <div className="text-center">
                      <button
                        onClick={() => setShowAIRecommendations(false)}
                        className="text-gray-600 hover:text-gray-800 text-sm font-medium"
                      >
                        ← Back to Initial Charts
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                  <div className="text-center py-8">
                    <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-2" />
                    <p className="text-gray-500">Generating visualizations...</p>
                    <p className="text-sm text-gray-400 mt-1">
                      Recommendations: {visualizationRecommendations.length}, Data: {datasetData.length} rows
                    </p>
selectedDataset && (
                      <button
                        onClick={() => analyzeDataset(selectedDataset)}
                        className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                      >
                        Retry Analysis
                      </button>
                    )}
                  </div>
                </div>
              )}

/* Dataset Analysis - Moved Below Charts */}
analysisResult && (
                <div className={`${isDarkTheme ? 'bg-slate-800/90 backdrop-blur-xl border-slate-700' : 'bg-white/95 backdrop-blur-xl border-gray-200'} rounded-2xl p-6 shadow-lg border relative z-0 hover:shadow-xl transition-all duration-300`}>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className={`text-lg font-semibold ${isDarkTheme ? 'text-white' : 'text-sky-900'}`}>
true ?
                        `What ${analysisResult.dataset.filename} tells us` :
                        `Analysis for ${analysisResult.dataset.filename}`
                      }
                    </h3>
analyzing && (
                      <div className={`flex items-center space-x-2 ${isDarkTheme ? 'text-sky-400' : 'text-sky-600'}`}>
                        <div className={`animate-spin rounded-full h-4 w-4 border-b-2 ${isDarkTheme ? 'border-sky-400' : 'border-sky-600'}`}></div>
                        <span className="text-sm">Analyzing...</span>
                      </div>
                    )}
                  </div>

                  <div className="space-y-4">
                    <div className={`p-4 rounded-xl bg-gradient-to-r ${true
                      ? (isDarkTheme ? 'from-green-500/20 to-emerald-500/20 border-green-500/30' : 'from-green-500/20 to-emerald-500/20 border-green-500/30')
                      : (isDarkTheme ? 'from-sky-500/20 to-cyan-500/20 border-sky-500/30' : 'from-sky-500/20 to-cyan-500/20 border-sky-500/30')
                      } border backdrop-blur-sm`}>
                      <h4 className={`font-medium mb-2 ${true
                        ? (isDarkTheme ? 'text-green-300' : 'text-green-700')
                        : (isDarkTheme ? 'text-sky-300' : 'text-sky-700')
                        }`}>
true ? 'Key Insights' : 'AI Analysis'}
                      </h4>
                      <p className={true
                        ? (isDarkTheme ? 'text-green-200' : 'text-green-800')
                        : (isDarkTheme ? 'text-sky-200' : 'text-sky-800')
                      }>
true ?
                          `Your ${analysisResult.dataset.filename} file has ${analysisResult.dataset.row_count} rows of data. This looks like a solid dataset that can help you make better business decisions. Here's what we found:` :
                          analysisResult.analysis.response
                        }
                      </p>
        </div>

                    <div className={`flex items-center justify-between text-sm ${isDarkTheme ? 'text-gray-300' : 'text-sky-700'}`}>
                      <span>
true ?
                          `Data Quality: ${Math.round(analysisResult.analysis.confidence * 100)}%` :
                          `Confidence: ${Math.round(analysisResult.analysis.confidence * 100)}%`
                        }
                      </span>
                      <span>
true ?
                          'Analysis Method: Automated' :
                          `Reasoning: ${analysisResult.analysis.reasoning}`
                        }
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            /* No Dataset Selected */
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-gray-900">Data Overview</h3>
                <div className="flex items-center space-x-2">
                  <button className="p-2 text-gray-400 hover:text-gray-600">
                    <RefreshCw className="h-4 w-4" />
                  </button>
                  <button className="p-2 text-gray-400 hover:text-gray-600">
                    <Maximize2 className="h-4 w-4" />
                  </button>
                </div>
          </div>
          
              <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg">
                <div className="text-center">
                  <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-2" />
                  <p className="text-gray-500">Select a dataset to see visualizations</p>
                </div>
              </div>
            </div>
          )}

/* Recent Datasets */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-gray-900">Recent Datasets</h3>
                <Link to="/datasets" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
                  View all
                </Link>
          </div>
          
recentDatasets.length > 0 ? (
                <div className="space-y-4">
recentDatasets.map((dataset) => (
                    <div key={dataset.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-primary-100 rounded-lg">
                          <Database className="h-4 w-4 text-primary-600" />
                        </div>
                        <div>
                          <h4 className="font-medium text-gray-900">{dataset.filename}</h4>
                          <p className="text-sm text-gray-500">
dataset.row_count.toLocaleString()} rows • {dataset.column_count} columns
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-sm text-gray-500">{formatFileSize(dataset.size)}</span>
                        <button className="p-1 text-gray-400 hover:text-gray-600">
                          <Eye className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Database className="h-12 w-12 text-gray-400 mx-auto mb-2" />
                  <p className="text-gray-500">No datasets uploaded yet</p>
                  <Link to="/datasets" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
                    Upload your first dataset
                  </Link>
                </div>
              )}
            </div>
              </div>
            </div>

/* Upload Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />

/* Data Preview Modal */}
      <DataPreview
        data={previewData}
        datasetName={previewDataset?.filename || ''}
        isOpen={isPreviewOpen}
        onClose={handlePreviewClose}
        isDarkTheme={isDarkTheme}
      />

/* Export Modal */}
      <ExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        data={datasetData}
        analysisResults={analysisResult}
        true={true}
      />
    </div>
  )
}

export default Dashboard
