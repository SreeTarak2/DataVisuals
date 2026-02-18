import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, BarChart3, TrendingUp, Target, AlertCircle, Eye, Download, Maximize2 } from 'lucide-react';
import PlotlyChart from './PlotlyChart';
import { cn } from '../lib/utils';

const VisualEvidencePanel = ({ 
  activeVisualization, 
  onClose, 
  onMaximize,
  className 
}) => {
  const [isLoading, setIsLoading] = useState(false);

  const getVisualizationIcon = (type) => {
    switch (type?.toLowerCase()) {
      case 'trend':
      case 'line':
        return <TrendingUp className="w-5 h-5" />;
      case 'correlation':
      case 'scatter':
        return <BarChart3 className="w-5 h-5" />;
      case 'performance':
      case 'bar':
        return <Target className="w-5 h-5" />;
      case 'anomaly':
      case 'box':
        return <AlertCircle className="w-5 h-5" />;
      default:
        return <Eye className="w-5 h-5" />;
    }
  };

  const getVisualizationColor = (type) => {
    switch (type?.toLowerCase()) {
      case 'trend':
      case 'line':
        return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20';
      case 'correlation':
      case 'scatter':
        return 'text-blue-400 bg-blue-400/10 border-blue-400/20';
      case 'performance':
      case 'bar':
        return 'text-purple-400 bg-purple-400/10 border-purple-400/20';
      case 'anomaly':
      case 'box':
        return 'text-orange-400 bg-orange-400/10 border-orange-400/20';
      default:
        return 'text-cyan-400 bg-cyan-400/10 border-cyan-400/20';
    }
  };

  if (!activeVisualization) {
    return (
      <div className={cn(
        "h-full flex items-center justify-center p-8",
        "bg-slate-900/30 backdrop-blur-sm border border-slate-700/30 rounded-xl",
        className
      )}>
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center"
        >
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-slate-800/50 flex items-center justify-center">
            <Eye className="w-8 h-8 text-slate-400" />
          </div>
          <h3 className="text-lg font-semibold text-slate-200 mb-2">
            Visual Evidence
          </h3>
          <p className="text-sm text-slate-400 max-w-xs">
            Click on any insight to see the supporting visualization here
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className={cn(
        "h-full flex flex-col",
        "bg-slate-900/30 backdrop-blur-sm border border-slate-700/30 rounded-xl overflow-hidden",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700/30">
        <div className="flex items-center gap-3">
          <div className={cn(
            "p-2 rounded-lg border",
            getVisualizationColor(activeVisualization.type)
          )}>
            {getVisualizationIcon(activeVisualization.type)}
          </div>
          <div>
            <h3 className="font-semibold text-slate-100">
              {activeVisualization.title}
            </h3>
            <p className="text-xs text-slate-400">
              {activeVisualization.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onMaximize && (
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => onMaximize(activeVisualization)}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-300 hover:bg-slate-700/50 transition-colors"
              title="Maximize"
            >
              <Maximize2 className="w-4 h-4" />
            </motion.button>
          )}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-300 hover:bg-slate-700/50 transition-colors"
            title="Close"
          >
            <X className="w-4 h-4" />
          </motion.button>
        </div>
      </div>

      {/* Chart Content */}
      <div className="flex-1 p-4">
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="h-full flex items-center justify-center"
            >
              <div className="text-center">
                <div className="w-8 h-8 mx-auto mb-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-slate-400">Generating visualization...</p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="chart"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="h-full"
            >
              {activeVisualization.chartData ? (
                <div className="h-full relative">
                  <PlotlyChart
                    data={activeVisualization.chartData.data}
                    layout={{
                      ...activeVisualization.chartData.layout,
                      paper_bgcolor: 'rgba(0,0,0,0)',
                      plot_bgcolor: 'rgba(0,0,0,0)',
                      font: {
                        color: '#e2e8f0',
                        family: 'Inter, system-ui, sans-serif'
                      },
                      xaxis: {
                        ...activeVisualization.chartData.layout?.xaxis,
                        gridcolor: 'rgba(148, 163, 184, 0.1)',
                        linecolor: 'rgba(148, 163, 184, 0.3)',
                        tickcolor: 'rgba(148, 163, 184, 0.3)'
                      },
                      yaxis: {
                        ...activeVisualization.chartData.layout?.yaxis,
                        gridcolor: 'rgba(148, 163, 184, 0.1)',
                        linecolor: 'rgba(148, 163, 184, 0.3)',
                        tickcolor: 'rgba(148, 163, 184, 0.3)'
                      }
                    }}
                    config={{
                      displayModeBar: true,
                      modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
                      displaylogo: false,
                      responsive: true
                    }}
                    style={{ 
                      height: '100%',
                      width: '100%',
                      borderRadius: '8px'
                    }}
                  />
                  
                  {/* Chart Overlay Info */}
                  <div className="absolute top-3 right-3 bg-slate-800/80 backdrop-blur-sm rounded-lg px-3 py-2">
                    <div className="flex items-center gap-2 text-xs text-slate-300">
                      {getVisualizationIcon(activeVisualization.type)}
                      <span className="font-medium">
                        {activeVisualization.chartType || 'Chart'}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-slate-800/50 flex items-center justify-center">
                      <BarChart3 className="w-6 h-6 text-slate-400" />
                    </div>
                    <p className="text-sm text-slate-400 mb-2">
                      Chart data not available
                    </p>
                    <p className="text-xs text-slate-500">
                      Unable to render visualization
                    </p>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer Actions */}
      {activeVisualization.chartData && (
        <div className="p-4 border-t border-slate-700/30">
          <div className="flex items-center justify-between">
            <div className="text-xs text-slate-400">
              Generated from: {activeVisualization.datasetName || 'Current Dataset'}
            </div>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-600/50 transition-colors text-xs"
            >
              <Download className="w-3 h-3" />
              Export
            </motion.button>
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default VisualEvidencePanel;
