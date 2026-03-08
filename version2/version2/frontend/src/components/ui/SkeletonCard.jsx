import React from 'react';
import { Skeleton } from './skeleton';

// Skeleton for KPI Cards
export const SkeletonKpiCard = () => (
  <div className="bg-card/80 backdrop-blur-sm border border-border/50 rounded-xl p-6 h-32">
    <div className="flex items-center justify-between mb-4">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-3 w-3 rounded-full" />
    </div>
    <Skeleton className="h-8 w-24 mb-2" />
    <Skeleton className="h-3 w-16" />
  </div>
);

// Skeleton for Chart Cards
export const SkeletonChartCard = () => (
  <div className="bg-card/80 backdrop-blur-sm border border-border/50 rounded-xl p-6 h-80">
    <div className="flex items-center justify-between mb-4">
      <div>
        <Skeleton className="h-5 w-40 mb-2" />
        <Skeleton className="h-3 w-60" />
      </div>
      <Skeleton className="h-6 w-6" />
    </div>
    <div className="flex-1 flex items-center justify-center">
      <div className="w-full h-48 space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
        <Skeleton className="h-4 w-3/6" />
        <Skeleton className="h-4 w-2/6" />
      </div>
    </div>
  </div>
);

// Skeleton for Small Info Cards
export const SkeletonInfoCard = () => (
  <div className="bg-card/80 backdrop-blur-sm border border-border/50 rounded-xl p-4 h-24">
    <div className="flex items-center justify-between">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-3 w-3 rounded-full" />
    </div>
    <Skeleton className="h-6 w-20 mt-2" />
  </div>
);

// Skeleton for Table Cards
export const SkeletonTableCard = () => (
  <div className="bg-card/80 backdrop-blur-sm border border-border/50 rounded-xl p-6 h-64">
    <div className="flex items-center justify-between mb-4">
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-6 w-6" />
    </div>
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex space-x-4">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-24" />
        </div>
      ))}
    </div>
  </div>
);

// Skeleton for Dashboard Header Info
export const SkeletonHeaderInfo = () => (
  <div className="flex items-center space-x-4 text-sm text-muted-foreground">
    <Skeleton className="h-4 w-16" />
    <span>•</span>
    <Skeleton className="h-4 w-20" />
    <span>•</span>
    <Skeleton className="h-4 w-32" />
  </div>
);

