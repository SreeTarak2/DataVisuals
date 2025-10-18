import React, { useState, useRef } from 'react';
import { 
  Plus, 
  Upload, 
  Search, 
  Filter, 
  MoreVertical, 
  Eye, 
  Trash2, 
  Download,
  Calendar,
  FileText,
  BarChart3,
  Sparkles
} from 'lucide-react';
import { useDataset } from '../contexts/DatasetContext';
import toast from 'react-hot-toast';
import UploadModal from '../components/UploadModal';
import DeleteConfirmModal from '../components/DeleteConfirmModal';

const Datasets = () => {
  const { 
    datasets, 
    loading, 
    uploadDataset, 
    deleteDataset, 
    getDataset 
  } = useDataset();
  
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('recent');
  const fileInputRef = useRef(null);

  const handleUpload = async (file) => {
    const result = await uploadDataset(file);
    if (result.success) {
      toast.success('Dataset uploaded successfully!');
      setShowUploadModal(false);
    } else {
      toast.error(result.error);
    }
  };

  const handleDelete = async (datasetId) => {
    const result = await deleteDataset(datasetId);
    if (result.success) {
      toast.success('Dataset deleted successfully!');
      setShowDeleteModal(false);
      setSelectedDataset(null);
    } else {
      toast.error(result.error);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const filteredDatasets = datasets.filter(dataset =>
    dataset.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    dataset.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sortedDatasets = [...filteredDatasets].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return (a.name || '').localeCompare(b.name || '');
      case 'size':
        return (b.file_size || 0) - (a.file_size || 0);
      case 'recent':
      default:
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    }
  });

  const DatasetCard = ({ dataset }) => (
    <div className="pinterest-card bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Dataset preview/icon */}
      <div className="relative h-48 bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 bg-blue-500 rounded-xl flex items-center justify-center mx-auto mb-3">
            <BarChart3 className="w-8 h-8 text-white" />
          </div>
          <p className="text-sm text-gray-600 font-medium">
            {dataset.rows || 0} rows × {dataset.columns || 0} columns
          </p>
        </div>
        
        {/* Quick actions overlay */}
        <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="flex space-x-2">
            <button className="w-8 h-8 bg-white rounded-full shadow-md flex items-center justify-center hover:bg-gray-50">
              <Eye className="w-4 h-4 text-gray-600" />
            </button>
            <button 
              onClick={() => {
                setSelectedDataset(dataset);
                setShowDeleteModal(true);
              }}
              className="w-8 h-8 bg-white rounded-full shadow-md flex items-center justify-center hover:bg-red-50"
            >
              <Trash2 className="w-4 h-4 text-red-600" />
            </button>
          </div>
        </div>
      </div>

      {/* Dataset info */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <h3 className="font-semibold text-gray-900 text-lg leading-tight">
            {dataset.name || 'Untitled Dataset'}
          </h3>
          <button className="text-gray-400 hover:text-gray-600">
            <MoreVertical className="w-4 h-4" />
          </button>
        </div>
        
        {dataset.description && (
          <p className="text-gray-600 text-sm mb-3 line-clamp-2">
            {dataset.description}
          </p>
        )}

        <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
          <div className="flex items-center">
            <Calendar className="w-3 h-3 mr-1" />
            {formatDate(dataset.created_at)}
          </div>
          <div className="flex items-center">
            <FileText className="w-3 h-3 mr-1" />
            {formatFileSize(dataset.file_size || 0)}
          </div>
        </div>

        {/* Dataset stats */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-gray-50 rounded-lg p-2 text-center">
            <p className="text-lg font-semibold text-gray-900">{dataset.rows || 0}</p>
            <p className="text-xs text-gray-600">Rows</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2 text-center">
            <p className="text-lg font-semibold text-gray-900">{dataset.columns || 0}</p>
            <p className="text-xs text-gray-600">Columns</p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex space-x-2">
          <button className="flex-1 bg-red-600 text-white py-2 px-3 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors duration-200">
            <Sparkles className="w-4 h-4 inline mr-1" />
            Analyze
          </button>
          <button className="px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors duration-200">
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Your Datasets</h1>
          <p className="text-gray-600 mt-1">
            Upload and manage your data files
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="mt-4 sm:mt-0 inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors duration-200"
        >
          <Plus className="w-4 h-4 mr-2" />
          Upload Dataset
        </button>
      </div>

      {/* Search and filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search datasets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-red-500 focus:border-transparent"
          >
            <option value="recent">Recent</option>
            <option value="name">Name</option>
            <option value="size">Size</option>
          </select>
        </div>
      </div>

      {/* Datasets grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="h-48 shimmer"></div>
              <div className="p-4 space-y-3">
                <div className="h-4 bg-gray-200 rounded shimmer"></div>
                <div className="h-3 bg-gray-200 rounded shimmer"></div>
                <div className="h-3 bg-gray-200 rounded shimmer"></div>
              </div>
            </div>
          ))}
        </div>
      ) : sortedDatasets.length === 0 ? (
        <div className="text-center py-12">
          <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <BarChart3 className="w-12 h-12 text-gray-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {searchQuery ? 'No datasets found' : 'No datasets yet'}
          </h3>
          <p className="text-gray-600 mb-6">
            {searchQuery 
              ? 'Try adjusting your search terms' 
              : 'Upload your first dataset to get started with data analysis'
            }
          </p>
          {!searchQuery && (
            <button
              onClick={() => setShowUploadModal(true)}
              className="inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors duration-200"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload Dataset
            </button>
          )}
        </div>
      ) : (
        <div className="masonry-grid">
          {sortedDatasets.map((dataset) => (
            <div key={dataset.id} className="masonry-item group">
              <DatasetCard dataset={dataset} />
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onUpload={handleUpload}
        loading={loading}
      />

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={() => handleDelete(selectedDataset?.id)}
        title="Delete Dataset"
        message={`Are you sure you want to delete "${selectedDataset?.name}"? This action cannot be undone.`}
      />
    </div>
  );
};

export default Datasets;

