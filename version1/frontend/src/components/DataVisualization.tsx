import React, { useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  ScatterChart,
  Scatter
} from 'recharts'
import { MessageCircle, Sparkles, X, Send, Bot, User } from 'lucide-react'

interface ChartData {
  [key: string]: any
}

interface DataVisualizationProps {
  chartType: string
  data: any[]
  fields: string[]
  title?: string
  description?: string
  showChat?: boolean
  showRecommendations?: boolean
  onRecommendation?: () => void
  datasetContext?: string
}

const COLORS = ['#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#06B6D4', '#EF4444', '#84CC16']

const DataVisualization: React.FC<DataVisualizationProps> = ({
  chartType,
  data,
  fields,
  title,
  description,
  showChat = false,
  showRecommendations = false,
  onRecommendation,
  datasetContext = ""
}) => {
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState<Array<{type: 'user' | 'ai', message: string}>>([])
  const [chatInput, setChatInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim()) return

    const userMessage = chatInput.trim()
    setChatMessages(prev => [...prev, { type: 'user', message: userMessage }])
    setChatInput('')
    setIsLoading(true)

    try {
      // Simulate AI response - in real implementation, this would call your LLM API
      const aiResponse = await simulateAIResponse(userMessage, chartType, data, datasetContext)
      setChatMessages(prev => [...prev, { type: 'ai', message: aiResponse }])
    } catch (error) {
      setChatMessages(prev => [...prev, { type: 'ai', message: 'Sorry, I encountered an error. Please try again.' }])
    } finally {
      setIsLoading(false)
    }
  }

  const simulateAIResponse = async (userMessage: string, chartType: string, data: any[], context: string): Promise<string> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // Generate contextual response based on chart type and data
    const responses = {
      bar_chart: [
        "This bar chart shows the distribution of data across different categories. The tallest bars represent the most frequent values.",
        "Looking at this bar chart, I can see some interesting patterns in your data. Would you like me to explain any specific bars?",
        "The data appears to be well-distributed. The highest value is in the first category, which might indicate a trend."
      ],
      line_chart: [
        "This line chart shows trends over time. I can see the data is trending upward/downward based on the slope.",
        "The line chart reveals interesting patterns in your data. There are some peaks and valleys that might be worth investigating.",
        "This trend line shows a clear pattern. Would you like me to help you identify what might be causing these changes?"
      ],
      pie_chart: [
        "This pie chart shows the proportional breakdown of your data. The largest slice represents the dominant category.",
        "Looking at this pie chart, I can see the data is distributed across several categories. The blue slice appears to be the largest.",
        "The pie chart gives us a clear view of the data distribution. Each slice represents a different segment of your data."
      ]
    }

    const chartResponses = responses[chartType as keyof typeof responses] || [
      "This visualization shows interesting patterns in your data. Can you tell me more about what you'd like to know?",
      "I can see some trends in this chart. What specific aspect would you like me to analyze?",
      "This data visualization reveals some insights. What questions do you have about it?"
    ]

    return chartResponses[Math.floor(Math.random() * chartResponses.length)]
  }

  const renderChart = () => {
    console.log('DataVisualization renderChart called:', {
      chartType,
      dataLength: data?.length || 0,
      fields,
      hasData: !!(data && data.length > 0),
      sampleData: data?.slice(0, 2)
    })

    if (!data || data.length === 0) {
      return (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <BarChart className="h-12 w-12 mx-auto mb-2 text-gray-400" />
            <p className="text-sm font-medium">No data available</p>
            <p className="text-xs text-gray-400 mt-1">Chart Type: {chartType}</p>
          </div>
        </div>
      )
    }

    console.log('Rendering chart:', chartType, 'with data:', data.slice(0, 3), 'fields:', fields)

    switch (chartType) {
      case 'bar_chart':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey={fields[0] || 'name'} 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <YAxis 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  color: '#374151',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Bar 
                dataKey={fields[1] || 'value'} 
                fill={COLORS[0]} 
                radius={[4, 4, 0, 0]} 
                stroke="none"
              />
            </BarChart>
          </ResponsiveContainer>
        )

      case 'line_chart':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey={fields[0] || 'name'} 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <YAxis 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  color: '#374151',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Line 
                type="monotone" 
                dataKey={fields[1] || 'value'} 
                stroke={COLORS[0]} 
                strokeWidth={2}
                dot={{ fill: COLORS[0], strokeWidth: 2, r: 3 }}
                activeDot={{ r: 5, stroke: COLORS[0], strokeWidth: 2, fill: 'white' }}
              />
            </LineChart>
          </ResponsiveContainer>
        )

      case 'pie_chart':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={80}
                fill="#8884d8"
                dataKey={fields[1] || 'value'}
                nameKey={fields[0] || 'name'}
                label={({ name, percent }) => (
                  <text 
                    x={0} 
                    y={0} 
                    textAnchor="middle" 
                    dominantBaseline="central" 
                    fill="#374151" 
                    fontSize="12" 
                    fontWeight="500"
                  >
                    {`${name} ${(percent * 100).toFixed(0)}%`}
                  </text>
                )}
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  color: '#374151',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        )

      case 'scatter_plot':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey={fields[0]} 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <YAxis 
                dataKey={fields[1]} 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  color: '#374151',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Scatter dataKey={fields[1]} fill={COLORS[0]} stroke={COLORS[0]} strokeWidth={1} />
            </ScatterChart>
          </ResponsiveContainer>
        )

      case 'histogram':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="range" 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <YAxis 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  color: '#374151',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Bar dataKey="count" fill={COLORS[0]} radius={[4, 4, 0, 0]} stroke="none" />
            </BarChart>
          </ResponsiveContainer>
        )

      case 'heatmap':
        // For heatmap, show a scatter plot with color intensity
        return (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey={fields[0]} 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <YAxis 
                dataKey={fields[1]} 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  color: '#374151',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Scatter dataKey={fields[1]} fill={COLORS[0]} stroke={COLORS[0]} strokeWidth={1} />
            </ScatterChart>
          </ResponsiveContainer>
        )

      case 'box_plot':
        // For box plot, show a bar chart as approximation
        return (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey={fields[0]} 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <YAxis 
                stroke="#6b7280" 
                tick={{ fill: '#6b7280', fontSize: 12 }} 
                axisLine={false}
                tickLine={false}
              />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  color: '#374151',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Bar dataKey={fields[1]} fill={COLORS[0]} radius={[4, 4, 0, 0]} stroke="none" />
            </BarChart>
          </ResponsiveContainer>
        )

      default:
        return (
          <div className="flex items-center justify-center h-64 text-gray-500">
            <p className="text-sm font-medium">Chart type "{chartType}" not supported</p>
          </div>
        )
    }
  }

  return (
    <div className="w-full h-full relative">
      {/* Chart Header with Actions */}
      <div className="flex items-center justify-end mb-4">
        {showChat && (
          <button
            onClick={() => setIsChatOpen(!isChatOpen)}
            className={`flex items-center space-x-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-all duration-200 ${
              isChatOpen 
                ? 'bg-indigo-100 hover:bg-indigo-200 text-indigo-700 shadow-md' 
                : 'bg-indigo-100 hover:bg-indigo-200 text-indigo-700 shadow-md hover:shadow-lg'
            }`}
          >
            <MessageCircle className="h-4 w-4" />
            <span>Chat</span>
          </button>
        )}
      </div>

      {/* Chart Container */}
      <div className="w-full h-full">
        {renderChart()}
      </div>

      {/* Chat Panel */}
      {isChatOpen && showChat && (
        <div className="absolute inset-0 bg-black/80 backdrop-blur-md border border-white/20 rounded-2xl shadow-2xl z-10 flex flex-col">
          {/* Chat Header */}
          <div className="flex items-center justify-between p-4 border-b border-white/20">
            <div className="flex items-center space-x-2">
              <Bot className="h-5 w-5 text-sky-400" />
              <span className="font-medium text-white">Chart Assistant</span>
            </div>
            <button
              onClick={() => setIsChatOpen(false)}
              className="p-1 hover:bg-white/10 rounded-lg transition-colors"
            >
              <X className="h-4 w-4 text-white" />
            </button>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4">
            {chatMessages.length === 0 ? (
              <div className="text-center text-gray-300 py-8">
                <Bot className="h-8 w-8 mx-auto mb-2 text-sky-400" />
                <p>Ask me anything about this chart!</p>
                <p className="text-sm">I can help explain the data, trends, and insights.</p>
              </div>
            ) : (
              chatMessages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-xs px-4 py-2 rounded-xl ${
                      message.type === 'user'
                        ? 'bg-gradient-to-r from-sky-600 to-cyan-600 text-white'
                        : 'bg-white/10 backdrop-blur-sm text-white border border-white/20'
                    }`}
                  >
                    <div className="flex items-start space-x-2">
                      {message.type === 'ai' && <Bot className="h-4 w-4 mt-0.5 flex-shrink-0 text-sky-400" />}
                      {message.type === 'user' && <User className="h-4 w-4 mt-0.5 flex-shrink-0" />}
                      <p className="text-sm">{message.message}</p>
                    </div>
                  </div>
                </div>
              ))
            )}
            
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white/10 backdrop-blur-sm text-white px-4 py-2 rounded-xl border border-white/20">
                  <div className="flex items-center space-x-2">
                    <Bot className="h-4 w-4 text-sky-400" />
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Chat Input */}
          <form onSubmit={handleChatSubmit} className="p-4 border-t border-white/20">
            <div className="flex space-x-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask about this chart..."
                className="flex-1 px-3 py-2 bg-white/10 border border-white/20 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-transparent text-white placeholder-gray-400"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={!chatInput.trim() || isLoading}
                className="px-4 py-2 bg-gradient-to-r from-sky-600 to-cyan-600 text-white rounded-xl hover:from-sky-700 hover:to-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1 transition-all duration-200"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

export default DataVisualization
