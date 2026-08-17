/**
 * DrillDownBreadcrumbs
 * ====================
 * Breadcrumb navigation for chart drill-down paths.
 *
 * Displays a clickable trail showing the current drill-down level:
 *   All Data > Category > Subcategory
 *
 * Each breadcrumb is clickable to navigate back to that level.
 * The last item is highlighted as the current level.
 */

import React from 'react';
import { motion } from 'framer-motion';
import { ChevronRight, Home, ShieldAlert } from 'lucide-react';

const MotionDiv = motion.div;

const DrillDownBreadcrumbs = ({ stack, onNavigate, colors }) => {
  if (!stack || stack.length === 0) return null;

  return (
    <MotionDiv
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className="overflow-hidden shrink-0 relative z-10"
    >
      <div className="px-5 pb-2">
        <nav
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border backdrop-blur-sm"
          style={{
            background: `${colors.primary}08`,
            borderColor: `${colors.primary}20`,
          }}
        >
          {stack.map((level, index) => {
            const isLast = index === stack.length - 1;
            const isRoot = index === 0;

            return (
              <React.Fragment key={`crumb-${index}`}>
                {index > 0 && (
                  <ChevronRight
                    size={10}
                    className="shrink-0"
                    style={{ color: 'rgba(128,128,128,0.3)' }}
                  />
                )}
                <button
                  onClick={() => onNavigate(index)}
                  className={`
                    inline-flex items-center gap-1 px-1.5 py-0.5 rounded
                    transition-all duration-200
                    ${isLast
                      ? 'font-semibold cursor-default'
                      : 'hover:bg-white/5 cursor-pointer opacity-70 hover:opacity-100'
                    }
                  `}
                  style={{
                    color: isLast ? colors.primary : colors.textMuted,
                  }}
                  disabled={isLast}
                  title={`${isLast ? 'Current' : 'Back to'}: ${level.label}${level.provisional ? ' (assumed hierarchy)' : ''}${level.nextLevel ? ` — drilled to ${level.nextLevel}` : ''}`}
                >
                  {isRoot && <Home size={10} className="shrink-0" />}
                  <span>
                    {Array.isArray(level.values) && level.values.length > 1
                      ? level.values.join(', ')
                      : level.label}
                  </span>
                  {level.provisional && (
                    <ShieldAlert
                      size={10}
                      className="shrink-0"
                      style={{ color: '#f59e0b' }}
                      title="Assumed hierarchy path (low confidence) — validate it in the assumptions review"
                    />
                  )}
                </button>
              </React.Fragment>
            );
          })}
        </nav>
      </div>
    </MotionDiv>
  );
};

export default DrillDownBreadcrumbs;
