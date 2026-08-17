import React, { useState } from 'react';
import { 
  Search, Plus, ChevronRight, ChevronDown,
  FileText, Star, Share2, HelpCircle, 
  Trash2, Database, Columns3, Copy, 
  Terminal, PlayCircle, Loader2, Hash,
  Type, Calendar, CheckSquare, Check, Filter, X
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';

/**
 * Helper to map standard DB types to icons and color-coded styles
 */
const getColVisuals = (type, HashIcon, TypeIcon, CalendarIcon, CheckSquareIcon, HelpIcon) => {
  const t = (type || '').toLowerCase();
  if (['numeric', 'integer', 'float', 'int64', 'float64', 'number', 'double', 'int', 'decimal'].includes(t)) {
    return { 
      color: 'text-blue-400/80', 
      icon: HashIcon
    };
  }
  if (['timestamp', 'datetime', 'date', 'time', 'datetime64'].includes(t)) {
    return { 
      color: 'text-emerald-400/80', 
      icon: CalendarIcon
    };
  }
  if (['text', 'string', 'object', 'varchar', 'char'].includes(t)) {
    return { 
      color: 'text-amber-400/80', 
      icon: TypeIcon
    };
  }
  if (['bool', 'boolean'].includes(t)) {
    return { 
      color: 'text-purple-400/80', 
      icon: CheckSquareIcon
    };
  }
  return { 
    color: 'text-zinc-400/80', 
    icon: HelpIcon
  };
};

/**
 * SqlQueriesSidebar — Premium Redesigned Supabase-style query catalog browser
 */
const SqlQueriesSidebar = ({
  queries = [],
  activeQueryId = null,
  onSelectQuery,
  onCreateQuery,
  onDeleteQuery,
  onToggleFavorite,
  columns = [],
  schemaLoading = false,
  datasetName = '',
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [colSearch, setColSearch] = useState('');
  const [copiedColName, setCopiedColName] = useState(null);

  const handleCopy = (text, displayName) => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopiedColName(displayName || text);
    setTimeout(() => setCopiedColName(null), 1500);
    toast.success(`Copied "${displayName || text}"`, {
      style: {
        background: '#18181a',
        color: '#f0f2f5',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        fontSize: '11.5px',
        fontFamily: 'var(--font-sans)',
      },
      iconTheme: {
        primary: 'var(--p2-cyan)',
        secondary: '#18181a',
      }
    });
  };
  
  // Collapsible section states
  const [expandedSections, setExpandedSections] = useState({
    shared: false,
    favorites: true,
    private: true,
    reference: true,
  });
  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  // Filter queries based on search
  const filteredQueries = queries.filter(q => 
    q.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const favoriteQueries = filteredQueries.filter(q => q.isFavorite);
  const privateQueries = filteredQueries.filter(q => !q.isShared);
  const sharedQueries = filteredQueries.filter(q => q.isShared);

  return (
    <div className="h-full flex flex-col bg-surface overflow-hidden select-none w-[260px] shrink-0">
      
      {/* Header Panel */}
      <div className="px-4 pt-4 pb-3 flex flex-col gap-3 shrink-0">
        <h2 className="text-[13px] font-black text-header tracking-widest uppercase select-none">
          SQL Editor
        </h2>
        
        {/* Search Queries and Add New Action */}
        <div className="flex items-center gap-1.5">
          <div className="relative flex-1 group h-8">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted/40 group-focus-within:text-accent-primary transition-all duration-200" size={11} />
            <input
              type="text"
              placeholder="Search queries..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-full bg-elevated/10 hover:bg-elevated/18 border border-border/40 focus:border-accent-primary/30 focus:bg-elevated/25 rounded-md !pl-8 pr-3 py-1 text-[11.5px] font-medium text-header placeholder:text-muted/35 focus:outline-none transition-all duration-150"
            />
          </div>
          <button
            onClick={onCreateQuery}
            className="h-8 w-8 rounded-md hover:bg-elevated/30 text-secondary hover:text-header transition-all duration-150 flex items-center justify-center shrink-0"
            title="New query"
          >
            <Plus size={13} />
          </button>
        </div>
      </div>

      {/* Folders Accordion Lists */}
      <div className="flex-1 flex flex-col min-h-0 gap-2 px-2 py-2 overflow-hidden">
        
        {/* SHARED SECTION */}
        <div className="flex flex-col gap-0.5">
          <button
            onClick={() => toggleSection('shared')}
            className="w-full flex items-center gap-1.5 px-2 py-1.5 text-[10px] font-bold text-muted/50 uppercase tracking-widest hover:text-header transition-colors select-none text-left"
          >
            <ChevronRight size={12} className={cn("text-muted/50 transition-transform duration-150", expandedSections.shared && "transform rotate-90")} />
            <span>Shared ({sharedQueries.length})</span>
          </button>
          
          {expandedSections.shared && (
            <div className="flex flex-col gap-0.5 pl-3">
              {sharedQueries.length === 0 ? (
                <div className="px-3 py-2 text-[10.5px] text-muted/35 flex items-center gap-2 select-none italic">
                  <Share2 size={11} className="opacity-40" />
                  <span>No shared queries</span>
                </div>
              ) : (
                sharedQueries.map(q => (
                  <QueryItem
                    key={q.id}
                    query={q}
                    isActive={q.id === activeQueryId}
                    onSelect={() => onSelectQuery(q.id)}
                    onDelete={() => onDeleteQuery(q.id)}
                    onToggleFavorite={() => onToggleFavorite(q.id)}
                  />
                ))
              )}
            </div>
          )}
        </div>

        {/* FAVORITES SECTION */}
        <div className="flex flex-col gap-0.5">
          <button
            onClick={() => toggleSection('favorites')}
            className="w-full flex items-center gap-1.5 px-2 py-1.5 text-[10px] font-bold text-muted/50 uppercase tracking-widest hover:text-header transition-colors select-none text-left"
          >
            <ChevronRight size={12} className={cn("text-muted/50 transition-transform duration-150", expandedSections.favorites && "transform rotate-90")} />
            <span>Favorites ({favoriteQueries.length})</span>
          </button>
          
          {expandedSections.favorites && (
            <div className="flex flex-col gap-0.5 pl-3">
              {favoriteQueries.length === 0 ? (
                <div className="px-3 py-2 text-[10.5px] text-muted/35 flex items-center gap-2 select-none italic">
                  <Star size={11} className="opacity-40" />
                  <span>No favorite queries</span>
                </div>
              ) : (
                favoriteQueries.map(q => (
                  <QueryItem
                    key={q.id}
                    query={q}
                    isActive={q.id === activeQueryId}
                    onSelect={() => onSelectQuery(q.id)}
                    onDelete={() => onDeleteQuery(q.id)}
                    onToggleFavorite={() => onToggleFavorite(q.id)}
                  />
                ))
              )}
            </div>
          )}
        </div>

        {/* PRIVATE SECTION */}
        <div className="flex flex-col gap-0.5">
          <button
            onClick={() => toggleSection('private')}
            className="w-full flex items-center gap-1.5 px-2 py-1.5 text-[10px] font-bold text-muted/50 uppercase tracking-widest hover:text-header transition-colors select-none text-left"
          >
            <ChevronRight size={12} className={cn("text-muted/50 transition-transform duration-150", expandedSections.private && "transform rotate-90")} />
            <span>Private ({privateQueries.length})</span>
          </button>
          
          {expandedSections.private && (
            <div className="flex flex-col gap-0.5 pl-3">
              {privateQueries.length === 0 ? (
                <div className="px-3 py-2 text-[10.5px] text-muted/35 flex items-center gap-2 select-none italic">
                  <FileText size={11} className="opacity-40" />
                  <span>No private queries</span>
                </div>
              ) : (
                privateQueries.map(q => (
                  <QueryItem
                    key={q.id}
                    query={q}
                    isActive={q.id === activeQueryId}
                    onSelect={() => onSelectQuery(q.id)}
                    onDelete={() => onDeleteQuery(q.id)}
                    onToggleFavorite={() => onToggleFavorite(q.id)}
                  />
                ))
              )}
            </div>
          )}
        </div>

        {/* REFERENCE (SCHEMA EXPLORER) SECTION */}
        <div className="mt-2 pt-2 flex flex-col gap-0.5 flex-1 min-h-0 overflow-hidden border-t border-border/10">
          <button
            onClick={() => toggleSection('reference')}
            className="w-full flex items-center justify-between px-2 py-1.5 text-[10px] font-bold text-muted/50 uppercase tracking-widest hover:text-header transition-colors select-none text-left truncate"
          >
            <div className="flex items-center gap-1.5 truncate">
              <ChevronRight size={12} className={cn("text-muted/50 transition-transform duration-150", expandedSections.reference && "transform rotate-90")} />
              <span className="truncate">Reference</span>
            </div>
            {columns.length > 0 && (
              <span className="text-[9px] bg-elevated/80 px-1.5 py-0.5 rounded font-mono text-muted/65 lowercase font-normal">
                {columns.length} cols
              </span>
            )}
          </button>
          
          {expandedSections.reference && (
            <div className="mt-1 flex flex-col px-2 flex-1 overflow-hidden min-h-0">
              {schemaLoading ? (
                <div className="flex items-center gap-2 py-3 text-secondary px-3">
                  <Loader2 size={11} className="animate-spin text-accent-primary" />
                  <span className="text-[10px] font-bold tracking-wider uppercase">Loading Columns...</span>
                </div>
              ) : !datasetName ? (
                <div className="px-3 py-3 text-[10.5px] text-muted/50 leading-relaxed italic select-none">
                  Select a processed dataset from the header to browse schema.
                </div>
              ) : columns.length === 0 ? (
                <div className="px-3 py-3 text-[10.5px] text-muted/40 italic select-none">No columns found</div>
              ) : (
                <>
                  {/* Local Column Search */}
                  <div className="relative shrink-0 group mb-2">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted/35 group-focus-within:text-accent-primary transition-all duration-200" size={11} />
                    <input
                      type="text"
                      placeholder="Search columns..."
                      value={colSearch}
                      onChange={(e) => setColSearch(e.target.value)}
                      className="w-full bg-elevated/10 hover:bg-elevated/18 border border-border/40 focus:border-accent-primary/30 focus:bg-elevated/25 rounded-md !pl-8 pr-7 py-1 h-7.5 text-[11px] font-medium text-header placeholder:text-muted/35 focus:outline-none transition-all duration-150"
                    />
                    {colSearch && (
                      <button
                        onClick={() => setColSearch('')}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted/35 hover:text-header transition-colors"
                      >
                        <X size={10} />
                      </button>
                    )}
                  </div>

                  {/* Flat Column List Container */}
                  <div className="flex-1 overflow-y-auto overflow-x-hidden studio-scrollbar pr-0.5">
                    {(() => {
                      const filteredCols = columns.filter(col => {
                        const name = typeof col === 'string' ? col : col.name;
                        return !colSearch || name.toLowerCase().includes(colSearch.toLowerCase());
                      });

                      if (filteredCols.length === 0) {
                        return (
                          <div className="px-3 py-4 text-center text-[10.5px] text-muted/40 italic select-none">
                            No columns match search
                          </div>
                        );
                      }

                      return (
                        <div className="flex flex-col gap-0.5 py-1 w-full overflow-hidden">
                          {filteredCols.map((col, i) => {
                            const name = typeof col === 'string' ? col : col.name;
                            const type = typeof col === 'string' ? '' : (col.type || '');
                            const visuals = getColVisuals(type, Hash, Type, Calendar, CheckSquare, HelpCircle);
                            const IconComponent = visuals.icon;
                            const isCopied = copiedColName === name;
                            
                            return (
                              <div 
                                key={`${name}-${i}`}
                                onClick={() => handleCopy(name)}
                                className="group flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-elevated/35 cursor-pointer transition-colors w-full min-w-0"
                                title={`Click to copy "${name}" (${type || 'unknown'})`}
                              >
                                <div className="flex items-center gap-2 truncate min-w-0 flex-1">
                                  <IconComponent size={12} className={cn("shrink-0", visuals.color)} />
                                  <span className="text-[12px] font-mono text-secondary truncate group-hover:text-header transition-colors">
                                    {name}
                                  </span>
                                </div>
                                
                                <div className="flex items-center gap-2 shrink-0 ml-1.5">
                                  {type && (
                                    <span className="text-[9.5px] font-mono text-muted/40 uppercase font-normal tracking-wide group-hover:text-muted/65 transition-colors">
                                      {type.toLowerCase()}
                                    </span>
                                  )}
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleCopy(name);
                                    }}
                                    className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-elevated text-muted hover:text-header transition-all duration-150"
                                    title="Copy column name"
                                  >
                                    {isCopied ? (
                                      <Check size={10} className="text-emerald-500" />
                                    ) : (
                                      <Copy size={10} />
                                    )}
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      );
                    })()}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

      </div>

    </div>
  );
};

/**
 * Single query list item component
 */
const QueryItem = ({ query, isActive, onSelect, onDelete, onToggleFavorite }) => {
  return (
    <div
      onClick={onSelect}
      className={cn(
        "group flex items-center justify-between px-2.5 py-1 rounded-md cursor-pointer transition-all duration-150 border border-transparent relative overflow-hidden",
        isActive 
          ? "bg-elevated text-header font-medium" 
          : "text-secondary hover:text-header hover:bg-elevated/35"
      )}
    >
      <div className="flex items-center gap-2 truncate min-w-0">
        <FileText size={13} className={cn("shrink-0 opacity-60", isActive && "opacity-90 text-header")} />
        <span className="text-[12.5px] truncate">
          {query.name}
        </span>
      </div>
      
      {/* Hover action icons */}
      <div className="flex items-center gap-1 shrink-0 ml-2 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity duration-100">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleFavorite();
          }}
          className={cn(
            "p-0.5 rounded hover:bg-elevated transition-colors",
            query.isFavorite ? "text-amber-500" : "text-muted hover:text-header"
          )}
          title={query.isFavorite ? "Remove favorite" : "Add favorite"}
        >
          <Star size={11} fill={query.isFavorite ? "currentColor" : "none"} />
        </button>
        
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="p-0.5 rounded hover:bg-red-500/10 text-muted hover:text-red-400 transition-colors"
          title="Delete query"
        >
          <Trash2 size={11} />
        </button>
      </div>
    </div>
  );
};

export default SqlQueriesSidebar;
