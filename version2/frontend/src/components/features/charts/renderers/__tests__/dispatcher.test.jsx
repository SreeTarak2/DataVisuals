/**
 * dispatcher.test.jsx
 * ===================
 * System tests for the ChartRenderer dispatcher (renderers/index.jsx).
 *
 * Verifies that ALL chart data — VIS objects, Plotly trace arrays,
 * and {data, layout} packages — routes to EChartsRenderer after
 * conversion via plotlyToECharts.
 *
 * The dispatcher is now ECharts-only (no more PlotlyRenderer routing).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// ── Mock: only the heavy ECharts renderer ────────────────────────────

vi.mock('../EChartsRenderer', () => ({
  default: function MockECharts({ option }) {
    // Expose option metadata for assertions
    const seriesCount = option?.series?.length || 0;
    const seriesTypes = (option?.series || []).map(s => s.type);
    return (
      <div data-testid="echarts-renderer">
        <span data-testid="echarts-series-count">{seriesCount}</span>
        <span data-testid="echarts-series-types">{JSON.stringify(seriesTypes)}</span>
        <span data-testid="echarts-theme">{option?.backgroundColor}</span>
      </div>
    );
  },
  EChartsRenderer: function MockECharts({ option }) {
    return <div data-testid="echarts-renderer">echarts</div>;
  },
}));

// ── Imports ─────────────────────────────────────────────────────────

import ChartRenderer from '../index';

// ── Helpers ─────────────────────────────────────────────────────────

function makeVIS(vizType, overrides = {}) {
  return {
    version: '1.0',
    visualization_type: vizType,
    title: `${vizType} chart`,
    series: [{ name: 'Series 1', x: [1, 2, 3], y: [4, 5, 6] }],
    ...overrides,
  };
}

// ── Tests ───────────────────────────────────────────────────────────

describe('ChartRenderer dispatcher (ECharts-only)', () => {
  beforeEach(() => {
    cleanup();
  });

  // ── All types → EChartsRenderer ──
  describe('All chart types dispatch to EChartsRenderer', () => {
    it.each([
      // ECharts-native types
      ['graph', 'echarts-native'],
      ['sankey', 'echarts-native'],
      ['parallel', 'echarts-native'],
      ['lines', 'echarts-native'],
      ['tree', 'echarts-native'],
      ['theme_river', 'echarts-native'],
      ['pictorial_bar', 'echarts-native'],
      ['effect_scatter', 'echarts-native'],
      ['map', 'echarts-native'],
      // Plotly-compatible types (now also ECharts)
      ['bar', 'plotly-compat'],
      ['line', 'plotly-compat'],
      ['pie', 'plotly-compat'],
      ['scatter', 'plotly-compat'],
      ['heatmap', 'plotly-compat'],
      ['treemap', 'plotly-compat'],
      ['radar', 'plotly-compat'],
      ['candlestick', 'plotly-compat'],
    ])('%s (%s) → EChartsRenderer', (vizType) => {
      render(<ChartRenderer data={makeVIS(vizType)} chartType={vizType} />);
      expect(screen.getByTestId('echarts-renderer')).toBeInTheDocument();
    });
  });

  // ── Legacy data (non-VIS) ──
  describe('Legacy data routes through plotlyToECharts → EChartsRenderer', () => {
    it('Plotly trace arrays → EChartsRenderer', () => {
      const plotlyData = [
        { x: [1, 2, 3], y: [4, 5, 6], type: 'scatter', mode: 'lines' },
      ];
      render(<ChartRenderer data={plotlyData} chartType="line" />);
      expect(screen.getByTestId('echarts-renderer')).toBeInTheDocument();
    });

    it('{data, layout} object → EChartsRenderer', () => {
      const chartPackage = {
        data: [{ x: [1, 2], y: [3, 4], type: 'bar' }],
        layout: { title: 'Test' },
      };
      render(<ChartRenderer data={chartPackage} chartType="bar" />);
      expect(screen.getByTestId('echarts-renderer')).toBeInTheDocument();
    });

    it('empty array → EChartsRenderer', () => {
      render(<ChartRenderer data={[]} chartType="line" />);
      expect(screen.getByTestId('echarts-renderer')).toBeInTheDocument();
    });

    it('null data → EChartsRenderer with empty option', () => {
      render(<ChartRenderer data={null} />);
      expect(screen.getByTestId('echarts-renderer')).toBeInTheDocument();
    });

    it('undefined (no data prop) → EChartsRenderer with empty option', () => {
      render(<ChartRenderer />);
      expect(screen.getByTestId('echarts-renderer')).toBeInTheDocument();
    });
  });

  // ── Theme passthrough ──
  describe('Theme prop reaches EChartsRenderer', () => {
    it('default theme is transparent background (ECharts canvas)', () => {
      render(<ChartRenderer data={makeVIS('bar')} chartType="bar" />);
      // ECharts uses 'transparent' as default dark bg
      expect(screen.getByTestId('echarts-theme').textContent).toBe('transparent');
    });
  });

  // ── Series conversion from Plotly trace arrays ──
  describe('Series conversion via plotlyToECharts', () => {
    it('creates bar series from Plotly trace array', () => {
      render(<ChartRenderer data={[{ x: ['A', 'B'], y: [1, 2], type: 'bar' }]} chartType="bar" />);
      const count = screen.getByTestId('echarts-series-count');
      expect(Number(count.textContent)).toBeGreaterThan(0);
    });
  });
});
