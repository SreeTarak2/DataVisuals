import React from 'react';
import { TrendingUp, TrendingDown, Minus, HelpCircle } from 'lucide-react';

const KPIWidget = ({ 
  title, 
  value, 
  change, 
  changeType = 'neutral', // 'positive', 'negative', 'neutral'
  icon: Icon,
  subtitle,
  loading = false,
  tooltip
}) => {

  // Skeleton Loader
  if (loading) {
    return (
      <div className="card p-5 flex items-start justify-between">
        <div className="space-y-3 w-full">
          <div className="h-4 rounded bg-bg-tertiary shimmer" style={{ width: '50%' }}></div>
          <div className="h-8 rounded bg-bg-tertiary shimmer" style={{ width: '70%' }}></div>
          <div className="h-3 rounded bg-bg-tertiary shimmer" style={{ width: '40%' }}></div>
        </div>
        <div className="w-10 h-10 rounded-lg bg-bg-tertiary shimmer"></div>
      </div>
    );
  }

  // Format value (add commas for large numbers if it's a number)
  const formattedValue = typeof value === 'number' 
    ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 2, notation: 'compact' }).format(value)
    : value;

  // Logic for change indicator
  let ChangeIcon = Minus;
  let changeColorClass = 'text-text-secondary';
  let changeBgClass = 'bg-bg-tertiary';

  if (changeType === 'positive') {
    ChangeIcon = TrendingUp;
    changeColorClass = 'text-green-600 dark:text-green-400';
    changeBgClass = 'bg-green-50 dark:bg-green-900/20';
  } else if (changeType === 'negative') {
    ChangeIcon = TrendingDown;
    changeColorClass = 'text-red-600 dark:text-red-400';
    changeBgClass = 'bg-red-50 dark:bg-red-900/20';
  }

  return (
    <div className="card p-5 relative group hover:shadow-lg transition-shadow duration-200">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          {/* Title with optional tooltip */}
          <div className="flex items-center gap-1">
            <p className="text-sm font-medium text-text-secondary truncate">
              {title}
            </p>
            {tooltip && (
              <div className="relative group/tooltip cursor-help">
                <HelpCircle className="w-3.5 h-3.5 text-text-muted" />
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 text-xs text-white bg-gray-800 rounded opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                  {tooltip}
                </div>
              </div>
            )}
          </div>
          
          {/* Main Value */}
          <h3 className="text-3xl font-bold text-text-primary tracking-tight">
            {formattedValue}
          </h3>
        </div>

        {/* Icon Container */}
        <div className={`p-2.5 rounded-xl bg-brand-primary bg-opacity-10`}>
          {Icon ? (
            <Icon className="w-5 h-5 text-brand-primary" />
          ) : (
            // Fallback icon if none provided
            <svg className="w-5 h-5 text-brand-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          )}
        </div>
      </div>

      {/* Footer: Subtitle and Change Indicator */}
      <div className="mt-4 flex items-center justify-between">
        {subtitle && (
          <p className="text-xs text-text-muted truncate max-w-[60%]">
            {subtitle}
          </p>
        )}
        
        {change !== undefined && change !== null && (
          <div className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${changeBgClass} ${changeColorClass}`}>
            <ChangeIcon className="w-3 h-3 mr-1" />
            {change}
          </div>
        )}
      </div>
    </div>
  );
};

export default KPIWidget;
