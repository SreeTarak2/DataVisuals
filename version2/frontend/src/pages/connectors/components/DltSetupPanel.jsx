import React, { useState, useCallback } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ExternalLink,
  KeyRound,
  Loader2,
  ShieldCheck,
  X,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from "../../../lib/utils";
import { dltAPI } from '../../../services/api';
import { toast } from 'react-hot-toast';

// ── Credential field definitions per source type ──────────────────────────
// Each entry defines what form fields to render for that source type.
// Source types not listed here get a single generic "API Key / Token" field.

const CREDENTIAL_FIELDS = {
  // ── API Key only ─────────────────────────────────────────────────
  hubspot: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter your HubSpot API key', docUrl: 'https://knowledge.hubspot.com/integrations/how-do-i-get-my-hubspot-api-key' },
  ],
  stripe: [
    { key: 'api_key', label: 'Secret Key', type: 'password', placeholder: 'sk_live_...', docUrl: 'https://dashboard.stripe.com/apikeys' },
  ],
  github: [
    { key: 'api_key', label: 'Personal Access Token', type: 'password', placeholder: 'ghp_...', docUrl: 'https://github.com/settings/tokens' },
  ],
  notion: [
    { key: 'api_key', label: 'Integration Token', type: 'password', placeholder: 'secret_...', docUrl: 'https://www.notion.so/my-integrations' },
  ],
  slack: [
    { key: 'api_key', label: 'Bot Token', type: 'password', placeholder: 'xoxb-...', docUrl: 'https://api.slack.com/apps' },
  ],
  airtable: [
    { key: 'api_key', label: 'Personal Access Token', type: 'password', placeholder: 'pat_...', docUrl: 'https://airtable.com/create/tokens' },
  ],
  asana: [
    { key: 'api_key', label: 'Personal Access Token', type: 'password', placeholder: 'Enter your Asana PAT', docUrl: 'https://app.asana.com/0/my-apps' },
  ],
  pipedrive: [
    { key: 'api_key', label: 'API Token', type: 'password', placeholder: 'Enter your Pipedrive API token', docUrl: 'https://pipedrive.readme.io/docs/how-to-find-the-api-token' },
  ],
  intercom: [
    { key: 'api_key', label: 'Access Token', type: 'password', placeholder: 'Enter your Intercom access token', docUrl: 'https://app.intercom.com/a/apps/_/developer-hub' },
  ],
  monday: [
    { key: 'api_key', label: 'API Token', type: 'password', placeholder: 'Enter your Monday.com API token', docUrl: 'https://monday.com/developers/v2#authentication-section' },
  ],
  amplitude: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter your Amplitude API key', docUrl: 'https://amplitude.com/docs/apis/authentication' },
  ],
  heap: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter your Heap API key', docUrl: 'https://heapanalytics.com/docs/api' },
  ],
  linkedin_ads: [
    { key: 'api_key', label: 'Access Token', type: 'password', placeholder: 'AQV...', docUrl: 'https://www.linkedin.com/developers/apps' },
  ],
  gitlab: [
    { key: 'api_key', label: 'Personal Access Token', type: 'password', placeholder: 'glpat-...', docUrl: 'https://gitlab.com/-/user_settings/personal_access_tokens' },
  ],
  klaviyo: [
    { key: 'api_key', label: 'Private API Key', type: 'password', placeholder: 'pk_...', docUrl: 'https://www.klaviyo.com/account#api-keys-tab' },
  ],
  xero: [
    { key: 'api_key', label: 'Access Token', type: 'password', placeholder: 'Enter your Xero access token', docUrl: 'https://developer.xero.com/documentation/guides/how-to-guides/create-app/' },
  ],
  linear: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'lin_api_...', docUrl: 'https://linear.app/settings/api' },
  ],
  // ── API Key + extra field ──────────────────────────────────────────
  mixpanel: [
    { key: 'api_key', label: 'API Secret', type: 'password', placeholder: 'Enter your Mixpanel API secret' },
    { key: 'project_id', label: 'Project ID', type: 'text', placeholder: '123456' },
  ],
  shopify: [
    { key: 'api_key', label: 'Admin API Key', type: 'password', placeholder: 'shpat_...' },
    { key: 'subdomain', label: 'Store Subdomain', type: 'text', placeholder: 'mystore', hint: 'Without .myshopify.com' },
  ],
  zendesk: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter your Zendesk API key' },
    { key: 'subdomain', label: 'Subdomain', type: 'text', placeholder: 'mycompany', hint: 'Your Zendesk subdomain' },
  ],
  freshdesk: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter your Freshdesk API key' },
    { key: 'subdomain', label: 'Subdomain', type: 'text', placeholder: 'mycompany', hint: 'Your Freshdesk subdomain' },
  ],
  facebook_ads: [
    { key: 'api_key', label: 'Access Token', type: 'password', placeholder: 'EAAB...' },
    { key: 'account_id', label: 'Ad Account ID', type: 'text', placeholder: 'act_123456789', hint: 'From Meta Ads Manager' },
  ],
  mailchimp: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'your-api-key-us1', hint: 'Includes data center suffix' },
  ],
  // ── Multi-field SaaS / OAuth ──────────────────────────────────────
  salesforce: [
    { key: 'client_id', label: 'Client ID', type: 'text', placeholder: '3MVG9...' },
    { key: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'Enter your Connected App secret' },
    { key: 'username', label: 'Username', type: 'text', placeholder: 'user@company.com' },
    { key: 'password', label: 'Password', type: 'password', placeholder: '••••••••' },
    { key: 'security_token', label: 'Security Token', type: 'password', placeholder: 'Optional — from Salesforce setup', optional: true },
    { key: 'instance_url', label: 'Instance URL', type: 'text', placeholder: 'https://mycompany.salesforce.com', optional: true },
  ],
  google_analytics: [
    { key: 'property_id', label: 'Property ID', type: 'text', placeholder: '123456789', hint: 'GA4 property ID' },
    { key: 'client_id', label: 'Client ID', type: 'text', placeholder: '123456789.apps.googleusercontent.com' },
    { key: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'GOCSPX-...' },
    { key: 'refresh_token', label: 'Refresh Token', type: 'password', placeholder: '1//0g...' },
  ],
  google_ads: [
    { key: 'developer_token', label: 'Developer Token', type: 'password', placeholder: 'Enter your Google Ads dev token' },
    { key: 'client_id', label: 'Client ID', type: 'text', placeholder: '123456789.apps.googleusercontent.com' },
    { key: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'GOCSPX-...' },
    { key: 'refresh_token', label: 'Refresh Token', type: 'password', placeholder: '1//0g...' },
    { key: 'login_customer_id', label: 'MCC Customer ID', type: 'text', placeholder: 'Optional — for MCC accounts', optional: true },
  ],
  jira: [
    { key: 'subdomain', label: 'Subdomain', type: 'text', placeholder: 'mycompany', hint: 'yourcompany.atlassian.net' },
    { key: 'username', label: 'Email', type: 'text', placeholder: 'user@company.com' },
    { key: 'api_key', label: 'API Token', type: 'password', placeholder: 'Enter your Atlassian API token' },
  ],
  confluence: [
    { key: 'subdomain', label: 'Subdomain', type: 'text', placeholder: 'mycompany', hint: 'yourcompany.atlassian.net' },
    { key: 'username', label: 'Email', type: 'text', placeholder: 'user@company.com' },
    { key: 'api_key', label: 'API Token', type: 'password', placeholder: 'Enter your Atlassian API token' },
  ],
  trello: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter your Trello API key' },
    { key: 'token', label: 'Token', type: 'password', placeholder: 'Enter your Trello token' },
  ],
  woocommerce: [
    { key: 'domain', label: 'Store Domain', type: 'text', placeholder: 'mystore.com', hint: 'Without https://' },
    { key: 'consumer_key', label: 'Consumer Key', type: 'password', placeholder: 'ck_...' },
    { key: 'consumer_secret', label: 'Consumer Secret', type: 'password', placeholder: 'cs_...' },
  ],
  quickbooks: [
    { key: 'company_id', label: 'Company ID', type: 'text', placeholder: '1234567890' },
    { key: 'api_key', label: 'Access Token', type: 'password', placeholder: 'eyJraWQiOiIx...' },
  ],
  // ── Database-style ────────────────────────────────────────────────
  mongodb: [
    { key: 'connection_url', label: 'Connection URI', type: 'text', placeholder: 'mongodb+srv://user:pass@cluster.mongodb.net/db' },
    { key: 'database', label: 'Database Name', type: 'text', placeholder: 'production' },
  ],
  postgresql: [
    { key: 'host', label: 'Host', type: 'text', placeholder: 'db.company.internal' },
    { key: 'port', label: 'Port', type: 'text', placeholder: '5432' },
    { key: 'database', label: 'Database', type: 'text', placeholder: 'analytics' },
    { key: 'username', label: 'Username', type: 'text', placeholder: 'signal_reader' },
    { key: 'password', label: 'Password', type: 'password', placeholder: '••••••••' },
  ],
  snowflake: [
    { key: 'host', label: 'Account URL', type: 'text', placeholder: 'xy12345.snowflakecomputing.com' },
    { key: 'username', label: 'Username', type: 'text', placeholder: 'ANALYTICS_USER' },
    { key: 'password', label: 'Password', type: 'password', placeholder: '••••••••' },
    { key: 'database', label: 'Database', type: 'text', placeholder: 'ANALYTICS_DB' },
  ],
  // ── Special auth ──────────────────────────────────────────────────
  zoho_crm: [
    { key: 'api_key', label: 'Access Token', type: 'password', placeholder: '1000.xxxxx...' },
    { key: 'data_center', label: 'Data Center', type: 'select', placeholder: 'Select region', options: [
      { value: 'com', label: '.com (Global)' },
      { value: 'eu', label: '.eu (Europe)' },
      { value: 'in', label: '.in (India)' },
      { value: 'com.cn', label: '.com.cn (China)' },
      { value: 'au', label: '.au (Australia)' },
    ]},
  ],
  marketo: [
    { key: 'base_url', label: 'REST API Base URL', type: 'text', placeholder: 'https://<munchkin-id>.mktorest.com' },
    { key: 'api_key', label: 'Access Token', type: 'password', placeholder: 'Enter your Marketo access token' },
  ],
};

const INPUT_CLASSES = {
  dark: "w-full bg-[#0D0D0F] border border-white/[0.06] rounded-lg py-2.5 px-4 text-sm text-white placeholder:text-gray-650 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/50 transition-all font-sans",
  light: "w-full bg-white border border-gray-300 rounded-lg py-2.5 px-4 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/50 transition-all font-sans",
};

// ── Select-style data center picker ─────────────────────────────────────

const SelectField = ({ value, onChange, options, placeholder, fieldClass }) => (
  <select
    value={value}
    onChange={(e) => onChange(e.target.value)}
    className={cn(fieldClass, "appearance-none cursor-pointer")}
    style={{
      backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23666' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
      backgroundRepeat: 'no-repeat',
      backgroundPosition: 'right 12px center',
      paddingRight: '36px',
    }}
  >
    {placeholder && <option value="" disabled>{placeholder}</option>}
    {options.map((opt) => (
      <option key={opt.value} value={opt.value}>{opt.label}</option>
    ))}
  </select>
);

// ── DltSetupPanel ────────────────────────────────────────────────────────

const DltSetupPanel = ({ connector, isDark, onClose }) => {
  const [name, setName] = useState('');
  const [credentials, setCredentials] = useState({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  const sourceType = connector?.id;
  const fields = CREDENTIAL_FIELDS[sourceType];
  const inputClass = isDark ? INPUT_CLASSES.dark : INPUT_CLASSES.light;

  // Determine how many required fields exist to know if form is fillable
  const requiredFields = fields ? fields.filter((f) => !f.optional) : [{ key: 'api_key', label: 'API Key / Token', type: 'password', placeholder: `Enter your ${connector?.name || ''} credentials` }];
  const canSave = name.trim().length > 0 && requiredFields.every((f) => {
    const v = credentials[f.key];
    return v && v.trim().length > 0;
  });

  const setCred = useCallback((key, value) => {
    setCredentials((prev) => ({ ...prev, [key]: value }));
    setError(null);
  }, []);

  const handleSave = useCallback(async () => {
    if (!canSave) return;
    setSaving(true);
    setError(null);

    try {
      const res = await dltAPI.setupConnection({
        name: name.trim(),
        source_type: sourceType,
        credentials,
        incremental: true,
      });
      if (res.data?.connection_id) {
        setSaved(true);
        toast.success(`${connector?.name || sourceType} connection saved`);
        setTimeout(() => onClose(), 1500);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to save connection';
      setError(typeof msg === 'string' ? msg : 'Something went wrong');
      toast.error('Connection failed');
    } finally {
      setSaving(false);
    }
  }, [canSave, name, sourceType, credentials, connector, onClose]);

  // Metadata lookup (match the same icons/colors from ConnectorsPage)
  const meta = connector?.meta || {};
  const Icon = meta.icon || (() => null);
  const color = meta.color || 'text-gray-400';

  if (!connector) return null;

  return (
    <motion.aside
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', damping: 25, stiffness: 260 }}
      className={cn(
        "fixed top-0 right-0 z-50 h-full w-full sm:w-[480px] lg:w-[540px] shadow-2xl overflow-y-auto",
        isDark ? "bg-[#0D0D0F] border-l border-white/[0.06]" : "bg-white border-l border-gray-200"
      )}
    >
      {/* Backdrop (click to close) */}
      <div className="absolute inset-0 -left-8 sm:-left-16 z-[-1]">
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      </div>

      {/* Header */}
      <div className={cn(
        "sticky top-0 z-10 flex items-center justify-between p-4 border-b",
        isDark ? "bg-[#0D0D0F] border-white/[0.06]" : "bg-white border-gray-200"
      )}>
        <button
          onClick={onClose}
          className={cn(
            "flex items-center gap-2 text-sm font-semibold transition-colors cursor-pointer",
            isDark ? "text-gray-400 hover:text-white" : "text-gray-500 hover:text-gray-900"
          )}
        >
          <ChevronLeft size={16} />
          Back
        </button>
        <h2 className={cn(
          "text-sm font-semibold tracking-tight",
          isDark ? "text-white" : "text-gray-900"
        )}>
          {saved ? 'Connected' : 'Configure connector'}
        </h2>
        <button
          onClick={onClose}
          className={cn(
            "p-1 rounded-md transition-colors cursor-pointer",
            isDark ? "text-gray-500 hover:text-white hover:bg-white/5" : "text-gray-400 hover:text-gray-900 hover:bg-gray-100"
          )}
        >
          <X size={16} />
        </button>
      </div>

      {saved ? (
        // ── Success state ────────────────────────────────────────────
        <div className="flex flex-col items-center justify-center py-24 px-8 text-center">
          <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mb-6">
            <CheckCircle2 size={32} className="text-emerald-400" />
          </div>
          <h3 className={cn("text-xl font-semibold mb-2", isDark ? "text-white" : "text-gray-900")}>
            {connector.name} connected
          </h3>
          <p className={cn("text-sm max-w-sm", isDark ? "text-gray-400" : "text-gray-500")}>
            Your credentials are encrypted and the source will be synced shortly.
          </p>
        </div>
      ) : (
        <div className="p-6 space-y-8">
          {/* Connector Identity */}
          <div className="flex items-center gap-4">
            <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", meta.bg || '', color)}>
              <Icon size={24} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className={cn("text-lg font-semibold", isDark ? "text-white" : "text-gray-900")}>
                  {connector.name}
                </h3>
                {connector.verified && (
                  <span className="inline-flex items-center gap-1 text-[9px] font-bold text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded uppercase tracking-wider">
                    <ShieldCheck size={10} />
                    Verified
                  </span>
                )}
              </div>
              <p className={cn("text-xs mt-0.5", isDark ? "text-gray-500" : "text-gray-400")}>
                {connector.tag || 'Data source'}
              </p>
            </div>
          </div>

          {/* Form */}
          <div className="space-y-6">
            {/* Connection Name */}
            <label className="block space-y-2">
              <span className={cn("text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                Connection name
              </span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={`My ${connector.name} source`}
                className={inputClass}
              />
            </label>

            {/* Dynamic Credential Fields */}
            {requiredFields.map((field) => (
              <label key={field.key} className="block space-y-2">
                <span className="flex items-center justify-between">
                  <span className={cn("text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                    {field.label}
                    {field.optional && <span className="text-gray-500 font-normal lowercase ml-1">(optional)</span>}
                  </span>
                  {field.hint && <span className={cn("text-[10px] font-medium", isDark ? "text-gray-600" : "text-gray-400")}>{field.hint}</span>}
                </span>
                {field.type === 'select' ? (
                  <SelectField
                    value={credentials[field.key] || ''}
                    onChange={(v) => setCred(field.key, v)}
                    options={field.options}
                    placeholder={field.placeholder}
                    fieldClass={inputClass}
                  />
                ) : (
                  <div className="relative">
                    <input
                      type={field.type}
                      value={credentials[field.key] || ''}
                      onChange={(e) => setCred(field.key, e.target.value)}
                      placeholder={field.placeholder}
                      className={inputClass}
                      autoComplete="off"
                    />
                    {field.docUrl && (
                      <a
                        href={field.docUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-orange-400 transition-colors"
                        title={`Get ${field.label}`}
                      >
                        <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                )}
              </label>
            ))}

            {/* Extra optional fields not in requiredFields */}
            {fields && fields.filter((f) => f.optional).length > 0 && (
              <details className="group">
                <summary className={cn(
                  "text-xs font-semibold cursor-pointer transition-colors py-1",
                  isDark ? "text-gray-500 hover:text-gray-300" : "text-gray-400 hover:text-gray-600"
                )}>
                  Advanced options
                </summary>
                <div className="mt-4 space-y-4">
                  {fields.filter((f) => f.optional).map((field) => (
                    <label key={field.key} className="block space-y-2">
                      <span className={cn("text-xs font-semibold uppercase tracking-wider", isDark ? "text-gray-400" : "text-gray-600")}>
                        {field.label}
                      </span>
                      <input
                        type={field.type}
                        value={credentials[field.key] || ''}
                        onChange={(e) => setCred(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        className={inputClass}
                      />
                    </label>
                  ))}
                </div>
              </details>
            )}
          </div>

          {/* Error */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                className="rounded-xl bg-red-500/[0.06] p-4 ring-1 ring-red-500/20"
              >
                <div className="flex gap-3">
                  <AlertCircle size={18} className="mt-0.5 shrink-0 text-red-400" />
                  <div>
                    <h4 className="text-sm font-semibold text-red-300">Connection failed</h4>
                    <p className="mt-1 text-xs leading-relaxed text-red-100/70">{error}</p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Security Note */}
          <div className={cn(
            "rounded-xl p-4 flex gap-3",
            isDark ? "bg-orange-500/[0.06] ring-1 ring-orange-500/15" : "bg-orange-50 ring-1 ring-orange-200"
          )}>
            <KeyRound size={16} className="mt-0.5 shrink-0 text-orange-400" />
            <p className={cn("text-xs leading-relaxed", isDark ? "text-orange-100/70" : "text-orange-800/70")}>
              Credentials are encrypted at rest and used only for schema discovery and data extraction.
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              className={cn(
                "flex-1 min-h-10 rounded-lg text-sm font-semibold transition-colors cursor-pointer",
                isDark
                  ? "bg-white/[0.06] text-gray-200 ring-1 ring-white/[0.08] hover:bg-white/[0.1]"
                  : "bg-gray-100 text-gray-700 ring-1 ring-gray-200 hover:bg-gray-200"
              )}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!canSave || saving}
              className="flex-1 min-h-10 rounded-lg bg-orange-600 text-sm font-semibold text-white transition-colors hover:bg-orange-500 active:bg-orange-700 disabled:cursor-not-allowed disabled:bg-white/[0.06] disabled:text-gray-500 flex items-center justify-center gap-2"
            >
              {saving ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Saving
                </>
              ) : (
                'Save & connect'
              )}
            </button>
          </div>
        </div>
      )}
    </motion.aside>
  );
};

export default DltSetupPanel;
