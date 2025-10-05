import React, { useState } from 'react'
import { 
  Upload, 
  FileText, 
  FileSpreadsheet, 
  Database, 
  X, 
  Cloud, 
  Server,
  CheckCircle,
  AlertCircle
} from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import axios from 'axios'

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onUploadSuccess: (dataset: any) => void
}

const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose, onUploadSuccess }) => {
  const [uploading, setUploading] = useState(false)
  const [uploadType, setUploadType] = useState<'file' | 'google-sheets' | 'sql-db'>('file')
  const [uploadProgress, setUploadProgress] = useState(0)

  const onDrop = async (acceptedFiles: File[]) => {
    setUploading(true)
    setUploadProgress(0)
    
    try {
      for (const file of acceptedFiles) {
        const formData = new FormData()
        formData.append('file', file)
        
        // Simulate progress
        const progressInterval = setInterval(() => {
          setUploadProgress(prev => Math.min(prev + 10, 90))
        }, 200)
        
        const response = await axios.post('http://localhost:8000/datasets/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        })
        
        clearInterval(progressInterval)
        setUploadProgress(100)
        
        const newDataset = {
          id: response.data.id,
          filename: response.data.filename,
          size: response.data.size,
          row_count: response.data.row_count,
          column_count: response.data.column_count,
          upload_date: response.data.upload_date
        }
        
        onUploadSuccess(newDataset)
        toast.success(`${file.name} uploaded successfully!`)
        
        // Reset progress after a short delay
        setTimeout(() => {
          setUploadProgress(0)
          setUploading(false)
          onClose()
        }, 1000)
      }
    } catch (error) {
      console.error('Upload error:', error)
      toast.error('Upload failed. Please try again.')
      setUploading(false)
      setUploadProgress(0)
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    },
    multiple: true,
    disabled: uploading || uploadType !== 'file'
  })

  const handleGoogleSheets = () => {
    toast.error('Google Sheets integration coming soon!')
  }

  const handleSQLDatabase = () => {
    toast.error('SQL Database integration coming soon!')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity duration-300"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative transform overflow-hidden rounded-2xl bg-white shadow-2xl transition-all duration-300 scale-100 opacity-100 w-full max-w-2xl">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 rounded-lg bg-primary-100">
                <Upload className="h-6 w-6 text-primary-600" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-gray-900">Upload Data</h3>
                <p className="text-sm text-gray-500">Choose how you'd like to add your data</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            {/* Upload Type Selector */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              {/* File Upload */}
              <button
                onClick={() => setUploadType('file')}
                className={`p-4 rounded-xl border-2 transition-all duration-200 ${
                  uploadType === 'file'
                    ? 'border-primary-500 bg-primary-50 shadow-md'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <div className="text-center">
                  <div className={`p-3 rounded-lg mx-auto mb-3 ${
                    uploadType === 'file' ? 'bg-primary-100' : 'bg-gray-100'
                  }`}>
                    <FileText className={`h-6 w-6 ${
                      uploadType === 'file' ? 'text-primary-600' : 'text-gray-600'
                    }`} />
                  </div>
                  <h4 className="font-medium text-gray-900 mb-1">File Upload</h4>
                  <p className="text-sm text-gray-500">CSV, Excel files</p>
                </div>
              </button>

              {/* Google Sheets */}
              <button
                onClick={handleGoogleSheets}
                disabled
                className="p-4 rounded-xl border-2 border-gray-200 bg-gray-50 cursor-not-allowed opacity-60"
              >
                <div className="text-center">
                  <div className="p-3 rounded-lg bg-gray-100 mx-auto mb-3">
                    <Cloud className="h-6 w-6 text-gray-400" />
                  </div>
                  <h4 className="font-medium text-gray-500 mb-1">Google Sheets</h4>
                  <p className="text-sm text-gray-400">Coming Soon</p>
                  <div className="mt-2 flex items-center justify-center space-x-1">
                    <AlertCircle className="h-3 w-3 text-gray-400" />
                    <span className="text-xs text-gray-400">Disabled</span>
                  </div>
                </div>
              </button>

              {/* SQL Database */}
              <button
                onClick={handleSQLDatabase}
                disabled
                className="p-4 rounded-xl border-2 border-gray-200 bg-gray-50 cursor-not-allowed opacity-60"
              >
                <div className="text-center">
                  <div className="p-3 rounded-lg bg-gray-100 mx-auto mb-3">
                    <Server className="h-6 w-6 text-gray-400" />
                  </div>
                  <h4 className="font-medium text-gray-500 mb-1">SQL Database</h4>
                  <p className="text-sm text-gray-400">Coming Soon</p>
                  <div className="mt-2 flex items-center justify-center space-x-1">
                    <AlertCircle className="h-3 w-3 text-gray-400" />
                    <span className="text-xs text-gray-400">Disabled</span>
                  </div>
                </div>
              </button>
            </div>

            {/* File Upload Area */}
            {uploadType === 'file' && (
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
                  isDragActive
                    ? 'border-primary-400 bg-primary-50 scale-105'
                    : 'border-gray-300 hover:border-primary-400 hover:bg-primary-50'
                } ${uploading ? 'pointer-events-none' : 'cursor-pointer'}`}
              >
                <input {...getInputProps()} />
                
                <div className="space-y-4">
                  <div className="flex justify-center">
                    <div className={`p-4 rounded-full transition-all duration-200 ${
                      isDragActive ? 'bg-primary-200 scale-110' : 'bg-primary-100'
                    }`}>
                      <Upload className={`h-8 w-8 transition-colors duration-200 ${
                        isDragActive ? 'text-primary-700' : 'text-primary-600'
                      }`} />
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-lg font-semibold text-gray-900 mb-2">
                      {isDragActive ? 'Drop files here' : 'Upload your datasets'}
                    </h4>
                    <p className="text-gray-600 mb-4">
                      Drag and drop CSV or Excel files, or click to browse
                    </p>
                    
                    <div className="flex items-center justify-center space-x-6 text-sm text-gray-500">
                      <div className="flex items-center space-x-2">
                        <FileText className="h-4 w-4" />
                        <span>CSV</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <FileSpreadsheet className="h-4 w-4" />
                        <span>Excel</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Database className="h-4 w-4" />
                        <span>Up to 100MB</span>
                      </div>
                    </div>
                  </div>
                  
                  {uploading && (
                    <div className="space-y-3">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-primary-600 h-2 rounded-full transition-all duration-300 ease-out"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-center space-x-2 text-primary-600">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600"></div>
                        <span className="text-sm font-medium">Uploading... {uploadProgress}%</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Upload Success */}
            {uploadProgress === 100 && (
              <div className="text-center py-4">
                <div className="flex items-center justify-center space-x-2 text-green-600 mb-2">
                  <CheckCircle className="h-5 w-5" />
                  <span className="font-medium">Upload Complete!</span>
                </div>
                <p className="text-sm text-gray-500">Your data is being processed...</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200 bg-gray-50">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default UploadModal

