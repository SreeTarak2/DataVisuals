/**
 * chartConstants.js
 * =================
 * Shared constants for chart types, aggregation options, and KPI formats.
 * Used by CanvasCardContent, CardVerticalConfig, and any other chart UI.
 *
 * Single source of truth — add a new chart type here and it shows up everywhere.
 */

export const CHART_TYPES = [
  // Comparison
  { id: 'bar', label: 'Bar', group: 'Comparison' },
  { id: 'grouped_bar', label: 'Grouped Bar', group: 'Comparison' },
  { id: 'stacked_bar', label: 'Stacked Bar', group: 'Comparison' },
  { id: 'radar', label: 'Radar', group: 'Comparison' },
  // Trends
  { id: 'line', label: 'Line', group: 'Trends' },
  { id: 'area', label: 'Area', group: 'Trends' },
  { id: 'multi_line', label: 'Multi Line', group: 'Trends' },
  // Distributions
  { id: 'scatter', label: 'Scatter', group: 'Distributions' },
  { id: 'heatmap', label: 'Heatmap', group: 'Distributions' },
  { id: 'box_plot', label: 'Box Plot', group: 'Distributions' },
  { id: 'histogram', label: 'Histogram', group: 'Distributions' },
  // Parts of a whole
  { id: 'pie', label: 'Pie', group: 'Composition' },
  { id: 'donut', label: 'Donut', group: 'Composition' },
  { id: 'treemap', label: 'Treemap', group: 'Composition' },
  { id: 'sunburst', label: 'Sunburst', group: 'Composition' },
  { id: 'funnel', label: 'Funnel', group: 'Composition' },
  // Advanced
  { id: 'bubble', label: 'Bubble', group: 'Advanced' },
  { id: 'candlestick', label: 'Candlestick', group: 'Advanced' },
  { id: 'sankey', label: 'Sankey Flow', group: 'Advanced' },
  { id: 'graph', label: 'Network Graph', group: 'Advanced' },
  { id: 'gauge', label: 'Gauge', group: 'Advanced' },
  { id: 'waterfall', label: 'Waterfall', group: 'Advanced' },
];

export const CHART_TYPE_GROUPS = [
  'Comparison',
  'Trends',
  'Distributions',
  'Composition',
  'Advanced',
];

export const AGG_OPTIONS = [
  { id: 'sum', label: 'Sum' },
  { id: 'mean', label: 'Average' },
  { id: 'median', label: 'Median' },
  { id: 'count', label: 'Count' },
  { id: 'max', label: 'Max' },
  { id: 'min', label: 'Min' },
];

export const KPI_FORMATS = [
  { id: 'number', label: 'Number' },
  { id: 'integer', label: 'Integer' },
  { id: 'currency', label: 'Currency' },
  { id: 'percentage', label: 'Percentage' },
];
