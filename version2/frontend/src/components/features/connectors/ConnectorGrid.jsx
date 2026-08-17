import React, { useState, useMemo } from 'react';
import { Loader2, ShieldCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import SearchInput from '../../ui/SearchInput';
import { useTheme } from '../../../store/themeStore';
import { cn } from '../../../lib/utils';
import { TABS, useConnectorCatalog } from '../../../pages/connectors/connectorCatalog';

/* ═══════════════════════════════════════════════════════════════
   ConnectorGrid — the searchable/filterable connector catalog.
   Shared by the standalone Connectors page and the unified
   "Add data" page. Emits onSelect(conn); the parent decides what
   a click means (navigate to setup, open dlt drawer, open file
   upload).
   ═══════════════════════════════════════════════════════════════ */

function ConnectorGrid({ onSelect }) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const { allConnectors, dltLoading } = useConnectorCatalog();
  const [activeTab, setActiveTab] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredConnectors = useMemo(() => {
    return allConnectors.filter((conn) => {
      const matchesTab = activeTab === 'All' || conn.tag === activeTab;
      const matchesSearch =
        conn.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        conn.desc.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesTab && matchesSearch;
    });
  }, [allConnectors, activeTab, searchQuery]);

  return (
    <div className="space-y-8">
      {/* Filters and Search */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className={cn(
          "flex items-center gap-1.5 p-1 rounded-lg border overflow-x-auto max-w-full transition-colors duration-300",
          isDark ? "bg-[#131316] border-white/[0.05]" : "bg-gray-100 border-gray-200"
        )}>
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer whitespace-nowrap",
                activeTab === tab
                  ? "bg-orange-600 text-white shadow-md shadow-orange-950/20"
                  : isDark
                    ? "text-gray-400 hover:text-white hover:bg-white/5"
                    : "text-gray-500 hover:text-gray-900 hover:bg-gray-200"
              )}
            >
              {tab}
            </button>
          ))}
        </div>

        <SearchInput
          placeholder="Search catalog..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full md:w-56 shrink-0"
          style={{ paddingTop: '8px', paddingBottom: '8px' }}
        />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {dltLoading && (
          <div className="col-span-full flex items-center justify-center py-8 gap-2">
            <Loader2 size={16} className="animate-spin text-gray-500" />
            <span className={cn("text-xs font-medium", isDark ? "text-gray-500" : "text-gray-400")}>
              Loading available connectors...
            </span>
          </div>
        )}

        {!dltLoading && (
          <AnimatePresence mode="popLayout">
            {filteredConnectors.map((conn) => (
              <motion.div
                layout
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.2 }}
                key={conn.id}
                onClick={() => onSelect(conn)}
                className={cn(
                  "group flex gap-5 p-6 rounded-xl border transition-all duration-300 cursor-pointer",
                  isDark
                    ? "bg-[#131316] border-white/[0.04] hover:bg-[#18181D] hover:border-white/[0.08]"
                    : "bg-white border-gray-200 hover:bg-gray-50 hover:border-gray-300",
                  "hover:-translate-y-0.5"
                )}
              >
                <div className={cn(
                  "w-12 h-12 shrink-0 rounded-xl flex items-center justify-center overflow-hidden transition-transform duration-300 group-hover:scale-105",
                  conn.bg, conn.color
                )}>
                  {conn.image ? (
                    <img src={conn.image} alt={conn.name} className="w-8 h-8 object-contain" />
                  ) : (
                    <conn.icon size={24} />
                  )}
                </div>
                <div className="flex flex-col flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className={cn(
                      "text-base font-semibold tracking-tight truncate transition-colors duration-300",
                      isDark ? "text-white" : "text-gray-900"
                    )}>{conn.name}</h3>
                    {conn.isNew && (
                      <span className="text-[9px] font-bold text-orange-500 bg-orange-500/10 px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0">
                        New
                      </span>
                    )}
                    {conn.verified && (
                      <span className="inline-flex items-center gap-1 text-[9px] font-bold text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0">
                        <ShieldCheck size={10} />
                        Verified
                      </span>
                    )}
                    {!conn.verified && conn._sourceType === 'dlt' && (
                      <span className="text-[9px] font-bold text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0">
                        REST API
                      </span>
                    )}
                  </div>
                  <p className={cn(
                    "text-xs mt-1.5 leading-relaxed line-clamp-2 transition-colors duration-300",
                    isDark ? "text-gray-400" : "text-gray-600"
                  )}>
                    {conn.desc}
                  </p>
                  <div className={cn(
                    "mt-4 pt-4 flex justify-between items-center transition-colors duration-300",
                    isDark ? "border-t border-white/[0.03]" : "border-t border-gray-200"
                  )}>
                    <span className={cn(
                      "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase transition-colors duration-300",
                      isDark
                        ? "bg-white/[0.03] text-gray-400 group-hover:bg-white/[0.06] group-hover:text-gray-300"
                        : "bg-gray-100 text-gray-500 group-hover:bg-gray-200 group-hover:text-gray-700"
                    )}>
                      {conn.tag}
                    </span>
                    <span className="text-[11px] text-orange-500/0 group-hover:text-orange-500 transition-all duration-300 font-semibold flex items-center gap-1">
                      Configure &rarr;
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        )}

        {!dltLoading && filteredConnectors.length === 0 && (
          <div className={cn(
            "col-span-full py-16 text-center text-sm transition-colors duration-300",
            isDark ? "text-gray-500" : "text-gray-400"
          )}>
            No connectors found matching &ldquo;{searchQuery}&rdquo;
          </div>
        )}
      </div>
    </div>
  );
}

export default ConnectorGrid;
