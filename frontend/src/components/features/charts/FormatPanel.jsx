import React from 'react';
import { Palette, Eye, LayoutGrid } from 'lucide-react';
import { motion } from 'framer-motion';

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
                    {chartTypes.map(type => (
                        <motion.button
                            key={type.id}
                            whileHover={{ y: -1 }}
                            whileTap={{ scale: 0.98 }}
                            onClick={() => onUpdateChartType(type.id)}
                            className={`relative rounded-lg overflow-hidden transition-all border group ${chartType === type.id
                                    ? 'bg-ocean/10 border-ocean/30'
                                    : 'bg-pearl/[0.02] border-pearl/[0.04] hover:border-pearl/[0.08]'
                                }`}
                        >
                            <div className="aspect-video w-full bg-noir flex items-center justify-center overflow-hidden opacity-70 group-hover:opacity-100 transition-opacity">
                                <img
                                    src={type.image}
                                    alt={type.label}
                                    className={`w-full h-full object-cover transition-all duration-200 ${chartType === type.id ? 'scale-105' : 'grayscale hover:grayscale-0'}`}
                                />
                            </div>
                            <div className={`px-2 py-1 text-[10px] font-medium text-center truncate border-t ${chartType === type.id
                                    ? 'text-pearl border-ocean/20 bg-ocean/5'
                                    : 'text-granite border-pearl/[0.04]'
                                }`}>
                                {type.label}
                            </div>
                        </motion.button>
                    ))}
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
