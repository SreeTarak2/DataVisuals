// Ensures chart data is mapped to x/y keys for chart rendering
export function getXYChartData(data = [], config = {}) {
  if (!Array.isArray(data) || !config || !Array.isArray(config.columns)) return data;
  const [xKey, yKey] = config.columns;
  if (!xKey || !yKey) return data;
  return data.map(row => ({
    x: row[xKey],
    y: row[yKey]
  }));
}
// Utility to map chart data to x/y keys for chart rendering
export const mapChartDataForRendering = (data = [], config = {}) => {
  if (!Array.isArray(data) || !config || !Array.isArray(config.columns)) return data;
  const [xKey, yKey] = config.columns;
  // Only map if both keys exist
  if (!xKey || !yKey) return data;
  return data.map(row => ({
    x: row[xKey],
    y: row[yKey]
  }));
};


const normalizeChartType = (t) => {
  if (!t) return null;
  const lower = t.toString().toLowerCase();
  if (lower.includes('line')) return 'line_chart';
  if (lower.includes('bar')) return 'bar_chart';
  if (lower.includes('pie')) return 'pie_chart';
  if (lower.includes('scatter')) return 'scatter_plot';
  if (lower.includes('hist')) return 'histogram';
  // accept short forms
  if (lower === 'line') return 'line_chart';
  if (lower === 'bar') return 'bar_chart';
  if (lower === 'pie') return 'pie_chart';
  return t;
};

const ensureArray = (v) => (Array.isArray(v) ? v : (v ? [v] : []));

const validateColumns = (columns = [], availableColumns = []) => {
  if (!Array.isArray(columns) || !Array.isArray(availableColumns)) return [];
  const available = new Set(availableColumns.map(c => c.toLowerCase()));
  const missingColumns = columns.filter(col => !available.has(col.toLowerCase()));
  return missingColumns;
};

const normalizeComponent = (component = {}, availableColumns = []) => {
  const c = { ...component };

  // Infer type if missing
  if (!c.type) {
    if (c.kpi || c.kpi_cards) c.type = 'kpi';
    else if (c.charts || c.chart_type || c.chart) c.type = 'chart';
    else if (c.table || c.columns) c.type = 'table';
    else c.type = 'chart';
  }

  // Ensure title
  c.title = c.title || (c.type === 'kpi' ? 'KPI' : c.type === 'table' ? 'Table' : 'Chart');

  // Default span
  if (typeof c.span === 'undefined' || c.span === null) {
    c.span = c.type === 'kpi' ? 1 : c.type === 'chart' ? 2 : 4;
  }
  
  // Track any missing columns for error reporting
  c.missingColumns = [];

  c.config = c.config ? { ...c.config } : {};

  // Normalize chart type
  if (c.type === 'chart') {
    c.config.chart_type = normalizeChartType(c.config.chart_type || c.chart_type || c.type || 'bar_chart');
    // ensure columns are an array
    c.config.columns = ensureArray(c.config.columns || c.data_columns || (c.charts?.[0]?.data ? c.charts[0].data.map(d => d.x || d.y).filter(Boolean) : null));
    
    // Check if columns exist in dataset
    if (availableColumns.length > 0) {
      const missing = validateColumns(c.config.columns, availableColumns);
      if (missing.length > 0) {
        console.warn(`Missing columns: ${missing.join(', ')}. Available: ${availableColumns.join(', ')}`);
        c.missingColumns = missing;
        // Use first available column as fallback
        c.config.columns = c.config.columns.map(col => 
          missing.includes(col) ? availableColumns[0] : col
        );
      }
    }
    
    // fallback default columns (only if no available columns provided)
    if (!c.config.columns || c.config.columns.length === 0) {
      c.config.columns = availableColumns.length > 0 ? [availableColumns[0]] : ['category', 'value'];
    }
    
    c.config.group_by = c.config.group_by || c.config.columns[0];
    c.config.aggregation = c.config.aggregation || 'mean';
    
    // Validate group_by column exists
    if (availableColumns.length > 0 && !availableColumns.includes(c.config.group_by)) {
      c.config.group_by = c.config.columns[0] || availableColumns[0];
    }
  }

  if (c.type === 'kpi') {
    c.config.column = c.config.column || (c.config.columns && c.config.columns[0]) || c.data_columns?.[0] || 'id';
    c.config.aggregation = (c.config.aggregation || 'count').toString().toLowerCase();
    c.config.color = c.config.color || 'emerald';
    c.config.icon = c.config.icon || 'Database';
  }

  if (c.type === 'table') {
    c.config.columns = ensureArray(c.config.columns || c.columns || c.table?.columns || []);
    if (c.config.columns.length === 0) c.config.columns = ['col1', 'col2'];
  }

  return c;
};

export const normalizeDashboardConfig = (dashboard = {}, availableColumns = []) => {
  const d = { ...dashboard };
  d.components = Array.isArray(d.components) ? 
    d.components.map(c => normalizeComponent(c, availableColumns)) : [];
  
  // Track components with missing columns
  d.componentsWithErrors = d.components.filter(c => c.missingColumns && c.missingColumns.length > 0);
  
  // Keep layout_grid if present, otherwise provide sensible default
  d.layout_grid = d.layout_grid || d.layout || "repeat(4, 1fr)";
  return d;
};

export default { normalizeDashboardConfig };
