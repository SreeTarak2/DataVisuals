import React, { useState } from 'react'
import { 
  BarChart3, 
  TrendingUp, 
  Activity, 
  Zap, 
  Cpu, 
  Beaker, 
  Database,
  ChevronRight,
  Play,
  Pause,
  RotateCcw,
  Download,
  Share
} from 'lucide-react'
import PlotlyChart from './PlotlyChart'

interface AdvancedAnalyticsProps {
  data: any[]
  fields: string[]
  isNormal?: boolean
  onExport?: () => void
  onShare?: () => void
}

const AdvancedAnalytics: React.FC<AdvancedAnalyticsProps> = ({
  data,
  fields,
  isNormal = false,
  onExport,
  onShare
}) => {
  const [activeTab, setActiveTab] = useState('correlation')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisResults, setAnalysisResults] = useState<any>(null)

  const tabs = [
    { id: 'correlation', name: 'Correlation Analysis', icon: BarChart3 },
    { id: 'distribution', name: 'Distribution Analysis', icon: Activity },
    { id: 'outliers', name: 'Outlier Detection', icon: Zap },
    { id: 'regression', name: 'Regression Analysis', icon: TrendingUp },
    { id: 'clustering', name: 'Clustering', icon: Cpu },
    { id: 'hypothesis', name: 'Hypothesis Testing', icon: Beaker }
  ]

  const runAnalysis = async (analysisType: string) => {
    setIsAnalyzing(true)
    
    // Simulate analysis delay
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    // Mock analysis results
    const mockResults = {
      correlation: {
        title: 'Correlation Matrix',
        description: 'Pearson correlation coefficients between numeric variables',
        results: generateCorrelationResults(),
        chartType: 'heatmap'
      },
      distribution: {
        title: 'Distribution Analysis',
        description: 'Statistical distribution of key variables',
        results: generateDistributionResults(),
        chartType: 'histogram'
      },
      outliers: {
        title: 'Outlier Detection',
        description: 'Statistical outliers using IQR method',
        results: generateOutlierResults(),
        chartType: 'box_plot'
      },
      regression: {
        title: 'Linear Regression',
        description: 'R-squared and regression coefficients',
        results: generateRegressionResults(),
        chartType: 'scatter_plot'
      },
      clustering: {
        title: 'K-Means Clustering',
        description: 'Data segmentation using unsupervised learning',
        results: generateClusteringResults(),
        chartType: 'scatter_plot'
      },
      hypothesis: {
        title: 'Statistical Tests',
        description: 'T-tests and ANOVA results',
        results: generateHypothesisResults(),
        chartType: 'bar_chart'
      }
    }
    
    setAnalysisResults(mockResults[analysisType as keyof typeof mockResults])
    setIsAnalyzing(false)
  }

  const generateCorrelationResults = () => ({
    matrix: [
      [1.0, 0.85, 0.23, -0.45],
      [0.85, 1.0, 0.31, -0.38],
      [0.23, 0.31, 1.0, 0.12],
      [-0.45, -0.38, 0.12, 1.0]
    ],
    fields: fields.slice(0, 4),
    strongest: { field1: fields[0], field2: fields[1], correlation: 0.85 },
    weakest: { field1: fields[0], field2: fields[3], correlation: -0.45 }
  })

  const generateDistributionResults = () => ({
    skewness: { value: 0.23, interpretation: 'Slightly right-skewed' },
    kurtosis: { value: 2.1, interpretation: 'Normal distribution' },
    normality: { pValue: 0.15, isNormal: true },
    outliers: { count: 3, percentage: 2.1 }
  })

  const generateOutlierResults = () => ({
    total: data.length,
    outliers: 3,
    percentage: 2.1,
    method: 'IQR (Interquartile Range)',
    threshold: 1.5
  })

  const generateRegressionResults = () => ({
    rSquared: 0.73,
    adjustedRSquared: 0.71,
    fStatistic: 45.2,
    pValue: 0.001,
    coefficients: [
      { variable: 'Intercept', value: 12.5, pValue: 0.001 },
      { variable: fields[0], value: 0.85, pValue: 0.001 },
      { variable: fields[1], value: -0.23, pValue: 0.05 }
    ]
  })

  const generateClusteringResults = () => ({
    clusters: 3,
    silhouette: 0.68,
    inertia: 245.7,
    centroids: [
      { x: 25.3, y: 45.7 },
      { x: 67.8, y: 23.1 },
      { x: 89.2, y: 78.4 }
    ]
  })

  const generateHypothesisResults = () => ({
    tTest: { statistic: 2.34, pValue: 0.023, significant: true },
    anova: { fStatistic: 4.56, pValue: 0.012, significant: true },
    chiSquare: { statistic: 8.92, pValue: 0.03, significant: true }
  })

  const getTabIcon = (tab: any) => {
    const Icon = tab.icon
    return <Icon className="w-4 h-4" />
  }

  const getSignificanceColor = (pValue: number) => {
    if (pValue < 0.001) return 'text-red-400'
    if (pValue < 0.01) return 'text-orange-400'
    if (pValue < 0.05) return 'text-yellow-400'
    return 'text-green-400'
  }

  const getSignificanceText = (pValue: number) => {
    if (pValue < 0.001) return 'Highly Significant (p < 0.001)'
    if (pValue < 0.01) return 'Very Significant (p < 0.01)'
    if (pValue < 0.05) return 'Significant (p < 0.05)'
    return 'Not Significant (p ≥ 0.05)'
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
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className={`
            p-2 rounded-lg
            ${isNormal 
              ? 'bg-blue-100 dark:bg-blue-900/20' 
              : 'bg-gradient-to-r from-cyan-500/20 to-purple-500/20'
            }
          `}>
            <Cpu className={`w-5 h-5 ${
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
              Advanced Analytics
            </h3>
            <p className={`text-sm ${
              isNormal 
                ? 'text-gray-500 dark:text-gray-400' 
                : 'text-slate-400'
            }`}>
              Statistical analysis and machine learning
            </p>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
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
              title="Export Analysis"
            >
              <Download className="w-4 h-4" />
            </button>
          )}
          
          {onShare && (
            <button
              onClick={onShare}
              className={`
                p-2 rounded-lg transition-colors duration-200
                ${isNormal 
                  ? 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700' 
                  : 'text-slate-400 hover:text-white hover:bg-white/10'
                }
              `}
              title="Share Analysis"
            >
              <Share className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 mb-6 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 whitespace-nowrap
              ${activeTab === tab.id
                ? isNormal
                  ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                  : 'bg-gradient-to-r from-cyan-500/20 to-purple-500/20 text-cyan-400 border border-cyan-500/30'
                : isNormal
                  ? 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                  : 'text-slate-400 hover:text-white hover:bg-white/10'
              }
            `}
          >
            {getTabIcon(tab)}
            <span>{tab.name}</span>
          </button>
        ))}
      </div>

      {/* Analysis Content */}
      <div className="space-y-6">
        {/* Run Analysis Button */}
        <div className="flex items-center justify-between">
          <div>
            <h4 className={`text-md font-medium ${
              isNormal 
                ? 'text-gray-900 dark:text-white' 
                : 'text-white'
            }`}>
              {tabs.find(t => t.id === activeTab)?.name}
            </h4>
            <p className={`text-sm ${
              isNormal 
                ? 'text-gray-500 dark:text-gray-400' 
                : 'text-slate-400'
            }`}>
              {tabs.find(t => t.id === activeTab)?.name === 'Correlation Analysis' 
                ? 'Analyze relationships between variables'
                : tabs.find(t => t.id === activeTab)?.name === 'Distribution Analysis'
                ? 'Examine data distribution patterns'
                : 'Run statistical analysis'
              }
            </p>
          </div>
          
          <button
            onClick={() => runAnalysis(activeTab)}
            disabled={isAnalyzing}
            className={`
              flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
              ${isAnalyzing
                ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                : isNormal
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-600 hover:to-purple-700 text-white'
              }
            `}
          >
            {isAnalyzing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-400"></div>
                <span>Analyzing...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                <span>Run Analysis</span>
              </>
            )}
          </button>
        </div>

        {/* Analysis Results */}
        {analysisResults && (
          <div className="space-y-4">
            {/* Results Summary */}
            <div className={`
              p-4 rounded-xl border
              ${isNormal 
                ? 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700' 
                : 'bg-white/5 border-white/10'
              }
            `}>
              <h5 className={`text-sm font-medium mb-2 ${
                isNormal 
                  ? 'text-gray-900 dark:text-white' 
                  : 'text-white'
              }`}>
                {analysisResults.title}
              </h5>
              <p className={`text-sm ${
                isNormal 
                  ? 'text-gray-600 dark:text-gray-400' 
                  : 'text-slate-400'
              }`}>
                {analysisResults.description}
              </p>
            </div>

            {/* Statistical Results */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(analysisResults.results).map(([key, value]: [string, any]) => (
                <div key={key} className={`
                  p-3 rounded-lg border
                  ${isNormal 
                    ? 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700' 
                    : 'bg-white/5 border-white/10'
                  }
                `}>
                  <div className={`text-xs font-medium mb-1 ${
                    isNormal 
                      ? 'text-gray-500 dark:text-gray-400' 
                      : 'text-slate-400'
                  }`}>
                    {key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                  </div>
                  <div className={`text-sm ${
                    isNormal 
                      ? 'text-gray-900 dark:text-white' 
                      : 'text-white'
                  }`}>
                    {typeof value === 'number' ? value.toFixed(3) : 
                     typeof value === 'object' ? JSON.stringify(value) : 
                     String(value)}
                  </div>
                  {key.includes('pValue') && (
                    <div className={`text-xs mt-1 ${getSignificanceColor(value)}`}>
                      {getSignificanceText(value)}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Chart Visualization */}
            <div className="h-96">
              <PlotlyChart
                data={data}
                chartType={analysisResults.chartType}
                fields={fields}
                isNormal={isNormal}
                showStatistics={true}
                title={analysisResults.title}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default AdvancedAnalytics

