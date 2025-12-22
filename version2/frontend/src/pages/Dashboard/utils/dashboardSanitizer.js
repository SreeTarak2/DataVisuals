/**
 * Dashboard Sanitizer Utilities
 * 
 * Sanitizes AI-generated dashboard components to remove hardcoded
 * example values and replace them with actual dataset columns.
 * Extracted from Dashboard.jsx to improve code organization.
 */

import { getDatasetColumns, firstNumericColumn, firstCategoricalColumn } from './columnHelpers';

/**
 * Sanitize transformed components by replacing example placeholders
 * with actual dataset column names
 * 
 * @param {Array} components - Array of dashboard components
 * @param {Object} helpers - Helper object with dataset access
 * @param {Array} helpers.datasetData - Full dataset
 * @param {Array} helpers.dataPreview - Preview dataset
 * @returns {Array} Sanitized components array
 */
export const sanitizeTransformedComponents = (components, helpers) => {
    try {
        const { datasetData, dataPreview } = helpers;

        const numCol = firstNumericColumn(datasetData, dataPreview);
        const catCol = firstCategoricalColumn(datasetData, dataPreview);
        const colsAll = getDatasetColumns(datasetData, dataPreview);

        /**
         * Replace known example values with actual column names
         */
        const sanitizeValue = (v) => {
            // Common example column names to replace
            if (v === 'home_wins' || v === 'away_wins') return numCol;
            if (v === 'team') return catCol;
            return v;
        };

        // Deep clone to avoid mutating original
        const deepClone = JSON.parse(JSON.stringify(components));

        /**
         * Recursively walk through object/array structure
         * and sanitize string values
         */
        const walk = (obj) => {
            if (Array.isArray(obj)) {
                for (let i = 0; i < obj.length; i++) {
                    if (typeof obj[i] === 'string') {
                        obj[i] = sanitizeValue(obj[i]);
                    } else if (typeof obj[i] === 'object' && obj[i] !== null) {
                        walk(obj[i]);
                    }
                }
            } else if (typeof obj === 'object' && obj !== null) {
                for (const k of Object.keys(obj)) {
                    if (typeof obj[k] === 'string') {
                        obj[k] = sanitizeValue(obj[k]);
                    } else if (Array.isArray(obj[k])) {
                        obj[k] = obj[k].map(v => (typeof v === 'string' ? sanitizeValue(v) : v));
                    } else if (typeof obj[k] === 'object' && obj[k] !== null) {
                        walk(obj[k]);
                    }
                }
            }
        };

        walk(deepClone);
        return deepClone;
    } catch (e) {
        console.warn('sanitizeTransformedComponents failed', e);
        return components;
    }
};
