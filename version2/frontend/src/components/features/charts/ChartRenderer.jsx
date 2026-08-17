/**
 * ChartRenderer
 * =============
 * Backward-compatible re-export — delegates to renderers/index.js.
 *
 * All consumers (DashboardComponent, ObservatoryPage, etc.) import from
 * this path and get the smart dispatcher that auto-selects between
 * PlotlyRenderer and EChartsRenderer.
 *
 * See: renderers/index.js for the dispatch logic.
 *      renderers/PlotlyRenderer.jsx for Plotly-specific code.
 *      renderers/EChartsRenderer.jsx for ECharts-specific code.
 */

export { default, ChartRenderer } from './renderers';
