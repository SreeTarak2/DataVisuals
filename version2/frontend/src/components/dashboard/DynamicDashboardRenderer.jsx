import React, { Suspense, lazy } from 'react'
import { motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { SkeletonChartCard, SkeletonInfoCard, SkeletonTableCard } from '../ui/SkeletonCard'

// Lazy load heavy components for better performance
const KpiCard = lazy(() => import('./KpiCard'))
const ChartRenderer = lazy(() => import('./ChartRenderer'))
const DataTable = lazy(() => import('./DataTable'))
const InsightCard = lazy(() => import('./InsightCard'))

const LoadingFallback = ({ type }) => {
  switch (type) {
    case 'chart':
    case 'hero_chart':
      return <SkeletonChartCard />
    case 'table':
      return <SkeletonTableCard />
    case 'insight':
    case 'info':
      return <SkeletonInfoCard />
    default:
      return <SkeletonInfoCard />
  }
}

const RenderComponent = ({ config, index, datasetInfo }) => {
  const { type, title, ...componentProps } = config

  const getComponentSize = () => {
    // Improved sizing for better layout
    switch (type) {
      case 'hero_chart':
        return 'lg:col-span-12' // Full width for main chart
      case 'kpi':
        return 'lg:col-span-3' // 4 KPIs per row
      case 'chart':
        return 'lg:col-span-6' // 2 charts per row
      case 'insight':
      case 'info':
        return 'lg:col-span-6' // 2 insights per row
      case 'table':
        return 'lg:col-span-12' // Full width for tables
      default:
        return 'lg:col-span-6' // Default to 2 per row
    }
  }

  const getAnimationDelay = () => index * 0.1

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: getAnimationDelay() }}
      className={`${getComponentSize()} group`}
    >
      <Suspense fallback={<LoadingFallback type={type} />}>
        <div className={`bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 ${
          type === 'hero_chart' ? 'h-96' : // Increased height for main chart
          type === 'chart' ? 'h-80' : // Increased height for regular charts
          type === 'table' ? 'h-96' : // Increased height for tables
          type === 'insight' || type === 'info' ? 'h-48' : // Increased height for insights
          'h-64' // Default height
        }`}>
          {renderComponentByType(type, { ...componentProps, title, datasetInfo })}
        </div>
      </Suspense>
    </motion.div>
  )
}

const renderComponentByType = (type, props) => {
  switch (type) {
    case 'kpi':
      return <KpiCard {...props} />
    case 'chart':
    case 'hero_chart':
      return <ChartRenderer {...props} />
    case 'table':
      return <DataTable {...props} />
    case 'insight':
      return <InsightCard {...props} />
    case 'info':
      // Handle info type components as insights
      return <InsightCard {...props} />
    default:
      // Instead of showing "Unknown component type", render as a chart if it has chart data
      if (props.chart_type && props.data) {
        return <ChartRenderer {...props} />
      }
      // Otherwise render as insight
      return <InsightCard {...props} />
  }
}

const DynamicDashboardRenderer = ({ layout, datasetInfo, loading }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
        {Array.from({ length: 6 }).map((_, i) => (
          <LoadingFallback key={i} type="component" />
        ))}
      </div>
    )
  }

  if (!layout || !layout.components || layout.components.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="w-16 h-16 bg-slate-800 rounded-xl flex items-center justify-center mx-auto mb-4">
          <Loader2 className="w-8 h-8 text-slate-500 animate-spin" />
        </div>
        <h3 className="text-lg font-semibold text-slate-300 mb-2">Generating Dashboard</h3>
        <p className="text-slate-400">AI is analyzing your data and creating the perfect dashboard layout...</p>
      </div>
    )
  }

  const gridStyle = layout.layout_grid || 'repeat(12, 1fr)'

  return (
    <div 
      className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]"
      style={{ gridTemplateColumns: gridStyle }}
    >
      {layout.components.map((component, index) => (
        <RenderComponent
          key={`${component.type}-${index}`}
          config={component}
          index={index}
          datasetInfo={datasetInfo}
        />
      ))}
    </div>
  )
}

export default DynamicDashboardRenderer
