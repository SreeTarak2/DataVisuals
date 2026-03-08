import React from 'react';
import { cn } from '../../lib/utils';

const GlassCard = ({ children, className, hover = false, elevated = false, ...props }) => {
  return (
    <div
      className={cn(
        // Core glass style — bluish tint and blur
        "relative overflow-hidden rounded-2xl border backdrop-blur-xl transition-all duration-300",
        "bg-[rgb(14, 14, 14)] border-[rgba(255,255,255,0.15)] shadow-[0_8px_32px_rgba(31,38,135,0.37)]",
        "before:absolute before:inset-0 before:bg-gradient-to-br before:from-[rgba(255,255,255,0.2)] before:to-[rgba(255,255,255,0.05)] before:pointer-events-none",
        
        hover && "hover:shadow-[0_12px_48px_rgba(31,38,135,0.5)] hover:scale-[1.02]",
        elevated && "border-[rgba(255,255,255,0.25)] bg-[rgba(255,255,255,0.12)] shadow-2xl",
        className
      )}
      {...props}
    >
      {/* Reflection highlight */}
      <div className="absolute inset-0 bg-gradient-to-t from-white/10 via-transparent to-transparent pointer-events-none" />
      <div className="relative z-10">{children}</div>
    </div>
  );
};

export default GlassCard;
