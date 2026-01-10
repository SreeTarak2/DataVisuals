import React from 'react';
import { RefreshCw, ChevronDown } from 'lucide-react';
import { motion } from 'framer-motion';

const AGGREGATIONS = [
    { id: 'sum', label: 'Sum' },
    { id: 'avg', label: 'Average' },
    { id: 'count', label: 'Count' },
    { id: 'min', label: 'Min' },
    { id: 'max', label: 'Max' },
];

const EncodingBar = ({
    columns,
    encoding,
    onUpdateEncoding,
    onRefresh,
    colors
}) => {
    const getFieldName = (col) => typeof col === 'string' ? col : col.name;

    const Dropdown = ({ label, value, options, onChange, width = 'w-40' }) => (
        <div className="flex items-center gap-2">
            <span
                className="text-xs font-medium uppercase tracking-wide"
                style={{ color: colors.textSecondary }}
            >
                {label}
            </span>
            <div className="relative">
                <select
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className={`${width} appearance-none px-3 py-2 pr-8 rounded text-sm cursor-pointer outline-none transition-colors`}
                    style={{
                        backgroundColor: colors.surface,
                        color: colors.textPrimary,
                        border: `1px solid ${colors.border}`,
                    }}
                >
                    <option value="">Select...</option>
                    {options.map((opt, i) => (
                        <option key={i} value={typeof opt === 'string' ? opt : opt.id || opt.value}>
                            {typeof opt === 'string' ? opt : opt.label || opt.name}
                        </option>
                    ))}
                </select>
                <ChevronDown
                    size={14}
                    className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none"
                    style={{ color: colors.textSecondary }}
                />
            </div>
        </div>
    );

    return (
        <div
            className="h-14 flex items-center justify-between px-6 border-t"
            style={{ backgroundColor: colors.surface, borderColor: colors.border }}
        >
            {/* Left: Encoding Dropdowns */}
            <div className="flex items-center gap-6">
                <Dropdown
                    label="X Axis"
                    value={encoding.x.field}
                    options={columns.map(getFieldName)}
                    onChange={(v) => onUpdateEncoding('x', v)}
                    width="w-44"
                />

                <Dropdown
                    label="Y Axis"
                    value={encoding.y.field}
                    options={columns.map(getFieldName)}
                    onChange={(v) => onUpdateEncoding('y', v)}
                    width="w-44"
                />

                <Dropdown
                    label="Aggregation"
                    value={encoding.y.aggregate}
                    options={AGGREGATIONS}
                    onChange={(v) => onUpdateEncoding('y', { ...encoding.y, aggregate: v })}
                    width="w-32"
                />
            </div>

            {/* Right: Refresh Button */}
            <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={onRefresh}
                className="px-4 py-2 rounded-lg transition-colors flex items-center gap-2 font-medium text-sm"
                style={{
                    backgroundColor: colors.accent,
                    color: '#fff',
                }}
                title="Refresh Chart"
            >
                <RefreshCw size={16} />
                Refresh
            </motion.button>
        </div>
    );
};

export default EncodingBar;
