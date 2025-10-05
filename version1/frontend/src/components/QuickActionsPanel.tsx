import React from 'react'
import { 
  Upload, 
  Download, 
  RefreshCw, 
  Settings, 
  Zap, 
  BarChart3, 
  Database, 
  Code,
  Share,
  Play,
  Pause,
  RotateCcw
} from 'lucide-react'

interface QuickAction {
  id: string
  title: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  action: () => void
  variant?: 'primary' | 'secondary' | 'accent'
  disabled?: boolean
}

interface QuickActionsPanelProps {
  isNormal?: boolean
  onUpload?: () => void
  onExport?: () => void
  onRefresh?: () => void
  onSettings?: () => void
  onAnalyze?: () => void
  onVisualize?: () => void
  onExportCode?: () => void
  onShare?: () => void
}

const QuickActionsPanel: React.FC<QuickActionsPanelProps> = ({
  isNormal = false,
  onUpload,
  onExport,
  onRefresh,
  onSettings,
  onAnalyze,
  onVisualize,
  onExportCode,
  onShare
}) => {
  const getActions = (): QuickAction[] => {
    if (isNormal) {
      return [
        {
          id: 'upload',
          title: 'Upload Data',
          description: 'Add new dataset',
          icon: Upload,
          action: onUpload || (() => {}),
          variant: 'primary'
        },
        {
          id: 'export',
          title: 'Export Report',
          description: 'Download PDF',
          icon: Download,
          action: onExport || (() => {}),
          variant: 'secondary'
        },
        {
          id: 'refresh',
          title: 'Refresh',
          description: 'Update data',
          icon: RefreshCw,
          action: onRefresh || (() => {}),
          variant: 'secondary'
        },
        {
          id: 'settings',
          title: 'Settings',
          description: 'Preferences',
          icon: Settings,
          action: onSettings || (() => {}),
          variant: 'secondary'
        }
      ]
    } else {
      return [
        {
          id: 'analyze',
          title: 'Run Analysis',
          description: 'Statistical tests',
          icon: Zap,
          action: onAnalyze || (() => {}),
          variant: 'primary'
        },
        {
          id: 'visualize',
          title: 'Create Charts',
          description: 'Interactive plots',
          icon: BarChart3,
          action: onVisualize || (() => {}),
          variant: 'accent'
        },
        {
          id: 'export-code',
          title: 'Export Code',
          description: 'Python/R scripts',
          icon: Code,
          action: onExportCode || (() => {}),
          variant: 'secondary'
        },
        {
          id: 'share',
          title: 'Share Results',
          description: 'Collaborate',
          icon: Share,
          action: onShare || (() => {}),
          variant: 'secondary'
        }
      ]
    }
  }

  const getVariantStyles = (variant: string) => {
    if (isNormal) {
      switch (variant) {
        case 'primary':
          return 'bg-blue-500 hover:bg-blue-600 text-white'
        case 'secondary':
          return 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300'
        default:
          return 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300'
      }
    } else {
      switch (variant) {
        case 'primary':
          return 'bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-600 hover:to-purple-700 text-white'
        case 'accent':
          return 'bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-600 hover:to-pink-700 text-white'
        case 'secondary':
          return 'bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white border border-white/20'
        default:
          return 'bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white border border-white/20'
      }
    }
  }

  const actions = getActions()

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
            ? 'bg-blue-100 dark:bg-blue-900/20' 
            : 'bg-gradient-to-r from-cyan-500/20 to-purple-500/20'
          }
        `}>
          <Zap className={`w-5 h-5 ${
            isNormal 
              ? 'text-blue-600 dark:text-blue-400' 
              : 'text-cyan-400'
          }`} />
        </div>
        <div>
          <h3 className={`text-lg font-semibold ${
            isNormal 
              ? 'text-gray-900 dark:text-white' 
              : 'text-white'
          }`}>
            Quick Actions
          </h3>
          <p className={`text-sm ${
            isNormal 
              ? 'text-gray-500 dark:text-gray-400' 
              : 'text-slate-400'
          }`}>
            {isNormal ? 'Common tasks' : 'Advanced tools'}
          </p>
        </div>
      </div>

      {/* Actions Grid */}
      <div className="grid grid-cols-2 gap-3">
        {actions.map((action) => {
          const Icon = action.icon
          return (
            <button
              key={action.id}
              onClick={action.action}
              disabled={action.disabled}
              className={`
                p-4 rounded-xl transition-all duration-200 text-left
                ${getVariantStyles(action.variant || 'secondary')}
                ${action.disabled ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105'}
              `}
            >
              <div className="flex items-center space-x-3">
                <Icon className="w-5 h-5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {action.title}
                  </p>
                  <p className={`text-xs ${
                    isNormal 
                      ? 'text-gray-500 dark:text-gray-400' 
                      : 'text-slate-400'
                  }`}>
                    {action.description}
                  </p>
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default QuickActionsPanel

