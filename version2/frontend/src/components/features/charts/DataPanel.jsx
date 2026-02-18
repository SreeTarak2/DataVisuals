import React, { useState } from 'react';
import { Search, Database, Hash, Calendar, Tag } from 'lucide-react';
import { motion } from 'framer-motion';

// Field type icons
const TYPE_ICONS = {
    numeric: { icon: Hash, color: '#58a6ff' },
    integer: { icon: Hash, color: '#58a6ff' },
    float: { icon: Hash, color: '#58a6ff' },
    temporal: { icon: Calendar, color: '#a371f7' },
    datetime: { icon: Calendar, color: '#a371f7' },
    date: { icon: Calendar, color: '#a371f7' },
    categorical: { icon: Tag, color: '#3fb950' },
    string: { icon: Tag, color: '#3fb950' },
    unknown: { icon: Database, color: '#8b949e' },
};

const DataPanel = ({ columns, encoding, onUpdateEncoding }) => {
    const [searchQuery, setSearchQuery] = useState('');

    // Filter columns by search
    const filteredColumns = columns.filter(col => {
        const name = typeof col === 'string' ? col : col.name;
        return name.toLowerCase().includes(searchQuery.toLowerCase());
    });

    // Group columns by type
    const groupedColumns = {
        numeric: filteredColumns.filter(col => {
            const type = typeof col === 'string' ? 'unknown' : col.type?.toLowerCase();
            return ['numeric', 'integer', 'float', 'int64', 'float64'].includes(type);
        }),
        temporal: filteredColumns.filter(col => {
            const type = typeof col === 'string' ? 'unknown' : col.type?.toLowerCase();
            return ['temporal', 'datetime', 'date', 'timestamp'].includes(type);
        }),
        categorical: filteredColumns.filter(col => {
            const type = typeof col === 'string' ? 'unknown' : col.type?.toLowerCase();
            return ['categorical', 'string', 'object', 'text'].includes(type);
        }),
        other: filteredColumns.filter(col => {
            const type = typeof col === 'string' ? 'unknown' : col.type?.toLowerCase();
            return !['numeric', 'integer', 'float', 'int64', 'float64', 'temporal', 'datetime', 'date', 'timestamp', 'categorical', 'string', 'object', 'text'].includes(type);
        }),
    };

    const getFieldName = (col) => typeof col === 'string' ? col : col.name;
    const getFieldType = (col) => {
        if (typeof col === 'string') return 'unknown';
        const type = col.type?.toLowerCase() || 'unknown';
        if (['numeric', 'integer', 'float', 'int64', 'float64'].includes(type)) return 'numeric';
        if (['temporal', 'datetime', 'date', 'timestamp'].includes(type)) return 'temporal';
        if (['categorical', 'string', 'object', 'text'].includes(type)) return 'categorical';
        return 'unknown';
    };

    const FieldPill = ({ column }) => {
        const name = getFieldName(column);
        const type = getFieldType(column);
        const typeConfig = TYPE_ICONS[type] || TYPE_ICONS.unknown;
        const Icon = typeConfig.icon;

        const isUsed = encoding.x.field === name || encoding.y.field === name;

        return (
            <motion.button
                whileHover={{ x: 2 }}
                onClick={() => {
                    if (!encoding.x.field) {
                        onUpdateEncoding('x', { field: name, type });
                    } else if (!encoding.y.field) {
                        onUpdateEncoding('y', { field: name, type });
                    } else {
                        onUpdateEncoding('y', { field: name, type });
                    }
                }}
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-sm text-left text-xs transition-colors border ${isUsed
                        ? 'bg-blue-900/20 border-blue-500/50 text-blue-200'
                        : 'bg-transparent border-transparent hover:bg-slate-800 text-slate-300 hover:text-slate-100'
                    }`}
            >
                <Icon size={12} style={{ color: typeConfig.color }} />
                <span className="truncate flex-1 font-medium">{name}</span>
                {isUsed && (
                    <span
                        className="text-[10px] px-1 py-0.5 rounded font-bold uppercase"
                        style={{ backgroundColor: typeConfig.color, color: '#000' }}
                    >
                        {encoding.x.field === name ? 'X' : 'Y'}
                    </span>
                )}
            </motion.button>
        );
    };

    const FieldGroup = ({ title, fields, type }) => {
        if (fields.length === 0) return null;
        const typeConfig = TYPE_ICONS[type] || TYPE_ICONS.unknown;

        return (
            <div className="mb-3">
                <div className="flex items-center justify-between px-2 mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{title}</span>
                    <span className="text-[10px] text-slate-600">{fields.length}</span>
                </div>
                <div className="space-y-0.5">
                    {fields.map((col, idx) => (
                        <FieldPill key={idx} column={col} />
                    ))}
                </div>
            </div>
        );
    };

    return (
        <div className="h-full flex flex-col bg-[#0b1117] border-r border-slate-800">
            {/* Header */}
            <div className="p-3 border-b border-slate-800 bg-[#0d141f]">
                <div className="flex items-center gap-2 px-2 py-1.5 rounded bg-slate-900 border border-slate-700 focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500/20 transition-all">
                    <Search size={12} className="text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search fields..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="flex-1 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-600"
                    />
                </div>
            </div>

            {/* Fields List */}
            <div className="flex-1 overflow-y-auto p-2 nice-scrollbar">
                <FieldGroup title="Numeric" fields={groupedColumns.numeric} type="numeric" />
                <FieldGroup title="Date/Time" fields={groupedColumns.temporal} type="temporal" />
                <FieldGroup title="Categorical" fields={groupedColumns.categorical} type="categorical" />
                <FieldGroup title="Other" fields={groupedColumns.other} type="unknown" />

                {filteredColumns.length === 0 && (
                    <div className="text-center py-8 text-xs text-slate-500">
                        {searchQuery ? 'No matching fields' : 'No fields available'}
                    </div>
                )}
            </div>
        </div>
    );
};

export default DataPanel;
