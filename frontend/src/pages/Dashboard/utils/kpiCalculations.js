/**
 * KPI Calculation Utilities
 * 
 * Functions for calculating and formatting KPI values from dataset.
 * Extracted from Dashboard.jsx to improve code organization.
 */

/**
 * Calculate aggregation on numeric values
 * @param {Array<number>} values - Array of numeric values
 * @param {string} aggregationType - Type of aggregation (sum, mean, count, etc.)
 * @returns {number} Calculated value
 */
export const calculateAggregation = (values, aggregationType) => {
    const agg = aggregationType.toLowerCase();

    if (agg === 'count') {
        return values.length;
    }

    if (agg === 'nunique') {
        return new Set(values).size;
    }

    // Numeric aggregations
    const numeric = values.map(v => Number(v)).filter(n => !Number.isNaN(n));

    if (numeric.length === 0) {
        return 0;
    }

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
            // Fallback to sum
            return numeric.reduce((a, b) => a + b, 0);
    }
};

/**
 * Format KPI value for display
 * @param {number|string} value - Value to format
 * @returns {string} Formatted value
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
 * Hydrate a KPI component with real data values
 * @param {Object} component - KPI component configuration
 * @param {Array} datasetData - Full dataset array
 * @returns {Object} Component with hydrated value
 */
export const hydrateKpiComponent = (component, datasetData) => {
    try {
        if (!component || component.type !== 'kpi') {
            return component;
        }

        const config = component.config || {};

        // Try to find column name from various possible locations
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
            // Collect values for the column
            const raw = datasetData
                .map(r => r[column])
                .filter(v => v !== null && v !== undefined && v !== '');

            if (raw.length > 0) {
                value = calculateAggregation(raw, aggregation);
                value = formatKpiValue(value);
            } else {
                value = 0;
            }
        }

        return { ...component, value };
    } catch (e) {
        console.warn('hydrateKpiComponent failed', e);
        return component;
    }
};
