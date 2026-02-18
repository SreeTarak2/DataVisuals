import React from 'react';
import { Palette, Grid3X3, Tag, Eye, EyeOff, LayoutGrid } from 'lucide-react';
import { motion } from 'framer-motion';

const COLOR_PALETTES = [
    { id: 'blue', colors: ['#58a6ff', '#388bfd', '#1f6feb', '#0d419d', '#0b2e6f'] },
    { id: 'green', colors: ['#3fb950', '#2ea043', '#238636', '#196c2e', '#0f4422'] },
    { id: 'purple', colors: ['#a371f7', '#8957e5', '#6e40c9', '#553098', '#3c1e70'] },
    { id: 'orange', colors: ['#d29922', '#bb8009', '#9e6a03', '#845306', '#633c01'] },
    { id: 'rainbow', colors: ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#a371f7'] },
];

const FormatPanel = ({ format, onUpdateFormat, chartType, chartTypes, onUpdateChartType }) => {
    const Section = ({ title, icon: Icon, children }) => (
        <div className="border-b border-slate-800">
            <div className="flex items-center gap-2 px-4 py-3 text-slate-500 bg-[#0d141f]">
                <Icon size={14} />
                <span className="text-[10px] font-bold uppercase tracking-wider">{title}</span>
            </div>
            <div className="px-4 py-4 bg-[#0b1117]">
                {children}
            </div>
        </div>
    );

    const Toggle = ({ label, value, onChange }) => (
        <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={() => onChange(!value)}
            className="w-full flex items-center justify-between py-2 group"
        >
            <span className="text-xs text-slate-300 group-hover:text-white transition-colors">{label}</span>
            <div
                className={`w-9 h-5 rounded-full relative transition-colors ${value ? 'bg-blue-600' : 'bg-slate-700'
                    }`}
            >
                <motion.div
                    className="w-3.5 h-3.5 rounded-full absolute top-[3px] bg-white shadow-sm"
                    animate={{ left: value ? '20px' : '3px' }}
                    transition={{ duration: 0.15 }}
                />
            </div>
        </motion.button>
    );

    return (
        <div className="h-full flex flex-col overflow-y-auto bg-[#0b1117] border-l border-slate-800 nice-scrollbar">
            {/* Header */}
            <div className="p-3 border-b border-slate-800 bg-[#0d141f] flex items-center justify-between">
                <h2 className="text-xs font-semibold text-slate-200 uppercase tracking-wide">
                    Properties
                </h2>
            </div>

            {/* Chart Type Selector */}
            <Section title="Chart Type" icon={LayoutGrid}>
                <div className="grid grid-cols-2 gap-2">
                    {chartTypes.map(type => (
                        <motion.button
                            key={type.id}
                            whileHover={{ y: -2 }}
                            whileTap={{ scale: 0.98 }}
                            onClick={() => onUpdateChartType(type.id)}
                            className={`relative rounded overflow-hidden transition-all border group ${chartType === type.id
                                    ? 'bg-blue-900/20 border-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.2)]'
                                    : 'bg-slate-900 border-slate-800 hover:border-slate-600'
                                }`}
                        >
                            {/* Chart Preview Image */}
                            <div className="aspect-video w-full bg-slate-950 flex items-center justify-center overflow-hidden opacity-80 group-hover:opacity-100 transition-opacity">
                                <img
                                    src={type.image}
                                    alt={type.label}
                                    className={`w-full h-full object-cover transition-all duration-300 ${chartType === type.id ? 'scale-110 filter-none' : 'grayscale hover:grayscale-0'
                                        }`}
                                />
                            </div>

                            {/* Label */}
                            <div className={`px-2 py-1.5 text-[10px] font-medium text-center truncate border-t ${chartType === type.id
                                    ? 'text-blue-200 border-blue-500/30 bg-blue-900/30'
                                    : 'text-slate-400 border-slate-800 bg-slate-900'
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
                            className={`w-full flex items-center gap-3 p-2 rounded transition-all border ${format.colorPalette[0] === palette.colors[0]
                                    ? 'bg-slate-800 border-blue-500/50'
                                    : 'bg-transparent border-transparent hover:bg-slate-800/50 hover:border-slate-700'
                                }`}
                        >
                            <div className="flex gap-0.5 shadow-sm">
                                {palette.colors.map((color, i) => (
                                    <div key={i} className="w-4 h-4 first:rounded-l-sm last:rounded-r-sm" style={{ backgroundColor: color }} />
                                ))}
                            </div>
                            <span className={`text-xs capitalize ${format.colorPalette[0] === palette.colors[0] ? 'text-white' : 'text-slate-500'
                                }`}>
                                {palette.id}
                            </span>
                        </motion.button>
                    ))}
                </div>
            </Section>

            {/* Display Options */}
            <Section title="Display" icon={Eye}>
                <div className="space-y-1">
                    <Toggle
                        label="Show Legend"
                        value={format.showLegend}
                        onChange={(v) => onUpdateFormat('showLegend', v)}
                    />
                    <Toggle
                        label="Show Labels"
                        value={format.showLabels}
                        onChange={(v) => onUpdateFormat('showLabels', v)}
                    />
                    <Toggle
                        label="Show Grid"
                        value={format.showGrid}
                        onChange={(v) => onUpdateFormat('showGrid', v)}
                    />
                </div>
            </Section>

            {/* Footer */}
            <div className="p-4 border-t border-slate-800 text-[10px] text-slate-600 text-center uppercase tracking-wider">
                Auto-saving changes
            </div>
        </div>
    );
};

export default FormatPanel;
