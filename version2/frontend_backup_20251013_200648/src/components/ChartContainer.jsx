import React from 'react';
import { RefreshCw, Maximize2, Download, Settings, AlertTriangle } from 'lucide-react';
import ModernCard from './ModernCard';
import LoadingSpinner from './LoadingSpinner';

const ChartContainer = ({ 
  title, 
  subtitle, 
  children, 
  loading = false,
  error = null,
  onRefresh,
  onExport,
  onSettings,
  className = '',
  height = '400px' // Default height for the chart area
}) => {

  const headerActions = [
    onRefresh && { icon: RefreshCw, label: 'Refresh', onClick: onRefresh },
    { icon: Maximize2, label: 'Fullscreen', onClick: () => console.log('Fullscreen') },
    onExport && { icon: Download, label: 'Export', onClick: onExport },
    onSettings && { icon: Settings, label: 'Settings', onClick: onSettings },
  ].filter(Boolean); // Filter out any undefined actions

  // Render Skeleton/Loading State
  if (loading) {
    return (
      <ModernCard
        title={title}
        subtitle={subtitle}
        className={className}
        headerActions={true}
      >
        <div 
          className="flex items-center justify-center w-full"
          style={{ height }}
        >
          <LoadingSpinner text="Rendering chart..." />
        </div>
      </ModernCard>
    );
  }

  // Render Error State
  if (error) {
    return (
      <ModernCard
        title={title}
        subtitle="Data Visualization"
        className={className}
        headerActions={true}
      >
        <div 
          className="flex flex-col items-center justify-center text-center w-full" 
          style={{ height }}
        >
          <div 
            className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
            style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)' }}
          >
            <AlertTriangle className="w-6 h-6 text-color-danger" />
          </div>
          <h4 className="font-semibold text-text-primary mb-1">
            Chart Error
          </h4>
          <p className="text-sm text-text-secondary max-w-xs mb-4">
            {typeof error === 'string' ? error : 'An unexpected error occurred while rendering this chart.'}
          </p>
          {onRefresh && (
            <button 
              onClick={onRefresh}
              className="btn btn-secondary text-sm"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </button>
          )}
        </div>
      </ModernCard>
    );
  }

  // Render Chart Content
  return (
    <ModernCard
      title={title}
      subtitle={subtitle}
      className={`flex flex-col ${className}`}
      actions={headerActions}
      headerActions={true}
    >
      <div className="flex-1" style={{ minHeight: height }}>
        {children}
      </div>
    </ModernCard>
  );
};

export default ChartContainer;
