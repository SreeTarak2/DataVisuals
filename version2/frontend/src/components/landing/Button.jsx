import React from 'react';
import { cn } from '../../lib/utils';

export const Button = ({ children, variant = 'primary', size = 'md', className, ...props }) => {
  const baseClass = "btn";
  const variantClasses = {
    primary: "btn-primary",
    accent: "btn-accent",
    secondary: "btn-secondary",
    ghost: "btn-ghost",
    danger: "btn-danger"
  };
  
  const sizeClasses = {
    xs: "btn-xs",
    sm: "btn-sm",
    md: "", // default
    lg: "btn-lg"
  };
  
  return (
    <button 
      className={cn(
        baseClass, 
        variantClasses[variant] || variantClasses.primary, 
        sizeClasses[size],
        className
      )} 
      {...props}
    >
      {children}
    </button>
  );
};
