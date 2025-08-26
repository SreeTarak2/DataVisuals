import React, { useState } from 'react'
import { Brain, BarChart3, TrendingUp, Search, Sparkles, MessageSquare } from 'lucide-react'
import { usePersona } from '../contexts/PersonaContext'

interface Insight {
  id: string
  type: 'explanation' | 'visualization' | 'query'
  title: string
  content: string
  confidence: number
  timestamp: string
}

const Analysis: React.FC = () => {
  const { persona, isNormal } = usePersona()
  const [query, setQuery] = useState('')
  const [insights, setInsights] = useState<Insight[]>([])
  const [loading, setLoading] = useState(false)

  const sampleInsights: Insight[] = [
    {
      id: '1',
      type: 'explanation',
      title: 'Dataset Overview',
      content: isNormal 
        ? 'This dataset contains sales information with 1,000 records across 8 columns. It shows customer purchases, product categories, and sales performance over time. The data quality is excellent with only 2% missing values.'
        : 'Dataset analysis reveals 1,000 observations across 8 variables with 98% data completeness. Primary variables include sales_amount (continuous), product_category (categorical), and date (temporal). Statistical analysis shows normal distribution for sales_amount with mean $245.67 and standard deviation $89.34.',
      confidence: 0.95,
      timestamp: new Date().toISOString()
    },
    {
      id: '2',
      type: 'visualization',
      title: 'Chart Recommendations',
      content: isNormal
        ? 'I recommend creating a line chart to show sales trends over time, and a bar chart to compare sales by product category. These will help you identify your best-performing products and seasonal patterns.'
        : 'Optimal visualization strategy: Line chart for temporal analysis (sales vs. time) with 95% confidence intervals. Bar chart for categorical comparison (sales by category) with statistical significance testing. Scatter plot for correlation analysis between sales_amount and customer_segment.',
      confidence: 0.88,
      timestamp: new Date().toISOString()
    }
  ]

  const handleQuery = async () => {
    if (!query.trim()) return
    
    setLoading(true)
    
    // Simulate API call
    setTimeout(() => {
      const newInsight: Insight = {
        id: Date.now().toString(),
        type: 'query',
        title: 'Query Response',
        content: isNormal
          ? `Based on your question "${query}", I found that sales have been increasing by an average of 15% month-over-month. The top performing category is electronics, accounting for 35% of total sales.`
          : `Query analysis: "${query}" reveals significant correlation (r=0.78, p<0.001) between sales and seasonal factors. Linear regression model shows 15.2% month-over-month growth with 95% confidence interval [12.8%, 17.6%]. Electronics category dominates with 35.2% market share (χ²=24.6, p<0.001).`,
        confidence: 0.82,
        timestamp: new Date().toISOString()
      }
      
      setInsights(prev => [newInsight, ...prev])
      setQuery('')
      setLoading(false)
    }, 2000)
  }

  const getInsightIcon = (type: string) => {
    switch (type) {
      case 'explanation':
        return <Brain className="h-5 w-5" />
      case 'visualization':
        return <BarChart3 className="h-5 w-5" />
      case 'query':
        return <MessageSquare className="h-5 w-5" />
      default:
        return <Sparkles className="h-5 w-5" />
    }
  }

  const getInsightColor = (type: string) => {
    switch (type) {
      case 'explanation':
        return 'primary'
      case 'visualization':
        return 'success'
      case 'query':
        return 'accent'
      default:
        return 'secondary'
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString()
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 mb-2">AI Analysis</h1>
        <p className="text-secondary-600">
          {isNormal
            ? 'Get intelligent insights and visualization recommendations in simple, business-friendly terms.'
            : 'Advanced statistical analysis, correlation detection, and technical insights with confidence intervals.'
          }
        </p>
      </div>

      {/* Query Input */}
      <div className="card p-6">
        <div className="flex items-center space-x-4">
          <div className="p-3 rounded-lg bg-accent-100">
            <Search className="h-6 w-6 text-accent-600" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-secondary-900 mb-2">Ask about your data</h3>
            <p className="text-sm text-secondary-600">
              {isNormal
                ? 'Ask questions in plain English and get business insights.'
                : 'Query your data with natural language for statistical analysis.'
              }
            </p>
          </div>
        </div>
        
        <div className="mt-4 flex space-x-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={isNormal 
              ? "e.g., 'Which products sell best?' or 'Show me sales trends'"
              : "e.g., 'What's the correlation between sales and time?' or 'Detect anomalies in the data'"
            }
            className="input flex-1"
            onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
          />
          <button
            onClick={handleQuery}
            disabled={loading || !query.trim()}
            className="btn-primary"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
            ) : (
              <>
                <Brain className="h-5 w-5 mr-2" />
                Analyze
              </>
            )}
          </button>
        </div>
      </div>

      {/* Sample Insights */}
      <div>
        <h2 className="text-2xl font-semibold text-secondary-900 mb-6">Sample Insights</h2>
        <div className="space-y-4">
          {sampleInsights.map((insight) => (
            <div key={insight.id} className="card p-6">
              <div className="flex items-start space-x-4">
                <div className={`p-3 rounded-lg bg-${getInsightColor(insight.type)}-100 text-${getInsightColor(insight.type)}-600`}>
                  {getInsightIcon(insight.type)}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-secondary-900">{insight.title}</h3>
                    <div className="flex items-center space-x-3">
                      <span className="text-sm text-secondary-500">
                        {formatDate(insight.timestamp)}
                      </span>
                      <div className="flex items-center space-x-2">
                        <div className="w-16 bg-secondary-200 rounded-full h-2">
                          <div 
                            className="bg-success-500 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${insight.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-sm text-secondary-600">
                          {Math.round(insight.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                  </div>
                  <p className="text-secondary-700 leading-relaxed">{insight.content}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Generated Insights */}
      {insights.length > 0 && (
        <div>
          <h2 className="text-2xl font-semibold text-secondary-900 mb-6">Generated Insights</h2>
          <div className="space-y-4">
            {insights.map((insight) => (
              <div key={insight.id} className="card p-6 border-accent-200 bg-accent-50">
                <div className="flex items-start space-x-4">
                  <div className="p-3 rounded-lg bg-accent-100 text-accent-600">
                    {getInsightIcon(insight.type)}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-secondary-900">{insight.title}</h3>
                      <div className="flex items-center space-x-3">
                        <span className="text-sm text-secondary-500">
                          {formatDate(insight.timestamp)}
                        </span>
                        <div className="flex items-center space-x-2">
                          <div className="w-16 bg-secondary-200 rounded-full h-2">
                            <div 
                              className="bg-accent-500 h-2 rounded-full transition-all duration-300"
                              style={{ width: `${insight.confidence * 100}%` }}
                            />
                          </div>
                          <span className="text-sm text-secondary-600">
                            {Math.round(insight.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    </div>
                    <p className="text-secondary-700 leading-relaxed">{insight.content}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Capabilities */}
      <div>
        <h2 className="text-2xl font-semibold text-secondary-900 mb-6">AI Capabilities</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card p-6">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-2 rounded-lg bg-primary-100">
                <Brain className="h-5 w-5 text-primary-600" />
              </div>
              <h3 className="font-semibold text-secondary-900">Smart Explanations</h3>
            </div>
            <p className="text-secondary-600 text-sm">
              {isNormal
                ? 'Get clear, business-focused explanations of your data without technical jargon.'
                : 'Comprehensive data profiling with statistical measures and confidence intervals.'
              }
            </p>
          </div>
          
          <div className="card p-6">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-2 rounded-lg bg-success-100">
                <BarChart3 className="h-5 w-5 text-success-600" />
              </div>
              <h3 className="font-semibold text-secondary-900">Visualization Recommendations</h3>
            </div>
            <p className="text-secondary-600 text-sm">
              {isNormal
                ? 'AI suggests the best charts and graphs to tell your data story.'
                : 'Advanced chart recommendations based on statistical analysis and data characteristics.'
              }
            </p>
          </div>
          
          <div className="card p-6">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-2 rounded-lg bg-accent-100">
                <TrendingUp className="h-5 w-5 text-accent-600" />
              </div>
              <h3 className="font-semibold text-secondary-900">Pattern Detection</h3>
            </div>
            <p className="text-secondary-600 text-sm">
              {isNormal
                ? 'Discover trends, correlations, and insights you might have missed.'
                : 'Statistical pattern recognition, anomaly detection, and correlation analysis.'
              }
            </p>
          </div>
          
          <div className="card p-6">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-2 rounded-lg bg-warning-100">
                <MessageSquare className="h-5 w-5 text-warning-600" />
              </div>
              <h3 className="font-semibold text-secondary-900">Natural Language Queries</h3>
            </div>
            <p className="text-secondary-600 text-sm">
              {isNormal
                ? 'Ask questions in plain English and get instant answers from your data.'
                : 'Advanced query processing with statistical validation and confidence scoring.'
              }
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Analysis
