import React from 'react';
import { AlertTriangle } from 'lucide-react';
import ModernModal from './ModernModal';

const DeleteConfirmModal = ({
  isOpen,
  onClose,
  onConfirm,
  title = 'Confirm Deletion',
  message = 'Are you sure you want to proceed? This action cannot be undone.',
  loading = false
}) => {
  if (!isOpen) return null;

  return (
    <ModernModal isOpen={isOpen} onClose={onClose} size="small" title={title}>
      <div className="text-center">
        <div 
          className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center bg-red-100 dark:bg-red-900/20"
        >
          <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
        </div>
        
        <p className="text-sm text-text-secondary mb-8">
          {message}
        </p>
        
        <div className="flex justify-center gap-x-4">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="btn btn-secondary w-full"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="btn w-full bg-color-danger text-white hover:bg-red-700 focus-visible:shadow-[0_0_0_3px_rgba(239,68,68,0.2)]"
          >
            {loading ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </ModernModal>
  );
};

export default DeleteConfirmModal;