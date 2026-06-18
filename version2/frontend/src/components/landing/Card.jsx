import React from 'react';
import { cn } from '../../lib/utils';

export const Card = ({ children, className, elevated = false, interactive = false, ...props }) => {
  return (
    <div 
      className={cn(
        "card", 
        elevated && "card-elevated", 
        interactive && "card-interactive",
        className
      )} 
      {...props}
    >
      {children}
    </div>
  );
};
