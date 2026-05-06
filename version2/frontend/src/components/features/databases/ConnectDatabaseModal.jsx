import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Database, X, CheckCircle, AlertCircle, Loader2,
  Server, ChevronRight, Table, Shield, Eye, RefreshCw,
  ArrowLeft, Hash, Lock
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { databaseAPI } from '../../../services/api';
import useDatasetStore from '../../../store/datasetStore';

/* ─── DB type config ─────────────────────────────────────── */
const DB_TYPES = [
  {
    id: 'postgresql',
    label: 'PostgreSQL',
    icon: 'https://www.postgresql.org/media/img/about/press/elephant.png',
    defaultPort: 5432,
    color: '#336791',
  },
  { id: 'mysql',      label: 'MySQL',      icon: '🐬', defaultPort: 3306, color: '#4479A1' },
  {
    id: 'mongodb',
    label: 'MongoDB',
    icon: 'https://cdn.brandfetch.io/ideyyfT0Lp/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386',
    defaultPort: 27017,
    color: '#47A248',
  },
];

const INITIAL_FORM = {
  name: '',
  db_type: 'postgresql',
  host: '',
  port: 5432,
  database: '',
  username: '',
  password: '',
  ssl_mode: 'prefer',
};

/* ─── Step indicator ─────────────────────────────────────── */
const StepDot = ({ n, active, done }) => (
  <div className="flex items-center gap-2">
    <div
      className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300"
      style={{
        backgroundColor: done ? 'var(--accent-success, #22c55e)' : active ? 'var(--accent-primary)' : 'var(--bg-elevated)',
        color: done || active ? '#fff' : 'var(--text-muted)',
        border: `2px solid ${done ? 'var(--accent-success, #22c55e)' : active ? 'var(--accent-primary)' : 'var(--border)'}`,
      }}
    >
      {done ? <CheckCircle className="w-3.5 h-3.5" /> : n}
    </div>
  </div>
);

const DbTypeIcon = ({ db, active }) => {
  if (db.id === 'mysql') {
    return <div className="text-xl mb-1">{db.icon}</div>;
  }

  return (
    <div className="mx-auto mb-1 flex h-8 w-8 items-center justify-center overflow-hidden rounded-md bg-transparent/80 p-1 shadow-sm">
      <img
        src={db.icon}
        alt={db.label}
        className="h-full w-full object-contain"
        style={{ filter: active ? 'none' : 'grayscale(0.05)' }}
        referrerPolicy="no-referrer"
      />
    </div>
  );
};

/* ─── Main modal ─────────────────────────────────────────── */
const ConnectDatabaseModal = ({ isOpen, onClose, onProcessingStart }) => {
  const [step, setStep] = useState(1); // 1 = credentials, 2 = pick table
  const [form, setForm] = useState(INITIAL_FORM);
  const [testStatus, setTestStatus] = useState(null); // null | 'testing' | 'ok' | 'fail'
  const [testMsg, setTestMsg] = useState('');
  const [savedConnId, setSavedConnId] = useState(null);
  const [tables, setTables] = useState([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [selectedTable, setSelectedTable] = useState('');
  const [useCustomQuery, setUseCustomQuery] = useState(false);
  const [customQuery, setCustomQuery] = useState('');
  const [rowLimit, setRowLimit] = useState(100000);
  const [datasetName, setDatasetName] = useState('');
  const [extracting, setExtracting] = useState(false);
  const { setProcessingDataset } = useDatasetStore();

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }));

  const handleClose = () => {
    if (extracting) return;
    setStep(1);
    setForm(INITIAL_FORM);
    setTestStatus(null);
    setSavedConnId(null);
    setTables([]);
    setSelectedTable('');
    setCustomQuery('');
    setDatasetName('');
    onClose();
  };

  /* ── Step 1: Test connection ─────────────────────────── */
  const handleTest = async () => {
    setTestStatus('testing');
    setTestMsg('');
    try {
      const { data } = await databaseAPI.testConnection({
        db_type: form.db_type,
        host: form.host,
        port: Number(form.port),
        database: form.database,
        username: form.username,
        password: form.password,
        ssl_mode: form.ssl_mode,
      });
      if (data.success) {
        setTestStatus('ok');
        setTestMsg(`Connected in ${Math.round(data.response_time_ms)}ms · ${data.tables_count ?? '?'} tables found`);
      } else {
        setTestStatus('fail');
        setTestMsg(data.message || 'Connection failed');
      }
    } catch (err) {
      setTestStatus('fail');
      setTestMsg(err.response?.data?.detail || 'Could not reach the database');
    }
  };

  /* ── Step 1 → Step 2: Save + load tables ────────────── */
  const handleConnect = async () => {
    setTestStatus('testing');
    try {
      const { data } = await databaseAPI.saveConnection(form);
      setSavedConnId(data.connection_id);

      // fetch tables immediately
      setLoadingTables(true);
      setStep(2);
      const tRes = await databaseAPI.getTables(data.connection_id);
      setTables(tRes.data.tables || []);
    } catch (err) {
      setTestStatus('fail');
      setTestMsg(err.response?.data?.detail || 'Failed to save connection');
    } finally {
      setLoadingTables(false);
    }
  };

  /* ── Step 2: Extract ─────────────────────────────────── */
  const handleExtract = async () => {
    if (!useCustomQuery && !selectedTable) {
      toast.error('Select a table first');
      return;
    }
    setExtracting(true);
    try {
      const { data } = await databaseAPI.extractTable(savedConnId, {
        table_name: useCustomQuery ? null : selectedTable,
        custom_query: useCustomQuery ? customQuery : null,
        dataset_name: datasetName || undefined,
        row_limit: rowLimit,
      });
      setProcessingDataset(data.dataset_id);
      if (onProcessingStart) onProcessingStart(data.dataset_id);
      toast.success(`Extracted ${data.rows_extracted.toLocaleString()} rows — processing started!`);
      handleClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const canConnect = form.name && form.host && form.database && form.username && form.password;
  const selectedDbType = DB_TYPES.find(d => d.id === form.db_type);

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-60 overflow-y-auto">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0"
            style={{ backgroundColor: 'var(--bg-overlay)' }}
            onClick={handleClose}
          />

          <div className="flex min-h-full items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="relative w-full max-w-xl rounded-2xl overflow-hidden"
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-lg)',
              }}
              onClick={e => e.stopPropagation()}
            >
              {/* ── Header ── */}
              <div className="flex items-center justify-between p-6" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg" style={{ backgroundColor: 'var(--accent-primary-light)' }}>
                    <Database className="h-5 w-5" style={{ color: 'var(--accent-primary)' }} />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold" style={{ color: 'var(--text-header)' }}>
                      Connect Database
                    </h3>
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {step === 1 ? 'Enter your database credentials' : 'Choose a table to analyze'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {/* Step indicator */}
                  <div className="flex items-center gap-1.5">
                    <StepDot n={1} active={step === 1} done={step > 1} />
                    <div className="w-6 h-px" style={{ backgroundColor: 'var(--border)' }} />
                    <StepDot n={2} active={step === 2} done={false} />
                  </div>
                  {!extracting && (
                    <button onClick={handleClose} className="p-1.5 rounded-lg" style={{ color: 'var(--text-muted)' }}>
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* ── Body ── */}
              <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
                <AnimatePresence mode="wait">
                  {/* ════════ STEP 1 ════════ */}
                  {step === 1 && (
                    <motion.div key="step1" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} className="space-y-5">

                      {/* DB type selector */}
                      <div>
                        <label className="block text-xs font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>
                          DATABASE TYPE
                        </label>
                        <div className="grid grid-cols-3 gap-2">
                          {DB_TYPES.map(db => (
                            <motion.button
                              key={db.id}
                              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                              onClick={() => { set('db_type', db.id); set('port', db.defaultPort); setTestStatus(null); }}
                              className="p-3 rounded-xl border-2 text-center transition-all"
                              style={{
                                borderColor: form.db_type === db.id ? 'var(--accent-primary)' : 'var(--border)',
                                backgroundColor: form.db_type === db.id ? 'var(--accent-primary-light)' : 'transparent',
                              }}
                            >
                              <DbTypeIcon db={db} active={form.db_type === db.id} />
                              <div className="text-xs font-semibold" style={{ color: form.db_type === db.id ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>
                                {db.label}
                              </div>
                            </motion.button>
                          ))}
                        </div>
                      </div>

                      {/* Connection name */}
                      <Field label="CONNECTION NAME" icon={<Hash className="w-3.5 h-3.5" />}>
                        <input
                          placeholder="e.g. Production Sales DB"
                          value={form.name}
                          onChange={e => set('name', e.target.value)}
                          className="w-full bg-transparent outline-none text-sm"
                          style={{ color: 'var(--text-primary)' }}
                        />
                      </Field>

                      {/* Host + Port */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="col-span-2">
                          <Field label="HOST">
                            <input
                              placeholder="db.example.com"
                              value={form.host}
                              onChange={e => set('host', e.target.value)}
                              className="w-full bg-transparent outline-none text-sm"
                              style={{ color: 'var(--text-primary)' }}
                            />
                          </Field>
                        </div>
                        <Field label="PORT">
                          <input
                            type="number"
                            value={form.port}
                            onChange={e => set('port', Number(e.target.value))}
                            className="w-full bg-transparent outline-none text-sm"
                            style={{ color: 'var(--text-primary)' }}
                          />
                        </Field>
                      </div>

                      {/* Database name */}
                      <Field label="DATABASE NAME">
                        <input
                          placeholder="my_database"
                          value={form.database}
                          onChange={e => set('database', e.target.value)}
                          className="w-full bg-transparent outline-none text-sm"
                          style={{ color: 'var(--text-primary)' }}
                        />
                      </Field>

                      {/* Username + Password */}
                      <div className="grid grid-cols-2 gap-3">
                        <Field label="USERNAME">
                          <input
                            placeholder="admin"
                            value={form.username}
                            onChange={e => set('username', e.target.value)}
                            className="w-full bg-transparent outline-none text-sm"
                            style={{ color: 'var(--text-primary)' }}
                          />
                        </Field>
                        <Field label="PASSWORD" icon={<Lock className="w-3.5 h-3.5" />}>
                          <input
                            type="password"
                            placeholder="••••••••"
                            value={form.password}
                            onChange={e => { set('password', e.target.value); setTestStatus(null); }}
                            className="w-full bg-transparent outline-none text-sm"
                            style={{ color: 'var(--text-primary)' }}
                          />
                        </Field>
                      </div>

                      {/* Test result */}
                      <AnimatePresence>
                        {testStatus && testStatus !== 'testing' && (
                          <motion.div
                            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
                            style={{
                              backgroundColor: testStatus === 'ok' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                              border: `1px solid ${testStatus === 'ok' ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                              color: testStatus === 'ok' ? '#16a34a' : '#dc2626',
                            }}
                          >
                            {testStatus === 'ok'
                              ? <CheckCircle className="w-4 h-4 shrink-0" />
                              : <AlertCircle className="w-4 h-4 shrink-0" />}
                            <span>{testMsg}</span>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* Security note */}
                      <div className="flex items-start gap-2 px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}>
                        <Shield className="w-3.5 h-3.5 mt-0.5 shrink-0" style={{ color: 'rgb(139,92,246)' }} />
                        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          Passwords are AES-encrypted before storage and never returned in API responses.
                        </p>
                      </div>
                    </motion.div>
                  )}

                  {/* ════════ STEP 2 ════════ */}
                  {step === 2 && (
                    <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-5">

                      {/* Table picker */}
                      {!useCustomQuery && (
                        <div>
                          <label className="block text-xs font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>
                            SELECT A TABLE
                          </label>
                          {loadingTables ? (
                            <div className="flex items-center gap-2 py-4" style={{ color: 'var(--text-muted)' }}>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              <span className="text-sm">Loading tables…</span>
                            </div>
                          ) : (
                            <div className="max-h-48 overflow-y-auto rounded-xl border space-y-1 p-2" style={{ borderColor: 'var(--border)' }}>
                              {tables.length === 0 && (
                                <p className="text-sm py-3 text-center" style={{ color: 'var(--text-muted)' }}>No tables found</p>
                              )}
                              {tables.map(t => (
                                <motion.button
                                  key={t}
                                  whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
                                  onClick={() => setSelectedTable(t)}
                                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all"
                                  style={{
                                    backgroundColor: selectedTable === t ? 'var(--accent-primary-light)' : 'transparent',
                                    color: selectedTable === t ? 'var(--accent-primary)' : 'var(--text-primary)',
                                  }}
                                >
                                  <Table className="w-3.5 h-3.5 shrink-0" />
                                  <span className="text-sm font-medium">{t}</span>
                                  {selectedTable === t && <CheckCircle className="w-3.5 h-3.5 ml-auto" />}
                                </motion.button>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Custom SQL toggle */}
                      <button
                        onClick={() => { setUseCustomQuery(u => !u); setSelectedTable(''); }}
                        className="flex items-center gap-2 text-xs font-medium transition-colors"
                        style={{ color: useCustomQuery ? 'var(--accent-primary)' : 'var(--text-muted)' }}
                      >
                        <Server className="w-3.5 h-3.5" />
                        {useCustomQuery ? 'Back to table picker' : 'Use custom SQL query instead'}
                      </button>

                      {useCustomQuery && (
                        <Field label="SQL QUERY (SELECT only)">
                          <textarea
                            rows={3}
                            placeholder="SELECT * FROM orders WHERE status = 'active'"
                            value={customQuery}
                            onChange={e => setCustomQuery(e.target.value)}
                            className="w-full bg-transparent outline-none text-sm font-mono resize-none"
                            style={{ color: 'var(--text-primary)' }}
                          />
                        </Field>
                      )}

                      {/* Row limit */}
                      <div>
                        <label className="block text-xs font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>
                          ROW LIMIT — <span style={{ color: 'var(--accent-primary)' }}>{rowLimit.toLocaleString()} rows</span>
                        </label>
                        <input
                          type="range" min={1000} max={1000000} step={1000}
                          value={rowLimit}
                          onChange={e => setRowLimit(Number(e.target.value))}
                          className="w-full accent-primary"
                        />
                        <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                          <span>1K</span><span>500K</span><span>1M</span>
                        </div>
                      </div>

                      {/* Dataset name override */}
                      <Field label="DATASET NAME (optional)">
                        <input
                          placeholder={`${form.name} — ${selectedTable || 'custom query'}`}
                          value={datasetName}
                          onChange={e => setDatasetName(e.target.value)}
                          className="w-full bg-transparent outline-none text-sm"
                          style={{ color: 'var(--text-primary)' }}
                        />
                      </Field>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* ── Footer ── */}
              <div
                className="flex items-center justify-between gap-3 p-5"
                style={{ borderTop: '1px solid var(--border)', backgroundColor: 'var(--bg-elevated)' }}
              >
                {step === 2 ? (
                  <button
                    onClick={() => setStep(1)}
                    disabled={extracting}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)', backgroundColor: 'var(--bg-surface)' }}
                  >
                    <ArrowLeft className="w-3.5 h-3.5" /> Back
                  </button>
                ) : (
                  <button
                    onClick={handleClose}
                    className="px-4 py-2 rounded-lg text-sm font-medium"
                    style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)', backgroundColor: 'var(--bg-surface)' }}
                  >
                    Cancel
                  </button>
                )}

                <div className="flex items-center gap-2">
                  {step === 1 && (
                    <motion.button
                      whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                      onClick={handleTest}
                      disabled={!canConnect || testStatus === 'testing'}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all"
                      style={{
                        border: '1px solid var(--border)',
                        backgroundColor: 'var(--bg-surface)',
                        color: 'var(--text-secondary)',
                        opacity: (!canConnect || testStatus === 'testing') ? 0.5 : 1,
                      }}
                    >
                      {testStatus === 'testing'
                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Testing…</>
                        : <><RefreshCw className="w-3.5 h-3.5" /> Test</>}
                    </motion.button>
                  )}

                  <motion.button
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                    onClick={step === 1 ? handleConnect : handleExtract}
                    disabled={
                      (step === 1 && (!canConnect || testStatus === 'testing')) ||
                      (step === 2 && extracting)
                    }
                    className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-all"
                    style={{
                      backgroundColor: 'var(--accent-primary)',
                      color: '#fff',
                      opacity: (step === 1 && (!canConnect || testStatus === 'testing')) || (step === 2 && extracting) ? 0.5 : 1,
                    }}
                  >
                    {step === 1 ? (
                      testStatus === 'testing'
                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Connecting…</>
                        : <>Connect <ChevronRight className="w-3.5 h-3.5" /></>
                    ) : (
                      extracting
                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Extracting…</>
                        : <>Extract &amp; Analyze <ChevronRight className="w-3.5 h-3.5" /></>
                    )}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
};

/* ─── Reusable field wrapper ─────────────────────────────── */
const Field = ({ label, icon, children }) => (
  <div>
    <label className="flex items-center gap-1 text-xs font-semibold mb-1.5" style={{ color: 'var(--text-secondary)' }}>
      {icon}{label}
    </label>
    <div
      className="flex items-center px-3 py-2.5 rounded-xl border"
      style={{ borderColor: 'var(--border)', backgroundColor: 'var(--bg-elevated)' }}
    >
      {children}
    </div>
  </div>
);

export default ConnectDatabaseModal;
