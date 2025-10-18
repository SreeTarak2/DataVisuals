import React, { useEffect } from 'react';
import { X, AlertTriangle } from 'lucide-react';

const ModernModal = ({
  isOpen = false,
  onClose,
  title,
  children,
  size = 'medium', // 'small', 'medium', 'large', 'full'
  showCloseButton = true,
  closeOnOverlayClick = true,
  className = ''
}) => {
  const sizeClasses = {
    small: 'max-w-md',
    medium: 'max-w-2xl',
    large: 'max-w-4xl',
    full: 'max-w-full mx-4'
  };

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose?.();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleOverlayClick = (e) => {
    if (closeOnOverlayClick && e.target === e.currentTarget) {
      onClose?.();
    }
  };

  return (
    <div 
      className="modal-overlay"
      onClick={handleOverlayClick}
    >
      <div 
        className={`modal-content ${sizeClasses[size]} ${className}`}
        style={{
          maxHeight: size === 'full' ? 'calc(100vh - 2rem)' : '90vh'
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              {title}
            </h2>
          </div>
          
          {showCloseButton && (
            <button
              onClick={onClose}
              className="p-2 rounded-lg transition-colors duration-200 hover:bg-hover"
              style={{ color: 'var(--text-secondary)' }}
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
};

// Confirmation Modal Component
export const ConfirmationModal = ({
  isOpen,
  onClose,
  onConfirm,
  title = 'Confirm Action',
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  type = 'warning', // 'warning', 'danger', 'info'
  loading = false
}) => {
  const getTypeConfig = () => {
    switch (type) {
      case 'danger':
        return {
          iconColor: '#FF6B6B',
          confirmBgColor: '#FF6B6B',
          confirmTextColor: 'white'
        };
      case 'info':
        return {
          iconColor: 'var(--accent-blue)',
          confirmBgColor: 'var(--accent-blue)',
          confirmTextColor: 'white'
        };
      default:
        return {
          iconColor: '#FFA726',
          confirmBgColor: '#FFA726',
          confirmTextColor: 'var(--bg-primary)'
        };
    }
  };

  const config = getTypeConfig();

  return (
    <ModernModal isOpen={isOpen} onClose={onClose} size="small" title={title}>
      <div className="text-center">
        <div 
          className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center"
          style={{ backgroundColor: `${config.iconColor}20` }}
        >
          <AlertTriangle 
            className="w-8 h-8" 
            style={{ color: config.iconColor }} 
          />
        </div>
        
        <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
          {message}
        </p>
        
        <div className="flex space-x-3 justify-center">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-6 py-2 rounded-lg transition-colors duration-200 btn-secondary"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-6 py-2 rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: config.confirmBgColor,
              color: config.confirmTextColor
            }}
          >
            {loading ? 'Processing...' : confirmText}
          </button>
        </div>
      </div>
    </ModernModal>
  );
};

export default ModernModal;

