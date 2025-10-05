import React, { useState, useEffect } from 'react'
import { Database, Upload, MoreVertical, Eye, Trash2, BarChart3, Download, Filter, Loader2 } from 'lucide-react'
import UploadModal from '../components/UploadModal'
import ConfirmationModal from '../components/ConfirmationModal'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import toast from 'react-hot-toast'

const Datasets = () => {
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [selectedDataset, setSelectedDataset] = useState(null)
  const [datasets, setDatasets] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [datasetToDelete, setDatasetToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const { user } = useAuth()
  
  // Load datasets on component mount
  useEffect(() => {
    loadDatasets()
  }, [])
  
  const loadDatasets = async () => {
    try {
      setLoading(true)
      const response = await axios.get('/api/datasets')
      console.log('Datasets response:', response.data)
      const datasets = response.data.datasets || []
      console.log('Datasets array:', datasets)
      setDatasets(datasets)
    } catch (error) {
      console.error('Error loading datasets:', error)
      toast.error('Failed to load datasets')
    } finally {
      setLoading(false)
    }
  }
  
  const handleUploadSuccess = (uploadResponse) => {
    // The upload response contains the dataset metadata
    // We need to create a dataset object that matches our expected structure
    const newDataset = {
      id: uploadResponse.dataset_id,
      name: uploadResponse.metadata?.name || 'Unnamed Dataset',
      file_size: uploadResponse.metadata?.file_size || 0,
      row_count: uploadResponse.metadata?.dataset_overview?.total_rows || 0,
      column_count: uploadResponse.metadata?.dataset_overview?.total_columns || 0,
      uploaded_at: new Date().toISOString(),
      is_processed: true,
      metadata: uploadResponse.metadata
    }
    
    setDatasets(prev => [newDataset, ...prev])
    setShowUploadModal(false)
    toast.success('Dataset uploaded successfully!')
  }
  
  const handleDeleteClick = (dataset) => {
    setDatasetToDelete(dataset)
    setShowDeleteModal(true)
  }

  const handleDeleteConfirm = async () => {
    if (!datasetToDelete) return

    setDeleting(true)
    try {
      await axios.delete(`/api/datasets/${datasetToDelete.id}`)
      setDatasets(prev => prev.filter(d => d.id !== datasetToDelete.id))
      toast.success('Dataset deleted successfully')
      setShowDeleteModal(false)
      setDatasetToDelete(null)
    } catch (error) {
      console.error('Error deleting dataset:', error)
      toast.error('Failed to delete dataset')
    } finally {
      setDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setShowDeleteModal(false)
    setDatasetToDelete(null)
  }
  
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }
  
  const formatDate = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInHours = Math.floor((now - date) / (1000 * 60 * 60))
    
    if (diffInHours < 1) return 'Just now'
    if (diffInHours < 24) return `${diffInHours} hours ago`
    if (diffInHours < 48) return '1 day ago'
    return `${Math.floor(diffInHours / 24)} days ago`
  }

  const filteredDatasets = datasets
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-gray-900 to-slate-800 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400 mx-auto mb-4" />
          <p className="text-slate-300">Loading datasets...</p>
        </div>
      </div>
    )
  }

  const handleDelete = (datasetId) => {
    if (window.confirm('Are you sure you want to delete this dataset?')) {
      setDatasets(datasets.filter(d => d.id !== datasetId))
    }
  }

  const handleView = (dataset) => {
    setSelectedDataset(dataset)
    // Open dataset preview modal or navigate to analysis
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-gray-900 to-slate-800 p-6">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Datasets</h1>
            <p className="text-slate-300 mt-1">
              Manage and explore your data collections
            </p>
          </div>
          <button
            onClick={() => setShowUploadModal(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Dataset</span>
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center space-x-4">
          <button className="flex items-center space-x-2 px-4 py-2 border border-slate-600 rounded-lg hover:bg-slate-800 transition-colors text-slate-300">
            <Filter className="w-4 h-4" />
            <span>Filter</span>
          </button>
        </div>

        {/* Datasets Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDatasets.map((dataset) => (
            <div key={dataset.id} className="relative bg-gradient-to-br from-slate-800/20 to-gray-800/20 backdrop-blur-sm rounded-xl border border-slate-600/20 p-6 shadow-2xl shadow-slate-500/10 hover:shadow-slate-500/20 transition-all duration-300">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-600/5 to-gray-600/5 rounded-xl"></div>
              <div className="relative">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center">
                      <Database className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white">{dataset.name}</h3>
                      <p className="text-sm text-slate-400">
                        {dataset.row_count ? dataset.row_count.toLocaleString() : 'Unknown'} records
                      </p>
                    </div>
                  </div>
                  <div className="relative">
                    <button className="p-1 text-slate-400 hover:text-slate-200 transition-colors">
                      <MoreVertical className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="space-y-2 mb-4">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Size:</span>
                    <span className="text-slate-200">{formatFileSize(dataset.file_size)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Columns:</span>
                    <span className="text-slate-200">{dataset.column_count || 'Unknown'}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Updated:</span>
                    <span className="text-slate-200">{formatDate(dataset.upload_date)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Status:</span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      dataset.is_processed 
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30' 
                        : 'bg-amber-500/20 text-amber-300 border border-amber-400/30'
                    }`}>
                      {dataset.is_processed ? 'Processed' : 'Processing'}
                    </span>
                  </div>
                </div>

                <div className="flex space-x-2">
                  <button
                    onClick={() => handleView(dataset)}
                    className="flex-1 flex items-center justify-center space-x-2 px-3 py-2 text-sm font-medium text-emerald-300 bg-emerald-500/20 rounded-lg hover:bg-emerald-500/30 transition-colors border border-emerald-400/30"
                  >
                    <Eye className="w-4 h-4" />
                    <span>View</span>
                  </button>
                  <button className="flex items-center justify-center px-3 py-2 text-sm font-medium text-slate-300 bg-slate-700/50 rounded-lg hover:bg-slate-700/70 transition-colors border border-slate-600/30">
                    <BarChart3 className="w-4 h-4" />
                  </button>
                  <button className="flex items-center justify-center px-3 py-2 text-sm font-medium text-slate-300 bg-slate-700/50 rounded-lg hover:bg-slate-700/70 transition-colors border border-slate-600/30">
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteClick(dataset)}
                    className="flex items-center justify-center px-3 py-2 text-sm font-medium text-red-400 bg-red-500/20 rounded-lg hover:bg-red-500/30 transition-colors border border-red-400/30"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Empty State */}
        {filteredDatasets.length === 0 && (
          <div className="text-center py-12">
            <div className="p-4 bg-slate-700/50 rounded-full w-20 h-20 mx-auto mb-4 flex items-center justify-center">
              <Database className="w-12 h-12 text-slate-400" />
            </div>
            <h3 className="text-lg font-medium text-white mb-2">No datasets found</h3>
            <p className="text-slate-400 mb-6">
              Upload your first dataset to get started
            </p>
            <button
              onClick={() => setShowUploadModal(true)}
              className="inline-flex items-center space-x-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
            >
              <Upload className="w-4 h-4" />
              <span>Upload Dataset</span>
            </button>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <UploadModal
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          onUploadSuccess={handleUploadSuccess}
        />
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmationModal
        isOpen={showDeleteModal}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        title="Delete Dataset"
        message={`Are you sure you want to permanently delete "${datasetToDelete?.name}"? This action cannot be undone and will remove all associated data and files.`}
        confirmText={deleting ? "Deleting..." : "Delete"}
        cancelText="Cancel"
        type="danger"
      />
    </div>
  )
}

export default Datasets



