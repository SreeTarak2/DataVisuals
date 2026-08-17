/**
 * EChartsAdapter.test.js
 * ======================
 * Tests for the EChartsAdapter — the pure VIS-to-ECharts-option converter.
 *
 * Verifies that renderVis() produces correct ECharts option objects for
 * all series types, with particular focus on the four new ECharts-preferred
 * types: pictorial_bar, effect_scatter, map, and donut.
 */

import { describe, it, expect } from 'vitest';
import { renderVis, isVIS, visToOption } from '../EChartsAdapter';

// ── Helper: build a minimal VIS object ──────────────────────────────
// seriesOverrides = properties to merge into the first series object
// extra           = extra top-level properties (axes, variant_config, etc.)

function makeVIS(vizType, seriesOverrides = {}, extra = {}) {
  return {
    version: '1.0',
    visualization_type: vizType,
    title: `${vizType} test`,
    series: [
      {
        name: 'Series 1',
        ...seriesOverrides,
      },
    ],
    ...extra,
  };
}

// ── Skeleton / Option Structure ─────────────────────────────────────

describe('option skeleton', () => {
  it('builds a valid option skeleton with default theme', () => {
    const vis = makeVIS('bar', { x: ['A', 'B'], y: [10, 20] });
    const option = renderVis(vis);

    expect(option).toHaveProperty('backgroundColor', '#111827');
    expect(option).toHaveProperty('animation', true);
    expect(option).toHaveProperty('title.text', 'bar test');
    expect(option).toHaveProperty('xAxis.type', 'category');
    expect(option).toHaveProperty('yAxis.type', 'value');
    expect(option).toHaveProperty('tooltip.trigger', 'axis');
    expect(option).toHaveProperty('legend.top', 35);
    expect(option.series).toHaveLength(1);
  });

  it('supports light theme', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] });
    const option = renderVis(vis, { theme: 'light' });
    expect(option).toHaveProperty('backgroundColor', '#ffffff');
    expect(option.xAxis.axisLabel.color).toBe('#1F2937');
  });

  it('applies axis titles from VIS axes', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] }, {
      axes: { x: { title: 'Category' }, y: { title: 'Value' } },
    });
    const option = renderVis(vis);
    expect(option.xAxis.name).toBe('Category');
    expect(option.yAxis.name).toBe('Value');
  });

  it('handles null vis gracefully', () => {
    expect(renderVis(null)).toEqual({});
    expect(renderVis(undefined)).toEqual({});
  });

  it('handles empty series gracefully', () => {
    const option = renderVis({ version: '1.0', visualization_type: 'bar' });
    expect(option.series).toEqual([]);
  });
});

// ── Bar / Line / Scatter (foundational) ─────────────────────────────

describe('bar / line / scatter types', () => {
  it('bar → type: bar with data tuples', () => {
    const vis = makeVIS('bar', { x: ['A', 'B', 'C'], y: [10, 20, 30] });
    const option = renderVis(vis);
    const series = option.series[0];
    expect(series.type).toBe('bar');
    expect(series.data).toEqual([
      ['A', 10],
      ['B', 20],
      ['C', 30],
    ]);
  });

  it('line → type: line', () => {
    const vis = makeVIS('line', { x: [1, 2, 3], y: [4, 5, 6] });
    const option = renderVis(vis);
    expect(option.series[0].type).toBe('line');
  });
});

// ── Pictorial Bar ──────────────────────────────────────────────────

describe('pictorial_bar', () => {
  it('maps to pictorialBar series type', () => {
    const vis = makeVIS('pictorial_bar', { x: ['A', 'B'], y: [15, 25] });
    const option = renderVis(vis);
    expect(option.series[0].type).toBe('pictorialBar');
  });

  it('includes pictorial-specific config', () => {
    const vis = makeVIS('pictorial_bar', { x: ['A', 'B'], y: [15, 25] });
    const option = renderVis(vis);
    const series = option.series[0];

    expect(series).toHaveProperty('symbol', 'circle');
    expect(series).toHaveProperty('symbolRepeat', true);
    expect(series).toHaveProperty('symbolSize', [20, 10]);
  });

  it('uses custom pictorial_symbol from series', () => {
    const vis = makeVIS('pictorial_bar', {
      x: ['A'], y: [10], pictorial_symbol: 'rect',
    });
    const option = renderVis(vis);
    expect(option.series[0].symbol).toBe('rect');
  });

  it('encodes data as coordinate tuples', () => {
    const vis = makeVIS('pictorial_bar', { x: ['A', 'B'], y: [15, 25] });
    const option = renderVis(vis);
    expect(option.series[0].data).toEqual([
      ['A', 15],
      ['B', 25],
    ]);
  });
});

// ── Effect Scatter ─────────────────────────────────────────────────

describe('effect_scatter', () => {
  it('maps to effectScatter series type', () => {
    const vis = makeVIS('effect_scatter', { x: [1, 2], y: [3, 4] });
    const option = renderVis(vis);
    expect(option.series[0].type).toBe('effectScatter');
  });

  it('includes ripple effect config', () => {
    const vis = makeVIS('effect_scatter', { x: [1, 2], y: [3, 4] });
    const option = renderVis(vis);
    const series = option.series[0];

    expect(series).toHaveProperty('rippleEffect');
    expect(series.rippleEffect).toMatchObject({
      period: 4,
      scale: 2.5,
      brushType: 'stroke',
    });
  });

  it('encodes scatter data as coordinate tuples', () => {
    const vis = makeVIS('effect_scatter', { x: [10, 20], y: [30, 40] });
    const option = renderVis(vis);
    expect(option.series[0].data).toEqual([
      [10, 30],
      [20, 40],
    ]);
  });
});

// ── Map ─────────────────────────────────────────────────────────────

describe('map', () => {
  it('maps to map series type', () => {
    const vis = makeVIS('map', { locations: ['USA', 'Canada'], z_geo: [100, 50] });
    const option = renderVis(vis);
    expect(option.series[0].type).toBe('map');
  });

  it('includes geographic data with location names and values', () => {
    const vis = makeVIS('map', { locations: ['USA', 'Canada'], z_geo: [100, 50] });
    const option = renderVis(vis);
    const series = option.series[0];

    expect(series.data).toEqual([
      { name: 'USA', value: 100 },
      { name: 'Canada', value: 50 },
    ]);
  });

  it('defaults to world map with roam enabled', () => {
    const vis = makeVIS('map', { locations: ['USA'], z_geo: [100] });
    const option = renderVis(vis);
    const series = option.series[0];

    expect(series.map).toBe('world');
    expect(series.roam).toBe(true);
    expect(series.selectedMode).toBe('single');
  });

  it('supports map_name and map_roam from variant_config', () => {
    const vis = makeVIS('map', { locations: ['USA'], z_geo: [100] }, {
      variant_config: { map_name: 'usa', map_roam: false },
    });
    const option = renderVis(vis);
    const series = option.series[0];

    expect(series.map).toBe('usa');
    expect(series.roam).toBe(false);
  });

  it('includes visualMap configuration', () => {
    const vis = makeVIS('map', { locations: ['USA'], z_geo: [100] });
    const option = renderVis(vis);
    const series = option.series[0];

    expect(series).toHaveProperty('visualMap');
    expect(series.visualMap).toMatchObject({ min: 0, calculable: true });
    expect(series.visualMap.inRange.color).toEqual([
      '#e0e7ff', '#6366f1', '#312e81',
    ]);
  });

  it('handles missing z_geo gracefully (defaults to 0)', () => {
    const vis = makeVIS('map', { locations: ['USA'] });
    const option = renderVis(vis);
    expect(option.series[0].data).toEqual([
      { name: 'USA', value: 0 },
    ]);
  });

  it('handles empty locations gracefully', () => {
    const vis = makeVIS('map', { locations: [], z_geo: [] });
    const option = renderVis(vis);
    expect(option.series[0].data).toEqual([]);
  });
});

// ── Donut ──────────────────────────────────────────────────────────

describe('donut', () => {
  it('maps to pie series type (ECharts calls it pie with radius)', () => {
    const vis = makeVIS('donut', { labels: ['A', 'B'], values: [30, 70] });
    const option = renderVis(vis);
    expect(option.series[0].type).toBe('pie');
  });

  it('applies built-in donut hole radius [40%, 70%]', () => {
    const vis = makeVIS('donut', { labels: ['A', 'B'], values: [30, 70] });
    const option = renderVis(vis);
    expect(option.series[0].radius).toEqual(['40%', '70%']);
  });

  it('converts labels/values to ECharts pie data format', () => {
    const vis = makeVIS('donut', { labels: ['Alpha', 'Beta'], values: [30, 70] });
    const option = renderVis(vis);
    const series = option.series[0];

    expect(series.data).toEqual([
      { name: 'Alpha', value: 30, itemStyle: { color: '#6366f1' } },
      { name: 'Beta', value: 70, itemStyle: { color: '#06b6d4' } },
    ]);
  });

  it('includes pie-specific config: avoidLabelOverlap, emphasis', () => {
    const vis = makeVIS('donut', { labels: ['A'], values: [100] });
    const option = renderVis(vis);
    const series = option.series[0];

    expect(series.avoidLabelOverlap).toBe(true);
    expect(series.label).toEqual({ show: false });
    expect(series.emphasis).toMatchObject({
      label: { show: true, fontSize: 14, fontWeight: 'bold' },
    });
  });

  it('respects donut_hole from variant_config over the built-in default', () => {
    const vis = makeVIS('donut', { labels: ['A', 'B'], values: [50, 50] }, {
      variant_config: { donut_hole: 0.3 },
    });
    const option = renderVis(vis);
    expect(option.series[0].radius).toEqual(['30%', '100%']);
  });

  it('applies rose_type variant from variant_config', () => {
    const vis = makeVIS('donut', { labels: ['A', 'B'], values: [50, 50] }, {
      variant_config: { rose_type: 'area' },
    });
    const option = renderVis(vis);
    expect(option.series[0].roseType).toBe('area');
  });

  it('handles missing labels gracefully', () => {
    const vis = makeVIS('donut', { values: [100] });
    const option = renderVis(vis);
    expect(option.series[0].data).toEqual([]);
  });

  it('handles missing values gracefully (defaults to 0)', () => {
    const vis = makeVIS('donut', { labels: ['A'] });
    const option = renderVis(vis);
    expect(option.series[0].data).toEqual([
      { name: 'A', value: 0, itemStyle: { color: '#6366f1' } },
    ]);
  });
});

// ── Multi-series ───────────────────────────────────────────────────

describe('multi-series handling', () => {
  it('converts each series in the array', () => {
    const vis = {
      version: '1.0',
      visualization_type: 'pictorial_bar',
      title: 'multi pictorial',
      series: [
        { name: 'S1', x: ['A'], y: [10] },
        { name: 'S2', x: ['A'], y: [20] },
      ],
    };
    const option = renderVis(vis);
    expect(option.series).toHaveLength(2);
    expect(option.series[0].name).toBe('S1');
    expect(option.series[1].name).toBe('S2');
    expect(option.series[0].type).toBe('pictorialBar');
    expect(option.series[1].type).toBe('pictorialBar');
  });

  it('handles series_collection as additional series', () => {
    const vis = {
      version: '1.0',
      visualization_type: 'effect_scatter',
      title: 'multi',
      series: [{ name: 'Primary', x: [1], y: [2] }],
      series_collection: {
        series: [{ name: 'Secondary', x: [3], y: [4] }],
      },
    };
    const option = renderVis(vis);
    expect(option.series).toHaveLength(2);
  });

  it('uses fallback name when series has no name', () => {
    const vis = {
      version: '1.0',
      visualization_type: 'bar',
      series: [{ x: [1], y: [2] }],  // no name
    };
    const option = renderVis(vis);
    expect(option.series[0].name).toBe('Series 1');
  });
});

// ── Variant Config ─────────────────────────────────────────────────

describe('variant configuration', () => {
  it('applies map-related variant config to map type', () => {
    const vis = makeVIS('map', { locations: ['USA'], z_geo: [100] }, {
      variant_config: { map_name: 'usa', map_roam: false },
    });
    const option = renderVis(vis);
    expect(option.series[0].map).toBe('usa');
    expect(option.series[0].roam).toBe(false);
  });

  it('does not apply map variants to non-map types', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] }, {
      variant_config: { map_name: 'usa' },
    });
    const option = renderVis(vis);
    expect(option.series[0].map).toBeUndefined();
  });
});

// ── isVIS detection ────────────────────────────────────────────────

describe('isVIS', () => {
  it('detects VIS by visualization_type', () => {
    expect(isVIS({ visualization_type: 'bar' })).toBe(true);
    expect(isVIS({ visualization_type: 'pictorial_bar' })).toBe(true);
    expect(isVIS({ visualization_type: 'effect_scatter' })).toBe(true);
    expect(isVIS({ visualization_type: 'map' })).toBe(true);
    expect(isVIS({ visualization_type: 'donut' })).toBe(true);
  });

  it('detects VIS by version prefix', () => {
    expect(isVIS({ version: '1.0', series: [] })).toBe(true);
    expect(isVIS({ version: '1.5', series: [] })).toBe(true);
  });

  it('rejects non-VIS objects', () => {
    expect(isVIS(null)).toBeFalsy();
    expect(isVIS(undefined)).toBeFalsy();
    expect(isVIS({})).toBeFalsy();
    expect(isVIS({ title: 'chart' })).toBeFalsy();
    expect(isVIS({ data: [] })).toBeFalsy();
  });
});

// ── visToOption compatibility ──────────────────────────────────────

describe('visToOption', () => {
  it('delegates to renderVis', () => {
    const vis = makeVIS('donut', { labels: ['A'], values: [100] });
    const option = visToOption(vis, { theme: 'light' });
    expect(option.series[0].type).toBe('pie');
    expect(option.backgroundColor).toBe('#ffffff');
  });
});
