import React, { useState, useEffect } from 'react'
import { Lightbulb,Star, Brain, BarChart3, TrendingUp, Database, Play, Download, RefreshCw, MessageSquare, Zap, Target, BarChart, PieChart, LineChart, ChartScatter, Filter, Search, ChevronDown, ChevronRight, Loader2, AlertCircle, CheckCircle, Info, Send, X, Maximize2, Minimize2 } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import toast from 'react-hot-toast'
import PlotlyChart from '../components/PlotlyChart'

const Analysis = () => {
  const [selectedDataset, setSelectedDataset] = useState(null)
  const [datasets, setDatasets] = useState([])
  const [analysisType, setAnalysisType] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisResults, setAnalysisResults] = useState([])
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedChart, setSelectedChart] = useState(null)
  const [showChartModal, setShowChartModal] = useState(false)
  const [analysisProgress, setAnalysisProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState('')
  const [insights, setInsights] = useState([])
  const [selectedInsightCategory, setSelectedInsightCategory] = useState('all')
  const [showInsights, setShowInsights] = useState(false)
  const { user } = useAuth()

  // Analysis types with advanced capabilities
  const analysisTypes = [
    { 
      id: 'correlation', 
      name: 'Correlation Analysis', 
      description: 'Find relationships between variables',
      icon: ChartScatter,
      color: 'blue',
      features: ['Pearson correlation', 'Spearman correlation', 'Heatmap visualization', 'Significance testing']
    },
    { 
      id: 'trend', 
      name: 'Trend Analysis', 
      description: 'Identify patterns over time',
      icon: LineChart,
      color: 'green',
      features: ['Time series decomposition', 'Seasonality detection', 'Trend forecasting', 'Anomaly detection']
    },
    { 
      id: 'distribution', 
      name: 'Distribution Analysis', 
      description: 'Analyze data distribution patterns',
      icon: BarChart,
      color: 'purple',
      features: ['Histogram analysis', 'Box plot generation', 'Normality testing', 'Skewness & kurtosis']
    },
    { 
      id: 'outlier', 
      name: 'Outlier Detection', 
      description: 'Find unusual data points',
      icon: AlertCircle,
      color: 'red',
      features: ['IQR method', 'Z-score analysis', 'Isolation forest', 'Visual outlier detection']
    },
    { 
      id: 'clustering', 
      name: 'Clustering Analysis', 
      description: 'Group similar data points',
      icon: Target,
      color: 'orange',
      features: ['K-means clustering', 'Hierarchical clustering', 'DBSCAN', 'Cluster validation']
    },
    { 
      id: 'regression', 
      name: 'Regression Analysis', 
      description: 'Predict relationships between variables',
      icon: TrendingUp,
      color: 'teal',
      features: ['Linear regression', 'Polynomial regression', 'Ridge/Lasso', 'Model validation']
    }
  ]

  // Load datasets on mount
  useEffect(() => {
    loadDatasets()
  }, [])

  const loadDatasets = async () => {
    try {
      setIsLoading(true)
      const response = await axios.get('/api/datasets')
      const datasetsData = response.data.datasets || []
      setDatasets(datasetsData)
      
      if (datasetsData.length > 0) {
        setSelectedDataset(datasetsData[0])
      }
    } catch (error) {
      console.error('Error loading datasets:', error)
      toast.error('Failed to load datasets')
    } finally {
      setIsLoading(false)
    }
  }

  const handleAnalyze = async () => {
    if (!selectedDataset || !analysisType) {
      toast.error('Please select a dataset and analysis type')
      return
    }

    try {
      setIsAnalyzing(true)
      setAnalysisProgress(0)
      setCurrentStep('Initializing analysis...')
      
      // Simulate analysis progress
      const progressSteps = [
        'Loading dataset...',
        'Preprocessing data...',
        'Running statistical analysis...',
        'Generating visualizations...',
        'Computing insights...',
        'Finalizing results...'
      ]

      for (let i = 0; i < progressSteps.length; i++) {
        setCurrentStep(progressSteps[i])
        setAnalysisProgress((i + 1) * 16.67)
        await new Promise(resolve => setTimeout(resolve, 500))
      }

      // Call analysis API
      const response = await axios.post('/api/analysis/run', {
        dataset_id: selectedDataset.id,
        analysis_type: analysisType,
        parameters: getAnalysisParameters()
      })

      setAnalysisResults(response.data.results || [])
      setCurrentStep('Analysis complete!')
      setAnalysisProgress(100)
      
      // Generate insights from analysis results
      await generateInsightsFromResults(response.data.results || [])
      
      toast.success('Analysis completed successfully!')
      
    } catch (error) {
      console.error('Error running analysis:', error)
      toast.error('Analysis failed. Please try again.')
    } finally {
      setIsAnalyzing(false)
      setTimeout(() => {
        setCurrentStep('')
        setAnalysisProgress(0)
      }, 2000)
    }
  }

  const getAnalysisParameters = () => {
    const params = {
      correlation: { method: 'pearson', significance_level: 0.05 },
      trend: { window_size: 7, seasonality: true },
      distribution: { bins: 30, test_normality: true },
      outlier: { method: 'iqr', threshold: 1.5 },
      clustering: { n_clusters: 3, algorithm: 'kmeans' },
      regression: { degree: 1, regularization: 'none' }
    }
    return params[analysisType] || {}
  }

  const handleChatSubmit = async (e) => {
    e.preventDefault()
    if (!chatInput.trim() || !selectedDataset) return

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: chatInput,
      timestamp: new Date()
    }

    setChatMessages(prev => [...prev, userMessage])
    setChatInput('')

    try {
      const response = await axios.post(`/api/datasets/${selectedDataset.id}/chat`, {
        message: chatInput
      })

      const aiMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: response.data.response || 'I apologize, but I could not process your query.',
        confidence: response.data.confidence || 0.5,
        timestamp: new Date(),
        suggestions: response.data.suggested_actions || [],
        chart: response.data.chart || null
      }

      setChatMessages(prev => [...prev, aiMessage])
      
      // If there's a chart recommendation, show it
      if (response.data.chart) {
        setMainChart(response.data.chart)
        toast.success('Chart generated based on your query!')
      }
      
    } catch (error) {
      console.error('Error processing chat query:', error)
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: 'Sorry, I encountered an error processing your query. Please try again.',
        timestamp: new Date()
      }
      setChatMessages(prev => [...prev, errorMessage])
    }
  }

  const handleViewChart = (chart) => {
    setSelectedChart(chart)
    setShowChartModal(true)
  }

  const getAnalysisIcon = (type) => {
    const analysis = analysisTypes.find(a => a.id === type)
    return analysis ? analysis.icon : BarChart3
  }

  const getAnalysisColor = (type) => {
    const analysis = analysisTypes.find(a => a.id === type)
    return analysis ? analysis.color : 'blue'
  }

  const generateInsightsFromResults = async (results) => {
    try {
      const generatedInsights = []
      
      results.forEach((result, index) => {
        // Generate insights based on analysis type
        if (result.type === 'correlation') {
          if (result.insights && result.insights.length > 0) {
            result.insights.forEach((insight, i) => {
              generatedInsights.push({
                id: `corr_${index}_${i}`,
                title: `Strong Correlation Found: ${insight.variable1} ↔ ${insight.variable2}`,
                category: 'trends',
                type: 'positive',
                confidence: Math.abs(insight.correlation) * 100,
                description: `Correlation coefficient of ${insight.correlation.toFixed(3)} indicates a ${Math.abs(insight.correlation) > 0.7 ? 'strong' : 'moderate'} relationship`,
                impact: Math.abs(insight.correlation) > 0.7 ? 'high' : 'medium',
                date: 'Just now',
                dataset: selectedDataset?.name || 'Current Dataset',
                tags: ['correlation', 'relationship', 'statistical'],
                isStarred: Math.abs(insight.correlation) > 0.8,
                analysisResult: result
              })
            })
          }
        } else if (result.type === 'trend') {
          if (result.insights && result.insights.length > 0) {
            result.insights.forEach((insight, i) => {
              const trendDirection = insight.value > 0 ? 'increasing' : 'decreasing'
              generatedInsights.push({
                id: `trend_${index}_${i}`,
                title: `${trendDirection.charAt(0).toUpperCase() + trendDirection.slice(1)} Trend Detected`,
                category: 'trends',
                type: insight.value > 0 ? 'positive' : 'negative',
                confidence: Math.min(95, Math.abs(insight.value) * 100),
                description: `Data shows ${trendDirection} trend with slope of ${insight.value.toFixed(4)}`,
                impact: Math.abs(insight.value) > 0.1 ? 'high' : 'medium',
                date: 'Just now',
                dataset: selectedDataset?.name || 'Current Dataset',
                tags: ['trend', 'time-series', 'slope'],
                isStarred: Math.abs(insight.value) > 0.2,
                analysisResult: result
              })
            })
          }
        } else if (result.type === 'outlier') {
          if (result.insights && result.insights.length > 0) {
            result.insights.forEach((insight, i) => {
              generatedInsights.push({
                id: `outlier_${index}_${i}`,
                title: `Outliers Detected: ${insight.value} data points`,
                category: 'anomalies',
                type: insight.value > 10 ? 'warning' : 'info',
                confidence: 85,
                description: `${insight.interpretation} - These outliers may need investigation`,
                impact: insight.value > 10 ? 'high' : 'medium',
                date: 'Just now',
                dataset: selectedDataset?.name || 'Current Dataset',
                tags: ['outlier', 'anomaly', 'data-quality'],
                isStarred: insight.value > 20,
                analysisResult: result
              })
            })
          }
        } else if (result.type === 'distribution') {
          if (result.insights && result.insights.length > 0) {
            result.insights.forEach((insight, i) => {
              generatedInsights.push({
                id: `dist_${index}_${i}`,
                title: `Distribution Analysis: ${insight.metric}`,
                category: 'recommendations',
                type: 'info',
                confidence: 80,
                description: `${insight.interpretation}`,
                impact: 'medium',
                date: 'Just now',
                dataset: selectedDataset?.name || 'Current Dataset',
                tags: ['distribution', 'statistics', 'analysis'],
                isStarred: false,
                analysisResult: result
              })
            })
          }
        }
      })
      
      setInsights(generatedInsights)
      setShowInsights(true)
      
    } catch (error) {
      console.error('Error generating insights:', error)
    }
  }

  const insightCategories = [
    { id: 'all', name: 'All Insights', count: insights.length },
    { id: 'trends', name: 'Trends', count: insights.filter(i => i.category === 'trends').length },
    { id: 'anomalies', name: 'Anomalies', count: insights.filter(i => i.category === 'anomalies').length },
    { id: 'recommendations', name: 'Recommendations', count: insights.filter(i => i.category === 'recommendations').length },
    { id: 'predictions', name: 'Predictions', count: insights.filter(i => i.category === 'predictions').length }
  ]

  const filteredInsights = insights.filter(insight => {
    const matchesCategory = selectedInsightCategory === 'all' || insight.category === selectedInsightCategory
    return matchesCategory
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-gray-900 to-slate-800 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400 mx-auto mb-4" />
          <p className="text-slate-300">Loading analysis tools...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-gray-900 to-slate-800">
      <div className="flex h-screen">
        {/* Main Content Area */}
        <div className={`flex-1 flex flex-col transition-all duration-300 ${isChatOpen ? 'mr-96' : ''}`}>
          {/* Header */}
          <div className="p-6 border-b border-slate-700/50">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-white">Advanced Data Analysis</h1>
                <p className="text-slate-300 mt-1">
                  Comprehensive statistical analysis and AI-powered insights
                </p>
              </div>
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setShowInsights(!showInsights)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                    showInsights 
                      ? 'bg-emerald-600 text-white' 
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  <Lightbulb className="w-4 h-4" />
                  <span>Insights ({insights.length})</span>
                </button>
                <button
                  onClick={() => setIsChatOpen(!isChatOpen)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                    isChatOpen 
                      ? 'bg-emerald-600 text-white' 
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>AI Chat</span>
                </button>
              </div>
            </div>
          </div>

          {/* Scrollable Content */}
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-7xl mx-auto space-y-6">

        {/* Analysis Configuration */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Configuration Panel */}
          <div className="lg:col-span-1">
            <div className="bg-gradient-to-br from-slate-800/90 to-gray-800/90 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10">
              <h2 className="text-lg font-semibold text-white mb-4">Analysis Configuration</h2>
              
              {/* Dataset Selection */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Select Dataset
                </label>
                <select
                  value={selectedDataset?.id || ''}
                  onChange={(e) => {
                    const dataset = datasets.find(d => d.id === e.target.value)
                    setSelectedDataset(dataset)
                  }}
                  className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-slate-200 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  <option value="">Choose a dataset...</option>
                  {datasets.map((dataset) => (
                    <option key={dataset.id} value={dataset.id}>
                      {dataset.name} ({dataset.row_count?.toLocaleString() || 0} records)
                    </option>
                  ))}
                </select>
              </div>

              {/* Analysis Type Selection */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Analysis Type
                </label>
                <div className="space-y-2">
                  {analysisTypes.map((type) => {
                    const Icon = type.icon
                    return (
                      <div
                        key={type.id}
                        onClick={() => setAnalysisType(type.id)}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          analysisType === type.id
                            ? 'border-emerald-500 bg-emerald-500/10'
                            : 'border-slate-600 bg-slate-700/30 hover:bg-slate-700/50'
                        }`}
                      >
                        <div className="flex items-center space-x-3">
                          <Icon className={`w-5 h-5 text-${type.color}-400`} />
                          <div className="flex-1">
                            <h3 className="text-sm font-medium text-slate-200">{type.name}</h3>
                            <p className="text-xs text-slate-400">{type.description}</p>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Run Analysis Button */}
              <button
                onClick={handleAnalyze}
                disabled={!selectedDataset || !analysisType || isAnalyzing}
                className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    <span>Run Analysis</span>
                  </>
                )}
              </button>

              {/* Analysis Progress */}
              {isAnalyzing && (
                <div className="mt-4">
                  <div className="flex items-center justify-between text-sm text-slate-300 mb-2">
                    <span>{currentStep}</span>
                    <span>{Math.round(analysisProgress)}%</span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <div 
                      className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${analysisProgress}%` }}
                    ></div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Results Panel */}
          <div className="lg:col-span-2">
            <div className="bg-gradient-to-br from-slate-800/90 to-gray-800/90 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10">
              <h2 className="text-lg font-semibold text-white mb-4">Analysis Results</h2>
              
              {analysisResults.length > 0 ? (
                <div className="space-y-4">
                  {analysisResults.map((result, index) => (
                    <div key={index} className="bg-slate-700/30 rounded-lg p-4 border border-slate-600/20">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          {React.createElement(getAnalysisIcon(result.type), { 
                            className: `w-5 h-5 text-${getAnalysisColor(result.type)}-400` 
                          })}
                          <h3 className="text-slate-200 font-medium">{result.title}</h3>
                        </div>
                        <button
                          onClick={() => handleViewChart(result)}
                          className="p-2 text-slate-400 hover:text-emerald-400 transition-colors"
                        >
                          <Maximize2 className="w-4 h-4" />
                        </button>
                      </div>
                      
                      <p className="text-slate-300 text-sm mb-3">{result.description}</p>
                      
                      {result.chart && (
                        <div className="h-64 mb-3">
                          <PlotlyChart
                            data={result.chart.data}
                            layout={result.chart.layout}
                            config={result.chart.config}
                          />
                        </div>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Confidence: {Math.round(result.confidence * 100)}%</span>
                        <span>Type: {result.type}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <div className="p-4 bg-slate-700/50 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                    <BarChart3 className="w-8 h-8 text-slate-400" />
                  </div>
                  <h3 className="text-lg font-medium text-white mb-2">No Analysis Results</h3>
                  <p className="text-slate-400">
                    Select a dataset and analysis type, then click "Run Analysis" to get started.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Insights Panel */}
        {showInsights && (
          <div className="bg-gradient-to-br from-slate-800/90 to-gray-800/90 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white flex items-center">
                <Lightbulb className="w-5 h-5 mr-2 text-emerald-400" />
                Analysis Insights ({insights.length})
              </h2>
              <button
                onClick={() => setShowInsights(false)}
                className="p-2 text-slate-400 hover:text-slate-200 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            {/* Insight Categories */}
            <div className="flex flex-wrap gap-2 mb-6">
              {insightCategories.map((category) => (
                <button
                  key={category.id}
                  onClick={() => setSelectedInsightCategory(category.id)}
                  className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                    selectedInsightCategory === category.id
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {category.name} ({category.count})
                </button>
              ))}
            </div>
            
            {/* Insights List */}
            <div className="space-y-4 max-h-96 overflow-y-auto">
              {filteredInsights.length > 0 ? (
                filteredInsights.map((insight) => (
                  <div
                    key={insight.id}
                    className="bg-slate-700/30 rounded-lg p-4 border border-slate-600/20 hover:bg-slate-700/50 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-3">
                        <div className={`p-2 rounded-lg ${
                          insight.type === 'positive' ? 'bg-green-500/20' :
                          insight.type === 'negative' ? 'bg-red-500/20' :
                          insight.type === 'warning' ? 'bg-yellow-500/20' :
                          'bg-blue-500/20'
                        }`}>
                          {insight.type === 'positive' ? <CheckCircle className="w-4 h-4 text-green-400" /> :
                           insight.type === 'negative' ? <AlertTriangle className="w-4 h-4 text-red-400" /> :
                           insight.type === 'warning' ? <AlertTriangle className="w-4 h-4 text-yellow-400" /> :
                           <Info className="w-4 h-4 text-blue-400" />}
                        </div>
                        <div className="flex-1">
                          <h3 className="text-slate-200 font-medium text-sm">{insight.title}</h3>
                          <p className="text-slate-400 text-xs mt-1">{insight.description}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        {insight.isStarred && <Star className="w-4 h-4 text-yellow-400 fill-current" />}
                        <span className="text-xs text-slate-400">{insight.confidence}%</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <div className="flex items-center space-x-4">
                        <span className={`px-2 py-1 rounded ${
                          insight.impact === 'high' ? 'bg-red-500/20 text-red-300' :
                          insight.impact === 'medium' ? 'bg-yellow-500/20 text-yellow-300' :
                          'bg-green-500/20 text-green-300'
                        }`}>
                          {insight.impact} impact
                        </span>
                        <span>{insight.date}</span>
                        <span>{insight.dataset}</span>
                      </div>
                      <div className="flex items-center space-x-1">
                        {insight.tags.map((tag, index) => (
                          <span key={index} className="px-2 py-1 bg-slate-600/30 rounded text-xs">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8">
                  <div className="p-4 bg-slate-700/50 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                    <Lightbulb className="w-8 h-8 text-slate-400" />
                  </div>
                  <p className="text-slate-300">No insights available</p>
                  <p className="text-slate-400 text-sm mt-1">Run an analysis to generate insights</p>
                </div>
              )}
            </div>
          </div>
        )}

            </div>
          </div>
        </div>

        {/* AI Chat Sidebar */}
        {isChatOpen && (
          <>
            {/* Overlay */}
            <div 
              className="fixed inset-0 bg-black/20 backdrop-blur-sm z-30"
              onClick={() => setIsChatOpen(false)}
            />
            <div className="fixed right-0 top-0 h-full w-96 bg-gradient-to-b from-slate-800/95 to-gray-800/95 backdrop-blur-sm border-l border-slate-600/20 shadow-2xl shadow-slate-500/10 z-40 transform transition-transform duration-300 ease-in-out">
            <div className="flex flex-col h-full">
              {/* Chat Header */}
              <div className="p-6 border-b border-slate-700/50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-emerald-600/20 rounded-lg">
                      <MessageSquare className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-white">AI Data Assistant</h2>
                      <p className="text-xs text-slate-400">Ask questions about your data</p>
                    </div>
                  </div>
                  <button
                    onClick={() => setIsChatOpen(false)}
                    className="p-2 text-slate-400 hover:text-slate-200 transition-colors rounded-lg hover:bg-slate-700/50"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {chatMessages.length === 0 ? (
                  <div className="text-center py-8">
                    <div className="p-4 bg-slate-700/50 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                      <Brain className="w-8 h-8 text-emerald-400" />
                    </div>
                    <p className="text-slate-300 font-medium">Ask me anything about your data!</p>
                    <p className="text-slate-400 text-sm mt-2">Try asking:</p>
                    <div className="mt-3 space-y-2">
                      <button 
                        onClick={() => setChatInput("What are the main trends in this dataset?")}
                        className="w-full text-xs text-slate-400 bg-slate-700/30 rounded-lg p-2 hover:bg-slate-700/50 transition-colors text-left"
                      >
                        "What are the main trends?"
                      </button>
                      <button 
                        onClick={() => setChatInput("Show correlations between columns")}
                        className="w-full text-xs text-slate-400 bg-slate-700/30 rounded-lg p-2 hover:bg-slate-700/50 transition-colors text-left"
                      >
                        "Show correlations between columns"
                      </button>
                      <button 
                        onClick={() => setChatInput("Create a chart for the data")}
                        className="w-full text-xs text-slate-400 bg-slate-700/30 rounded-lg p-2 hover:bg-slate-700/50 transition-colors text-left"
                      >
                        "Create a chart for the data"
                      </button>
                    </div>
                  </div>
                ) : (
                  chatMessages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                          message.type === 'user'
                            ? 'bg-emerald-600 text-white rounded-br-md'
                            : 'bg-slate-700/50 text-slate-200 rounded-bl-md'
                        }`}
                      >
                        <p className="text-sm leading-relaxed">{message.content}</p>
                        {message.confidence && (
                          <p className="text-xs opacity-70 mt-2">
                            Confidence: {Math.round(message.confidence * 100)}%
                          </p>
                        )}
                        {message.suggestions && message.suggestions.length > 0 && (
                          <div className="mt-3 pt-2 border-t border-slate-600/30">
                            <p className="text-xs font-medium mb-2 text-emerald-300">Suggestions:</p>
                            <ul className="text-xs space-y-1">
                              {message.suggestions.map((suggestion, idx) => (
                                <li key={idx} className="opacity-80">• {suggestion}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Chart Display for Chat */}
              {mainChart && (
                <div className="mx-6 mb-4 p-4 bg-slate-700/30 rounded-xl border border-slate-600/30">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-slate-200">Generated Chart</h4>
                    <button
                      onClick={() => setMainChart(null)}
                      className="text-slate-400 hover:text-slate-200 transition-colors p-1 rounded hover:bg-slate-600/30"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="h-48">
                    <PlotlyChart
                      data={[{
                        x: mainChart.data.map(d => d.x),
                        y: mainChart.data.map(d => d.y),
                        type: mainChart.type === 'scatter_plot' ? 'scatter' : 
                              mainChart.type === 'bar_chart' ? 'bar' :
                              mainChart.type === 'line_chart' ? 'line' :
                              mainChart.type === 'pie_chart' ? 'pie' : 'bar',
                        mode: mainChart.type === 'scatter_plot' ? 'markers' : undefined,
                        name: mainChart.title,
                        marker: { color: '#10b981' }
                      }]}
                      layout={{
                        title: { text: mainChart.title, font: { size: 12, color: '#e2e8f0' } },
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        font: { color: '#e2e8f0', size: 10 },
                        xaxis: { color: '#e2e8f0', gridcolor: 'rgba(148, 163, 184, 0.1)' },
                        yaxis: { color: '#e2e8f0', gridcolor: 'rgba(148, 163, 184, 0.1)' },
                        margin: { t: 30, b: 20, l: 20, r: 20 }
                      }}
                      config={{ displayModeBar: false, responsive: true }}
                    />
                  </div>
                </div>
              )}

              {/* Chat Input */}
              <div className="p-6 border-t border-slate-700/50">
                <form onSubmit={handleChatSubmit} className="flex space-x-3">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask about your data..."
                    className="flex-1 px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-xl text-slate-200 placeholder-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                  />
                  <button
                    type="submit"
                    disabled={!chatInput.trim() || !selectedDataset}
                    className="px-4 py-3 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
                {!selectedDataset && (
                  <p className="text-xs text-slate-500 mt-2 text-center">
                    Select a dataset to start chatting
                  </p>
                )}
              </div>
            </div>
          </div>
          </>
        )}

        {/* Chart Modal */}
        {showChartModal && selectedChart && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] overflow-hidden">
              <div className="flex items-center justify-between p-6 border-b border-slate-600">
                <h3 className="text-xl font-semibold text-white">{selectedChart.title}</h3>
                <button
                  onClick={() => setShowChartModal(false)}
                  className="p-2 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-6 h-96">
                <PlotlyChart
                  data={selectedChart.chart.data}
                  layout={selectedChart.chart.layout}
                  config={selectedChart.chart.config}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Analysis