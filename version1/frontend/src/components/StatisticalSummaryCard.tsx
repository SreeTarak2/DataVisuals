import React from 'react'
import { TrendingUp, TrendingDown, Activity, Zap, AlertCircle, CheckCircle } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  change?: string
  trend?: 'up' | 'down' | 'neutral'
  icon: React.ComponentType<{ className?: string }>
  description?: string
  isNormal?: boolean
}

const StatCard: React.FC<StatCardProps> = ({ 
  title, 
  value, 
  change, 
  trend, 
  icon: Icon, 
  description,
  isNormal = false 
}) => {
  const getTrendIcon = () => {
    if (trend === 'up') return <TrendingUp className="w-4 h-4" />
    if (trend === 'down') return <TrendingDown className="w-4 h-4" />
    return <Activity className="w-4 h-4" />
  }

  const getTrendColor = () => {
    if (trend === 'up') return 'text-green-400'
    if (trend === 'down') return 'text-red-400'
    return 'text-slate-400'
  }

  return (
    <div className={`
      backdrop-blur-xl border rounded-2xl p-6 shadow-2xl
      hover:shadow-3xl transition-all duration-300
      ${isNormal 
        ? 'bg-white/95 dark:bg-slate-800/95 border-gray-200 dark:border-slate-700'
        : 'bg-white/10 border-white/20 hover:bg-white/20'
      }
    `}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className={`text-sm font-medium ${
            isNormal 
              ? 'text-gray-600 dark:text-gray-400' 
              : 'text-slate-400'
          }`}>
            {title}
          </p>
          <p className={`text-3xl font-bold mt-2 ${
            isNormal 
              ? 'text-gray-900 dark:text-white' 
              : 'text-white'
          }`}>
            {value}
          </p>
          {change && (
            <div className={`flex items-center mt-2 ${getTrendColor()}`}>
              {getTrendIcon()}
              <span className="text-sm font-medium ml-1">{change}</span>
            </div>
          )}
          {description && (
            <p className={`text-xs mt-2 ${
              isNormal 
                ? 'text-gray-500 dark:text-gray-500' 
                : 'text-slate-500'
            }`}>
              {description}
            </p>
          )}
        </div>
        <div className={`
          p-3 rounded-xl
          ${isNormal 
            ? 'bg-blue-100 dark:bg-blue-900/20' 
            : 'bg-gradient-to-r from-cyan-500/20 to-purple-500/20'
          }
        `}>
          <Icon className={`w-6 h-6 ${
            isNormal 
              ? 'text-blue-600 dark:text-blue-400' 
              : 'text-cyan-400'
          }`} />
        </div>
      </div>
    </div>
  )
}

export default StatCard

