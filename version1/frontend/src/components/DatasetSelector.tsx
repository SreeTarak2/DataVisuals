import React from 'react'
import { Database, ChevronDown, Check, Eye } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'

interface Dataset {
  id: string
  filename: string
  size: number
  row_count: number
  column_count: number
  upload_date: string
}

interface DatasetSelectorProps {
  datasets: Dataset[]
  selectedDataset: Dataset | null
  onDatasetSelect: (dataset: Dataset) => void
  onPreviewDataset?: (dataset: Dataset) => void
}

const DatasetSelector: React.FC<DatasetSelectorProps> = ({
  datasets,
  selectedDataset,
  onDatasetSelect,
  onPreviewDataset
}) => {
  const [isOpen, setIsOpen] = React.useState(false)
  const { isDarkTheme } = useTheme()

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

  if (datasets.length === 0) {
    return (
      <div className={`flex items-center space-x-2 ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
        <Database className="h-5 w-5" />
        <span className="text-sm">No datasets available</span>
      </div>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-4 py-2 text-left bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors duration-200 min-w-[280px]"
      >
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          <Database className="h-5 w-5 text-gray-400 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {selectedDataset ? selectedDataset.filename : 'Select Dataset'}
            </p>
            {selectedDataset && (
              <p className="text-xs text-gray-500 truncate">
                {selectedDataset.row_count.toLocaleString()} rows • {formatFileSize(selectedDataset.size)}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-2 flex-shrink-0">
          {selectedDataset && onPreviewDataset && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onPreviewDataset(selectedDataset)
              }}
              className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors duration-200"
              title="Preview data"
            >
              <Eye className="h-4 w-4" />
            </button>
          )}
          <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-md shadow-lg z-50 max-h-64 overflow-y-auto">
          <div className="py-1">
            {datasets.map((dataset) => (
              <button
                key={dataset.id}
                onClick={() => {
                  onDatasetSelect(dataset)
                  setIsOpen(false)
                }}
                className="w-full flex items-center space-x-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors duration-200"
              >
                <div className="flex-shrink-0">
                  <Database className="h-4 w-4 text-gray-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {dataset.filename}
                  </p>
                  <p className="text-xs text-gray-500 truncate">
                    {dataset.row_count.toLocaleString()} rows • {dataset.column_count} columns • {formatDate(dataset.upload_date)}
                  </p>
                </div>
                <div className="flex items-center space-x-2 flex-shrink-0">
                  {onPreviewDataset && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onPreviewDataset(dataset)
                      }}
                      className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors duration-200"
                      title="Preview data"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                  )}
                  {selectedDataset?.id === dataset.id && (
                    <Check className="h-4 w-4 text-blue-600" />
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default DatasetSelector
