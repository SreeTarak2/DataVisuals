import React, { useState } from 'react'
import { X, Eye, EyeOff, Download, Table } from 'lucide-react'

interface DataPreviewProps {
  data: any[]
  datasetName: string
  isOpen: boolean
  onClose: () => void
  isDarkTheme: boolean
}

const DataPreview: React.FC<DataPreviewProps> = ({
  data,
  datasetName,
  isOpen,
  onClose,
  isDarkTheme
}) => {
  const [showAllColumns, setShowAllColumns] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  if (!isOpen || !data || data.length === 0) {
    return null
  }

  // Get column names from the first row
  const columns = Object.keys(data[0] || {})
  const visibleColumns = showAllColumns ? columns : columns.slice(0, 5)
  const hiddenColumnsCount = columns.length - visibleColumns.length

  // Filter data based on search term
  const filteredData = data.filter(row =>
    Object.values(row).some(value =>
      String(value).toLowerCase().includes(searchTerm.toLowerCase())
    )
  )

  // Limit rows for performance
  const displayData = filteredData.slice(0, 100)
  const totalRows = data.length
  const showingRows = displayData.length

  const exportToCSV = () => {
    const csvContent = [
      columns.join(','),
      ...data.map(row => 
        columns.map(col => `"${row[col] || ''}"`).join(',')
      )
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${datasetName}_preview.csv`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className={`${isDarkTheme ? 'bg-slate-800' : 'bg-white'} rounded-2xl shadow-2xl max-w-7xl w-full mx-4 max-h-[90vh] flex flex-col`}>
        {/* Header */}
        <div className={`${isDarkTheme ? 'bg-slate-700' : 'bg-gray-50'} px-6 py-4 rounded-t-2xl border-b ${isDarkTheme ? 'border-slate-600' : 'border-gray-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Table className={`h-6 w-6 ${isDarkTheme ? 'text-indigo-400' : 'text-indigo-600'}`} />
              <div>
                <h3 className={`text-lg font-semibold ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
                  Data Preview: {datasetName}
                </h3>
                <p className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
                  {totalRows.toLocaleString()} rows • {columns.length} columns
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={exportToCSV}
                className={`flex items-center space-x-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  isDarkTheme 
                    ? 'bg-slate-600 hover:bg-slate-500 text-white' 
                    : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
                }`}
              >
                <Download className="h-4 w-4" />
                <span>Export CSV</span>
              </button>
              <button
                onClick={onClose}
                className={`p-2 rounded-lg transition-colors ${
                  isDarkTheme 
                    ? 'hover:bg-slate-600 text-gray-400 hover:text-white' 
                    : 'hover:bg-gray-200 text-gray-500 hover:text-gray-700'
                }`}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Search and Controls */}
        <div className={`px-6 py-4 border-b ${isDarkTheme ? 'border-slate-600' : 'border-gray-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search data..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className={`w-64 px-4 py-2 pl-10 rounded-lg border transition-colors ${
                    isDarkTheme 
                      ? 'bg-slate-700 border-slate-600 text-white placeholder-gray-400 focus:border-indigo-500' 
                      : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500 focus:border-indigo-500'
                  } focus:outline-none focus:ring-2 focus:ring-indigo-500/20`}
                />
                <div className="absolute left-3 top-1/2 transform -translate-y-1/2">
                  <svg className={`h-4 w-4 ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
              </div>
              
              {hiddenColumnsCount > 0 && (
                <button
                  onClick={() => setShowAllColumns(!showAllColumns)}
                  className={`flex items-center space-x-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                    isDarkTheme 
                      ? 'bg-indigo-600 hover:bg-indigo-700 text-white' 
                      : 'bg-indigo-100 hover:bg-indigo-200 text-indigo-700'
                  }`}
                >
                  {showAllColumns ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  <span>
                    {showAllColumns ? 'Hide Columns' : `Show All ${columns.length} Columns`}
                  </span>
                </button>
              )}
            </div>
            
            <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
              Showing {showingRows.toLocaleString()} of {totalRows.toLocaleString()} rows
            </div>
          </div>
        </div>

        {/* Data Table */}
        <div className="flex-1 overflow-auto">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className={`${isDarkTheme ? 'bg-slate-700' : 'bg-gray-50'} sticky top-0`}>
                <tr>
                  <th className={`px-4 py-3 text-left text-xs font-medium uppercase tracking-wider ${isDarkTheme ? 'text-gray-300' : 'text-gray-500'}`}>
                    #
                  </th>
                  {visibleColumns.map((column, index) => (
                    <th
                      key={column}
                      className={`px-4 py-3 text-left text-xs font-medium uppercase tracking-wider ${isDarkTheme ? 'text-gray-300' : 'text-gray-500'}`}
                    >
                      {column}
                    </th>
                  ))}
                  {hiddenColumnsCount > 0 && !showAllColumns && (
                    <th className={`px-4 py-3 text-left text-xs font-medium uppercase tracking-wider ${isDarkTheme ? 'text-gray-300' : 'text-gray-500'}`}>
                      +{hiddenColumnsCount} more
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className={`${isDarkTheme ? 'bg-slate-800' : 'bg-white'} divide-y ${isDarkTheme ? 'divide-slate-700' : 'divide-gray-200'}`}>
                {displayData.map((row, rowIndex) => (
                  <tr
                    key={rowIndex}
                    className={`${isDarkTheme ? 'hover:bg-slate-700' : 'hover:bg-gray-50'} transition-colors`}
                  >
                    <td className={`px-4 py-3 text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                      {rowIndex + 1}
                    </td>
                    {visibleColumns.map((column, colIndex) => (
                      <td
                        key={column}
                        className={`px-4 py-3 text-sm ${isDarkTheme ? 'text-white' : 'text-gray-900'} max-w-xs truncate`}
                        title={String(row[column] || '')}
                      >
                        {String(row[column] || '')}
                      </td>
                    ))}
                    {hiddenColumnsCount > 0 && !showAllColumns && (
                      <td className={`px-4 py-3 text-sm ${isDarkTheme ? 'text-gray-400' : 'text-gray-500'}`}>
                        ...
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className={`${isDarkTheme ? 'bg-slate-700' : 'bg-gray-50'} px-6 py-4 rounded-b-2xl border-t ${isDarkTheme ? 'border-slate-600' : 'border-gray-200'}`}>
          <div className="flex items-center justify-between">
            <div className={`text-sm ${isDarkTheme ? 'text-gray-300' : 'text-gray-600'}`}>
              {searchTerm && (
                <span>
                  Filtered from {totalRows.toLocaleString()} to {showingRows.toLocaleString()} rows
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={onClose}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  isDarkTheme 
                    ? 'bg-slate-600 hover:bg-slate-500 text-white' 
                    : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
                }`}
              >
                Close
              </button>
              <button
                onClick={() => {
                  // This would trigger chart generation
                  onClose()
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors"
              >
                Generate Charts
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DataPreview

