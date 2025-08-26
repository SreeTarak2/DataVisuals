import React, { useState } from 'react'
import { Upload, FileText, Xlsx, Database, Trash2, Eye, BarChart3 } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { usePersona } from '../contexts/PersonaContext'

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

  const onDrop = async (acceptedFiles: File[]) => {
    setUploading(true)
    
    try {
      for (const file of acceptedFiles) {
        // Simulate upload - in real app, this would call the API
        const newDataset: Dataset = {
          id: Date.now().toString(),
          filename: file.name,
          size: file.size,
          row_count: Math.floor(Math.random() * 10000) + 100,
          column_count: Math.floor(Math.random() * 20) + 5,
          upload_date: new Date().toISOString()
        }
        
        setDatasets(prev => [newDataset, ...prev])
        toast.success(`${file.name} uploaded successfully!`)
      }
    } catch (error) {
      toast.error('Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    },
    multiple: true
  })

  const deleteDataset = (id: string) => {
    setDatasets(prev => prev.filter(dataset => dataset.id !== id))
    toast.success('Dataset deleted successfully!')
  }

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

      {/* Upload Area */}
      <div className="card p-8">
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            isDragActive
              ? 'border-primary-400 bg-primary-50'
              : 'border-secondary-300 hover:border-primary-400 hover:bg-primary-50'
          }`}
        >
          <input {...getInputProps()} />
          
          <div className="space-y-4">
            <div className="flex justify-center">
              <div className="p-4 rounded-full bg-primary-100">
                <Upload className="h-8 w-8 text-primary-600" />
              </div>
            </div>
            
            <div>
              <h3 className="text-lg font-semibold text-secondary-900 mb-2">
                {isDragActive ? 'Drop files here' : 'Upload your datasets'}
              </h3>
              <p className="text-secondary-600 mb-4">
                Drag and drop CSV or Excel files, or click to browse
              </p>
              
              <div className="flex items-center justify-center space-x-6 text-sm text-secondary-500">
                <div className="flex items-center space-x-2">
                  <FileText className="h-4 w-4" />
                  <span>CSV</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Xlsx className="h-4 w-4" />
                  <span>Excel</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Database className="h-4 w-4" />
                  <span>Up to 100MB</span>
                </div>
              </div>
            </div>
            
            {uploading && (
              <div className="text-primary-600">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600 mx-auto"></div>
                <p className="mt-2">Processing...</p>
              </div>
            )}
          </div>
        </div>
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
                  <button className="btn-primary flex-1 text-sm">
                    <BarChart3 className="h-4 w-4 mr-2" />
                    Analyze
                  </button>
                </div>
              </div>
            ))}
          </div>
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
            onClick={() => document.querySelector('[data-dropzone]')?.click()}
            className="btn-primary"
          >
            <Upload className="h-5 w-5 mr-2" />
            Upload Dataset
          </button>
        </div>
      )}
    </div>
  )
}

export default Datasets
