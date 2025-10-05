import React, { useState } from 'react'
import { 
  Download, 
  FileText, 
  Code, 
  Share, 
  X, 
  CheckCircle,
  Loader,
  ExternalLink,
  Copy,
  Mail,
  MessageSquare
} from 'lucide-react'

interface ExportModalProps {
  isOpen: boolean
  onClose: () => void
  data: any[]
  analysisResults?: any
  isNormal?: boolean
}

const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  data,
  analysisResults,
  isNormal = false
}) => {
  const [exportType, setExportType] = useState('pdf')
  const [isExporting, setIsExporting] = useState(false)
  const [exportComplete, setExportComplete] = useState(false)
  const [shareUrl, setShareUrl] = useState('')

  const exportOptions = [
    {
      id: 'pdf',
      name: 'PDF Report',
      description: 'Professional report with charts and analysis',
      icon: FileText,
      formats: ['A4', 'Letter', 'Legal']
    },
    {
      id: 'excel',
      name: 'Excel Workbook',
      description: 'Data with charts and pivot tables',
      icon: Download,
      formats: ['.xlsx', '.xls']
    },
    {
      id: 'python',
      name: 'Python Code',
      description: 'Jupyter notebook with analysis code',
      icon: Code,
      formats: ['.ipynb', '.py']
    },
    {
      id: 'r',
      name: 'R Script',
      description: 'R markdown with analysis and plots',
      icon: Code,
      formats: ['.Rmd', '.R']
    },
    {
      id: 'json',
      name: 'JSON Data',
      description: 'Raw data and analysis results',
      icon: Download,
      formats: ['.json']
    }
  ]

  const shareOptions = [
    {
      id: 'link',
      name: 'Share Link',
      description: 'Generate a shareable URL',
      icon: ExternalLink
    },
    {
      id: 'email',
      name: 'Email Report',
      description: 'Send via email',
      icon: Mail
    },
    {
      id: 'embed',
      name: 'Embed Code',
      description: 'Embed in website',
      icon: Code
    }
  ]

  const handleExport = async (type: string) => {
    setIsExporting(true)
    
    // Simulate export process
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    // Mock export completion
    setExportComplete(true)
    setIsExporting(false)
    
    // Generate mock share URL
    setShareUrl(`https://datasage.app/share/${Math.random().toString(36).substr(2, 9)}`)
  }

  const handleShare = async (type: string) => {
    if (type === 'link') {
      setShareUrl(`https://datasage.app/share/${Math.random().toString(36).substr(2, 9)}`)
    } else if (type === 'email') {
      // Mock email sharing
      console.log('Email sharing initiated')
    } else if (type === 'embed') {
      // Mock embed code generation
      console.log('Embed code generated')
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    // You could add a toast notification here
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        {/* Backdrop */}
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className={`
          inline-block align-bottom rounded-2xl text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full
          ${isNormal 
            ? 'bg-white' 
            : 'backdrop-blur-xl bg-slate-900/90 border border-white/20'
          }
        `}>
          {/* Header */}
          <div className={`
            px-6 py-4 border-b
            ${isNormal 
              ? 'bg-gray-50 border-gray-200' 
              : 'bg-white/5 border-white/10'
            }
          `}>
            <div className="flex items-center justify-between">
              <h3 className={`text-lg font-semibold ${
                isNormal 
                  ? 'text-gray-900' 
                  : 'text-white'
              }`}>
                Export & Share
              </h3>
              <button
                onClick={onClose}
                className={`
                  p-2 rounded-lg transition-colors duration-200
                  ${isNormal 
                    ? 'text-gray-400 hover:text-gray-600 hover:bg-gray-100' 
                    : 'text-slate-400 hover:text-white hover:bg-white/10'
                  }
                `}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="px-6 py-6">
            {!exportComplete ? (
              <div className="space-y-6">
                {/* Export Options */}
                <div>
                  <h4 className={`text-md font-medium mb-4 ${
                    isNormal 
                      ? 'text-gray-900' 
                      : 'text-white'
                  }`}>
                    Export Format
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {exportOptions.map((option) => {
                      const Icon = option.icon
                      return (
                        <button
                          key={option.id}
                          onClick={() => setExportType(option.id)}
                          className={`
                            p-4 rounded-xl border text-left transition-all duration-200
                            ${exportType === option.id
                              ? isNormal
                                ? 'bg-blue-50 border-blue-200 text-blue-900'
                                : 'bg-gradient-to-r from-cyan-500/20 to-purple-500/20 border-cyan-500/30 text-cyan-400'
                              : isNormal
                                ? 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
                                : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'
                            }
                          `}
                        >
                          <div className="flex items-center space-x-3">
                            <Icon className="w-5 h-5" />
                            <div>
                              <div className="font-medium">{option.name}</div>
                              <div className={`text-sm ${
                                isNormal 
                                  ? 'text-gray-500' 
                                  : 'text-slate-400'
                              }`}>
                                {option.description}
                              </div>
                            </div>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Export Button */}
                <div className="flex justify-end">
                  <button
                    onClick={() => handleExport(exportType)}
                    disabled={isExporting}
                    className={`
                      flex items-center space-x-2 px-6 py-3 rounded-lg text-sm font-medium transition-all duration-200
                      ${isExporting
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : isNormal
                          ? 'bg-blue-600 hover:bg-blue-700 text-white'
                          : 'bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-600 hover:to-purple-700 text-white'
                      }
                    `}
                  >
                    {isExporting ? (
                      <>
                        <Loader className="w-4 h-4 animate-spin" />
                        <span>Exporting...</span>
                      </>
                    ) : (
                      <>
                        <Download className="w-4 h-4" />
                        <span>Export {exportOptions.find(o => o.id === exportType)?.name}</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Success Message */}
                <div className="text-center">
                  <CheckCircle className={`w-16 h-16 mx-auto mb-4 ${
                    isNormal 
                      ? 'text-green-500' 
                      : 'text-green-400'
                  }`} />
                  <h4 className={`text-lg font-semibold mb-2 ${
                    isNormal 
                      ? 'text-gray-900' 
                      : 'text-white'
                  }`}>
                    Export Complete!
                  </h4>
                  <p className={`text-sm ${
                    isNormal 
                      ? 'text-gray-600' 
                      : 'text-slate-400'
                  }`}>
                    Your {exportOptions.find(o => o.id === exportType)?.name} has been generated successfully.
                  </p>
                </div>

                {/* Share Options */}
                <div>
                  <h4 className={`text-md font-medium mb-4 ${
                    isNormal 
                      ? 'text-gray-900' 
                      : 'text-white'
                  }`}>
                    Share Results
                  </h4>
                  <div className="space-y-3">
                    {shareOptions.map((option) => {
                      const Icon = option.icon
                      return (
                        <button
                          key={option.id}
                          onClick={() => handleShare(option.id)}
                          className={`
                            w-full p-4 rounded-xl border text-left transition-all duration-200
                            ${isNormal
                              ? 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
                              : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'
                            }
                          `}
                        >
                          <div className="flex items-center space-x-3">
                            <Icon className="w-5 h-5" />
                            <div>
                              <div className="font-medium">{option.name}</div>
                              <div className={`text-sm ${
                                isNormal 
                                  ? 'text-gray-500' 
                                  : 'text-slate-400'
                              }`}>
                                {option.description}
                              </div>
                            </div>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Share URL */}
                {shareUrl && (
                  <div className={`
                    p-4 rounded-xl border
                    ${isNormal 
                      ? 'bg-gray-50 border-gray-200' 
                      : 'bg-white/5 border-white/10'
                    }
                  `}>
                    <div className="flex items-center space-x-2">
                      <input
                        type="text"
                        value={shareUrl}
                        readOnly
                        className={`
                          flex-1 px-3 py-2 rounded-lg text-sm
                          ${isNormal 
                            ? 'bg-white border-gray-300 text-gray-900' 
                            : 'bg-slate-800 border-slate-600 text-white'
                          }
                        `}
                      />
                      <button
                        onClick={() => copyToClipboard(shareUrl)}
                        className={`
                          p-2 rounded-lg transition-colors duration-200
                          ${isNormal 
                            ? 'text-gray-500 hover:text-gray-700 hover:bg-gray-100' 
                            : 'text-slate-400 hover:text-white hover:bg-white/10'
                          }
                        `}
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex justify-end space-x-3">
                  <button
                    onClick={() => {
                      setExportComplete(false)
                      setShareUrl('')
                    }}
                    className={`
                      px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200
                      ${isNormal
                        ? 'text-gray-700 hover:bg-gray-100'
                        : 'text-slate-300 hover:bg-white/10'
                      }
                    `}
                  >
                    Export Another
                  </button>
                  <button
                    onClick={onClose}
                    className={`
                      px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200
                      ${isNormal
                        ? 'bg-blue-600 hover:bg-blue-700 text-white'
                        : 'bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-600 hover:to-purple-700 text-white'
                      }
                    `}
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ExportModal

