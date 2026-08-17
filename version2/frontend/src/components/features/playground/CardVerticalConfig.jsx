import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart3,
  TrendingUp,
  LineChart,
  PieChart,
  Calculator,
  Database,
  Search,
  Check,
  Hash,
  ListFilter,
  DollarSign,
  Percent,
  Sliders,
  Layers,
  X,
} from 'lucide-react';
import { cn } from '../../../lib/utils';
import { CHART_TYPES, AGG_OPTIONS, KPI_FORMATS } from '../../features/charts/chartConstants';

// Helper for mapping chart types to matching Lucide icons
const getChartTypeIcon = (typeId) => {
  switch (typeId) {
    case 'bar':
    case 'grouped_bar':
    case 'stacked_bar':
      return <BarChart3 className="w-4 h-4" />;
    case 'line':
    case 'multi_line':
      return <LineChart className="w-4 h-4" />;
    case 'area':
      return <TrendingUp className="w-4 h-4" />;
    case 'pie':
    case 'donut':
      return <PieChart className="w-4 h-4" />;
    default:
      return <Sliders className="w-4 h-4" />;
  }
};

// Map KPI format IDs to Lucide icons (icons can't live in plain JS constants)
const getFormatIcon = (formatId) => {
  switch (formatId) {
    case 'number': return <Hash className="w-3.5 h-3.5" />;
    case 'integer': return <Check className="w-3.5 h-3.5" />;
    case 'currency': return <DollarSign className="w-3.5 h-3.5" />;
    case 'percentage': return <Percent className="w-3.5 h-3.5" />;
    default: return <Hash className="w-3.5 h-3.5" />;
  }
};

export default function CardVerticalConfig({
  card,
  onUpdateConfig,
  linkedColumns = [],
  linkedDatasetId,
  accentColor = '#3b82f6',
  side = 'left',
}) {
  const [activeMenu, setActiveMenu] = useState(null); // 'type' | 'xColumn' | 'yColumn' | 'agg' | 'groupBy' | 'column' | 'format' | null
  const [searchQuery, setSearchQuery] = useState('');
  const containerRef = useRef(null);

  // Close menus when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setActiveMenu(null);
        setSearchQuery('');
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const config = card.config || {};
  const isChart = card.type === 'chart';
  const isKpi = card.type === 'kpi';

  if (!isChart && !isKpi) return null;

  // Toggle helper
  const handleToggleMenu = (menuName) => {
    if (activeMenu === menuName) {
      setActiveMenu(null);
    } else {
      setActiveMenu(menuName);
    }
    setSearchQuery('');
  };

  // Filter columns by search
  const filteredColumns = linkedColumns.filter((col) =>
    col.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // ── Single-select handler (X axis, agg, format, type, kpi column) ──
  const handleSelectValue = (key, val) => {
    onUpdateConfig({ [key]: val });
    setActiveMenu(null);
    setSearchQuery('');
  };

  // ── Auto-switch map: single-type → multi-series variant ──
  const MULTI_TYPE_MAP = {
    bar: 'grouped_bar',
    line: 'multi_line',
    area: 'stacked_area',
  };

  // ── Multi-select handler for Y columns ──
  const handleToggleYColumn = (col) => {
    const current = config.yColumns || (config.yColumn ? [config.yColumn] : []);
    const isSelected = current.includes(col);
    const updated = isSelected
      ? current.filter((c) => c !== col)
      : [...current, col];

    const patch = {
      yColumns: updated,
      yColumn: updated[0] || '', // Keep backward-compat single field
    };

    // Auto-switch chart type when going from 1→2+ Y columns
    if (updated.length > 1 && current.length <= 1) {
      const currentType = config.chart_type || 'bar';
      const multiType = MULTI_TYPE_MAP[currentType];
      if (multiType) {
        patch.chart_type = multiType;
      }
    }

    onUpdateConfig(patch);
  };

  // ── Single-select toggle for Group By ──
  const handleSelectGroupBy = (col) => {
    if (config.groupBy === col) {
      onUpdateConfig({ groupBy: null });
    } else {
      onUpdateConfig({ groupBy: col });
    }
    setActiveMenu(null);
    setSearchQuery('');
  };

  // ── Resolve Y columns (backward compat: prefer yColumns[], fallback to [yColumn]) ──
  const yColumns = config.yColumns && config.yColumns.length > 0
    ? config.yColumns
    : (config.yColumn ? [config.yColumn] : []);
  const yCount = yColumns.length;

  // Sidebar wrapper positioning based on side
  const isLeft = side === 'left';

  return (
    <div
      ref={containerRef}
      className={cn(
        "absolute top-0 flex flex-col gap-2 z-30 pointer-events-auto",
        isLeft ? "right-full mr-3" : "left-full ml-3"
      )}
    >
      {/* ─── Main Vertical Floating Dock ─── */}
      <div
        className="flex flex-col gap-1.5 p-1.5 rounded-xl border shadow-2xl transition-all duration-300"
        style={{
          background: 'rgba(15, 17, 26, 0.96)',
          borderColor: 'rgba(255, 255, 255, 0.12)',
          backdropFilter: 'blur(20px)',
          boxShadow: `0 8px 32px rgba(0, 0, 0, 0.5), 0 0 16px ${accentColor}18`,
        }}
      >
        {isChart && (
          <>
            {/* Chart Type Trigger */}
            <DockButton
              onClick={() => handleToggleMenu('type')}
              active={activeMenu === 'type'}
              tooltip="Chart Type"
              accentColor={accentColor}
            >
              {getChartTypeIcon(config.chart_type || 'bar')}
            </DockButton>

            {/* X-Axis Trigger */}
            <DockButton
              onClick={() => handleToggleMenu('xColumn')}
              active={activeMenu === 'xColumn'}
              tooltip="X Axis Column"
              accentColor={accentColor}
              labeled
              label="X"
            >
              <Database className="w-4 h-4 text-slate-200" />
            </DockButton>

            {/* Y-Axis Trigger (multi-select with count badge) */}
            <DockButton
              onClick={() => handleToggleMenu('yColumn')}
              active={activeMenu === 'yColumn'}
              tooltip={`Y Axis Columns${yCount > 1 ? ` (${yCount})` : ''}`}
              accentColor={accentColor}
              labeled
              label={yCount > 1 ? `Y+${yCount - 1}` : 'Y'}
              badge={yCount > 1 ? yCount : null}
            >
              <Database className="w-4 h-4 text-slate-200" />
            </DockButton>

            {/* Group By Trigger */}
            <DockButton
              onClick={() => handleToggleMenu('groupBy')}
              active={activeMenu === 'groupBy'}
              tooltip={config.groupBy ? `Group by ${config.groupBy}` : 'Group By'}
              accentColor={accentColor}
              labeled
              label="G"
              highlight={!!config.groupBy}
            >
              <Layers className={cn("w-4 h-4", config.groupBy ? 'text-blue-300' : 'text-slate-200')} />
            </DockButton>

            {/* Aggregation Trigger */}
            <DockButton
              onClick={() => handleToggleMenu('agg')}
              active={activeMenu === 'agg'}
              tooltip="Aggregation"
              accentColor={accentColor}
            >
              <Calculator className="w-4 h-4 text-slate-200" />
            </DockButton>
          </>
        )}

        {isKpi && (
          <>
            {/* Column Trigger */}
            <DockButton
              onClick={() => handleToggleMenu('column')}
              active={activeMenu === 'column'}
              tooltip="Metric Column"
              accentColor={accentColor}
            >
              <Database className="w-4 h-4 text-slate-200" />
            </DockButton>

            {/* Aggregation Trigger */}
            <DockButton
              onClick={() => handleToggleMenu('agg')}
              active={activeMenu === 'agg'}
              tooltip="Aggregation"
              accentColor={accentColor}
            >
              <Calculator className="w-4 h-4 text-slate-200" />
            </DockButton>

            {/* Format Trigger */}
            <DockButton
              onClick={() => handleToggleMenu('format')}
              active={activeMenu === 'format'}
              tooltip="Number Format"
              accentColor={accentColor}
            >
              <ListFilter className="w-4 h-4 text-slate-200" />
            </DockButton>
          </>
        )}
      </div>

      {/* ─── Floating Popover Panels ─── */}
      <AnimatePresence mode="wait">
        {activeMenu && (
          <motion.div
            initial={{ opacity: 0, x: isLeft ? 10 : -10, y: 0 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            exit={{ opacity: 0, x: isLeft ? 10 : -10 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            className={cn(
              "absolute top-0 w-64 max-h-[340px] flex flex-col rounded-xl border shadow-2xl overflow-hidden z-50",
              isLeft ? "left-full ml-2" : "right-full mr-2"
            )}
            style={{
              background: 'rgba(15, 17, 26, 0.98)',
              borderColor: 'rgba(255, 255, 255, 0.15)',
              backdropFilter: 'blur(24px)',
            }}
          >
            {/* 1. CHART TYPE POPUP */}
            {activeMenu === 'type' && (
              <div className="flex flex-col h-full overflow-y-auto">
                <div className="px-3.5 py-2.5 border-b border-white/10 bg-white/5 flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-200">Select Chart Type</span>
                </div>
                <div className="p-1.5 space-y-2">
                  {['Comparison', 'Trends', 'Distributions', 'Composition', 'Advanced'].map((group) => {
                    const items = CHART_TYPES.filter((t) => t.group === group);
                    if (items.length === 0) return null;
                    return (
                      <div key={group} className="space-y-1">
                        <div className="px-2 pt-1.5 text-[9px] font-black uppercase tracking-widest text-slate-400">
                          {group}
                        </div>
                        {items.map((item) => (
                          <button
                            key={item.id}
                            onClick={() => handleSelectValue('chart_type', item.id)}
                            className={cn(
                              "w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-colors text-left",
                              config.chart_type === item.id || (!config.chart_type && item.id === 'bar')
                                ? "bg-white/15 text-white font-semibold"
                                : "text-slate-300 hover:bg-white/10 hover:text-white"
                            )}
                          >
                            <div className="flex items-center gap-2 text-slate-200">
                              {getChartTypeIcon(item.id)}
                              <span>{item.label}</span>
                            </div>
                            {(config.chart_type === item.id || (!config.chart_type && item.id === 'bar')) && (
                              <Check className="w-3.5 h-3.5" style={{ color: accentColor }} />
                            )}
                          </button>
                        ))}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 2. X-AXIS POPUP (single-select with search) */}
            {activeMenu === 'xColumn' && (
              <div className="flex flex-col h-full overflow-hidden min-h-[240px]">
                <div className="px-3.5 py-2.5 border-b border-white/10 bg-white/5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-200">Select X Axis</span>
                </div>
                <div className="p-2 border-b border-white/10 bg-black/20 flex items-center gap-2">
                  <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <input
                    autoFocus
                    placeholder="Search columns..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-transparent text-xs outline-none text-white placeholder-slate-400"
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                  {!linkedDatasetId ? (
                    <div className="p-4 text-center text-xs text-slate-400">Link a dataset to select columns.</div>
                  ) : filteredColumns.length === 0 ? (
                    <div className="p-4 text-center text-xs text-slate-400">No columns match.</div>
                  ) : (
                    filteredColumns.map((col) => {
                      const isSelected = config.xColumn === col;
                      return (
                        <button
                          key={col}
                          onClick={() => handleSelectValue('xColumn', col)}
                          className={cn(
                            "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all text-left",
                            isSelected
                              ? "bg-white/15 text-white font-semibold"
                              : "text-slate-300 hover:bg-white/10 hover:text-white"
                          )}
                        >
                          <span className="truncate pr-2">{col}</span>
                          {isSelected && (
                            <Check className="w-3.5 h-3.5 shrink-0" style={{ color: accentColor }} />
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {/* 3. Y-AXIS POPUP (MULTI-SELECT with checkboxes) */}
            {activeMenu === 'yColumn' && (
              <div className="flex flex-col h-full overflow-hidden min-h-[280px]">
                <div className="px-3.5 py-2.5 border-b border-white/10 bg-white/5 flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-200">
                    Y Axis — {yCount} selected
                  </span>
                </div>
                <div className="p-2 border-b border-white/10 bg-black/20 flex items-center gap-2">
                  <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <input
                    autoFocus
                    placeholder="Search columns..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-transparent text-xs outline-none text-white placeholder-slate-400"
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                  {!linkedDatasetId ? (
                    <div className="p-4 text-center text-xs text-slate-400">Link a dataset to select columns.</div>
                  ) : filteredColumns.length === 0 ? (
                    <div className="p-4 text-center text-xs text-slate-400">No columns match.</div>
                  ) : (
                    filteredColumns.map((col) => {
                      const isSelected = yColumns.includes(col);
                      const isX = col === config.xColumn;
                      return (
                        <button
                          key={col}
                          onClick={() => !isX && handleToggleYColumn(col)}
                          disabled={isX}
                          className={cn(
                            "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition-all text-left",
                            isX
                              ? "opacity-30 cursor-not-allowed"
                              : isSelected
                                ? "bg-white/15 text-white font-semibold"
                                : "text-slate-300 hover:bg-white/10 hover:text-white"
                          )}
                          title={isX ? 'Already selected as X axis' : ''}
                        >
                          {/* Custom checkbox */}
                          <div
                            className={cn(
                              "w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors",
                              isSelected
                                ? 'border-transparent'
                                : isX
                                  ? 'border-white/10'
                                  : 'border-white/20 hover:border-white/40'
                            )}
                            style={isSelected ? { background: accentColor, borderColor: accentColor } : undefined}
                          >
                            {isSelected && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
                          </div>
                          <span className="truncate flex-1">{col}</span>
                          {isX && (
                            <span className="text-[9px] uppercase tracking-wider text-slate-500 shrink-0">X axis</span>
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
                {/* Footer: selection summary */}
                {yCount > 0 && (
                  <div className="px-3 py-2 border-t border-white/10 bg-white/5 flex items-center gap-1.5 overflow-x-auto">
                    {yColumns.map((col) => (
                      <span
                        key={col}
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium whitespace-nowrap"
                        style={{ background: `${accentColor}25`, color: accentColor }}
                      >
                        {col}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleToggleYColumn(col);
                          }}
                          className="hover:opacity-70"
                        >
                          <X className="w-2.5 h-2.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 4. GROUP BY POPUP (single-select toggle) */}
            {activeMenu === 'groupBy' && (
              <div className="flex flex-col h-full overflow-hidden min-h-[240px]">
                <div className="px-3.5 py-2.5 border-b border-white/10 bg-white/5 flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-200">Group By Dimension</span>
                  {config.groupBy && (
                    <button
                      onClick={() => {
                        onUpdateConfig({ groupBy: null });
                        setActiveMenu(null);
                      }}
                      className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-medium"
                      style={{ color: 'rgba(239,68,68,0.7)', border: '1px solid rgba(239,68,68,0.2)' }}
                    >
                      <X className="w-2.5 h-2.5" /> Clear
                    </button>
                  )}
                </div>
                <div className="p-2 border-b border-white/10 bg-black/20 flex items-center gap-2">
                  <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <input
                    autoFocus
                    placeholder="Search dimensions..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-transparent text-xs outline-none text-white placeholder-slate-400"
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                  {!linkedDatasetId ? (
                    <div className="p-4 text-center text-xs text-slate-400">Link a dataset to select columns.</div>
                  ) : filteredColumns.length === 0 ? (
                    <div className="p-4 text-center text-xs text-slate-400">No columns match.</div>
                  ) : (
                    filteredColumns.map((col) => {
                      const isSelected = config.groupBy === col;
                      const isInY = yColumns.includes(col);
                      return (
                        <button
                          key={col}
                          onClick={() => !isInY && handleSelectGroupBy(col)}
                          disabled={isInY}
                          className={cn(
                            "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all text-left",
                            isInY
                              ? "opacity-30 cursor-not-allowed"
                              : isSelected
                                ? "bg-white/15 text-white font-semibold"
                                : "text-slate-300 hover:bg-white/10 hover:text-white"
                          )}
                          title={isInY ? 'Already selected as a Y axis column' : ''}
                        >
                          <div className="flex items-center gap-2">
                            {isSelected && <Check className="w-3.5 h-3.5" style={{ color: accentColor }} />}
                            <span>{col}</span>
                          </div>
                          {isInY && (
                            <span className="text-[9px] uppercase tracking-wider text-slate-500">Y axis</span>
                          )}
                        </button>
                      );
                    })
                  )}
                  {/* Empty option: no group by */}
                  <div className="border-t border-white/10 pt-1 mt-1">
                    <button
                      onClick={() => {
                        onUpdateConfig({ groupBy: null });
                        setActiveMenu(null);
                      }}
                      className={cn(
                        "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all text-left",
                        !config.groupBy
                          ? "bg-white/15 text-white font-semibold"
                          : "text-slate-300 hover:bg-white/10 hover:text-white"
                      )}
                    >
                      <span className="text-slate-400">No grouping</span>
                      {!config.groupBy && <Check className="w-3.5 h-3.5" style={{ color: accentColor }} />}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 5. AGGREGATION POPUP */}
            {activeMenu === 'agg' && (
              <div className="flex flex-col h-full overflow-y-auto">
                <div className="px-3.5 py-2.5 border-b border-white/10 bg-white/5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-200">Select Aggregation</span>
                </div>
                <div className="p-1.5 space-y-0.5">
                  {AGG_OPTIONS.map((opt) => {
                    const isSelected = config.aggregation === opt.id || (!config.aggregation && opt.id === 'sum');
                    return (
                      <button
                        key={opt.id}
                        onClick={() => handleSelectValue('aggregation', opt.id)}
                        className={cn(
                          "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors text-left",
                          isSelected
                            ? "bg-white/15 text-white font-semibold"
                            : "text-slate-300 hover:bg-white/10 hover:text-white"
                        )}
                      >
                        <span>{opt.label}</span>
                        {isSelected && (
                          <Check className="w-3.5 h-3.5" style={{ color: accentColor }} />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 6. KPI COLUMN POPUP */}
            {activeMenu === 'column' && (
              <div className="flex flex-col h-full overflow-hidden min-h-[240px]">
                <div className="px-3.5 py-2.5 border-b border-white/10 bg-white/5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-200">Select Metric Column</span>
                </div>
                <div className="p-2 border-b border-white/10 bg-black/20 flex items-center gap-2">
                  <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <input
                    autoFocus
                    placeholder="Search columns..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-transparent text-xs outline-none text-white placeholder-slate-400"
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                  {!linkedDatasetId ? (
                    <div className="p-4 text-center text-xs text-slate-400">Link a dataset first.</div>
                  ) : filteredColumns.length === 0 ? (
                    <div className="p-4 text-center text-xs text-slate-400">No columns match.</div>
                  ) : (
                    filteredColumns.map((col) => {
                      const isSelected = config.column === col;
                      return (
                        <button
                          key={col}
                          onClick={() => handleSelectValue('column', col)}
                          className={cn(
                            "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all text-left",
                            isSelected
                              ? "bg-white/15 text-white font-semibold"
                              : "text-slate-300 hover:bg-white/10 hover:text-white"
                          )}
                        >
                          <span className="truncate pr-2">{col}</span>
                          {isSelected && (
                            <Check className="w-3.5 h-3.5 shrink-0" style={{ color: accentColor }} />
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {/* 7. KPI FORMAT POPUP */}
            {activeMenu === 'format' && (
              <div className="flex flex-col h-full overflow-y-auto">
                <div className="px-3.5 py-2.5 border-b border-white/10 bg-white/5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-200">Select Format</span>
                </div>
                <div className="p-1.5 space-y-0.5">
                  {KPI_FORMATS.map((opt) => {
                    const isSelected = config.format === opt.id || (!config.format && opt.id === 'number');
                    return (
                      <button
                        key={opt.id}
                        onClick={() => handleSelectValue('format', opt.id)}
                        className={cn(
                          "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors text-left",
                          isSelected
                            ? "bg-white/15 text-white font-semibold"
                            : "text-slate-300 hover:bg-white/10 hover:text-white"
                        )}
                      >
                        <div className="flex items-center gap-2">
                          {getFormatIcon(opt.id)}
                          <span>{opt.label}</span>
                        </div>
                        {isSelected && (
                          <Check className="w-3.5 h-3.5" style={{ color: accentColor }} />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Sleek Button component for the Dock
function DockButton({ children, onClick, active, tooltip, accentColor, labeled, label, badge, highlight }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div className="relative group">
      <motion.button
        type="button"
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.95 }}
        onClick={onClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={cn(
          "w-8.5 h-8.5 rounded-lg flex items-center justify-center relative transition-all duration-200 border",
          active || highlight
            ? "border-transparent text-white"
            : "border-white/10 hover:border-white/25 text-slate-200 hover:text-white bg-white/5 hover:bg-white/15"
        )}
        style={{
          background: active ? accentColor : (highlight ? `${accentColor}30` : undefined),
          boxShadow: active ? `0 0 14px ${accentColor}60` : (highlight ? `0 0 8px ${accentColor}30` : 'none'),
        }}
      >
        {children}
        {labeled && (
          <span className={cn(
            "absolute -bottom-1 -right-1 text-[8px] font-black uppercase px-1 py-0.2 rounded leading-none border shadow",
            highlight
              ? "bg-accent-primary text-white border-accent-primary"
              : "bg-slate-900 text-slate-200 border-white/20"
          )}>
            {label}
          </span>
        )}
        {/* Badge count for multi-select */}
        {badge !== null && badge !== undefined && badge > 0 && (
          <span
            className="absolute -top-1.5 -right-1.5 text-[8px] font-bold text-white rounded-full min-w-[16px] h-4 flex items-center justify-center px-1 leading-none shadow-lg"
            style={{ background: accentColor }}
          >
            {badge}
          </span>
        )}
      </motion.button>

      {/* Hover Tooltip */}
      <AnimatePresence>
        {isHovered && !active && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8, x: -10 }}
            animate={{ opacity: 1, scale: 1, x: 0 }}
            exit={{ opacity: 0, scale: 0.8, x: -10 }}
            className="absolute left-full top-1/2 -translate-y-1/2 ml-2 pointer-events-none px-2 py-1 rounded-md bg-slate-900 border border-white/20 text-[9px] uppercase tracking-wider text-slate-100 font-bold whitespace-nowrap z-50 shadow-2xl"
          >
            {tooltip}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
