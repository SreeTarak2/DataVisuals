import React from 'react';
import { motion } from 'framer-motion';

const DashboardSkeleton = () => {
  const SkeletonCard = ({ className = "", children }) => (
    <div className={`bg-slate-800/50 border border-slate-700 rounded-xl p-6 ${className}`}>
      <div className="animate-pulse">
        {children}
      </div>
    </div>
  );

  const SkeletonKPI = () => (
    <SkeletonCard className="h-32">
      <div className="space-y-3">
        <div className="h-4 bg-slate-700 rounded w-3/4"></div>
        <div className="h-8 bg-slate-700 rounded w-1/2"></div>
        <div className="h-3 bg-slate-700 rounded w-1/3"></div>
      </div>
    </SkeletonCard>
  );

  const SkeletonChart = () => (
    <SkeletonCard className="h-96">
      <div className="space-y-4">
        <div className="h-6 bg-slate-700 rounded w-1/3"></div>
        <div className="h-64 bg-slate-700 rounded"></div>
        <div className="flex justify-between">
          <div className="h-3 bg-slate-700 rounded w-1/4"></div>
          <div className="h-3 bg-slate-700 rounded w-1/4"></div>
        </div>
      </div>
    </SkeletonCard>
  );

  const SkeletonTable = () => (
    <SkeletonCard className="h-64">
      <div className="space-y-4">
        <div className="h-6 bg-slate-700 rounded w-1/3"></div>
        <div className="space-y-2">
          <div className="h-4 bg-slate-700 rounded"></div>
          <div className="h-4 bg-slate-700 rounded"></div>
          <div className="h-4 bg-slate-700 rounded"></div>
          <div className="h-4 bg-slate-700 rounded"></div>
        </div>
      </div>
    </SkeletonCard>
  );

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      {/* Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-8 bg-slate-800 rounded w-64 animate-pulse"></div>
          <div className="h-4 bg-slate-800 rounded w-48 animate-pulse"></div>
        </div>
        <div className="flex gap-3">
          <div className="h-10 bg-slate-800 rounded w-24 animate-pulse"></div>
          <div className="h-10 bg-slate-800 rounded w-32 animate-pulse"></div>
        </div>
      </div>

      {/* KPI Row Skeleton */}
      <div className="flex flex-wrap gap-6">
        <div className="w-64 flex-shrink-0">
          <SkeletonKPI />
        </div>
        <div className="w-64 flex-shrink-0">
          <SkeletonKPI />
        </div>
        <div className="w-64 flex-shrink-0">
          <SkeletonKPI />
        </div>
        <div className="w-64 flex-shrink-0">
          <SkeletonKPI />
        </div>
      </div>

      {/* Hero Chart Row Skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3">
          <SkeletonChart />
        </div>
        <div>
          <SkeletonChart />
        </div>
      </div>

      {/* Table Row Skeleton */}
      <SkeletonTable />

      {/* Loading Message */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="text-center py-8"
      >
        <div className="inline-flex items-center gap-3 text-slate-400">
          <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-lg font-medium">AI is designing your perfect dashboard...</span>
        </div>
        <p className="text-sm text-slate-500 mt-2">
          Analyzing data patterns and creating professional visualizations
        </p>
      </motion.div>
    </motion.div>
  );
};

export default DashboardSkeleton;

