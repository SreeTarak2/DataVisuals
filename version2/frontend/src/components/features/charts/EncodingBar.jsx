import React from 'react';
import { RefreshCw, ChevronDown, Database, Settings, Save, Download } from 'lucide-react';
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
    showDataPanel,
    onToggleDataPanel,
    showFormatPanel,
    onToggleFormatPanel,
    chartData,
    onSave,
    onExport,
}) => {
    const getFieldName = (col) => typeof col === 'string' ? col : col.name;

    const Dropdown = ({ label, value, options, onChange, width = 'w-36' }) => (
        <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-granite">
                {label}
            </span>
            <div className="relative group">
                <select
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className={`${width} appearance-none px-2.5 py-1.5 pr-7 rounded-md bg-midnight border border-pearl/[0.06] text-[11px] text-pearl cursor-pointer outline-none focus:border-ocean/30 transition-colors`}
                >
                    <option value="" className="bg-midnight text-granite">Select…</option>
                    {options.map((opt, i) => (
                        <option key={i} value={typeof opt === 'string' ? opt : opt.id || opt.value} className="bg-midnight text-pearl">
                            {typeof opt === 'string' ? opt : opt.label || opt.name}
                        </option>
                    ))}
                </select>
                <ChevronDown
                    size={11}
                    className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-granite"
                />
            </div>
        </div>
    );

    return (
        <div className="h-11 flex items-center justify-between px-3 border-t border-pearl/[0.06] bg-midnight">
            {/* Left: Panel toggle + Encoding dropdowns */}
            <div className="flex items-center gap-3">
                <button
                    onClick={onToggleDataPanel}
                    className={`p-1.5 rounded-md transition-colors ${showDataPanel ? 'bg-ocean/15 text-ocean' : 'text-granite hover:text-pearl'}`}
                    title="Toggle Data Panel"
                >
                    <Database size={13} />
                </button>

                <div className="h-4 w-px bg-pearl/[0.06]" />

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

            {/* Right: Actions + Panel toggle */}
            <div className="flex items-center gap-1.5">
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={onRefresh}
                    className="p-1.5 rounded-md text-granite hover:text-pearl hover:bg-pearl/[0.04] transition-colors"
                    title="Refresh Chart"
                >
                    <RefreshCw size={13} />
                </motion.button>

                <div className="h-4 w-px bg-pearl/[0.06]" />

                <button
                    onClick={onSave}
                    disabled={!chartData}
                    className="p-1.5 rounded-md text-granite hover:text-pearl hover:bg-pearl/[0.04] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title="Save"
                >
                    <Save size={13} />
                </button>
                <button
                    onClick={onExport}
                    disabled={!chartData}
                    className="p-1.5 rounded-md text-granite hover:text-pearl hover:bg-pearl/[0.04] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title="Export"
                >
                    <Download size={13} />
                </button>

                <div className="h-4 w-px bg-pearl/[0.06]" />

                <button
                    onClick={onToggleFormatPanel}
                    className={`p-1.5 rounded-md transition-colors ${showFormatPanel ? 'bg-ocean/15 text-ocean' : 'text-granite hover:text-pearl'}`}
                    title="Toggle Format Panel"
                >
                    <Settings size={13} />
                </button>
            </div>
        </div>
    );
};

export default EncodingBar;
