import React from 'react'
import { Lightbulb, TrendingUp, AlertTriangle, CheckCircle, Zap } from 'lucide-react'

const InsightCard = ({ 
  title, 
  description, 
  confidence, 
  type, 
  icon, 
  actionable,
  datasetInfo 
}) => {
  const getIcon = () => {
    switch (icon || type) {
      case 'trending_up':
      case 'trend':
        return <TrendingUp className="w-5 h-5 text-green-400" />
      case 'alert':
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />
      case 'success':
      case 'check':
        return <CheckCircle className="w-5 h-5 text-green-400" />
      case 'lightbulb':
      case 'insight':
        return <Lightbulb className="w-5 h-5 text-blue-400" />
      default:
        return <Zap className="w-5 h-5 text-purple-400" />
    }
  }

  const getConfidenceColor = () => {
    if (confidence >= 0.8) return 'text-green-400 bg-green-500/20'
    if (confidence >= 0.6) return 'text-yellow-400 bg-yellow-500/20'
    return 'text-red-400 bg-red-500/20'
  }

  const getConfidenceText = () => {
    if (confidence >= 0.8) return 'High'
    if (confidence >= 0.6) return 'Medium'
    return 'Low'
  }

  // Highlight column names in description if they exist in dataset
  const highlightColumns = (text) => {
    if (!datasetInfo?.columns) return text
    
    const columnNames = datasetInfo.columns.map(col => col.name || col)
    let highlightedText = text
    
    columnNames.forEach(column => {
      const regex = new RegExp(`\\b${column}\\b`, 'gi')
      highlightedText = highlightedText.replace(
        regex, 
        `<span class="font-semibold text-blue-300">${column}</span>`
      )
    })
    
    return highlightedText
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
            {getIcon()}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{title}</h3>
            {confidence && (
              <div className={`text-xs px-2 py-1 rounded-full ${getConfidenceColor()}`}>
                {getConfidenceText()} Confidence
              </div>
            )}
          </div>
        </div>
      </div>
      
      <div className="flex-1">
        <p 
          className="text-sm text-slate-300 leading-relaxed mb-4"
          dangerouslySetInnerHTML={{ 
            __html: highlightColumns(description) 
          }}
        />
        
        {actionable && (
          <div className="mt-4 p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
            <div className="flex items-start gap-2">
              <Lightbulb className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs font-medium text-blue-300 mb-1">Actionable Insight</p>
                <p className="text-xs text-blue-200">{actionable}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default InsightCard

