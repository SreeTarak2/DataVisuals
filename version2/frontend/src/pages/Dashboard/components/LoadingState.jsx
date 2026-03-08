/**
 * LoadingState Component
 * 
 * Skeleton shimmer loading state that mirrors the actual dashboard layout:
 *  4 KPI cards → 2 chart placeholders → insights bar → data table
 * Replaces the previous simple spinner for a more polished UX.
 */

import React from 'react';

const Shimmer = ({ className = '' }) => (
    <div className={`animate-pulse-skeleton rounded-lg bg-ui-border ${className}`} />
);

const SkeletonKpi = () => (
    <div className="bento-card p-5 h-[140px]">
        <div className="flex items-center justify-between mb-4">
            <Shimmer className="h-4 w-28" />
            <Shimmer className="h-6 w-6 rounded-md" />
        </div>
        <Shimmer className="h-8 w-20 mb-3" />
        <div className="flex items-center gap-2">
            <Shimmer className="h-3 w-14" />
            <Shimmer className="h-3 w-20" />
        </div>
    </div>
);

const SkeletonChart = () => (
    <div className="bento-card overflow-hidden">
        <div className="p-5 border-b border-ui-border flex items-center justify-between">
            <div>
                <Shimmer className="h-5 w-44 mb-2" />
                <Shimmer className="h-3 w-24" />
            </div>
            <Shimmer className="h-4 w-12" />
        </div>
        <div className="p-4 h-[380px] flex items-end gap-2">
            {[40, 65, 50, 80, 55, 70, 45, 90, 60, 75].map((h, i) => (
                <Shimmer key={i} className="flex-1 rounded-t" style={{ height: `${h}%` }} />
            ))}
        </div>
    </div>
);

const SkeletonInsights = () => (
    <div className="bento-card p-5">
        <div className="flex items-center gap-3 mb-4">
            <Shimmer className="h-8 w-8 rounded-lg" />
            <div>
                <Shimmer className="h-4 w-32 mb-1.5" />
                <Shimmer className="h-3 w-48" />
            </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[...Array(4)].map((_, i) => (
                <div key={i} className="flex items-start gap-3 p-3.5 rounded-xl bg-base-bg/40 border border-ui-border/30">
                    <Shimmer className="w-7 h-7 rounded-lg flex-shrink-0" />
                    <div className="flex-1">
                        <Shimmer className="h-3.5 w-3/4 mb-2" />
                        <Shimmer className="h-3 w-full mb-1" />
                        <Shimmer className="h-3 w-2/3" />
                    </div>
                </div>
            ))}
        </div>
    </div>
);

const SkeletonTable = () => (
    <div className="bento-card p-5 mt-5">
        <div className="flex items-center gap-3 mb-5">
            <Shimmer className="h-8 w-8 rounded-lg" />
            <Shimmer className="h-5 w-28" />
        </div>
        <div className="space-y-3">
            {/* Header row */}
            <div className="flex gap-4 pb-2 border-b border-ui-border">
                {[80, 120, 100, 140, 90].map((w, i) => (
                    <Shimmer key={i} className="h-4" style={{ width: `${w}px` }} />
                ))}
            </div>
            {/* Data rows */}
            {[...Array(5)].map((_, i) => (
                <div key={i} className="flex gap-4">
                    {[70, 110, 90, 130, 80].map((w, j) => (
                        <Shimmer key={j} className="h-3.5" style={{ width: `${w}px` }} />
                    ))}
                </div>
            ))}
        </div>
    </div>
);

const LoadingState = () => {
    return (
        <div className="min-h-screen bg-base-bg p-6 space-y-8">
            {/* Header skeleton */}
            <div className="flex items-center justify-between">
                <div>
                    <Shimmer className="h-7 w-64 mb-2" />
                    <Shimmer className="h-4 w-40" />
                </div>
                <Shimmer className="h-9 w-28 rounded-lg" />
            </div>

            {/* KPI grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {[...Array(4)].map((_, i) => (
                    <SkeletonKpi key={i} />
                ))}
            </div>

            {/* Charts — Bento layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                <div className="col-span-1 lg:col-span-12"><SkeletonChart /></div>
                <div className="col-span-1 lg:col-span-7"><SkeletonChart /></div>
                <div className="col-span-1 lg:col-span-5"><SkeletonChart /></div>
            </div>

            {/* Insights */}
            <SkeletonInsights />

            {/* Table */}
            <SkeletonTable />

            {/* Subtle bottom message */}
            <div className="text-center pb-4">
                <p className="text-xs text-text-secondary animate-pulse-skeleton">AI is analyzing your data and generating insights…</p>
            </div>
        </div>
    );
};

export default LoadingState;
