import React from 'react';
import { cn } from '@/lib/utils'; // Assuming cn utility exists, if not I will implement it or use simple template literals

const GlassPanel = ({ children, className, ...props }) => {
    return (
        <div
            className={`glass-panel p-6 ${className || ''}`}
            {...props}
        >
            {children}
        </div>
    );
};

export default GlassPanel;
