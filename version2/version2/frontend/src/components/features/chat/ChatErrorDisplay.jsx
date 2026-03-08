import React from 'react';
import { AlertCircle, Clock, Wifi, WifiOff, RefreshCw, Zap, Info, XCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

/**
 * ChatErrorDisplay - Beautiful error messages for chat failures
 * 
 * Handles:
 * - Rate limit errors (429)
 * - Network errors
 * - Timeout errors
 * - Generic errors
 */

const ERROR_CONFIGS = {
  rate_limit: {
    icon: Clock,
    title: "High Demand",
    color: "amber",
    gradient: "from-amber-500/20 to-orange-500/20",
    border: "border-amber-500/30",
    iconColor: "text-amber-400",
    suggestions: [
      "Check the Dashboard for pre-computed insights",
      "Try Chart Studio for custom visualizations",
      "Wait 1-2 minutes and retry"
    ]
  },
  network: {
    icon: WifiOff,
    title: "Connection Issue",
    color: "red",
    gradient: "from-red-500/20 to-rose-500/20",
    border: "border-red-500/30",
    iconColor: "text-red-400",
    suggestions: [
      "Check your internet connection",
      "Try refreshing the page",
      "The server might be temporarily unavailable"
    ]
  },
  timeout: {
    icon: Clock,
    title: "Request Timed Out",
    color: "blue",
    gradient: "from-blue-500/20 to-indigo-500/20",
    border: "border-blue-500/30",
    iconColor: "text-blue-400",
    suggestions: [
      "Try a simpler question",
      "Break complex queries into smaller parts",
      "Check if the dataset is very large"
    ]
  },
  unavailable: {
    icon: XCircle,
    title: "Service Unavailable",
    color: "purple",
    gradient: "from-purple-500/20 to-pink-500/20",
    border: "border-purple-500/30",
    iconColor: "text-purple-400",
    suggestions: [
      "The AI service is temporarily down",
      "Use Dashboard for available insights",
      "Try again in a few minutes"
    ]
  },
  generic: {
    icon: AlertCircle,
    title: "Something Went Wrong",
    color: "slate",
    gradient: "from-slate-500/20 to-slate-600/20",
    border: "border-slate-500/30",
    iconColor: "text-slate-400",
    suggestions: [
      "Try rephrasing your question",
      "Refresh and try again",
      "Contact support if the issue persists"
    ]
  }
};

/**
 * Detect error type from error message
 */
const detectErrorType = (error) => {
  const errorStr = typeof error === 'string' ? error : error?.message || error?.detail || '';
  const errorLower = errorStr.toLowerCase();
  
  if (errorLower.includes('429') || errorLower.includes('rate') || errorLower.includes('limit') || errorLower.includes('high demand')) {
    return 'rate_limit';
  }
  if (errorLower.includes('network') || errorLower.includes('connection') || errorLower.includes('offline')) {
    return 'network';
  }
  if (errorLower.includes('timeout') || errorLower.includes('timed out')) {
    return 'timeout';
  }
  if (errorLower.includes('unavailable') || errorLower.includes('502') || errorLower.includes('503')) {
    return 'unavailable';
  }
  return 'generic';
};

/**
 * ChatErrorDisplay Component
 */
export const ChatErrorDisplay = ({ 
  error, 
  onRetry, 
  onDismiss,
  className 
}) => {
  const errorType = detectErrorType(error);
  const config = ERROR_CONFIGS[errorType];
  const Icon = config.icon;
  
  const errorMessage = typeof error === 'string' 
    ? error 
    : error?.message || error?.detail || 'An unexpected error occurred';
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn(
        "mx-4 my-3 rounded-xl overflow-hidden",
        className
      )}
    >
      <div className={cn(
        "p-4 bg-gradient-to-br border",
        config.gradient,
        config.border
      )}>
        {/* Header */}
        <div className="flex items-start gap-3">
          <div className={cn(
            "w-10 h-10 rounded-lg flex items-center justify-center",
            "bg-black/20"
          )}>
            <Icon className={cn("w-5 h-5", config.iconColor)} />
          </div>
          
          <div className="flex-1 min-w-0">
            <h4 className="font-semibold text-white text-sm mb-1">
              {config.title}
            </h4>
            <p className="text-slate-300 text-sm leading-relaxed">
              {errorMessage}
            </p>
          </div>
          
          {onDismiss && (
            <button 
              onClick={onDismiss}
              aria-label="Dismiss error"
              className="p-1 hover:bg-white/10 rounded-lg transition-colors"
            >
              <XCircle className="w-4 h-4 text-slate-400" />
            </button>
          )}
        </div>
        
        {/* Suggestions */}
        <div className="mt-4 pt-3 border-t border-white/10">
          <p className="text-xs text-slate-400 mb-2 flex items-center gap-1.5">
            <Info className="w-3 h-3" />
            What you can do:
          </p>
          <ul className="space-y-1.5">
            {config.suggestions.map((suggestion, i) => (
              <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                <span className="text-slate-500 mt-0.5">•</span>
                {suggestion}
              </li>
            ))}
          </ul>
        </div>
        
        {/* Action buttons */}
        {onRetry && (
          <div className="mt-4 flex gap-2">
            <button
              onClick={onRetry}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium",
                "bg-white/10 hover:bg-white/20 text-white transition-colors"
              )}
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
};

/**
 * RateLimitBanner - Shows when approaching rate limit
 */
export const RateLimitBanner = ({ 
  remaining, 
  total = 30,
  onClose 
}) => {
  if (!total) return null; // Avoid division by zero
  const percentage = (remaining / total) * 100;
  const isLow = percentage <= 20;
  const isCritical = percentage <= 10;
  
  if (percentage > 50) return null; // Don't show if plenty remaining
  
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn(
        "mx-4 mb-2 px-4 py-2.5 rounded-lg flex items-center justify-between",
        "border",
        isCritical 
          ? "bg-red-500/10 border-red-500/30" 
          : isLow 
            ? "bg-amber-500/10 border-amber-500/30"
            : "bg-blue-500/10 border-blue-500/30"
      )}
    >
      <div className="flex items-center gap-2">
        <Zap className={cn(
          "w-4 h-4",
          isCritical ? "text-red-400" : isLow ? "text-amber-400" : "text-blue-400"
        )} />
        <span className="text-sm text-slate-300">
          {isCritical 
            ? `Only ${remaining} requests left! AI may become unavailable.`
            : isLow
              ? `${remaining} requests remaining. Consider spacing out queries.`
              : `${remaining}/${total} requests remaining`
          }
        </span>
      </div>
      
      {onClose && (
        <button 
          onClick={onClose}
          aria-label="Close"
          className="p-1 hover:bg-white/10 rounded transition-colors"
        >
          <XCircle className="w-4 h-4 text-slate-400" />
        </button>
      )}
    </motion.div>
  );
};

/**
 * ConnectionStatus - Shows WebSocket connection state
 */
export const ConnectionStatus = ({ 
  isConnected, 
  isReconnecting,
  className 
}) => {
  return (
    <div className={cn(
      "flex items-center gap-1.5 text-xs",
      className
    )}>
      {isReconnecting ? (
        <>
          <RefreshCw className="w-3 h-3 text-amber-400 animate-spin" />
          <span className="text-amber-400">Reconnecting...</span>
        </>
      ) : isConnected ? (
        <>
          <Wifi className="w-3 h-3 text-green-400" />
          <span className="text-green-400">Live</span>
        </>
      ) : (
        <>
          <WifiOff className="w-3 h-3 text-red-400" />
          <span className="text-red-400">Offline</span>
        </>
      )}
    </div>
  );
};

/**
 * TypingIndicator - Shows when AI is thinking/typing
 */
export const TypingIndicator = ({ 
  stage = 'thinking', // 'thinking' | 'generating' | 'chart'
  className 
}) => {
  const stages = {
    thinking: { text: 'Analyzing your question...', icon: '🤔' },
    generating: { text: 'Generating response...', icon: '✨' },
    chart: { text: 'Creating visualization...', icon: '📊' }
  };
  
  const current = stages[stage] || stages.thinking;
  
  return (
    <div className={cn(
      "flex items-center gap-2 text-sm text-slate-400",
      className
    )}>
      <span>{current.icon}</span>
      <span>{current.text}</span>
      <div className="flex gap-1">
        {[0, 1, 2].map(i => (
          <span 
            key={i}
            className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  );
};

export default ChatErrorDisplay;
