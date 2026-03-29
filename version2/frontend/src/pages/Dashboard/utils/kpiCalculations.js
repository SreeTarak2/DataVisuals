/**
 * KPI Calculation Utilities
 * 
 * Functions for calculating, formatting, and enriching KPI values from dataset.
 * Prefers backend-computed values (from full dataset). Falls back to client-side
 * computation only when backend values are missing.
 */

/**
 * Calculate aggregation on numeric values (client-side fallback only)
 */
export const calculateAggregation = (values, aggregationType) => {
    const agg = aggregationType.toLowerCase();

    if (agg === 'count') return values.length;
    if (agg === 'nunique') return new Set(values).size;

    const numeric = values.map(v => Number(v)).filter(n => !Number.isNaN(n));
    if (numeric.length === 0) return 0;

    switch (agg) {
        case 'sum':
            return numeric.reduce((a, b) => a + b, 0);
        case 'mean':
        case 'avg':
            return numeric.reduce((a, b) => a + b, 0) / numeric.length;
        case 'max':
            return Math.max(...numeric);
        case 'min':
            return Math.min(...numeric);
        default:
            return numeric.reduce((a, b) => a + b, 0);
    }
};

/**
 * Format KPI value for display
 */
export const formatKpiValue = (value) => {
    if (typeof value === 'number') {
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        }).format(value);
    }
    return value;
};

/**
 * Detect format type from column name heuristics (fallback)
 */
const detectFormat = (columnName = '', aggregation = '') => {
    const col = columnName.toLowerCase();
    if (/price|cost|revenue|amount|salary|income|profit|tax|fee|total/.test(col)) return 'currency';
    if (/percent|ratio|rate|efficiency/.test(col)) return 'percentage';
    if (/count|num|number|quantity|total/.test(col) || aggregation === 'count') return 'integer';
    return 'number';
};

/**
 * Map column name keywords to lucide icon names (fallback)
 */
const detectIcon = (columnName = '', aggregation = '') => {
    const col = columnName.toLowerCase();
    if (/price|cost|revenue|amount|salary|income|profit|fee/.test(col)) return 'DollarSign';
    if (/user|customer|employee|person|people|member/.test(col)) return 'Users';
    if (/order|purchase|cart|buy|sale/.test(col)) return 'ShoppingCart';
    if (/count|total|number|quantity/.test(col) || aggregation === 'count') return 'Hash';
    if (/rate|percent|ratio|efficiency/.test(col)) return 'Percent';
    if (/date|time|year|month|day/.test(col)) return 'Calendar';
    if (/mile|distance|speed/.test(col)) return 'Activity';
    if (/target|goal/.test(col)) return 'Target';
    if (/engine|power|energy/.test(col)) return 'Zap';
    if (/file|document|record/.test(col)) return 'FileText';
    if (/package|product|item/.test(col)) return 'Package';
    return 'BarChart3';
};

/**
 * Generate sparkline data by bucketing (client-side fallback only)
 */
const generateSparklineData = (datasetData, columnName) => {
    if (!Array.isArray(datasetData) || datasetData.length < 5 || !columnName) return [];

    const values = datasetData
        .map(row => Number(row[columnName]))
        .filter(n => !isNaN(n));

    if (values.length < 5) return [];

    const bucketCount = Math.min(16, values.length);
    const bucketSize = Math.floor(values.length / bucketCount);
    const sparkline = [];

    for (let i = 0; i < bucketCount; i++) {
        const start = i * bucketSize;
        const end = Math.min(start + bucketSize, values.length);
        const bucket = values.slice(start, end);
        const avg = bucket.reduce((a, b) => a + b, 0) / bucket.length;
        sparkline.push(avg);
    }

    return sparkline;
};

/**
 * Hydrate a KPI component.
 * Prefers backend-computed fields (sparkline_data, comparison_value, format, etc.)
 * Falls back to client-side computation only when backend didn't provide them.
 */
export const hydrateKpiComponent = (component, datasetData) => {
    try {
        if (!component || component.type !== 'kpi') {
            return component;
        }

        const config = component.config || {};
        const column =
            config.column ||
            (config.columns && config.columns[0]) ||
            component.x_axis ||
            component.y_axis ||
            null;

        const aggregation = (
            config.aggregation ||
            component.aggregation ||
            'sum'
        ).toString().toLowerCase();

        // --- Value: prefer backend, fallback to client-side ---
        let value = component.value;
        if ((value === undefined || value === null || value === 'N/A') &&
            column && Array.isArray(datasetData) && datasetData.length > 0) {
            const raw = datasetData
                .map(r => r[column])
                .filter(v => v !== null && v !== undefined && v !== '');
            value = raw.length > 0 ? calculateAggregation(raw, aggregation) : 0;
        }

        // --- Sparkline: prefer backend, fallback to client-side ---
        const sparklineData = (component.sparkline_data && component.sparkline_data.length > 0)
            ? component.sparkline_data
            : generateSparklineData(datasetData, column);

        // --- Comparison: prefer backend, fallback not computed (it's misleading) ---
        const comparisonValue = component.comparison_value ?? null;
        const comparisonLabel = component.comparison_label || null;
        const deltaPercent = component.delta_percent ?? null;

        // --- Format & Icon: prefer backend, fallback to heuristic ---
        const format = component.format || config.format || detectFormat(column, aggregation);
        const icon = config.icon || detectIcon(column, aggregation);

        // --- Extra enrichment from backend ---
        const topValues = component.top_values || null;
        const recordCount = component.record_count ?? null;
        const minValue = component.min_value ?? null;
        const maxValue = component.max_value ?? null;
        const definition = component.definition || null;
        const benchmarkText = component.benchmarkText || null;
        const isOutlier = component.isOutlier || false;
        const aiSuggestion = component.aiSuggestion || null;

        return {
            ...component,
            value,
            sparklineData,
            comparisonValue,
            comparisonLabel,
            deltaPercent,
            format,
            icon,
            topValues,
            recordCount,
            minValue,
            maxValue,
            definition,
            benchmarkText,
            isOutlier,
            aiSuggestion,
        };
    } catch (e) {
        console.warn('hydrateKpiComponent failed', e);
        return component;
    }
};
