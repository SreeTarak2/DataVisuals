import React from 'react';
import { CheckCircle, AlertCircle, Info, X, XCircle } from 'lucide-react';

const ModernToast = ({ 
  type = 'info', // 'success', 'error', 'warning', 'info'
  title, 
  message, 
  onClose,
  duration = 5000,
  show = true 
}) => {
  const getToastConfig = () => {
    switch (type) {
      case 'success':
        return {
          icon: CheckCircle,
          bgColor: 'var(--accent-teal)',
          textColor: 'var(--bg-primary)',
          iconColor: 'var(--bg-primary)'
        };
      case 'error':
        return {
          icon: XCircle,
          bgColor: '#FF6B6B',
          textColor: 'white',
          iconColor: 'white'
        };
      case 'warning':
        return {
          icon: AlertCircle,
          bgColor: '#FFA726',
          textColor: 'var(--bg-primary)',
          iconColor: 'var(--bg-primary)'
        };
      default:
        return {
          icon: Info,
          bgColor: 'var(--accent-blue)',
          textColor: 'white',
          iconColor: 'white'
        };
    }
  };

  const config = getToastConfig();
  const Icon = config.icon;

  React.useEffect(() => {
    if (duration > 0 && show) {
      const timer = setTimeout(() => {
        onClose?.();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, show, onClose]);

  if (!show) return null;

  return (
    <div 
      className="fixed top-4 right-4 z-50 max-w-sm w-full transform transition-all duration-300 ease-in-out"
      style={{
        backgroundColor: config.bgColor,
        color: config.textColor,
        borderRadius: 'var(--radius-md)',
        boxShadow: 'var(--shadow-heavy)',
        border: '1px solid rgba(255, 255, 255, 0.1)'
      }}
    >
      <div className="flex items-start p-4">
        <div className="flex-shrink-0 mr-3">
          <Icon className="w-5 h-5" style={{ color: config.iconColor }} />
        </div>
        
        <div className="flex-1 min-w-0">
          {title && (
            <h4 className="text-sm font-semibold mb-1">
              {title}
            </h4>
          )}
          {message && (
            <p className="text-sm opacity-90">
              {message}
            </p>
          )}
        </div>
        
        {onClose && (
          <button
            onClick={onClose}
            className="flex-shrink-0 ml-3 p-1 rounded-full transition-colors duration-200 hover:bg-black hover:bg-opacity-10"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
      
      {/* Progress bar */}
      {duration > 0 && (
        <div className="h-1 bg-black bg-opacity-20 rounded-b-md overflow-hidden">
          <div 
            className="h-full bg-white bg-opacity-30 transition-all ease-linear"
            style={{
              animation: `toast-progress ${duration}ms linear forwards`
            }}
          />
        </div>
      )}
    </div>
  );
};

export default ModernToast;

