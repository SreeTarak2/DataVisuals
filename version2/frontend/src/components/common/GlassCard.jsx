import React from 'react';
import { cn } from '../../lib/utils';

const GlassCard = ({ children, className, hover = false, elevated = false, ...props }) => {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border transition-all duration-300",
        "bg-[var(--card-bg)] border-[var(--card-border)]",
        "shadow-[var(--card-shadow)]",
        "before:absolute before:inset-0 before:pointer-events-none",
        hover && "hover:shadow-[var(--shadow-lg)] hover:scale-[1.01]",
        elevated && "border-[var(--border-hover)] shadow-[var(--shadow-md)]",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export default GlassCard;
