import { useState, useEffect, useMemo } from 'react';
import {
  Database,
  FileText,
  Users,
  Megaphone,
  Code2,
  Layout,
  BarChart3,
  ShoppingCart,
  Puzzle,
} from 'lucide-react';
import { dltAPI } from '../../services/api';

/* ═══════════════════════════════════════════════════════════════
   connectorCatalog — the single source of truth for the connector
   catalog. Used by both the standalone Connectors page and the
   unified "Add data" page so the two never drift apart.
   ═══════════════════════════════════════════════════════════════ */

// ── Static Connectors (existing) ──────────────────────────────────────────

export const STATIC_CONNECTORS = [
  { id: 'postgres', name: 'PostgreSQL', desc: 'Connect your PostgreSQL database for instant AI analysis', tag: 'Databases', isNew: false, image: '/postgres.png', color: 'text-blue-400', bg: 'bg-white/5' },
  { id: 'mysql', name: 'MySQL', desc: 'Connect your MySQL database for instant AI analysis', tag: 'Databases', isNew: false, image: '/mysql.png', color: 'text-orange-400', bg: 'bg-white/5' },
  { id: 'mongodb', name: 'MongoDB', desc: 'Connect your MongoDB database for instant AI analysis', tag: 'Databases', isNew: false, image: '/mongodb.png', color: 'text-green-500', bg: 'bg-white/5' },
  { id: 'csv', name: 'CSV', desc: 'Upload CSV files to instantly analyze your structured data', tag: 'Files', isNew: false, icon: FileText, color: 'text-green-400', bg: 'bg-green-400/10' },
  { id: 'excel', name: 'Excel', desc: 'Upload Excel spreadsheets (.xlsx, .xls) for automated insights', tag: 'Files', isNew: false, image: '/excel.png', color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  { id: 'tsv', name: 'TSV', desc: 'Upload TSV files to run powerful statistical analysis', tag: 'Files', isNew: false, icon: FileText, color: 'text-teal-400', bg: 'bg-teal-400/10' },
  { id: 'gsheets', name: 'Google Sheets', desc: 'Live connection to your Google Sheets', tag: 'Integrations', isNew: false, image: '/google-sheets.png', color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  { id: 'supabase', name: 'Supabase', desc: 'Connect your Supabase Postgres database for instant AI analysis', tag: 'Databases', isNew: true, image: '/supabase.png', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
];

// ── dlt Source Metadata ───────────────────────────────────────────────────

export const SOURCE_META = {
  // ── CRM & Sales ─────────────────────────────────────────────────
  salesforce:      { tag: 'CRM & Sales', icon: Users,         color: 'text-blue-400',       bg: 'bg-blue-400/10',       desc: 'Sync Salesforce accounts, opportunities, and contacts for AI-driven pipeline analysis' },
  hubspot:         { tag: 'CRM & Sales', icon: Users,         color: 'text-orange-400',     bg: 'bg-orange-400/10',     desc: 'Connect HubSpot CRM to analyze contacts, deals, and marketing performance' },
  zendesk:         { tag: 'CRM & Sales', icon: Users,         color: 'text-green-400',      bg: 'bg-green-400/10',      desc: 'Import Zendesk tickets and customer interactions for support analytics' },
  pipedrive:       { tag: 'CRM & Sales', icon: Users,         color: 'text-emerald-400',    bg: 'bg-emerald-400/10',    desc: 'Sync Pipedrive deals and pipeline data for revenue forecasting' },
  freshdesk:       { tag: 'CRM & Sales', icon: Users,         color: 'text-teal-400',       bg: 'bg-teal-400/10',       desc: 'Connect Freshdesk to analyze support tickets and agent performance' },
  zoho_crm:        { tag: 'CRM & Sales', icon: Users,         color: 'text-violet-400',     bg: 'bg-violet-400/10',     desc: 'Sync Zoho CRM accounts, leads, and deals for sales intelligence' },
  intercom:        { tag: 'CRM & Sales', icon: Users,         color: 'text-cyan-400',       bg: 'bg-cyan-400/10',       desc: 'Import Intercom conversations and contacts for customer insights' },
  // ── Marketing & Ads ─────────────────────────────────────────────
  google_ads:      { tag: 'Marketing & Ads', icon: Megaphone, color: 'text-yellow-400',     bg: 'bg-yellow-400/10',     desc: 'Analyze Google Ads campaigns, keywords, and spend for ROI optimization' },
  facebook_ads:    { tag: 'Marketing & Ads', icon: Megaphone, color: 'text-indigo-400',     bg: 'bg-indigo-400/10',     desc: 'Connect Meta Ads to analyze campaign performance and audience data' },
  linkedin_ads:    { tag: 'Marketing & Ads', icon: Megaphone, color: 'text-blue-600',       bg: 'bg-blue-600/10',       desc: 'Sync LinkedIn Ads campaigns and analytics for B2B marketing insights' },
  mailchimp:       { tag: 'Marketing & Ads', icon: Megaphone, color: 'text-amber-400',      bg: 'bg-amber-400/10',      desc: 'Import Mailchimp audiences, campaigns, and reports for email analytics' },
  klaviyo:         { tag: 'Marketing & Ads', icon: Megaphone, color: 'text-rose-400',       bg: 'bg-rose-400/10',       desc: 'Connect Klaviyo for e-commerce marketing analytics and segmentation' },
  marketo:         { tag: 'Marketing & Ads', icon: Megaphone, color: 'text-blue-500',       bg: 'bg-blue-500/10',       desc: 'Sync Marketo leads, campaigns, and programs for marketing ROI analysis' },
  // ── Engineering & Productivity ──────────────────────────────────
  github:          { tag: 'Engineering & Prod', icon: Code2,  color: 'text-gray-400',       bg: 'bg-gray-400/10',       desc: 'Analyze GitHub repositories, pull requests, and contributions' },
  gitlab:          { tag: 'Engineering & Prod', icon: Code2,  color: 'text-orange-500',     bg: 'bg-orange-500/10',     desc: 'Connect GitLab to analyze CI/CD pipelines, merge requests, and projects' },
  jira:            { tag: 'Engineering & Prod', icon: Code2,  color: 'text-blue-500',       bg: 'bg-blue-500/10',       desc: 'Sync Jira issues, sprints, and projects for engineering analytics' },
  linear:          { tag: 'Engineering & Prod', icon: Code2,  color: 'text-violet-500',     bg: 'bg-violet-500/10',     desc: 'Connect Linear to analyze issues, cycles, and team velocity' },
  asana:           { tag: 'Engineering & Prod', icon: Layout, color: 'text-pink-500',       bg: 'bg-pink-500/10',       desc: 'Import Asana projects and tasks for work management analytics' },
  monday:          { tag: 'Engineering & Prod', icon: Layout, color: 'text-yellow-500',     bg: 'bg-yellow-500/10',     desc: 'Sync Monday.com boards and items for project tracking insights' },
  trello:          { tag: 'Engineering & Prod', icon: Layout, color: 'text-teal-500',       bg: 'bg-teal-500/10',       desc: 'Connect Trello boards and cards for workflow analytics' },
  confluence:      { tag: 'Engineering & Prod', icon: FileText, color: 'text-sky-400',      bg: 'bg-sky-400/10',        desc: 'Sync Confluence pages and spaces for knowledge base analytics' },
  slack:           { tag: 'Engineering & Prod', icon: Layout, color: 'text-purple-400',     bg: 'bg-purple-400/10',     desc: 'Analyze Slack conversations and channel activity for collaboration insights' },
  notion:          { tag: 'Engineering & Prod', icon: Layout, color: 'text-gray-300',       bg: 'bg-gray-300/10',       desc: 'Connect Notion databases and pages for content analytics' },
  airtable:        { tag: 'Engineering & Prod', icon: Layout, color: 'text-green-400',      bg: 'bg-green-400/10',      desc: 'Import Airtable bases and tables for flexible data management' },
  // ── Analytics & Data ────────────────────────────────────────────
  google_analytics: { tag: 'Analytics', icon: BarChart3,      color: 'text-orange-500',     bg: 'bg-orange-500/10',     desc: 'Import Google Analytics 4 data for web and app performance insights' },
  mixpanel:        { tag: 'Analytics', icon: BarChart3,        color: 'text-purple-500',    bg: 'bg-purple-500/10',     desc: 'Connect Mixpanel for product analytics and user behavior tracking' },
  amplitude:       { tag: 'Analytics', icon: BarChart3,        color: 'text-violet-500',    bg: 'bg-violet-500/10',     desc: 'Sync Amplitude events and cohorts for product engagement analytics' },
  heap:            { tag: 'Analytics', icon: BarChart3,        color: 'text-pink-400',      bg: 'bg-pink-400/10',       desc: 'Connect Heap for auto-captured product analytics and user sessions' },
  // ── E-Commerce & Finance ────────────────────────────────────────
  shopify:         { tag: 'E-Commerce & Finance', icon: ShoppingCart, color: 'text-green-500',   bg: 'bg-green-500/10',   desc: 'Sync Shopify orders, products, and customers for e-commerce analytics' },
  stripe:          { tag: 'E-Commerce & Finance', icon: ShoppingCart, color: 'text-indigo-500',  bg: 'bg-indigo-500/10',  desc: 'Connect Stripe for payment analytics and subscription insights' },
  woocommerce:     { tag: 'E-Commerce & Finance', icon: ShoppingCart, color: 'text-purple-600',  bg: 'bg-purple-600/10',  desc: 'Import WooCommerce orders and products for online store analytics' },
  xero:            { tag: 'E-Commerce & Finance', icon: ShoppingCart, color: 'text-teal-400',    bg: 'bg-teal-400/10',    desc: 'Connect Xero for accounting and financial data analytics' },
  quickbooks:      { tag: 'E-Commerce & Finance', icon: ShoppingCart, color: 'text-green-400',   bg: 'bg-green-400/10',   desc: 'Sync QuickBooks invoices, customers, and accounts for financial insights' },
  // ── Infrastructure ──────────────────────────────────────────────
  mongodb:         { tag: 'Databases', icon: Database,        color: 'text-green-500',      bg: 'bg-green-500/10',      desc: 'Connect your MongoDB database for instant AI analysis' },
  snowflake:       { tag: 'Databases', icon: Database,        color: 'text-blue-400',       bg: 'bg-blue-400/10',       desc: 'Connect Snowflake data warehouse for cloud analytics' },
  postgresql:      { tag: 'Databases', icon: Database,        color: 'text-blue-400',       bg: 'bg-blue-400/10',       desc: 'Connect your PostgreSQL database for instant AI analysis' },
  // ── Generic / Catch-all ─────────────────────────────────────────
  rest_api:        { tag: 'Integrations', icon: Puzzle,       color: 'text-gray-400',       bg: 'bg-gray-400/10',       desc: 'Connect any REST API with configurable endpoints and authentication' },
};

// ── Static connector IDs — dlt sources with matching IDs are filtered out ──
export const STATIC_IDS = new Set(STATIC_CONNECTORS.map((c) => c.id));

export const TABS = ['All', 'Databases', 'Files', 'CRM & Sales', 'Marketing & Ads', 'Engineering & Prod', 'Analytics', 'E-Commerce & Finance', 'Integrations'];

export const FILE_CONNECTOR_IDS = ['csv', 'excel', 'tsv'];

/**
 * Fetch dlt sources from the API and merge with the static catalog.
 * dlt sources whose id collides with a static connector (e.g. mongodb)
 * are filtered out so the static entry wins.
 */
export function useConnectorCatalog() {
  const [dltSources, setDltSources] = useState([]);
  const [dltLoading, setDltLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setDltLoading(true);

    dltAPI.listSources()
      .then((res) => {
        if (!cancelled) {
          const sources = (res.data?.sources || [])
            .filter((src) => !STATIC_IDS.has(src.id))
            .map((src) => ({
              ...src,
              _sourceType: 'dlt',
            }));
          setDltSources(sources);
        }
      })
      .catch((err) => {
        console.warn('Failed to load dlt sources:', err);
      })
      .finally(() => {
        if (!cancelled) setDltLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  const allConnectors = useMemo(() => {
    const staticMapped = STATIC_CONNECTORS.map((conn) => ({
      ...conn,
      verified: false,
      _sourceType: 'static',
    }));

    const dltMapped = dltSources.map((src) => {
      const meta = SOURCE_META[src.id] || {};
      const tag = meta.tag || 'Integrations';
      return {
        id: src.id,
        name: src.name || src.id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        desc: meta.desc || `Connect ${src.name || src.id} for automated data extraction and AI-powered analysis`,
        tag,
        isNew: false,
        verified: src.verified || false,
        _sourceType: 'dlt',
        icon: meta.icon || Puzzle,
        color: meta.color || 'text-gray-400',
        bg: meta.bg || 'bg-gray-400/10',
      };
    });

    return [...staticMapped, ...dltMapped];
  }, [dltSources]);

  return { allConnectors, dltLoading };
}
