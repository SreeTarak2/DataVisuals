import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Database,
  Fingerprint,
  GitBranch,
  KeyRound,
  Layers3,
  Link2,
  Loader2,
  LockKeyhole,
  Radar,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Table2,
} from 'lucide-react';
import { cn } from "../../../lib/utils";

const Field = ({ label, hint, children }) => (
  <label className="block space-y-2">
    <span className="flex items-center justify-between gap-3">
      <span className="text-[11px] font-semibold text-gray-400">{label}</span>
      {hint && <span className="text-[10px] font-medium text-gray-600">{hint}</span>}
    </span>
    {children}
  </label>
);

const InsightRow = ({ icon: Icon, label, value, status = 'neutral' }) => {
  const statusClass = {
    success: 'text-emerald-400 bg-emerald-400/10',
    warning: 'text-amber-400 bg-amber-400/10',
    active: 'text-orange-400 bg-orange-400/10',
    neutral: 'text-gray-400 bg-white/[0.04]',
  }[status];

  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="flex items-center gap-3 min-w-0">
        <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", statusClass)}>
          <Icon size={15} />
        </span>
        <span className="text-sm font-medium text-gray-300 truncate">{label}</span>
      </div>
      <span className="text-right text-xs font-semibold text-gray-500">{value}</span>
    </div>
  );
};

const Benefit = ({ icon: Icon, title, text }) => (
  <div className="min-w-0 space-y-3 rounded-xl bg-white/[0.025] p-4 ring-1 ring-white/[0.05]">
    <Icon size={18} className="text-orange-400" />
    <div className="space-y-1">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <p className="text-xs leading-relaxed text-gray-500">{text}</p>
    </div>
  </div>
);

const SetupModeView = ({
  id,
  isGsheets,
  isMongo,
  isSupabase,
  form,
  set,
  canTest,
  canSave,
  isTesting,
  isSaving,
  testResult,
  testMessage,
  handleTestConnection,
  handleSaveAndConnect,
  sheetUrl,
  setSheetUrl,
  isFetching,
  fetchSuccess,
  handleFetchSheet,
  error,
  dbInfo,
  isDark,
  INPUT_CLASSES,
  LABEL_CLASSES,
  savedConnId
}) => {
  const inputClass = isDark ? INPUT_CLASSES.dark : INPUT_CLASSES.light;
  const labelClass = isDark ? LABEL_CLASSES.dark : LABEL_CLASSES.light;
  const connectionUrlMode = isMongo || isSupabase;
  const hasConnectionSignal = testResult === 'success' || savedConnId || fetchSuccess;
  const isPostgres = id === 'postgres';

  const completedFields = isGsheets
    ? [form.name, sheetUrl].filter(Boolean).length
    : connectionUrlMode
      ? [form.name, form.connection_url].filter(Boolean).length
      : [form.name, form.host, form.port, form.database, form.username, form.password].filter(Boolean).length;

  const totalFields = isGsheets ? 2 : connectionUrlMode ? 2 : 6;
  const readiness = Math.round((completedFields / totalFields) * 100);

  return (
    <div className="space-y-10">
      <section className={cn(
        "overflow-hidden rounded-2xl border animate-in fade-in slide-in-from-bottom-4 duration-500",
        isDark ? "border-white/[0.06] bg-[#111114]" : "border-gray-200 bg-white"
      )}>
        <div className="grid min-h-[620px] grid-cols-1 lg:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
          <div className="p-6 md:p-8 lg:p-10">
            <div className="mb-8 flex flex-col gap-4 border-b border-white/[0.06] pb-6 md:flex-row md:items-end md:justify-between">
              <div>
                <p className={cn("mb-2", labelClass)}>Connection workspace</p>
                <h2 className={cn("text-2xl font-semibold tracking-tight", isDark ? "text-white" : "text-gray-950")}>
                  {isGsheets ? 'Authorize a spreadsheet source' : `Connect ${dbInfo.name} to Signal`}
                </h2>
                <p className={cn("mt-2 max-w-2xl text-sm leading-6", isDark ? "text-gray-400" : "text-gray-600")}>
                  {isGsheets
                    ? 'Signal will import the sheet, normalize columns, and prepare it for analysis.'
                    : 'Provide read access once. Signal tests the connection, maps the schema, and prepares the source for AI analysis.'}
                </p>
              </div>
              <div className="flex items-center gap-2 rounded-xl bg-black/30 px-3 py-2 ring-1 ring-white/[0.06]">
                <CircleDashed size={14} className={cn(hasConnectionSignal ? "text-emerald-400" : "text-orange-400")} />
                <span className="text-xs font-semibold text-gray-300">
                  {hasConnectionSignal ? 'Ready for analysis' : `${readiness}% configured`}
                </span>
              </div>
            </div>

            {isGsheets ? (
              <div className="space-y-6">
                <Field label="Connection name">
                  <input
                    type="text"
                    value={form.name}
                    onChange={e => set('name', e.target.value)}
                    placeholder="Revenue planning sheet"
                    className={inputClass}
                  />
                </Field>
                <Field label="Google Sheets URL">
                  <input
                    type="url"
                    value={sheetUrl}
                    onChange={e => setSheetUrl(e.target.value)}
                    placeholder="https://docs.google.com/spreadsheets/d/..."
                    className={cn(inputClass, "font-mono text-xs")}
                  />
                </Field>
                <div className="rounded-xl bg-emerald-500/[0.06] p-4 ring-1 ring-emerald-500/15">
                  <div className="flex gap-3">
                    <Link2 size={16} className="mt-0.5 shrink-0 text-emerald-400" />
                    <p className="text-xs leading-relaxed text-emerald-100/75">
                      Share the sheet with anyone who has the link before importing. Signal reads the data and creates an analysis-ready dataset.
                    </p>
                  </div>
                </div>
                <div className="flex justify-end border-t border-white/[0.06] pt-6">
                  <button
                    type="button"
                    onClick={handleFetchSheet}
                    disabled={!sheetUrl.trim() || isFetching}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-orange-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-orange-500 active:bg-orange-700 disabled:cursor-not-allowed disabled:bg-white/[0.06] disabled:text-gray-500"
                  >
                    {isFetching ? <Loader2 size={16} className="animate-spin" /> : <Link2 size={16} />}
                    {isFetching ? 'Importing sheet' : 'Fetch and import'}
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleTestConnection} className="space-y-8">
                <Field label="Connection name">
                  <input
                    type="text"
                    value={form.name}
                    onChange={e => set('name', e.target.value)}
                    placeholder={isPostgres ? 'Production warehouse' : `Production ${dbInfo.name}`}
                    className={inputClass}
                  />
                </Field>

                {connectionUrlMode ? (
                  <div className="space-y-4">
                    <Field label="Connection URL">
                      <input
                        type="text"
                        value={form.connection_url}
                        onChange={e => set('connection_url', e.target.value)}
                        placeholder={isSupabase
                          ? "postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres"
                          : "mongodb+srv://user:pass@cluster.mongodb.net/db?retryWrites=true"
                        }
                        className={cn(inputClass, "font-mono text-xs")}
                      />
                    </Field>
                    <div className="rounded-xl bg-orange-500/[0.06] p-4 ring-1 ring-orange-500/15">
                      <div className="flex gap-3">
                        <LockKeyhole size={16} className="mt-0.5 shrink-0 text-orange-400" />
                        <p className="text-xs leading-relaxed text-orange-100/70">
                          Use a dedicated read-only user. Signal stores credentials encrypted and uses them only for metadata discovery and extraction.
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,1fr)_160px]">
                      <Field label="Host">
                        <input
                          type="text"
                          value={form.host}
                          onChange={e => set('host', e.target.value)}
                          placeholder="db.company.internal"
                          className={inputClass}
                        />
                      </Field>
                      <Field label="Port" hint={`Default ${dbInfo.defaultPort}`}>
                        <input
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          value={form.port}
                          onChange={e => set('port', e.target.value.replace(/\D/g, ''))}
                          placeholder={dbInfo.defaultPort}
                          className={inputClass}
                        />
                      </Field>
                    </div>
                    <Field label="Database">
                      <input
                        type="text"
                        value={form.database}
                        onChange={e => set('database', e.target.value)}
                        placeholder={isPostgres || isSupabase ? 'analytics' : id === 'mysql' ? 'production' : 'primary'}
                        className={inputClass}
                      />
                    </Field>
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                      <Field label="Username">
                        <input
                          type="text"
                          value={form.username}
                          onChange={e => set('username', e.target.value)}
                          placeholder={isPostgres ? 'signal_reader' : 'readonly_user'}
                          className={inputClass}
                        />
                      </Field>
                      <Field label="Password">
                        <input
                          type="password"
                          value={form.password}
                          onChange={e => set('password', e.target.value)}
                          placeholder="••••••••••••"
                          className={inputClass}
                        />
                      </Field>
                    </div>
                  </div>
                )}

                <div className="flex flex-col gap-3 border-t border-white/[0.06] pt-6 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-h-5">
                    {savedConnId && (
                      <motion.span
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400"
                      >
                        <CheckCircle2 size={14} />
                        Connection saved
                      </motion.span>
                    )}
                  </div>
                  <div className="flex w-full flex-col-reverse gap-3 sm:w-auto sm:flex-row">
                    <button
                      type="submit"
                      disabled={!canTest || isTesting || isSaving}
                      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-white/[0.06] px-5 text-sm font-semibold text-gray-100 ring-1 ring-white/[0.08] transition-colors hover:bg-white/[0.1] active:bg-white/[0.14] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {isTesting ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
                      {isTesting ? 'Testing connection' : 'Test connection'}
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveAndConnect}
                      disabled={!canSave || isSaving || isTesting}
                      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-orange-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-orange-500 active:bg-orange-700 disabled:cursor-not-allowed disabled:bg-white/[0.06] disabled:text-gray-500"
                    >
                      {isSaving ? <Loader2 size={16} className="animate-spin" /> : <ChevronRight size={16} />}
                      {isSaving ? 'Saving connection' : 'Save and connect'}
                    </button>
                  </div>
                </div>

                <AnimatePresence>
                  {(testResult || error) && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                    >
                      {testResult === 'success' && (
                        <div className="rounded-xl bg-emerald-500/[0.06] p-4 ring-1 ring-emerald-500/20">
                          <div className="flex gap-3">
                            <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-400" />
                            <div>
                              <h4 className="text-sm font-semibold text-emerald-300">Connection verified</h4>
                              <p className="mt-1 text-xs leading-relaxed text-emerald-100/70">{testMessage}</p>
                            </div>
                          </div>
                        </div>
                      )}
                      {testResult === 'error' && (
                        <div className="rounded-xl bg-red-500/[0.06] p-4 ring-1 ring-red-500/20">
                          <div className="flex gap-3">
                            <AlertCircle size={18} className="mt-0.5 shrink-0 text-red-400" />
                            <div>
                              <h4 className="text-sm font-semibold text-red-300">Connection failed</h4>
                              <p className="mt-1 text-xs leading-relaxed text-red-100/70">{testMessage}</p>
                            </div>
                          </div>
                        </div>
                      )}
                      {error && (
                        <div className="mt-3 rounded-xl bg-red-500/[0.06] p-4 ring-1 ring-red-500/20">
                          <div className="flex gap-3">
                            <AlertCircle size={18} className="mt-0.5 shrink-0 text-red-400" />
                            <div>
                              <h4 className="text-sm font-semibold text-red-300">Save failed</h4>
                              <p className="mt-1 text-xs leading-relaxed text-red-100/70">{error}</p>
                            </div>
                          </div>
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </form>
            )}
          </div>

          <aside className={cn(
            "border-t p-6 md:p-8 lg:border-l lg:border-t-0",
            isDark ? "border-white/[0.06] bg-[#0B0B0D]" : "border-gray-200 bg-gray-50"
          )}>
            <div className="flex h-full flex-col">
              <div className="mb-8 flex items-center justify-between gap-4">
                <div>
                  <p className={labelClass}>Live intelligence</p>
                  <h3 className={cn("mt-2 text-xl font-semibold", isDark ? "text-white" : "text-gray-950")}>
                    Signal readiness
                  </h3>
                </div>
                <span className={cn(
                  "inline-flex h-10 w-10 items-center justify-center rounded-xl",
                  hasConnectionSignal ? "bg-emerald-400/10 text-emerald-400" : "bg-orange-400/10 text-orange-400"
                )}>
                  <Radar size={20} />
                </span>
              </div>

              <div className="rounded-xl bg-white/[0.025] p-4 ring-1 ring-white/[0.05]">
                <div className="mb-4 flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-400">Connection status</span>
                  <span className={cn(
                    "rounded-md px-2 py-1 text-[10px] font-bold",
                    testResult === 'success' || fetchSuccess
                      ? "bg-emerald-400/10 text-emerald-300"
                      : testResult === 'error' || error
                        ? "bg-red-400/10 text-red-300"
                        : "bg-orange-400/10 text-orange-300"
                  )}>
                    {testResult === 'success' || fetchSuccess ? 'Verified' : testResult === 'error' || error ? 'Needs review' : 'Pending test'}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-300",
                      hasConnectionSignal ? "bg-emerald-400" : "bg-orange-500"
                    )}
                    style={{ width: `${hasConnectionSignal ? 100 : readiness}%` }}
                  />
                </div>
              </div>

              <div className="mt-5 divide-y divide-white/[0.06]">
                <InsightRow icon={ShieldCheck} label="Security model" value="Encrypted credentials" status="success" />
                <InsightRow icon={ScanSearch} label="Schema discovery" value={hasConnectionSignal ? "Ready" : "After test"} status={hasConnectionSignal ? "success" : "active"} />
                <InsightRow icon={Table2} label="Estimated tables" value={testResult === 'success' ? "Detected" : "Unknown"} status={testResult === 'success' ? "success" : "neutral"} />
                <InsightRow icon={KeyRound} label="Permissions" value="Read access expected" status="neutral" />
                <InsightRow icon={Fingerprint} label="Environment" value={isPostgres ? "PostgreSQL 5432" : dbInfo.meta || "Source"} status="active" />
              </div>

              <div className="mt-auto pt-8">
                <div className="rounded-xl bg-orange-500/[0.07] p-4 ring-1 ring-orange-500/15">
                  <p className="text-sm font-semibold text-orange-200">What happens next</p>
                  <p className="mt-2 text-xs leading-relaxed text-orange-100/65">
                    Signal turns this source into a semantic layer: tables, relationships, metadata, and analysis context become available to the AI workspace.
                  </p>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-5">
        <Benefit icon={ScanSearch} title="Discover schemas" text="Read tables, columns, and types without manual mapping." />
        <Benefit icon={GitBranch} title="Detect relationships" text="Identify keys and useful join paths for analysis." />
        <Benefit icon={Layers3} title="Generate metadata" text="Create names, descriptions, and column context." />
        <Benefit icon={Sparkles} title="Build understanding" text="Prepare the source for natural language reasoning." />
        <Benefit icon={ShieldCheck} title="Stay controlled" text="Use read-only access with encrypted credentials." />
      </section>
    </div>
  );
};

export default SetupModeView;
