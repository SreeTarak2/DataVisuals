import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, TrendingUp, Activity, Zap, Loader2, FileText, ChevronRight, AlertTriangle, CheckCircle, Lightbulb, Upload, TrendingDown, BarChart3, Sparkles, RefreshCw } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';
import { Button } from '../components/Button';
import DashboardSkeleton from '../components/DashboardSkeleton';
import DashboardComponent from '../components/DashboardComponent';
import InsightsPanel from '../components/InsightsPanel';
import ExecutiveSummary from '../components/ExecutiveSummary';
import IntelligentChartExplanation from '../components/IntelligentChartExplanation';
import UploadModal from '../components/UploadModal';
import { useAuth } from '../contexts/AuthContext';
import useDatasetStore from '../store/datasetStore';
import { toast } from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { normalizeDashboardConfig } from '../utils/dashboardUtils';

const Dashboard = () => {
  const { user } = useAuth();
  const { datasets, selectedDataset, fetchDatasets } = useDatasetStore();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState([]);
  const [kpiData, setKpiData] = useState([]);
  const [chartData, setChartData] = useState({});
  const [datasetInfo, setDatasetInfo] = useState(null);
  const [dataPreview, setDataPreview] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [aiDashboardConfig, setAiDashboardConfig] = useState(null);
  const [layoutLoading, setLayoutLoading] = useState(false);
  const [datasetData, setDatasetData] = useState([]);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [prioritizedColumns, setPrioritizedColumns] = useState([]);

  // Helpers to derive dataset-aware defaults (avoid hardcoded example columns)
  const getDatasetColumns = () => {
    if (datasetData && datasetData.length > 0) return Object.keys(datasetData[0]);
    if (dataPreview && dataPreview.length > 0) return Object.keys(dataPreview[0]);
    return [];
  };

  const firstNumericColumn = () => {
    const cols = getDatasetColumns();
    for (let c of cols) {
      const val = datasetData?.[0]?.[c] ?? dataPreview?.[0]?.[c];
      if (typeof val === 'number') return c;
      if (val != null && val !== '' && !isNaN(parseFloat(val))) return c;
    }
    return cols[0] || 'value';
  };

  const firstCategoricalColumn = () => {
    const cols = getDatasetColumns();
    for (let c of cols) {
      const val = datasetData?.[0]?.[c] ?? dataPreview?.[0]?.[c];
      if (typeof val === 'string') return c;
    }
    return cols[0] || 'category';
  };

  // Sanitize transformed components produced by legacy/AI responses to remove example placeholders
  const sanitizeTransformedComponents = (components) => {
    try {
      const numCol = firstNumericColumn();
      const catCol = firstCategoricalColumn();
      const colsAll = getDatasetColumns();
      const sanitizeValue = (v) => {
        if (v === 'home_wins' || v === 'away_wins') return numCol;
        if (v === 'team') return catCol;
        return v;
      };

      const deepClone = JSON.parse(JSON.stringify(components));
      const walk = (obj) => {
        if (Array.isArray(obj)) {
          for (let i = 0; i < obj.length; i++) {
            if (typeof obj[i] === 'string') obj[i] = sanitizeValue(obj[i]);
            else if (typeof obj[i] === 'object' && obj[i] !== null) walk(obj[i]);
          }
        } else if (typeof obj === 'object' && obj !== null) {
          for (const k of Object.keys(obj)) {
            if (typeof obj[k] === 'string') obj[k] = sanitizeValue(obj[k]);
            else if (Array.isArray(obj[k])) obj[k] = obj[k].map(v => (typeof v === 'string' ? sanitizeValue(v) : v));
            else if (typeof obj[k] === 'object' && obj[k] !== null) walk(obj[k]);
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

  // Icon mapping for insights
  const iconMap = {
    TrendingUp,
    AlertTriangle,
    CheckCircle,
    Lightbulb
  };



  useEffect(() => {
    const loadDashboardData = async () => {
      if (!selectedDataset || !selectedDataset.id) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        // Clear any cached dashboard data to ensure fresh data
        setKpiData([]);
        setInsights([]);
        setChartData({});

        // Always fetch fresh dataset data to get updated row/column counts
        const freshDatasets = await fetchDatasets(true);

        // Check if dataset is still processing and set up polling
        const currentDataset = freshDatasets.find(d => d.id === selectedDataset.id || d._id === selectedDataset.id);
        if (currentDataset && !currentDataset.is_processed && currentDataset.processing_status !== 'failed') {
          // Dataset is still processing, set up polling to refresh every 3 seconds
          const pollInterval = setInterval(async () => {
            try {
              const updatedDatasets = await fetchDatasets(true);
              const updatedDataset = updatedDatasets.find(d => d.id === selectedDataset.id || d._id === selectedDataset.id);
              if (updatedDataset && updatedDataset.is_processed) {
                clearInterval(pollInterval);
                // Reload dashboard data once processing is complete
                loadDashboardData();
              }
    } catch (error) {
              console.error('Error polling for dataset updates:', error);
            }
          }, 3000);

          // Clean up interval on unmount
          return () => clearInterval(pollInterval);
        }

        const token = localStorage.getItem('datasage-token');

        // First, load the actual dataset data for chart rendering
        const dataResponse = await fetch(`/api/datasets/${selectedDataset.id}/data?page=1&page_size=1000`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (dataResponse.ok) {
          const dataResult = await dataResponse.json();
          setDatasetData(dataResult.data || []);
          console.log('Loaded dataset data for charts:', dataResult.data?.length || 0, 'rows');
        } else {
          console.error('Failed to load dataset data:', dataResponse.status);
          setDatasetData([]);
        }

        // Load dashboard data sequentially to avoid overwhelming Ollama
        // First load overview (no AI calls)
        const overviewRes = await fetch(`/api/dashboard/${selectedDataset.id}/overview`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        // Then load charts (no AI calls)
        const chartsRes = await fetch(`/api/dashboard/${selectedDataset.id}/charts`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        // Add delay before heavy AI calls to prevent overwhelming the backend
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Finally load insights (this calls Ollama - do it last)
        const insightsRes = await fetch(`/api/dashboard/${selectedDataset.id}/insights`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        // Process overview data - prioritize API data over fallbacks
        if (overviewRes.ok) {
          const overviewData = await overviewRes.json();
          console.log('Dashboard overview data:', overviewData);
          setKpiData(overviewData.kpis || []);
          setDatasetInfo(overviewData.dataset || {
            name: selectedDataset.name,
            row_count: selectedDataset.row_count || 0,
            column_count: selectedDataset.column_count || 0
          });
        } else {
          console.error('Failed to load overview data:', overviewRes.status);
          setKpiData([]);
          setDatasetInfo({
            name: selectedDataset.name,
            row_count: selectedDataset.row_count || 0,
            column_count: selectedDataset.column_count || 0
          });
        }

        // Process charts data - prioritize API data
        if (chartsRes.ok) {
          const chartsData = await chartsRes.json();
          console.log('Dashboard charts data:', chartsData);
          setChartData(chartsData.charts || {});
        } else {
          console.error('Failed to load charts data:', chartsRes.status);
          setChartData({});
        }

        // Process insights data - prioritize API data (this calls Ollama)
        if (insightsRes.ok) {
          const insightsData = await insightsRes.json();
          console.log('Dashboard insights data:', insightsData);
          // Filter out any hardcoded insights
          const realInsights = (insightsData.insights || []).filter(insight => 
            !insight.title?.toLowerCase().includes('pearson correlation') &&
            !insight.title?.toLowerCase().includes('strong correlation') &&
            insight.title && insight.description
          );
          setInsights(realInsights);
        } else {
          console.error('Failed to load insights data:', insightsRes.status);
          setInsights([]);
        }

        // Load data preview for table display
        if (token) {
          loadDataPreview(selectedDataset.id, token);
        }

      } catch (err) {
        console.error('Dashboard load failed:', err);
        // Clear all data on failure
        setKpiData([]);
        setChartData({});
        setInsights([]);
        setDatasetInfo({
          name: selectedDataset.name,
          row_count: selectedDataset.row_count || 0,
          column_count: selectedDataset.column_count || 0
        });
        toast.error('Failed to load dashboard data');
    } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [selectedDataset, fetchDatasets]);

  // Generate AI-designed dashboard using the new AI Designer service
  const generateAiDashboard = useCallback(async (forceRegenerate = false) => {
    if (!selectedDataset || !selectedDataset.id) {
      console.log('No dataset selected, skipping AI dashboard generation');
      setAiDashboardConfig(null);
      return;
    }

    if (!selectedDataset.is_processed) {
      console.log('Dataset not processed yet, skipping AI dashboard generation');
      setAiDashboardConfig(null);
      return;
    }

    try {
      setLayoutLoading(true);
      const token = localStorage.getItem('datasage-token');
      console.log('Starting AI dashboard generation for dataset:', selectedDataset.id);

      // First, get the dataset data for the AI to work with
      const dataResponse = await fetch(`/api/datasets/${selectedDataset.id}/data?page=1&page_size=1000`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (dataResponse.ok) {
        const dataResult = await dataResponse.json();
        setDatasetData(dataResult.data || []);
        console.log('Loaded dataset data:', dataResult.data?.length || 0, 'rows');
      } else {
        console.error('Failed to load dataset data:', dataResponse.status);
      }

      // Also load data preview for the table display
      loadDataPreview(selectedDataset.id, token);

      // Add delay before AI dashboard generation to prevent overwhelming backend
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Try the new AI Designer service first
      try {
        console.log('Trying AI Designer service...');
        const response = await fetch(`/api/ai/${selectedDataset.id}/design-dashboard`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            force_regenerate: !!forceRegenerate
          })
        });

        if (response.ok) {
          const dashboardConfig = await response.json();
          console.log('AI Designer response:', dashboardConfig);
          if (dashboardConfig.dashboard_blueprint && dashboardConfig.dashboard_blueprint.components) {
            const normalized = normalizeDashboardConfig({
              components: dashboardConfig.dashboard_blueprint.components || [],
              layout_grid: dashboardConfig.dashboard_blueprint.layout_grid || "repeat(4, 1fr)",
              design_pattern: dashboardConfig.design_pattern,
              pattern_name: dashboardConfig.pattern_name,
              reasoning: dashboardConfig.reasoning
            });
            setAiDashboardConfig(normalized);
            toast.success(`AI dashboard generated using ${dashboardConfig.pattern_name || 'AI Designer'} pattern!`);
            return;
          } else if (dashboardConfig.dashboard && dashboardConfig.dashboard.components) {
            // Handle direct dashboard response from AI Designer
            const transformedComponents = [];
            dashboardConfig.dashboard.components.forEach((component, index) => {
              // Handle KPI cards
              if (component.kpi_cards) {
                component.kpi_cards.forEach((kpi, kpiIndex) => {
                  transformedComponents.push({
                    type: 'kpi',
                    title: kpi.title || `KPI ${kpiIndex + 1}`,
                    span: 1,
                    config: {
                      column: kpi.sum || kpi.mean || kpi.count || firstNumericColumn(),
                      aggregation: kpi.sum ? 'sum' : kpi.mean ? 'mean' : 'count',
                      color: kpiIndex % 4 === 0 ? 'emerald' : kpiIndex % 4 === 1 ? 'blue' : kpiIndex % 4 === 2 ? 'teal' : 'purple'
                    }
                  });
                });
              }
              
              // Handle charts
              if (component.charts) {
                component.charts.forEach((chart, chartIndex) => {
                  transformedComponents.push({
                    type: 'chart',
                    title: chart.chart_type ? `${chart.chart_type.replace('_', ' ').toUpperCase()} Chart` : `Chart ${chartIndex + 1}`,
                    span: 2,
                    config: {
                      chart_type: chart.chart_type || chart.type || 'bar_chart',
                      columns: chart.data ? chart.data.map(d => d.x || d.y).filter(Boolean) : [firstNumericColumn(), firstCategoricalColumn()],
                      aggregation: 'mean',
                      group_by: chart.data?.[0]?.x || firstCategoricalColumn()
                    }
                  });
                });
              }
              
              // Handle table
              if (component.table) {
                transformedComponents.push({
                  type: 'table',
                  title: 'Data Table',
                  span: 4,
                  config: {
                    columns: component.table.columns || getDatasetColumns()
                  }
                });
              }
            });
            
              if (transformedComponents.length > 0) {
              const sanitized = sanitizeTransformedComponents(transformedComponents);
              const normalized = normalizeDashboardConfig({ components: sanitized, layout_grid: dashboardConfig.dashboard.layout_grid || "repeat(4, 1fr)" });
              setAiDashboardConfig(normalized);
              toast.success('AI dashboard generated successfully!');
              return;
            }
          }
        } else {
          console.error('AI Designer service failed:', response.status);
        }
      } catch (designError) {
        console.log('AI Designer service failed, falling back to legacy service:', designError);
      }

      // Fallback to legacy AI dashboard generation
      console.log('Trying legacy AI dashboard generation...');
      const response = await fetch(`/api/ai/${selectedDataset.id}/generate-dashboard?force_regenerate=${forceRegenerate}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const dashboardConfig = await response.json();
        console.log('Legacy dashboard response:', dashboardConfig);

        // Transform the backend response to match frontend expectations
        if (dashboardConfig.dashboard && dashboardConfig.dashboard.components) {
          const transformedComponents = [];
          
          // Process each component in the response
          dashboardConfig.dashboard.components.forEach((component, index) => {
            // Handle KPI cards
            if (component.kpi_cards) {
              component.kpi_cards.forEach((kpi, kpiIndex) => {
                transformedComponents.push({
                  type: 'kpi',
                  title: kpi.title || `KPI ${kpiIndex + 1}`,
                  span: 1,
                  config: {
                    column: kpi.sum || kpi.mean || kpi.count || 'home_wins',
                    aggregation: kpi.sum ? 'sum' : kpi.mean ? 'mean' : 'count',
                    color: kpiIndex % 4 === 0 ? 'emerald' : kpiIndex % 4 === 1 ? 'blue' : kpiIndex % 4 === 2 ? 'teal' : 'purple'
                  }
                });
              });
            }
            
            // Handle charts
            if (component.charts) {
              component.charts.forEach((chart, chartIndex) => {
                transformedComponents.push({
                  type: 'chart',
                  title: chart.chart_type ? `${chart.chart_type.replace('_', ' ').toUpperCase()} Chart` : `Chart ${chartIndex + 1}`,
                  span: 2,
                  config: {
                    chart_type: chart.chart_type || chart.type || 'bar_chart',
                    columns: chart.data ? chart.data.map(d => d.x || d.y).filter(Boolean) : ['home_wins', 'away_wins'],
                    aggregation: 'mean',
                    group_by: chart.data?.[0]?.x || 'home_wins'
                  }
                });
              });
            }
            
            // Handle table
            if (component.table) {
              transformedComponents.push({
                type: 'table',
                title: 'Data Table',
                span: 4,
                config: {
                  columns: component.table.columns || ['team', 'home_wins', 'away_wins']
                }
              });
            }
            
            // Handle legacy format
            if (component.kpi && component.chart_type) {
              transformedComponents.push({
                type: 'kpi',
                title: component.kpi,
              span: 1,
                config: {
                  column: component.data_columns?.[0] || firstNumericColumn(),
                  aggregation: component.kpi.includes('Total') ? 'count' : 'mean',
                  color: index % 4 === 0 ? 'emerald' : index % 4 === 1 ? 'blue' : index % 4 === 2 ? 'teal' : 'purple'
                }
              });
            } else if (component.chart_type && component.title && !component.kpi) {
              transformedComponents.push({
                type: 'chart',
                title: component.title,
              span: 2,
                config: {
                  chart_type: component.chart_type,
                  columns: component.data_columns || [firstNumericColumn(), firstCategoricalColumn()],
                  aggregation: 'mean',
                  group_by: component.data_columns?.[0] || firstCategoricalColumn()
                }
              });
            }
          });

          console.log('Transformed components:', transformedComponents);
          
          if (transformedComponents.length > 0) {
          const sanitized = sanitizeTransformedComponents(transformedComponents);
          const normalized = normalizeDashboardConfig({ components: sanitized, layout_grid: dashboardConfig.dashboard.layout_grid || "repeat(4, 1fr)" });
          setAiDashboardConfig(normalized);
        } else {
            console.log('No valid components found after transformation');
            setAiDashboardConfig(null);
          }
        } else if (dashboardConfig.components) {
          const transformedComponents = [];
          
          // Process each component in the response
          dashboardConfig.components.forEach((component, index) => {
            // Handle KPI cards
            if (component.kpi_cards) {
              component.kpi_cards.forEach((kpi, kpiIndex) => {
                transformedComponents.push({
              type: 'kpi',
                  title: kpi.title || `KPI ${kpiIndex + 1}`,
              span: 1,
                  config: {
                    column: kpi.sum || kpi.mean || kpi.count || firstNumericColumn(),
                    aggregation: kpi.sum ? 'sum' : kpi.mean ? 'mean' : 'count',
                    color: kpiIndex % 4 === 0 ? 'emerald' : kpiIndex % 4 === 1 ? 'blue' : kpiIndex % 4 === 2 ? 'teal' : 'purple'
                  }
                });
              });
            }
            
            // Handle charts
            if (component.charts) {
              component.charts.forEach((chart, chartIndex) => {
                transformedComponents.push({
                  type: 'chart',
                  title: chart.chart_type ? `${chart.chart_type.replace('_', ' ').toUpperCase()} Chart` : `Chart ${chartIndex + 1}`,
                  span: 2,
                  config: {
                    chart_type: chart.chart_type || chart.type || 'bar_chart',
                    columns: chart.data ? chart.data.map(d => d.x || d.y).filter(Boolean) : [firstNumericColumn(), firstCategoricalColumn()],
                    aggregation: 'mean',
                    group_by: chart.data?.[0]?.x || firstCategoricalColumn()
                  }
                });
              });
            }
            
            // Handle table
            if (component.table) {
                transformedComponents.push({
                  type: 'table',
                  title: 'Data Table',
                  span: 4,
                  config: {
                    columns: component.table.columns || getDatasetColumns()
                  }
                });
            }
            
            // Handle legacy format
            if (component.kpi && component.chart_type) {
              transformedComponents.push({
              type: 'kpi',
                title: component.kpi,
              span: 1,
                config: {
                  column: component.data_columns?.[0] || 'home_wins',
                  aggregation: component.kpi.includes('Total') ? 'count' : 'mean',
                  color: index % 4 === 0 ? 'emerald' : index % 4 === 1 ? 'blue' : index % 4 === 2 ? 'teal' : 'purple'
                }
              });
            } else if (component.chart_type && component.title && !component.kpi) {
              transformedComponents.push({
              type: 'chart',
                title: component.title,
              span: 2,
                config: {
                  chart_type: component.chart_type,
                  columns: component.data_columns || ['home_wins', 'away_wins'],
                  aggregation: 'mean',
                  group_by: component.data_columns?.[0] || 'home_wins'
                }
              });
            }
          });

          console.log('Transformed components:', transformedComponents);
          
          if (transformedComponents.length > 0) {
          const sanitized = sanitizeTransformedComponents(transformedComponents);
          const normalized = normalizeDashboardConfig({ components: sanitized, layout_grid: dashboardConfig.layout_grid || "repeat(4, 1fr)" });
          setAiDashboardConfig(normalized);
        toast.success('AI dashboard generated successfully!');
      } else {
            console.log('No valid components found after transformation');
            setAiDashboardConfig(null);
          }
        } else {
          console.log('No dashboard components found in response');
          setAiDashboardConfig(null);
        }
      } else {
        console.error('Legacy AI dashboard generation failed:', response.status);
        setAiDashboardConfig(null);
        throw new Error('Failed to generate AI dashboard');
      }
    } catch (error) {
      console.error('AI Dashboard generation failed:', error);
      setAiDashboardConfig(null);
      toast.error('Failed to generate AI dashboard');
    } finally {
      setLayoutLoading(false);
    }
  }, [selectedDataset]);
  const handleRegenerate = useCallback(() => {
    generateAiDashboard(true);
  }, [generateAiDashboard]);


  // Load insights and prioritized columns
  const loadInsights = useCallback(async () => {
    if (!selectedDataset || !selectedDataset.id) return;

    try {
      const token = localStorage.getItem('datasage-token');

      // Load insights
      const insightsResponse = await fetch(`/api/dashboard/${selectedDataset.id}/insights`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (insightsResponse.ok) {
        const insightsData = await insightsResponse.json();
        setInsights(insightsData.insights || []);
      }

      // Load prioritized columns from QUIS analysis
      const quisResponse = await fetch(`/api/analysis/run-quis`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          dataset_id: selectedDataset.id,
          max_depth: 2
        })
      });

      if (quisResponse.ok) {
        const quisData = await quisResponse.json();
        // Handle QUIS response format: prioritized insights with explanation, significance, type
        setPrioritizedColumns(quisData.prioritized_insights || quisData.prioritized_columns || []);
      }

    } catch (error) {
      console.error('Failed to load insights:', error);
      setInsights([]);
      setPrioritizedColumns([]);
    }
  }, [selectedDataset]);

  // Generate AI dashboard when dataset changes
  useEffect(() => {
    generateAiDashboard();
    loadInsights();
  }, [generateAiDashboard, loadInsights]);

  // Load data preview
  const loadDataPreview = async (datasetId, token) => {
    if (!datasetId) {
      console.warn('loadDataPreview: No dataset ID provided');
      return;
    }

    try {
      setPreviewLoading(true);
      console.log('Loading data preview for dataset:', datasetId);

      const response = await fetch(`/api/datasets/${datasetId}/preview?limit=10`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      console.log('Data preview response status:', response.status);

      if (response.ok) {
        const data = await response.json();
        console.log('Data preview response:', data);
        setDataPreview(data.rows || []);
      } else {
        console.warn('Could not load data preview, response status:', response.status);
        const errorText = await response.text();
        console.warn('Error response:', errorText);

        // Fallback to regular data endpoint
        console.log('Trying fallback to regular data endpoint...');
        try {
          const fallbackResponse = await fetch(`/api/datasets/${datasetId}/data?page=1&page_size=10`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });

          if (fallbackResponse.ok) {
            const fallbackData = await fallbackResponse.json();
            console.log('Fallback data response:', fallbackData);
            setDataPreview(fallbackData.data || []);
          } else {
            console.warn('Fallback also failed, status:', fallbackResponse.status);
            setDataPreview([]);
          }
        } catch (fallbackErr) {
          console.warn('Fallback error:', fallbackErr);
          setDataPreview([]);
        }
      }
    } catch (err) {
      console.warn('Data preview loading error:', err);
      setDataPreview([]);
    } finally {
      setPreviewLoading(false);
    }
  };

  // Enhanced chart data processing
  const processChartData = (data) => {
    if (!data || data.length === 0) return [];
    return data;
  };

  // Hydrate AI-generated KPI components with real values from datasetData
  const hydrateKpiComponent = (component) => {
    try {
      if (!component || component.type !== 'kpi') return component;
      const config = component.config || {};
      // Try common places for the column and aggregation info
      const column = config.column || (config.columns && config.columns[0]) || component.x_axis || component.y_axis || null;
      const aggregation = (config.aggregation || component.aggregation || 'sum').toString().toLowerCase();
      let value = component.value ?? 'N/A';

      if (column && Array.isArray(datasetData) && datasetData.length > 0) {
        // Collect candidate values for the column
        const raw = datasetData.map(r => r[column]).filter(v => v !== null && v !== undefined && v !== '');
        if (aggregation === 'count') {
          value = raw.length;
        } else if (aggregation === 'nunique') {
          value = new Set(raw).size;
        } else {
          // numeric aggregations
          const numeric = raw.map(v => Number(v)).filter(n => !Number.isNaN(n));
          if (numeric.length === 0) {
            value = 0;
          } else if (aggregation === 'sum') {
            value = numeric.reduce((a, b) => a + b, 0);
          } else if (aggregation === 'mean' || aggregation === 'avg') {
            value = numeric.reduce((a, b) => a + b, 0) / numeric.length;
          } else if (aggregation === 'max') {
            value = Math.max(...numeric);
          } else if (aggregation === 'min') {
            value = Math.min(...numeric);
          } else {
            // fallback to sum
            value = numeric.reduce((a, b) => a + b, 0);
          }
        }

        // Format numbers nicely
        if (typeof value === 'number') {
          value = new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
          }).format(value);
        }
      }

      return { ...component, value };
    } catch (e) {
      console.warn('hydrateKpiComponent failed', e);
      return component;
    }
  };

  // Refresh dashboard data
  const refreshDashboard = async () => {
    if (!selectedDataset) return;

    setLoading(true);
    try {
      const token = localStorage.getItem('datasage-token');

      // Load data sequentially to avoid overwhelming Ollama
      const overviewRes = await fetch(`/api/dashboard/${selectedDataset.id}/overview`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const chartsRes = await fetch(`/api/dashboard/${selectedDataset.id}/charts`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const insightsRes = await fetch(`/api/dashboard/${selectedDataset.id}/insights`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      // Update data with fresh API calls only
      if (overviewRes.ok) {
        const overviewData = await overviewRes.json();
        console.log('Refreshed overview data:', overviewData);
        setKpiData(overviewData.kpis || []);
        setDatasetInfo(overviewData.dataset || {
          name: selectedDataset.name,
          row_count: selectedDataset.row_count || 0,
          column_count: selectedDataset.column_count || 0
        });
      } else {
        console.error('Failed to refresh overview data');
        setKpiData([]);
      }

      if (chartsRes.ok) {
        const chartsData = await chartsRes.json();
        console.log('Refreshed charts data:', chartsData);
        setChartData(chartsData.charts || {});
      } else {
        console.error('Failed to refresh charts data');
        setChartData({});
      }

      if (insightsRes.ok) {
        const insightsData = await insightsRes.json();
        console.log('Refreshed insights data:', insightsData);
        setInsights(insightsData.insights || []);
      } else {
        console.error('Failed to refresh insights data');
        setInsights([]);
      }

      toast.success('Dashboard refreshed successfully');
    } catch (err) {
      console.error('Refresh failed:', err);
      toast.error('Failed to refresh dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-950 p-6 flex items-center justify-center">
        <div className="text-center">
        <Loader2 className="w-12 h-12 animate-spin text-blue-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-white mb-2">Loading Dashboard</h3>
        <p className="text-slate-400">AI is analyzing your data and generating insights...</p>
        </div>
      </div>
    );

  if (!selectedDataset) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Database className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
          <h2 className="text-2xl font-bold text-foreground mb-2">No Dataset Selected</h2>
          <p className="text-muted-foreground">Please select a dataset to view the dashboard</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6 space-y-8">
      {/* Enhanced Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col lg:flex-row gap-6 items-start lg:items-center justify-between"
      >
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-white tracking-tight flex items-center gap-3">
            <Sparkles className="w-10 h-10 text-emerald-400" />
            DataSage AI
          </h1>
          <p className="text-slate-400 text-lg">
            {selectedDataset?.name ? (
              <>
                Intelligent analysis of: <span className="text-slate-200 font-medium">{selectedDataset.name}</span>
                <span className="ml-4 text-sm bg-slate-800/50 px-3 py-1 rounded-full border border-slate-700">
                  {selectedDataset.row_count || 0} rows • {selectedDataset.column_count || 0} columns
                </span>
                {selectedDataset.metadata?.data_quality?.data_cleaning_applied && (
                  <span className="ml-2 text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full border border-green-500/30">
                    ✨ Data Cleaned
                  </span>
                )}
              </>
            ) : (
              <span className="text-slate-300 font-medium">No data has been uploaded yet</span>
            )}
          </p>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
          <div className="text-right sm:text-left">
            <p className="text-sm text-slate-500">Last updated</p>
            <p className="text-slate-200 font-medium">
              {new Date().toLocaleTimeString()}
            </p>
          </div>

          <div className="flex items-center gap-3">

            <Button
              onClick={handleRegenerate}
              disabled={layoutLoading || !selectedDataset?.is_processed}
              className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-600 transition-all duration-200 shadow-lg"
              title="Ask AI to redesign this dashboard with fresh analysis"
            >
              {layoutLoading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              {layoutLoading ? 'Redesigning...' : 'Redesign'}
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Main Dashboard Content */}
      {!selectedDataset ? (
        /* No Dataset State */
        <div className="text-center py-20 bg-slate-800/50 border border-slate-700 rounded-xl">
          <Database className="w-16 h-16 mx-auto text-slate-500 mb-6" />
          <h3 className="text-2xl font-semibold text-white mb-3">No Data Has Been Uploaded</h3>
          <p className="text-slate-400 mb-8 max-w-md mx-auto">
            Upload your first dataset to begin your AI-powered data exploration journey.
            Our intelligent system will automatically analyze and create beautiful visualizations for you.
          </p>
          <Button
            onClick={() => setShowUploadModal(true)}
            className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-3 text-lg"
          >
            <Upload className="w-5 h-5 mr-2" />
            Upload Your First Dataset
          </Button>
              </div>
      ) : !selectedDataset.is_processed ? (
        /* Processing State */
        <div className="text-center py-20 bg-slate-800/50 border border-slate-700 rounded-xl">
          <Loader2 className="w-16 h-16 mx-auto animate-spin text-emerald-400 mb-6" />
          <h3 className="text-2xl font-semibold text-white mb-3">AI is Analyzing Your Dataset</h3>
          <p className="text-slate-400 mb-4">
            Our intelligent system is processing your data and designing your personalized dashboard.
          </p>
          <p className="text-sm text-slate-500">
            This will appear automatically when ready - no action needed from you!
          </p>
            </div>
      ) : layoutLoading ? (
        /* Loading State */
        <DashboardSkeleton />
      ) : aiDashboardConfig && aiDashboardConfig.components && aiDashboardConfig.components.length > 0 ? (
        /* AI Dashboard State */
        <div className="space-y-6">
          {console.log('Rendering AI Dashboard with components:', aiDashboardConfig.components)}
          {/* Separate KPI Cards Section */}
          <motion.div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
            variants={{
              hidden: {},
              visible: {
                transition: { staggerChildren: 0.1 }
              }
            }}
            initial="hidden"
            animate="visible"
          >
            {aiDashboardConfig.components
              .filter(component => component.type === 'kpi')
              .map((component, index) => {
                const hydrated = hydrateKpiComponent(component);
                return (
                  <motion.div
                    key={`kpi-${index}`}
                    variants={{
                      hidden: { y: 20, opacity: 0 },
                      visible: { y: 0, opacity: 1 }
                    }}
                  >
                    <DashboardComponent
                      component={hydrated}
                      datasetData={datasetData}
                    />
                  </motion.div>
                );
              })}
          </motion.div>

          {/* Charts and Tables Section */}
          <motion.div
            className="space-y-6"
            variants={{
              hidden: {},
              visible: {
                transition: { staggerChildren: 0.1 }
              }
            }}
            initial="hidden"
            animate="visible"
          >
            {(() => {
              // Deduplicate chart components by title + type + columns
              const rawChartComponents = aiDashboardConfig.components.filter(component => component.type !== 'kpi' && component.type !== 'table');
              const seen = new Set();
              const chartComponents = rawChartComponents.filter(c => {
                const cols = JSON.stringify(c.config?.columns || c.config?.data_columns || []);
                const key = `${c.title}::${c.config?.chart_type || ''}::${cols}`;
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
              });

              if (chartComponents.length === 0) return null;

              // Choose the hero chart as the one with the largest span (fallback to first)
              let mainChart = chartComponents.reduce((best, c) => {
                if (!best) return c;
                return (c.span || 1) > (best.span || 1) ? c : best;
              }, null);

              // Ensure we only render the mainChart once
              const otherCharts = chartComponents.filter(c => c !== mainChart);

              return (
                <>
                  {/* Main Chart - Large with Explanation */}
                  {mainChart && (
                    <motion.div
                      key="main-chart"
                      className="space-y-6"
                      variants={{
                        hidden: { y: 20, opacity: 0 },
                        visible: { y: 0, opacity: 1 }
                      }}
                    >
                      <DashboardComponent
                        component={mainChart}
                        datasetData={datasetData}
                      />
                      <IntelligentChartExplanation
                        component={mainChart}
                        datasetData={datasetData}
                        datasetInfo={datasetInfo}
                      />
                    </motion.div>
                  )}

                  {/* Secondary Charts - Smaller Grid with Insights */}
                  {otherCharts.length > 0 && (
                    <motion.div
                      className="space-y-6"
                      variants={{
                        hidden: {},
                        visible: {
                          transition: { staggerChildren: 0.1 }
                        }
                      }}
                    >
                      {otherCharts.map((component, index) => (
                        <motion.div
                          key={`secondary-${index}`}
                          className={`grid grid-cols-1 lg:grid-cols-2 gap-6 ${
                            index % 2 === 0 ? 'lg:grid-flow-col' : 'lg:grid-flow-col-dense'
                          }`}
                          variants={{
                            hidden: { y: 20, opacity: 0 },
                            visible: { y: 0, opacity: 1 }
                          }}
                        >
                          {/* Chart Component */}
                          <div className={index % 2 === 0 ? 'lg:order-1' : 'lg:order-2'}>
                            <DashboardComponent
                              component={component}
                              datasetData={datasetData}
                            />
                          </div>
                          
                          {/* Intelligent Chart Explanation */}
                          <div className={index % 2 === 0 ? 'lg:order-2' : 'lg:order-1'}>
                            <IntelligentChartExplanation
                              component={component}
                              datasetData={datasetData}
                              datasetInfo={datasetInfo}
                            />
                          </div>
                        </motion.div>
                      ))}
                    </motion.div>
                  )}

                </>
              );
            })()}
          </motion.div>

          {/* Insights Panel */}
          <InsightsPanel
            insights={insights}
            prioritizedColumns={prioritizedColumns}
            datasetInfo={datasetInfo}
          />

          {/* Executive Summary */}
          <ExecutiveSummary
            datasetId={selectedDataset?.id}
            insights={insights}
            prioritizedColumns={prioritizedColumns}
          />

          {/* Data Preview Section - Always show after AI dashboard */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="group"
          >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                  <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center">
                    <BarChart3 className="w-5 h-5 text-green-400" />
                  </div>
                  Data Preview
                </h2>
                <div className="flex items-center gap-4 text-sm text-slate-400">
                  <span>Showing first 10 rows</span>
                  <span>•</span>
                  <span>{selectedDataset?.row_count?.toLocaleString() || 0} total rows</span>
                </div>
              </div>
              <div className="overflow-x-auto">
                <div className="min-w-full">
                  {previewLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                      <span className="ml-3 text-slate-400">Loading data preview...</span>
                    </div>
                  ) : dataPreview.length > 0 ? (
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-700">
                          {Object.keys(dataPreview[0] || {}).slice(0, 8).map((column, index) => (
                            <th key={index} className="text-left py-3 px-4 text-sm font-medium text-slate-300">
                              {column}
                            </th>
                          ))}
                          {Object.keys(dataPreview[0] || {}).length > 8 && (
                            <th className="text-left py-3 px-4 text-sm font-medium text-slate-300">
                              ...
                            </th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {dataPreview.slice(0, 10).map((row, rowIndex) => (
                          <tr key={rowIndex} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                            {Object.entries(row).slice(0, 8).map(([key, value], colIndex) => (
                              <td key={colIndex} className="py-3 px-4 text-sm text-slate-400">
                                <div className="w-24 truncate" title={String(value)}>
                                  {String(value).length > 20 ? `${String(value).substring(0, 20)}...` : String(value)}
                                </div>
                              </td>
                            ))}
                            {Object.keys(row).length > 8 && (
                              <td className="py-3 px-4 text-sm text-slate-500">
                                ...
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="text-center py-12 text-slate-400">
                      <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center mx-auto mb-4">
                        <BarChart3 className="w-6 h-6 opacity-50" />
                      </div>
                      <p className="text-sm">No data preview available</p>
                      <p className="text-xs mt-1">Check browser console for debugging info</p>
              <button
                        onClick={() => {
                          const token = localStorage.getItem('datasage-token');
                          if (selectedDataset && token) {
                            loadDataPreview(selectedDataset.id, token);
                          }
                        }}
                        className="mt-2 px-3 py-1 text-xs bg-slate-800 hover:bg-slate-700 rounded border border-slate-600"
                      >
                        Retry Loading
              </button>
            </div>
                  )}
          </div>
        </div>

              <div className="mt-6 flex items-center justify-between">
                <div className="text-sm text-slate-400">
                  <span className="font-medium text-white">
                    {dataPreview.length > 0 ? Object.keys(dataPreview[0]).length : selectedDataset?.column_count || 0}
                  </span> columns •
                  <span className="font-medium text-white ml-1">{selectedDataset?.row_count?.toLocaleString() || 0}</span> rows
      </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="bg-slate-800/50 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white"
                  >
                    View Full Dataset
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="bg-slate-800/50 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white"
                  >
                    Export Data
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>

        </div>
      ) : (
        /* Fallback to original dashboard layout */
        <div className="space-y-6">
          {/* Enhanced KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <AnimatePresence>
              {kpiData.map((kpi, i) => (
          <motion.div
                  key={kpi.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="group"
                >
                  <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 w-full h-full">
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">
                      {kpi.title}
                  </div>
                      <div className={`w-2 h-2 rounded-full ${kpi.color === 'green' ? 'bg-emerald-500' :
                          kpi.color === 'red' ? 'bg-red-500' :
                            kpi.color === 'blue' ? 'bg-blue-500' : 'bg-slate-500'
                        }`}></div>
                    </div>
                    <div className="space-y-2">
                      <div className="text-3xl font-bold text-white">
                    {kpi.value}
                  </div>
                      <div className={`flex items-center text-sm ${kpi.change && kpi.change.includes('+') ? 'text-emerald-400' : 'text-red-400'
                        }`}>
                        {kpi.change && (
                          <>
                            {kpi.change.includes('+') ? (
                              <TrendingUp className="w-4 h-4 mr-1" />
                            ) : (
                              <TrendingDown className="w-4 h-4 mr-1" />
                            )}
                            {kpi.change}
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          {/* Charts will be dynamically generated by AI */}
          <div className="space-y-6">
            <div className="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-xl">
              <BarChart3 className="w-12 h-12 mx-auto text-slate-500 mb-4" />
              <h3 className="text-xl font-semibold text-white mb-2">No Charts Available</h3>
              <p className="text-slate-400">Charts will appear here once you upload and process your data</p>
                    </div>

                      </div>


          {/* AI Insights Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="group"
          >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
              <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
                  <Zap className="w-5 h-5 text-blue-400" />
                </div>
                AI Insights
            </h2>
              <div className="space-y-4">
                {insights.length > 0 ? (
                  insights.map((insight, i) => {
                    const IconComponent = iconMap[insight.icon] || Zap;
                    return (
                <motion.div
                        key={insight.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.1 }}
                        className="flex items-start gap-4 p-4 rounded-2xl border border-slate-800 bg-slate-800/30 hover:bg-slate-800/50 hover:border-slate-700 transition-all duration-200"
                      >
                        <div className="flex-shrink-0 mt-1">
                          <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
                            <IconComponent className="w-4 h-4 text-blue-400" />
                          </div>
                    </div>
                    <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <p className="text-sm text-white font-medium">{insight.title}</p>
                            <span className="text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                              {insight.confidence}%
                          </span>
                        </div>
                          <p className="text-xs text-slate-400 leading-relaxed">{insight.description}</p>
                    </div>
                        <button className="ml-auto p-1 text-slate-400 hover:text-white transition-colors relative top-2">
                          <ChevronRight className="w-6 h-6" />
                        </button>
                </motion.div>
                    );
                  })
                ) : (
                  <div className="text-center py-8 text-slate-400">
                    <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center mx-auto mb-4">
                      <Zap className="w-6 h-6 opacity-50" />
            </div>
                    <p className="text-sm">No insights available. Upload a dataset to get started.</p>
                  </div>
        )}
              </div>
            </div>
          </motion.div>

          {/* Insights Panel */}
          <InsightsPanel
            insights={insights}
            prioritizedColumns={prioritizedColumns}
            datasetInfo={datasetInfo}
          />

          {/* Executive Summary */}
          <ExecutiveSummary
            datasetId={selectedDataset?.id}
            insights={insights}
            prioritizedColumns={prioritizedColumns}
          />

        {/* Data Preview Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="group"
          >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                  <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center">
                    <BarChart3 className="w-5 h-5 text-green-400" />
                  </div>
              Data Preview
            </h2>
                <div className="flex items-center gap-4 text-sm text-slate-400">
                  <span>No data available</span>
                </div>
              </div>

                    <div className="text-center py-12 text-slate-400">
                      <div className="w-12 h-12 bg-slate-800 rounded-lg flex items-center justify-center mx-auto mb-4">
                        <BarChart3 className="w-6 h-6 opacity-50" />
              </div>
                      <p className="text-sm">No data preview available</p>
                <p className="text-xs mt-1">Upload a dataset to see your data here</p>
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {/* Upload Modal */}
      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
      />
    </div>
  );
};

export default Dashboard;