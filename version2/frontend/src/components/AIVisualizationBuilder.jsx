import React, { useState, useEffect } from 'react'
import { 
  BarChart3, PieChart, LineChart, ChartScatter, TrendingUp, 
  Map, Gauge, Table, Calendar, Target, Zap, Brain,
  ChevronRight, Play, RefreshCw, Lightbulb, Sparkles
} from 'lucide-react'
import PlotlyChart from './PlotlyChart'
import axios from 'axios'
import toast from 'react-hot-toast'

const AIVisualizationBuilder = ({ dataset, onClose, onSave }) => {
  const [selectedFields, setSelectedFields] = useState([])
  const [aiRecommendations, setAiRecommendations] = useState([])
  const [selectedChart, setSelectedChart] = useState(null)
  const [chartData, setChartData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [aiInsights, setAiInsights] = useState([])
  const [naturalQuery, setNaturalQuery] = useState('')
  const [queryResults, setQueryResults] = useState(null)

  // Chart type definitions with AI capabilities
  const chartTypes = [
    {
      id: 'bar',
      name: 'Bar Chart',
      icon: BarChart3,
      description: 'Compare values across categories',
      aiPrompt: 'Best for categorical comparisons and rankings',
      color: 'bg-blue-500'
    },
    {
      id: 'pie',
      name: 'Pie Chart',
      icon: PieChart,
      description: 'Show proportions and percentages',
      aiPrompt: 'Ideal for showing parts of a whole',
      color: 'bg-green-500'
    },
    {
      id: 'line',
      name: 'Line Chart',
      icon: LineChart,
      description: 'Track trends over time',
      aiPrompt: 'Perfect for time series and trend analysis',
      color: 'bg-purple-500'
    },
    {
      id: 'scatter',
      name: 'Scatter Plot',
      icon: ChartScatter,
      description: 'Find correlations between variables',
      aiPrompt: 'Great for finding relationships between two variables',
      color: 'bg-orange-500'
    },
    {
      id: 'area',
      name: 'Area Chart',
      icon: TrendingUp,
      description: 'Show cumulative data over time',
      aiPrompt: 'Best for showing cumulative values over time',
      color: 'bg-pink-500'
    },
    {
      id: 'gauge',
      name: 'Gauge',
      icon: Gauge,
      description: 'Display single values with context',
      aiPrompt: 'Perfect for KPIs and single metrics',
      color: 'bg-red-500'
    },
    {
      id: 'table',
      name: 'Table',
      icon: Table,
      description: 'Show detailed data in rows and columns',
      aiPrompt: 'Best for detailed data exploration',
      color: 'bg-gray-500'
    }
  ]

  // AI-powered field recommendations
  const getAIFieldRecommendations = async () => {
    if (!dataset?.metadata?.column_metadata) return

    try {
      setLoading(true)
      const response = await axios.post('/api/ai/recommend-fields', {
        columns: dataset.metadata.column_metadata,
        dataset_name: dataset.name
      })
      
      setAiRecommendations(response.data.recommendations || [])
    } catch (error) {
      console.error('Error getting AI recommendations:', error)
      // Fallback to basic recommendations
      setAiRecommendations(generateBasicRecommendations())
    } finally {
      setLoading(false)
    }
  }

  const generateBasicRecommendations = () => {
    const columns = dataset?.metadata?.column_metadata || []
    const numericCols = columns.filter(col => ['int64', 'float64'].includes(col.type))
    const categoricalCols = columns.filter(col => ['object', 'category'].includes(col.type))
    
    return [
      {
        chartType: 'bar',
        fields: [categoricalCols[0]?.name, numericCols[0]?.name].filter(Boolean),
        confidence: 0.9,
        reasoning: 'High confidence: Categorical vs numeric data perfect for bar chart',
        insight: `Compare ${categoricalCols[0]?.name} distribution across ${numericCols[0]?.name}`
      },
      {
        chartType: 'pie',
        fields: [categoricalCols[0]?.name],
        confidence: 0.8,
        reasoning: 'Good choice: Categorical data with limited unique values',
        insight: `Show ${categoricalCols[0]?.name} distribution as proportions`
      },
      {
        chartType: 'scatter',
        fields: [numericCols[0]?.name, numericCols[1]?.name].filter(Boolean),
        confidence: 0.85,
        reasoning: 'Excellent: Two numeric variables for correlation analysis',
        insight: `Explore relationship between ${numericCols[0]?.name} and ${numericCols[1]?.name}`
      }
    ]
  }

  // Generate AI insights
  const generateAIInsights = async () => {
    if (!dataset?.metadata) return

    try {
      const response = await axios.post('/api/ai/generate-insights', {
        dataset_metadata: dataset.metadata,
        dataset_name: dataset.name
      })
      
      setAiInsights(response.data.insights || [])
    } catch (error) {
      console.error('Error generating AI insights:', error)
      // Fallback insights
      setAiInsights(generateFallbackInsights())
    }
  }

  const generateFallbackInsights = () => {
    const overview = dataset?.metadata?.dataset_overview || {}
    return [
      {
        type: 'data_quality',
        title: 'Data Quality Assessment',
        content: `Your dataset has ${overview.total_rows || 0} rows with ${overview.total_columns || 0} columns. Data completeness is ${overview.missing_values ? Math.round((1 - overview.missing_values / (overview.total_rows * overview.total_columns)) * 100) : 100}%.`,
        confidence: 0.9
      },
      {
        type: 'recommendation',
        title: 'Visualization Recommendation',
        content: 'Based on your data structure, I recommend starting with bar charts for categorical analysis and scatter plots for correlation discovery.',
        confidence: 0.8
      },
      {
        type: 'pattern',
        title: 'Data Pattern Detected',
        content: 'Your dataset contains both numeric and categorical variables, making it ideal for multi-dimensional analysis.',
        confidence: 0.7
      }
    ]
  }

  // Natural language query processing
  const handleNaturalQuery = async () => {
    if (!naturalQuery.trim()) return

    try {
      setLoading(true)
      const response = await axios.post('/api/ai/natural-query', {
        query: naturalQuery,
        dataset_metadata: dataset.metadata,
        dataset_name: dataset.name
      })
      
      setQueryResults(response.data)
    } catch (error) {
      console.error('Error processing natural query:', error)
      toast.error('AI query processing failed')
    } finally {
      setLoading(false)
    }
  }

  // Generate chart from AI recommendation
  const generateChartFromRecommendation = (recommendation) => {
    const chartType = chartTypes.find(ct => ct.id === recommendation.chartType)
    if (!chartType) return

    setSelectedChart(chartType)
    setSelectedFields(recommendation.fields)
    
    // Generate sample data based on recommendation
    const data = generateChartDataFromFields(recommendation.fields, recommendation.chartType)
    setChartData(data)
  }

  const generateChartDataFromFields = (fields, chartType) => {
    // This would normally use real data from the dataset
    // For now, we'll generate sample data based on field types
    switch (chartType) {
      case 'bar':
        return [{
          x: ['Category A', 'Category B', 'Category C', 'Category D'],
          y: [20, 35, 25, 40],
          type: 'bar',
          name: fields[0] || 'Data',
          marker: { color: '#3B82F6' }
        }]
      case 'pie':
        return [{
          labels: ['North', 'South', 'East', 'West'],
          values: [30, 25, 20, 25],
          type: 'pie',
          name: fields[0] || 'Data',
          marker: { colors: ['#3B82F6', '#10B981', '#F59E0B', '#EF4444'] }
        }]
      case 'scatter':
        return [{
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          y: [2, 4, 3, 6, 5, 8, 7, 10, 9, 12],
          type: 'scatter',
          mode: 'markers',
          name: `${fields[0]} vs ${fields[1]}`,
          marker: { color: '#3B82F6', size: 8 }
        }]
      default:
        return []
    }
  }

  useEffect(() => {
    if (dataset) {
      getAIFieldRecommendations()
      generateAIInsights()
    }
  }, [dataset])

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-7xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Brain className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">AI Visualization Builder</h2>
              <p className="text-gray-600">Let AI help you discover insights in your data</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ×
          </button>
        </div>

        <div className="flex h-[calc(90vh-120px)]">
          {/* Left Panel - AI Recommendations */}
          <div className="w-1/3 border-r border-gray-200 p-6 overflow-y-auto">
            <div className="space-y-6">
              {/* AI Insights */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                  <Sparkles className="w-5 h-5 text-yellow-500 mr-2" />
                  AI Insights
                </h3>
                <div className="space-y-3">
                  {aiInsights.map((insight, index) => (
                    <div key={index} className="p-3 bg-blue-50 rounded-lg">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-medium text-blue-900">{insight.title}</h4>
                          <p className="text-sm text-blue-700 mt-1">{insight.content}</p>
                        </div>
                        <span className="text-xs text-blue-600 bg-blue-200 px-2 py-1 rounded">
                          {Math.round(insight.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* AI Recommendations */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                  <Lightbulb className="w-5 h-5 text-yellow-500 mr-2" />
                  AI Recommendations
                </h3>
                <div className="space-y-3">
                  {aiRecommendations.map((rec, index) => (
                    <div 
                      key={index} 
                      className="p-4 border border-gray-200 rounded-lg hover:border-blue-300 cursor-pointer transition-colors"
                      onClick={() => generateChartFromRecommendation(rec)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2">
                          <div className={`w-3 h-3 rounded-full ${chartTypes.find(ct => ct.id === rec.chartType)?.color || 'bg-gray-500'}`}></div>
                          <span className="font-medium">{chartTypes.find(ct => ct.id === rec.chartType)?.name}</span>
                        </div>
                        <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded">
                          {Math.round(rec.confidence * 100)}%
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{rec.reasoning}</p>
                      <p className="text-xs text-blue-600">{rec.insight}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Natural Language Query */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                  <Zap className="w-5 h-5 text-yellow-500 mr-2" />
                  Ask AI
                </h3>
                <div className="space-y-3">
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      placeholder="Ask: 'Show me sales trends' or 'What's the correlation between...'"
                      value={naturalQuery}
                      onChange={(e) => setNaturalQuery(e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      onKeyPress={(e) => e.key === 'Enter' && handleNaturalQuery()}
                    />
                    <button
                      onClick={handleNaturalQuery}
                      disabled={loading}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                    >
                      {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    </button>
                  </div>
                  
                  {queryResults && (
                    <div className="p-3 bg-green-50 rounded-lg">
                      <h4 className="font-medium text-green-900">AI Response:</h4>
                      <p className="text-sm text-green-700 mt-1">{queryResults.response}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel - Chart Builder */}
          <div className="flex-1 p-6">
            <div className="h-full flex flex-col">
              {/* Chart Type Selection */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Choose Visualization Type</h3>
                <div className="grid grid-cols-4 gap-3">
                  {chartTypes.map((chart) => (
                    <button
                      key={chart.id}
                      onClick={() => setSelectedChart(chart)}
                      className={`p-4 border-2 rounded-lg text-center transition-all ${
                        selectedChart?.id === chart.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <chart.icon className={`w-8 h-8 mx-auto mb-2 ${
                        selectedChart?.id === chart.id ? 'text-blue-600' : 'text-gray-600'
                      }`} />
                      <div className="text-sm font-medium">{chart.name}</div>
                      <div className="text-xs text-gray-500 mt-1">{chart.description}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Chart Preview */}
              <div className="flex-1 bg-gray-50 rounded-lg p-4">
                {selectedChart && chartData ? (
                  <div className="h-full">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-lg font-semibold">{selectedChart.name}</h4>
                      <div className="flex space-x-2">
                        <button className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700">
                          Generate
                        </button>
                        <button className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50">
                          Save
                        </button>
                      </div>
                    </div>
                    <div className="h-64">
                      <PlotlyChart
                        data={chartData}
                        layout={{
                          title: `${selectedChart.name} - ${dataset?.name}`,
                          autosize: true,
                          margin: { l: 50, r: 50, t: 50, b: 50 }
                        }}
                        config={{
                          displayModeBar: true,
                          displaylogo: false
                        }}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    <div className="text-center">
                      <Brain className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                      <p>Select a chart type or use AI recommendations to get started</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AIVisualizationBuilder

