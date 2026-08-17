import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search, ChevronLeft, ChevronRight,
  Loader2, Table2, Columns3, Sparkles, Copy, Database, HelpCircle,
  Plus, X, PanelLeftOpen, PanelLeftClose, FileText
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';
import useDatasetStore from '@/store/datasetStore';
import { datasetAPI } from '@/services/api';
import SqlEditorPanel from '@/components/features/sql/SqlEditorPanel';
import SqlQueriesSidebar from '@/components/features/sql/SqlQueriesSidebar';
import SideChatPanel from '@/components/features/chat/SideChatPanel';

/**
 * SqlEditorPage — Redesigned Supabase-style Full-page SQL Workspace
 */
const SqlEditorPage = () => {
  const { selectedDataset } = useDatasetStore();

  // ── Panel & Sidebar layout state ──────────────────────────────────
  const [showQueriesSidebar, setShowQueriesSidebar] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const [externalSql, setExternalSql] = useState('');
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 900;

  const handleCloseChat = useCallback(() => {
    setChatOpen(false);
  }, []);

  const handleInsertSql = useCallback((sqlText) => {
    setExternalSql(sqlText);
  }, []);

  const handleExternalSqlConsumed = useCallback(() => {
    setExternalSql('');
  }, []);

  // ── Queries / Tabs state ──────────────────────────────────────────
  const [queries, setQueries] = useState(() => {
    try {
      const saved = localStorage.getItem('sql-queries-catalog');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.length > 0) return parsed;
      }
    } catch {}
    return [
      {
        id: 'default-query',
        name: 'Untitled query',
        sql: 'SELECT * FROM data LIMIT 100;',
        isFavorite: false,
        isShared: false,
      }
    ];
  });
  
  const [activeQueryId, setActiveQueryId] = useState(() => {
    try {
      const savedActive = localStorage.getItem('sql-queries-active-id');
      if (savedActive) return savedActive;
    } catch {}
    return 'default-query';
  });

  // Load columns when dataset changes
  const [columns, setColumns] = useState([]);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaSearch, setSchemaSearch] = useState('');

  // Persist queries & active ID
  useEffect(() => {
    localStorage.setItem('sql-queries-catalog', JSON.stringify(queries));
  }, [queries]);

  useEffect(() => {
    localStorage.setItem('sql-queries-active-id', activeQueryId);
  }, [activeQueryId]);

  useEffect(() => {
    if (selectedDataset?.is_processed) {
      loadColumns();
    } else {
      setColumns([]);
    }
  }, [selectedDataset]);

  const loadColumns = async () => {
    if (!selectedDataset) return;
    setSchemaLoading(true);
    try {
      if (selectedDataset.metadata?.column_metadata?.length > 0) {
        setColumns(selectedDataset.metadata.column_metadata);
        return;
      }
      if (selectedDataset.column_names?.length > 0) {
        setColumns(selectedDataset.column_names.map(name => ({ name, type: 'unknown' })));
        return;
      }
      const response = await datasetAPI.getDatasetData(selectedDataset.id, 1, 1);
      if (response.data?.data?.length > 0) {
        const colNames = Object.keys(response.data.data[0]);
        setColumns(colNames.map(name => ({ name, type: 'unknown' })));
      }
    } catch (err) {
      console.error('Failed to load columns:', err);
      setColumns([]);
    } finally {
      setSchemaLoading(false);
    }
  };

  // ── Tab Management Actions ────────────────────────────────────────
  const handleCreateQuery = useCallback(() => {
    const newId = `query-${Date.now()}`;
    const newQuery = {
      id: newId,
      name: `Untitled query ${queries.length + 1}`,
      sql: 'SELECT * FROM data LIMIT 100;',
      isFavorite: false,
      isShared: false,
    };
    setQueries(prev => [...prev, newQuery]);
    setActiveQueryId(newId);
  }, [queries.length]);

  const handleDeleteQuery = useCallback((idToDelete) => {
    if (queries.length === 1) {
      // Just clear and reset the current query
      setQueries([
        {
          id: 'default-query',
          name: 'Untitled query',
          sql: 'SELECT * FROM data LIMIT 100;',
          isFavorite: false,
          isShared: false,
        }
      ]);
      setActiveQueryId('default-query');
      return;
    }

    const index = queries.findIndex(q => q.id === idToDelete);
    const newQueries = queries.filter(q => q.id !== idToDelete);
    setQueries(newQueries);

    // If active tab was deleted, switch active tab
    if (activeQueryId === idToDelete) {
      const nextActiveIndex = index > 0 ? index - 1 : 0;
      setActiveQueryId(newQueries[nextActiveIndex].id);
    }
  }, [queries, activeQueryId]);

  const handleToggleFavorite = useCallback((id) => {
    setQueries(prev => prev.map(q => 
      q.id === id ? { ...q, isFavorite: !q.isFavorite } : q
    ));
  }, []);

  // Pass full column metadata (name + type) for rich autocomplete badges
  const columnMeta = columns;

  const filteredColumns = schemaSearch
    ? columns.filter(c =>
        (typeof c === 'string' ? c : c.name).toLowerCase().includes(schemaSearch.toLowerCase())
      )
    : columns;

  const getTypeHint = (type) => {
    const t = (type || '').toLowerCase();
    if (['numeric', 'integer', 'float', 'int64', 'float64', 'number'].includes(t)) {
      return { label: 'num', color: 'text-blue-400 bg-blue-500/[0.08]', dot: 'bg-blue-400' };
    }
    if (['timestamp', 'datetime', 'date', 'time', 'datetime64'].includes(t)) {
      return { label: 'time', color: 'text-emerald-400 bg-emerald-500/[0.08]', dot: 'bg-emerald-400' };
    }
    if (['text', 'string', 'object', 'varchar', 'char'].includes(t)) {
      return { label: 'text', color: 'text-amber-400 bg-amber-500/[0.08]', dot: 'bg-amber-400' };
    }
    if (['bool', 'boolean'].includes(t)) {
      return { label: 'bool', color: 'text-purple-400 bg-purple-500/[0.08]', dot: 'bg-purple-400' };
    }
    return { label: t.slice(0, 4) || '—', color: 'text-zinc-400 bg-zinc-500/[0.08]', dot: 'bg-zinc-400' };
  };



  return (
    <div className="h-full flex flex-col bg-primary overflow-hidden">
      


      {/* ── Main Workspace (3-Column Flex Architecture) ── */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Mobile backdrop */}
        {isMobile && showQueriesSidebar && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowQueriesSidebar(false)}
            className="fixed inset-0 z-30 bg-black/50 backdrop-blur-xs"
          />
        )}

        {/* Column 1: Left SQL Queries Sidebar */}
        <AnimatePresence initial={false}>
          {showQueriesSidebar && (
            <motion.div
              key="queries-sidebar"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 260, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.18, ease: 'easeInOut' }}
              className="shrink-0 overflow-hidden z-20 h-full bg-surface"
            >
              <SqlQueriesSidebar
                queries={queries}
                activeQueryId={activeQueryId}
                onSelectQuery={setActiveQueryId}
                onCreateQuery={handleCreateQuery}
                onDeleteQuery={handleDeleteQuery}
                onToggleFavorite={handleToggleFavorite}
                columns={columns}
                schemaLoading={schemaLoading}
                datasetName={selectedDataset?.name || ''}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Column 2: Main Editor Workspace */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-primary/5">
          {selectedDataset && selectedDataset.is_processed ? (
            <>
              {/* Tabs Bar */}
              <div className="flex items-center bg-surface border-b border-border h-9 select-none shrink-0 overflow-x-auto studio-scrollbar pr-4">
                
                {/* Collapse Sidebar Button */}
                <button
                  onClick={() => setShowQueriesSidebar(!showQueriesSidebar)}
                  className="h-full px-3 text-secondary hover:text-header hover:bg-elevated/40 transition-colors flex items-center justify-center border-r border-border"
                  title={showQueriesSidebar ? "Collapse Sidebar" : "Expand Sidebar"}
                >
                  {showQueriesSidebar ? <PanelLeftClose size={13} /> : <PanelLeftOpen size={13} />}
                </button>

                {/* Tabs row */}
                <div className="flex items-center h-full min-w-0 overflow-x-auto hide-scrollbar">
                  {queries.map((q) => {
                    const isActive = q.id === activeQueryId;
                    return (
                      <div
                        key={q.id}
                        onClick={() => setActiveQueryId(q.id)}
                        className={cn(
                          "h-full px-4 flex items-center gap-2 border-r border-border cursor-pointer transition-all duration-150 relative text-[12px] group",
                          isActive 
                            ? "bg-primary text-header font-semibold border-b-2 border-b-accent-primary" 
                            : "text-muted hover:text-header hover:bg-elevated/20"
                        )}
                      >
                        <FileText size={11} className={isActive ? "text-accent-primary" : "opacity-50"} />
                        <span className="truncate max-w-[100px]">{q.name}</span>
                        
                        {/* Close tab */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteQuery(q.id);
                          }}
                          className="p-0.5 rounded hover:bg-elevated/60 text-muted/40 hover:text-header opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity ml-1.5"
                          title="Close tab"
                        >
                          <X size={10} />
                        </button>
                      </div>
                    );
                  })}
                </div>

                {/* Add Tab Button */}
                <button
                  onClick={handleCreateQuery}
                  className="h-full px-3 text-muted hover:text-header hover:bg-elevated/35 transition-colors border-r border-border flex items-center justify-center"
                  title="New Tab"
                >
                  <Plus size={13} />
                </button>
              </div>

              {/* Workspaces + Collapsible Right Schema Sidebar */}
              <div className="flex-1 flex overflow-hidden min-h-0 relative w-full">
                {queries.map((q) => {
                  const isActive = q.id === activeQueryId;
                  return (
                    <div
                      key={q.id}
                      className={cn("flex-1 overflow-hidden min-h-0 w-full h-full", isActive ? "flex" : "hidden")}
                    >
                      <SqlEditorPanel
                        datasetId={selectedDataset.id}
                        columns={columnMeta}
                        isOpen={true}
                        initialSql={q.sql}
                        queryId={q.id}
                        onSqlChange={(newSql) => {
                          setQueries(prev => prev.map(item => item.id === q.id ? { ...item, sql: newSql } : item));
                        }}
                        isFavorite={q.isFavorite}
                        onToggleFavorite={() => handleToggleFavorite(q.id)}
                        onToggleChat={() => setChatOpen(prev => !prev)}
                        externalSql={isActive ? externalSql : ''}
                        onExternalSqlConsumed={handleExternalSqlConsumed}
                        className="flex-1 h-full"
                        compact={false}
                      />
                    </div>
                  );
                })}


              </div>
            </>
          ) : (
            /* ── Redesigned Empty State Canvas ── */
            <div className="h-full flex items-center justify-center p-8 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-accent-primary/[0.03] via-transparent to-transparent">
              <div className="text-center max-w-2xl w-full px-6 py-10 bg-transparent select-none relative">
                
                {/* Minimal database icon */}
                <div className="w-12 h-12 rounded-xl bg-accent-primary/10 flex items-center justify-center mx-auto mb-5">
                  <Database className="w-5.5 h-5.5 text-accent-primary" />
                </div>
                
                <h2 className="text-sm font-bold text-header tracking-wider mb-2 uppercase">
                  SQL Workbench
                </h2>
                <p className="text-xs text-muted/80 leading-relaxed mb-10 max-w-sm mx-auto">
                  Select a processed dataset from the assets dropdown to initialize the SQL canvas and schema explorer.
                </p>

                {/* 3-Column Steps Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
                  {/* Step 1 */}
                  <div className="flex flex-col gap-2 p-5 rounded-2xl bg-elevated/5 hover:bg-elevated/10 transition-all duration-200">
                    <div className="text-[10px] font-bold text-accent-primary uppercase tracking-widest">Step 01</div>
                    <h4 className="text-xs font-bold text-header">Choose Dataset</h4>
                    <p className="text-[11px] text-muted/70 leading-relaxed mt-0.5">
                      Use the database dropdown in the header selector to load processed tables.
                    </p>
                  </div>

                  {/* Step 2 */}
                  <div className="flex flex-col gap-2 p-5 rounded-2xl bg-elevated/5 hover:bg-elevated/10 transition-all duration-200">
                    <div className="text-[10px] font-bold text-accent-primary uppercase tracking-widest">Step 02</div>
                    <h4 className="text-xs font-bold text-header">Develop SQL</h4>
                    <p className="text-[11px] text-muted/70 leading-relaxed mt-0.5">
                      Type queries directly, autocomplete using schema tags, or run AI generation commands.
                    </p>
                  </div>

                  {/* Step 3 */}
                  <div className="flex flex-col gap-2 p-5 rounded-2xl bg-elevated/5 hover:bg-elevated/10 transition-all duration-200">
                    <div className="text-[10px] font-bold text-accent-primary uppercase tracking-widest">Step 03</div>
                    <h4 className="text-xs font-bold text-header">Run & Export</h4>
                    <p className="text-[11px] text-muted/70 leading-relaxed mt-0.5">
                      Execute using <kbd className="px-1.5 py-0.5 rounded bg-elevated/30 border border-border/40 text-[9px] font-sans text-muted">Ctrl+Enter</kbd> and export to CSV or JSON.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Column 3: AI Copilot Chat Panel (Embedded 3rd Column in Flex Layout) */}
        <SideChatPanel
          isOpen={chatOpen}
          onClose={handleCloseChat}
          onInsertSql={handleInsertSql}
          mode="sql_analyst"
          embedded={true}
        />
      </div>
    </div>
  );
};

export default SqlEditorPage;
