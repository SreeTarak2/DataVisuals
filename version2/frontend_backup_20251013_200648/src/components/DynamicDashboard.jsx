import React, { useState, useEffect } from 'react';
import { Loader2, RefreshCw, Download, Share2, Settings } from 'lucide-react';
import { useDashboard } from '../contexts/DashboardContext';
import { useDataset } from '../contexts/DatasetContext';
import KPIWidget from './KPIWidget';
import ModernCard from './ModernCard';
import ChartContainer from './ChartContainer';
import LoadingSpinner, { SkeletonCard } from './LoadingSpinner';

const DynamicDashboard = ({ datasetId, dashboardConfig, onRefresh }) => {
  const { renderChartPreview, loading } = useDashboard();
  const { getDatasetData } = useDataset();
  const [dashboardData, setDashboardData] = useState(null);
  const [chartData, setChartData] = useState({});
  const [loadingCharts, setLoadingCharts] = useState(false);

  useEffect(() => {
    if (dashboardConfig) {
      loadDashboardData();
    }
  }, [dashboardConfig, datasetId]);

  const loadDashboardData = async () => {
    if (!dashboardConfig || !dashboardConfig.components) return;

    setLoadingCharts(true);
    try {
      // Load dataset data first
      const datasetData = await getDatasetData(datasetId, 1, 1000);
      
      // Process each component and load chart data
      const processedComponents = await Promise.all(
        dashboardConfig.components.map(async (component) => {
          if (component.type === 'chart' && component.config) {
            try {
              const chartResult = await renderChartPreview(component.config, datasetId);
              return {
                ...component,
                data: chartResult,
                loaded: true
              };
            } catch (error) {
              console.error(`Error loading chart for component ${component.title}:`, error);
              return {
                ...component,
                error: error.message,
                loaded: false
              };
            }
          }
          
          // For KPI and table components, process the data directly
          if (component.type === 'kpi' || component.type === 'table') {
            return processComponentData(component, datasetData.data);
          }
          
          return component;
        })
      );

      setDashboardData({
        ...dashboardConfig,
        components: processedComponents
      });
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoadingCharts(false);
    }
  };

  const processComponentData = (component, data) => {
    if (component.type === 'kpi' && component.config) {
      const { column, aggregation } = component.config;
      
      if (!data || !Array.isArray(data)) {
        return { ...component, error: 'No data available' };
      }

      let value;
      switch (aggregation) {
        case 'sum':
          value = data.reduce((sum, row) => sum + (parseFloat(row[column]) || 0), 0);
          break;
        case 'mean':
          const validValues = data.map(row => parseFloat(row[column])).filter(val => !isNaN(val));
          value = validValues.length > 0 ? validValues.reduce((sum, val) => sum + val, 0) / validValues.length : 0;
          break;
        case 'count':
          value = data.length;
          break;
        case 'nunique':
          const uniqueValues = new Set(data.map(row => row[column]).filter(val => val !== null && val !== undefined));
          value = uniqueValues.size;
          break;
        default:
          value = data.length;
      }

      return {
        ...component,
        kpiValue: value,
        loaded: true
      };
    }

    if (component.type === 'table' && component.config) {
      const { columns } = component.config;
      const tableData = data.slice(0, 100); // Limit to first 100 rows for performance
      
      return {
        ...component,
        tableData,
        loaded: true
      };
    }

    return component;
  };

  const renderComponent = (component, index) => {
    if (!component.loaded && component.type !== 'chart') {
      return <SkeletonCard key={index} />;
    }

    switch (component.type) {
      case 'kpi':
        return (
          <KPIWidget
            key={index}
            title={component.title}
            value={component.kpiValue || 0}
            icon={getKPIIcon(component.title)}
            subtitle={`${component.config?.aggregation || 'total'} of ${component.config?.column || 'data'}`}
          />
        );

      case 'chart':
        return (
          <ChartContainer
            key={index}
            title={component.title}
            subtitle={component.config?.chart_type || 'Chart'}
            loading={loadingCharts}
            error={component.error}
            onRefresh={loadDashboardData}
          >
            {component.data && component.loaded ? (
              <div className="h-full w-full">
                {/* Render chart based on type */}
                <div className="text-center p-4">
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Chart data loaded successfully
                  </p>
                  <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                    Chart type: {component.config?.chart_type}
                  </p>
                </div>
              </div>
            ) : component.error ? (
              <div className="text-center p-4">
                <p className="text-sm text-red-500">{component.error}</p>
              </div>
            ) : (
              <LoadingSpinner text="Loading chart..." />
            )}
          </ChartContainer>
        );

      case 'table':
        return (
          <ModernCard
            key={index}
            title={component.title}
            subtitle="Data table"
          >
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {component.config?.columns?.map((col, idx) => (
                      <th key={idx}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {component.tableData?.slice(0, 10).map((row, rowIdx) => (
                    <tr key={rowIdx}>
                      {component.config?.columns?.map((col, colIdx) => (
                        <td key={colIdx}>{row[col] || '-'}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {component.tableData?.length > 10 && (
                <p className="text-xs mt-2 text-center" style={{ color: 'var(--text-muted)' }}>
                  Showing first 10 rows of {component.tableData.length} total rows
                </p>
              )}
            </div>
          </ModernCard>
        );

      default:
        return (
          <ModernCard key={index} title={component.title || 'Component'}>
            <p style={{ color: 'var(--text-secondary)' }}>
              Unknown component type: {component.type}
            </p>
          </ModernCard>
        );
    }
  };

  const getKPIIcon = (title) => {
    // You can import icons and return appropriate ones based on title
    // For now, returning a generic icon
    return null;
  };

  if (!dashboardConfig) {
    return (
      <div className="text-center p-8">
        <p style={{ color: 'var(--text-secondary)' }}>
          No dashboard configuration available. Generate a dashboard first.
        </p>
      </div>
    );
  }

  const gridTemplateColumns = dashboardConfig.layout_grid || 'repeat(auto-fit, minmax(300px, 1fr))';

  return (
    <div className="space-y-6">
      {/* Dashboard Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            AI Generated Dashboard
          </h2>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            Automatically designed based on your dataset
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={onRefresh}
            disabled={loadingCharts}
            className="p-2 rounded-lg transition-colors duration-200 hover:bg-hover"
            style={{ color: 'var(--text-secondary)' }}
            title="Refresh Dashboard"
          >
            <RefreshCw className={`w-4 h-4 ${loadingCharts ? 'loading-spin' : ''}`} />
          </button>
          
          <button
            className="p-2 rounded-lg transition-colors duration-200 hover:bg-hover"
            style={{ color: 'var(--text-secondary)' }}
            title="Export Dashboard"
          >
            <Download className="w-4 h-4" />
          </button>
          
          <button
            className="p-2 rounded-lg transition-colors duration-200 hover:bg-hover"
            style={{ color: 'var(--text-secondary)' }}
            title="Share Dashboard"
          >
            <Share2 className="w-4 h-4" />
          </button>
          
          <button
            className="p-2 rounded-lg transition-colors duration-200 hover:bg-hover"
            style={{ color: 'var(--text-secondary)' }}
            title="Dashboard Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Dashboard Grid */}
      <div 
        className="grid gap-6"
        style={{ 
          gridTemplateColumns,
          gridAutoRows: 'minmax(200px, auto)'
        }}
      >
        {dashboardData?.components?.map((component, index) => (
          <div 
            key={index}
            style={{ gridColumn: `span ${component.span || 1}` }}
          >
            {renderComponent(component, index)}
          </div>
        )) || (
          <div className="col-span-full">
            <LoadingSpinner text="Loading dashboard components..." />
          </div>
        )}
      </div>
    </div>
  );
};

export default DynamicDashboard;

