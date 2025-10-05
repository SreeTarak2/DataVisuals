import React from 'react'
import { CheckCircle, AlertTriangle, XCircle, Info, Shield, Database } from 'lucide-react'

interface DataQualityProps {
  score: number
  issues: Array<{
    type: 'error' | 'warning' | 'info'
    message: string
    count?: number
  }>
  isNormal?: boolean
}

const DataQualityPanel: React.FC<DataQualityProps> = ({ score, issues, isNormal = false }) => {
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-400'
    if (score >= 70) return 'text-yellow-400'
    return 'text-red-400'
  }

  const getScoreBg = (score: number) => {
    if (score >= 90) return 'bg-green-500/20'
    if (score >= 70) return 'bg-yellow-500/20'
    return 'bg-red-500/20'
  }

  const getIssueIcon = (type: string) => {
    switch (type) {
      case 'error': return <XCircle className="w-4 h-4 text-red-400" />
      case 'warning': return <AlertTriangle className="w-4 h-4 text-yellow-400" />
      default: return <Info className="w-4 h-4 text-blue-400" />
    }
  }

  return (
    <div className={`
      backdrop-blur-xl border rounded-2xl p-6 shadow-2xl
      ${isNormal 
        ? 'bg-white/95 dark:bg-slate-800/95 border-gray-200 dark:border-slate-700'
        : 'bg-white/10 border-white/20'
      }
    `}>
      {/* Header */}
      <div className="flex items-center space-x-3 mb-6">
        <div className={`
          p-2 rounded-lg
          ${isNormal 
            ? 'bg-green-100 dark:bg-green-900/20' 
            : 'bg-gradient-to-r from-green-500/20 to-emerald-500/20'
          }
        `}>
          <Shield className={`w-5 h-5 ${
            isNormal 
              ? 'text-green-600 dark:text-green-400' 
              : 'text-green-400'
          }`} />
        </div>
        <div>
          <h3 className={`text-lg font-semibold ${
            isNormal 
              ? 'text-gray-900 dark:text-white' 
              : 'text-white'
          }`}>
            Data Quality
          </h3>
          <p className={`text-sm ${
            isNormal 
              ? 'text-gray-500 dark:text-gray-400' 
              : 'text-slate-400'
          }`}>
            Overall assessment
          </p>
        </div>
      </div>

      {/* Score Display */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-sm font-medium ${
            isNormal 
              ? 'text-gray-600 dark:text-gray-400' 
              : 'text-slate-400'
          }`}>
            Quality Score
          </span>
          <span className={`text-2xl font-bold ${getScoreColor(score)}`}>
            {score}/100
          </span>
        </div>
        <div className={`
          w-full h-3 rounded-full overflow-hidden
          ${isNormal 
            ? 'bg-gray-200 dark:bg-gray-700' 
            : 'bg-slate-700'
          }
        `}>
          <div 
            className={`h-full transition-all duration-1000 ${getScoreBg(score)}`}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      {/* Issues List */}
      <div className="space-y-3">
        <h4 className={`text-sm font-medium ${
          isNormal 
            ? 'text-gray-700 dark:text-gray-300' 
            : 'text-slate-300'
        }`}>
          Issues Found
        </h4>
        {issues.length === 0 ? (
          <div className="flex items-center space-x-2 text-green-400">
            <CheckCircle className="w-4 h-4" />
            <span className="text-sm">No issues detected</span>
          </div>
        ) : (
          <div className="space-y-2">
            {issues.map((issue, index) => (
              <div key={index} className="flex items-center space-x-3">
                {getIssueIcon(issue.type)}
                <span className={`text-sm ${
                  isNormal 
                    ? 'text-gray-600 dark:text-gray-400' 
                    : 'text-slate-400'
                }`}>
                  {issue.message}
                  {issue.count && (
                    <span className={`ml-2 px-2 py-0.5 text-xs rounded-full ${
                      isNormal 
                        ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400' 
                        : 'bg-slate-700 text-slate-300'
                    }`}>
                      {issue.count}
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default DataQualityPanel

