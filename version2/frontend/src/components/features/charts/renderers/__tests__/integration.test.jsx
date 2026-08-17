/**
 * integration.test.jsx
 * ====================
 * Integration tests for the full plotlyToECharts → EChartsRenderer pipeline.
 *
 * Tests the real plotlyToECharts converter with mock EChartsRenderer,
 * verifying that Plotly-format traces are correctly converted to
 * ECharts option objects.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// ── Mock: only the heavy ECharts renderer ────────────────────────────

vi.mock('../EChartsRenderer', () => ({
  default: function MockECharts({ option }) {
    // Expose option metadata so tests can assert on converter output
    const seriesInfo = option?.series?.map((s) => ({
      type: s.type,
      name: s.name,
      dataLen: Array.isArray(s.data) ? s.data.length : 0,
    }));
    return (
      <div data-testid="echarts-renderer">
        <span data-testid="echarts-series">{JSON.stringify(seriesInfo)}</span>
        <span data-testid="echarts-theme">{option?.backgroundColor}</span>
        <span data-testid="echarts-datazoom">{option?.dataZoom ? 'yes' : 'no'}</span>
        <span data-testid="echarts-brush">{option?.brush ? 'yes' : 'no'}</span>
      </div>
    );
  },
}));

// ── Import the real dispatcher ──────────────────────────────────────

import ChartRenderer from '../index';

// ── Test data creators ──────────────────────────────────────────────

function makeTraceArray(chartType, dataOverrides = {}) {
  const baseTraces = {
    bar: [{ x: ['A', 'B', 'C'], y: [10, 20, 15], type: 'bar' }],
    line: [{ x: [1, 2, 3], y: [4, 5, 6], type: 'scatter', mode: 'lines' }],
    scatter: [{ x: [1, 2, 3], y: [4, 5, 6], type: 'scatter', mode: 'markers' }],
    pie: [{ labels: ['Alpha', 'Beta'], values: [30, 70], type: 'pie' }],
    heatmap: [{ z: [[1, 2], [3, 4]], type: 'heatmap' }],
    treemap: [{
      ids: ['/a', '/a/b', '/a/c'],
      parents: ['', '/a', '/a'],
      labels: ['root', 'b', 'c'],
      values: [100, 40, 60],
      type: 'treemap',
    }],
    donut: [{ labels: ['X', 'Y'], values: [50, 50], type: 'pie', hole: 0.4 }],
    sankey: [{
      type: 'sankey',
      nodes: [{ name: 'A' }, { name: 'B' }, { name: 'C' }],
      links: [{ source: 'A', target: 'B', value: 10 }, { source: 'B', target: 'C', value: 5 }],
    }],
    graph: [{
      type: 'graph',
      nodes: [{ name: 'A' }, { name: 'B' }],
      links: [{ source: 'A', target: 'B', value: 1 }],
    }],
  };
  return (baseTraces[chartType] || baseTraces.bar).map(t => ({ ...t, ...dataOverrides }));
}

// ── Tests ───────────────────────────────────────────────────────────

describe('Integration: plotlyToECharts pipeline', () => {
  beforeEach(() => {
    cleanup();
  });

  // ── ECharts series conversion ──
  describe('Plotly traces → ECharts series conversion', () => {
    it('bar traces → ECharts bar series', () => {
      render(<ChartRenderer data={makeTraceArray('bar')} chartType="bar" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('bar');
      expect(series[0].dataLen).toBe(3);
    });

    it('line traces → ECharts line series', () => {
      render(<ChartRenderer data={makeTraceArray('line')} chartType="line" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('line');
      expect(series[0].dataLen).toBe(3);
    });

    it('scatter traces → ECharts scatter series', () => {
      render(<ChartRenderer data={makeTraceArray('scatter')} chartType="scatter" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('scatter');
    });

    it('pie traces → ECharts pie series', () => {
      render(<ChartRenderer data={makeTraceArray('pie')} chartType="pie" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('pie');
      expect(series[0].dataLen).toBe(2);
    });

    it('treemap traces → ECharts treemap series', () => {
      render(<ChartRenderer data={makeTraceArray('treemap')} chartType="treemap" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('treemap');
    });

    it('heatmap traces → ECharts heatmap series', () => {
      render(<ChartRenderer data={makeTraceArray('heatmap')} chartType="heatmap" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('heatmap');
    });

    it('sankey traces → ECharts sankey series', () => {
      render(<ChartRenderer data={makeTraceArray('sankey')} chartType="sankey" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('sankey');
    });

    it('graph traces → ECharts graph series', () => {
      render(<ChartRenderer data={makeTraceArray('graph')} chartType="graph" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('graph');
    });

    it('donut traces → ECharts pie series (donut is pie with hole)', () => {
      render(<ChartRenderer data={makeTraceArray('donut')} chartType="donut" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(1);
      expect(series[0].type).toBe('pie');
    });
  });

  // ── Interactive features (dataZoom, brush) ──
  describe('Interactive features added to ECharts option', () => {
    it('bar chart gets dataZoom + brush', () => {
      render(<ChartRenderer data={makeTraceArray('bar')} chartType="bar" />);
      expect(screen.getByTestId('echarts-datazoom').textContent).toBe('yes');
      expect(screen.getByTestId('echarts-brush').textContent).toBe('yes');
    });

    it('line chart gets dataZoom + brush', () => {
      render(<ChartRenderer data={makeTraceArray('line')} chartType="line" />);
      expect(screen.getByTestId('echarts-datazoom').textContent).toBe('yes');
      expect(screen.getByTestId('echarts-brush').textContent).toBe('yes');
    });

    it('pie chart does NOT get dataZoom or brush', () => {
      render(<ChartRenderer data={makeTraceArray('pie')} chartType="pie" />);
      expect(screen.getByTestId('echarts-datazoom').textContent).toBe('no');
      expect(screen.getByTestId('echarts-brush').textContent).toBe('no');
    });

    it('sankey chart does NOT get dataZoom or brush', () => {
      render(<ChartRenderer data={makeTraceArray('sankey')} chartType="sankey" />);
      expect(screen.getByTestId('echarts-datazoom').textContent).toBe('no');
      expect(screen.getByTestId('echarts-brush').textContent).toBe('no');
    });

    it('graph does NOT get dataZoom or brush', () => {
      render(<ChartRenderer data={makeTraceArray('graph')} chartType="graph" />);
      expect(screen.getByTestId('echarts-datazoom').textContent).toBe('no');
      expect(screen.getByTestId('echarts-brush').textContent).toBe('no');
    });

    it('treemap does NOT get dataZoom or brush', () => {
      render(<ChartRenderer data={makeTraceArray('treemap')} chartType="treemap" />);
      expect(screen.getByTestId('echarts-datazoom').textContent).toBe('no');
      expect(screen.getByTestId('echarts-brush').textContent).toBe('no');
    });

    it('heatmap does NOT get dataZoom or brush', () => {
      render(<ChartRenderer data={makeTraceArray('heatmap')} chartType="heatmap" />);
      expect(screen.getByTestId('echarts-datazoom').textContent).toBe('no');
      expect(screen.getByTestId('echarts-brush').textContent).toBe('no');
    });
  });

  // ── Multi-series ──
  describe('Multi-series traces', () => {
    it('converts multi-series bar traces', () => {
      const multiData = [
        { name: 'S1', x: ['A', 'B'], y: [10, 20], type: 'bar' },
        { name: 'S2', x: ['A', 'B'], y: [30, 40], type: 'bar' },
      ];
      render(<ChartRenderer data={multiData} chartType="bar" />);
      const series = JSON.parse(screen.getByTestId('echarts-series').textContent);
      expect(series).toHaveLength(2);
      expect(series[0].name).toBe('S1');
      expect(series[1].name).toBe('S2');
      expect(series[0].type).toBe('bar');
      expect(series[1].type).toBe('bar');
    });
  });

  // ── Error handling ──
  describe('Error handling', () => {
    it('renders EChartsRenderer with empty option for null data', () => {
      render(<ChartRenderer data={null} />);
      expect(screen.getByTestId('echarts-renderer')).toBeInTheDocument();
    });

    it('renders EChartsRenderer with empty option for empty array', () => {
      render(<ChartRenderer data={[]} chartType="bar" />);
      expect(screen.getByTestId('echarts-renderer')).toBeInTheDocument();
    });
  });

  // ── Theme ──
  describe('Theme handling', () => {
    it('dark theme (default) → transparent background (ECharts canvas)', () => {
      render(<ChartRenderer data={makeTraceArray('bar')} chartType="bar" />);
      // EChartsWith transparent bg for dark theme so parent shows through
      expect(screen.getByTestId('echarts-theme').textContent).toBe('transparent');
    });
  });
});
