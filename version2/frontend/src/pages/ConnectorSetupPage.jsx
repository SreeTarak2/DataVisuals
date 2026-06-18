import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { cn } from "../lib/utils";
import { useTheme } from '../store/themeStore';
import { databaseAPI, datasetAPI } from '../services/api';
import useDatasetStore from '../store/datasetStore';
import { toast } from 'react-hot-toast';
import RelationshipGraph from '../components/features/databases/RelationshipGraph';

// Import Modular Sub-components
import Breadcrumbs from './connectors/components/Breadcrumbs';
import ConnectorHeader from './connectors/components/ConnectorHeader';
import ManageModeView from './connectors/components/ManageModeView';
import SetupModeView from './connectors/components/SetupModeView';

const DB_CONFIG = {
  postgres: {
    name: 'PostgreSQL',
    defaultPort: '5432',
    meta: 'RELATIONAL SQL',
    color: 'text-blue-400',
    bg: 'bg-blue-400/10',
    docUrl: 'https://www.postgresql.org/docs/',
  },
  mysql: {
    name: 'MySQL',
    defaultPort: '3306',
    meta: 'RELATIONAL',
    color: 'text-orange-400',
    bg: 'bg-orange-400/10',
    docUrl: 'https://dev.mysql.com/doc/',
  },
  mongodb: {
    name: 'MongoDB',
    defaultPort: '27017',
    meta: 'DOCUMENT',
    color: 'text-green-500',
    bg: 'bg-green-500/10',
    docUrl: 'https://www.mongodb.com/docs/',
  },
  supabase: {
    name: 'Supabase',
    defaultPort: '5432',
    meta: 'POSTGRESQL',
    color: 'text-emerald-400',
    bg: 'bg-emerald-400/10',
    docUrl: 'https://supabase.com/docs',
  },
};

const INPUT_CLASSES = {
  dark: "w-full bg-[#0D0D0F] border border-white/[0.06] rounded-lg py-2.5 px-4 text-sm text-white placeholder:text-gray-650 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/50 transition-all font-sans",
  light: "w-full bg-white border border-gray-300 rounded-lg py-2.5 px-4 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/50 transition-all font-sans",
};

const LABEL_CLASSES = {
  dark: "text-xs font-semibold uppercase tracking-wider text-gray-400",
  light: "text-xs font-semibold uppercase tracking-wider text-gray-600",
};

const ConnectorSetupPage = () => {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const connId = searchParams.get('connId');
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const { processingDataset, setProcessingDataset } = useDatasetStore();

  const isGsheets = id === 'gsheets';
  const isMongo = id === 'mongodb';
  const isSupabase = id === 'supabase';
  const isManage = !!connId && !isGsheets;

  const dbType = id === 'postgres' ? 'postgresql' : id === 'mysql' ? 'mysql' : id === 'mongodb' ? 'mongodb' : id === 'supabase' ? 'supabase' : isGsheets ? 'gsheets' : null;
  const dbInfo = DB_CONFIG[id] || { name: 'Database', defaultPort: '', meta: '', color: 'text-gray-400', bg: 'bg-white/5', docUrl: '' };

  const [form, setForm] = useState({
    name: '',
    host: '',
    port: dbInfo.defaultPort,
    database: '',
    username: '',
    password: '',
    connection_url: '',
  });

  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testMessage, setTestMessage] = useState('');
  const [savedConnId, setSavedConnId] = useState(null);
  const [error, setError] = useState(null);
  const [sheetUrl, setSheetUrl] = useState('');
  const [isFetching, setIsFetching] = useState(false);
  const [fetchSuccess, setFetchSuccess] = useState(false);

  // ---- Manage mode state ----
  const [loadedConn, setLoadedConn] = useState(null);
  const [connectionLoading, setConnectionLoading] = useState(isManage);
  const [connectionNotFound, setConnectionNotFound] = useState(false);
  const [tables, setTables] = useState([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [selectedTable, setSelectedTable] = useState('');
  const [useCustomQuery, setUseCustomQuery] = useState(false);
  const [customQuery, setCustomQuery] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [datasetName, setDatasetName] = useState('');
  const [rowLimit, setRowLimit] = useState(100000);

  // Load saved connection when connId is present
  useEffect(() => {
    if (!connId || isGsheets) return;
    setConnectionLoading(true);
    setConnectionNotFound(false);
    setLoadedConn(null);
    databaseAPI.listConnections()
      .then((res) => {
        const conns = res.data || [];
        const found = conns.find((c) => c.connection_id === connId);
        if (found) {
          setLoadedConn(found);
          setConnectionNotFound(false);
          setForm({
            name: found.name || '',
            host: found.host || '',
            port: found.port?.toString() || dbInfo.defaultPort,
            database: found.database || '',
            username: found.username || '',
            password: '',
            connection_url: '',
          });
          setSavedConnId(connId);
          // Fetch tables
          setLoadingTables(true);
          databaseAPI.getTables(connId)
            .then((tRes) => setTables(tRes.data.tables || []))
            .catch(() => {})
            .finally(() => setLoadingTables(false));
        } else {
          setConnectionNotFound(true);
        }
      })
      .catch(() => {
        setConnectionNotFound(true);
      })
      .finally(() => {
        setConnectionLoading(false);
      });
  }, [connId]);

  useEffect(() => {
    if (isManage) return;
    setForm(prev => ({
      ...prev,
      port: dbInfo.defaultPort,
      host: '',
      database: '',
      username: '',
      password: '',
      connection_url: '',
    }));
    setTestResult(null);
    setTestMessage('');
    setError(null);
    setSavedConnId(null);
  }, [id]);

  const set = (key, val) => {
    setForm(prev => ({ ...prev, [key]: val }));
    if (key !== 'name') {
      setTestResult(null);
      setTestMessage('');
      setError(null);
    }
  };

  const connectionUrlMode = isMongo || isSupabase;

  const canTest = connectionUrlMode
    ? form.connection_url.length > 0
    : form.host.length > 0 && form.database.length > 0 && form.username.length > 0 && form.password.length > 0;

  const canSave = connectionUrlMode
    ? form.name.length > 0 && form.connection_url.length > 0 && testResult === 'success'
    : form.name.length > 0 && form.host.length > 0 && form.database.length > 0 && form.username.length > 0 && form.password.length > 0 && testResult === 'success';

  const handleExtract = async () => {
    if (!useCustomQuery && !selectedTable) {
      toast.error('Select a table to extract');
      return;
    }
    setExtracting(true);
    try {
      const { data } = await databaseAPI.extractTable(connId, {
        table_name: useCustomQuery ? null : selectedTable,
        custom_query: useCustomQuery ? customQuery : null,
        dataset_name: datasetName || undefined,
        row_limit: rowLimit,
      });
      setProcessingDataset(data.dataset_id);
      toast.success('Table extraction started');
      navigate('/app/workspace');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const parsePostgresUrl = (url) => {
    try {
      const u = new URL(url);
      const parts = u.pathname.split('/').filter(Boolean);
      return {
        host: u.hostname,
        port: u.port || '5432',
        database: parts[0] || 'postgres',
        username: decodeURIComponent(u.username),
        password: decodeURIComponent(u.password),
      };
    } catch {
      return null;
    }
  };

  const buildConfig = () => {
    let cfg = { db_type: dbType };
    if (connectionUrlMode && form.connection_url) {
      if (isSupabase) {
        const parsed = parsePostgresUrl(form.connection_url);
        if (parsed) {
          cfg = { ...cfg, ...parsed, connection_url: form.connection_url };
        } else {
          cfg.connection_url = form.connection_url;
        }
      } else {
        cfg.connection_url = form.connection_url;
      }
    } else {
      cfg.host = form.host || undefined;
      cfg.port = form.port ? parseInt(form.port, 10) : undefined;
      cfg.database = form.database || undefined;
      cfg.username = form.username || undefined;
      cfg.password = form.password || undefined;
    }
    return cfg;
  };

  const handleTestConnection = async (e) => {
    if (e) e.preventDefault();
    setIsTesting(true);
    setTestResult(null);
    setTestMessage('');
    setError(null);

    try {
      const config = buildConfig();
      Object.keys(config).forEach(key => config[key] === undefined && delete config[key]);

      const response = await databaseAPI.testConnection(config);
      const data = response.data;

      if (data.success) {
        setTestResult('success');
        setTestMessage(data.tables_count !== undefined
          ? `Connected successfully. Found ${data.tables_count} tables/collections.`
          : 'Connection successful. Credentials are valid.'
        );
      } else {
        setTestResult('error');
        setTestMessage(data.message || 'Connection failed. Check your credentials.');
      }
    } catch (err) {
      setTestResult('error');
      const detail = err.response?.data?.detail || err.message || 'Connection failed. Check your credentials and network.';
      setTestMessage(typeof detail === 'string' ? detail : 'Connection failed. Please verify your credentials.');
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveAndConnect = async () => {
    setIsSaving(true);
    setError(null);

    try {
      const config = buildConfig();
      config.name = form.name;
      Object.keys(config).forEach(key => config[key] === undefined && delete config[key]);

      const response = await databaseAPI.saveConnection(config);
      const data = response.data;
      setSavedConnId(data.connection_id);
      // Notify the sidebar to refresh its Sources list
      window.dispatchEvent(new CustomEvent('db-connection-saved', {
        detail: { connection_id: data.connection_id },
      }));
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Failed to save connection.';
      setError(typeof detail === 'string' ? detail : 'Failed to save connection. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleFetchSheet = async (e) => {
    if (e) e.preventDefault();
    if (!sheetUrl.trim()) return;
    setIsFetching(true);
    setError(null);

    try {
      const response = await datasetAPI.importGoogleSheets(sheetUrl.trim());
      const data = response.data;
      if (data.success) {
        setFetchSuccess(true);
        // Navigate to datasets after short delay
        setTimeout(() => navigate('/app/datasets'), 1200);
      } else {
        setError(data.message || 'Failed to import Google Sheet.');
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Failed to import Google Sheet.';
      setError(typeof detail === 'string' ? detail : 'Connection failed. Please check the URL.');
    } finally {
      setIsFetching(false);
    }
  };

  if (isManage && connectionLoading) {
    return (
      <div className={cn(
        "h-full flex flex-col overflow-hidden relative",
        isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
      )}>
        <main className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <div className="w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
            <p className={cn("text-sm", isDark ? "text-gray-400" : "text-gray-500")}>Loading connection...</p>
          </div>
        </main>
      </div>
    );
  }

  if (isManage && connectionNotFound) {
    return (
      <div className={cn(
        "h-full flex flex-col overflow-hidden relative",
        isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
      )}>
        <main className="flex-1 flex items-center justify-center p-8">
          <div className="max-w-md text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center mx-auto">
              <svg className="w-6 h-6 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h2 className={cn("text-lg font-semibold", isDark ? "text-white" : "text-gray-900")}>
              Connection not found
            </h2>
            <p className={cn("text-sm", isDark ? "text-gray-400" : "text-gray-500")}>
              This saved connection no longer exists or the link is invalid.
            </p>
            <button
              onClick={() => navigate('/app/connectors')}
              className="px-4 py-2 text-xs font-semibold uppercase tracking-wider rounded-lg bg-orange-600 text-white hover:bg-orange-500 transition-colors cursor-pointer"
            >
              Back to Connectors
            </button>
          </div>
        </main>
      </div>
    );
  }

  if (isManage && loadedConn) {
    const connectionLabel = loadedConn.name || loadedConn.database || dbInfo.name;
    return (
      <div className={cn(
        "h-full flex flex-col overflow-hidden relative selection:bg-orange-500/20 selection:text-white transition-colors duration-300",
        isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
      )}>
        <div className="absolute top-0 left-1/3 w-[500px] h-[500px] bg-orange-500/[0.02] rounded-full blur-[140px] pointer-events-none animate-pulse-soft" />
        <main className="flex-1 overflow-y-auto px-6 py-8 md:px-12 lg:px-16">
          <div className="mx-auto max-w-[1200px] space-y-8">
            
            {/* Header & Breadcrumbs Group */}
            <div className="space-y-4">
              <Breadcrumbs
                dbName={dbInfo.name}
                isManage={true}
                navigate={navigate}
                isDark={isDark}
              />
              <ConnectorHeader
                id={id}
                dbInfo={dbInfo}
                connectionLabel={connectionLabel}
                isManage={true}
                isGsheets={false}
                loadedConn={loadedConn}
                isDark={isDark}
              />
            </div>

            <ManageModeView
              connId={connId}
              isDark={isDark}
              loadedConn={loadedConn}
              isSupabase={isSupabase}
              tables={tables}
              setTables={setTables}
              loadingTables={loadingTables}
              setLoadingTables={setLoadingTables}
              selectedTable={selectedTable}
              setSelectedTable={setSelectedTable}
              useCustomQuery={useCustomQuery}
              setUseCustomQuery={setUseCustomQuery}
              customQuery={customQuery}
              setCustomQuery={setCustomQuery}
              extracting={extracting}
              handleExtract={handleExtract}
              datasetName={datasetName}
              setDatasetName={setDatasetName}
              rowLimit={rowLimit}
              setRowLimit={setRowLimit}
            />

            {/* Table Relationships Graph */}
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
              <RelationshipGraph
                connId={connId}
                isDark={isDark}
              />
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className={cn(
      "h-full flex flex-col overflow-hidden relative selection:bg-orange-500/20 selection:text-white transition-colors duration-300",
      isDark ? "bg-[#0D0D0F]" : "bg-gray-50"
    )}>
      {/* Background Ambient Glows */}
      <div className="absolute top-0 left-1/3 w-[500px] h-[500px] bg-orange-500/[0.02] rounded-full blur-[140px] pointer-events-none animate-pulse-soft" />
      <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-orange-500/[0.015] rounded-full blur-[120px] pointer-events-none" />
      
      <main className="flex-1 overflow-y-auto px-6 py-8 md:px-12 lg:px-16">
        <div className="mx-auto max-w-[1200px] space-y-8">
          
          {/* Header & Breadcrumbs Group */}
          <div className="space-y-4">
            <Breadcrumbs
              dbName={dbInfo.name}
              isManage={false}
              navigate={navigate}
              isDark={isDark}
            />
            <ConnectorHeader
              id={id}
              dbInfo={dbInfo}
              isManage={false}
              isGsheets={isGsheets}
              isDark={isDark}
            />
          </div>

          <SetupModeView
            id={id}
            isGsheets={isGsheets}
            isMongo={isMongo}
            isSupabase={isSupabase}
            form={form}
            set={set}
            canTest={canTest}
            canSave={canSave}
            isTesting={isTesting}
            isSaving={isSaving}
            testResult={testResult}
            testMessage={testMessage}
            handleTestConnection={handleTestConnection}
            handleSaveAndConnect={handleSaveAndConnect}
            sheetUrl={sheetUrl}
            setSheetUrl={setSheetUrl}
            isFetching={isFetching}
            fetchSuccess={fetchSuccess}
            handleFetchSheet={handleFetchSheet}
            error={error}
            dbInfo={dbInfo}
            isDark={isDark}
            INPUT_CLASSES={INPUT_CLASSES}
            LABEL_CLASSES={LABEL_CLASSES}
            savedConnId={savedConnId}
          />
        </div>
      </main>
    </div>
  );
};

export default ConnectorSetupPage;
