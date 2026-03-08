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
    onRefresh
}) => {
    const getFieldName = (col) => typeof col === 'string' ? col : col.name;

    const Dropdown = ({ label, value, options, onChange, width = 'w-40' }) => (
        <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                {label}
            </span>
            <div className="relative group">
                <select
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className={`${width} appearance-none px-3 py-1.5 pr-8 rounded bg-[#0b1117] border border-slate-700 text-xs text-slate-200 cursor-pointer outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-all`}
                >
                    <option value="">Select...</option>
                    {options.map((opt, i) => (
                        <option key={i} value={typeof opt === 'string' ? opt : opt.id || opt.value}>
                            {typeof opt === 'string' ? opt : opt.label || opt.name}
                        </option>
                    ))}
                </select>
                <ChevronDown
                    size={12}
                    className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 group-hover:text-slate-300"
                />
            </div>
        </div>
    );

    return (
        <div className="h-12 flex items-center justify-between px-4 border-t border-slate-800 bg-[#0d141f]">
            {/* Left: Encoding Dropdowns */}
            <div className="flex items-center gap-4">
                <Dropdown
                    label="X Axis"
                    value={encoding.x.field}
                    options={columns.map(getFieldName)}
                    onChange={(v) => onUpdateEncoding('x', v)}
                    width="w-32"
                />

                <Dropdown
                    label="Y Axis"
                    value={encoding.y.field}
                    options={columns.map(getFieldName)}
                    onChange={(v) => onUpdateEncoding('y', v)}
                    width="w-32"
                />

                <Dropdown
                    label="Aggr"
                    value={encoding.y.aggregate}
                    options={AGGREGATIONS}
                    onChange={(v) => onUpdateEncoding('y', { ...encoding.y, aggregate: v })}
                    width="w-24"
                />
            </div>

            {/* Right: Refresh Button */}
            <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={onRefresh}
                className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white shadow-sm flex items-center gap-1.5 font-medium text-xs transition-colors"
                title="Refresh Chart"
            >
                <RefreshCw size={12} />
                Refresh
            </motion.button>
        </div>
    );
};

export default EncodingBar;
