import React from 'react';
import {
  Activity,
  CheckCircle2,
  Code2,
  Database,
  FileText,
  GitBranch,
  Loader2,
  RefreshCw,
  Rows3,
  ShieldCheck,
  SlidersHorizontal,
  Table,
  Table2,
  Zap,
} from 'lucide-react';
import { cn } from "../../../lib/utils";
import { databaseAPI } from '../../../services/api';

const SourceStat = ({ icon: Icon, label, value, tone = 'neutral' }) => {
  const toneClass = {
    success: 'bg-emerald-400/10 text-emerald-300',
    active: 'bg-orange-400/10 text-orange-300',
    neutral: 'bg-white/[0.045] text-gray-400',
  }[tone];

  return (
    <div className="min-w-0 rounded-xl bg-white/[0.025] p-4 ring-1 ring-white/[0.055]">
      <div className="flex items-center justify-between gap-3">
        <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", toneClass)}>
          <Icon size={15} />
        </span>
        <span className="truncate text-right text-xs font-semibold text-gray-500">{label}</span>
      </div>
      <p className="mt-4 truncate text-lg font-semibold tracking-tight text-white">{value}</p>
    </div>
  );
};

const ConnectionLine = ({ label, value }) => (
  <div className="flex min-w-0 items-center justify-between gap-4 border-b border-white/[0.06] py-3 last:border-b-0">
    <span className="text-xs font-medium text-gray-500">{label}</span>
    <span className="truncate text-right text-xs font-semibold text-gray-300">{value || '-'}</span>
  </div>
);

const ManageModeView = ({
  connId,
  isDark,
  loadedConn,
  isSupabase,
  tables,
  setTables,
  loadingTables,
  setLoadingTables,
  selectedTable,
  setSelectedTable,
  useCustomQuery,
  setUseCustomQuery,
  customQuery,
  setCustomQuery,
  extracting,
  handleExtract,
  datasetName,
  setDatasetName,
  rowLimit,
  setRowLimit
}) => {
  const hasExtractionScope = useCustomQuery ? customQuery.trim().length > 0 : Boolean(selectedTable);
  const extractionLabel = useCustomQuery ? 'Custom SQL' : selectedTable || 'No table selected';
  const connectionHost = isSupabase
    ? `db.${loadedConn.host || 'project'}.supabase.co`
    : loadedConn.host;

  const refreshTables = () => {
    setLoadingTables(true);
    databaseAPI.getTables(connId)
      .then((tRes) => setTables(tRes.data.tables || []))
      .catch(() => {})
      .finally(() => setLoadingTables(false));
  };

  return (
    <div className="space-y-8">
      <section className={cn(
        "rounded-2xl border p-5 md:p-6 animate-in fade-in slide-in-from-bottom-4 duration-500",
        isDark ? "border-white/[0.06] bg-[#111114]" : "border-gray-200 bg-white"
      )}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <SourceStat icon={CheckCircle2} label="Source state" value="Connected" tone="success" />
          <SourceStat icon={Table2} label="Schema inventory" value={loadingTables ? 'Scanning' : `${tables.length} tables`} tone="active" />
          <SourceStat icon={ShieldCheck} label="Credential scope" value="Read access" tone="success" />
          <SourceStat icon={GitBranch} label="Relationships" value="Discovering" />
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className={cn(
          "overflow-hidden rounded-2xl border",
          isDark ? "border-white/[0.06] bg-[#111114]" : "border-gray-200 bg-white"
        )}>
          <div className="flex flex-col gap-4 border-b border-white/[0.06] p-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-[11px] font-semibold text-gray-500">Schema browser</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Choose what Signal should understand</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-400">
                Browse the live schema, select a table, or switch to SQL when you need a precise slice. This page is for operating a connected source, not reconnecting it.
              </p>
            </div>
            <button
              type="button"
              onClick={refreshTables}
              className="inline-flex min-h-9 items-center justify-center gap-2 rounded-lg bg-white/[0.06] px-3 text-xs font-semibold text-gray-200 ring-1 ring-white/[0.08] transition-colors hover:bg-white/[0.1]"
            >
              <RefreshCw size={14} className={cn(loadingTables && "animate-spin")} />
              Refresh schema
            </button>
          </div>

          <div className="p-6">
            <div className="mb-5 flex w-full rounded-lg bg-black/25 p-1 ring-1 ring-white/[0.06] sm:w-fit">
              <button
                type="button"
                onClick={() => setUseCustomQuery(false)}
                className={cn(
                  "flex min-h-9 flex-1 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors sm:flex-none",
                  !useCustomQuery ? "bg-white/[0.1] text-white" : "text-gray-500 hover:text-gray-300"
                )}
              >
                <Table2 size={15} />
                Tables
              </button>
              <button
                type="button"
                onClick={() => setUseCustomQuery(true)}
                className={cn(
                  "flex min-h-9 flex-1 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors sm:flex-none",
                  useCustomQuery ? "bg-white/[0.1] text-white" : "text-gray-500 hover:text-gray-300"
                )}
              >
                <Code2 size={15} />
                SQL
              </button>
            </div>

            {useCustomQuery ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-medium text-gray-500">
                  <FileText size={14} />
                  Query preview
                </div>
                <textarea
                  value={customQuery}
                  onChange={(e) => setCustomQuery(e.target.value)}
                  placeholder="SELECT * FROM public.orders WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'"
                  rows={14}
                  className={cn(
                    "w-full resize-none rounded-xl p-4 font-mono text-sm leading-6 outline-none transition-colors",
                    isDark
                      ? "bg-[#0D0D0F] border border-white/[0.06] text-white placeholder:text-gray-600 focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/40"
                      : "bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:border-orange-500"
                  )}
                />
              </div>
            ) : (
              <div className="min-h-[420px]">
                {loadingTables ? (
                  <div className="flex h-[420px] flex-col items-center justify-center gap-4 rounded-xl bg-black/20 ring-1 ring-white/[0.05]">
                    <Loader2 className="h-6 w-6 animate-spin text-gray-500" />
                    <p className="text-sm font-medium text-gray-500">Reading schema</p>
                  </div>
                ) : tables.length === 0 ? (
                  <div className="flex h-[420px] flex-col items-center justify-center rounded-xl bg-black/20 px-6 text-center ring-1 ring-white/[0.05]">
                    <Database className="h-7 w-7 text-gray-600" />
                    <p className="mt-3 text-sm font-semibold text-gray-300">No tables detected</p>
                    <p className="mt-1 max-w-md text-xs leading-relaxed text-gray-500">
                      Refresh after granting read permissions, or use SQL if this source exposes analysis through views.
                    </p>
                  </div>
                ) : (
                  <div className="grid max-h-[480px] grid-cols-1 gap-3 overflow-y-auto pr-1 md:grid-cols-2 xl:grid-cols-3">
                    {tables.map((tableName) => (
                      <button
                        type="button"
                        key={tableName}
                        onClick={() => setSelectedTable(tableName)}
                        className={cn(
                          "group flex min-h-20 flex-col items-start justify-between rounded-xl p-4 text-left transition-colors ring-1",
                          selectedTable === tableName
                            ? "bg-orange-500/10 text-orange-100 ring-orange-500/35"
                            : "bg-black/25 text-gray-300 ring-white/[0.06] hover:bg-white/[0.04] hover:ring-white/[0.12]"
                        )}
                      >
                        <span className="flex w-full items-center justify-between gap-3">
                          <span className="flex min-w-0 items-center gap-2">
                            <Table size={16} className="shrink-0" />
                            <span className="truncate text-sm font-semibold">{tableName}</span>
                          </span>
                          {selectedTable === tableName && <CheckCircle2 size={15} className="shrink-0 text-orange-300" />}
                        </span>
                        <span className="mt-3 text-[11px] font-medium text-gray-600 group-hover:text-gray-500">
                          Table source
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <aside className={cn(
          "h-fit rounded-2xl border lg:sticky lg:top-6",
          isDark ? "border-white/[0.06] bg-[#0B0B0D]" : "border-gray-200 bg-gray-50"
        )}>
          <div className="border-b border-white/[0.06] p-6">
            <p className="text-[11px] font-semibold text-gray-500">Extraction composer</p>
            <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">Create analysis dataset</h3>
            <p className="mt-2 text-sm leading-6 text-gray-400">
              Define the extraction scope. Signal uses this scope to build metadata, relationships, and AI-ready context.
            </p>
          </div>

          <div className="space-y-6 p-6">
            <div className="rounded-xl bg-white/[0.025] p-4 ring-1 ring-white/[0.055]">
              <div className="flex items-center gap-2 text-xs font-semibold text-gray-500">
                <Activity size={14} />
                Current scope
              </div>
              <p className="mt-3 truncate text-sm font-semibold text-white">{extractionLabel}</p>
              <p className="mt-1 text-xs leading-relaxed text-gray-500">
                {hasExtractionScope ? 'Ready to extract into Signal.' : 'Select a table or write SQL to continue.'}
              </p>
            </div>

            <label className="block space-y-2">
              <span className="flex items-center gap-2 text-xs font-semibold text-gray-500">
                <Rows3 size={14} />
                Row limit <span className="text-orange-400">{rowLimit.toLocaleString()}</span>
              </span>
              <input
                type="range"
                min={1000}
                max={1000000}
                step={1000}
                value={rowLimit}
                onChange={(e) => setRowLimit(Number(e.target.value))}
                className="w-full cursor-pointer accent-orange-500"
              />
              <span className="flex justify-between text-[10px] font-semibold text-gray-600">
                <span>1K</span>
                <span>1M</span>
              </span>
            </label>

            <label className="block space-y-2">
              <span className="flex items-center gap-2 text-xs font-semibold text-gray-500">
                <SlidersHorizontal size={14} />
                Dataset name
              </span>
              <input
                type="text"
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
                placeholder={selectedTable || 'analysis_dataset'}
                className={cn(
                  "w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-colors",
                  isDark
                    ? "bg-[#0D0D0F] border border-white/[0.06] text-white placeholder:text-gray-600 focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/40"
                    : "bg-white border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:border-orange-500"
                )}
              />
            </label>

            <button
              type="button"
              onClick={handleExtract}
              disabled={!hasExtractionScope || extracting}
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-orange-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-orange-500 active:bg-orange-700 disabled:cursor-not-allowed disabled:bg-white/[0.06] disabled:text-gray-500"
            >
              {extracting ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
              {extracting ? 'Extracting dataset' : 'Extract and analyze'}
            </button>

            <div className="rounded-xl bg-black/25 p-4 ring-1 ring-white/[0.055]">
              <p className="text-xs font-semibold text-gray-500">Connection details</p>
              {isSupabase ? (
                <code className="mt-3 block break-all text-xs leading-5 text-gray-400">
                  postgresql://{loadedConn.username}@{connectionHost}:{loadedConn.port || '5432'}/{loadedConn.database || 'postgres'}
                </code>
              ) : (
                <div className="mt-2">
                  <ConnectionLine label="Host" value={loadedConn.host} />
                  <ConnectionLine label="Port" value={loadedConn.port} />
                  <ConnectionLine label="Database" value={loadedConn.database} />
                  <ConnectionLine label="Username" value={loadedConn.username} />
                </div>
              )}
            </div>
          </div>
        </aside>
      </section>
    </div>
  );
};

export default ManageModeView;
