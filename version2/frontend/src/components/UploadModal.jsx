import React, { useState } from 'react'
import { Upload, X, FileText, FileSpreadsheet, Database, Cloud, Server, CheckCircle, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import axios from 'axios'

const UploadModal = ({ isOpen, onClose, onUploadSuccess }) => {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadType, setUploadType] = useState('file')
  const [datasetName, setDatasetName] = useState('')
  const [datasetDescription, setDatasetDescription] = useState('')

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  const handleFile = (file) => {
    const allowedTypes = [
      'text/csv', 
      'application/vnd.ms-excel', 
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/json'
    ]
    
    if (!allowedTypes.includes(file.type)) {
      toast.error('Please upload a CSV, Excel, or JSON file')
      return
    }

    if (file.size > 100 * 1024 * 1024) { // 100MB limit for large files
      toast.error('File size must be less than 100MB')
      return
    }

    setSelectedFile(file)
    // Auto-generate dataset name from filename
    if (!datasetName) {
      setDatasetName(file.name.split('.')[0])
    }
  }

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error('Please select a file')
      return
    }

    setUploading(true)
    setUploadProgress(0)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('name', datasetName.trim() || selectedFile.name.split('.')[0])
      formData.append('description', datasetDescription.trim())

      const response = await axios.post('/api/datasets/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress(percentCompleted)
        }
      })

      toast.success('Dataset uploaded successfully!')
      onUploadSuccess?.(response.data)
      onClose()
      
      // Reset form
      setSelectedFile(null)
      setDatasetName('')
      setDatasetDescription('')
      setUploadProgress(0)
      
    } catch (error) {
      console.error('Upload error:', error)
      toast.error(error.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

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
              <div className="p-2 rounded-lg bg-blue-100">
                <Upload className="h-6 w-6 text-blue-600" />
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
                    ? 'border-blue-500 bg-blue-50 shadow-md'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <div className="text-center">
                  <div className={`p-3 rounded-lg mx-auto mb-3 ${
                    uploadType === 'file' ? 'bg-blue-100' : 'bg-gray-100'
                  }`}>
                    <FileText className={`h-6 w-6 ${
                      uploadType === 'file' ? 'text-blue-600' : 'text-gray-600'
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
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
                  dragActive
                    ? 'border-blue-400 bg-blue-50 scale-105'
                    : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
                } ${uploading ? 'pointer-events-none' : 'cursor-pointer'}`}
              >
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileInput}
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                  <div className="space-y-4">
                    <div className="flex justify-center">
                      <div className={`p-4 rounded-full transition-all duration-200 ${
                        dragActive ? 'bg-blue-200 scale-110' : 'bg-blue-100'
                      }`}>
                        <Upload className={`h-8 w-8 transition-colors duration-200 ${
                          dragActive ? 'text-blue-700' : 'text-blue-600'
                        }`} />
                      </div>
                    </div>
                    
                    <div>
                      <h4 className="text-lg font-semibold text-gray-900 mb-2">
                        {dragActive ? 'Drop files here' : 'Upload your datasets'}
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
                          <span>Up to 10MB</span>
                        </div>
                      </div>
                    </div>
                    
                    {uploading && (
                      <div className="space-y-3">
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
                            style={{ width: `${uploadProgress}%` }}
                          />
                        </div>
                        <div className="flex items-center justify-center space-x-2 text-blue-600">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                          <span className="text-sm font-medium">Uploading... {uploadProgress}%</span>
                        </div>
                      </div>
                    )}
                  </div>
                </label>
              </div>
            )}

            {/* Selected File Display */}
            {selectedFile && !uploading && (
              <div className="mt-4 space-y-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <FileText className="w-5 h-5 text-gray-500" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">{selectedFile.name}</p>
                      <p className="text-xs text-gray-500">
                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                </div>
                
                {/* Dataset Name - Auto-generated, but editable */}
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Dataset Name
                    </label>
                    <input
                      type="text"
                      value={datasetName}
                      onChange={(e) => setDatasetName(e.target.value)}
                      placeholder="Enter dataset name"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Leave empty to use filename
                    </p>
                  </div>
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
            {selectedFile && !uploading && uploadProgress !== 100 && (
              <button
                onClick={handleUpload}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 transition-colors"
              >
                Upload
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default UploadModal
