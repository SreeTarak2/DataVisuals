import React, { useState } from 'react'
import { Download, Settings, Maximize2, MoreHorizontal, BarChart3, TrendingUp } from 'lucide-react'

interface ChartContainerProps {
  title: string
  children: React.ReactNode
  chartType?: string
  isNormal?: boolean
  className?: string
  onExport?: () => void
  onSettings?: () => void
  onMaximize?: () => void
}

const ModernChartContainer: React.FC<ChartContainerProps> = ({ 
  title, 
  children, 
  chartType = 'chart',
  isNormal = false,
  className = '',
  onExport,
  onSettings,
  onMaximize
}) => {
  const [isHovered, setIsHovered] = useState(false)

  const getChartIcon = () => {
    switch (chartType) {
      case 'bar': return <BarChart3 className="w-5 h-5" />
      case 'line': return <TrendingUp className="w-5 h-5" />
      default: return <BarChart3 className="w-5 h-5" />
    }
  }

  return (
    <div 
      className={`
        backdrop-blur-xl border rounded-2xl shadow-2xl
        hover:shadow-3xl transition-all duration-300
        ${isNormal 
          ? 'bg-white/95 dark:bg-slate-800/95 border-gray-200 dark:border-slate-700'
          : 'bg-white/10 border-white/20 hover:bg-white/20'
        }
        ${className}
      `}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b border-white/10">
        <div className="flex items-center space-x-3">
          <div className={`
            p-2 rounded-lg
            ${isNormal 
              ? 'bg-blue-100 dark:bg-blue-900/20' 
              : 'bg-gradient-to-r from-cyan-500/20 to-purple-500/20'
            }
          `}>
            {getChartIcon()}
          </div>
          <div>
            <h3 className={`text-lg font-semibold ${
              isNormal 
                ? 'text-gray-900 dark:text-white' 
                : 'text-white'
            }`}>
              {title}
            </h3>
            <p className={`text-sm ${
              isNormal 
                ? 'text-gray-500 dark:text-gray-400' 
                : 'text-slate-400'
            }`}>
              {chartType.charAt(0).toUpperCase() + chartType.slice(1)} Chart
            </p>
          </div>
        </div>
        
        {/* Action Buttons */}
        <div className={`flex items-center space-x-2 transition-opacity duration-200 ${
          isHovered ? 'opacity-100' : 'opacity-0'
        }`}>
          {onExport && (
            <button
              onClick={onExport}
              className={`
                p-2 rounded-lg transition-colors duration-200
                ${isNormal 
                  ? 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700' 
                  : 'text-slate-400 hover:text-white hover:bg-white/10'
                }
              `}
              title="Export Chart"
            >
              <Download className="w-4 h-4" />
            </button>
          )}
          
          {onSettings && (
            <button
              onClick={onSettings}
              className={`
                p-2 rounded-lg transition-colors duration-200
                ${isNormal 
                  ? 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700' 
                  : 'text-slate-400 hover:text-white hover:bg-white/10'
                }
              `}
              title="Chart Settings"
            >
              <Settings className="w-4 h-4" />
            </button>
          )}
          
          {onMaximize && (
            <button
              onClick={onMaximize}
              className={`
                p-2 rounded-lg transition-colors duration-200
                ${isNormal 
                  ? 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700' 
                  : 'text-slate-400 hover:text-white hover:bg-white/10'
                }
              `}
              title="Maximize Chart"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          )}
          
          <button
            className={`
              p-2 rounded-lg transition-colors duration-200
              ${isNormal 
                ? 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700' 
                : 'text-slate-400 hover:text-white hover:bg-white/10'
              }
            `}
            title="More Options"
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Chart Content */}
      <div className="p-6">
        <div className="relative">
          {children}
        </div>
      </div>
    </div>
  )
}

export default ModernChartContainer

