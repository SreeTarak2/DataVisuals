import React, { useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  Upload,
  FileText,
  FileSpreadsheet,
  Database,
  X,
  Cloud,
  Server,
  CheckCircle,
  AlertCircle,
  Shield,
  Eye
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import useDatasetStore from '../../../store/datasetStore';
import { toast } from 'react-hot-toast';

const UploadModal = ({ isOpen, onClose, onProcessingStart }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadType, setUploadType] = useState('file');
  const [uploadProgress, setUploadProgress] = useState(0);
  const { uploadDataset, setProcessingDataset } = useDatasetStore();

  const onDrop = useCallback(async (acceptedFiles) => {
    setUploading(true);
    setUploadProgress(0);

    try {
      for (const file of acceptedFiles) {
        const progressInterval = setInterval(() => {
          setUploadProgress(prev => Math.min(prev + 10, 90));
        }, 200);

        const result = await uploadDataset(file, file.name, '');

        clearInterval(progressInterval);
        setUploadProgress(100);

        if (result.success) {
          const datasetId = result.dataset?.id || result.dataset?._id;
          
          if (datasetId) {
            setProcessingDataset(datasetId);
            if (onProcessingStart) {
              onProcessingStart(datasetId);
            }
            toast.success(`${file.name} uploaded! Processing started...`);
            
            setTimeout(() => {
              setUploadProgress(0);
              setUploading(false);
              onClose();
            }, 800);
          } else {
            toast.success(`${file.name} uploaded successfully!`);
            setTimeout(() => {
              setUploadProgress(0);
              setUploading(false);
              onClose();
            }, 1000);
          }

          setTimeout(() => {
            setUploadProgress(0);
            setUploading(false);
          }, 1500);
        } else {
          throw new Error(result.error || 'Upload failed');
        }
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Upload failed. Please try again.');
      setUploading(false);
      setUploadProgress(0);
    }
  }, [uploadDataset, setProcessingDataset, onClose, onProcessingStart]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    },
    multiple: true,
    disabled: uploading || uploadType !== 'file'
  });

  const handleGoogleSheets = () => {
    toast.error('Google Sheets integration coming soon!');
  };

  const handleSQLDatabase = () => {
    toast.error('SQL Database integration coming soon!');
  };

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[60] overflow-y-auto">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0"
            style={{ backgroundColor: 'var(--bg-overlay)' }}
            onClick={!uploading ? onClose : undefined}
          />

          <div className="flex min-h-full items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="relative transform overflow-hidden rounded-2xl w-full max-w-2xl"
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-lg)',
              }}
            >
              <div 
                className="flex items-center justify-between p-6"
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <div className="flex items-center gap-3">
                  <div 
                    className="p-2 rounded-lg"
                    style={{ backgroundColor: 'var(--accent-primary-light)' }}
                  >
                    <Upload className="h-6 w-6" style={{ color: 'var(--accent-primary)' }} />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold" style={{ color: 'var(--text-header)' }}>Upload Data</h3>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Choose how you'd like to add your data</p>
                  </div>
                </div>
                {!uploading && (
                  <button
                    onClick={onClose}
                    className="p-2 rounded-lg transition-colors"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    <X className="h-5 w-5" />
                  </button>
                )}
              </div>

              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setUploadType('file')}
                    className="p-4 rounded-xl border-2 transition-all duration-200"
                    style={{
                      borderColor: uploadType === 'file' ? 'var(--accent-primary)' : 'var(--border)',
                      backgroundColor: uploadType === 'file' ? 'var(--accent-primary-light)' : 'transparent',
                    }}
                  >
                    <div className="text-center">
                      <div 
                        className="p-3 rounded-lg mx-auto mb-3"
                        style={{ backgroundColor: uploadType === 'file' ? 'var(--accent-primary-light)' : 'var(--bg-elevated)' }}
                      >
                        <FileText 
                          className="h-6 w-6" 
                          style={{ color: uploadType === 'file' ? 'var(--accent-primary)' : 'var(--text-secondary)' }} 
                        />
                      </div>
                      <h4 className="font-medium mb-1" style={{ color: 'var(--text-header)' }}>File Upload</h4>
                      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>CSV, Excel files</p>
                    </div>
                  </motion.button>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleGoogleSheets}
                    disabled
                    className="p-4 rounded-xl border-2 cursor-not-allowed opacity-60"
                    style={{ 
                      borderColor: 'var(--border)',
                      backgroundColor: 'var(--bg-elevated)',
                    }}
                  >
                    <div className="text-center">
                      <div 
                        className="p-3 rounded-lg mx-auto mb-3"
                        style={{ backgroundColor: 'var(--bg-surface)' }}
                      >
                        <Cloud className="h-6 w-6" style={{ color: 'var(--text-muted)' }} />
                      </div>
                      <h4 className="font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Google Sheets</h4>
                      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Coming Soon</p>
                      <div className="mt-2 flex items-center justify-center gap-1">
                        <AlertCircle className="h-3 w-3" style={{ color: 'var(--text-muted)' }} />
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Disabled</span>
                      </div>
                    </div>
                  </motion.button>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleSQLDatabase}
                    disabled
                    className="p-4 rounded-xl border-2 cursor-not-allowed opacity-60"
                    style={{ 
                      borderColor: 'var(--border)',
                      backgroundColor: 'var(--bg-elevated)',
                    }}
                  >
                    <div className="text-center">
                      <div 
                        className="p-3 rounded-lg mx-auto mb-3"
                        style={{ backgroundColor: 'var(--bg-surface)' }}
                      >
                        <Server className="h-6 w-6" style={{ color: 'var(--text-muted)' }} />
                      </div>
                      <h4 className="font-medium mb-1" style={{ color: 'var(--text-muted)' }}>SQL Database</h4>
                      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Coming Soon</p>
                      <div className="mt-2 flex items-center justify-center gap-1">
                        <AlertCircle className="h-3 w-3" style={{ color: 'var(--text-muted)' }} />
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Disabled</span>
                      </div>
                    </div>
                  </motion.button>
                </div>

                {uploadType === 'file' && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                  >
                    <div
                      {...getRootProps()}
                      className="border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 cursor-pointer"
                      style={{
                        borderColor: isDragActive ? 'var(--accent-primary)' : 'var(--border)',
                        backgroundColor: isDragActive ? 'var(--accent-primary-light)' : 'transparent',
                        transform: isDragActive ? 'scale(1.02)' : 'scale(1)',
                      }}
                    >
                      <input {...getInputProps()} />

                      <div className="space-y-4">
                        <motion.div
                          className="flex justify-center"
                          animate={{ scale: isDragActive ? 1.1 : 1 }}
                          transition={{ duration: 0.2 }}
                        >
                          <div 
                            className="p-4 rounded-full transition-all duration-200"
                            style={{ 
                              backgroundColor: isDragActive ? 'rgba(47,128,237,0.3)' : 'var(--accent-primary-light)',
                              transform: isDragActive ? 'scale(1.1)' : 'scale(1)',
                            }}
                          >
                            <Upload 
                              className="h-8 w-8" 
                              style={{ color: 'var(--accent-primary)' }} 
                            />
                          </div>
                        </motion.div>

                        <div>
                          <h4 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-header)' }}>
                            {isDragActive ? 'Drop files here' : 'Upload your datasets'}
                          </h4>
                          <p className="mb-4" style={{ color: 'var(--text-secondary)' }}>
                            Drag and drop CSV or Excel files, or click to browse
                          </p>

                          <div className="flex items-center justify-center gap-6 text-sm" style={{ color: 'var(--text-muted)' }}>
                            <div className="flex items-center gap-2">
                              <FileText className="h-4 w-4" />
                              <span>CSV</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <FileSpreadsheet className="h-4 w-4" />
                              <span>Excel</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Database className="h-4 w-4" />
                              <span>Up to 100MB</span>
                            </div>
                          </div>
                        </div>

                        {uploading && (
                          <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="space-y-3"
                          >
                            <div 
                              className="w-full rounded-full h-2"
                              style={{ backgroundColor: 'var(--border)' }}
                            >
                              <motion.div
                                className="h-2 rounded-full transition-all duration-300 ease-out"
                                style={{ backgroundColor: 'var(--accent-primary)' }}
                                initial={{ width: 0 }}
                                animate={{ width: `${uploadProgress}%` }}
                                transition={{ duration: 0.3 }}
                              />
                            </div>
                            <div 
                              className="flex items-center justify-center gap-2"
                              style={{ color: 'var(--accent-primary)' }}
                            >
                              <motion.div
                                className="rounded-full h-4 w-4 border-2"
                                style={{ borderColor: 'var(--accent-primary)' }}
                                animate={{ rotate: 360 }}
                                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                              />
                              <span className="text-sm font-medium">Uploading... {uploadProgress}%</span>
                            </div>
                          </motion.div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}

                {uploadProgress === 100 && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="text-center py-4"
                  >
                    <div 
                      className="flex items-center justify-center gap-2 mb-2"
                      style={{ color: 'var(--accent-success)' }}
                    >
                      <CheckCircle className="h-5 w-5" />
                      <span className="font-medium">Upload Complete!</span>
                    </div>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Your data is being processed...</p>
                  </motion.div>
                )}

                {/* Privacy Notice */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="mt-6 p-4 rounded-xl border"
                  style={{
                    backgroundColor: 'var(--bg-elevated)',
                    borderColor: 'var(--border)',
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div 
                      className="p-2 rounded-lg flex-shrink-0"
                      style={{ backgroundColor: 'rgba(139,92,246,0.1)' }}
                    >
                      <Shield className="h-5 w-5" style={{ color: 'rgb(139,92,246)' }} />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium mb-1" style={{ color: 'var(--text-header)' }}>
                        Privacy Notice
                      </h4>
                      <p className="text-sm mb-3" style={{ color: 'var(--text-secondary)' }}>
                        Your data is processed by AI models to provide insights. Sensitive information 
                        like emails, phone numbers, and other PII can be automatically detected and redacted 
                        for your protection.
                      </p>
                      <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                        <div className="flex items-center gap-1.5">
                          <Eye className="h-3.5 w-3.5" />
                          <span>Column names shared with AI</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <Shield className="h-3.5 w-3.5" />
                          <span>PII auto-detection enabled</span>
                        </div>
                      </div>
                      <a
                        href="/app/settings"
                        className="inline-flex items-center gap-1 mt-2 text-sm font-medium transition-colors"
                        style={{ color: 'var(--accent-primary)' }}
                        onClick={(e) => {
                          e.preventDefault();
                          onClose();
                          window.location.href = '/app/settings';
                        }}
                      >
                        Configure privacy settings
                        <span className="ml-1">→</span>
                      </a>
                    </div>
                  </div>
                </motion.div>
              </div>

              <div 
                className="flex items-center justify-end gap-3 p-6"
                style={{ 
                  borderTop: '1px solid var(--border)',
                  backgroundColor: 'var(--bg-elevated)',
                }}
              >
                {!uploading && (
                  <button
                    onClick={onClose}
                    className="px-4 py-2 text-sm font-medium rounded-lg transition-colors"
                    style={{ 
                      backgroundColor: 'var(--bg-surface)',
                      color: 'var(--text-secondary)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </motion.div>
          </div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default UploadModal;
