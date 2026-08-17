/**
 * PlotlyAdapter.test.js
 * =====================
 * Tests for the PlotlyAdapter — the VIS-to-Plotly-traces converter.
 *
 * Verifies that renderVis() produces correct Plotly trace arrays and
 * layouts for all series types, with focus on the four new ECharts-
 * preferred types that fall back to Plotly rendering.
 */

import { describe, it, expect } from 'vitest';
import { renderVis, isVIS, isLegacyPlotly, visToChartData } from '../PlotlyAdapter';

// ── Helper: build a minimal VIS object ──────────────────────────────
// seriesOverrides = properties to merge into the first series object
// extra           = extra top-level properties (axes, narrative, etc.)

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

// ── Result structure ───────────────────────────────────────────────

describe('result structure', () => {
  it('returns traces array and layout object', () => {
    const vis = makeVIS('bar', { x: ['A', 'B'], y: [10, 20] });
    const result = renderVis(vis);

    expect(result).toHaveProperty('traces');
    expect(result).toHaveProperty('layout');
    expect(result).toHaveProperty('type', 'chart');
    expect(result).toHaveProperty('chart_type', 'bar');
    expect(result).toHaveProperty('title', 'bar test');
    expect(result).toHaveProperty('meta');
    expect(result.meta).toHaveProperty('success', true);
    expect(Array.isArray(result.traces)).toBe(true);
    expect(typeof result.layout).toBe('object');
  });

  it('handles null vis', () => {
    expect(renderVis(null)).toEqual({ traces: [], layout: {} });
    expect(renderVis(undefined)).toEqual({ traces: [], layout: {} });
  });

  it('handles empty series', () => {
    const result = renderVis({ version: '1.0', visualization_type: 'bar' });
    expect(result.traces).toEqual([]);
    expect(result.meta.success).toBe(false);
  });
});

// ── Pictorial Bar → Plotly bar trace ───────────────────────────────

describe('pictorial_bar → Plotly bar trace', () => {
  it('maps to bar trace type', () => {
    const vis = makeVIS('pictorial_bar', { x: ['A', 'B'], y: [15, 25] });
    const { traces } = renderVis(vis);
    expect(traces[0].type).toBe('bar');
  });

  it('passes x/y data through', () => {
    const vis = makeVIS('pictorial_bar', { x: ['A', 'B', 'C'], y: [10, 20, 30] });
    const { traces } = renderVis(vis);
    expect(traces[0].x).toEqual(['A', 'B', 'C']);
    expect(traces[0].y).toEqual([10, 20, 30]);
  });

  it('assigns marker color from palette', () => {
    const vis = makeVIS('pictorial_bar', { x: ['A'], y: [10] });
    const { traces } = renderVis(vis);
    expect(traces[0].marker).toHaveProperty('color');
    expect(traces[0].marker).toHaveProperty('line');
    expect(traces[0].marker.line).toHaveProperty('width', 0);
  });

  it('does NOT include ECharts-specific pictorial config (symbol, symbolRepeat)', () => {
    const vis = makeVIS('pictorial_bar', { x: ['A'], y: [10] });
    const { traces } = renderVis(vis);
    // Plotly has no concept of pictorial bar symbols
    expect(traces[0]).not.toHaveProperty('symbol');
    expect(traces[0]).not.toHaveProperty('symbolRepeat');
  });
});

// ── Effect Scatter → Plotly scatter trace ──────────────────────────

describe('effect_scatter → Plotly scatter trace', () => {
  it('maps to scatter trace type', () => {
    const vis = makeVIS('effect_scatter', { x: [1, 2], y: [3, 4] });
    const { traces } = renderVis(vis);
    expect(traces[0].type).toBe('scatter');
  });

  it('renders as markers mode (no lines)', () => {
    const vis = makeVIS('effect_scatter', { x: [1, 2], y: [3, 4] });
    const { traces } = renderVis(vis);
    expect(traces[0].mode).toBe('markers');
  });

  it('passes x/y data through', () => {
    const vis = makeVIS('effect_scatter', { x: [10, 20], y: [30, 40] });
    const { traces } = renderVis(vis);
    expect(traces[0].x).toEqual([10, 20]);
    expect(traces[0].y).toEqual([30, 40]);
  });

  it('assigns marker config', () => {
    const vis = makeVIS('effect_scatter', { x: [1], y: [2] });
    const { traces } = renderVis(vis);
    expect(traces[0].marker).toHaveProperty('color');
    expect(traces[0].marker).toHaveProperty('size', 8);
    expect(traces[0].marker).toHaveProperty('opacity', 0.85);
  });

  it('does NOT include ECharts-specific ripple effect', () => {
    const vis = makeVIS('effect_scatter', { x: [1], y: [2] });
    const { traces } = renderVis(vis);
    // Plotly has no concept of ripple animation
    expect(traces[0]).not.toHaveProperty('rippleEffect');
  });
});

// ── Map → Plotly choropleth trace ──────────────────────────────────

describe('map → Plotly choropleth trace', () => {
  it('maps to choropleth trace type', () => {
    const vis = makeVIS('map', { locations: ['USA', 'Canada'], z_geo: [100, 50] });
    const { traces } = renderVis(vis);
    expect(traces[0].type).toBe('choropleth');
  });

  it('passes locations and values through', () => {
    const vis = makeVIS('map', { locations: ['USA', 'Canada'], z_geo: [100, 50] });
    const { traces } = renderVis(vis);
    expect(traces[0].locations).toEqual(['USA', 'Canada']);
    expect(traces[0].z).toEqual([100, 50]);
  });

  it('sets locationmode and colorscale', () => {
    const vis = makeVIS('map', { locations: ['USA'], z_geo: [100] });
    const { traces } = renderVis(vis);
    expect(traces[0].locationmode).toBe('country names');
    expect(traces[0].colorscale).toBe('Viridis');
  });

  it('handles empty locations', () => {
    const vis = makeVIS('map', { locations: [], z_geo: [] });
    const { traces } = renderVis(vis);
    expect(traces[0].type).toBe('choropleth');
    expect(traces[0].locations).toEqual([]);
    expect(traces[0].z).toEqual([]);
  });
});

// ── Donut → Plotly pie trace with hole ─────────────────────────────

describe('donut → Plotly pie trace with hole', () => {
  it('maps to pie trace type', () => {
    const vis = makeVIS('donut', { labels: ['A', 'B'], values: [30, 70] });
    const { traces } = renderVis(vis);
    expect(traces[0].type).toBe('pie');
  });

  it('passes labels and values through', () => {
    const vis = makeVIS('donut', { labels: ['Alpha', 'Beta'], values: [30, 70] });
    const { traces } = renderVis(vis);
    expect(traces[0].labels).toEqual(['Alpha', 'Beta']);
    expect(traces[0].values).toEqual([30, 70]);
  });

  it('applies donut hole (0.65) and hides text info', () => {
    const vis = makeVIS('donut', { labels: ['A'], values: [100] });
    const { traces } = renderVis(vis);
    expect(traces[0].hole).toBe(0.65);
    expect(traces[0].textinfo).toBe('none');
  });

  it('assigns palette colors and marker line', () => {
    const vis = makeVIS('donut', { labels: ['A'], values: [100] });
    const { traces } = renderVis(vis);
    expect(traces[0].marker).toHaveProperty('colors');
    expect(traces[0].marker).toHaveProperty('line');
    expect(traces[0].marker.line).toHaveProperty('color');
    expect(traces[0].marker.line).toHaveProperty('width', 2);
  });
});

// ── Layout ─────────────────────────────────────────────────────────

describe('layout', () => {
  it('uses dark theme by default', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] });
    const { layout } = renderVis(vis);
    expect(layout.paper_bgcolor).toBe('#111827');
    expect(layout.plot_bgcolor).toBe('#111827');
    expect(layout.title.font.color).toBe('#E5E7EB');
  });

  it('supports light theme', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] });
    const { layout } = renderVis(vis, { theme: 'light' });
    expect(layout.paper_bgcolor).toBe('white');
    expect(layout.title.font.color).toBe('#1F2937');
  });

  it('applies axis titles from VIS axes', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] }, {
      axes: { x: { title: 'X Axis' }, y: { title: 'Y Axis' } },
    });
    const { layout } = renderVis(vis);
    expect(layout.xaxis.title.text).toBe('X Axis');
    expect(layout.yaxis.title.text).toBe('Y Axis');
  });

  it('applies pie/donut layout adjustments', () => {
    const vis = makeVIS('donut', { labels: ['A'], values: [100] });
    const { layout } = renderVis(vis);
    expect(layout.xaxis.showticklabels).toBe(false);
    expect(layout.xaxis.showgrid).toBe(false);
    expect(layout.yaxis.showticklabels).toBe(false);
    expect(layout.yaxis.showgrid).toBe(false);
    expect(layout.legend.orientation).toBe('v');
    expect(layout.margin.b).toBe(80);
  });

  it('does NOT apply pie layout adjustments for non-pie types', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] });
    const { layout } = renderVis(vis);
    expect(layout.xaxis.showticklabels).not.toBe(false); // default
  });

  it('creates secondary y-axis when axes.y2 is present', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] }, {
      axes: { y2: { title: 'Right Axis' } },
    });
    const { layout } = renderVis(vis);
    expect(layout.yaxis2).toHaveProperty('overlaying', 'y');
    expect(layout.yaxis2).toHaveProperty('side', 'right');
  });
});

// ── ECharts-only types → notice trace ──────────────────────────────

describe('ECharts-only types produce notice trace', () => {
  it.each([
    'graph', 'sankey', 'parallel', 'lines', 'tree', 'theme_river',
  ])('%s → notice trace', (vizType) => {
    const vis = makeVIS(vizType, { x: [1], y: [2] });
    const { traces } = renderVis(vis);
    expect(traces).toHaveLength(1);
    expect(traces[0].type).toBe('scatter');
    expect(traces[0].mode).toBe('text');
    expect(traces[0].text[0]).toContain(vizType.replace(/_/g, ' '));
    expect(traces[0].text[0]).toContain('requires ECharts');
  });
});

// ── New types are NOT in ECharts-only set ──────────────────────────

describe('new ECharts-preferred types fall back to Plotly', () => {
  it.each([
    'pictorial_bar',
    'effect_scatter',
    'map',
    'donut',
  ])('%s renders a normal trace, not a notice', (vizType) => {
    const series = vizType === 'map'
      ? { locations: ['USA'], z_geo: [100] }
      : { x: [1], y: [2] };
    const extra = vizType === 'donut'
      ? { labels: ['A'], values: [100] }
      : {};

    const vis = makeVIS(vizType, { ...series, ...extra });
    const { traces } = renderVis(vis);

    // Should produce a real trace, not a notice
    expect(traces).toHaveLength(1);
    expect(traces[0].mode).not.toBe('text');
    expect(traces[0].text).toBeUndefined();
  });
});

// ── Multi-series ───────────────────────────────────────────────────

describe('multi-series', () => {
  it('converts each series in the array', () => {
    const vis = {
      version: '1.0',
      visualization_type: 'pictorial_bar',
      title: 'multi',
      series: [
        { name: 'S1', x: ['A'], y: [10] },
        { name: 'S2', x: ['A'], y: [20] },
      ],
    };
    const result = renderVis(vis);
    expect(result.traces).toHaveLength(2);
    expect(result.traces[0].name).toBe('S1');
    expect(result.traces[1].name).toBe('S2');
    expect(result.traces[0].type).toBe('bar');
    expect(result.traces[1].type).toBe('bar');
  });

  it('handles series_collection', () => {
    const vis = {
      version: '1.0',
      visualization_type: 'effect_scatter',
      title: 'multi',
      series: [{ name: 'Primary', x: [1], y: [2] }],
      series_collection: {
        series: [{ name: 'Secondary', x: [3], y: [4] }],
      },
    };
    const result = renderVis(vis);
    expect(result.traces).toHaveLength(2);
  });
});

// ── Strategy ───────────────────────────────────────────────────────

describe('series strategy', () => {
  it('applies grouped strategy', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] }, {
      series_strategy: 'grouped',
      series: [{ name: 'S1', x: ['A'], y: [1] }, { name: 'S2', x: ['A'], y: [2] }],
    });
    const { layout } = renderVis(vis);
    expect(layout.barmode).toBe('group');
  });

  it('applies stacked strategy', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] }, {
      series_strategy: 'stacked',
      series: [{ name: 'S1', x: ['A'], y: [1] }, { name: 'S2', x: ['A'], y: [2] }],
    });
    const { layout } = renderVis(vis);
    expect(layout.barmode).toBe('stack');
  });
});

// ── Narrative passthrough ──────────────────────────────────────────

describe('narrative passthrough', () => {
  it('passes through narrative fields', () => {
    const vis = makeVIS('bar', { x: ['A'], y: [1] }, {
      narrative: {
        headline: 'Key insight',
        confidence: 0.95,
        badge_type: 'success',
        key_numbers: ['42% growth'],
        reading_guide: 'Look at Q3',
        description: 'Subtitle text',
      },
    });
    const result = renderVis(vis);
    expect(result.explanation).toBe('Key insight');
    expect(result.confidence).toBe(0.95);
    expect(result.badge_type).toBe('success');
    expect(result.key_numbers).toEqual(['42% growth']);
    expect(result.reading_guide).toBe('Look at Q3');
    expect(result.subtitle_scope).toBe('Subtitle text');
  });
});

// ── isVIS detection ────────────────────────────────────────────────

describe('isVIS', () => {
  it('detects VIS by visualization_type', () => {
    expect(isVIS({ visualization_type: 'pictorial_bar' })).toBe(true);
    expect(isVIS({ visualization_type: 'effect_scatter' })).toBe(true);
    expect(isVIS({ visualization_type: 'map' })).toBe(true);
    expect(isVIS({ visualization_type: 'donut' })).toBe(true);
  });

  it('rejects non-VIS objects', () => {
    expect(isVIS(null)).toBeFalsy();
    expect(isVIS(undefined)).toBeFalsy();
    expect(isVIS({})).toBeFalsy();
  });
});

// ── isLegacyPlotly ─────────────────────────────────────────────────

describe('isLegacyPlotly', () => {
  it('detects legacy Plotly trace arrays', () => {
    expect(isLegacyPlotly({ traces: [{ x: [1], y: [2] }] })).toBe(true);
    expect(isLegacyPlotly({ data: [{ x: [1], y: [2] }] })).toBe(true);
  });

  it('rejects VIS objects', () => {
    expect(isLegacyPlotly({ visualization_type: 'bar', traces: [] })).toBe(false);
  });
});

// ── visToChartData compat ──────────────────────────────────────────

describe('visToChartData', () => {
  it('returns data/layout/chart_type format', () => {
    const vis = makeVIS('donut', { labels: ['A', 'B'], values: [30, 70] });
    const result = visToChartData(vis);

    expect(result).toHaveProperty('data');
    expect(result).toHaveProperty('layout');
    expect(result).toHaveProperty('chart_type', 'donut');
    expect(result).toHaveProperty('explanation');
    expect(result).toHaveProperty('metadata');
    expect(Array.isArray(result.data)).toBe(true);
  });
});
