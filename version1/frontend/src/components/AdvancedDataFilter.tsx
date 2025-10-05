import React, { useState } from 'react'
import { 
  Filter, 
  Plus, 
  X, 
  ChevronDown, 
  ChevronUp, 
  Search, 
  Calendar,
  Hash,
  Type,
  ToggleLeft,
  ToggleRight,
  Zap,
  Cpu
} from 'lucide-react'

interface FilterCondition {
  id: string
  column: string
  operator: string
  value: any
  type: 'text' | 'number' | 'date' | 'boolean'
  logicalOperator?: 'AND' | 'OR'
}

interface AdvancedDataFilterProps {
  columns: string[]
  onFiltersChange: (filters: FilterCondition[]) => void
  isNormal?: boolean
}

const AdvancedDataFilter: React.FC<AdvancedDataFilterProps> = ({
  columns,
  onFiltersChange,
  isNormal = false
}) => {
  const [filters, setFilters] = useState<FilterCondition[]>([])
  const [isExpanded, setIsExpanded] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const operators = {
    text: [
      { value: 'equals', label: 'Equals' },
      { value: 'contains', label: 'Contains' },
      { value: 'starts_with', label: 'Starts with' },
      { value: 'ends_with', label: 'Ends with' },
      { value: 'regex', label: 'Regex match' },
      { value: 'is_empty', label: 'Is empty' },
      { value: 'is_not_empty', label: 'Is not empty' }
    ],
    number: [
      { value: 'equals', label: 'Equals' },
      { value: 'greater_than', label: 'Greater than' },
      { value: 'less_than', label: 'Less than' },
      { value: 'between', label: 'Between' },
      { value: 'is_null', label: 'Is null' },
      { value: 'is_not_null', label: 'Is not null' }
    ],
    date: [
      { value: 'equals', label: 'Equals' },
      { value: 'after', label: 'After' },
      { value: 'before', label: 'Before' },
      { value: 'between', label: 'Between' },
      { value: 'last_n_days', label: 'Last N days' },
      { value: 'this_month', label: 'This month' },
      { value: 'this_year', label: 'This year' }
    ],
    boolean: [
      { value: 'equals', label: 'Equals' },
      { value: 'is_true', label: 'Is true' },
      { value: 'is_false', label: 'Is false' }
    ]
  }

  const addFilter = () => {
    const newFilter: FilterCondition = {
      id: Date.now().toString(),
      column: columns[0] || '',
      operator: 'equals',
      value: '',
      type: 'text',
      logicalOperator: filters.length > 0 ? 'AND' : undefined
    }
    const newFilters = [...filters, newFilter]
    setFilters(newFilters)
    onFiltersChange(newFilters)
  }

  const removeFilter = (id: string) => {
    const newFilters = filters.filter(f => f.id !== id)
    setFilters(newFilters)
    onFiltersChange(newFilters)
  }

  const updateFilter = (id: string, field: keyof FilterCondition, value: any) => {
    const newFilters = filters.map(f => 
      f.id === id ? { ...f, [field]: value } : f
    )
    setFilters(newFilters)
    onFiltersChange(newFilters)
  }

  const getColumnType = (column: string): 'text' | 'number' | 'date' | 'boolean' => {
    // This would typically be determined by the actual data
    // For now, we'll use simple heuristics
    if (column.toLowerCase().includes('date') || column.toLowerCase().includes('time')) {
      return 'date'
    }
    if (column.toLowerCase().includes('id') || column.toLowerCase().includes('count') || column.toLowerCase().includes('amount')) {
      return 'number'
    }
    if (column.toLowerCase().includes('active') || column.toLowerCase().includes('enabled') || column.toLowerCase().includes('status')) {
      return 'boolean'
    }
    return 'text'
  }

  const getInputComponent = (filter: FilterCondition) => {
    const { type, operator, value } = filter

    switch (type) {
      case 'boolean':
        return (
          <select
            value={value}
            onChange={(e) => updateFilter(filter.id, 'value', e.target.value)}
            className={`
              px-3 py-2 rounded-lg border text-sm
              ${isNormal 
                ? 'bg-white border-gray-300 text-gray-900' 
                : 'bg-slate-800 border-slate-600 text-white'
              }
            `}
          >
            <option value="true">True</option>
            <option value="false">False</option>
          </select>
        )

      case 'date':
        if (operator === 'between') {
          return (
            <div className="flex items-center space-x-2">
              <input
                type="date"
                value={value?.start || ''}
                onChange={(e) => updateFilter(filter.id, 'value', { ...value, start: e.target.value })}
                className={`
                  px-3 py-2 rounded-lg border text-sm
                  ${isNormal 
                    ? 'bg-white border-gray-300 text-gray-900' 
                    : 'bg-slate-800 border-slate-600 text-white'
                  }
                `}
              />
              <span className={isNormal ? 'text-gray-500' : 'text-slate-400'}>to</span>
              <input
                type="date"
                value={value?.end || ''}
                onChange={(e) => updateFilter(filter.id, 'value', { ...value, end: e.target.value })}
                className={`
                  px-3 py-2 rounded-lg border text-sm
                  ${isNormal 
                    ? 'bg-white border-gray-300 text-gray-900' 
                    : 'bg-slate-800 border-slate-600 text-white'
                  }
                `}
              />
            </div>
          )
        }
        return (
          <input
            type="date"
            value={value}
            onChange={(e) => updateFilter(filter.id, 'value', e.target.value)}
            className={`
              px-3 py-2 rounded-lg border text-sm
              ${isNormal 
                ? 'bg-white border-gray-300 text-gray-900' 
                : 'bg-slate-800 border-slate-600 text-white'
              }
            `}
          />
        )

      case 'number':
        if (operator === 'between') {
          return (
            <div className="flex items-center space-x-2">
              <input
                type="number"
                placeholder="Min"
                value={value?.min || ''}
                onChange={(e) => updateFilter(filter.id, 'value', { ...value, min: e.target.value })}
                className={`
                  px-3 py-2 rounded-lg border text-sm
                  ${isNormal 
                    ? 'bg-white border-gray-300 text-gray-900' 
                    : 'bg-slate-800 border-slate-600 text-white'
                  }
                `}
              />
              <span className={isNormal ? 'text-gray-500' : 'text-slate-400'}>to</span>
              <input
                type="number"
                placeholder="Max"
                value={value?.max || ''}
                onChange={(e) => updateFilter(filter.id, 'value', { ...value, max: e.target.value })}
                className={`
                  px-3 py-2 rounded-lg border text-sm
                  ${isNormal 
                    ? 'bg-white border-gray-300 text-gray-900' 
                    : 'bg-slate-800 border-slate-600 text-white'
                  }
                `}
              />
            </div>
          )
        }
        return (
          <input
            type="number"
            value={value}
            onChange={(e) => updateFilter(filter.id, 'value', e.target.value)}
            placeholder="Enter value"
            className={`
              px-3 py-2 rounded-lg border text-sm
              ${isNormal 
                ? 'bg-white border-gray-300 text-gray-900' 
                : 'bg-slate-800 border-slate-600 text-white'
              }
            `}
          />
        )

      default:
        return (
          <input
            type="text"
            value={value}
            onChange={(e) => updateFilter(filter.id, 'value', e.target.value)}
            placeholder="Enter value"
            className={`
              px-3 py-2 rounded-lg border text-sm
              ${isNormal 
                ? 'bg-white border-gray-300 text-gray-900' 
                : 'bg-slate-800 border-slate-600 text-white'
              }
            `}
          />
        )
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'text': return <Type className="w-4 h-4" />
      case 'number': return <Hash className="w-4 h-4" />
      case 'date': return <Calendar className="w-4 h-4" />
      case 'boolean': return <ToggleLeft className="w-4 h-4" />
      default: return <Type className="w-4 h-4" />
    }
  }

  return (
    <div className={`
      rounded-lg shadow-sm border p-6
      ${isNormal 
        ? 'bg-white border-gray-200' 
        : 'backdrop-blur-xl bg-white/10 border-white/20'
      }
    `}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className={`
            p-2 rounded-lg
            ${isNormal 
              ? 'bg-blue-100' 
              : 'bg-gradient-to-r from-cyan-500/20 to-purple-500/20'
            }
          `}>
            {isNormal ? (
              <Filter className={`w-5 h-5 ${isNormal ? 'text-blue-600' : 'text-cyan-400'}`} />
            ) : (
              <Cpu className="w-5 h-5 text-cyan-400" />
            )}
          </div>
          <div>
            <h3 className={`text-lg font-semibold ${
              isNormal 
                ? 'text-gray-900' 
                : 'text-white'
            }`}>
              {isNormal ? 'Data Filters' : 'Advanced Data Filters'}
            </h3>
            <p className={`text-sm ${
              isNormal 
                ? 'text-gray-500' 
                : 'text-slate-400'
            }`}>
              {isNormal 
                ? 'Filter your data easily'
                : 'Create complex filter conditions with logical operators'
              }
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {!isNormal && (
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={`
                flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                ${showAdvanced
                  ? isNormal
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-cyan-500/20 text-cyan-400'
                  : isNormal
                    ? 'text-gray-600 hover:bg-gray-100'
                    : 'text-slate-300 hover:bg-white/10'
                }
              `}
            >
              <Zap className="w-4 h-4" />
              <span>Advanced</span>
            </button>
          )}
          
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className={`
              p-2 rounded-lg transition-colors
              ${isNormal 
                ? 'text-gray-400 hover:text-gray-600 hover:bg-gray-100' 
                : 'text-slate-400 hover:text-white hover:bg-white/10'
              }
            `}
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Filter Conditions */}
      {isExpanded && (
        <div className="space-y-4">
          {filters.map((filter, index) => (
            <div key={filter.id} className={`
              p-4 rounded-lg border
              ${isNormal 
                ? 'bg-gray-50 border-gray-200' 
                : 'bg-white/5 border-white/10'
              }
            `}>
              <div className="flex items-center space-x-3">
                {/* Logical Operator */}
                {index > 0 && (
                  <select
                    value={filter.logicalOperator || 'AND'}
                    onChange={(e) => updateFilter(filter.id, 'logicalOperator', e.target.value)}
                    className={`
                      px-3 py-2 rounded-lg border text-sm font-medium
                      ${isNormal 
                        ? 'bg-white border-gray-300 text-gray-900' 
                        : 'bg-slate-800 border-slate-600 text-white'
                      }
                    `}
                  >
                    <option value="AND">AND</option>
                    <option value="OR">OR</option>
                  </select>
                )}

                {/* Column Selector */}
                <select
                  value={filter.column}
                  onChange={(e) => {
                    const newType = getColumnType(e.target.value)
                    updateFilter(filter.id, 'column', e.target.value)
                    updateFilter(filter.id, 'type', newType)
                    updateFilter(filter.id, 'operator', operators[newType][0].value)
                  }}
                  className={`
                    px-3 py-2 rounded-lg border text-sm
                    ${isNormal 
                      ? 'bg-white border-gray-300 text-gray-900' 
                      : 'bg-slate-800 border-slate-600 text-white'
                    }
                  `}
                >
                  {columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>

                {/* Type Indicator */}
                <div className={`
                  flex items-center space-x-1 px-2 py-1 rounded text-xs font-medium
                  ${isNormal 
                    ? 'bg-gray-100 text-gray-600' 
                    : 'bg-slate-700 text-slate-300'
                  }
                `}>
                  {getTypeIcon(filter.type)}
                  <span className="capitalize">{filter.type}</span>
                </div>

                {/* Operator Selector */}
                <select
                  value={filter.operator}
                  onChange={(e) => updateFilter(filter.id, 'operator', e.target.value)}
                  className={`
                    px-3 py-2 rounded-lg border text-sm
                    ${isNormal 
                      ? 'bg-white border-gray-300 text-gray-900' 
                      : 'bg-slate-800 border-slate-600 text-white'
                    }
                  `}
                >
                  {operators[filter.type].map(op => (
                    <option key={op.value} value={op.value}>{op.label}</option>
                  ))}
                </select>

                {/* Value Input */}
                {!['is_empty', 'is_not_empty', 'is_null', 'is_not_null', 'is_true', 'is_false'].includes(filter.operator) && (
                  getInputComponent(filter)
                )}

                {/* Remove Button */}
                <button
                  onClick={() => removeFilter(filter.id)}
                  className={`
                    p-2 rounded-lg transition-colors
                    ${isNormal 
                      ? 'text-red-600 hover:bg-red-50' 
                      : 'text-red-400 hover:bg-red-500/10'
                    }
                  `}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}

          {/* Add Filter Button */}
          <button
            onClick={addFilter}
            className={`
              w-full flex items-center justify-center space-x-2 px-4 py-3 rounded-lg text-sm font-medium transition-colors border-2 border-dashed
              ${isNormal
                ? 'border-gray-300 text-gray-600 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50'
                : 'border-white/20 text-slate-400 hover:border-cyan-400 hover:text-cyan-400 hover:bg-cyan-500/10'
              }
            `}
          >
            <Plus className="w-4 h-4" />
            <span>Add Filter Condition</span>
          </button>

          {/* Advanced Options */}
          {showAdvanced && !isNormal && (
            <div className={`
              p-4 rounded-lg border
              ${isNormal 
                ? 'bg-blue-50 border-blue-200' 
                : 'bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border-cyan-500/20'
              }
            `}>
              <h4 className={`text-sm font-medium mb-3 ${
                isNormal ? 'text-blue-800' : 'text-cyan-300'
              }`}>
                Advanced Options
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className={`text-xs font-medium ${
                    isNormal ? 'text-blue-700' : 'text-cyan-400'
                  }`}>
                    Case Sensitivity
                  </label>
                  <select className={`
                    w-full mt-1 px-3 py-2 rounded-lg border text-sm
                    ${isNormal 
                      ? 'bg-white border-gray-300 text-gray-900' 
                      : 'bg-slate-800 border-slate-600 text-white'
                    }
                  `}>
                    <option value="insensitive">Case Insensitive</option>
                    <option value="sensitive">Case Sensitive</option>
                  </select>
                </div>
                <div>
                  <label className={`text-xs font-medium ${
                    isNormal ? 'text-blue-700' : 'text-cyan-400'
                  }`}>
                    Null Handling
                  </label>
                  <select className={`
                    w-full mt-1 px-3 py-2 rounded-lg border text-sm
                    ${isNormal 
                      ? 'bg-white border-gray-300 text-gray-900' 
                      : 'bg-slate-800 border-slate-600 text-white'
                    }
                  `}>
                    <option value="exclude">Exclude Nulls</option>
                    <option value="include">Include Nulls</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AdvancedDataFilter

