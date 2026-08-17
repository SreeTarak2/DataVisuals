/**
 * chatUtils.js — Shared Constants & Helpers for the Chat Panel
 *
 * Extracted from the monolithic SideChatPanel.jsx to support
 * modular components: ModernReasoningBlock, ChatMessage,
 * QueryResultTable, CopyButton.
 */

// ─── Copilot Mode Display Configuration ───────────
export const COPILOT_MODES = {
  analyst:      { label: 'AI Analyst',         icon: '🧠' },
  sql_analyst:  { label: 'SQL Analyst',        icon: '⚙️' },
  investigator: { label: 'Deep Investigator',  icon: '🔍' },
  dashboarder:  { label: 'Dashboard Designer', icon: '📊' },
  chart_expert: { label: 'Chart Expert',       icon: '📈' },
  report_writer:{ label: 'Report Writer',      icon: '📝' },
  data_prep:    { label: 'Data Prep',          icon: '🔧' },
};

export const RATE_LIMIT_TOTAL = 30;

// ─── Component Intent Detection ────────────────────
export const COMPONENT_INTENT_PATTERNS = [
  // KPI patterns
  { type: 'kpi', regex: /^(show|add|display|create|put|give me)\s+(me\s+)?(a\s+)?(kpi|metric|card|number|total|sum|average|avg|count)\s+(of|for|on)\s+(.+)/i },
  { type: 'kpi', regex: /^(what'?s?\s+)?(the\s+)?(total|sum|average|avg|count|mean|median)\s+(of\s+)?(.+)/i },
  // Chart patterns
  { type: 'chart', regex: /^(show|add|display|create|plot|draw|make)\s+(me\s+)?(a\s+)?(chart|graph|visualization|viz|plot)\s+(of|for|on)\s+(.+)/i },
  { type: 'chart', regex: /^(show|plot|chart|graph)\s+(me\s+)?(.+)\s+(by|across|vs|versus|against)\s+(.+)/i },
  { type: 'chart', regex: /^(bar|line|pie|scatter|area|histogram)\s+(chart|graph|plot|of|for)\s+(.+)/i },
];

export const AGGREGATION_MAP = {
  total: 'sum', sum: 'sum',
  average: 'mean', avg: 'mean', mean: 'mean',
  median: 'median',
  count: 'count', 'number of': 'count',
  max: 'max', highest: 'max', peak: 'max',
  min: 'min', lowest: 'min',
};

export const CHART_TYPE_MAP = {
  bar: 'bar', 'bar chart': 'bar',
  line: 'line', 'line chart': 'line', trend: 'line',
  pie: 'pie', 'pie chart': 'pie',
  scatter: 'scatter', 'scatter plot': 'scatter',
  area: 'area', 'area chart': 'area',
  histogram: 'histogram', hist: 'histogram', distribution: 'histogram',
};

// ─── Animation Variants ────────────────────────────
export const msgVariants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: 'easeOut' } },
};

// ─── Helpers ────────────────────────────────────────

export const formatTime = (ts) => {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

export const formatTableValue = (value) => {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  if (typeof value === 'boolean') return value ? 'True' : 'False';
  return String(value);
};

export const getTableColumns = (table) => {
  if (!table?.columns?.length) {
    const firstRow = table?.rows?.[0];
    return firstRow && typeof firstRow === 'object'
      ? Object.keys(firstRow).map((key) => ({ key, label: key.replace(/_/g, ' ') }))
      : [];
  }
  return table.columns.map((column) => (
    typeof column === 'string'
      ? { key: column, label: column.replace(/_/g, ' ') }
      : { key: column.key, label: column.label || String(column.key).replace(/_/g, ' ') }
  )).filter((column) => column.key);
};

export const findBestColumnMatch = (text, columnNames) => {
  if (!text || !columnNames.length) return null;
  const normalized = text.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim();
  const words = normalized.split(/\s+/).filter(w => w.length > 1);

  // Exact match
  for (const col of columnNames) {
    if (col.toLowerCase() === normalized) return col;
  }

  // Contains match
  for (const col of columnNames) {
    const colLower = col.toLowerCase();
    if (words.some(w => colLower.includes(w)) || colLower.includes(normalized)) return col;
  }

  // Fuzzy: first word match
  if (words.length > 0) {
    for (const col of columnNames) {
      if (col.toLowerCase().includes(words[0])) return col;
    }
  }

  return null;
};

export const detectComponentIntent = (message, columnNames = []) => {
  const trimmed = message.trim();

  for (const pattern of COMPONENT_INTENT_PATTERNS) {
    const match = trimmed.match(pattern.regex);
    if (!match) continue;

    const intent = { type: pattern.type, raw: trimmed };

    if (pattern.type === 'kpi') {
      const aggWord = match[1] || match[3] || '';
      const colPart = match[4] || match[5] || '';
      intent.aggregation = AGGREGATION_MAP[aggWord.toLowerCase()] || 'sum';
      intent.column = findBestColumnMatch(colPart, columnNames);
      intent.title = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
    } else if (pattern.type === 'chart') {
      const chartWord = match[1] || match[3] || '';
      const colPart = match[4] || match[5] || match[3] || '';
      const groupPart = match[5] || match[4] || '';
      intent.chart_type = CHART_TYPE_MAP[chartWord.toLowerCase()] || 'bar';
      intent.column = findBestColumnMatch(colPart, columnNames);
      intent.group_by = findBestColumnMatch(groupPart, columnNames);
      intent.aggregation = 'sum';
      intent.title = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
    }

    if (intent.column) return intent;
  }

  return null;
};
