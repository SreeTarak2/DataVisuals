import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BarChart3, Info, Sparkles } from 'lucide-react';
import { cn } from '../lib/utils';

const InteractiveKeyword = ({ 
  children, 
  type = 'default',
  onVisualize,
  definition,
  className 
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const getKeywordColor = (type) => {
    switch (type) {
      case 'number':
      case 'percentage':
        return 'text-emerald-400 bg-emerald-400/10 hover:bg-emerald-400/20';
      case 'currency':
        return 'text-green-400 bg-green-400/10 hover:bg-green-400/20';
      case 'trend':
        return 'text-blue-400 bg-blue-400/10 hover:bg-blue-400/20';
      case 'correlation':
        return 'text-purple-400 bg-purple-400/10 hover:bg-purple-400/20';
      case 'performance':
        return 'text-orange-400 bg-orange-400/10 hover:bg-orange-400/20';
      default:
        return 'text-cyan-400 bg-cyan-400/10 hover:bg-cyan-400/20';
    }
  };

  const getKeywordIcon = (type) => {
    switch (type) {
      case 'correlation':
        return <BarChart3 className="w-3 h-3" />;
      case 'trend':
        return <Sparkles className="w-3 h-3" />;
      default:
        return <Info className="w-3 h-3" />;
    }
  };

  const handleClick = () => {
    if (onVisualize) {
      onVisualize(children, type);
    }
  };

  return (
    <span className="relative inline-block">
      <motion.span
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onMouseEnter={() => {
          setIsHovered(true);
          if (definition) {
            setShowTooltip(true);
          }
        }}
        onMouseLeave={() => {
          setIsHovered(false);
          setShowTooltip(false);
        }}
        onClick={handleClick}
        className={cn(
          "inline-flex items-center gap-1 px-2 py-1 rounded-md cursor-pointer transition-all duration-200",
          "font-medium text-sm border border-transparent",
          getKeywordColor(type),
          isHovered && "shadow-md",
          onVisualize && "hover:border-current/30",
          className
        )}
      >
        {getKeywordIcon(type)}
        {children}
      </motion.span>

      {/* Tooltip */}
      <AnimatePresence>
        {showTooltip && definition && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 z-50"
          >
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-xl max-w-xs">
              <div className="flex items-start gap-2">
                <Info className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-slate-100 text-sm mb-1">
                    {children}
                  </h4>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {definition}
                  </p>
                </div>
              </div>
              
              {/* Tooltip Arrow */}
              <div className="absolute top-full left-1/2 transform -translate-x-1/2">
                <div className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-slate-800" />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
};

export default InteractiveKeyword;
