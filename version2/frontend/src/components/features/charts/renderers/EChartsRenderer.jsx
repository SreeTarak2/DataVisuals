/**
 * EChartsRenderer
 * ===============
 * Standalone React component for rendering ECharts visualizations.
 *
 * Handles the full echarts lifecycle:
 * - Static import of echarts (always available — declared in package.json)
 * - init(), setOption(), resize(), dispose()
 * - Loading, error, and empty states
 * - ResizeObserver-based responsive resizing
 * - echarts.connect() group support for shared hover/tooltip across charts
 *
 * Usage:
 *   <EChartsRenderer option={echartsOption} style={{ height: '100%' }} />
 *
 * Integration: renderers/index.js dispatches to this for ECharts-native types.
 */

import React, { useEffect, useRef, useState } from 'react';
import { BarChart3, AlertTriangle } from 'lucide-react';
import * as echarts from 'echarts';

// ── Global chart group for echarts.connect ────────────────────────
const DASHBOARD_GROUP = 'datasage-dashboard';
let groupConnected = false;

/**
 * Register a chart instance into the shared dashboard group.
 * This enables `echarts.connect(DASHBOARD_GROUP)` which syncs
 * tooltips, highlights, and axis pointers across all charts.
 * `connect()` is called only once regardless of how many chart
 * instances mount.
 */
function registerGroup(chartInstance) {
  if (!chartInstance) return;
  try {
    chartInstance.group = DASHBOARD_GROUP;
    if (!groupConnected) {
      echarts.connect(DASHBOARD_GROUP);
      groupConnected = true;
    }
  } catch (e) {
    // Silently fail — connect is best-effort
  }
}

const EChartsRenderer = ({ option, style = {}, onPointClick, chartId }) => {
  const containerRef = useRef(null);
  const instanceRef = useRef(null);
  const resizeObserverRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let chartInstance = null;
    let isMounted = true;

    const initChart = async () => {
      try {
        setIsLoading(true);
        setError(null);

        if (!isMounted || !containerRef.current) {
          setIsLoading(false);
          return;
        }

        chartInstance = echarts.init(containerRef.current, null, {
          renderer: 'canvas',
        });
        instanceRef.current = chartInstance;

        // Register into shared group for cross-chart hover sync
        registerGroup(chartInstance);

        if (option && Object.keys(option).length > 0) {
          chartInstance.setOption(option, true);
        }

        // ── Click handler with double-click detection for drill-down ──
        if (onPointClick) {
          chartInstance.on('click', (params) => {
            onPointClick({
              x: params.name ?? params.value?.[0] ?? null,
              y: params.value ?? null,
              seriesName: params.seriesName ?? '',
              pointIndex: params.dataIndex,
            });
          });
        }

        // ── Brush-selected event for cross-filtering ──
        chartInstance.on('brushSelected', (params) => {
          const brushedIndices = params.batch?.[0]?.selected?.[0]?.dataIndex || [];
          if (brushedIndices.length > 0 && chartInstance.getOption()?.series?.[0]?.data) {
            const data = chartInstance.getOption().series[0].data;
            const brushedValues = brushedIndices.map(idx => {
              const item = data[idx];
              return Array.isArray(item) ? item[0] : item?.name ?? item;
            });
            // Dispatch custom event for cross-filtering
            window.dispatchEvent(new CustomEvent('chart-brush', {
              detail: { values: brushedValues, chartId, seriesIndex: params.batch[0].selected[0].seriesIndex },
            }));
          }
        });

        // ── Brush-cleared event → clear cross-filter ──
        // Fires when user clicks the clear button in the brush toolbox
        chartInstance.on('brushcleared', () => {
          window.dispatchEvent(new CustomEvent('chart-brush-clear', {
            detail: { chartId },
          }));
        });

        setIsLoading(false);
      } catch (err) {
        console.error('ECharts load error:', err);
        if (isMounted) {
          setError(err.message || 'Failed to render ECharts');
          setIsLoading(false);
        }
      }
    };

    initChart();

    if (containerRef.current?.parentElement) {
      resizeObserverRef.current = new ResizeObserver(() => {
        if (instanceRef.current) instanceRef.current.resize();
      });
      resizeObserverRef.current.observe(containerRef.current.parentElement);
    }

    return () => {
      isMounted = false;
      if (resizeObserverRef.current) resizeObserverRef.current.disconnect();
      if (chartInstance) {
        try { chartInstance.dispose(); } catch (e) { /* ignore */ }
        instanceRef.current = null;
      }
    };
  }, []);

  /** Update option when props change */
  useEffect(() => {
    if (instanceRef.current && option && Object.keys(option).length > 0) {
      instanceRef.current.setOption(option, true);
      instanceRef.current.resize();
    }
  }, [option]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '200px', ...style }}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', minHeight: '200px', visibility: isLoading ? 'hidden' : 'visible' }}
      />
      {isLoading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6C6E79', pointerEvents: 'none' }}>
          <div style={{ textAlign: 'center' }}><BarChart3 size={24} style={{ marginBottom: '8px', opacity: 0.5, display: 'inline-block' }} /><div style={{ fontSize: '14px', opacity: 0.7 }}>Loading chart...</div></div>
        </div>
      )}
      {error && !isLoading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444' }}>
          <div style={{ textAlign: 'center' }}><AlertTriangle size={24} style={{ marginBottom: '8px', opacity: 0.7, display: 'inline-block' }} /><div style={{ fontSize: '14px', marginBottom: '4px' }}>Chart Error</div><div style={{ fontSize: '12px', opacity: 0.7 }}>{error}</div></div>
        </div>
      )}
    </div>
  );
};

export default EChartsRenderer;
export { EChartsRenderer, DASHBOARD_GROUP };
