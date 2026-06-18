import React from 'react';
import { Info, ExternalLink } from 'lucide-react';
import { cn } from "../../../lib/utils";

const ConnectionGuide = ({
  id,
  dbInfo,
  requirements,
  isManage,
  isGsheets,
  isMongo,
  isSupabase,
  isDark
}) => {
  if (isManage) {
    return (
      <div className="lg:col-span-3">
        <div className={cn(
          "border rounded-2xl p-7 transition-colors duration-300",
          isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
        )}>
          <h3 className={cn("text-xs font-semibold uppercase tracking-wider mb-5", isDark ? "text-gray-300" : "text-gray-700")}>
            Extractor Guide
          </h3>
          <p className={cn("text-xs leading-relaxed transition-colors duration-300", isDark ? "text-gray-400" : "text-gray-600")}>
            Select any table from the dropdown list to initiate a schema drift check and pull data rows.
            <br /><br />
            You can restrict the number of rows extracted to prevent heavy memory usage, or configure custom query triggers for complex database view joins.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="lg:col-span-3 space-y-6">
      {isGsheets ? (
        /* Google Sheets Guide */
        <div className={cn(
          "border rounded-2xl p-7 transition-colors duration-300",
          isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
        )}>
          <div className="flex items-center gap-3 mb-5">
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center transition-colors duration-300",
              isDark ? "bg-emerald-500/10" : "bg-emerald-50"
            )}>
              <Info size={14} className="text-emerald-500" />
            </div>
            <div>
              <h3 className={cn(
                "text-xs font-semibold uppercase tracking-wider transition-colors duration-300",
                isDark ? "text-gray-300" : "text-gray-700"
              )}>Import Guide</h3>
              <p className={cn(
                "text-[10px] transition-colors duration-300",
                isDark ? "text-gray-500" : "text-gray-400"
              )}>Google Sheets</p>
            </div>
          </div>

          <div className="space-y-4 text-xs leading-relaxed">
            <p className={isDark ? "text-gray-400" : "text-gray-600"}>
              To import a Google Sheet successfully, make sure your document satisfies the following constraints:
            </p>
            <ul className="space-y-2.5 list-disc pl-4">
              <li className={isDark ? "text-gray-400" : "text-gray-600"}>
                The spreadsheet link must be set to <strong>"Anyone with the link can view"</strong> or public.
              </li>
              <li className={isDark ? "text-gray-400" : "text-gray-600"}>
                The first row of each sheet will automatically be processed as the column header.
              </li>
              <li className={isDark ? "text-gray-400" : "text-gray-600"}>
                Signal will convert each tab/sheet in the spreadsheet into a separate table in your workspace.
              </li>
            </ul>
          </div>
        </div>
      ) : (
        /* Database Connection Guide */
        <div className={cn(
          "border rounded-2xl p-7 transition-colors duration-300",
          isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
        )}>
          <div className="flex items-center gap-3 mb-5">
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center transition-colors duration-300",
              isDark ? "bg-orange-500/10" : "bg-orange-50"
            )}>
              <Info size={14} className="text-orange-500" />
            </div>
            <div>
              <h3 className={cn(
                "text-xs font-semibold uppercase tracking-wider transition-colors duration-300",
                isDark ? "text-gray-300" : "text-gray-700"
              )}>Connection Guide</h3>
              <p className={cn(
                "text-[10px] transition-colors duration-300",
                isDark ? "text-gray-500" : "text-gray-400"
              )}>{dbInfo.name}</p>
            </div>
          </div>

          {/* Connection String Preview */}
          <div className={cn(
            "rounded-xl p-4 mb-5 border transition-colors duration-300",
            isDark ? "bg-[#0A0A0A] border-white/[0.04]" : "bg-gray-50 border-gray-100"
          )}>
            <p className={cn(
              "text-[9px] font-bold uppercase tracking-wider mb-2 transition-colors duration-300",
              isDark ? "text-gray-500" : "text-gray-400"
            )}>Connection String Format</p>
            <code className={cn(
              "block text-[11px] font-mono leading-relaxed break-all transition-colors duration-300",
              isDark ? "text-gray-300" : "text-gray-700"
            )}>
              {isMongo && !isSupabase
                ? 'mongodb+srv://<user>:<password>@<cluster>.mongodb.net/<database>'
                : isSupabase
                  ? 'postgresql://<user>:<password>@db.<project>.supabase.co:5432/postgres'
                  : `${dbInfo.name.toLowerCase() === 'mysql' ? 'mysql' : 'postgresql'}://<user>:<password>@<host>:${dbInfo.defaultPort}/<database>`
              }
            </code>
          </div>

          {/* Requirements Checklist */}
          <div className="space-y-3">
            <p className={cn(
              "text-[9px] font-bold uppercase tracking-wider transition-colors duration-300",
              isDark ? "text-gray-500" : "text-gray-400"
            )}>Requirements</p>
            <ul className="space-y-3">
              {requirements.map((req, i) => (
                <li key={i} className="flex items-start gap-3">
                  <div className={cn(
                    "w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5 transition-colors duration-300",
                    isDark ? "bg-white/[0.03]" : "bg-gray-100"
                  )}>
                    <req.icon size={11} className={cn("transition-colors duration-300", isDark ? "text-gray-500" : "text-gray-400")} />
                  </div>
                  <span className={cn("text-[11px] leading-relaxed transition-colors duration-300", isDark ? "text-gray-400" : "text-gray-600")}>
                    {req.text}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {dbInfo.docUrl && (
            <div className={cn(
              "pt-5 mt-5 border-t transition-colors duration-300",
              isDark ? "border-white/[0.04]" : "border-gray-100"
            )}>
              <a
                href={dbInfo.docUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  "flex items-center justify-between text-[11px] font-medium transition-all group/link",
                  isDark ? "text-gray-400 hover:text-white" : "text-gray-500 hover:text-gray-950"
                )}
              >
                <span>View {dbInfo.name} Documentation</span>
                <ExternalLink size={11} className="transition-transform group-hover/link:translate-x-0.5 group-hover/link:-translate-y-0.5" />
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ConnectionGuide;
