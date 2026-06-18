import React from 'react';
import { cn } from '../../lib/utils';

export const Section = ({ children, className, id, ...props }) => {
  return (
    <section id={id} className={cn("py-20", className)} {...props}>
      <div className="lp-wrapper">
        {children}
      </div>
    </section>
  );
};
