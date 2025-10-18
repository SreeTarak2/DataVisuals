import React from 'react';
import { Loader2 } from 'lucide-react';

const LoadingSpinner = ({ 
  size = 'medium', // 'small', 'medium', 'large'
  color = 'var(--accent-blue)',
  text,
  className = ''
}) => {
  const sizeClasses = {
    small: 'w-4 h-4',
    medium: 'w-6 h-6',
    large: 'w-8 h-8'
  };

  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="flex flex-col items-center space-y-3">
        <Loader2 
          className={`loading-spin ${sizeClasses[size]}`}
          style={{ color }}
        />
        {text && (
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {text}
          </p>
        )}
      </div>
    </div>
  );
};

// Full page loading overlay
export const LoadingOverlay = ({ 
  isVisible = false, 
  text = 'Loading...',
  backgroundColor = 'rgba(18, 18, 18, 0.8)'
}) => {
  if (!isVisible) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor }}
    >
      <div className="text-center">
        <Loader2 
          className="w-12 h-12 loading-spin mx-auto mb-4"
          style={{ color: 'var(--accent-blue)' }}
        />
        <p className="text-lg" style={{ color: 'var(--text-primary)' }}>
          {text}
        </p>
      </div>
    </div>
  );
};

// Skeleton loading components
export const SkeletonCard = () => (
  <div className="card animate-pulse">
    <div className="flex items-center justify-between mb-4">
      <div>
        <div className="h-5 bg-gray-300 rounded mb-2" style={{ width: '60%', backgroundColor: 'var(--text-muted)' }}></div>
        <div className="h-3 bg-gray-300 rounded" style={{ width: '40%', backgroundColor: 'var(--text-muted)' }}></div>
      </div>
      <div className="w-8 h-8 rounded" style={{ backgroundColor: 'var(--text-muted)' }}></div>
    </div>
    <div className="space-y-3">
      <div className="h-4 bg-gray-300 rounded" style={{ backgroundColor: 'var(--text-muted)' }}></div>
      <div className="h-4 bg-gray-300 rounded" style={{ width: '80%', backgroundColor: 'var(--text-muted)' }}></div>
      <div className="h-4 bg-gray-300 rounded" style={{ width: '60%', backgroundColor: 'var(--text-muted)' }}></div>
    </div>
  </div>
);

export const SkeletonTable = ({ rows = 5, columns = 4 }) => (
  <div className="card">
    <div className="overflow-hidden">
      <table className="w-full">
        <thead>
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="p-3 text-left">
                <div 
                  className="h-4 bg-gray-300 rounded animate-pulse"
                  style={{ backgroundColor: 'var(--text-muted)' }}
                ></div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <tr key={i}>
              {Array.from({ length: columns }).map((_, j) => (
                <td key={j} className="p-3">
                  <div 
                    className="h-4 bg-gray-300 rounded animate-pulse"
                    style={{ 
                      backgroundColor: 'var(--text-muted)',
                      width: j === 0 ? '80%' : '60%'
                    }}
                  ></div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

export default LoadingSpinner;

