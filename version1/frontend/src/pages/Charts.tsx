import React, { useState } from 'react'
import { BarChart3, LineChart, PieChart, TrendingUp, Activity, Zap } from 'lucide-react'
import DataVisualization from '../components/DataVisualization'
import axios from 'axios'
import toast from 'react-hot-toast'

interface Dataset {
  id: string
  filename: string
  size: number
  row_count: number
  column_count: number
  upload_date: string
  columns: any[]
}

interface ChartType {
  id: string
  name: string
  description: string
  icon: React.ComponentType<any>
  chartType: string
  color: string
}

const Charts: React.FC = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null)
  const [selectedChartType, setSelectedChartType] = useState<string | null>(null)
  const [chartData, setChartData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const chartTypes: ChartType[] = [
    {
      id: 'bar_chart',
      name: 'Bar Chart',
      description: isNormal 
        ? 'Compare different categories or groups at a glance'
        : 'Categorical comparison with statistical significance testing',
      icon: BarChart3,
      chartType: 'bar_chart',
      color: 'primary'
    },
    {
      id: 'line_chart',
      name: 'Line Chart',
      description: isNormal
        ? 'Show trends and patterns over time'
        : 'Temporal analysis with trend detection and forecasting',
      icon: LineChart,
      chartType: 'line_chart',
      color: 'success'
    },
    {
      id: 'pie_chart',
      name: 'Pie Chart',
      description: isNormal
        ? 'Show how different parts make up the whole'
        : 'Proportional composition with percentage breakdowns',
      icon: PieChart,
      chartType: 'pie_chart',
      color: 'accent'
    },
      {
        id: 'scatter_plot',
        name: 'Scatter Plot',
        description: isNormal
          ? 'See relationships between two different measurements'
          : 'Correlation analysis with outlier detection',
        icon: TrendingUp,
        chartType: 'scatter_plot',
        color: 'warning'
      },
    {
      id: 'histogram',
      name: 'Histogram',
      description: isNormal
        ? 'See how your data is spread out and distributed'
        : 'Distribution analysis with statistical properties',
      icon: Activity,
      chartType: 'histogram',
      color: 'info'
    },
    {
      id: 'heatmap',
      name: 'Heatmap',
      description: isNormal
        ? 'Show relationships between many variables using colors'
        : 'Correlation matrix visualization with statistical significance',
      icon: Zap,
      chartType: 'heatmap',
      color: 'error'
    }
  ]

  const loadDatasets = async () => {
    try {
      const response = await axios.get('http://localhost:8000/datasets')
      setDatasets(response.data)
    } catch (error) {
      console.error('Failed to load datasets:', error)
      toast.error('Failed to load datasets')
    }
  }

  const generateChartData = (dataset: Dataset, chartType: string) => {
    const columns = dataset.columns || []
    
    // Special handling for histogram
    if (chartType === 'histogram') {
      const numericCols = columns.filter((col: any) => col.is_numeric)
      const numericCol = numericCols[0]?.name || 'value'
      const histData: any[] = []
      const min = columns.find((col: any) => col.name === numericCol)?.min || 0
      const max = columns.find((col: any) => col.name === numericCol)?.max || 100
      const bins = 5
      const binSize = (max - min) / bins
      
      for (let i = 0; i < bins; i++) {
        const rangeStart = min + i * binSize
        const rangeEnd = min + (i + 1) * binSize
        histData.push({
          range: `${Math.round(rangeStart)}-${Math.round(rangeEnd)}`,
          count: Math.floor(Math.random() * 10) + 1
        })
      }
      return histData
    }
    
    const sampleData: any[] = []
    
    // Generate sample data based on chart type
    for (let i = 0; i < Math.min(20, dataset.row_count); i++) {
      const row: any = {}
      
      columns.forEach((col: any) => {
        if (col.is_numeric) {
          const min = col.min || 0
          const max = col.max || 100
          row[col.name] = Math.floor(Math.random() * (max - min + 1)) + min
        } else if (col.is_categorical) {
          const values = col.sample_values || ['A', 'B', 'C']
          row[col.name] = values[Math.floor(Math.random() * values.length)]
        } else {
          const values = col.sample_values || ['Sample']
          row[col.name] = values[Math.floor(Math.random() * values.length)]
        }
      })
      
      // Add index for line charts
      if (chartType === 'line_chart') {
        row.index = i
      }
      
      sampleData.push(row)
    }
    
    return sampleData
  }

  const getChartFields = (dataset: Dataset, chartType: string) => {
    const columns = dataset.columns || []
    const numericCols = columns.filter((col: any) => col.is_numeric)
    const categoricalCols = columns.filter((col: any) => col.is_categorical)
    
    switch (chartType) {
      case 'bar_chart':
        return [
          categoricalCols[0]?.name || 'category',
          numericCols[0]?.name || 'value'
        ]
      case 'line_chart':
        return [
          'index',
          numericCols[0]?.name || 'value'
        ]
      case 'pie_chart':
        return [
          categoricalCols[0]?.name || 'category'
        ]
      case 'scatter_plot':
        return [
          numericCols[0]?.name || 'x',
          numericCols[1]?.name || numericCols[0]?.name || 'y'
        ]
      case 'histogram':
        return [
          'range',
          'count'
        ]
      case 'heatmap':
        return [
          numericCols[0]?.name || 'x',
          numericCols[1]?.name || numericCols[0]?.name || 'y'
        ]
      default:
        return ['x', 'y']
    }
  }

  const handleChartSelect = async (chartType: string) => {
    if (!selectedDataset) {
      toast.error('Please select a dataset first')
      return
    }

    setLoading(true)
    setSelectedChartType(chartType)
    
    try {
      const data = generateChartData(selectedDataset, chartType)
      setChartData(data)
      toast.success(`${chartTypes.find(c => c.id === chartType)?.name} generated successfully!`)
    } catch (error) {
      console.error('Error generating chart:', error)
      toast.error('Failed to generate chart')
    } finally {
      setLoading(false)
    }
  }

  // Load datasets on component mount
  React.useEffect(() => {
    loadDatasets()
  }, [])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 mb-2">Charts</h1>
        <p className="text-secondary-600">
          {isNormal
            ? 'Create beautiful visualizations from your data. Select a dataset and choose a chart type to get started.'
            : 'Advanced data visualization tools with statistical analysis and interactive chart generation capabilities.'
          }
        </p>
      </div>

      {/* Dataset Selection */}
      <div className="card p-6">
        <h2 className="text-xl font-semibold text-secondary-900 mb-4">Select Dataset</h2>
        {datasets.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {datasets.map((dataset) => (
              <div
                key={dataset.id}
                className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                  selectedDataset?.id === dataset.id
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-secondary-200 hover:border-primary-300'
                }`}
                onClick={() => setSelectedDataset(dataset)}
              >
                <h3 className="font-semibold text-secondary-900">{dataset.filename}</h3>
                <p className="text-sm text-secondary-600">
                  {dataset.row_count} rows • {dataset.column_count} columns
                </p>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-secondary-600 mb-4">No datasets available</p>
            <p className="text-sm text-secondary-500">
              Upload a dataset first to create visualizations
            </p>
          </div>
        )}
      </div>

      {/* Chart Type Selection */}
      {selectedDataset && (
        <div className="card p-6">
          <h2 className="text-xl font-semibold text-secondary-900 mb-4">Choose Chart Type</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {chartTypes.map((chart) => {
              const IconComponent = chart.icon
              return (
                <div
                  key={chart.id}
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    selectedChartType === chart.id
                      ? `border-${chart.color}-500 bg-${chart.color}-50`
                      : 'border-secondary-200 hover:border-primary-300'
                  }`}
                  onClick={() => handleChartSelect(chart.id)}
                >
                  <div className="flex items-center space-x-3 mb-2">
                    <div className={`p-2 rounded-lg bg-${chart.color}-100`}>
                      <IconComponent className={`h-5 w-5 text-${chart.color}-600`} />
                    </div>
                    <h3 className="font-semibold text-secondary-900">{chart.name}</h3>
                  </div>
                  <p className="text-sm text-secondary-600">{chart.description}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Chart Display */}
      {selectedDataset && selectedChartType && chartData.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold text-secondary-900 mb-4">Visualization</h2>
          <DataVisualization
            chartType={selectedChartType}
            data={chartData}
            fields={getChartFields(selectedDataset, selectedChartType)}
            title={`${chartTypes.find(c => c.id === selectedChartType)?.name} of ${selectedDataset.filename}`}
            description={`Visualization of ${selectedDataset.filename} data`}
          />
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="card p-6 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-secondary-600">Generating chart...</p>
        </div>
      )}
    </div>
  )
}

export default Charts
