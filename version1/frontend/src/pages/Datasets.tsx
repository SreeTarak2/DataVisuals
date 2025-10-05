import React, { useState } from 'react'
import { Upload, FileText, FileSpreadsheet, Database, Trash2, Eye, BarChart3, Plus } from 'lucide-react'
import toast from 'react-hot-toast'
import { usePersona } from '../contexts/PersonaContext'
import axios from 'axios'
import DataVisualization from '../components/DataVisualization'
import UploadModal from '../components/UploadModal'

interface Dataset {
  id: string
  filename: string
  size: number
  row_count: number
  column_count: number
  upload_date: string
}

const Datasets: React.FC = () => {
  const { persona, isNormal } = usePersona()
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState<string | null>(null)
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const [visualizationRecommendations, setVisualizationRecommendations] = useState<any[]>([])
  const [datasetData, setDatasetData] = useState<any[]>([])
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)

  const handleUploadSuccess = (newDataset: Dataset) => {
    setDatasets(prev => [newDataset, ...prev])
  }

  const deleteDataset = async (id: string) => {
    const dataset = datasets.find(d => d.id === id)
    if (!dataset) return
    
    if (window.confirm(`Are you sure you want to delete "${dataset.filename}"? This action cannot be undone.`)) {
      try {
        await axios.delete(`http://localhost:8000/datasets/${id}`)
        setDatasets(prev => prev.filter(dataset => dataset.id !== id))
        toast.success('Dataset deleted successfully!')
      } catch (error) {
        console.error('Error deleting dataset:', error)
        toast.error('Failed to delete dataset')
      }
    }
  }

  const analyzeDataset = async (dataset: Dataset) => {
    setAnalyzing(dataset.id)
    setAnalysisResult(null)
    setVisualizationRecommendations([])
    setDatasetData([])
    
    try {
      // Get analysis
      const analysisResponse = await axios.post(`http://localhost:8000/datasets/${dataset.id}/analyze?persona=${persona}`)
      
      // Get visualization recommendations
      const vizResponse = await axios.get(`http://localhost:8000/visualization/chart-types?dataset_id=${dataset.id}&persona=${persona}`)
      
      // Get dataset details for chart data generation
      const datasetResponse = await axios.get(`http://localhost:8000/datasets/${dataset.id}`)
      
      setAnalysisResult({
        dataset: dataset,
        analysis: analysisResponse.data
      })
      
      setVisualizationRecommendations(vizResponse.data)
      
      // Generate sample chart data based on dataset columns
      const sampleData = generateSampleChartData(datasetResponse.data)
      setDatasetData(sampleData)
      
      toast.success('Analysis completed successfully!')
    } catch (error) {
      console.error('Analysis error:', error)
      toast.error('Failed to analyze dataset. Please try again.')
    } finally {
      setAnalyzing(null)
    }
  }

  const loadDatasets = async () => {
    try {
      const response = await axios.get('http://localhost:8000/datasets')
      setDatasets(response.data)
    } catch (error) {
      console.error('Failed to load datasets:', error)
      toast.error('Failed to load datasets')
    }
  }

  const generateSampleChartData = (datasetInfo: any) => {
    const columns = datasetInfo.columns || []
    const sampleData: any[] = []
    
    // Generate sample data for each row
    for (let i = 0; i < Math.min(10, datasetInfo.row_count); i++) {
      const row: any = {}
      columns.forEach((col: any) => {
        if (col.is_numeric) {
          // Generate numeric data based on min/max
          const min = col.min || 0
          const max = col.max || 100
          row[col.name] = Math.floor(Math.random() * (max - min + 1)) + min
        } else if (col.is_categorical) {
          // Use sample values for categorical data
          const values = col.sample_values || ['A', 'B', 'C']
          row[col.name] = values[Math.floor(Math.random() * values.length)]
        } else {
          // Use sample values for text data
          const values = col.sample_values || ['Sample']
          row[col.name] = values[Math.floor(Math.random() * values.length)]
        }
      })
      sampleData.push(row)
    }
    
    return sampleData
  }

  // Load datasets on component mount
  React.useEffect(() => {
    loadDatasets()
  }, [])

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-secondary-900 mb-2">Datasets</h1>
        <p className="text-secondary-600">
          {isNormal 
            ? 'Upload and manage your data files for AI-powered analysis and insights.'
            : 'Upload datasets for comprehensive profiling, statistical analysis, and advanced visualization.'
          }
        </p>
      </div>

      {/* Upload Button */}
      <div className="flex justify-end">
        <button
          onClick={() => setIsUploadModalOpen(true)}
          className="btn-primary flex items-center space-x-2 px-6 py-3 text-lg font-medium transition-all duration-200 hover:scale-105 hover:shadow-lg"
        >
          <Plus className="h-5 w-5" />
          <span>Upload Data</span>
        </button>
      </div>

      {/* Datasets List */}
      {datasets.length > 0 && (
        <div>
          <h2 className="text-2xl font-semibold text-secondary-900 mb-6">Your Datasets</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {datasets.map((dataset) => (
              <div key={dataset.id} className="card p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-primary-100">
                      <Database className="h-5 w-5 text-primary-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-secondary-900 truncate max-w-32">
                        {dataset.filename}
                      </h3>
                      <p className="text-sm text-secondary-500">
                        {formatFileSize(dataset.size)}
                      </p>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => deleteDataset(dataset.id)}
                    className="p-2 text-secondary-400 hover:text-error-600 hover:bg-error-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                
                <div className="space-y-3 mb-4">
                  <div className="flex justify-between text-sm">
                    <span className="text-secondary-600">Rows:</span>
                    <span className="font-medium text-secondary-900">{dataset.row_count.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-secondary-600">Columns:</span>
                    <span className="font-medium text-secondary-900">{dataset.column_count}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-secondary-600">Uploaded:</span>
                    <span className="font-medium text-secondary-900">{formatDate(dataset.upload_date)}</span>
                  </div>
                </div>
                
                <div className="flex space-x-2">
                  <button className="btn-outline flex-1 text-sm">
                    <Eye className="h-4 w-4 mr-2" />
                    View
                  </button>
                  <button 
                    className="btn-primary flex-1 text-sm disabled:opacity-50"
                    onClick={() => analyzeDataset(dataset)}
                    disabled={analyzing === dataset.id}
                  >
                    <BarChart3 className="h-4 w-4 mr-2" />
                    {analyzing === dataset.id ? 'Analyzing...' : 'Analyze'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysisResult && (
        <div className="space-y-6">
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-secondary-900">
                Analysis Results for {analysisResult.dataset.filename}
              </h3>
              <button 
                onClick={() => {
                  setAnalysisResult(null)
                  setVisualizationRecommendations([])
                  setDatasetData([])
                }}
                className="text-secondary-400 hover:text-secondary-600"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            
            <div className="space-y-4">
              <div className="p-4 bg-primary-50 rounded-lg">
                <h4 className="font-medium text-primary-900 mb-2">AI Analysis</h4>
                <p className="text-primary-800">{analysisResult.analysis.response}</p>
              </div>
              
              {analysisResult.analysis.suggested_actions && analysisResult.analysis.suggested_actions.length > 0 && (
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <h4 className="font-medium text-secondary-900 mb-2">Suggested Actions</h4>
                  <ul className="list-disc list-inside space-y-1 text-secondary-700">
                    {analysisResult.analysis.suggested_actions.map((action: string, index: number) => (
                      <li key={index}>{action}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              <div className="flex items-center justify-between text-sm text-secondary-600">
                <span>Confidence: {Math.round(analysisResult.analysis.confidence * 100)}%</span>
                <span>Reasoning: {analysisResult.analysis.reasoning}</span>
              </div>
            </div>
          </div>

          {/* Visualizations */}
          {visualizationRecommendations.length > 0 && (
            <div>
              <h3 className="text-xl font-semibold text-secondary-900 mb-4">Recommended Visualizations</h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {visualizationRecommendations.slice(0, 4).map((rec, index) => (
                  <DataVisualization
                    key={index}
                    chartType={rec.chart_type}
                    data={datasetData}
                    fields={rec.fields}
                    title={rec.title}
                    description={rec.description}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Fallback: Generate basic charts if no recommendations */}
          {visualizationRecommendations.length === 0 && datasetData.length > 0 && (
            <div>
              <h3 className="text-xl font-semibold text-secondary-900 mb-4">Data Visualizations</h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {analysisResult.dataset.columns && analysisResult.dataset.columns.length > 0 && (
                  <>
                    {/* Bar Chart for categorical data */}
                    {analysisResult.dataset.columns.some((col: any) => col.is_categorical) && (
                      <DataVisualization
                        chartType="bar_chart"
                        data={datasetData}
                        fields={[
                          analysisResult.dataset.columns.find((col: any) => col.is_categorical)?.name || 'category',
                          analysisResult.dataset.columns.find((col: any) => col.is_numeric)?.name || 'value'
                        ]}
                        title="Category Distribution"
                        description="Distribution of data across different categories"
                      />
                    )}
                    
                    {/* Line Chart for numeric data */}
                    {analysisResult.dataset.columns.some((col: any) => col.is_numeric) && (
                      <DataVisualization
                        chartType="line_chart"
                        data={datasetData}
                        fields={[
                          'index',
                          analysisResult.dataset.columns.find((col: any) => col.is_numeric)?.name || 'value'
                        ]}
                        title="Value Trends"
                        description="Trend analysis of numeric values"
                      />
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {datasets.length === 0 && (
        <div className="card p-12 text-center">
          <div className="p-4 rounded-full bg-secondary-100 mx-auto mb-4 w-20 h-20 flex items-center justify-center">
            <Database className="h-10 w-10 text-secondary-400" />
          </div>
          <h3 className="text-lg font-semibold text-secondary-900 mb-2">No datasets yet</h3>
          <p className="text-secondary-600 mb-6 max-w-md mx-auto">
            Upload your first dataset to start getting AI-powered insights and visualization recommendations.
          </p>
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="btn-primary"
          >
            <Plus className="h-5 w-5 mr-2" />
            Upload Dataset
          </button>
        </div>
      )}

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />
    </div>
  )
}

export default Datasets
