/**
 * Column Helper Utilities
 * 
 * Utilities for identifying and working with dataset columns.
 * Extracted from Dashboard.jsx to improve code organization.
 */

/**
 * Get all column names from dataset
 * @param {Array} datasetData - Full dataset array
 * @param {Array} dataPreview - Preview dataset array
 * @returns {Array<string>} Array of column names
 */
export const getDatasetColumns = (datasetData, dataPreview) => {
    if (datasetData && datasetData.length > 0) {
        return Object.keys(datasetData[0]);
    }
    if (dataPreview && dataPreview.length > 0) {
        return Object.keys(dataPreview[0]);
    }
    return [];
};

/**
 * Find the first numeric column in the dataset
 * @param {Array} datasetData - Full dataset array
 * @param {Array} dataPreview - Preview dataset array
 * @returns {string} Name of first numeric column, or first column as fallback
 */
export const firstNumericColumn = (datasetData, dataPreview) => {
    const cols = getDatasetColumns(datasetData, dataPreview);

    for (let c of cols) {
        const val = datasetData?.[0]?.[c] ?? dataPreview?.[0]?.[c];
        if (typeof val === 'number') return c;
        if (val != null && val !== '' && !isNaN(parseFloat(val))) return c;
    }

    return cols[0] || 'value';
};

/**
 * Find the first categorical (string) column in the dataset
 * @param {Array} datasetData - Full dataset array
 * @param {Array} dataPreview - Preview dataset array
 * @returns {string} Name of first categorical column, or first column as fallback
 */
export const firstCategoricalColumn = (datasetData, dataPreview) => {
    const cols = getDatasetColumns(datasetData, dataPreview);

    for (let c of cols) {
        const val = datasetData?.[0]?.[c] ?? dataPreview?.[0]?.[c];
        if (typeof val === 'string') return c;
    }

    return cols[0] || 'category';
};
