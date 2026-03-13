import React from 'react';
import { Palette, Eye, LayoutGrid } from 'lucide-react';
import { motion } from 'framer-motion';

/* ── Inline SVG chart-type icons (20×20 viewBox) ── */
const ChartIcon = ({ d, children, ...props }) => (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
        {d ? <path d={d} stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /> : children}
    </svg>
);

const CHART_ICONS = {
    bar: (p) => (
        <ChartIcon {...p}>
            <rect x="2" y="10" width="3" height="8" rx="0.6" fill="currentColor" opacity="0.5" />
            <rect x="6.5" y="5" width="3" height="13" rx="0.6" fill="currentColor" opacity="0.7" />
            <rect x="11" y="8" width="3" height="10" rx="0.6" fill="currentColor" opacity="0.5" />
            <rect x="15.5" y="3" width="3" height="15" rx="0.6" fill="currentColor" opacity="0.8" />
        </ChartIcon>
    ),
    line: (p) => (
        <ChartIcon {...p}>
            <polyline points="2,15 6,10 10,12 14,5 18,8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="2" cy="15" r="1.2" fill="currentColor" />
            <circle cx="6" cy="10" r="1.2" fill="currentColor" />
            <circle cx="10" cy="12" r="1.2" fill="currentColor" />
            <circle cx="14" cy="5" r="1.2" fill="currentColor" />
            <circle cx="18" cy="8" r="1.2" fill="currentColor" />
        </ChartIcon>
    ),
    area: (p) => (
        <ChartIcon {...p}>
            <path d="M2,16 L5,11 L9,13 L13,6 L18,9 L18,18 L2,18 Z" fill="currentColor" opacity="0.2" />
            <polyline points="2,16 5,11 9,13 13,6 18,9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </ChartIcon>
    ),
    scatter: (p) => (
        <ChartIcon {...p}>
            <circle cx="4" cy="14" r="1.5" fill="currentColor" opacity="0.6" />
            <circle cx="7" cy="9" r="1.5" fill="currentColor" opacity="0.8" />
            <circle cx="10" cy="12" r="1.5" fill="currentColor" opacity="0.5" />
            <circle cx="13" cy="6" r="1.5" fill="currentColor" opacity="0.7" />
            <circle cx="16" cy="10" r="1.5" fill="currentColor" opacity="0.9" />
            <circle cx="5" cy="6" r="1.5" fill="currentColor" opacity="0.4" />
            <circle cx="15" cy="15" r="1.5" fill="currentColor" opacity="0.6" />
        </ChartIcon>
    ),
    pie: (p) => (
        <ChartIcon {...p}>
            <circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.3" opacity="0.4" />
            <path d="M10,10 L10,2.5 A7.5,7.5 0 0,1 17,7 Z" fill="currentColor" opacity="0.8" />
            <path d="M10,10 L17,7 A7.5,7.5 0 0,1 14,17 Z" fill="currentColor" opacity="0.5" />
        </ChartIcon>
    ),
    treemap: (p) => (
        <ChartIcon {...p}>
            <rect x="2" y="2" width="9" height="10" rx="0.8" fill="currentColor" opacity="0.6" />
            <rect x="12.5" y="2" width="5.5" height="5" rx="0.8" fill="currentColor" opacity="0.4" />
            <rect x="12.5" y="8.5" width="5.5" height="3.5" rx="0.8" fill="currentColor" opacity="0.3" />
            <rect x="2" y="13.5" width="5.5" height="4.5" rx="0.8" fill="currentColor" opacity="0.5" />
            <rect x="9" y="13.5" width="9" height="4.5" rx="0.8" fill="currentColor" opacity="0.35" />
        </ChartIcon>
    ),
    sunburst: (p) => (
        <ChartIcon {...p}>
            <circle cx="10" cy="10" r="3" fill="currentColor" opacity="0.7" />
            <path d="M10,10 L10,3.5 A6.5,6.5 0 0,1 16,7.5 Z" fill="currentColor" opacity="0.4" stroke="currentColor" strokeWidth="0.5" />
            <path d="M10,10 L16,7.5 A6.5,6.5 0 0,1 15,15 Z" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="0.5" />
            <path d="M10,10 L15,15 A6.5,6.5 0 0,1 5,15 Z" fill="currentColor" opacity="0.35" stroke="currentColor" strokeWidth="0.5" />
            <path d="M10,10 L5,15 A6.5,6.5 0 0,1 10,3.5 Z" fill="currentColor" opacity="0.5" stroke="currentColor" strokeWidth="0.5" />
        </ChartIcon>
    ),
    funnel: (p) => (
        <ChartIcon {...p}>
            <rect x="2" y="2" width="16" height="3" rx="0.6" fill="currentColor" opacity="0.8" />
            <rect x="4" y="6.5" width="12" height="3" rx="0.6" fill="currentColor" opacity="0.6" />
            <rect x="6" y="11" width="8" height="3" rx="0.6" fill="currentColor" opacity="0.4" />
            <rect x="8" y="15.5" width="4" height="3" rx="0.6" fill="currentColor" opacity="0.25" />
        </ChartIcon>
    ),
    histogram: (p) => (
        <ChartIcon {...p}>
            <rect x="2" y="12" width="3.2" height="6" fill="currentColor" opacity="0.35" />
            <rect x="5.2" y="8" width="3.2" height="10" fill="currentColor" opacity="0.55" />
            <rect x="8.4" y="4" width="3.2" height="14" fill="currentColor" opacity="0.8" />
            <rect x="11.6" y="7" width="3.2" height="11" fill="currentColor" opacity="0.6" />
            <rect x="14.8" y="11" width="3.2" height="7" fill="currentColor" opacity="0.4" />
        </ChartIcon>
    ),
    box_plot: (p) => (
        <ChartIcon {...p}>
            <line x1="6" y1="3" x2="6" y2="17" stroke="currentColor" strokeWidth="1.2" opacity="0.4" />
            <rect x="3" y="7" width="6" height="6" rx="0.8" stroke="currentColor" strokeWidth="1.2" fill="currentColor" opacity="0.2" />
            <line x1="3" y1="10" x2="9" y2="10" stroke="currentColor" strokeWidth="1.4" />
            <line x1="14" y1="5" x2="14" y2="16" stroke="currentColor" strokeWidth="1.2" opacity="0.4" />
            <rect x="11" y="8" width="6" height="5" rx="0.8" stroke="currentColor" strokeWidth="1.2" fill="currentColor" opacity="0.2" />
            <line x1="11" y1="11" x2="17" y2="11" stroke="currentColor" strokeWidth="1.4" />
        </ChartIcon>
    ),
    violin: (p) => (
        <ChartIcon {...p}>
            <path d="M6,3 C6,3 3,7 3,10 C3,13 6,17 6,17 C6,17 9,13 9,10 C9,7 6,3 6,3 Z" fill="currentColor" opacity="0.3" stroke="currentColor" strokeWidth="1.2" />
            <line x1="3" y1="10" x2="9" y2="10" stroke="currentColor" strokeWidth="1.2" />
            <path d="M14,4 C14,4 11.5,7 11.5,10 C11.5,13 14,16 14,16 C14,16 16.5,13 16.5,10 C16.5,7 14,4 14,4 Z" fill="currentColor" opacity="0.3" stroke="currentColor" strokeWidth="1.2" />
            <line x1="11.5" y1="10" x2="16.5" y2="10" stroke="currentColor" strokeWidth="1.2" />
        </ChartIcon>
    ),
    heatmap: (p) => (
        <ChartIcon {...p}>
            <rect x="2" y="2" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.8" />
            <rect x="8" y="2" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.3" />
            <rect x="14" y="2" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.5" />
            <rect x="2" y="8" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.4" />
            <rect x="8" y="8" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.9" />
            <rect x="14" y="8" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.2" />
            <rect x="2" y="14" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.6" />
            <rect x="8" y="14" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.35" />
            <rect x="14" y="14" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.7" />
        </ChartIcon>
    ),
    radar: (p) => (
        <ChartIcon {...p}>
            <polygon points="10,2 17,7 15,16 5,16 3,7" stroke="currentColor" strokeWidth="0.8" fill="none" opacity="0.25" />
            <polygon points="10,5 14.5,8 13,14 7,14 5.5,8" stroke="currentColor" strokeWidth="0.8" fill="none" opacity="0.25" />
            <polygon points="10,4 15,7.5 14,15 6,15 4.5,7.5" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="1.2" />
            <circle cx="10" cy="4" r="1" fill="currentColor" />
            <circle cx="15" cy="7.5" r="1" fill="currentColor" />
            <circle cx="14" cy="15" r="1" fill="currentColor" />
            <circle cx="6" cy="15" r="1" fill="currentColor" />
            <circle cx="4.5" cy="7.5" r="1" fill="currentColor" />
        </ChartIcon>
    ),
    bubble: (p) => (
        <ChartIcon {...p}>
            <circle cx="6" cy="12" r="3" fill="currentColor" opacity="0.4" />
            <circle cx="13" cy="7" r="4" fill="currentColor" opacity="0.35" />
            <circle cx="10" cy="14" r="2" fill="currentColor" opacity="0.5" />
            <circle cx="16" cy="14" r="2.5" fill="currentColor" opacity="0.3" />
            <circle cx="5" cy="6" r="1.8" fill="currentColor" opacity="0.45" />
        </ChartIcon>
    ),
    waterfall: (p) => (
        <ChartIcon {...p}>
            <rect x="2" y="4" width="2.5" height="14" rx="0.4" fill="currentColor" opacity="0.7" />
            <rect x="5.5" y="4" width="2.5" height="5" rx="0.4" fill="currentColor" opacity="0.4" />
            <rect x="9" y="9" width="2.5" height="4" rx="0.4" fill="currentColor" opacity="0.5" />
            <rect x="12.5" y="6" width="2.5" height="7" rx="0.4" fill="currentColor" opacity="0.35" />
            <rect x="16" y="3" width="2.5" height="15" rx="0.4" fill="currentColor" opacity="0.7" />
            <line x1="4.5" y1="4" x2="5.5" y2="4" stroke="currentColor" strokeWidth="0.8" strokeDasharray="1.5 1" opacity="0.5" />
            <line x1="8" y1="9" x2="9" y2="9" stroke="currentColor" strokeWidth="0.8" strokeDasharray="1.5 1" opacity="0.5" />
            <line x1="11.5" y1="6" x2="12.5" y2="6" stroke="currentColor" strokeWidth="0.8" strokeDasharray="1.5 1" opacity="0.5" />
            <line x1="15" y1="3" x2="16" y2="3" stroke="currentColor" strokeWidth="0.8" strokeDasharray="1.5 1" opacity="0.5" />
        </ChartIcon>
    ),
    gauge: (p) => (
        <ChartIcon {...p}>
            <path d="M3,14 A7.5,7.5 0 0,1 17,14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fill="none" opacity="0.2" />
            <path d="M3,14 A7.5,7.5 0 0,1 10,6.5" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fill="none" opacity="0.7" />
            <line x1="10" y1="14" x2="13" y2="8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            <circle cx="10" cy="14" r="1.5" fill="currentColor" />
        </ChartIcon>
    ),
};

const COLOR_PALETTES = [
    { id: 'ocean',   colors: ['#5B88B2', '#4a7a9e', '#3a6c8a', '#2a5e76', '#1a5062'] },
    { id: 'emerald', colors: ['#10b981', '#0d9668', '#0a7d56', '#086343', '#064a31'] },
    { id: 'violet',  colors: ['#a78bfa', '#8b5cf6', '#7c3aed', '#6d28d9', '#5b21b6'] },
    { id: 'amber',   colors: ['#f59e0b', '#d97706', '#b45309', '#92400e', '#78350f'] },
    { id: 'mixed',   colors: ['#5B88B2', '#10b981', '#f59e0b', '#ef4444', '#a78bfa'] },
];

const FormatPanel = ({ format, onUpdateFormat, chartType, chartTypes, onUpdateChartType }) => {
    const Section = ({ title, icon: Icon, children }) => (
        <div className="border-b border-pearl/[0.04]">
            <div className="flex items-center gap-2 px-4 py-2.5 text-granite">
                <Icon size={12} />
                <span className="text-[10px] font-semibold uppercase tracking-wider">{title}</span>
            </div>
            <div className="px-4 py-3">
                {children}
            </div>
        </div>
    );

    const Toggle = ({ label, value, onChange }) => (
        <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={() => onChange(!value)}
            className="w-full flex items-center justify-between py-1.5 group"
        >
            <span className="text-[11px] text-granite group-hover:text-pearl transition-colors">{label}</span>
            <div className={`w-8 h-[18px] rounded-full relative transition-colors ${value ? 'bg-ocean/30' : 'bg-pearl/[0.06]'}`}>
                <motion.div
                    className={`w-3 h-3 rounded-full absolute top-[3px] shadow-sm ${value ? 'bg-ocean' : 'bg-granite'}`}
                    animate={{ left: value ? '17px' : '3px' }}
                    transition={{ duration: 0.15 }}
                />
            </div>
        </motion.button>
    );

    return (
        <div className="h-full flex flex-col overflow-y-auto bg-midnight border-l border-pearl/[0.06] nice-scrollbar">
            {/* Header */}
            <div className="px-4 py-2.5 border-b border-pearl/[0.06]">
                <h2 className="text-[11px] font-semibold text-granite uppercase tracking-wider">
                    Properties
                </h2>
            </div>

            {/* Chart Type Selector */}
            <Section title="Chart Type" icon={LayoutGrid}>
                <div className="grid grid-cols-2 gap-1.5">
                    {chartTypes.map(type => {
                        const IconRenderer = CHART_ICONS[type.id];
                        return (
                            <motion.button
                                key={type.id}
                                whileHover={{ y: -1 }}
                                whileTap={{ scale: 0.97 }}
                                onClick={() => onUpdateChartType(type.id)}
                                className={`flex flex-col items-center gap-1 rounded-lg py-2 px-1 transition-all border group ${chartType === type.id
                                        ? 'bg-ocean/10 border-ocean/30 text-ocean'
                                        : 'bg-pearl/[0.02] border-pearl/[0.04] hover:border-pearl/[0.08] text-granite hover:text-pearl'
                                    }`}
                            >
                                <div className="w-5 h-5">
                                    {IconRenderer ? IconRenderer({ className: 'w-full h-full' }) : null}
                                </div>
                                <span className={`text-[9px] font-medium truncate w-full text-center leading-tight ${chartType === type.id ? 'text-pearl' : ''}`}>
                                    {type.label}
                                </span>
                            </motion.button>
                        );
                    })}
                </div>
            </Section>

            {/* Color Palette */}
            <Section title="Color Palette" icon={Palette}>
                <div className="space-y-1">
                    {COLOR_PALETTES.map(palette => (
                        <motion.button
                            key={palette.id}
                            whileTap={{ scale: 0.98 }}
                            onClick={() => onUpdateFormat('colorPalette', palette.colors)}
                            className={`w-full flex items-center gap-3 p-2 rounded-md transition-colors border ${format.colorPalette[0] === palette.colors[0]
                                    ? 'bg-pearl/[0.06] border-pearl/[0.12]'
                                    : 'bg-transparent border-transparent hover:bg-pearl/[0.03]'
                                }`}
                        >
                            <div className="flex gap-0.5">
                                {palette.colors.map((color, i) => (
                                    <div key={i} className="w-3.5 h-3.5 first:rounded-l-sm last:rounded-r-sm" style={{ backgroundColor: color }} />
                                ))}
                            </div>
                            <span className={`text-[11px] capitalize ${format.colorPalette[0] === palette.colors[0] ? 'text-pearl' : 'text-granite'}`}>
                                {palette.id}
                            </span>
                        </motion.button>
                    ))}
                </div>
            </Section>

            {/* Display Options */}
            <Section title="Display" icon={Eye}>
                <div className="space-y-0.5">
                    <Toggle label="Show Legend" value={format.showLegend} onChange={(v) => onUpdateFormat('showLegend', v)} />
                    <Toggle label="Show Labels" value={format.showLabels} onChange={(v) => onUpdateFormat('showLabels', v)} />
                    <Toggle label="Show Grid" value={format.showGrid} onChange={(v) => onUpdateFormat('showGrid', v)} />
                </div>
            </Section>

            <div className="p-3 border-t border-pearl/[0.04] text-[10px] text-granite/50 text-center tracking-wider">
                Auto-saving
            </div>
        </div>
    );
};

export default FormatPanel;
