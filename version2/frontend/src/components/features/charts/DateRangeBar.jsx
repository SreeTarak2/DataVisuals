import React, { useState, useRef, useEffect } from 'react';
import { Calendar, ChevronDown, Clock } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const PRESETS = [
    { label: 'Today',     days: 1 },
    { label: 'Last 7D',   days: 7 },
    { label: 'Last 30D',  days: 30 },
    { label: 'Last 90D',  days: 90 },
    { label: 'Last 365D', days: 365 },
    { label: 'All time',  days: 0 },
];

const GRANULARITIES = [
    { id: 'hour',  label: 'Hourly' },
    { id: 'day',   label: 'Daily' },
    { id: 'week',  label: 'Weekly' },
    { id: 'month', label: 'Monthly' },
];

function toISODate(date) {
    return date.toISOString().slice(0, 10);
}

function formatDisplay(from, to, preset) {
    if (preset === 'All time') return 'All time';
    if (!from || !to) return 'Select range';
    if (preset) return preset;
    return `${from} → ${to}`;
}

/**
 * DateRangeBar — global date filter for the Charts page.
 *
 * Props:
 *   value: { from: string|null, to: string|null, preset: string|null, granularity: string }
 *   onChange: (value) => void
 */
const DateRangeBar = ({ value, onChange }) => {
    const [open, setOpen] = useState(false);
    const [customFrom, setCustomFrom] = useState(value?.from || '');
    const [customTo, setCustomTo] = useState(value?.to || '');
    const ref = useRef(null);

    useEffect(() => {
        const handler = (e) => {
            if (ref.current && !ref.current.contains(e.target)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const applyPreset = (preset) => {
        if (preset.days === 0) {
            onChange({ from: null, to: null, preset: preset.label, granularity: value?.granularity || 'day' });
        } else {
            const to = new Date();
            const from = new Date();
            from.setDate(from.getDate() - preset.days);
            onChange({
                from: toISODate(from),
                to: toISODate(to),
                preset: preset.label,
                granularity: value?.granularity || 'day',
            });
        }
        setOpen(false);
    };

    const applyCustom = () => {
        if (!customFrom || !customTo) return;
        onChange({ from: customFrom, to: customTo, preset: null, granularity: value?.granularity || 'day' });
        setOpen(false);
    };

    const setGranularity = (g) => {
        onChange({ ...value, granularity: g });
    };

    const display = formatDisplay(value?.from, value?.to, value?.preset);
    const hasFilter = value?.from || value?.preset === 'All time';

    return (
        <div className="flex items-center gap-2 flex-wrap" ref={ref}>
            {/* Date range button */}
            <div className="relative">
                <button
                    onClick={() => setOpen(v => !v)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-[12px] font-semibold transition-all ${
                        hasFilter
                            ? 'border-accent-primary/40 bg-accent-primary/10 text-accent-primary'
                            : 'border-border bg-surface text-secondary hover:text-header hover:border-border-hover'
                    }`}
                >
                    <Calendar size={13} />
                    {display}
                    <ChevronDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
                </button>

                <AnimatePresence>
                    {open && (
                        <motion.div
                            initial={{ opacity: 0, y: -6, scale: 0.97 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: -6, scale: 0.97 }}
                            transition={{ duration: 0.12 }}
                            className="absolute top-10 left-0 z-50 w-72 rounded-xl border border-border bg-surface shadow-xl overflow-hidden"
                        >
                            {/* Presets */}
                            <div className="p-3 grid grid-cols-2 gap-1.5">
                                {PRESETS.map(preset => (
                                    <button
                                        key={preset.label}
                                        onClick={() => applyPreset(preset)}
                                        className={`px-3 py-2 rounded-lg text-[12px] font-semibold text-left transition-all hover:bg-accent-primary/10 hover:text-accent-primary ${
                                            value?.preset === preset.label
                                                ? 'bg-accent-primary/15 text-accent-primary'
                                                : 'text-secondary'
                                        }`}
                                    >
                                        {preset.label}
                                    </button>
                                ))}
                            </div>

                            {/* Custom range */}
                            <div className="border-t border-border p-3">
                                <p className="text-[10px] font-black uppercase tracking-widest text-muted mb-2">Custom Range</p>
                                <div className="flex gap-2 items-center">
                                    <input
                                        type="date"
                                        value={customFrom}
                                        onChange={e => setCustomFrom(e.target.value)}
                                        className="flex-1 px-2 py-1.5 rounded-lg border border-border bg-secondary text-[12px] text-header font-medium outline-none focus:border-accent-primary"
                                    />
                                    <span className="text-muted text-[11px]">→</span>
                                    <input
                                        type="date"
                                        value={customTo}
                                        onChange={e => setCustomTo(e.target.value)}
                                        className="flex-1 px-2 py-1.5 rounded-lg border border-border bg-secondary text-[12px] text-header font-medium outline-none focus:border-accent-primary"
                                    />
                                </div>
                                <button
                                    onClick={applyCustom}
                                    disabled={!customFrom || !customTo}
                                    className="mt-2 w-full py-2 rounded-lg bg-accent-primary text-white text-[11px] font-black uppercase tracking-widest disabled:opacity-40 disabled:cursor-not-allowed hover:bg-accent-primary-hover transition-colors"
                                >
                                    Apply
                                </button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Granularity pills */}
            <div className="flex items-center gap-1 bg-surface border border-border rounded-lg p-1">
                <Clock size={11} className="text-muted ml-1 mr-0.5 shrink-0" />
                {GRANULARITIES.map(g => (
                    <button
                        key={g.id}
                        onClick={() => setGranularity(g.id)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-all ${
                            value?.granularity === g.id
                                ? 'bg-accent-primary text-white shadow-sm'
                                : 'text-muted hover:text-header'
                        }`}
                    >
                        {g.label}
                    </button>
                ))}
            </div>

            {/* Clear */}
            {hasFilter && (
                <button
                    onClick={() => onChange({ from: null, to: null, preset: null, granularity: value?.granularity || 'day' })}
                    className="text-[11px] font-bold text-muted hover:text-red-400 transition-colors"
                >
                    Clear
                </button>
            )}
        </div>
    );
};

export default DateRangeBar;
