import React, { useState, useRef, useEffect } from 'react';
import { 
  X, 
  Upload, 
  FileText, 
  AlertCircle, 
  Cloud, 
  Check, 
  Trash2, 
  Loader2,
  Database,
  Lock,
  Sparkles
} from 'lucide-react';

const UploadModal = ({ isOpen, onClose, onUpload, loading }) => {
  const [formData, setFormData] = useState({
    file: null
  });
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, uploading, completed, error
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [activeTab, setActiveTab] = useState('file'); // file, database
  const [isDarkMode, setIsDarkMode] = useState(false);
  const fileInputRef = useRef(null);

  // Check for dark mode preference
  useEffect(() => {
    const checkDarkMode = () => {
      setIsDarkMode(window.matchMedia('(prefers-color-scheme: dark)').matches);
    };
    
    checkDarkMode();
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', checkDarkMode);
    
    return () => mediaQuery.removeEventListener('change', checkDarkMode);
  }, []);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file) => {
    // Validate file type
    const allowedTypes = ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
    if (!allowedTypes.includes(file.type)) {
      alert('Please upload a CSV or Excel file');
      return;
    }

    // Validate file size (10MB limit)
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return;
    }

    const newFile = {
      id: Date.now(),
      file: file,
      name: file.name,
      size: file.size,
      type: file.type,
      progress: 0,
      status: 'pending'
    };

    setUploadedFiles(prev => [...prev, newFile]);
    setFormData(prev => ({
      ...prev,
      file
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.file) {
      setUploadStatus('uploading');
      
      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 100) {
            clearInterval(progressInterval);
            setUploadStatus('completed');
            return 100;
          }
          return prev + Math.random() * 10;
        });
      }, 200);

      // Update file progress
      setUploadedFiles(prev => prev.map(f => 
        f.file === formData.file ? { ...f, progress: 0, status: 'uploading' } : f
      ));

      try {
        await onUpload(formData.file);
        
        // Mark as completed
        setUploadedFiles(prev => prev.map(f => 
          f.file === formData.file ? { ...f, progress: 100, status: 'completed' } : f
        ));
        
        clearInterval(progressInterval);
        setUploadStatus('completed');
      } catch (error) {
        setUploadedFiles(prev => prev.map(f => 
          f.file === formData.file ? { ...f, status: 'error' } : f
        ));
        setUploadStatus('error');
        clearInterval(progressInterval);
      }
    }
  };

  const removeFile = (fileId) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId));
    if (uploadedFiles.length === 1) {
      setFormData(prev => ({ ...prev, file: null }));
    }
  };

  const resetForm = () => {
    setFormData({
      file: null
    });
    setUploadedFiles([]);
    setUploadProgress(0);
    setUploadStatus('idle');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (fileType) => {
    if (fileType.includes('csv') || fileType.includes('excel') || fileType.includes('sheet')) {
      return <FileText className="w-5 h-5 text-red-500" />;
    }
    return <FileText className="w-5 h-5 text-gray-500" />;
  };

  if (!isOpen) return null;

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center p-4 ${isDarkMode ? 'bg-black/60' : 'bg-black/50'} backdrop-blur-sm`}>
      <div className={`${isDarkMode ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'} rounded-2xl border shadow-2xl w-full max-w-2xl transform transition-all duration-300 scale-100`}>
        {/* Header */}
        <div className={`flex items-center justify-between p-6 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-red-100 rounded-xl flex items-center justify-center">
              <Cloud className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <h2 className={`text-xl font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                Upload files
              </h2>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                Select and upload the files of your choice
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className={`p-2 rounded-lg ${isDarkMode ? 'hover:bg-gray-800 text-gray-400' : 'hover:bg-gray-100 text-gray-500'} transition-colors duration-200`}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className={`flex border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <button
            onClick={() => setActiveTab('file')}
            className={`flex-1 px-6 py-4 text-sm font-medium transition-colors duration-200 ${
              activeTab === 'file'
                ? isDarkMode 
                  ? 'text-red-400 border-b-2 border-red-400 bg-gray-800/50' 
                  : 'text-red-600 border-b-2 border-red-600 bg-red-50'
                : isDarkMode
                  ? 'text-gray-400 hover:text-gray-300'
                  : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <Upload className="w-4 h-4" />
              <span>File Upload</span>
            </div>
          </button>
          <button
            onClick={() => setActiveTab('database')}
            className={`flex-1 px-6 py-4 text-sm font-medium transition-colors duration-200 relative ${
              activeTab === 'database'
                ? isDarkMode 
                  ? 'text-red-400 border-b-2 border-red-400 bg-gray-800/50' 
                  : 'text-red-600 border-b-2 border-red-600 bg-red-50'
                : isDarkMode
                  ? 'text-gray-400 hover:text-gray-300'
                  : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <Database className="w-4 h-4" />
              <span>Database Import</span>
              <Lock className="w-3 h-3 opacity-60" />
            </div>
          </button>
        </div>

        <div className="p-6">
          {activeTab === 'file' ? (
            <>
              {/* Drag and Drop Area */}
              <div
                className={`relative border-2 border-dashed rounded-xl p-12 text-center transition-all duration-300 ${
                  dragActive
                    ? isDarkMode 
                      ? 'border-red-400 bg-red-900/20' 
                      : 'border-red-500 bg-red-50'
                    : formData.file
                    ? isDarkMode
                      ? 'border-green-500 bg-green-900/20'
                      : 'border-green-500 bg-green-50'
                    : isDarkMode
                      ? 'border-gray-600 hover:border-gray-500'
                      : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileInput}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                
                <div className="space-y-4">
                  <div className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center ${
                    isDarkMode ? 'bg-gray-800' : 'bg-gray-100'
                  }`}>
                    <Cloud className={`w-8 h-8 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`} />
                  </div>
                  
                  <div>
                    <p className={`text-lg font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      Choose a file or drag & drop it here.
                    </p>
                    <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                      CSV, XLS, XLSX formats, up to 10 MB
                    </p>
                  </div>
                  
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className={`inline-flex items-center px-6 py-3 rounded-lg font-medium transition-colors duration-200 ${
                      isDarkMode
                        ? 'bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:text-gray-900'
                    }`}
                  >
                    Browse File
                  </button>
                </div>
              </div>

              {/* Uploaded Files */}
              {uploadedFiles.length > 0 && (
                <div className="mt-6 space-y-3">
                  {uploadedFiles.map((file) => (
                    <div
                      key={file.id}
                      className={`p-4 rounded-xl border transition-all duration-300 ${
                        isDarkMode 
                          ? 'bg-gray-800 border-gray-700' 
                          : 'bg-gray-50 border-gray-200'
                      }`}
                    >
                      <div className="flex items-center space-x-4">
                        {getFileIcon(file.type)}
                        
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium truncate ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                            {file.name}
                          </p>
                          <div className="flex items-center space-x-2 mt-1">
                            <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                              {formatFileSize(file.size)}
                            </p>
                            {file.status === 'uploading' && (
                              <>
                                <span className={`text-xs ${isDarkMode ? 'text-blue-400' : 'text-blue-600'}`}>
                                  Uploading...
                                </span>
                                <Loader2 className="w-3 h-3 animate-spin text-blue-500" />
                              </>
                            )}
                            {file.status === 'completed' && (
                              <>
                                <span className={`text-xs ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>
                                  Completed
                                </span>
                                <Check className="w-3 h-3 text-green-500" />
                              </>
                            )}
                            {file.status === 'error' && (
                              <span className="text-xs text-red-600">Failed</span>
                            )}
                          </div>
                          
                          {file.status === 'uploading' && (
                            <div className={`w-full bg-gray-200 rounded-full h-1.5 mt-2 ${isDarkMode ? 'bg-gray-700' : ''}`}>
                              <div 
                                className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                                style={{ width: `${Math.min(file.progress, 100)}%` }}
                              />
                            </div>
                          )}
                        </div>
                        
                        <button
                          onClick={() => removeFile(file.id)}
                          className={`p-2 rounded-lg transition-colors duration-200 ${
                            isDarkMode 
                              ? 'hover:bg-gray-700 text-gray-400' 
                              : 'hover:bg-gray-200 text-gray-500'
                          }`}
                        >
                          {file.status === 'completed' ? (
                            <Trash2 className="w-4 h-4" />
                          ) : (
                            <X className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

            </>
          ) : (
            /* Database Import Tab */
            <div className="text-center py-12">
              <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <Database className="w-10 h-10 text-gray-400" />
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                Database Import Coming Soon
              </h3>
              <p className={`text-sm mb-6 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                Connect your MySQL, PostgreSQL, or other databases directly to DataSage
              </p>
              <div className={`inline-flex items-center px-4 py-2 rounded-lg ${isDarkMode ? 'bg-gray-800 text-gray-400' : 'bg-gray-100 text-gray-500'}`}>
                <Lock className="w-4 h-4 mr-2" />
                <span className="text-sm">Feature in development</span>
              </div>
            </div>
          )}

          {/* File Requirements */}
          {activeTab === 'file' && (
            <div className={`mt-6 p-4 rounded-xl border ${
              isDarkMode 
                ? 'bg-blue-900/20 border-blue-800' 
                : 'bg-blue-50 border-blue-200'
            }`}>
              <div className="flex items-start">
                <AlertCircle className={`w-5 h-5 mt-0.5 mr-3 flex-shrink-0 ${isDarkMode ? 'text-blue-400' : 'text-blue-600'}`} />
                <div className={`text-sm ${isDarkMode ? 'text-blue-300' : 'text-blue-800'}`}>
                  <p className="font-medium mb-1">File Requirements:</p>
                  <ul className="text-xs space-y-1">
                    <li>• CSV, XLS, or XLSX format</li>
                    <li>• Maximum file size: 10MB</li>
                    <li>• First row should contain column headers</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex space-x-3 mt-6">
            <button
              type="button"
              onClick={handleClose}
              className={`flex-1 px-6 py-3 rounded-lg font-medium transition-colors duration-200 ${
                isDarkMode
                  ? 'border border-gray-600 text-gray-300 hover:bg-gray-800'
                  : 'border border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!formData.file || loading || uploadStatus === 'completed'}
              className="flex-1 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-medium flex items-center justify-center space-x-2"
            >
              {loading || uploadStatus === 'uploading' ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : uploadStatus === 'completed' ? (
                <>
                  <Check className="w-4 h-4" />
                  <span>Completed</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Upload Dataset</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadModal;

