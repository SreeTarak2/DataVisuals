import React, { useState, useEffect } from 'react'
import { 
  Brain, 
  BarChart3, 
  TrendingUp, 
  Search, 
  Sparkles, 
  MessageSquare, 
  Play, 
  RefreshCw, 
  Eye, 
  ChevronRight,
  Lightbulb,
  Target,
  Zap,
  Activity,
  CheckCircle,
  AlertCircle,
  Send,
  Bot,
  User,
  Trash2
} from 'lucide-react'
import axios from 'axios'
import toast from 'react-hot-toast'
import DataVisualization from '../components/DataVisualization'

interface Dataset {
  id: string
  filename: string
  size: number
  row_count: number
  column_count: number
  upload_date: string
}

interface InsightCard {
  question: string
  reason: string
  breakdown: string
  measure: string
}

interface Insight {
  pattern_type: string
  significance_score: number
  description: string
  chart_type: string
  filters: Record<string, any>
  p_value?: number
  trend_direction?: string
  trend_strength?: number
  ratio?: number
  top_category?: string
  top_value?: number
  share?: number
  dominant_category?: string
  jsd?: number
  categories?: [string, string]
}

const Analysis: React.FC = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null)
  const [insightCards, setInsightCards] = useState<InsightCard[]>([])
  const [selectedCard, setSelectedCard] = useState<InsightCard | null>(null)
  const [insights, setInsights] = useState<Insight[]>([])
  const [loading, setLoading] = useState(false)
  const [generatingQuestions, setGeneratingQuestions] = useState(false)
  const [generatingInsights, setGeneratingInsights] = useState(false)
  const [chartData, setChartData] = useState<any[]>([])
  
  // Chat state
  const [chatMessages, setChatMessages] = useState<Array<{id: string, type: 'user' | 'ai', message: string, visualization?: any}>>([])
  const [chatInput, setChatInput] = useState('')
  const [sendingMessage, setSendingMessage] = useState(false)
  const [chatVisualization, setChatVisualization] = useState<any>(null)

  // Load datasets on component mount
  useEffect(() => {
    loadDatasets()
  }, [])

  const loadDatasets = async () => {
    try {
      const response = await axios.get('http://localhost:8000/datasets')
      setDatasets(response.data)
    } catch (error) {
      console.error('Failed to load datasets:', error)
      toast.error('Failed to load datasets')
    }
  }

  const generateQuestions = async () => {
    if (!selectedDataset) {
      toast.error('Please select a dataset first')
      return
    }

    setGeneratingQuestions(true)
    try {
      const response = await axios.post(
        `http://localhost:8000/analysis/generate-questions?dataset_id=${selectedDataset.id}`
      )
      setInsightCards(response.data)
      toast.success(`Generated ${response.data.length} insightful questions!`)
    } catch (error) {
      console.error('Error generating questions:', error)
      toast.error('Failed to generate questions')
    } finally {
      setGeneratingQuestions(false)
    }
  }

  const generateInsights = async (card: InsightCard) => {
    if (!selectedDataset) return

    setSelectedCard(card)
    setGeneratingInsights(true)
    setInsights([])
    setChartData([])

    try {
      const response = await axios.post(
        `http://localhost:8000/analysis/generate-insights?dataset_id=${selectedDataset.id}`,
        card
      )
      setInsights(response.data)
      
      // Generate chart data for visualization
      if (response.data.length > 0) {
        const chartData = generateChartDataFromInsights(response.data, card)
        setChartData(chartData)
      }
      
      toast.success(`Found ${response.data.length} statistical insights!`)
    } catch (error) {
      console.error('Error generating insights:', error)
      toast.error('Failed to generate insights')
    } finally {
      setGeneratingInsights(false)
    }
  }

  const generateChartDataFromInsights = (insights: Insight[], card: InsightCard) => {
    // This is a simplified version - in a real app, you'd generate proper chart data
    return insights.map((insight, index) => ({
      id: index,
      [card.breakdown]: `Sample ${card.breakdown} ${index + 1}`,
      [card.measure]: Math.random() * 100,
      significance: insight.significance_score
    }))
  }

  const sendChatMessage = async () => {
    if (!chatInput.trim() || !selectedDataset || sendingMessage) return

    const userMessage = chatInput.trim()
    setChatInput('')
    setSendingMessage(true)

    // Add user message to chat
    const userMessageId = `user-${Date.now()}`
    setChatMessages(prev => [...prev, {
      id: userMessageId,
      type: 'user',
      message: userMessage
    }])

    try {
      const response = await axios.post(
        `http://localhost:8000/chat/message?dataset_id=${selectedDataset.id}`,
        userMessage,
        { headers: { 'Content-Type': 'text/plain' } }
      )

      // Add AI response to chat
      const aiMessageId = `ai-${Date.now()}`
      setChatMessages(prev => [...prev, {
        id: aiMessageId,
        type: 'ai',
        message: response.data.message || response.data.response,
        visualization: response.data.visualization
      }])

      // If there's a visualization, set it for the dedicated area
      if (response.data.visualization) {
        setChatVisualization(response.data.visualization)
      }

      toast.success('AI response generated!')
    } catch (error) {
      console.error('Error sending chat message:', error)
      toast.error('Failed to send message')
      
      // Add error message to chat
      const errorMessageId = `error-${Date.now()}`
      setChatMessages(prev => [...prev, {
        id: errorMessageId,
        type: 'ai',
        message: 'Sorry, I encountered an error processing your message. Please try again.'
      }])
    } finally {
      setSendingMessage(false)
    }
  }

  const handleChatKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendChatMessage()
    }
  }

  const clearChat = () => {
    setChatMessages([])
    setChatVisualization(null)
  }

  const deleteDataset = async (id: string) => {
    const dataset = datasets.find(d => d.id === id)
    if (!dataset) return
    
    if (window.confirm(`Are you sure you want to delete "${dataset.filename}"? This action cannot be undone.`)) {
      try {
        await axios.delete(`http://localhost:8000/datasets/${id}`)
        setDatasets(prev => prev.filter(dataset => dataset.id !== id))
        
        // If the deleted dataset was selected, clear the selection
        if (selectedDataset?.id === id) {
          setSelectedDataset(null)
          setInsightCards([])
          setSelectedCard(null)
          setInsights([])
          setChartData([])
          setChatMessages([])
          setChatVisualization(null)
        }
        
        toast.success('Dataset deleted successfully!')
      } catch (error) {
        console.error('Error deleting dataset:', error)
        toast.error('Failed to delete dataset')
      }
    }
  }

  const getPatternIcon = (patternType: string) => {
    switch (patternType) {
      case 'trend': return <TrendingUp className="h-5 w-5 text-blue-600" />
      case 'outstanding_value': return <Zap className="h-5 w-5 text-yellow-600" />
      case 'attribution': return <Target className="h-5 w-5 text-green-600" />
      case 'distribution_difference': return <BarChart3 className="h-5 w-5 text-purple-600" />
      case 'correlation': return <Activity className="h-5 w-5 text-indigo-600" />
      default: return <Search className="h-5 w-5 text-gray-600" />
    }
  }

  const getPatternColor = (patternType: string) => {
    switch (patternType) {
      case 'trend': return 'blue'
      case 'outstanding_value': return 'yellow'
      case 'attribution': return 'green'
      case 'distribution_difference': return 'purple'
      case 'correlation': return 'indigo'
      default: return 'gray'
    }
  }

  const formatSignificanceScore = (score: number) => {
    if (score >= 0.8) return 'Very High'
    if (score >= 0.6) return 'High'
    if (score >= 0.4) return 'Medium'
    if (score >= 0.2) return 'Low'
    return 'Very Low'
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">AI Analysis</h1>
              <p className="mt-1 text-sm text-gray-600">
                {isNormal
                  ? 'Discover insights automatically with AI-powered question generation and statistical analysis.'
                  : 'Advanced automated EDA with QUIS methodology - question generation, pattern detection, and statistical insights.'
                }
              </p>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <Brain className="h-4 w-4" />
              <span>QUIS Methodology</span>
            </div>
          </div>
        </div>

        {/* How It Works Section */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-medium text-gray-900 mb-2 flex items-center">
                <Lightbulb className="h-5 w-5 text-yellow-600 mr-2" />
                Question Generation (QUGen)
              </h3>
              <p className="text-sm text-gray-600">
                AI analyzes your dataset schema and statistics to automatically generate 
                insightful questions that guide exploration.
              </p>
            </div>
            <div>
              <h3 className="font-medium text-gray-900 mb-2 flex items-center">
                <Target className="h-5 w-5 text-green-600 mr-2" />
                Insight Generation (ISGen)
              </h3>
              <p className="text-sm text-gray-600">
                Statistical analysis detects patterns like trends, outliers, and distributions 
                with mathematical rigor and significance testing.
              </p>
            </div>
          </div>
        </div>

        {/* Main Content Area - Two Column Layout */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Left Column - Questions and Insights */}
          <div className="xl:col-span-2 space-y-8">
            {/* Dataset Selection */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Select Dataset for Analysis</h2>
              {datasets.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {datasets.map((dataset) => (
                    <div
                      key={dataset.id}
                      className={`p-4 border-2 rounded-lg transition-all cursor-pointer ${
                        selectedDataset?.id === dataset.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                      }`}
                      onClick={() => setSelectedDataset(dataset)}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-gray-900 truncate">{dataset.filename}</h3>
                          <p className="text-sm text-gray-600 truncate">
                            {dataset.row_count.toLocaleString()} rows • {dataset.column_count} columns
                          </p>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteDataset(dataset.id)
                          }}
                          className="text-gray-400 hover:text-red-600 transition-colors p-1 rounded"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                      <div className="text-xs text-gray-500">
                        Uploaded: {new Date(dataset.upload_date).toLocaleDateString()}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-2" />
                  <p className="text-gray-600">No datasets available. Upload a dataset to get started.</p>
                </div>
              )}
            </div>

            {/* Question Generation */}
            {selectedDataset && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-900">AI-Generated Questions</h2>
                  <button
                    onClick={generateQuestions}
                    disabled={generatingQuestions}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
                  >
                    {generatingQuestions ? (
                      <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <Sparkles className="h-4 w-4 mr-2" />
                    )}
                    <span>{generatingQuestions ? 'Generating...' : 'Generate Questions'}</span>
                  </button>
                </div>

                {insightCards.length > 0 && (
                  <div className="space-y-4">
                    <p className="text-sm text-gray-600 mb-4">
                      Click on any question to analyze the data and discover statistical insights.
                    </p>
                    <div className="grid gap-4">
                      {insightCards.map((card, index) => (
                        <div
                          key={index}
                          className={`p-4 border rounded-lg cursor-pointer transition-all ${
                            selectedCard?.question === card.question
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                          }`}
                          onClick={() => generateInsights(card)}
                        >
                          <div className="flex items-start space-x-3">
                            <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                              <span className="text-sm font-medium text-blue-600">{index + 1}</span>
                            </div>
                            <div className="flex-1 min-w-0">
                              <h3 className="font-medium text-gray-900 mb-2">{card.question}</h3>
                              <p className="text-sm text-gray-600 mb-3">{card.reason}</p>
                              <div className="flex items-center space-x-4 text-xs text-gray-500">
                                <span>Breakdown: {card.breakdown}</span>
                                <span>Measure: {card.measure}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Insights Display */}
            {selectedCard && (
              <div className="space-y-6">
                {/* Selected Question */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Analysis Results</h2>
                  <div className="bg-blue-50 p-4 rounded-lg mb-4">
                    <h3 className="font-medium text-blue-900 mb-2">Question: {selectedCard.question}</h3>
                    <p className="text-blue-800 text-sm">{selectedCard.reason}</p>
                  </div>

                  {generatingInsights ? (
                    <div className="flex items-center justify-center py-8">
                      <RefreshCw className="h-6 w-6 animate-spin text-blue-600 mr-2" />
                      <span className="text-gray-600">Analyzing data and generating insights...</span>
                    </div>
                  ) : insights.length > 0 ? (
                    <div className="space-y-4">
                      <h3 className="font-medium text-gray-900">Statistical Insights ({insights.length})</h3>
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {insights.map((insight, index) => (
                          <div key={index} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                            <div className="flex items-start space-x-3 mb-3">
                              {getPatternIcon(insight.pattern_type)}
                              <div className="flex-1 min-w-0">
                                <h4 className="font-medium text-gray-900 capitalize">
                                  {insight.pattern_type.replace('_', ' ')} Pattern
                                </h4>
                                <div className="flex items-center space-x-2 mt-1">
                                  <span className="text-sm text-gray-600">
                                    Significance: {formatSignificanceScore(insight.significance_score)}
                                  </span>
                                  <div className="w-16 bg-gray-200 rounded-full h-2">
                                    <div 
                                      className={`bg-${getPatternColor(insight.pattern_type)}-500 h-2 rounded-full`}
                                      style={{ width: `${insight.significance_score * 100}%` }}
                                    />
                                  </div>
                                </div>
                              </div>
                            </div>
                            <p className="text-sm text-gray-700 mb-3">{insight.description}</p>
                            
                            {/* Additional details based on pattern type */}
                            {insight.trend_direction && (
                              <div className="text-xs text-gray-600">
                                <span className="font-medium">Trend:</span> {insight.trend_direction} 
                                (strength: {insight.trend_strength?.toFixed(3)})
                              </div>
                            )}
                            {insight.top_category && (
                              <div className="text-xs text-gray-600">
                                <span className="font-medium">Top Category:</span> {insight.top_category} 
                                (value: {insight.top_value?.toFixed(2)})
                              </div>
                            )}
                            {insight.dominant_category && (
                              <div className="text-xs text-gray-600">
                                <span className="font-medium">Dominant:</span> {insight.dominant_category} 
                                ({insight.share?.toFixed(1)}%)
                              </div>
                            )}
                            {insight.p_value && (
                              <div className="text-xs text-gray-600">
                                <span className="font-medium">P-value:</span> {insight.p_value.toFixed(4)}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-2" />
                      <p className="text-gray-600">No significant patterns found for this question</p>
                    </div>
                  )}
                </div>
                
                {/* Visualization */}
                {chartData.length > 0 && insights.length > 0 && (
                  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Data Visualization</h3>
                    <div className="h-80">
                      <DataVisualization
                        chartType={insights[0]?.chart_type || 'bar_chart'}
                        data={chartData}
                        fields={[selectedCard.breakdown, selectedCard.measure]}
                        showChat={true}
                        showRecommendations={false}
                        datasetContext={`Dataset: ${selectedDataset?.filename}, Rows: ${selectedDataset?.row_count}`}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column - AI Chat and Visualizations */}
          <div className="space-y-8">
            {/* AI Chat Interface */}
            {selectedDataset && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                    <MessageSquare className="h-5 w-5 text-blue-600 mr-2" />
                    Ask AI About Your Data
                  </h2>
                  <button
                    onClick={clearChat}
                    className="text-sm text-gray-500 hover:text-gray-700 flex items-center transition-colors duration-200"
                  >
                    <RefreshCw className="h-4 w-4 mr-1" />
                    Clear Chat
                  </button>
                </div>
                
                <p className="text-sm text-gray-600 mb-4">
                  Ask questions about your data in natural language. I can help you explore correlations, 
                  distributions, trends, and generate visualizations.
                </p>

                {/* Chat Messages */}
                <div className="bg-gray-50 rounded-lg p-4 h-96 overflow-y-auto mb-4 space-y-4">
                  {chatMessages.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                      <Bot className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                      <p className="text-sm font-medium">Start a conversation about your data!</p>
                      <p className="text-xs mt-1">Try asking: "Show me the correlation between age and salary"</p>
                    </div>
                  ) : (
                    chatMessages.map((msg) => (
                      <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                          msg.type === 'user' 
                            ? 'bg-blue-600 text-white' 
                            : 'bg-white text-gray-900 border border-gray-200'
                        }`}>
                          <div className="flex items-start space-x-2">
                            {msg.type === 'ai' && <Bot className="h-4 w-4 mt-0.5 flex-shrink-0" />}
                            {msg.type === 'user' && <User className="h-4 w-4 mt-0.5 flex-shrink-0" />}
                            <div className="flex-1 min-w-0">
                              <p className="text-sm">{msg.message}</p>
                              {msg.visualization && (
                                <div className="mt-2 p-2 bg-gray-50 rounded border">
                                  <p className="text-xs text-gray-600 mb-2">Generated Visualization:</p>
                                  <div className="text-xs text-gray-500">
                                    Chart Type: {msg.visualization.type}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Chat Input */}
                <div className="flex space-x-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyPress={handleChatKeyPress}
                    placeholder="Ask me about your data... (e.g., 'Show correlation between sales and profit')"
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    disabled={sendingMessage}
                  />
                  <button
                    onClick={sendChatMessage}
                    disabled={!chatInput.trim() || sendingMessage}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 text-sm font-medium transition-colors duration-200"
                  >
                    {sendingMessage ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Chat-Generated Visualizations */}
            {chatVisualization && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <BarChart3 className="h-5 w-5 text-blue-600 mr-2" />
                  AI-Generated Visualization
                </h3>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-600 mb-4">
                    Chart Type: <span className="font-medium">{chatVisualization.type}</span>
                  </div>
                  <div className="h-64 flex items-center justify-center bg-white rounded border">
                    <div className="text-center text-gray-500">
                      <BarChart3 className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                      <p className="text-sm font-medium">Visualization would be rendered here</p>
                      <p className="text-xs mt-1">Data: {JSON.stringify(chatVisualization.data, null, 2).substring(0, 100)}...</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Analysis