import React from 'react'
import { Table, FileText } from 'lucide-react'

const DataTable = ({ title, data, columns, maxRows = 10, description }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
            {description && (
              <p className="text-slate-400 text-sm">{description}</p>
            )}
          </div>
          <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center">
            <Table className="w-5 h-5 text-green-400" />
          </div>
        </div>
        
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-slate-400">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-sm">No data available</p>
          </div>
        </div>
      </div>
    )
  }

  const displayData = data.slice(0, maxRows)
  const tableColumns = columns || Object.keys(data[0] || {})

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
          {description && (
            <p className="text-slate-400 text-sm">{description}</p>
          )}
        </div>
        <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center">
          <Table className="w-5 h-5 text-green-400" />
        </div>
      </div>
      
      <div className="flex-1 overflow-hidden">
        <div className="overflow-x-auto h-full">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                {tableColumns.map((column, index) => (
                  <th 
                    key={index}
                    className="text-left py-3 px-2 font-medium text-slate-300"
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayData.map((row, rowIndex) => (
                <tr 
                  key={rowIndex}
                  className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
                >
                  {tableColumns.map((column, colIndex) => (
                    <td 
                      key={colIndex}
                      className="py-3 px-2 text-slate-200"
                    >
                      {typeof row[column] === 'number' 
                        ? row[column].toLocaleString() 
                        : String(row[column] || '').substring(0, 50)
                      }
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {data.length > maxRows && (
          <div className="mt-3 text-center">
            <span className="text-xs text-slate-500">
              Showing {maxRows} of {data.length} rows
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default DataTable

