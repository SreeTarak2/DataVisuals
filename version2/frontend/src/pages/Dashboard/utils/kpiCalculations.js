/**
 * KPI Calculation Utilities
 * 
 * Functions for calculating and formatting KPI values from dataset.
 * Enhanced with enterprise features: comparisons, goals, status, sparklines.
 */

/**
 * Calculate aggregation on numeric values
 * @param {Array<number>} values - Array of numeric values
 * @param {string} aggregationType - Type of aggregation (sum, mean, count, etc.)
 * @returns {number} Calculated value
 */
export const calculateAggregation = (values, aggregationType) => {
    const agg = (aggregationType || 'sum').toLowerCase();

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

// ============================================
// ENTERPRISE KPI FUNCTIONS
// ============================================

/**
 * Calculate period-over-period comparison
 * @param {number} currentValue - Current period value
 * @param {number} previousValue - Previous period value
 * @returns {Object|null} Comparison data or null if not calculable
 */
export const calculateComparison = (currentValue, previousValue) => {
    if (previousValue === null || previousValue === undefined || previousValue === 0) {
        return null;
    }

    const delta = currentValue - previousValue;
    const percentChange = (delta / Math.abs(previousValue)) * 100;

    return {
        delta,
        percentChange,
        direction: delta > 0 ? 'up' : delta < 0 ? 'down' : 'neutral'
    };
};

/**
 * Calculate goal/target progress
 * @param {number} currentValue - Current value
 * @param {number} targetValue - Target/goal value
 * @returns {Object|null} Progress data or null
 */
export const calculateGoalProgress = (currentValue, targetValue) => {
    if (!targetValue || targetValue === 0) return null;

    const progress = Math.min((currentValue / targetValue) * 100, 100);

    return {
        progress,
        remaining: Math.max(targetValue - currentValue, 0),
        achieved: currentValue >= targetValue
    };
};

/**
 * Determine KPI status based on performance
 * @param {number} percentChange - Percentage change from comparison
 * @param {Object} thresholds - Custom thresholds
 * @returns {string} Status: 'success' | 'warning' | 'critical' | 'neutral'
 */
export const determineKpiStatus = (percentChange, thresholds = {}) => {
    const { critical = -10, warning = 0 } = thresholds;

    if (percentChange === null || percentChange === undefined) return 'neutral';
    if (percentChange <= critical) return 'critical';
    if (percentChange <= warning) return 'warning';
    return 'success';
};

/**
 * Generate sparkline data from dataset
 * Samples the data to create trend visualization
 * @param {Array} datasetData - Full dataset
 * @param {string} column - Column to extract values from
 * @param {number} maxPoints - Maximum number of points (default 12)
 * @returns {Array} Array of {x, y} points for sparkline
 */
export const generateSparklineData = (datasetData, column, maxPoints = 12) => {
    if (!datasetData || !Array.isArray(datasetData) || datasetData.length === 0) {
        return [];
    }

    // Extract numeric values for the column
    const values = datasetData
        .map(row => row[column])
        .filter(v => v !== null && v !== undefined)
        .map(v => Number(v))
        .filter(n => !isNaN(n));

    if (values.length === 0) return [];

    // Sample values if too many
    const step = Math.max(1, Math.floor(values.length / maxPoints));
    const sampled = values.filter((_, i) => i % step === 0).slice(0, maxPoints);

    return sampled.map((y, x) => ({ x, y }));
};

/**
 * Generate mock comparison value (for demo purposes)
 * Creates a realistic previous period value based on current value
 * @param {number} currentValue - Current value
 * @param {string} aggregation - Aggregation type
 * @returns {number|null} Mock previous value
 */
export const generateMockComparison = (currentValue, aggregation) => {
    if (typeof currentValue !== 'number' || isNaN(currentValue)) return null;

    // Generate a random variance between -15% and +20%
    const variance = (Math.random() * 0.35) - 0.15;
    const previousValue = currentValue / (1 + variance);

    return Math.round(previousValue * 100) / 100;
};

/**
 * Generate mock target value (for demo purposes)
 * Creates a realistic goal based on current value
 * @param {number} currentValue - Current value
 * @returns {number|null} Mock target value
 */
export const generateMockTarget = (currentValue) => {
    if (typeof currentValue !== 'number' || isNaN(currentValue)) return null;

    // Target is typically 5-25% higher than current
    const targetMultiplier = 1 + (Math.random() * 0.20) + 0.05;
    return Math.round(currentValue * targetMultiplier * 100) / 100;
};

/**
 * Determine appropriate format for KPI based on column name and values
 * @param {string} column - Column name
 * @param {number} value - Value
 * @returns {string} Format type: 'currency' | 'percentage' | 'integer' | 'decimal'
 */
export const inferKpiFormat = (column, value) => {
    const colLower = (column || '').toLowerCase();

    // Currency indicators
    if (/price|revenue|sales|cost|amount|total|profit|income|expense|budget/i.test(colLower)) {
        return 'currency';
    }

    // Percentage indicators
    if (/rate|ratio|percent|pct|growth|change|margin/i.test(colLower)) {
        return 'percentage';
    }

    // Count/integer indicators
    if (/count|quantity|qty|units|number|num|id/i.test(colLower)) {
        return 'integer';
    }

    // Check if value looks like a percentage (0-100 or small decimal)
    if (typeof value === 'number' && value >= 0 && value <= 1) {
        return 'percentage';
    }

    return 'number';
};

/**
 * Map aggregation type to semantic icon
 * @param {string} aggregation - Aggregation type
 * @param {string} column - Column name (for context)
 * @returns {string} Icon name
 */
export const getKpiIcon = (aggregation, column) => {
    const colLower = (column || '').toLowerCase();
    const agg = (aggregation || 'sum').toLowerCase();

    // Column-based icons (priority)
    if (/user|customer|client|member/i.test(colLower)) return 'Users';
    if (/revenue|sales|price|cost|amount|profit/i.test(colLower)) return 'DollarSign';
    if (/order|transaction|purchase/i.test(colLower)) return 'ShoppingCart';
    if (/product|item|inventory/i.test(colLower)) return 'Package';
    if (/date|time|period/i.test(colLower)) return 'Calendar';
    if (/percent|rate|ratio/i.test(colLower)) return 'Percent';

    // Aggregation-based icons
    switch (agg) {
        case 'count':
        case 'nunique':
            return 'Hash';
        case 'sum':
            return 'Activity';
        case 'mean':
        case 'avg':
            return 'BarChart3';
        case 'max':
            return 'TrendingUp';
        case 'min':
            return 'Target';
        default:
            return 'BarChart3';
    }
};

/**
 * Hydrate a KPI component with real data values (legacy)
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

/**
 * Hydrate a KPI component with enterprise data (comparisons, goals, sparklines)
 * Uses backend-provided data when available, falls back to mock generation
 * @param {Object} component - KPI component configuration
 * @param {Array} datasetData - Full dataset array
 * @param {Object} options - Options for mock data generation
 * @returns {Object} Component with enterprise data
 */
export const hydrateEnterpriseKpiComponent = (component, datasetData, options = {}) => {
    try {
        if (!component || component.type !== 'kpi') {
            return component;
        }

        const { enableMockComparison = true, enableMockTarget = true } = options;
        const config = component.config || {};

        // Extract column and aggregation
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

        // Check if backend already provided enterprise data
        const hasBackendEnterpriseData =
            component.comparison_value !== undefined ||
            component.target_value !== undefined ||
            (component.sparkline_data && component.sparkline_data.length > 0);

        // Use backend value if provided, otherwise calculate
        let value = component.value ?? 0;

        // If value is a formatted string, try to get raw_value
        if (typeof value === 'string' && component.raw_value !== undefined) {
            value = component.raw_value;
        }

        // If still need to calculate value from data
        if ((value === 0 || value === 'N/A') && column && Array.isArray(datasetData) && datasetData.length > 0) {
            const raw = datasetData
                .map(r => r[column])
                .filter(v => v !== null && v !== undefined && v !== '');

            if (raw.length > 0) {
                value = calculateAggregation(raw, aggregation);
            }
        }

        // Use backend enterprise data if available, otherwise generate fallback
        const comparisonValue = component.comparison_value ??
            (enableMockComparison ? generateMockComparison(value, aggregation) : null);

        const targetValue = component.target_value ??
            (enableMockTarget ? generateMockTarget(value) : null);

        const sparklineData = (component.sparkline_data && component.sparkline_data.length > 0)
            ? component.sparkline_data
            : (column ? generateSparklineData(datasetData, column, 12) : []);

        // Use backend format if provided, otherwise infer
        const format = component.format || inferKpiFormat(column, value);

        // Use backend icon or infer from column/aggregation
        const icon = component.icon || getKpiIcon(aggregation, column);

        return {
            ...component,
            // Core data
            value,
            format,
            // Comparison (from backend or mock)
            comparisonValue,
            comparisonLabel: component.comparison_label || 'vs last period',
            // Goal (from backend or mock)
            targetValue,
            targetLabel: component.target_label || (targetValue ? `Goal: ${formatKpiValue(targetValue)}` : null),
            // Trend (from backend or generated)
            sparklineData,
            // Context (from backend)
            context: component.context || '',
            // Appearance
            icon,
            // Pass through config
            config: {
                ...config,
                column,
                aggregation
            }
        };
    } catch (e) {
        console.warn('hydrateEnterpriseKpiComponent failed', e);
        return component;
    }
};


