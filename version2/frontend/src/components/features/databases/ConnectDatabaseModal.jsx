import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  DatabaseZap, X, ChevronRight, CheckCircle, AlertCircle, Loader2,
  RefreshCw, Globe, Server, Database, Lock, Eye, Hash, Table, Zap, Network, ArrowLeft, ShieldCheck,
  Cpu, Fingerprint, ArrowRight
} from 'lucide-react';
import { databaseAPI } from '../../../services/api';
import useDatasetStore from '../../../store/datasetStore';
import { useTheme } from '../../../store/themeStore';
import { toast } from 'react-hot-toast';

const DB_TYPES = [
  { id: 'postgres', label: 'Postgres', icon: 'postgres', defaultPort: '5432', meta: 'SQL CLUSTER' },
  { id: 'mysql', label: 'MySQL', icon: 'mysql', defaultPort: '3306', meta: 'RELATIONAL' },
  { id: 'mongodb', label: 'MongoDB', icon: 'mongodb', defaultPort: '27017', meta: 'DOCUMENT' },
];

const DbTypeIcon = ({ db, active }) => {
  const images = {
    postgres: '/postgres.png',
    mysql: '/mysql.png',
    mongodb: '/mongodb.png'
  };

  return (
    <div className="w-10 h-10 md:w-12 flex items-center justify-center overflow-hidden">
      <img
        src={images[db.id]}
        alt={db.label}
        className={`w-full h-full object-contain transition-all duration-300 ${active ? 'grayscale-0 opacity-100 scale-110' : 'grayscale opacity-30'}`}
      />
    </div>
  );
};

const Field = ({ label, children, icon, isDark }) => (
  <div className="flex flex-col gap-2 md:gap-3 group">
    <div className="flex items-center gap-3">
      {icon && <span className={`${isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'} group-focus-within:text-[#E85002] transition-colors`}>{icon}</span>}
      <label className={`text-[9px] md:text-[10px] font-black uppercase tracking-[0.3em] transition-colors ${isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'} group-focus-within:text-[#E85002]`}>
        {label}
      </label>
    </div>
    <div className={`border group-focus-within:border-[#E85002] transition-all transition-colors duration-500 ${
      isDark ? 'bg-black border-[#333333]' : 'bg-[#F9F9F9] border-[#E5E5E5]'
    }`}>
      {children}
    </div>
  </div>
);

const ConnectDatabaseModal = ({ isOpen, onClose, onProcessingStart, onBack }) => {
  const { processingDataset, setProcessingDataset } = useDatasetStore();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    name: '',
    db_type: 'postgres',
    host: '',
    port: '5432',
    database: '',
    username: '',
    password: '',
    connection_url: '',
  });
  const [testStatus, setTestStatus] = useState(null); // 'testing', 'ok', 'fail'
  const [testMsg, setTestMsg] = useState('');
  const [loadingTables, setLoadingTables] = useState(false);
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState('');
  const [useCustomQuery, setUseCustomQuery] = useState(false);
  const [customQuery, setCustomQuery] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [savedConnId, setSavedConnId] = useState(null);
  const [datasetName, setDatasetName] = useState('');
  const [rowLimit, setRowLimit] = useState(10000);

  const isMongo = form.db_type === 'mongodb';

  const set = (key, val) => setForm(prev => ({ ...prev, [key]: val }));

  const handleClose = () => {
    setStep(1);
    setTestStatus(null);
    onClose();
  };

  const canConnect = isMongo
    ? form.name && form.connection_url
    : form.name && form.host && form.database && form.username && form.password;

  const handleTest = async () => {
    setTestStatus('testing');
    setTestMsg('HANDSHAKE IN PROGRESS...');
    try {
      await databaseAPI.testConnection(form);
      setTestStatus('ok');
      setTestMsg('LINK ESTABLISHED');
    } catch (err) {
      setTestStatus('fail');
      setTestMsg('ERR: AUTHENTICATION FAILED');
    }
  };

  const handleConnect = async () => {
    setTestStatus('testing');
    try {
      const { data } = await databaseAPI.saveConnection(form);
      setSavedConnId(data.connection_id);
      setLoadingTables(true);
      setStep(2);
      const tRes = await databaseAPI.getTables(data.connection_id);
      setTables(tRes.data.tables || []);
    } catch (err) {
      setTestStatus('fail');
      setTestMsg('ERR: INTERNAL LINK FAILURE');
    } finally {
      setLoadingTables(false);
    }
  };

  const handleExtract = async () => {
    if (!useCustomQuery && !selectedTable) {
      toast.error('ERR: SCOPE NOT DEFINED');
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
      toast.success(`LOG: DATA STREAM INITIALIZED`);
      handleClose();
    } catch (err) {
      toast.error('ERR: SYNCHRONIZATION INTERRUPTED');
    } finally {
      setExtracting(false);
    }
  };

  const modalPortal = createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className={`fixed inset-0 z-[160] flex items-center justify-center p-0 lg:p-12 overflow-hidden backdrop-blur-sm transition-colors duration-500 ${isDark ? 'bg-black/90' : 'bg-black/30'}`}>
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className={`relative w-full max-w-7xl h-full lg:h-[820px] flex flex-col border shadow-2xl transition-all duration-500 ${
              isDark 
                ? 'bg-black border-[#333333] shadow-[0_0_100px_rgba(232,80,2,0.1)]' 
                : 'bg-white border-[#E5E5E5] shadow-[0_0_100px_rgba(0,0,0,0.05)]'
            }`}
            onClick={e => e.stopPropagation()}
          >
            {/* Body Split */}
            <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
              {/* Sidebar Protocol */}
              <div className={`w-full lg:w-[320px] xl:w-[380px] border-r flex flex-col overflow-hidden shrink-0 transition-colors duration-500 ${
                isDark ? 'bg-black border-[#333333]' : 'bg-[#F9F9F9] border-[#E5E5E5]'
              }`}>
                <div className="p-6 lg:p-8 xl:p-10 flex-1 overflow-y-auto no-scrollbar">
                  <div className="mb-12 xl:mb-16 flex items-center gap-4">
                    <div className="w-10 h-10 md:w-12 md:h-12 bg-[#E85002] flex items-center justify-center rounded-sm">
                      <Cpu className={`${isDark ? 'text-black' : 'text-white'} w-6 h-6 md:w-7 md:h-7`} strokeWidth={2.5} />
                    </div>
                    <div>
                      <h2 className={`text-xl md:text-2xl font-black tracking-tighter uppercase leading-tight transition-colors duration-500 ${
                        isDark ? 'text-[#F9F9F9]' : 'text-black'
                      }`}>DATA_INGESTION</h2>
                      <p className={`text-[8px] md:text-[10px] font-bold tracking-[0.3em] uppercase transition-colors duration-500 ${
                        isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'
                      }`}>Forge Protocol v2.0</p>
                    </div>
                  </div>

                  <div className="flex flex-col gap-8">
                    <div>
                      <p className={`text-[10px] font-black uppercase tracking-[0.4em] mb-6 transition-colors duration-500 ${
                        isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'
                      }`}>Modules</p>

                      <div className="space-y-4">
                        <ModuleTab
                          active={true}
                          icon={<Server />}
                          label="Database Sync"
                          meta="Cloud Tunnel"
                          isDark={isDark}
                        />
                        
                        <div className="pt-8">
                          <p className={`text-[9px] md:text-[10px] font-black uppercase tracking-[0.4em] mb-6 transition-colors duration-500 ${
                            isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'
                          }`}>Sequence Status</p>
                          <div className="flex flex-row lg:flex-col gap-6 lg:gap-12 overflow-x-auto lg:overflow-x-visible no-scrollbar pb-2 md:pb-0">
                            <StepIndicator
                              step={1}
                              current={step}
                              label="Auth Handshake"
                              sub="VERIFY_CREDENTIALS"
                              isDark={isDark}
                            />
                            <StepIndicator
                              step={2}
                              current={step}
                              label="Data Mapping"
                              sub="DEFINE_SCOPE"
                              isDark={isDark}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Sidebar Footer */}
                <div className={`mt-auto border-t p-8 xl:p-10 transition-colors duration-500 ${
                  isDark ? 'bg-[#000000] border-[#333333]' : 'bg-[#F9F9F9] border-[#E5E5E5]'
                }`}>
                  <div className="flex items-center gap-3 mb-6">
                    <Fingerprint className="text-[#E85002] w-5 h-5" />
                    <span className={`text-[10px] font-black tracking-[0.2em] uppercase transition-colors duration-500 ${
                      isDark ? 'text-[#F9F9F9]' : 'text-black'
                    }`}>Security Verified</span>
                  </div>
                  <div className="space-y-4">
                    <div className={`flex items-center justify-between text-[10px] font-bold uppercase tracking-widest transition-colors duration-500 ${
                      isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'
                    }`}>
                      <span>Protocol</span>
                      <span className="text-[#E85002]">AES-256</span>
                    </div>
                    <div className={`flex items-center justify-between text-[10px] font-bold uppercase tracking-widest transition-colors duration-500 ${
                      isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'
                    }`}>
                      <span>Status</span>
                      <span className="text-emerald-500">Encrypted</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Main Action Area */}
              <div className={`flex-1 relative flex flex-col overflow-hidden transition-colors duration-500 ${
                isDark ? 'bg-[#050505]' : 'bg-white'
              }`}>
                <button
                  onClick={handleClose}
                  className={`absolute top-6 right-6 md:top-8 md:right-8 lg:top-10 lg:right-10 transition-colors z-20 cursor-pointer ${
                    isDark ? 'text-[#333333] hover:text-[#E85002]' : 'text-[#A1A1A1] hover:text-[#E85002]'
                  }`}
                >
                  <X size={24} md:size={32} strokeWidth={1} />
                </button>

                {/* Body Content (Scrollable) */}
                <div className="flex-1 overflow-y-auto no-scrollbar p-6 lg:p-10 xl:p-20">
                  <AnimatePresence mode="wait">
                    {step === 1 ? (
                      <motion.div
                        key="step-1"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="space-y-8 lg:space-y-10 xl:space-y-12"
                      >
                        <div>
                          <h3 className={`text-3xl md:text-5xl xl:text-6xl font-black tracking-tighter mb-2 md:mb-4 uppercase leading-none transition-colors duration-500 ${
                            isDark ? 'text-[#F9F9F9]' : 'text-black'
                          }`}>
                            ESTABLISH <span className="text-[#E85002]">_LINK</span>
                          </h3>
                          <p className={`text-base md:text-lg xl:text-xl font-medium max-w-2xl leading-relaxed transition-colors duration-500 ${
                            isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'
                          }`}>
                            Establish high-performance secure tunnel to database infrastructure. Configure authentication protocols to enable direct data extraction.
                          </p>
                        </div>

                        <div className="space-y-4 md:space-y-6">
                          <p className={`text-[9px] md:text-[10px] font-black uppercase tracking-[0.4em] transition-colors duration-500 ${
                            isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'
                          }`}>Engine Architecture</p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 xl:gap-6">
                            {DB_TYPES.map(db => (
                              <button
                                key={db.id}
                                onClick={() => {
                                  set('db_type', db.id);
                                  set('port', db.defaultPort);
                                  setTestStatus(null);
                                  // Clear connection_url when switching away from MongoDB
                                  if (db.id !== 'mongodb') {
                                    set('connection_url', '');
                                  }
                                  // Clear individual fields when switching to MongoDB
                                  if (db.id === 'mongodb') {
                                    set('host', '');
                                    set('database', '');
                                    set('username', '');
                                    set('password', '');
                                  }
                                }}
                                className={`p-5 md:p-6 xl:p-8 border transition-all duration-300 text-left cursor-pointer ${form.db_type === db.id
                                  ? 'border-[#E85002] bg-[#E85002]/5'
                                  : isDark ? 'border-[#333333] bg-black hover:border-[#A7A7A7]' : 'border-[#E5E5E5] bg-[#F9F9F9] hover:border-[#A1A1A1]'
                                  }`}
                              >
                                <DbTypeIcon db={db} active={form.db_type === db.id} />
                                <div className="mt-6 xl:mt-8">
                                  <p className={`text-base xl:text-xl font-black tracking-tighter uppercase leading-tight ${form.db_type === db.id ? 'text-[#E85002]' : isDark ? 'text-white' : 'text-black'}`}>{db.label}</p>
                                  <p className={`text-[8px] xl:text-[10px] font-black uppercase tracking-widest transition-colors duration-500 ${
                                    isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'
                                  }`}>{db.meta}</p>
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>

                        <div className="flex flex-col gap-6 xl:gap-8 pt-4">
                            <Field label="Connection Name" icon={<Hash size={14} />} isDark={isDark}>
                            <input
                              placeholder="E.G. PRODUCTION_NODE_01"
                              value={form.name}
                              onChange={e => set('name', e.target.value)}
                              className={`w-full h-12 md:h-14 bg-transparent !bg-none appearance-none outline-none focus:ring-0 text-base md:text-lg font-black uppercase tracking-tight px-4 md:px-6 border-none transition-colors duration-500 ${
                                isDark ? 'text-white placeholder:text-[#333333]' : 'text-black placeholder:text-[#A1A1A1]'
                              }`}
                            />
                          </Field>

                          {isMongo ? (
                            <>
                              <Field label="Connection URL" icon={<Globe size={14} />} isDark={isDark}>
                                <input
                                  placeholder="mongodb+srv://user:pass@cluster.mongodb.net/db?retryWrites=true"
                                  value={form.connection_url}
                                  onChange={e => { set('connection_url', e.target.value); setTestStatus(null); }}
                                  autoComplete="off"
                                  className={`w-full h-12 md:h-14 bg-transparent !bg-none appearance-none outline-none focus:ring-0 text-base md:text-lg font-mono tracking-tight px-4 md:px-6 border-none transition-colors duration-500 ${
                                    isDark ? 'text-white placeholder:text-[#333333]' : 'text-black placeholder:text-[#A1A1A1]'
                                  }`}
                                />
                              </Field>
                              <div className={`flex items-center gap-3 px-4 py-3 border transition-colors duration-500 ${
                                isDark ? 'bg-[#0A0A0A] border-[#333333] text-[#A7A7A7]' : 'bg-[#F5F5F5] border-[#E5E5E5] text-[#666666]'
                              }`}>
                                <Database size={14} className="shrink-0" />
                                <p className="text-[9px] md:text-[10px] font-medium leading-relaxed">
                                  Paste your full MongoDB Atlas connection string. Supports <code className="font-mono font-bold text-[#E85002]">mongodb+srv://</code> and <code className="font-mono font-bold text-[#E85002]">mongodb://</code> protocols.
                                </p>
                              </div>
                            </>
                          ) : (
                            <>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 xl:gap-8">
                                <Field label="Host" icon={<Globe size={14} />} isDark={isDark}>
                                  <input
                                    placeholder="db.example.com or 127.0.0.1"
                                    value={form.host}
                                    onChange={e => set('host', e.target.value)}
                                    className={`w-full h-12 md:h-14 bg-transparent !bg-none appearance-none outline-none focus:ring-0 text-base md:text-lg font-black px-4 md:px-6 border-none transition-colors duration-500 ${
                                      isDark ? 'text-white placeholder:text-[#333333]' : 'text-black placeholder:text-[#A1A1A1]'
                                    }`}
                                  />
                                </Field>

                                <Field label="Port" icon={<Server size={14} />} isDark={isDark}>
                                  <input
                                    type="text"
                                    inputMode="numeric"
                                    pattern="[0-9]*"
                                    placeholder="5432"
                                    value={form.port}
                                    onChange={e => set('port', e.target.value.replace(/\D/g, ''))}
                                    autoComplete="off"
                                    className={`w-full h-12 md:h-14 bg-transparent !bg-none appearance-none outline-none focus:ring-0 text-base md:text-lg font-black px-4 md:px-6 border-none transition-colors duration-500 ${
                                      isDark ? 'text-white placeholder:text-[#333333]' : 'text-black placeholder:text-[#A1A1A1]'
                                    }`}
                                  />
                                </Field>
                              </div>

                              <Field label="Database" icon={<Database size={14} />} isDark={isDark}>
                                <input
                                  placeholder="e.g. analytics_db"
                                  value={form.database}
                                  onChange={e => set('database', e.target.value)}
                                  className={`w-full h-12 md:h-14 bg-transparent !bg-none appearance-none outline-none focus:ring-0 text-base md:text-lg font-black px-4 md:px-6 border-none transition-colors duration-500 ${
                                    isDark ? 'text-white placeholder:text-[#333333]' : 'text-black placeholder:text-[#A1A1A1]'
                                  }`}
                                />
                              </Field>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 xl:gap-8">
                                <Field label="Username" icon={<Lock size={14} />} isDark={isDark}>
                                  <input
                                    placeholder="e.g. admin_user"
                                    value={form.username}
                                    onChange={e => set('username', e.target.value)}
                                    className={`w-full h-12 md:h-14 bg-transparent !bg-none appearance-none outline-none focus:ring-0 text-base md:text-lg font-black px-4 md:px-6 border-none transition-colors duration-500 ${
                                      isDark ? 'text-white placeholder:text-[#333333]' : 'text-black placeholder:text-[#A1A1A1]'
                                    }`}
                                  />
                                </Field>

                                <Field label="Password" icon={<Eye size={14} />} isDark={isDark}>
                                  <input
                                    type="password"
                                    placeholder="••••••••"
                                    value={form.password}
                                    onChange={e => { set('password', e.target.value); setTestStatus(null); }}
                                    autoComplete="new-password"
                                    className={`w-full h-12 md:h-14 bg-transparent !bg-none appearance-none outline-none focus:ring-0 text-base md:text-lg font-black px-4 md:px-6 border-none transition-colors duration-500 ${
                                      isDark 
                                        ? 'text-white placeholder:text-[#333333] [&:-webkit-autofill]:shadow-[0_0_0_1000px_black_inset] [&:-webkit-autofill]:text-white' 
                                        : 'text-black placeholder:text-[#A1A1A1] [&:-webkit-autofill]:shadow-[0_0_0_1000px_white_inset] [&:-webkit-autofill]:text-black'
                                    }`}
                                  />
                                </Field>
                              </div>
                            </>
                          )}
                        </div>

                        {testStatus && testStatus !== 'testing' && (
                          <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className={`flex items-center gap-4 p-6 md:p-8 border transition-colors duration-500 ${testStatus === 'ok' 
                              ? 'border-emerald-500 text-emerald-500 bg-emerald-500/5' 
                              : 'border-[#E85002] text-[#E85002] bg-[#E85002]/5'
                              } text-[9px] md:text-[10px] font-black uppercase tracking-[0.4em]`}
                          >
                            {testStatus === 'ok' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
                            {testMsg}
                          </motion.div>
                        )}
                      </motion.div>
                    ) : (
                      <motion.div
                        key="step-2"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="space-y-8 md:space-y-12 h-full flex flex-col"
                      >
                        <div className="flex justify-between items-end">
                          <div>
                            <h3 className={`text-3xl md:text-5xl xl:text-6xl font-black tracking-tighter mb-2 md:mb-4 uppercase leading-none transition-colors duration-500 ${
                              isDark ? 'text-[#F9F9F9]' : 'text-black'
                            }`}>
                              Object <span className="text-[#E85002]">Definition</span>
                            </h3>
                            <p className={`text-base md:text-lg xl:text-xl font-medium max-w-2xl leading-relaxed transition-colors duration-500 ${
                              isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'
                            }`}>
                              Select target entity for extraction or define custom SQL scope for granular data retrieval.
                            </p>
                          </div>
                        </div>

                        <div className="flex-1 min-h-[300px] md:min-h-[400px] overflow-hidden flex flex-col gap-4 md:gap-6">
                          <div className={`flex items-center gap-6 md:gap-12 border-b transition-colors duration-500 ${
                            isDark ? 'border-[#333333]' : 'border-[#E5E5E5]'
                          }`}>
                            <button
                              onClick={() => setUseCustomQuery(false)}
                              className={`pb-4 text-[9px] md:text-[10px] font-black uppercase tracking-[0.4em] transition-all ${!useCustomQuery ? 'text-[#E85002] border-b-2 border-[#E85002]' : isDark ? 'text-[#333333] hover:text-[#A7A7A7]' : 'text-[#A1A1A1] hover:text-[#666666]'}`}
                            >
                              Table Index
                            </button>
                            <button
                              onClick={() => setUseCustomQuery(true)}
                              className={`pb-4 text-[9px] md:text-[10px] font-black uppercase tracking-[0.4em] transition-all ${useCustomQuery ? 'text-[#E85002] border-b-2 border-[#E85002]' : isDark ? 'text-[#333333] hover:text-[#A7A7A7]' : 'text-[#A1A1A1] hover:text-[#666666]'}`}
                            >
                              Custom Scope
                            </button>
                          </div>

                          <div className="flex-1 overflow-y-auto no-scrollbar py-4">
                            {!useCustomQuery ? (
                              loadingTables ? (
                                <div className={`h-full flex flex-col items-center justify-center gap-6 transition-colors duration-500 ${
                                  isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'
                                }`}>
                                  <Loader2 className="h-10 w-10 md:h-12 md:w-12 animate-spin" />
                                  <p className="text-[9px] md:text-[10px] font-black uppercase tracking-[0.5em]">Scanning Node Schema...</p>
                                </div>
                              ) : (
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-2 gap-4">
                                  {tables.map(t => (
                                    <button
                                      key={t}
                                      onClick={() => setSelectedTable(t)}
                                      className={`flex items-center gap-4 md:gap-6 p-5 md:p-6 xl:p-8 border transition-all duration-300 cursor-pointer text-left ${selectedTable === t
                                        ? 'bg-[#E85002] text-white dark:text-black border-[#E85002] shadow-lg'
                                        : isDark 
                                          ? 'bg-black text-[#A7A7A7] border-[#333333] hover:border-[#A7A7A7]' 
                                          : 'bg-[#F9F9F9] text-[#666666] border-[#E5E5E5] hover:border-[#A1A1A1]'
                                        }`}
                                    >
                                      <Table className="h-5 w-5 md:h-6 md:w-6" strokeWidth={2.5} />
                                      <span className="text-base md:text-lg font-black uppercase tracking-tighter truncate">{t}</span>
                                    </button>
                                  ))}
                                </div>
                              )
                            ) : (
                              <div className="h-full flex flex-col gap-6">
                                <Field label="SQL COMMAND" icon={<Database size={14} />} isDark={isDark}>
                                  <textarea
                                    placeholder="SELECT * FROM production_node WHERE active = true;"
                                    value={customQuery}
                                    onChange={e => setCustomQuery(e.target.value)}
                                    className={`w-full h-32 md:h-48 bg-transparent border-none outline-none focus:ring-0 text-base md:text-lg font-black p-2 md:p-4 resize-none transition-colors duration-500 ${
                                      isDark ? 'text-white placeholder:text-[#333333]' : 'text-black placeholder:text-[#A1A1A1]'
                                    }`}
                                  />
                                </Field>
                              </div>
                            )}
                          </div>
                        </div>

                        <div className={`grid grid-cols-1 md:grid-cols-2 gap-8 xl:gap-12 pt-8 xl:pt-12 border-t transition-colors duration-500 ${
                          isDark ? 'border-[#333333]' : 'border-[#E5E5E5]'
                        }`}>
                          <Field label="Throughput" icon={<Network size={14} />} isDark={isDark}>
                            <div className="w-full space-y-4 md:space-y-6 py-2 md:py-4">
                              <input
                                type="range" min={1000} max={1000000} step={1000}
                                value={rowLimit}
                                onChange={e => setRowLimit(Number(e.target.value))}
                                className={`w-full h-1 appearance-none cursor-pointer accent-[#E85002] transition-colors duration-500 ${
                                  isDark ? 'bg-[#333333]' : 'bg-[#E5E5E5]'
                                }`}
                              />
                              <div className={`flex justify-between text-[8px] md:text-[10px] font-black uppercase tracking-widest transition-colors duration-500 ${
                                isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'
                              }`}>
                                <span>1K ROWS</span>
                                <span className="text-white bg-[#E85002] px-2 py-0.5">{rowLimit.toLocaleString()} ROWS</span>
                                <span>1M ROWS</span>
                              </div>
                            </div>
                          </Field>

                          <Field label="Dataset Name" icon={<Hash size={14} />} isDark={isDark}>
                            <input
                              placeholder="E.G. NODE_EXTRACT_01"
                              value={datasetName}
                              onChange={e => setDatasetName(e.target.value)}
                              className={`w-full h-8 md:h-10 bg-transparent outline-none focus:ring-0 text-base md:text-lg font-black uppercase tracking-tight py-1 md:py-2 border-none transition-colors duration-500 ${
                                isDark ? 'text-white placeholder:text-[#333333]' : 'text-black placeholder:text-[#A1A1A1]'
                              }`}
                            />
                          </Field>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Shared Footer Area */}
                <div className={`border-t p-6 lg:p-8 xl:p-10 flex flex-col lg:flex-row items-center justify-between gap-6 lg:gap-0 min-h-[100px] lg:min-h-[120px] transition-colors duration-500 ${
                  isDark ? 'bg-[#080808] border-[#333333]' : 'bg-[#F0F0F0] border-[#E5E5E5]'
                }`}>
                  {/* On Mobile/Stacked, include the Security info here */}
                  <div className={`flex lg:hidden items-center justify-between w-full pb-4 border-b transition-colors duration-500 ${
                    isDark ? 'border-[#333333]/50' : 'border-[#E5E5E5]'
                  }`}>
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2 text-[9px] font-bold uppercase tracking-widest transition-colors duration-500 font-black">
                        <ShieldCheck size={12} className="text-emerald-500" />
                        <span className={isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'}>Security Tunnel</span>
                      </div>
                      <p className={`text-[8px] font-black uppercase tracking-widest transition-colors duration-500 ${
                        isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'
                      }`}>AES-256 GCM Active</p>
                    </div>
                    {step === 2 ? (
                      <button onClick={() => setStep(1)} className={`text-[9px] font-black uppercase tracking-widest flex items-center gap-2 ${isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'}`}>
                        <ArrowLeft size={12} /> Return
                      </button>
                    ) : onBack ? (
                      <button onClick={onBack} className={`text-[9px] font-black uppercase tracking-widest flex items-center gap-2 ${isDark ? 'text-[#A7A7A7]' : 'text-[#666666]'}`}>
                        Exit
                      </button>
                    ) : <div />}
                  </div>

                  <div className="hidden lg:block w-auto">
                    {step === 2 ? (
                      <button
                        onClick={() => setStep(1)}
                        className={`flex items-center gap-4 text-[10px] font-black uppercase tracking-[0.4em] transition-colors cursor-pointer ${
                          isDark ? 'text-[#A7A7A7] hover:text-[#E85002]' : 'text-[#666666] hover:text-[#E85002]'
                        }`}
                      >
                        <ArrowLeft className="h-5 w-5" /> Return to Authentication
                      </button>
                    ) : onBack ? (
                      <button
                        onClick={onBack}
                        className={`flex items-center gap-4 text-[10px] font-black uppercase tracking-[0.4em] transition-colors cursor-pointer ${
                          isDark ? 'text-[#A7A7A7] hover:text-[#E85002]' : 'text-[#666666] hover:text-[#E85002]'
                        }`}
                      >
                        <ArrowLeft className="h-5 w-5" /> Back
                      </button>
                    ) : (
                      <div />
                    )}
                  </div>

                  <div className="flex flex-row items-center gap-4 md:gap-6 w-full lg:w-auto">
                    {step === 1 && (
                      <button
                        onClick={handleTest}
                        disabled={!canConnect || testStatus === 'testing'}
                        className={`flex-1 lg:flex-none flex items-center justify-center gap-4 px-6 md:px-8 py-3 md:py-4 border text-[9px] md:text-[10px] font-black uppercase tracking-[0.3em] transition-all disabled:opacity-90 cursor-pointer ${
                          isDark 
                            ? 'bg-black border-[#A7A7A7] text-[#F9F9F9] hover:border-[#FF4D00] hover:text-[#FF4D00]' 
                            : 'bg-white border-[#E5E5E5] text-black hover:border-[#FF4D00] hover:text-[#FF4D00]'
                        }`}
                      >
                        {testStatus === 'testing' ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                        <span className="hidden sm:inline">Test Connection</span>
                        <span className="sm:hidden">Test</span>
                      </button>
                    )}

                    <button
                      onClick={step === 1 ? handleConnect : handleExtract}
                      disabled={(step === 1 && !canConnect) || extracting || testStatus === 'testing'}
                      className={`flex-1 lg:flex-none flex items-center justify-center gap-4 px-8 md:px-10 py-3 md:py-4 text-[10px] md:text-[11px] font-black uppercase tracking-[0.3em] transition-all active:scale-[0.98] border-2 disabled:opacity-90 cursor-pointer ${step === 2
                        ? 'bg-[#00FF94] text-black border-[#00FF94] hover:bg-[#00E685] shadow-[0_0_40px_rgba(0,255,148,0.2)]'
                        : 'bg-[#FF4D00] text-white dark:text-black border-[#FF4D00] hover:bg-[#FF6A00] shadow-[0_0_40px_rgba(255,77,0,0.2)]'
                        }`}
                    >
                      {step === 1 ? (
                        <>Connect <span className="hidden sm:inline">Database</span> <ChevronRight className="h-4 w-4 md:h-5 md:w-5" strokeWidth={4} /></>
                      ) : (
                        extracting ? <><Loader2 className="h-4 w-4 md:h-5 md:w-5 animate-spin" /> Syncing...</> : <>Engage Forge <Zap className="h-4 w-4 md:h-5 md:w-5" fill="currentColor" /></>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );

  return modalPortal;
};

/* ─── Sidebar Module Tab ────────────────────────────────── */
const ModuleTab = ({ active, icon, label, meta, isDark }) => {
  return (
    <div
      className={`group w-full flex items-center gap-6 p-6 transition-all duration-300 relative ${active
          ? 'bg-[#E85002] text-white dark:text-[#000000]'
          : isDark 
            ? 'bg-transparent text-[#A7A7A7] border border-[#333333]' 
            : 'bg-transparent text-[#666666] border border-[#E5E5E5]'
        } cursor-default`}
    >
      <div className={`${active ? 'text-white dark:text-[#000000]' : isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'} transition-colors`}>
        {React.cloneElement(icon, { size: 32, strokeWidth: 2 })}
      </div>

      <div className="text-left flex-1">
        <p className="font-black text-sm uppercase tracking-tighter mb-0.5">
          {label}
        </p>
        <p className={`text-[9px] font-bold uppercase tracking-[0.2em] ${active ? 'text-white/80 dark:text-[#000000]/60' : isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'}`}>
          {meta}
        </p>
      </div>

      {active && (
        <ArrowRight className={`w-6 h-6 ${active ? 'text-white dark:text-black' : ''}`} />
      )}
    </div>
  );
};

/* ─── Sidebar Step Indicator ────────────────────────────── */
const StepIndicator = ({ step, current, label, sub, isDark }) => {
  const active = current === step;
  const done = current > step;

  return (
    <div className="flex items-center gap-4 md:gap-8 shrink-0">
      <div className={`w-10 h-10 md:w-14 md:h-14 flex items-center justify-center text-[10px] md:text-[11px] font-black transition-all duration-500 ${active
        ? 'bg-[#E85002] text-white dark:text-black'
        : done
          ? isDark ? 'bg-[#333333] text-[#A7A7A7]' : 'bg-[#E5E5E5] text-[#666666]'
          : isDark ? 'bg-black text-[#333333] border border-[#333333]' : 'bg-white text-[#A1A1A1] border border-[#E5E5E5]'
        }`}>
        {done ? <CheckCircle size={20} md:size={24} /> : `0${step}`}
      </div>
      <div className="text-left">
        <p className={`text-sm md:text-base font-black tracking-tighter uppercase mb-0.5 transition-colors duration-500 ${
          active ? isDark ? 'text-[#F9F9F9]' : 'text-black' : isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'
        }`}>{label}</p>
        <p className={`text-[8px] md:text-[10px] font-bold uppercase tracking-[0.2em] transition-colors duration-500 ${
          active ? 'text-[#E85002]' : isDark ? 'text-[#333333]' : 'text-[#A1A1A1]'
        }`}>{sub}</p>
      </div>
    </div>
  );
};

export default ConnectDatabaseModal;
