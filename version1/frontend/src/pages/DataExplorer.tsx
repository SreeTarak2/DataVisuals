import React, { useState, useEffect } from 'react'
import { 
  Search, 
  BarChart3, 
  TrendingUp, 
  PieChart, 
  Eye, 
  Download,
  Filter,
  RefreshCw,
  Lightbulb,
  Target,
  Zap,
  Activity,
  CheckCircle,
  AlertCircle,
  Database,
  FileText,
  BarChart,
  LineChart,
} from 'lucide-react'
import axios from 'axios'
import toast from 'react-hot-toast'
import DataVisualization from '../components/DataVisualization'

interface Dataset {
  id: string
  filename: string
  size: number
  row_count: number
  column_count: number
  upload_date: string
  columns?: string[]
  data?: any[]
}

interface DataSummary {
  totalRows: number
  totalColumns: number
  dataTypes: { [key: string]: string }
  missingValues: { [key: string]: number }
  uniqueValues: { [key: string]: number }
  topCategories: { [key: string]: any[] }
  correlations: { [key: string]: number }
}

const DataExplorer: React.FC = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null)
  const [dataSummary, setDataSummary] = useState<DataSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'overview' | 'visualizations' | 'insights'>('overview')
  const [chartData, setChartData] = useState<any[]>([])
  const [selectedColumns, setSelectedColumns] = useState<string[]>([])

  // Load datasets on component mount
  useEffect(() => {
    loadDatasets()
  }, [])

  const loadDatasets = async () => {
    try {
      const response = await axios.get('http://localhost:8000/datasets')
      setDatasets(response.data)
    } catch (error) {
      console.error('Failed to load datasets:', error)
      toast.error('Failed to load datasets')
    }
  }

  const analyzeDataset = async (dataset: Dataset) => {
    setLoading(true)
    setSelectedDataset(dataset)
    setDataSummary(null)
    setChartData([])

    try {
      // Get dataset data
      const response = await axios.get(`http://localhost:8000/datasets/${dataset.id}`)
      const rawData = response.data.data || []
      
      // Generate data summary
      const summary = generateDataSummary(rawData, dataset)
      setDataSummary(summary)
      
      // Generate chart data
      const charts = generateChartData(rawData, dataset)
      setChartData(charts)
      
      toast.success('Dataset analysis completed!')
    } catch (error) {
      console.error('Error analyzing dataset:', error)
      toast.error('Failed to analyze dataset')
    } finally {
      setLoading(false)
    }
  }

  const generateDataSummary = (data: any[], dataset: Dataset): DataSummary => {
    if (data.length === 0) {
      return {
        totalRows: 0,
        totalColumns: 0,
        dataTypes: {},
        missingValues: {},
        uniqueValues: {},
        topCategories: {},
        correlations: {}
      }
    }

    const columns = Object.keys(data[0] || {})
    const dataTypes: { [key: string]: string } = {}
    const missingValues: { [key: string]: number } = {}
    const uniqueValues: { [key: string]: number } = {}
    const topCategories: { [key: string]: any[] } = {}
    const correlations: { [key: string]: number } = {}

    columns.forEach(col => {
      const values = data.map(row => row[col]).filter(val => val !== null && val !== undefined)
      const nonNullValues = values.filter(val => val !== '' && val !== 'N/A')
      
      // Data type detection
      if (nonNullValues.length > 0) {
        const firstValue = nonNullValues[0]
        if (typeof firstValue === 'number') {
          dataTypes[col] = 'numeric'
        } else if (firstValue instanceof Date || (typeof firstValue === 'string' && !isNaN(Date.parse(firstValue)))) {
          dataTypes[col] = 'date'
        } else {
          dataTypes[col] = 'categorical'
        }
      } else {
        dataTypes[col] = 'unknown'
      }

      // Missing values
      missingValues[col] = data.length - nonNullValues.length

      // Unique values
      uniqueValues[col] = new Set(nonNullValues).size

      // Top categories (for categorical data)
      if (dataTypes[col] === 'categorical') {
        const valueCounts: { [key: string]: number } = {}
        nonNullValues.forEach(val => {
          valueCounts[val] = (valueCounts[val] || 0) + 1
        })
        topCategories[col] = Object.entries(valueCounts)
          .sort(([,a], [,b]) => b - a)
          .slice(0, 5)
          .map(([value, count]) => ({ value, count }))
      }
    })

    return {
      totalRows: data.length,
      totalColumns: columns.length,
      dataTypes,
      missingValues,
      uniqueValues,
      topCategories,
      correlations
    }
  }

  const generateChartData = (data: any[], dataset: Dataset) => {
    if (data.length === 0) return []

    const charts: any[] = []
    const columns = Object.keys(data[0] || {})
    const numericColumns = columns.filter(col => 
      data.some(row => typeof row[col] === 'number' && !isNaN(row[col]))
    )
    const categoricalColumns = columns.filter(col => 
      data.some(row => typeof row[col] === 'string' || typeof row[col] === 'boolean')
    )

    // Bar chart for categorical data
    if (categoricalColumns.length > 0) {
      const categoryCol = categoricalColumns[0]
      const valueCounts: { [key: string]: number } = {}
      data.forEach(row => {
        const value = row[categoryCol]
        if (value !== null && value !== undefined && value !== '') {
          valueCounts[value] = (valueCounts[value] || 0) + 1
        }
      })
      
      const barData = Object.entries(valueCounts)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 10)
        .map(([name, value]) => ({ name, value }))

      charts.push({
        type: 'bar_chart',
        title: `Distribution of ${categoryCol}`,
        data: barData,
        fields: ['name', 'value']
      })
    }

    // Line chart for numeric data over time
    if (numericColumns.length > 0 && data.length > 1) {
      const numericCol = numericColumns[0]
      const lineData = data.slice(0, 20).map((row, index) => ({
        name: `Point ${index + 1}`,
        value: row[numericCol] || 0
      }))

      charts.push({
        type: 'line_chart',
        title: `Time Series: ${numericCol}`,
        data: lineData,
        fields: ['name', 'value']
      })
    }

    // Pie chart for categorical distribution
    if (categoricalColumns.length > 0) {
      const categoryCol = categoricalColumns[0]
      const valueCounts: { [key: string]: number } = {}
      data.forEach(row => {
        const value = row[categoryCol]
        if (value !== null && value !== undefined && value !== '') {
          valueCounts[value] = (valueCounts[value] || 0) + 1
        }
      })
      
      const pieData = Object.entries(valueCounts)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 6)
        .map(([name, value]) => ({ name, value }))

      charts.push({
        type: 'pie_chart',
        title: `Categorical Distribution: ${categoryCol}`,
        data: pieData,
        fields: ['name', 'value']
      })
    }

    return charts
  }

  const getDataTypeIcon = (type: string) => {
    switch (type) {
      case 'numeric': return <BarChart3 className="h-4 w-4 text-blue-600" />
      case 'categorical': return <PieChart className="h-4 w-4 text-green-600" />
      case 'date': return <TrendingUp className="h-4 w-4 text-purple-600" />
      default: return <Database className="h-4 w-4 text-gray-600" />
    }
  }

  const getDataTypeColor = (type: string) => {
    switch (type) {
      case 'numeric': return 'blue'
      case 'categorical': return 'green'
      case 'date': return 'purple'
      default: return 'gray'
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="rounded-lg shadow-sm border p-6 mb-8 bg-white border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">
                Data Explorer
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                Explore your data with intelligent insights and visualizations
              </p>
            </div>
            <div className="flex items-center space-x-2 text-sm">
              <Search className="h-4 w-4 text-gray-600" />
              <span className="text-gray-600">
                AI-Powered Analytics
              </span>
            </div>
          </div>
        </div>
            
        {/* Dataset Selection */}
        <div className="rounded-lg shadow-sm border p-6 mb-8 bg-white border-gray-200">
          <h2 className="text-lg font-semibold mb-4 text-gray-900">
            Select Dataset for Analysis
          </h2>
          {datasets.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {datasets.map((dataset) => (
                <div
                  key={dataset.id}
                  className={`
                    p-4 border-2 rounded-lg transition-all cursor-pointer
                    ${selectedDataset?.id === dataset.id
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                    }
                  `}
                  onClick={() => analyzeDataset(dataset)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium truncate text-gray-900">
                        {dataset.filename}
                      </h3>
                      <p className="text-sm truncate text-gray-600">
                        {dataset.row_count.toLocaleString()} rows • {dataset.column_count} columns
                      </p>
                    </div>
                    <Database className="h-4 w-4 text-gray-400" />
                  </div>
                  <div className="text-xs text-gray-500">
                    Uploaded: {new Date(dataset.upload_date).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Database className="h-12 w-12 mx-auto mb-2 text-gray-400" />
              <p className="text-gray-600">
                No datasets available. Upload a dataset to get started.
              </p>
            </div>
          )}
        </div>

        {/* Analysis Results */}
        {selectedDataset && dataSummary && (
          <div className="space-y-8">
            {/* Tabs */}
            <div className="rounded-lg shadow-sm border p-6 bg-white border-gray-200">
              <div className="flex space-x-1 mb-6">
                {[
                  { id: 'overview', label: 'Data Profile', icon: Eye },
                  { id: 'visualizations', label: 'Visualizations', icon: BarChart3 },
                  { id: 'insights', label: 'Statistical Insights', icon: Lightbulb }
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`
                      flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-colors
                      ${activeTab === tab.id
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                      }
                    `}
                  >
                    <tab.icon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Basic Stats */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="p-4 rounded-lg border bg-blue-50 border-blue-200">
                      <div className="flex items-center space-x-2 mb-2">
                        <Database className="h-5 w-5 text-blue-600" />
                        <h3 className="font-medium text-blue-900">
                          Dataset Size
                        </h3>
                      </div>
                      <p className="text-2xl font-bold text-blue-700">
                        {dataSummary.totalRows.toLocaleString()}
                      </p>
                    </div>

                    <div className="p-4 rounded-lg border bg-green-50 border-green-200">
                      <div className="flex items-center space-x-2 mb-2">
                        <FileText className="h-5 w-5 text-green-600" />
                        <h3 className="font-medium text-green-900">
                          Columns
                        </h3>
                      </div>
                      <p className="text-2xl font-bold text-green-700">
                        {dataSummary.totalColumns}
                      </p>
                    </div>

                    <div className="p-4 rounded-lg border bg-purple-50 border-purple-200">
                      <div className="flex items-center space-x-2 mb-2">
                        <CheckCircle className="h-5 w-5 text-purple-600" />
                        <h3 className="font-medium text-purple-900">
                          Completeness
                        </h3>
                      </div>
                      <p className="text-2xl font-bold text-purple-700">
                        {Math.round((1 - Object.values(dataSummary.missingValues).reduce((a, b) => a + b, 0) / (dataSummary.totalRows * dataSummary.totalColumns)) * 100)}%
                      </p>
                    </div>
                  </div>

                  {/* Column Details */}
                  <div>
                    <h3 className="text-lg font-semibold mb-4 text-gray-900">
                      Column Analysis
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {Object.entries(dataSummary.dataTypes).map(([column, type]) => (
                        <div
                          key={column}
                          className="p-4 rounded-lg border bg-gray-50 border-gray-200"
                        >
                          <div className="flex items-center space-x-2 mb-2">
                            {getDataTypeIcon(type)}
                            <h4 className="font-medium text-gray-900">
                              {column}
                            </h4>
                          </div>
                          <div className="space-y-1 text-sm">
                            <p className="text-gray-600">
                              Type: <span className="capitalize">{type}</span>
                            </p>
                            <p className="text-gray-600">
                              Unique: {dataSummary.uniqueValues[column]}
                            </p>
                            {dataSummary.missingValues[column] > 0 && (
                              <p className="text-orange-600">
                                Missing: {dataSummary.missingValues[column]}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'visualizations' && (
                <div className="space-y-6">
                  <h3 className="text-lg font-semibold text-gray-900">
                    Data Visualizations
                  </h3>
                  {chartData.length > 0 ? (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {chartData.map((chart, index) => (
                        <div
                          key={index}
                          className="rounded-lg border p-6 bg-white border-gray-200"
                        >
                          <h4 className="font-medium mb-4 text-gray-900">
                            {chart.title}
                          </h4>
                          <div className="h-80">
                            <DataVisualization
                              chartType={chart.type}
                              data={chart.data}
                              fields={chart.fields}
                              showChat={true}
                              showRecommendations={true}
                              datasetContext={`Dataset: ${selectedDataset.filename}`}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <BarChart3 className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                      <p className="text-gray-600">
                        No visualizations generated
                      </p>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'insights' && (
                <div className="space-y-6">
                  <h3 className="text-lg font-semibold text-gray-900">
                    Statistical Insights
                  </h3>
                  
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-4 rounded-lg border bg-blue-50 border-blue-200">
                        <h4 className="font-medium mb-2 text-blue-900">
                          Data Quality Metrics
                        </h4>
                        <div className="space-y-1 text-sm">
                          <p className="text-blue-800">
                            Completeness: {Math.round((1 - Object.values(dataSummary.missingValues).reduce((a, b) => a + b, 0) / (dataSummary.totalRows * dataSummary.totalColumns)) * 100)}%
                          </p>
                          <p className="text-blue-800">
                            Total Missing Values: {Object.values(dataSummary.missingValues).reduce((a, b) => a + b, 0)}
                          </p>
                        </div>
                      </div>

                      <div className="p-4 rounded-lg border bg-green-50 border-green-200">
                        <h4 className="font-medium mb-2 text-green-900">
                          Data Types Distribution
                        </h4>
                        <div className="space-y-1 text-sm">
                          {(() => {
                            const typeCounts: { [key: string]: number } = {}
                            Object.values(dataSummary.dataTypes).forEach(type => {
                              typeCounts[type] = (typeCounts[type] || 0) + 1
                            })
                            return Object.entries(typeCounts).map(([type, count]) => (
                              <p key={type} className="text-green-800">
                                {type}: {count} columns
                              </p>
                            ))
                          })()}
                        </div>
                      </div>
                    </div>

                    {Object.entries(dataSummary.topCategories).map(([column, categories]) => (
                      <div
                        key={column}
                        className="p-4 rounded-lg border bg-purple-50 border-purple-200"
                      >
                        <h4 className="font-medium mb-2 text-purple-900">
                          Categorical Analysis: {column}
                        </h4>
                        <div className="space-y-1 text-sm">
                          <p className="text-purple-800">
                            Unique Values: {dataSummary.uniqueValues[column]}
                          </p>
                          <div className="mt-2">
                            <p className="font-medium mb-1 text-purple-900">
                              Top Categories:
                            </p>
                            {categories.slice(0, 5).map((item, index) => (
                              <p key={index} className="text-purple-800">
                                {item.value}: {item.count} ({Math.round((item.count / dataSummary.totalRows) * 100)}%)
                              </p>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {loading && (
          <div className="text-center py-8">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2 text-blue-600" />
            <p className="text-gray-600">Analyzing your data...</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default DataExplorer