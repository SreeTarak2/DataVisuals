/**
 * renderers/index.js
 * ==================
 * ECharts-only chart renderer.
 *
 * Converts all backend Plotly-format chart data into ECharts options
 * via the plotlyToECharts converter. Supports 30+ chart types.
 *
 * Features:
 * - dataZoom slider + inside zoom for interactive exploration
 * - echarts.connect group for shared hover/tooltip across charts
 * - Brush selection for cross-filtering
 * - Double-click drill-down
 *
 * Usage:
 *   import ChartRenderer from './renderers';
 *   <ChartRenderer data={[...]} chartType="line" />
 */

import React, { memo, useMemo, useId } from 'react';
import { plotlyToECharts, applyDimEffect } from '../../../../utils/plotlyToECharts';
import EChartsRenderer from './EChartsRenderer';

/**
 * ChartRenderer
 * -------------
 * ECharts-only renderer. Accepts Plotly-format trace arrays, VIS objects,
 * or {data, layout} packages. Converts them to ECharts options and renders
 * via EChartsRenderer — with shared hover, dataZoom, and brush support.
 *
 * Props:
 *   data         — Plotly trace array, VIS object, or {data, layout, ...}
 *   layout       — layout overrides (not all Plotly keys apply to ECharts)
 *   style        — container style overrides
 *   chartType    — chart type string (bar, line, pie, sankey, graph, etc.)
 *   onPointClick — click handler receiving {x, y, seriesName, pointIndex}
 *   chartTitle   — optional title override
 *   crossFilters — optional [{ field, value }, ...] filter context. Only
 *                  values on THIS chart's own field (chartFilterField) dim
 *                  the chart — filtering only propagates to visuals sharing
 *                  the field. Multiple values on the field keep all of them
 *                  lit (multi-select OR). A legacy single crossFilter
 *                  ({ field, value } or plain string) is still accepted.
 *   chartFilterField — the dimension this chart is grouped by
 *   theme        — 'dark' (default) or 'light'
 */
const ChartRenderer = memo(({
  data,
  layout = {},
  style = {},
  chartType = 'bar',
  onPointClick,
  chartTitle,
  crossFilters,
  crossFilter,
  chartFilterField,
  theme = 'dark',
}) => {
  // Stable ID for echarts.connect group membership
  const chartId = useId();

  const option = useMemo(() => {
    if (!data) return {};

    // Common options for the converter
    const opts = { title: chartTitle || '', theme };

    let echartsOption;

    // Case 1: VIS object (has visualization_type)
    if (typeof data === 'object' && !Array.isArray(data) && data.visualization_type) {
      echartsOption = plotlyToECharts([], chartType, layout, {
        ...opts,
        title: chartTitle || data.title,
      });
    }

    // Case 2: {data: [...], layout: {...}} or {traces: [...], layout: {...}}
    else if (typeof data === 'object' && !Array.isArray(data) && (data.data || data.traces)) {
      const traces = data.data || data.traces || [];
      echartsOption = plotlyToECharts(traces, chartType, { ...layout, ...data.layout }, {
        ...opts,
        title: chartTitle || data.title || data.explanation || '',
      });
    }

    // Case 3: Plotly trace array
    else if (Array.isArray(data)) {
      echartsOption = plotlyToECharts(data, chartType, layout, opts);
    }

    // ── Cross-filter dim (multi-select, multi-field) ──
    // Only dim when THIS chart's field has active filter values. Charts on a
    // different dimension are left untouched — cross-filtering only propagates
    // to visuals sharing the filtered field. When the field has multiple
    // selected values, all of them stay lit (OR); everything else dims.
    const legacy = typeof crossFilter === 'string'
      ? { field: null, value: crossFilter }
      : crossFilter;
    const entries = Array.isArray(crossFilters) && crossFilters.length > 0
      ? crossFilters
      : legacy
        ? [legacy]
        : [];
    if (echartsOption && entries.length > 0) {
      const ownValues = entries
        .filter((f) => !f?.field || !chartFilterField || f.field === chartFilterField)
        .map((f) => f?.value)
        .filter((v) => v !== undefined && v !== null && v !== '');
      if (ownValues.length > 0) {
        echartsOption = applyDimEffect(echartsOption, ownValues);
      }
    }

    return echartsOption || {};
  }, [data, layout, chartType, chartTitle, crossFilters, crossFilter, chartFilterField, theme]);

  return (
    <EChartsRenderer
      option={option}
      style={style}
      onPointClick={onPointClick}
      chartId={chartId}
    />
  );
});

export default ChartRenderer;
export { ChartRenderer };

