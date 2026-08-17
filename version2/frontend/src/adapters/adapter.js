/**
 * Adapter Index
 * =============
 * Central export point for all frontend visualization adapters.
 *
 * Current adapters:
 * - PlotlyAdapter: VIS → Plotly trace/layout conversion
 * - EChartsAdapter: VIS → ECharts option conversion
 *
 * Future:
 * - VegaAdapter: VIS → Vega-Lite spec conversion
 */

export {
  renderVis as renderPlotlyVis,
  visToChartData,
  isVIS,
  isLegacyPlotly,
} from './PlotlyAdapter';

export {
  renderVis as renderEChartsVis,
  visToOption,
} from './EChartsAdapter';

// Singleton exports for default use
export { default as PlotlyAdapter } from './PlotlyAdapter';
export { default as EChartsAdapter } from './EChartsAdapter';
