import React, { useState } from 'react';
import { Search, Database, Hash, Calendar, Tag } from 'lucide-react';
import { motion } from 'framer-motion';

const TYPE_ICONS = {
    numeric: { icon: Hash, color: '#5B88B2' },
    integer: { icon: Hash, color: '#5B88B2' },
    float: { icon: Hash, color: '#5B88B2' },
    temporal: { icon: Calendar, color: '#a78bfa' },
    datetime: { icon: Calendar, color: '#a78bfa' },
    date: { icon: Calendar, color: '#a78bfa' },
    categorical: { icon: Tag, color: '#10b981' },
    string: { icon: Tag, color: '#10b981' },
    unknown: { icon: Database, color: '#64748b' },
};

const DataPanel = ({ columns, encoding, onUpdateEncoding }) => {
    const [searchQuery, setSearchQuery] = useState('');

    const filteredColumns = columns.filter(col => {
        const name = typeof col === 'string' ? col : col.name;
        return name.toLowerCase().includes(searchQuery.toLowerCase());
    });

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
                    // Toggle off if already selected
                    if (encoding.x.field === name) {
                        onUpdateEncoding('x', { field: '', type: '' });
                    } else if (encoding.y.field === name) {
                        onUpdateEncoding('y', { field: '', type: '' });
                    } else if (!encoding.x.field) {
                        onUpdateEncoding('x', { field: name, type });
                    } else if (!encoding.y.field) {
                        onUpdateEncoding('y', { field: name, type });
                    } else {
                        // Both assigned — replace Y
                        onUpdateEncoding('y', { field: name, type });
                    }
                }}
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-left text-[11px] transition-colors ${isUsed
                        ? 'bg-pearl/[0.06] border border-pearl/[0.12] text-pearl'
                        : 'bg-transparent border border-transparent hover:bg-pearl/[0.04] text-granite hover:text-pearl'
                    }`}
            >
                <Icon size={12} style={{ color: typeConfig.color }} />
                <span className="truncate flex-1 font-medium">{name}</span>
                {isUsed && (
                    <span
                        className="text-[9px] px-1 py-px rounded font-bold uppercase"
                        style={{ backgroundColor: typeConfig.color, color: '#020203' }}
                    >
                        {encoding.x.field === name ? 'X' : 'Y'}
                    </span>
                )}
            </motion.button>
        );
    };

    const FieldGroup = ({ title, fields, type }) => {
        if (fields.length === 0) return null;
        return (
            <div className="mb-3">
                <div className="flex items-center justify-between px-2 mb-1">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-granite">{title}</span>
                    <span className="text-[10px] text-granite/50">{fields.length}</span>
                </div>
                <div className="space-y-px">
                    {fields.map((col, idx) => (
                        <FieldPill key={idx} column={col} />
                    ))}
                </div>
            </div>
        );
    };

    return (
        <div className="h-full flex flex-col bg-midnight border-r border-pearl/[0.06]">
            {/* Search */}
            <div className="p-3 border-b border-pearl/[0.06]">
                <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-pearl/[0.04] border border-pearl/[0.06] focus-within:border-ocean/30 transition-colors">
                    <Search size={12} className="text-granite" />
                    <input
                        type="text"
                        placeholder="Search fields…"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="flex-1 bg-transparent text-[11px] text-pearl outline-none placeholder:text-granite"
                    />
                </div>
            </div>

            {/* Fields */}
            <div className="flex-1 overflow-y-auto p-2 nice-scrollbar">
                <FieldGroup title="Numeric" fields={groupedColumns.numeric} type="numeric" />
                <FieldGroup title="Date/Time" fields={groupedColumns.temporal} type="temporal" />
                <FieldGroup title="Categorical" fields={groupedColumns.categorical} type="categorical" />
                <FieldGroup title="Other" fields={groupedColumns.other} type="unknown" />

                {filteredColumns.length === 0 && (
                    <div className="text-center py-8 text-[11px] text-granite">
                        {searchQuery ? 'No matching fields' : 'No fields available'}
                    </div>
                )}
            </div>
        </div>
    );
};

export default DataPanel;
