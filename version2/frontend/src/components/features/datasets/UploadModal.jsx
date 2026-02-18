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
  AlertCircle
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import GlassCard from '../../common/GlassCard';
import useDatasetStore from '../../../store/datasetStore';
import { toast } from 'react-hot-toast';

const UploadModal = ({ isOpen, onClose }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadType, setUploadType] = useState('file');
  const [uploadProgress, setUploadProgress] = useState(0);
  const { uploadDataset } = useDatasetStore();

  const onDrop = useCallback(async (acceptedFiles) => {
    setUploading(true);
    setUploadProgress(0);

    try {
      for (const file of acceptedFiles) {
        // Simulate progress
        const progressInterval = setInterval(() => {
          setUploadProgress(prev => Math.min(prev + 10, 90));
        }, 200);

        const result = await uploadDataset(file, file.name, '');

        clearInterval(progressInterval);
        setUploadProgress(100);

        if (result.success) {
          toast.success(`${file.name} uploaded successfully!`);

          // Reset progress after a short delay
          setTimeout(() => {
            setUploadProgress(0);
            setUploading(false);
            onClose();
          }, 1000);
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
  }, [uploadDataset, onClose]);

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
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity duration-300"
            onClick={!uploading ? onClose : undefined}
          />

          {/* Modal */}
          <div className="flex min-h-full items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="relative transform overflow-hidden rounded-2xl bg-white shadow-2xl transition-all duration-300 scale-100 opacity-100 w-full max-w-2xl"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-gray-200">
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-primary/20">
                    <Upload className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900">Upload Data</h3>
                    <p className="text-sm text-gray-500">Choose how you'd like to add your data</p>
                  </div>
                </div>
                {!uploading && (
                  <button
                    onClick={onClose}
                    className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <X className="h-5 w-5" />
                  </button>
                )}
              </div>

              {/* Content */}
              <div className="p-6">
                {/* Upload Type Selector */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  {/* File Upload */}
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setUploadType('file')}
                    className={`p-4 rounded-xl border-2 transition-all duration-200 ${uploadType === 'file'
                        ? 'border-primary bg-primary/10 shadow-md'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                      }`}
                  >
                    <div className="text-center">
                      <div className={`p-3 rounded-lg mx-auto mb-3 ${uploadType === 'file' ? 'bg-primary/20' : 'bg-gray-100'
                        }`}>
                        <FileText className={`h-6 w-6 ${uploadType === 'file' ? 'text-primary' : 'text-gray-600'
                          }`} />
                      </div>
                      <h4 className="font-medium text-gray-900 mb-1">File Upload</h4>
                      <p className="text-sm text-gray-500">CSV, Excel files</p>
                    </div>
                  </motion.button>

                  {/* Google Sheets */}
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
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
                  </motion.button>

                  {/* SQL Database */}
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
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
                  </motion.button>
                </div>

                {/* File Upload Area */}
                {uploadType === 'file' && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                  >
                    <div
                      {...getRootProps()}
                      className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${isDragActive
                          ? 'border-primary bg-primary/10 scale-105'
                          : 'border-gray-300 hover:border-primary hover:bg-primary/5'
                        } ${uploading ? 'pointer-events-none' : 'cursor-pointer'}`}
                    >
                      <input {...getInputProps()} />

                      <div className="space-y-4">
                        <motion.div
                          className="flex justify-center"
                          animate={{ scale: isDragActive ? 1.1 : 1 }}
                          transition={{ duration: 0.2 }}
                        >
                          <div className={`p-4 rounded-full transition-all duration-200 ${isDragActive ? 'bg-primary/30 scale-110' : 'bg-primary/20'
                            }`}>
                            <Upload className={`h-8 w-8 transition-colors duration-200 ${isDragActive ? 'text-primary' : 'text-primary'
                              }`} />
                          </div>
                        </motion.div>

                        <div>
                          <h4 className="text-lg font-semibold text-gray-900 mb-2">
                            {isDragActive ? 'Drop files here' : 'Upload your datasets'}
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
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <motion.div
                                className="bg-primary h-2 rounded-full transition-all duration-300 ease-out"
                                initial={{ width: 0 }}
                                animate={{ width: `${uploadProgress}%` }}
                                transition={{ duration: 0.3 }}
                              />
                            </div>
                            <div className="flex items-center justify-center space-x-2 text-primary">
                              <motion.div
                                className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"
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

                {/* Upload Success */}
                {uploadProgress === 100 && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="text-center py-4"
                  >
                    <div className="flex items-center justify-center space-x-2 text-green-600 mb-2">
                      <CheckCircle className="h-5 w-5" />
                      <span className="font-medium">Upload Complete!</span>
                    </div>
                    <p className="text-sm text-gray-500">Your data is being processed...</p>
                  </motion.div>
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200 bg-gray-50">
                {!uploading && (
                  <button
                    onClick={onClose}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
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