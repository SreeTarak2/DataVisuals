import React, { useState } from 'react';
import { Database, Search, Hash } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '../../../lib/utils';

const DataPanel = ({ columns, encoding, onUpdateEncoding }) => {
    const [searchTerm, setSearchTerm] = useState('');

    const groupedColumns = {
        QUANTITATIVE: columns.filter(c => {
            const t = (typeof c === 'string' ? 'unknown' : c.type?.toLowerCase()) || '';
            return ['numeric', 'integer', 'float', 'int64', 'float64'].includes(t);
        }),
        CATEGORICAL: columns.filter(c => {
            const t = (typeof c === 'string' ? 'unknown' : c.type?.toLowerCase()) || '';
            return !['numeric', 'integer', 'float', 'int64', 'float64'].includes(t);
        }),
    };

    const FieldPill = ({ col }) => {
        const name = typeof col === 'string' ? col : col.name;
        const isX = encoding.x.field === name;
        const isY = encoding.y.field === name;
        const isActive = isX || isY;

        return (
            <motion.div
                whileHover={{ x: 3 }}
                whileTap={{ scale: 0.98 }}
                className={cn(
                    "group flex items-center justify-between px-3 py-2.5 rounded-lg transition-all cursor-pointer select-none",
                    isActive
                        ? "bg-header text-surface shadow-xl shadow-black/10"
                        : "bg-transparent hover:bg-secondary/20 text-secondary"
                )}
                onClick={() => onUpdateEncoding(isActive ? (isX ? 'x' : 'y') : (encoding.x.field ? 'y' : 'x'), isActive ? '' : name)}
            >
                <div className="flex items-center gap-3 min-w-0">
                    <div className={cn(
                        "w-5 h-5 rounded flex items-center justify-center shrink-0 shadow-inner",
                        isActive ? "bg-surface/20" : "bg-secondary/10 text-muted group-hover:bg-header group-hover:text-surface"
                    )}>
                        <Hash size={11} strokeWidth={3} />
                    </div>
                    <span className={cn(
                        "text-[12.5px] font-bold truncate tracking-tight",
                        isActive ? "text-surface" : "text-header group-hover:text-primary transition-colors"
                    )}>
                        {name}
                    </span>
                </div>
                {isActive && (
                    <div className="flex items-center gap-1 shrink-0">
                        <span className="w-5 h-5 rounded bg-surface text-header text-[10px] font-black flex items-center justify-center shadow-md">
                            {isX ? 'X' : 'Y'}
                        </span>
                    </div>
                )}
            </motion.div>
        );
    };

    return (
        <div className="h-full flex flex-col bg-surface font-sans select-none overflow-hidden">
            {/* Header */}
            <div className="px-5 py-6">
                <h2 className="text-[13px] font-black text-header uppercase tracking-[0.2em] flex items-center gap-3">
                    <Database size={16} className="text-accent-primary" strokeWidth={3} />
                    VARIABLES
                </h2>
            </div>

            {/* Search - Inset Style, No Border */}
            <div className="px-5 pb-6">
                <div className="relative group bg-secondary/30 shadow-inner rounded-lg transition-all focus-within:bg-secondary/50">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={14} strokeWidth={2.5} />
                    <input
                        type="text"
                        placeholder="Search fields..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full bg-transparent pl-9 pr-4 py-3 text-[13px] font-semibold text-header placeholder:text-muted/40 outline-none"
                    />
                </div>
            </div>

            {/* List Body */}
            <div className="flex-1 overflow-y-auto studio-scrollbar px-3 py-2 bg-secondary/10 shadow-inner">
                {(() => {
                    let hasResults = false;
                    const items = Object.entries(groupedColumns).map(([group, fields]) => {
                        const filteredFields = fields.filter(f =>
                            (typeof f === 'string' ? f : f.name).toLowerCase().includes(searchTerm.toLowerCase())
                        );
                        if (filteredFields.length === 0) return null;
                        hasResults = true;

                        return (
                            <div key={group} className="mb-8 first:mt-2 last:mb-0">
                                <div className="px-2 mb-3 flex items-center justify-between group/header">
                                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-[0.25em]">
                                        {group}
                                    </span>
                                    <div className="px-1.5 py-0.5 rounded-md bg-secondary/30 text-[9px] font-black text-secondary shadow-inner">
                                        {filteredFields.length}
                                    </div>
                                </div>
                                <div className="grid gap-0.5">
                                    {filteredFields.map((field, i) => (
                                        <FieldPill key={i} col={field} />
                                    ))}
                                </div>
                            </div>
                        );
                    });

                    if (!hasResults && searchTerm) {
                        return (
                            <div className="h-full flex flex-col items-center justify-center py-20 px-6 opacity-90 transition-opacity">
                                <Search size={24} className="mb-4 text-accent-primary" />
                                <p className="text-[13px] font-black uppercase tracking-widest text-secondary text-center leading-relaxed">
                                    No results found for<br />
                                    <span className="text-header font-black opacity-100 italic">"{searchTerm}"</span>
                                </p>
                            </div>
                        );
                    }
                    return items;
                })()}
            </div>

            {/* Status Integration */}
            <div className="mt-auto p-5 bg-secondary/20 backdrop-blur-sm">
                <div className="flex items-center justify-between text-[10px] font-black text-muted tracking-widest uppercase opacity-60">
                    <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-success" />
                        SYSTEM READY
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DataPanel;
