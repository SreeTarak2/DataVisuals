import React from 'react'
import { TrendingUp, TrendingDown, DollarSign, Users, Activity } from 'lucide-react'

const KpiCard = ({ title, value, change, changeType, icon, description }) => {
  const getIcon = () => {
    switch (icon) {
      case 'trending_up':
        return <TrendingUp className="w-5 h-5" />
      case 'trending_down':
        return <TrendingDown className="w-5 h-5" />
      case 'dollar':
        return <DollarSign className="w-5 h-5" />
      case 'users':
        return <Users className="w-5 h-5" />
      case 'activity':
        return <Activity className="w-5 h-5" />
      default:
        return <TrendingUp className="w-5 h-5" />
    }
  }

  const getChangeColor = () => {
    if (changeType === 'positive') return 'text-green-400'
    if (changeType === 'negative') return 'text-red-400'
    return 'text-slate-400'
  }

  const getChangeIcon = () => {
    if (changeType === 'positive') return <TrendingUp className="w-3 h-3" />
    if (changeType === 'negative') return <TrendingDown className="w-3 h-3" />
    return null
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">
          {title}
        </div>
        <div className={`w-2 h-2 rounded-full ${
          changeType === 'positive' ? 'bg-green-400' : 
          changeType === 'negative' ? 'bg-red-400' : 'bg-slate-400'
        }`} />
      </div>
      
      <div className="flex-1 flex flex-col justify-center">
        <div className="text-3xl font-bold text-white mb-2">
          {value}
        </div>
        
        {change && (
          <div className={`flex items-center gap-1 text-sm ${getChangeColor()}`}>
            {getChangeIcon()}
            <span>{change}</span>
          </div>
        )}
        
        {description && (
          <div className="text-xs text-slate-500 mt-2">
            {description}
          </div>
        )}
      </div>
    </div>
  )
}

export default KpiCard

