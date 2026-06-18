import React from 'react';
import { CheckCircle2, Database, Server } from 'lucide-react';
import { cn } from "../../../lib/utils";

const ConnectorHeader = ({
  id,
  dbInfo,
  connectionLabel,
  isManage,
  isGsheets,
  loadedConn,
  isDark
}) => {
  return (
    <header className="animate-in fade-in slide-in-from-top-4 duration-500">
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-5">
        <div className={cn(
          "w-14 h-14 shrink-0 rounded-2xl flex items-center justify-center overflow-hidden transition-all duration-300 ring-1",
          isDark 
            ? "bg-emerald-500/10 ring-white/[0.08]" 
            : "bg-emerald-50 ring-gray-200"
        )}>
          {id === 'gsheets' ? (
            <img src="/google-sheets.png" alt="Google Sheets" className="w-9 h-9 object-contain" />
          ) : ['postgres', 'mysql', 'mongodb', 'supabase'].includes(id) ? (
            <img src={`/${id}.png`} alt={dbInfo.name} className="w-9 h-9 object-contain" />
          ) : (
            <Database size={26} className={isDark ? "text-gray-400" : "text-gray-500"} />
          )}
        </div>
        
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] font-bold",
              isManage ? "bg-emerald-400/10 text-emerald-300" : "bg-orange-400/10 text-orange-300"
            )}>
              {isManage ? <CheckCircle2 size={12} /> : <Server size={12} />}
              {isManage ? 'Connected' : 'Setup'}
            </span>
            <span className={cn(
              "inline-flex rounded-md px-2 py-1 text-[10px] font-bold",
              isDark ? "bg-white/[0.06] text-gray-400" : "bg-gray-100 text-gray-600"
            )}>
              {dbInfo.meta || 'Data source'}
            </span>
          </div>

          <h1 className={cn(
            "text-4xl font-semibold tracking-tight transition-colors duration-300", 
            isDark ? "text-white" : "text-gray-900"
          )}>
            {isGsheets ? 'Google Sheets' : dbInfo.name}
          </h1>
          
          <p className={cn(
            "text-sm max-w-2xl leading-relaxed transition-colors duration-300", 
            isDark ? "text-gray-400" : "text-gray-600",
            isManage && "font-mono"
          )}>
            {isManage && loadedConn
              ? (dbInfo.name === 'Supabase' || id === 'supabase'
                  ? `postgresql://${loadedConn.username}@db.${loadedConn.host || 'project'}.supabase.co:${loadedConn.port || '5432'}/${loadedConn.database || 'postgres'}`
                  : `${connectionLabel} · ${loadedConn.host}:${loadedConn.port} · Database: ${loadedConn.database}`
                )
              : (isGsheets
                  ? 'Import a spreadsheet and let Signal prepare it for analysis.'
                  : `Securely connect ${dbInfo.name} and allow Signal to understand your data automatically.`
                )
            }
          </p>
        </div>
      </div>

        <div className={cn(
          "flex w-full items-center justify-between gap-4 rounded-xl px-4 py-3 md:w-auto",
          isDark ? "bg-white/[0.035] ring-1 ring-white/[0.06]" : "bg-white ring-1 ring-gray-200"
        )}>
          <div>
            <p className={cn("text-[10px] font-semibold", isDark ? "text-gray-500" : "text-gray-500")}>
              Environment
            </p>
            <p className={cn("mt-0.5 text-sm font-semibold", isDark ? "text-gray-100" : "text-gray-900")}>
              Production
            </p>
          </div>
          <span className={cn(
            "h-2 w-2 rounded-full",
            isManage ? "bg-emerald-400" : "bg-orange-400"
          )} />
        </div>
      </div>
    </header>
  );
};

export default ConnectorHeader;
