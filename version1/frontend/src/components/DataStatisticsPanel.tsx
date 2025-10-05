import React, { useState, useEffect } from 'react'
import { 
  BarChart3, 
  TrendingUp, 
  Activity, 
  Zap, 
  Cpu, 
  Database,
  ChevronDown,
  ChevronUp,
  Info,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'
import PlotlyChart from './PlotlyChart'

interface DataStatisticsPanelProps {
  data: any[]
  columns: string[]
  isNormal?: boolean
}

interface ColumnStats {
  name: string
  type: string
  count: number
  nullCount: number
  nullPercentage: number
  uniqueCount: number
  uniquePercentage: number
  stats: {
    mean?: number
    median?: number
    mode?: any
    std?: number
    min?: number
    max?: number
    q1?: number
    q3?: number
    skewness?: number
    kurtosis?: number
  }
  distribution?: any[]
  outliers?: any[]
}

const DataStatisticsPanel: React.FC<DataStatisticsPanelProps> = ({
  data,
  columns,
  isNormal = false
}) => {
  const [columnStats, setColumnStats] = useState<ColumnStats[]>([])
  const [selectedColumn, setSelectedColumn] = useState<string>('')
  const [isExpanded, setIsExpanded] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (data.length > 0 && columns.length > 0) {
      calculateStatistics()
    }
  }, [data, columns])

  const calculateStatistics = async () => {
    setLoading(true)
    
    // Simulate calculation delay for better UX
    await new Promise(resolve => setTimeout(resolve, 500))
    
    const stats: ColumnStats[] = columns.map(column => {
      const values = data.map(row => row[column]).filter(v => v !== null && v !== undefined)
      const isNumeric = values.every(v => typeof v === 'number' || !isNaN(Number(v)))
      
      const stats: ColumnStats = {
        name: column,
        type: isNumeric ? 'numeric' : 'categorical',
        count: values.length,
        nullCount: data.length - values.length,
        nullPercentage: ((data.length - values.length) / data.length) * 100,
        uniqueCount: new Set(values).size,
        uniquePercentage: (new Set(values).size / values.length) * 100,
        stats: {}
      }

      if (isNumeric && values.length > 0) {
        const numericValues = values.map(v => Number(v)).sort((a, b) => a - b)
        const mean = numericValues.reduce((a, b) => a + b, 0) / numericValues.length
        const variance = numericValues.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / numericValues.length
        const std = Math.sqrt(variance)
        
        stats.stats = {
          mean: Number(mean.toFixed(2)),
          median: numericValues[Math.floor(numericValues.length / 2)],
          std: Number(std.toFixed(2)),
          min: numericValues[0],
          max: numericValues[numericValues.length - 1],
          q1: numericValues[Math.floor(numericValues.length * 0.25)],
          q3: numericValues[Math.floor(numericValues.length * 0.75)],
          skewness: calculateSkewness(numericValues, mean, std),
          kurtosis: calculateKurtosis(numericValues, mean, std)
        }

        // Detect outliers using IQR method
        const iqr = stats.stats.q3! - stats.stats.q1!
        const lowerBound = stats.stats.q1! - 1.5 * iqr
        const upperBound = stats.stats.q3! + 1.5 * iqr
        stats.outliers = numericValues.filter(v => v < lowerBound || v > upperBound)
      } else {
        // Categorical statistics
        const valueCounts = values.reduce((acc: any, val) => {
          acc[val] = (acc[val] || 0) + 1
          return acc
        }, {})
        
        const mode = Object.keys(valueCounts).reduce((a, b) => valueCounts[a] > valueCounts[b] ? a : b)
        stats.stats.mode = mode
        stats.distribution = Object.entries(valueCounts)
          .map(([value, count]) => ({ value, count }))
          .sort((a: any, b: any) => b.count - a.count)
      }

      return stats
    })

    setColumnStats(stats)
    if (stats.length > 0) {
      setSelectedColumn(stats[0].name)
    }
    setLoading(false)
  }

  const calculateSkewness = (values: number[], mean: number, std: number): number => {
    if (std === 0) return 0
    const n = values.length
    const skewness = values.reduce((sum, val) => sum + Math.pow((val - mean) / std, 3), 0) / n
    return Number(skewness.toFixed(3))
  }

  const calculateKurtosis = (values: number[], mean: number, std: number): number => {
    if (std === 0) return 0
    const n = values.length
    const kurtosis = values.reduce((sum, val) => sum + Math.pow((val - mean) / std, 4), 0) / n - 3
    return Number(kurtosis.toFixed(3))
  }

  const getQualityScore = (stats: ColumnStats): number => {
    let score = 100
    
    // Deduct for null values
    score -= stats.nullPercentage * 0.5
    
    // Deduct for low uniqueness (potential duplicates)
    if (stats.uniquePercentage < 10) {
      score -= 20
    }
    
    // Deduct for outliers in numeric columns
    if (stats.type === 'numeric' && stats.outliers && stats.outliers.length > stats.count * 0.1) {
      score -= 15
    }
    
    return Math.max(0, Math.round(score))
  }

  const getQualityColor = (score: number) => {
    if (score >= 90) return 'text-green-400'
    if (score >= 70) return 'text-yellow-400'
    return 'text-red-400'
  }

  const getQualityIcon = (score: number) => {
    if (score >= 90) return <CheckCircle className="w-4 h-4 text-green-400" />
    if (score >= 70) return <AlertTriangle className="w-4 h-4 text-yellow-400" />
    return <AlertTriangle className="w-4 h-4 text-red-400" />
  }

  const selectedStats = columnStats.find(s => s.name === selectedColumn)

  return (
    <div className={`
      rounded-lg shadow-sm border p-6
      ${isNormal 
        ? 'bg-white border-gray-200' 
        : 'backdrop-blur-xl bg-white/10 border-white/20'
      }
    `}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className={`
            p-2 rounded-lg
            ${isNormal 
              ? 'bg-green-100' 
              : 'bg-gradient-to-r from-green-500/20 to-emerald-500/20'
            }
          `}>
            <Activity className={`w-5 h-5 ${
              isNormal ? 'text-green-600' : 'text-green-400'
            }`} />
          </div>
          <div>
            <h3 className={`text-lg font-semibold ${
              isNormal 
                ? 'text-gray-900' 
                : 'text-white'
            }`}>
              {isNormal ? 'Data Statistics' : 'Advanced Data Statistics'}
            </h3>
            <p className={`text-sm ${
              isNormal 
                ? 'text-gray-500' 
                : 'text-slate-400'
            }`}>
              {isNormal 
                ? 'Overview of your data quality and distribution'
                : 'Comprehensive statistical analysis with distribution insights'
              }
            </p>
          </div>
        </div>

        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={`
            p-2 rounded-lg transition-colors
            ${isNormal 
              ? 'text-gray-400 hover:text-gray-600 hover:bg-gray-100' 
              : 'text-slate-400 hover:text-white hover:bg-white/10'
            }
          `}
        >
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {isExpanded && (
        <div className="space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className={`text-sm ${
                  isNormal ? 'text-gray-600' : 'text-slate-400'
                }`}>
                  Calculating statistics...
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Column Selector */}
              <div>
                <label className={`text-sm font-medium ${
                  isNormal ? 'text-gray-700' : 'text-slate-300'
                }`}>
                  Select Column for Detailed Analysis
                </label>
                <select
                  value={selectedColumn}
                  onChange={(e) => setSelectedColumn(e.target.value)}
                  className={`
                    w-full mt-2 px-3 py-2 rounded-lg border text-sm
                    ${isNormal 
                      ? 'bg-white border-gray-300 text-gray-900' 
                      : 'bg-slate-800 border-slate-600 text-white'
                    }
                  `}
                >
                  {columnStats.map(stat => (
                    <option key={stat.name} value={stat.name}>
                      {stat.name} ({stat.type})
                    </option>
                  ))}
                </select>
              </div>

              {/* Column Statistics Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {columnStats.map(stat => {
                  const qualityScore = getQualityScore(stat)
                  return (
                    <div key={stat.name} className={`
                      p-4 rounded-lg border cursor-pointer transition-all
                      ${selectedColumn === stat.name
                        ? isNormal
                          ? 'bg-blue-50 border-blue-200'
                          : 'bg-cyan-500/10 border-cyan-500/30'
                        : isNormal
                          ? 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                          : 'bg-white/5 border-white/10 hover:bg-white/10'
                      }
                    `} onClick={() => setSelectedColumn(stat.name)}>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className={`font-medium ${
                          isNormal ? 'text-gray-900' : 'text-white'
                        }`}>
                          {stat.name}
                        </h4>
                        {getQualityIcon(qualityScore)}
                      </div>
                      
                      <div className="space-y-1">
                        <div className={`text-xs ${
                          isNormal ? 'text-gray-600' : 'text-slate-400'
                        }`}>
                          Type: <span className="capitalize">{stat.type}</span>
                        </div>
                        <div className={`text-xs ${
                          isNormal ? 'text-gray-600' : 'text-slate-400'
                        }`}>
                          Values: {stat.count.toLocaleString()}
                        </div>
                        <div className={`text-xs ${
                          isNormal ? 'text-gray-600' : 'text-slate-400'
                        }`}>
                          Unique: {stat.uniquePercentage.toFixed(1)}%
                        </div>
                        <div className={`text-xs ${
                          isNormal ? 'text-gray-600' : 'text-slate-400'
                        }`}>
                          Nulls: {stat.nullPercentage.toFixed(1)}%
                        </div>
                        <div className={`text-xs font-medium ${getQualityColor(qualityScore)}`}>
                          Quality: {qualityScore}%
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Detailed Statistics */}
              {selectedStats && (
                <div className="space-y-6">
                  {/* Summary Stats */}
                  <div className={`
                    p-4 rounded-lg border
                    ${isNormal 
                      ? 'bg-gray-50 border-gray-200' 
                      : 'bg-white/5 border-white/10'
                    }
                  `}>
                    <h4 className={`text-md font-medium mb-4 ${
                      isNormal ? 'text-gray-900' : 'text-white'
                    }`}>
                      {selectedStats.name} - Detailed Statistics
                    </h4>
                    
                    {selectedStats.type === 'numeric' ? (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-gray-500' : 'text-slate-400'
                          }`}>
                            Mean
                          </div>
                          <div className={`text-lg font-semibold ${
                            isNormal ? 'text-gray-900' : 'text-white'
                          }`}>
                            {selectedStats.stats.mean}
                          </div>
                        </div>
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-gray-500' : 'text-slate-400'
                          }`}>
                            Median
                          </div>
                          <div className={`text-lg font-semibold ${
                            isNormal ? 'text-gray-900' : 'text-white'
                          }`}>
                            {selectedStats.stats.median}
                          </div>
                        </div>
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-gray-500' : 'text-slate-400'
                          }`}>
                            Std Dev
                          </div>
                          <div className={`text-lg font-semibold ${
                            isNormal ? 'text-gray-900' : 'text-white'
                          }`}>
                            {selectedStats.stats.std}
                          </div>
                        </div>
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-gray-500' : 'text-slate-400'
                          }`}>
                            Range
                          </div>
                          <div className={`text-lg font-semibold ${
                            isNormal ? 'text-gray-900' : 'text-white'
                          }`}>
                            {selectedStats.stats.min} - {selectedStats.stats.max}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-gray-500' : 'text-slate-400'
                          }`}>
                            Most Common Value
                          </div>
                          <div className={`text-lg font-semibold ${
                            isNormal ? 'text-gray-900' : 'text-white'
                          }`}>
                            {selectedStats.stats.mode}
                          </div>
                        </div>
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-gray-500' : 'text-slate-400'
                          }`}>
                            Unique Values
                          </div>
                          <div className={`text-lg font-semibold ${
                            isNormal ? 'text-gray-900' : 'text-white'
                          }`}>
                            {selectedStats.uniqueCount}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Distribution Chart */}
                  <div className="h-96">
                    <PlotlyChart
                      data={data}
                      chartType={selectedStats.type === 'numeric' ? 'histogram' : 'pie_chart'}
                      fields={[selectedStats.name]}
                      isNormal={isNormal}
                      showStatistics={!isNormal}
                      title={`${selectedStats.name} Distribution`}
                    />
                  </div>

                  {/* Advanced Stats for Expert Users */}
                  {!isNormal && selectedStats.type === 'numeric' && (
                    <div className={`
                      p-4 rounded-lg border
                      ${isNormal 
                        ? 'bg-blue-50 border-blue-200' 
                        : 'bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border-cyan-500/20'
                      }
                    `}>
                      <h5 className={`text-sm font-medium mb-3 ${
                        isNormal ? 'text-blue-800' : 'text-cyan-300'
                      }`}>
                        Advanced Statistical Measures
                      </h5>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-blue-700' : 'text-cyan-400'
                          }`}>
                            Skewness
                          </div>
                          <div className={`text-sm font-semibold ${
                            isNormal ? 'text-blue-900' : 'text-cyan-200'
                          }`}>
                            {selectedStats.stats.skewness}
                          </div>
                        </div>
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-blue-700' : 'text-cyan-400'
                          }`}>
                            Kurtosis
                          </div>
                          <div className={`text-sm font-semibold ${
                            isNormal ? 'text-blue-900' : 'text-cyan-200'
                          }`}>
                            {selectedStats.stats.kurtosis}
                          </div>
                        </div>
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-blue-700' : 'text-cyan-400'
                          }`}>
                            Q1 (25%)
                          </div>
                          <div className={`text-sm font-semibold ${
                            isNormal ? 'text-blue-900' : 'text-cyan-200'
                          }`}>
                            {selectedStats.stats.q1}
                          </div>
                        </div>
                        <div>
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-blue-700' : 'text-cyan-400'
                          }`}>
                            Q3 (75%)
                          </div>
                          <div className={`text-sm font-semibold ${
                            isNormal ? 'text-blue-900' : 'text-cyan-200'
                          }`}>
                            {selectedStats.stats.q3}
                          </div>
                        </div>
                      </div>
                      
                      {selectedStats.outliers && selectedStats.outliers.length > 0 && (
                        <div className="mt-4">
                          <div className={`text-xs font-medium ${
                            isNormal ? 'text-blue-700' : 'text-cyan-400'
                          }`}>
                            Outliers Detected: {selectedStats.outliers.length}
                          </div>
                          <div className={`text-xs ${
                            isNormal ? 'text-blue-600' : 'text-cyan-300'
                          }`}>
                            Values: {selectedStats.outliers.slice(0, 5).join(', ')}
                            {selectedStats.outliers.length > 5 && '...'}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default DataStatisticsPanel

