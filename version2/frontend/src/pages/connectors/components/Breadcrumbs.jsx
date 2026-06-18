import React from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from "../../../lib/utils";

const Breadcrumbs = ({ dbName, isManage, navigate, isDark }) => {
  return (
    <nav className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
      <button
        type="button"
        onClick={() => navigate('/app/connectors')}
        className="hover:text-gray-900 dark:hover:text-white transition-colors cursor-pointer"
      >
        Connectors
      </button>
      <ChevronRight size={12} className={isDark ? "text-gray-600" : "text-gray-400"} />
      <span className={isDark ? "text-gray-300" : "text-gray-700"}>{dbName}</span>
      <ChevronRight size={12} className={isDark ? "text-gray-600" : "text-gray-400"} />
      <span className="text-orange-500">{isManage ? 'Extraction' : 'Setup'}</span>
    </nav>
  );
};

export default Breadcrumbs;
