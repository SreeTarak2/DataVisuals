/**
 * KPI Calculation Utilities
 * 
 * Functions for calculating, formatting, and enriching KPI values from dataset.
 * Generates sparkline data, comparison deltas, format hints, and icon mappings.
 */

/**
 * Calculate aggregation on numeric values
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
 * Detect format type from column name heuristics
 */
const detectFormat = (columnName = '', aggregation = '') => {
    const col = columnName.toLowerCase();
    if (/price|cost|revenue|amount|salary|income|profit|tax|fee|total/.test(col)) return 'currency';
    if (/percent|ratio|rate|efficiency/.test(col)) return 'percentage';
    if (/count|num|number|quantity|total/.test(col) || aggregation === 'count') return 'integer';
    return 'number';
};

/**
 * Map column name keywords to lucide icon names
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
 * Generate sparkline data by bucketing dataset values into ~20 bins
 * Creates a mini trend line from the raw column data
 */
const generateSparklineData = (datasetData, columnName) => {
    if (!Array.isArray(datasetData) || datasetData.length < 5 || !columnName) return [];

    const values = datasetData
        .map(row => Number(row[columnName]))
        .filter(n => !isNaN(n));

    if (values.length < 5) return [];

    // Bucket into ~20 points for a smooth sparkline
    const bucketCount = Math.min(20, values.length);
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
 * Calculate a simple comparison value by comparing first-half vs second-half averages
 */
const generateComparisonValue = (datasetData, columnName, aggregation) => {
    if (!Array.isArray(datasetData) || datasetData.length < 6 || !columnName) return null;

    const values = datasetData
        .map(row => Number(row[columnName]))
        .filter(n => !isNaN(n));

    if (values.length < 6) return null;

    const mid = Math.floor(values.length / 2);
    const firstHalf = values.slice(0, mid);
    const secondHalf = values.slice(mid);

    const agg = (aggregation || 'mean').toLowerCase();

    if (agg === 'sum') {
        return firstHalf.reduce((a, b) => a + b, 0);
    }
    if (agg === 'count') {
        return firstHalf.length;
    }

    // Default: mean of first half as "previous period"
    return firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
};

/**
 * Hydrate a KPI component with real data values, sparkline, and comparison
 */
export const hydrateKpiComponent = (component, datasetData) => {
    try {
        if (!component || component.type !== 'kpi') {
            return component;
        }

        const config = component.config || {};

        // Find column name
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

        let value = component.value ?? 'N/A';

        if (column && Array.isArray(datasetData) && datasetData.length > 0) {
            const raw = datasetData
                .map(r => r[column])
                .filter(v => v !== null && v !== undefined && v !== '');

            if (raw.length > 0) {
                value = calculateAggregation(raw, aggregation);
            } else {
                value = 0;
            }
        }

        // Enrichment: sparkline, comparison, format, icon
        const sparklineData = generateSparklineData(datasetData, column);
        const comparisonValue = generateComparisonValue(datasetData, column, aggregation);
        const format = config.format || detectFormat(column, aggregation);
        const icon = config.icon || detectIcon(column, aggregation);

        return {
            ...component,
            value,
            sparklineData,
            comparisonValue,
            format,
            icon,
            comparisonLabel: 'vs prior half'
        };
    } catch (e) {
        console.warn('hydrateKpiComponent failed', e);
        return component;
    }
};
