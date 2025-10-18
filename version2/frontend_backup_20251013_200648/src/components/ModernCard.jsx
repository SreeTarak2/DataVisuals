import React, { useState, Fragment } from 'react';
import { MoreVertical, Download, Share2, Edit3, Trash2 } from 'lucide-react';

const ModernCard = ({ 
  title, 
  subtitle, 
  children, 
  actions,
  loading = false,
  className = '',
  headerActions = true 
}) => {
  const [menuOpen, setMenuOpen] = useState(false);

  const defaultActions = [
    { icon: Edit3, label: 'Edit', onClick: () => console.log('Edit clicked') },
    { icon: Share2, label: 'Share', onClick: () => console.log('Share clicked') },
    { icon: Download, label: 'Export', onClick: () => console.log('Export clicked') },
    { icon: Trash2, label: 'Delete', onClick: () => console.log('Delete clicked'), destructive: true }
  ];

  const cardActions = actions || (headerActions ? defaultActions : []);

  // Skeleton Loader
  if (loading) {
    return (
      <div className={`card ${className}`}>
        <div className="card-header flex items-center justify-between">
          <div className="w-3/4">
            <div className="h-5 rounded bg-bg-tertiary shimmer mb-2" style={{ width: '60%' }}></div>
            <div className="h-4 rounded bg-bg-tertiary shimmer" style={{ width: '40%' }}></div>
          </div>
          {headerActions && <div className="w-6 h-6 rounded-md bg-bg-tertiary shimmer"></div>}
        </div>
        <div className="space-y-3 pt-4">
          <div className="h-4 rounded bg-bg-tertiary shimmer"></div>
          <div className="h-4 rounded bg-bg-tertiary shimmer" style={{ width: '80%' }}></div>
          <div className="h-4 rounded bg-bg-tertiary shimmer" style={{ width: '90%' }}></div>
        </div>
      </div>
    );
  }

  return (
    <div className={`card flex flex-col ${className}`}>
      {/* Card Header */}
      {(title || headerActions) && (
        <div className="card-header flex items-start justify-between">
          <div>
            {title && <h3 className="card-title">{title}</h3>}
            {subtitle && <p className="card-subtitle">{subtitle}</p>}
          </div>
          
          {headerActions && cardActions.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                onBlur={() => setTimeout(() => setMenuOpen(false), 150)} // Close on blur with delay
                className="p-2 rounded-md transition-colors duration-200 text-text-secondary hover:bg-bg-hover hover:text-text-primary"
                aria-label="More options"
              >
                <MoreVertical className="w-5 h-5" />
              </button>
              
              {/* Dropdown Menu */}
              {menuOpen && (
                <div 
                  className="absolute right-0 top-full mt-2 w-48 origin-top-right rounded-lg bg-bg-secondary shadow-lg ring-1 ring-border-primary z-10 focus:outline-none"
                  role="menu"
                >
                  <div className="py-1" role="none">
                    {cardActions.map((action, index) => {
                      const Icon = action.icon;
                      return (
                        <button
                          key={index}
                          onClick={() => {
                            action.onClick();
                            setMenuOpen(false);
                          }}
                          className={`w-full flex items-center px-4 py-2 text-sm text-left transition-colors duration-150
                            ${action.destructive 
                              ? 'text-color-danger hover:bg-red-500/[.08]' 
                              : 'text-text-primary hover:bg-bg-hover'}`
                          }
                          role="menuitem"
                        >
                          <Icon className="w-4 h-4 mr-3" aria-hidden="true" />
                          {action.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Card Content */}
      <div className="flex-1">
        {children}
      </div>
    </div>
  );
};

export default ModernCard;
