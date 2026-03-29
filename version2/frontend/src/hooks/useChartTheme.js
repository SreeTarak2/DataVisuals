import { useTheme } from '@/store/themeStore';

export function useChartTheme() {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const colors = {
    revenue: '#8B5CF6',
    expense: '#EF4444',
    profit: '#14B8A6',
    neutral: '#98989F',
    text: '#FFFFFF',
    textMuted: '#98989F',
    gridColor: 'rgba(46, 46, 48, 0.6)',
    cardBg: '#161618',
    hoverBg: '#1F1F23',
    hoverBorder: '#3E3E42',
    axisLine: 'rgba(46, 46, 48, 0.8)',
    border: 'rgba(255, 255, 255, 0.08)',
    lineColor: 'rgba(255, 255, 255, 0.03)',
    categorical: [
      '#8B5CF6',
      '#14B8A6',
      '#F59E0B',
      '#EC4899',
      '#3B82F6',
      '#10B981',
      '#F97316',
    ],
  };

  const lightColors = {
    revenue: '#7C3AED',
    expense: '#DC2626',
    profit: '#0D9488',
    neutral: '#64748B',
    text: '#0A0A0C',
    textMuted: '#64748B',
    gridColor: 'rgba(100, 116, 139, 0.2)',
    cardBg: '#FFFFFF',
    hoverBg: '#F8FAFC',
    hoverBorder: '#E2E8F0',
    axisLine: 'rgba(100, 116, 139, 0.2)',
    border: 'rgba(0, 0, 0, 0.08)',
    lineColor: 'rgba(0, 0, 0, 0.03)',
    categorical: [
      '#7C3AED',
      '#0D9488',
      '#F59E0B',
      '#DB2777',
      '#2563EB',
      '#059669',
      '#EA580C',
    ],
  };

  const activeColors = isDark ? colors : lightColors;

  const baseLayout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: {
      family: 'Inter, "Plus Jakarta Sans", system-ui, sans-serif',
      color: activeColors.text,
      size: 13,
    },
    margin: { t: 28, r: 24, b: 50, l: 60 },
    autosize: true,
    hoverlabel: {
      bgcolor: activeColors.hoverBg,
      bordercolor: activeColors.hoverBorder,
      font: { color: activeColors.text, family: 'Inter, system-ui, sans-serif', size: 13 },
    },
    xaxis: {
      showgrid: true,
      gridcolor: activeColors.gridColor,
      gridwidth: 1,
      zeroline: false,
      tickfont: { color: activeColors.textMuted, size: 12 },
      linecolor: activeColors.axisLine,
      titlefont: { color: activeColors.textMuted, size: 12 },
    },
    yaxis: {
      showgrid: true,
      gridcolor: activeColors.gridColor,
      gridwidth: 1,
      zeroline: false,
      tickfont: { color: activeColors.textMuted, size: 12 },
      linecolor: activeColors.axisLine,
      titlefont: { color: activeColors.textMuted, size: 12 },
    },
  };

  const config = {
    responsive: true,
    displayModeBar: false,
    displaylogo: false,
  };

  const palettes = {
    bar: activeColors.categorical,
    line: ['#8B5CF6', '#14B8A6', '#3B82F6', '#F59E0B', '#EC4899', '#10B981'],
    pie: activeColors.categorical,
    scatter: ['#8B5CF6', '#14B8A6', '#F59E0B', '#3B82F6', '#EC4899', '#F97316'],
    box: ['#8B5CF6', '#14B8A6', '#F59E0B', '#EF4444', '#3B82F6', '#10B981'],
    area: ['#8B5CF6', '#14B8A6', '#3B82F6', '#F59E0B', '#EC4899'],
    default: activeColors.categorical,
    heatmap: isDark
      ? [[0, '#1e1b4b'], [0.2, '#4338ca'], [0.4, '#7c3aed'], [0.6, '#8b5cf6'], [0.8, '#a78bfa'], [1, '#c4b5fd']]
      : [[0, '#f5f3ff'], [0.2, '#ddd6fe'], [0.4, '#c4b5fd'], [0.6, '#a78bfa'], [0.8, '#8b5cf6'], [1, '#7c3aed']],
  };

  const getPalette = (chartType) => {
    const normalized = (chartType || '').toLowerCase().replace('_chart', '').replace('_plot', '');
    return palettes[normalized] || palettes.default;
  };

  return { 
    colors: activeColors, 
    baseLayout, 
    config,
    palettes,
    getPalette,
    isDark 
  };
}
