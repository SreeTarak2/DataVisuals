import React from 'react';
import {
    RefreshCw, ChevronDown, Settings, Save, Download,
    TrendingUp, SlidersHorizontal, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen,
    Layers
} from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '../../../lib/utils';

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

    const Dropdown = ({ label, value, options, onChange, icon: Icon, color = "text-accent-primary" }) => (
        <div className="flex flex-col min-w-[120px]">
            <div className="relative group">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none text-muted opacity-40 group-hover:opacity-100 transition-opacity">
                    <Icon size={12} className={color} strokeWidth={2.5} />
                </div>
                <select
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className="w-full appearance-none pl-9 pr-8 py-2 rounded-lg bg-secondary/30 shadow-inner text-[12px] font-bold text-header cursor-pointer outline-none focus:bg-secondary/50 transition-all border border-transparent focus:border-accent-primary/20"
                >
                    <option value="" className="bg-surface text-muted">{label}</option>
                    {options.map((opt, i) => (
                        <option key={i} value={typeof opt === 'string' ? opt : opt.id || opt.value} className="bg-surface text-header font-medium">
                            {typeof opt === 'string' ? opt : opt.label || opt.name}
                        </option>
                    ))}
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-muted/40 group-hover:text-header transition-colors">
                    <ChevronDown size={12} strokeWidth={3} />
                </div>
            </div>
        </div>
    );

    const ActionButton = ({ onClick, icon: Icon, label, disabled, active, variant = "ghost" }) => (
        <motion.button
            whileHover={!disabled ? { y: -2, scale: 1.02 } : {}}
            whileTap={!disabled ? { scale: 0.95 } : {}}
            onClick={onClick}
            disabled={disabled}
            className={cn(
                "flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-widest transition-all relative overflow-hidden group cursor-pointer",
                disabled ? "opacity-20 grayscale cursor-not-allowed" : "",
                active
                    ? "bg-accent-primary text-white shadow-lg shadow-accent-primary/30"
                    : variant === "primary"
                        ? "bg-header text-surface shadow-xl shadow-black/10"
                        : "bg-secondary/20 text-secondary hover:bg-secondary/40 hover:text-header transition-colors"
            )}
            title={label}
        >
            <Icon size={14} strokeWidth={3} />
            <span className="hidden xl:inline">{label}</span>
        </motion.button>
    );

    return (
        <div className="w-full flex items-center justify-between p-2 rounded-xl bg-surface/90 backdrop-blur-3xl shadow-[0_32px_64px_-16px_rgba(0,0,0,0.3)]">
            {/* Left: Encoding Controls */}
            <div className="flex items-center gap-3 px-1">
                <button
                    onClick={onToggleDataPanel}
                    className={cn(
                        "p-2 rounded-lg transition-all shadow-sm cursor-pointer",
                        showDataPanel
                            ? "bg-accent-primary text-white shadow-lg shadow-accent-primary/20"
                            : "bg-secondary/20 text-muted hover:text-header hover:bg-secondary/40"
                    )}
                    title={showDataPanel ? "Close Dimensions" : "Open Dimensions"}
                >
                    {showDataPanel ? <PanelLeftClose size={18} strokeWidth={2.5} /> : <PanelLeftOpen size={18} strokeWidth={2.5} />}
                </button>

                <div className="flex items-center gap-3">
                    <Dropdown
                        label="X-Axis"
                        value={encoding.x.field}
                        options={columns.map(getFieldName)}
                        onChange={(v) => onUpdateEncoding('x', v)}
                        icon={Settings}
                    />
                    <Dropdown
                        label="Y-Axis"
                        value={encoding.y.field}
                        options={columns.map(getFieldName)}
                        onChange={(v) => onUpdateEncoding('y', v)}
                        icon={TrendingUp}
                        color="text-accent-secondary"
                    />
                    <Dropdown
                        label="Segment"
                        value={encoding.group_by}
                        options={columns.map(getFieldName)}
                        onChange={(v) => onUpdateEncoding('group_by', v)}
                        icon={Layers}
                        color="text-amber-400"
                    />
                    <Dropdown
                        label="Method"
                        value={encoding.y.aggregate}
                        options={AGGREGATIONS}
                        onChange={(v) => onUpdateEncoding('y', { ...encoding.y, aggregate: v })}
                        icon={SlidersHorizontal}
                        color="text-accent-purple"
                    />
                </div>

                <motion.button
                    whileHover={{ rotate: 180, scale: 1.1 }}
                    transition={{ duration: 0.8 }}
                    onClick={onRefresh}
                    className="p-2 rounded-full bg-accent-primary shadow-lg shadow-accent-primary/20 text-white cursor-pointer"
                    title="Compute Visualization"
                >
                    <RefreshCw size={18} strokeWidth={3} />
                </motion.button>
            </div>

            {/* Right: Workspace Actions */}
            <div className="flex items-center gap-2 px-1">
                <ActionButton
                    onClick={onSave}
                    disabled={!chartData}
                    icon={Save}
                    label="Commit"
                />
                <ActionButton
                    onClick={onExport}
                    disabled={!chartData}
                    icon={Download}
                    label="Export"
                    variant="primary"
                />

                <button
                    onClick={onToggleFormatPanel}
                    className={cn(
                        "ml-3 p-2 rounded-lg transition-all shadow-sm cursor-pointer",
                        showFormatPanel
                            ? "bg-accent-primary text-white shadow-lg shadow-accent-primary/20"
                            : "bg-secondary/20 text-muted hover:text-header hover:bg-secondary/40"
                    )}
                    title={showFormatPanel ? "Close Properties" : "Open Properties"}
                >
                    {showFormatPanel ? <PanelRightClose size={18} strokeWidth={2.5} /> : <PanelRightOpen size={18} strokeWidth={2.5} />}
                </button>
            </div>
        </div>
    );
};


export default EncodingBar;
