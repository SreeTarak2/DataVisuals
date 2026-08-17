import React, { useState, useCallback, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  Upload,
  FileText,
  X,
  ArrowRight,
  Database
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import useDatasetStore from '../../../store/datasetStore';
import { useTheme } from '../../../store/themeStore';
import { toast } from 'react-hot-toast';
import ConnectDatabaseModal from '../databases/ConnectDatabaseModal';

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

const UploadModal = ({ isOpen, onClose, onProcessingStart, fileOnly = true }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDbModalOpen, setIsDbModalOpen] = useState(false);
  const [stagedFile, setStagedFile] = useState(null);
  const progressRef = useRef(null);
  const { uploadDataset, setProcessingDataset } = useDatasetStore();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;
    setStagedFile(file);
  }, []);

  const handleAnalyze = useCallback(async () => {
    if (!stagedFile) return;
    const currentFile = stagedFile;
    setUploading(true);
    setUploadProgress(0);
    setStagedFile(null);

    try {
      progressRef.current = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 120);

      const result = await uploadDataset(currentFile, currentFile.name);

      clearInterval(progressRef.current);
      progressRef.current = null;
      setUploadProgress(100);

      if (result.success) {
        const datasetId = result.dataset?.id || result.dataset?._id;
        if (datasetId) {
          setProcessingDataset(datasetId);
          if (onProcessingStart) onProcessingStart(datasetId);
          toast.success(`${currentFile.name} uploaded successfully.`);
          setTimeout(() => {
            setUploadProgress(0);
            setUploading(false);
            onClose();
          }, 600);
        }
      } else if (result.isDuplicate) {
        const existingId = result.existingDataset?.id;
        setUploadProgress(0);
        setUploading(false);
        if (existingId) {
          setProcessingDataset(existingId);
          if (onProcessingStart) onProcessingStart(existingId);
          setTimeout(() => {
            onClose();
          }, 600);
        } else {
          onClose();
        }
      } else {
        const errMsg = result?.error || 'Upload failed';
        toast.error(errMsg);
        setUploadProgress(0);
        setUploading(false);
        setStagedFile(currentFile);
      }
    } catch (error) {
      if (progressRef.current) {
        clearInterval(progressRef.current);
        progressRef.current = null;
      }
      toast.error('Upload failed. Please try again.');
      setUploading(false);
      setStagedFile(currentFile);
    }
  }, [stagedFile, uploadDataset, setProcessingDataset, onClose, onProcessingStart]);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    return () => {
      if (progressRef.current) {
        clearInterval(progressRef.current);
        progressRef.current = null;
      }
    };
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    },
    multiple: false,
    disabled: uploading || !!stagedFile
  });

  const uploadPortal = createPortal(
    <AnimatePresence>
      {isOpen && !isDbModalOpen && (
        <div 
          className="fixed inset-0 z-[150] flex items-center justify-center p-4 backdrop-blur-md bg-black/60"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.98, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 8 }}
            className={`relative w-full max-w-xl border shadow-2xl rounded-xl p-6 md:p-8 overflow-hidden transition-all duration-300 ${
              isDark 
                ? 'bg-[#0B0C0E] border-zinc-800/80 shadow-[0_0_50px_rgba(0,0,0,0.8)]' 
                : 'bg-white border-zinc-200 shadow-[0_0_50px_rgba(0,0,0,0.05)]'
            }`}
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between mb-6">
              <div>
                <h3 className={`text-lg font-semibold tracking-tight ${isDark ? 'text-zinc-100' : 'text-zinc-900'}`}>
                  Upload dataset
                </h3>
                <p className={`text-xs mt-1 leading-relaxed ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
                  Select a CSV or Excel file to begin your analysis. Your data is encrypted and secure.
                </p>
              </div>
              <button 
                onClick={onClose}
                className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                  isDark ? 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900' : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'
                }`}
                aria-label="Close modal"
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex flex-col">
              {uploading ? (
                /* Progress Monitor */
                <div className="py-6">
                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-xs font-medium ${isDark ? 'text-zinc-400' : 'text-zinc-600'}`}>
                      Uploading and analyzing dataset...
                    </span>
                    <span className={`text-xs font-semibold ${isDark ? 'text-zinc-300' : 'text-zinc-800'}`}>
                      {uploadProgress}%
                    </span>
                  </div>
                  <div className={`w-full h-1 rounded-full overflow-hidden ${isDark ? 'bg-zinc-800' : 'bg-zinc-100'}`}>
                    <motion.div 
                      className="bg-orange-500 h-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${uploadProgress}%` }}
                      transition={{ ease: "easeOut", duration: 0.5 }}
                    />
                  </div>
                </div>
              ) : !stagedFile ? (
                /* Drag-and-Drop Area */
                <div
                  {...getRootProps()}
                  className={`flex flex-col items-center justify-center p-8 md:p-12 border-2 border-dashed rounded-lg transition-all duration-200 cursor-pointer ${
                    isDragActive 
                      ? 'border-orange-500 bg-orange-500/[0.01]' 
                      : isDark 
                        ? 'border-zinc-800 bg-zinc-900/[0.15] hover:border-zinc-700 hover:bg-zinc-900/[0.25]' 
                        : 'border-zinc-200 bg-zinc-50/50 hover:border-zinc-300 hover:bg-zinc-50'
                  }`}
                >
                  <input {...getInputProps()} />
                  
                  <div className={`p-3 rounded-lg border mb-4 ${
                    isDark ? 'bg-zinc-900 border-zinc-800 text-zinc-400' : 'bg-white border-zinc-200 text-zinc-500'
                  }`}>
                    <Upload size={20} />
                  </div>
                  
                  <h4 className={`text-sm font-medium mb-1 ${
                    isDark ? 'text-zinc-200' : 'text-zinc-700'
                  }`}>
                    {isDragActive ? 'Drop your file here' : 'Click to upload or drag and drop'}
                  </h4>
                  <p className={`text-xs ${
                    isDark ? 'text-zinc-500' : 'text-zinc-400'
                  }`}>
                    CSV, XLS, or XLSX up to 256MB
                  </p>
                </div>
              ) : (
                /* Staged File Details & Custom Intent Select */
                <div className="space-y-6">
                  {/* File preview */}
                  <div className={`flex items-center gap-3 p-4 border rounded-lg ${
                    isDark ? 'bg-zinc-900/10 border-zinc-800/80' : 'bg-zinc-50/30 border-zinc-200'
                  }`}>
                    <div className={`p-2.5 rounded-lg border ${
                      isDark ? 'bg-zinc-900 border-zinc-800 text-orange-500' : 'bg-white border-zinc-200 text-orange-600'
                    }`}>
                      <FileText size={18} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm font-medium truncate ${isDark ? 'text-zinc-200' : 'text-zinc-800'}`}>
                        {stagedFile.name}
                      </p>
                      <p className={`text-xs mt-0.5 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                        {formatFileSize(stagedFile.size)}
                      </p>
                    </div>
                    <button
                      onClick={() => setStagedFile(null)}
                      className={`text-xs font-medium px-3 py-1.5 border rounded-md transition-colors cursor-pointer ${
                        isDark 
                          ? 'text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:bg-zinc-900' 
                          : 'text-zinc-600 border-zinc-200 hover:text-zinc-900 hover:bg-zinc-100'
                      }`}
                    >
                      Change
                    </button>
                  </div>



                  {/* Action Button */}
                  <div className="pt-2">
                    <button
                      onClick={handleAnalyze}
                      disabled={uploading}
                      className={`w-full py-2.5 px-4 text-sm font-semibold rounded-lg transition-all duration-200 cursor-pointer flex items-center justify-center gap-2 ${
                        isDark
                          ? 'bg-orange-500 hover:bg-orange-600 text-white shadow-lg shadow-orange-950/20'
                          : 'bg-zinc-950 hover:bg-zinc-900 text-white shadow-sm'
                      } disabled:opacity-40 disabled:cursor-not-allowed`}
                    >
                      {uploading ? 'Processing...' : (
                        <>
                          Analyze dataset
                          <ArrowRight size={14} />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}

              {/* Database Connect (Secondary Option) */}
              {!fileOnly && !uploading && (
                <div className={`mt-6 pt-5 border-t text-center ${isDark ? 'border-zinc-900' : 'border-zinc-100'}`}>
                  <button
                    onClick={() => setIsDbModalOpen(true)}
                    className={`inline-flex items-center gap-1.5 text-xs font-medium transition-colors cursor-pointer ${
                      isDark ? 'text-zinc-400 hover:text-orange-500' : 'text-zinc-500 hover:text-orange-600'
                    }`}
                  >
                    <Database size={13} />
                    Connect a database instead
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );

  return (
    <>
      {uploadPortal}
      <ConnectDatabaseModal
        isOpen={isDbModalOpen}
        onClose={() => setIsDbModalOpen(false)}
        onProcessingStart={onProcessingStart}
        onBack={() => setIsDbModalOpen(false)}
      />
    </>
  );
};

export default UploadModal;
