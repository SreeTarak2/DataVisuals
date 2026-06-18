import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Zap, Brain } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * DESIGN OPTION 1: Premium Glassmorphism with Animated Gradient Ring
 * Perfect for: Modern, sophisticated, premium feel
 * Features: Animated gradient ring, glassmorphic card, smooth transitions
 */
export const PremiumGlassmorphismLoader = ({ stage = 'analyzing', className }) => {
  const stages = {
    analyzing: { label: 'Analyzing your question', icon: Brain, color: 'from-blue-400 to-cyan-400' },
    processing: { label: 'Processing data', icon: Zap, color: 'from-orange-400 to-pink-400' },
    generating: { label: 'Generating insights', icon: Sparkles, color: 'from-amber-400 to-orange-400' },
    reanalyzing: { label: 'Refining results', icon: Brain, color: 'from-emerald-400 to-teal-400' }
  };

  const config = stages[stage] || stages.analyzing;
  const IconComponent = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={cn(
        "flex flex-col items-center gap-4 p-8 rounded-2xl",
        "backdrop-blur-md bg-gradient-to-br from-slate-900/50 via-slate-800/50 to-slate-900/50",
        "border border-slate-700/30 shadow-2xl",
        className
      )}
    >
      {/* Animated Gradient Ring */}
      <div className="relative w-24 h-24">
        {/* Outer rotating ring */}
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-0 rounded-full"
          style={{
            background: `conic-gradient(from 0deg, transparent, rgb(51, 65, 85), transparent)`,
            filter: 'blur(1px)'
          }}
        />

        {/* Inner pulse ring */}
        <motion.div
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          className={cn(
            "absolute inset-2 rounded-full bg-gradient-to-r",
            config.color,
            "opacity-30 blur-md"
          )}
        />

        {/* Center icon */}
        <div className="absolute inset-0 flex items-center justify-center">
          <motion.div
            animate={{ y: [0, -4, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          >
            <IconComponent className={cn("w-10 h-10 text-slate-200")} />
          </motion.div>
        </div>
      </div>

      {/* Text with gradient */}
      <div className="text-center space-y-1">
        <motion.p
          animate={{ opacity: [0.7, 1, 0.7] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          className={cn(
            "text-lg font-semibold bg-gradient-to-r",
            config.color,
            "bg-clip-text text-transparent"
          )}
        >
          {config.label}
        </motion.p>
        <p className="text-xs text-slate-400">This may take a few seconds</p>
      </div>

      {/* Progress dots */}
      <div className="flex gap-2">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              delay: i * 0.2,
              ease: 'easeInOut'
            }}
            className={cn(
              "w-2 h-2 rounded-full",
              config.color.replace('from-', 'bg-').split(' ')[0]
            )}
          />
        ))}
      </div>
    </motion.div>
  );
};

/**
 * DESIGN OPTION 2: Minimalist Line Animation with Steps
 * Perfect for: Corporate, clean, professional
 * Features: Animated line drawing, step indicators, elegant simplicity
 */
export const MinimalistLineLoader = ({ stage = 'analyzing', className }) => {
  const stages = {
    analyzing: { label: 'Analyzing your question', step: 1 },
    processing: { label: 'Processing data', step: 2 },
    generating: { label: 'Generating insights', step: 3 },
    reanalyzing: { label: 'Refining results', step: 4 }
  };

  const config = stages[stage] || stages.analyzing;
  const totalSteps = 4;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className={cn(
        "flex flex-col items-center gap-6 p-6 rounded-xl",
        "bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800",
        "border border-slate-200 dark:border-slate-700",
        className
      )}
    >
      {/* Animated SVG Line */}
      <svg width="120" height="80" viewBox="0 0 120 80" className="mx-auto">
        {/* Horizontal line with animated dash */}
        <motion.line
          x1="0"
          y1="40"
          x2="120"
          y2="40"
          stroke="currentColor"
          strokeWidth="2"
          className="text-slate-300 dark:text-slate-600"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />

        {/* Dots on line */}
        {[30, 60, 90].map((x, i) => (
          <motion.circle
            key={i}
            cx={x}
            cy="40"
            r="4"
            fill="currentColor"
            className={i < config.step ? "text-blue-500" : "text-slate-300 dark:text-slate-600"}
            animate={i < config.step ? { r: [4, 6, 4] } : {}}
            transition={{
              duration: 1,
              repeat: Infinity,
              delay: i * 0.2
            }}
          />
        ))}
      </svg>

      {/* Text */}
      <div className="text-center space-y-2">
        <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">
          {config.label}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Step {config.step} of {totalSteps}
        </p>
      </div>

      {/* Progress bar */}
      <div className="w-full max-w-xs h-1 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full"
          animate={{ width: `${(config.step / totalSteps) * 100}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>
    </motion.div>
  );
};

/**
 * DESIGN OPTION 3: Animated Particle System (Premium Enterprise)
 * Perfect for: High-end, sophisticated, visually striking
 * Features: Particle animations, gradient text, hero-style loading
 */
export const AnimatedParticleLoader = ({ stage = 'analyzing', className }) => {
  const stages = {
    analyzing: { label: 'Analyzing your question', gradient: 'from-blue-400 via-blue-500 to-cyan-400' },
    processing: { label: 'Processing data', gradient: 'from-orange-400 via-pink-500 to-red-400' },
    generating: { label: 'Generating insights', gradient: 'from-amber-300 via-orange-400 to-red-500' },
    reanalyzing: { label: 'Refining results', gradient: 'from-emerald-400 via-teal-500 to-cyan-400' }
  };

  const config = stages[stage] || stages.analyzing;

  const particles = Array.from({ length: 12 }, (_, i) => ({
    id: i,
    delay: i * 0.08,
    size: Math.random() * 3 + 1,
    offset: Math.random() * 360
  }));

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className={cn(
        "flex flex-col items-center justify-center gap-6 p-8 rounded-2xl",
        "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900",
        "border border-slate-700/50 shadow-2xl",
        className
      )}
    >
      {/* Particle container */}
      <div className="relative w-32 h-32">
        {/* Center glow */}
        <motion.div
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          className={cn(
            "absolute inset-0 rounded-full blur-2xl opacity-40",
            `bg-gradient-to-r ${config.gradient}`
          )}
        />

        {/* Particles */}
        {particles.map((particle) => (
          <motion.div
            key={particle.id}
            animate={{
              x: Math.cos((particle.offset * Math.PI) / 180) * 50,
              y: Math.sin((particle.offset * Math.PI) / 180) * 50
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: particle.delay
            }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
          >
            <motion.div
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{
                duration: 2,
                repeat: Infinity,
                delay: particle.delay
              }}
              className={cn(
                "rounded-full",
                `bg-gradient-to-r ${config.gradient}`
              )}
              style={{
                width: `${particle.size}px`,
                height: `${particle.size}px`
              }}
            />
          </motion.div>
        ))}

        {/* Center dot */}
        <div className="absolute inset-0 flex items-center justify-center">
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className={cn(
              "w-4 h-4 rounded-full bg-white shadow-lg",
              `shadow-${config.gradient.split('-')[1]}-500/50`
            )}
          />
        </div>
      </div>

      {/* Enhanced Text */}
      <div className="text-center max-w-xs space-y-2">
        <motion.h3
          animate={{ opacity: [0.8, 1, 0.8] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          className={cn(
            "text-xl font-bold bg-gradient-to-r",
            config.gradient,
            "bg-clip-text text-transparent"
          )}
        >
          {config.label}
        </motion.h3>
        <p className="text-xs text-slate-400">
          Preparing your AI-powered insights...
        </p>
      </div>

      {/* Animated underline */}
      <motion.div
        animate={{ scaleX: [0, 1, 0] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        className={cn(
          "h-0.5 w-24 rounded-full bg-gradient-to-r origin-center",
          config.gradient
        )}
      />
    </motion.div>
  );
};

/**
 * DESIGN OPTION 4: Hybrid Smart Loader (RECOMMENDED)
 * Perfect for: Best of all worlds - professional, modern, clear progress
 * Features: Icon + animated border + text + progress bar
 */
export const HybridSmartLoader = ({ stage = 'analyzing', showProgress = true, className }) => {
  const stages = {
    analyzing: { 
      label: 'Analyzing your question', 
      icon: Brain,
      color: 'blue',
      bgGradient: 'from-blue-500/10 to-cyan-500/10',
      borderColor: 'border-blue-400/30'
    },
    processing: { 
      label: 'Processing data', 
      icon: Zap,
      color: 'purple',
      bgGradient: 'from-orange-500/10 to-pink-500/10',
      borderColor: 'border-orange-400/30'
    },
    generating: { 
      label: 'Generating insights', 
      icon: Sparkles,
      color: 'amber',
      bgGradient: 'from-amber-500/10 to-orange-500/10',
      borderColor: 'border-amber-400/30'
    },
    reanalyzing: { 
      label: 'Refining results', 
      icon: Brain,
      color: 'emerald',
      bgGradient: 'from-emerald-500/10 to-teal-500/10',
      borderColor: 'border-emerald-400/30'
    }
  };

  const config = stages[stage] || stages.analyzing;
  const IconComponent = config.icon;
  const colorMap = {
    blue: 'text-blue-400',
    purple: 'text-orange-400',
    amber: 'text-amber-400',
    emerald: 'text-emerald-400'
  };
  const progressColorMap = {
    blue: 'from-blue-500 to-cyan-500',
    purple: 'from-orange-500 to-pink-500',
    amber: 'from-amber-500 to-orange-500',
    emerald: 'from-emerald-500 to-teal-500'
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "flex items-center gap-4 px-6 py-4 rounded-xl",
        `bg-gradient-to-r ${config.bgGradient}`,
        `border ${config.borderColor}`,
        "backdrop-blur-sm shadow-lg",
        className
      )}
    >
      {/* Animated Icon */}
      <motion.div
        animate={{ rotate: [0, 360] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        className="flex-shrink-0"
      >
        <IconComponent className={cn("w-6 h-6", colorMap[config.color])} />
      </motion.div>

      {/* Text Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-50 truncate">
          {config.label}
        </p>
        {showProgress && (
          <div className="mt-1.5 h-1 w-full bg-slate-700/40 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: '0%' }}
              animate={{ width: '100%' }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              className={cn("h-full rounded-full bg-gradient-to-r", progressColorMap[config.color])}
            />
          </div>
        )}
      </div>

      {/* Pulsing dot indicator */}
      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
        className={cn("w-2 h-2 rounded-full flex-shrink-0", colorMap[config.color].replace('text', 'bg'))}
      />
    </motion.div>
  );
};
