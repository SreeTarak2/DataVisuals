/**
 * useKpiHydration Hook
 * 
 * Custom hook for hydrating KPI components with real data values.
 * Extracted from Dashboard.jsx to separate KPI calculation concerns.
 */

import { useCallback } from 'react';
import { hydrateKpiComponent } from '../utils/kpiCalculations';

export const useKpiHydration = (datasetData) => {
    const hydrateComponents = useCallback((components) => {
        if (!components || !Array.isArray(components)) {
            return components;
        }

        return components.map(component => {
            if (component.type === 'kpi') {
                return hydrateKpiComponent(component, datasetData);
            }
            return component;
        });
    }, [datasetData]);

    return { hydrateComponents };
};
