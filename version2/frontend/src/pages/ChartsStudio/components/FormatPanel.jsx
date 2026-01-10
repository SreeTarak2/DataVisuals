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

const FormatPanel = ({ format, onUpdateFormat, chartType, chartTypes, onUpdateChartType, colors }) => {
    const Section = ({ title, icon: Icon, children }) => (
        <div className="border-b" style={{ borderColor: colors.border }}>
            <div
                className="flex items-center gap-2 px-4 py-3"
                style={{ color: colors.textSecondary }}
            >
                <Icon size={14} />
                <span className="text-xs font-medium uppercase tracking-wide">{title}</span>
            </div>
            <div className="px-4 pb-4">
                {children}
            </div>
        </div>
    );

    const Toggle = ({ label, value, onChange }) => (
        <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={() => onChange(!value)}
            className="w-full flex items-center justify-between py-2"
        >
            <span className="text-sm" style={{ color: colors.textPrimary }}>{label}</span>
            <div
                className="w-10 h-5 rounded-full relative transition-colors"
                style={{
                    backgroundColor: value ? colors.accent : colors.border
                }}
            >
                <motion.div
                    className="w-4 h-4 rounded-full absolute top-0.5"
                    animate={{ left: value ? '22px' : '2px' }}
                    transition={{ duration: 0.15 }}
                    style={{ backgroundColor: '#fff' }}
                />
            </div>
        </motion.button>
    );

    return (
        <div className="h-full flex flex-col overflow-y-auto">
            {/* Header */}
            <div
                className="p-4 border-b"
                style={{ borderColor: colors.border }}
            >
                <h2
                    className="text-sm font-semibold"
                    style={{ color: colors.textPrimary }}
                >
                    Chart Settings
                </h2>
            </div>

            {/* Chart Type Selector */}
            <Section title="Chart Type" icon={LayoutGrid}>
                <div className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto">
                    {chartTypes.map(type => (
                        <motion.button
                            key={type.id}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                            onClick={() => onUpdateChartType(type.id)}
                            className="relative rounded-lg overflow-hidden transition-all"
                            style={{
                                backgroundColor: chartType === type.id ? `${colors.accent}20` : colors.bg,
                                border: chartType === type.id
                                    ? `2px solid ${colors.accent}`
                                    : `1px solid ${colors.border}`,
                            }}
                        >
                            {/* Chart Preview Image */}
                            <div className="aspect-video w-full bg-slate-900 flex items-center justify-center overflow-hidden">
                                <img
                                    src={type.image}
                                    alt={type.label}
                                    className="w-full h-full object-cover opacity-80 hover:opacity-100 transition-opacity"
                                    style={{
                                        filter: chartType === type.id ? 'none' : 'grayscale(30%)'
                                    }}
                                />
                            </div>

                            {/* Label */}
                            <div
                                className="px-2 py-1.5 text-xs font-medium text-center"
                                style={{
                                    color: chartType === type.id ? colors.accent : colors.textSecondary
                                }}
                            >
                                {type.label}
                            </div>

                            {/* Active Indicator */}
                            {chartType === type.id && (
                                <div
                                    className="absolute top-1 right-1 w-2 h-2 rounded-full"
                                    style={{ backgroundColor: colors.accent }}
                                />
                            )}
                        </motion.button>
                    ))}
                </div>
            </Section>

            {/* Color Palette */}
            <Section title="Color Palette" icon={Palette}>
                <div className="space-y-2">
                    {COLOR_PALETTES.map(palette => (
                        <motion.button
                            key={palette.id}
                            whileTap={{ scale: 0.98 }}
                            onClick={() => onUpdateFormat('colorPalette', palette.colors)}
                            className="w-full flex items-center gap-2 p-2 rounded transition-colors"
                            style={{
                                backgroundColor: format.colorPalette[0] === palette.colors[0]
                                    ? `${colors.accent}20`
                                    : 'transparent',
                                border: format.colorPalette[0] === palette.colors[0]
                                    ? `1px solid ${colors.accent}`
                                    : '1px solid transparent',
                            }}
                        >
                            <div className="flex gap-0.5">
                                {palette.colors.map((color, i) => (
                                    <div
                                        key={i}
                                        className="w-5 h-5 rounded-sm"
                                        style={{ backgroundColor: color }}
                                    />
                                ))}
                            </div>
                            <span
                                className="text-xs capitalize"
                                style={{ color: colors.textSecondary }}
                            >
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

            {/* Spacer */}
            <div className="flex-1" />

            {/* Footer */}
            <div
                className="p-4 border-t text-xs"
                style={{ borderColor: colors.border, color: colors.textSecondary }}
            >
                Changes apply instantly
            </div>
        </div>
    );
};

export default FormatPanel;
