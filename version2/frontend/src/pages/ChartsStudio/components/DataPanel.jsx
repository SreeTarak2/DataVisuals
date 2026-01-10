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

const DataPanel = ({ columns, encoding, onUpdateEncoding, colors }) => {
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
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                    // Quick assign: if X is empty, assign to X; else assign to Y
                    if (!encoding.x.field) {
                        onUpdateEncoding('x', { field: name, type });
                    } else if (!encoding.y.field) {
                        onUpdateEncoding('y', { field: name, type });
                    } else {
                        // Replace Y
                        onUpdateEncoding('y', { field: name, type });
                    }
                }}
                className="w-full flex items-center gap-2 px-3 py-2 rounded text-left text-sm transition-colors"
                style={{
                    backgroundColor: isUsed ? `${typeConfig.color}20` : 'transparent',
                    border: isUsed ? `1px solid ${typeConfig.color}` : '1px solid transparent',
                    color: colors.textPrimary,
                }}
            >
                <Icon size={14} style={{ color: typeConfig.color }} />
                <span className="truncate flex-1">{name}</span>
                {isUsed && (
                    <span
                        className="text-xs px-1.5 py-0.5 rounded font-medium"
                        style={{ backgroundColor: typeConfig.color, color: '#fff' }}
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
            <div className="mb-4">
                <div
                    className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium uppercase tracking-wide"
                    style={{ color: typeConfig.color }}
                >
                    {title}
                    <span
                        className="px-1.5 py-0.5 rounded text-xs"
                        style={{ backgroundColor: `${typeConfig.color}20` }}
                    >
                        {fields.length}
                    </span>
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
        <div className="h-full flex flex-col">
            {/* Header */}
            <div
                className="p-3 border-b"
                style={{ borderColor: colors.border }}
            >
                <h2
                    className="text-sm font-semibold mb-2"
                    style={{ color: colors.textPrimary }}
                >
                    Data Fields
                </h2>

                {/* Search */}
                <div
                    className="flex items-center gap-2 px-3 py-2 rounded"
                    style={{ backgroundColor: colors.bg }}
                >
                    <Search size={14} style={{ color: colors.textSecondary }} />
                    <input
                        type="text"
                        placeholder="Search fields..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="flex-1 bg-transparent text-sm outline-none"
                        style={{ color: colors.textPrimary }}
                    />
                </div>
            </div>

            {/* Fields List */}
            <div className="flex-1 overflow-y-auto p-2">
                <FieldGroup title="Numeric" fields={groupedColumns.numeric} type="numeric" />
                <FieldGroup title="Date/Time" fields={groupedColumns.temporal} type="temporal" />
                <FieldGroup title="Categorical" fields={groupedColumns.categorical} type="categorical" />
                <FieldGroup title="Other" fields={groupedColumns.other} type="unknown" />

                {filteredColumns.length === 0 && (
                    <div
                        className="text-center py-8 text-sm"
                        style={{ color: colors.textSecondary }}
                    >
                        {searchQuery ? 'No matching fields' : 'No fields available'}
                    </div>
                )}
            </div>

            {/* Quick Help */}
            <div
                className="p-3 border-t text-xs"
                style={{ borderColor: colors.border, color: colors.textSecondary }}
            >
                Click a field to assign to X or Y axis
            </div>
        </div>
    );
};

export default DataPanel;
