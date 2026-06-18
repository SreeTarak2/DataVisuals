import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Table, Grid, Info, Filter } from 'lucide-react';
import { useChartTheme } from '../../../hooks/useChartTheme';
import useDashboardActionStore from '../../../store/dashboardActionStore';

/**
 * PivotTable Component
 * Renders a high-fidelity multi-dimensional grid for data exploration.
 */
const PivotTable = ({ component, datasetData }) => {
  const { colors } = useChartTheme();
  const { crossFilter, setCrossFilter } = useDashboardActionStore();
  
  // Extract data from the component or hydrated data
  const data = useMemo(() => {
    return component.chart_data?.data || component.data || [];
  }, [component]);

  // Handle row click for cross-filtering
  const handleRowClick = (row) => {
    // Usually we filter by the first column (dimension)
    const firstCol = Object.keys(row)[0];
    const value = row[firstCol];
    if (crossFilter === String(value)) {
      setCrossFilter(null); // Toggle off
    } else {
      setCrossFilter(String(value));
    }
  };

  // If no data, show empty state
  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <Grid className="w-12 h-12 mb-4 opacity-20" style={{ color: colors?.primary }} />
        <p className="text-sm opacity-50" style={{ color: colors?.text }}>
          No pivot data available for this selection.
        </p>
      </div>
    );
  }

  // Get columns from data
  const columns = useMemo(() => {
    if (data.length === 0) return [];
    return Object.keys(data[0]);
  }, [data]);

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col h-full overflow-hidden"
    >
      <div className="flex-1 overflow-auto custom-scrollbar">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10">
            <tr style={{ background: colors?.cardBg }}>
              {columns.map((col, i) => (
                <th 
                  key={col}
                  className="px-4 py-3 text-left font-semibold border-b tracking-wider uppercase text-[11px]"
                  style={{ 
                    borderColor: colors?.border,
                    color: colors?.text,
                    opacity: 0.7,
                    borderRight: i < columns.length - 1 ? `1px solid ${colors?.border}40` : 'none'
                  }}
                >
                  {col.replace(/_/g, ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 100).map((row, i) => {
              const firstCol = Object.keys(row)[0];
              const isFiltered = crossFilter === String(row[firstCol]);

              return (
                <tr 
                  key={i} 
                  onClick={() => handleRowClick(row)}
                  className="group cursor-pointer transition-colors"
                  style={{ 
                    borderBottom: `1px solid ${colors?.border}40`,
                    background: isFiltered ? `${colors?.primary}15` : 'transparent'
                  }}
                >
                  {columns.map((col, j) => {
                  const val = row[col];
                  const isNumeric = typeof val === 'number';
                  
                  return (
                    <td 
                      key={col}
                      className={`px-4 py-3 whitespace-nowrap ${isNumeric ? 'font-mono text-right' : ''}`}
                      style={{ 
                        color: colors?.text,
                        borderRight: j < columns.length - 1 ? `1px solid ${colors?.border}20` : 'none'
                      }}
                    >
                      {isNumeric 
                        ? val.toLocaleString(undefined, { 
                            minimumFractionDigits: val % 1 === 0 ? 0 : 2,
                            maximumFractionDigits: 2 
                          })
                        : String(val)}
                    </td>
                  );
                })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      
      {data.length > 100 && (
        <div className="px-4 py-2 text-[11px] opacity-40 border-t" style={{ borderColor: colors?.border, color: colors?.text }}>
          Showing top 100 of {data.length} records
        </div>
      )}
    </motion.div>
  );
};

export default PivotTable;
