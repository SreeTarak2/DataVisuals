import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, TrendingUp, Activity, Zap, Loader2, FileText, ChevronRight, AlertTriangle, CheckCircle, Lightbulb, Upload, TrendingDown, BarChart3, Sparkles, RefreshCw } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';
import { Button } from '../components/Button';
import GlassCard from '../components/common/GlassCard';
import KpiCard from '../components/ui/KpiCard'; // Your KPI component with minis
import DashboardSkeleton from '../components/DashboardSkeleton';
import DashboardComponent from '../components/DashboardComponent';
import UploadModal from '../components/UploadModal';
import { useAuth } from '../contexts/AuthContext';
import useDatasetStore from '../store/datasetStore';
import { toast } from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';

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

  // Icon mapping for insights
  const iconMap = {
    TrendingUp,
    AlertTriangle,
    CheckCircle,
    Lightbulb
  };

  // Generate fallback data for when APIs fail
  const generateFallbackData = () => {
    const fallbackKpis = [
      {
        title: 'TOTAL PRICE PER UNIT',
        value: '$418,759.00',
        change: '+12.5%',
        color: 'green'
      },
      {
        title: 'AVERAGE PRICE PER UNIT',
        value: '$44.74',
        change: '+8.2%',
        color: 'blue'
      },
      {
        title: 'TOTAL RECORDS',
        value: '9,360',
        change: '+156',
        color: 'green'
      },
      {
        title: 'DATA COLUMNS',
        value: '9',
        change: '0',
        color: 'blue'
      }
    ];

    const fallbackCharts = {
      revenue_over_time: [
        { month: 'Jan 2024', revenue: 45000 },
        { month: 'Feb 2024', revenue: 42000 },
        { month: 'Mar 2024', revenue: 48000 },
        { month: 'Apr 2024', revenue: 52000 },
        { month: 'May 2024', revenue: 49000 },
        { month: 'Jun 2024', revenue: 55000 },
        { month: 'Jul 2024', revenue: 58000 },
        { month: 'Aug 2024', revenue: 62000 },
        { month: 'Sep 2024', revenue: 59000 },
        { month: 'Oct 2024', revenue: 65000 },
        { month: 'Nov 2024', revenue: 68000 },
        { month: 'Dec 2024', revenue: 72000 }
      ],
      sales_by_category: [
        { name: 'Electronics', value: 25000 },
        { name: 'Clothing', value: 18000 },
        { name: 'Books', value: 12000 },
        { name: 'Home', value: 15000 },
        { name: 'Sports', value: 10000 }
      ],
      monthly_active_users: [
        { month: 'Week 1', users: 1200 },
        { month: 'Week 2', users: 1350 },
        { month: 'Week 3', users: 1420 },
        { month: 'Week 4', users: 1580 },
        { month: 'Week 5', users: 1650 },
        { month: 'Week 6', users: 1720 }
      ],
      traffic_source: [
        { name: 'Organic', value: 45 },
        { name: 'Direct', value: 25 },
        { name: 'Social', value: 15 },
        { name: 'Email', value: 10 },
        { name: 'Paid', value: 5 }
      ]
    };

    const fallbackInsights = [
      {
        id: 1,
        title: 'Revenue Growth Trend',
        description: 'Strong upward trend in revenue over the past 12 months with consistent growth patterns.',
        confidence: 92,
        icon: 'TrendingUp'
      },
      {
        id: 2,
        title: 'Category Performance',
        description: 'Electronics category shows highest sales volume, indicating strong market demand.',
        confidence: 87,
        icon: 'BarChart3'
      },
      {
        id: 3,
        title: 'User Engagement',
        description: 'Monthly active users showing steady growth with 15% increase over last quarter.',
        confidence: 78,
        icon: 'Activity'
      }
    ];

    return { fallbackKpis, fallbackCharts, fallbackInsights };
  };


  useEffect(() => {
    const loadDashboardData = async () => {
      if (!selectedDataset || !selectedDataset.id) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        await fetchDatasets();
        
        const token = localStorage.getItem('datasage-token');
        const { fallbackKpis, fallbackCharts, fallbackInsights } = generateFallbackData();
        
        // Load all dashboard data in parallel with better error handling
        const [overviewRes, insightsRes, chartsRes] = await Promise.allSettled([
          fetch(`/api/dashboard/${selectedDataset.id}/overview`, {
            headers: { 'Authorization': `Bearer ${token}` }
          }),
          fetch(`/api/dashboard/${selectedDataset.id}/insights`, {
            headers: { 'Authorization': `Bearer ${token}` }
          }),
          fetch(`/api/dashboard/${selectedDataset.id}/charts`, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
        ]);

        // Process overview data with fallback
        if (overviewRes.status === 'fulfilled' && overviewRes.value.ok) {
          const overviewData = await overviewRes.value.json();
          setKpiData(overviewData.kpis || fallbackKpis);
          setDatasetInfo(overviewData.dataset || {
            name: selectedDataset.name,
            row_count: selectedDataset.row_count || 9360,
            column_count: selectedDataset.column_count || 9
          });
        } else {
          console.log('Using fallback KPI data');
          setKpiData(fallbackKpis);
          setDatasetInfo({
            name: selectedDataset.name,
            row_count: selectedDataset.row_count || 9360,
            column_count: selectedDataset.column_count || 9
          });
        }

        // Process insights data with fallback
        if (insightsRes.status === 'fulfilled' && insightsRes.value.ok) {
          const insightsData = await insightsRes.value.json();
          setInsights(insightsData.insights || fallbackInsights);
        } else {
          console.log('Using fallback insights data');
          setInsights(fallbackInsights);
        }

        // Process charts data with fallback
        if (chartsRes.status === 'fulfilled' && chartsRes.value.ok) {
          const chartsData = await chartsRes.value.json();
          setChartData(chartsData.charts || fallbackCharts);
        } else {
          console.log('Using fallback chart data');
          setChartData(fallbackCharts);
        }

        // Load data preview
        if (token) {
          loadDataPreview(selectedDataset.id, token);
        }

      } catch (err) {
        console.error('Dashboard load failed:', err);
        // Use fallback data on complete failure
        const { fallbackKpis, fallbackCharts, fallbackInsights } = generateFallbackData();
        setKpiData(fallbackKpis);
        setChartData(fallbackCharts);
        setInsights(fallbackInsights);
        setDatasetInfo({
          name: selectedDataset.name,
          row_count: selectedDataset.row_count || 9360,
          column_count: selectedDataset.column_count || 9
        });
        toast.error('Using demo data - API connection failed');
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [selectedDataset, fetchDatasets]);

  // Generate AI-designed dashboard
  const generateAiDashboard = useCallback(async (forceRegenerate = false) => {
    if (!selectedDataset || !selectedDataset.id || !selectedDataset.is_processed) {
      setAiDashboardConfig(null);
      return;
    }
    
    try {
      setLayoutLoading(true);
      const token = localStorage.getItem('datasage-token');
      
      // First, get the dataset data for the AI to work with
      const dataResponse = await fetch(`/api/datasets/${selectedDataset.id}/data?page=1&page_size=1000`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (dataResponse.ok) {
        const dataResult = await dataResponse.json();
        setDatasetData(dataResult.data || []);
      }
      
      // Also load data preview for the table display
      loadDataPreview(selectedDataset.id, token);
      
      // Generate AI dashboard layout
      const response = await fetch(`/api/ai/${selectedDataset.id}/generate-dashboard?force_regenerate=${forceRegenerate}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const dashboardConfig = await response.json();
        setAiDashboardConfig(dashboardConfig);
        toast.success('AI dashboard generated successfully!');
      } else {
        throw new Error('Failed to generate AI dashboard');
      }
    } catch (error) {
      console.error('AI Dashboard generation failed:', error);
      toast.error('Failed to generate AI dashboard');
    } finally {
      setLayoutLoading(false);
    }
  }, [selectedDataset]);

  // Generate AI dashboard when dataset changes
  useEffect(() => {
    generateAiDashboard();
  }, [generateAiDashboard]);

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

  // Enhanced chart data processing with better fallbacks
  const processChartData = (data, fallback = []) => {
    if (!data || data.length === 0) return fallback;
    return data;
  };

  const revenueData = processChartData(chartData.revenue_over_time, [
    { month: 'Jan 2024', revenue: 45000 },
    { month: 'Feb 2024', revenue: 42000 },
    { month: 'Mar 2024', revenue: 48000 },
    { month: 'Apr 2024', revenue: 52000 },
    { month: 'May 2024', revenue: 49000 },
    { month: 'Jun 2024', revenue: 55000 }
  ]);

  const salesData = processChartData(chartData.sales_by_category, [
    { name: 'Electronics', value: 25000 },
    { name: 'Clothing', value: 18000 },
    { name: 'Books', value: 12000 },
    { name: 'Home', value: 15000 },
    { name: 'Sports', value: 10000 }
  ]);

  const mauData = processChartData(chartData.monthly_active_users, [
    { month: 'Week 1', users: 1200 },
    { month: 'Week 2', users: 1350 },
    { month: 'Week 3', users: 1420 },
    { month: 'Week 4', users: 1580 },
    { month: 'Week 5', users: 1650 },
    { month: 'Week 6', users: 1720 }
  ]);

  const trafficData = processChartData(chartData.traffic_source, [
    { name: 'Organic', value: 45 },
    { name: 'Direct', value: 25 },
    { name: 'Social', value: 15 },
    { name: 'Email', value: 10 },
    { name: 'Paid', value: 5 }
  ]);

  // Refresh dashboard data
  const refreshDashboard = async () => {
    if (!selectedDataset) return;
    
    setLoading(true);
    try {
      const token = localStorage.getItem('datasage-token');
      const { fallbackKpis, fallbackCharts, fallbackInsights } = generateFallbackData();
      
      const [overviewRes, insightsRes, chartsRes] = await Promise.allSettled([
        fetch(`/api/dashboard/${selectedDataset.id}/overview`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch(`/api/dashboard/${selectedDataset.id}/insights`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch(`/api/dashboard/${selectedDataset.id}/charts`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      // Update data with fresh API calls or fallbacks
      if (overviewRes.status === 'fulfilled' && overviewRes.value.ok) {
        const overviewData = await overviewRes.value.json();
        setKpiData(overviewData.kpis || fallbackKpis);
      }

      if (insightsRes.status === 'fulfilled' && insightsRes.value.ok) {
        const insightsData = await insightsRes.value.json();
        setInsights(insightsData.insights || fallbackInsights);
      }

      if (chartsRes.status === 'fulfilled' && chartsRes.value.ok) {
        const chartsData = await chartsRes.value.json();
        setChartData(chartsData.charts || fallbackCharts);
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
            DataWizard AI
        </h1>
          <p className="text-slate-400 text-lg">
            {selectedDataset?.name ? (
              <>
                Intelligent analysis of: <span className="text-slate-200 font-medium">{selectedDataset.name}</span>
                <span className="ml-4 text-sm bg-slate-800/50 px-3 py-1 rounded-full border border-slate-700">
                  {selectedDataset.row_count || 0} rows • {selectedDataset.column_count || 0} columns
                </span>
              </>
            ) : (
              "AI-powered data exploration and insights"
            )}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-sm text-slate-500">Last updated</p>
            <p className="text-slate-200 font-medium">
              {new Date().toLocaleTimeString()}
        </p>
      </div>

          {/* Dataset Selector */}
          {datasets.length > 0 && (
            <select 
              value={selectedDataset?.id || ''} 
              onChange={(e) => {
                const newDataset = datasets.find(d => d.id === e.target.value);
                if (newDataset) setSelectedDataset(newDataset);
              }}
              className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 focus:ring-2 focus:ring-emerald-500 text-white text-sm"
            >
              {datasets.map(d => (
                <option key={d.id} value={d.id}>
                  {d.name} {d.is_processed ? '✓' : '⏳'}
                </option>
              ))}
            </select>
          )}
          
          {/* Power-user "Redesign" button - subtle and optional */}
          <Button 
            onClick={() => generateAiDashboard(true)}
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
          
          <Button 
            onClick={() => setShowUploadModal(true)}
            className="bg-emerald-600 hover:bg-emerald-700 text-white border border-emerald-500 hover:border-emerald-400 transition-all duration-200 shadow-lg"
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload Dataset
          </Button>
        </div>
      </motion.div>

      {/* Main Dashboard Content */}
      {!selectedDataset ? (
        /* No Dataset State */
        <div className="text-center py-20 bg-slate-800/50 border border-slate-700 rounded-xl">
          <Database className="w-16 h-16 mx-auto text-slate-500 mb-6" />
          <h3 className="text-2xl font-semibold text-white mb-3">Welcome to DataWizard AI</h3>
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
          <h3 className="text-2xl font-semibold text-white mb-3">AI is Analyzing "{selectedDataset.name}"</h3>
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
      ) : aiDashboardConfig && aiDashboardConfig.components ? (
        /* AI Dashboard State */
        <div className="space-y-6">
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
              .map((component, index) => (
                <motion.div 
                  key={`kpi-${index}`} 
                  variants={{ 
                    hidden: { y: 20, opacity: 0 }, 
                    visible: { y: 0, opacity: 1 } 
                  }}
                >
                  <DashboardComponent 
                    component={component} 
                    datasetData={datasetData}
                  />
                </motion.div>
              ))}
          </motion.div>

          {/* Charts and Tables Section */}
          <motion.div
            className="grid gap-6"
            style={{ gridTemplateColumns: aiDashboardConfig.layout_grid || 'repeat(4, 1fr)' }}
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
              .filter(component => component.type !== 'kpi')
              .map((component, index) => (
                <motion.div 
                  key={`other-${index}`} 
                  variants={{ 
                    hidden: { y: 20, opacity: 0 }, 
                    visible: { y: 0, opacity: 1 } 
                  }}
                >
                  <DashboardComponent 
                    component={component} 
                    datasetData={datasetData}
                  />
                </motion.div>
              ))}
          </motion.div>

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
          <div className="flex flex-wrap gap-6">
            <AnimatePresence>
              {kpiData.map((kpi, i) => (
                <motion.div
                  key={kpi.title}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="group w-64 flex-shrink-0"
                >
                  <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 w-full h-full">
                  <div className="flex items-center justify-between mb-4">
                    <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">
                      {kpi.title}
                    </div>
                    <div className={`w-2 h-2 rounded-full ${
                        kpi.color === 'green' ? 'bg-emerald-500' :
                        kpi.color === 'red' ? 'bg-red-500' :
                        kpi.color === 'blue' ? 'bg-blue-500' : 'bg-slate-500'
                      }`}></div>
                    </div>
                    <div className="space-y-2">
                      <div className="text-3xl font-bold text-white">
                        {kpi.value}
                      </div>
                      <div className={`flex items-center text-sm ${
                        kpi.change && kpi.change.includes('+') ? 'text-emerald-400' : 'text-red-400'
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

      {/* Optimized Layout - Main Chart Full Width */}
      <div className="space-y-6">
        {/* Top Row: Main Chart + QUIS/Quality Stack */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Revenue Over Time - HERO CHART (8 columns) */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }} 
            animate={{ opacity: 1, y: 0 }} 
            className="lg:col-span-8 group"
          >
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
            <div className="flex items-center justify-between mb-6">
            <div>
                <h2 className="text-2xl font-bold text-white mb-2">Revenue Over Time</h2>
                <p className="text-slate-400 text-sm">Showing revenue trends and patterns</p>
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-500">Data Points</div>
                <div className="text-xl font-bold text-white">
                  {revenueData.length > 0 ? revenueData.length : 0}
                </div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={450}>
              <LineChart data={revenueData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="1 1" stroke="#334155" opacity={0.2} />
                <XAxis 
                  dataKey="month" 
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8' }}
                />
                <YAxis 
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8' }}
                  tickFormatter={(value) => `$${value.toLocaleString()}`}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#f1f5f9',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                  }}
                  formatter={(value, name) => [`$${value.toLocaleString()}`, 'Revenue']}
                  labelFormatter={(label) => `Month: ${label}`}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="revenue" 
                  stroke="#3b82f6" 
                  strokeWidth={3}
                  dot={{ fill: '#3b82f6', strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6, stroke: '#3b82f6', strokeWidth: 2, fill: '#1e40af' }}
                />
            </LineChart>
          </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Right Side: QUIS Insights + Data Quality Stack (4 columns) */}
        <div className="lg:col-span-4 space-y-4">
          {/* QUIS Insights - Top Priority */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }} 
            animate={{ opacity: 1, y: 0 }}
            className="group"
          >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-7 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
              <div className="flex items-center justify-between mb-4">
            <div>
                  <h3 className="text-2xl font-bold text-white mb-1">QUIS Insights</h3>
                  <p className="text-slate-400 text-1xs">AI Analysis</p>
                </div>
                <div className="w-8 h-8 bg-purple-500/20 rounded-lg flex items-center justify-center">
                  <Zap className="w-5 h-5 text-purple-400" />
                </div>
              </div>
              <div className="space-y-3">
                {insights.length > 0 ? (
                  insights.slice(0, 2).map((insight, index) => (
                    <div key={insight.id || index} className="bg-slate-800/50 rounded-3xl p-3 border border-slate-700">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-white">{insight.title}</span>
                        <span className="text-xs px-2 py-1 bg-green-500/20 text-green-400 rounded-full">
                          {insight.confidence}%
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">{insight.description}</p>
                    </div>
                  ))
                ) : (
                  <>
                    <div className="bg-slate-800/50 rounded-3xl p-3 border border-slate-700">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-white">Strong Correlation</span>
                        <span className="text-xs px-2 py-1 bg-green-500/20 text-green-400 rounded-full">0.87</span>
                      </div>
                      <p className="text-xs text-slate-400">Price ↔ Sales</p>
                    </div>
                    <div className="bg-slate-800/50 rounded-3xl p-3 border border-slate-700">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-white">Pattern Found</span>
                        <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-400 rounded-full">Q4</span>
                      </div>
                      <p className="text-xs text-slate-400">Seasonal Peak</p>
                    </div>
                  </>
                )}
              </div>
            </div>
        </motion.div>

          {/* Data Quality - Second Priority */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }} 
            animate={{ opacity: 1, y: 0 }}
            className="group"
          >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 text-center h-full">
              <div className="flex items-center justify-center mb-4">
                <div className="w-8 h-8 bg-emerald-500/20 rounded-lg flex items-center justify-center">
                  <CheckCircle className="w-5 h-5 text-emerald-400" />
                </div>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">Data Quality</h3>
              <div className="text-3xl font-bold text-emerald-400 mb-2">92%</div>
              <div className="text-sm text-slate-400 mb-4">High Quality</div>
              <div className="space-y-1 text-xs text-slate-500">
                <div className="flex justify-between">
                  <span>Complete</span>
                  <span className="text-emerald-400">95%</span>
                </div>
                <div className="flex justify-between">
                  <span>Accurate</span>
                  <span className="text-emerald-400">89%</span>
                </div>
                <div className="flex justify-between">
                  <span>Consistent</span>
                  <span className="text-emerald-400">92%</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Bottom Row: Activity and Distribution Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activity Over Time - Proper Size */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }} 
          animate={{ opacity: 1, y: 0 }}
          className="group"
        >
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-white mb-2">
                  {mauData.length > 0 ? 'Activity Over Time' : 'Data Activity'}
                </h3>
                <p className="text-slate-400 text-sm">Usage patterns and trends</p>
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-500">Periods</div>
                <div className="text-2xl font-bold text-white">
                  {mauData.length > 0 ? mauData.length : 0}
                </div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={mauData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="1 1" stroke="#334155" opacity={0.2} />
                <XAxis 
                  dataKey="month" 
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8' }}
                />
                <YAxis 
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8' }}
                  tickFormatter={(value) => value.toLocaleString()}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#f1f5f9',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                  }}
                  formatter={(value, name) => [value.toLocaleString(), 'Activity']}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="users" 
                  stroke="#10b981" 
                  strokeWidth={3}
                  dot={{ fill: '#10b981', strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6, stroke: '#10b981', strokeWidth: 2, fill: '#059669' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Data Distribution - Proper Size */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }} 
          animate={{ opacity: 1, y: 0 }}
          className="group"
        >
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-white mb-2">
                  {trafficData.length > 0 ? 'Data Distribution' : 'Category Breakdown'}
                </h3>
                <p className="text-slate-400 text-sm">Distribution across categories</p>
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-500">Segments</div>
                <div className="text-2xl font-bold text-white">
                  {trafficData.length > 0 ? trafficData.length : 0}
                </div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={trafficData} margin={{ top: 20, right: 30, left: 20, bottom: 40 }}>
                <CartesianGrid strokeDasharray="1 1" stroke="#334155" opacity={0.2} />
                <XAxis 
                  dataKey="name" 
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8' }}
                  angle={-45}
                  textAnchor="end"
                  height={60}
                />
                <YAxis 
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8' }}
                  tickFormatter={(value) => value.toLocaleString()}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#f1f5f9',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.3)'
                  }}
                  formatter={(value, name) => [value.toLocaleString(), 'Count']}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar 
                  dataKey="value" 
                  fill="#8b5cf6" 
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </div>



      {/* chart section */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }} 
        animate={{ opacity: 1, y: 0 }}
        className="group"
      >
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-white mb-2">
                  {salesData.length > 0 ? 'Sales by Category' : 'Category Analysis'}
                </h3>
                <p className="text-slate-400 text-sm">Performance breakdown by category</p>
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-500">Categories</div>
                <div className="text-2xl font-bold text-white">
                  {salesData.length > 0 ? salesData.length : 0}
                </div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={salesData} margin={{ top: 15, right: 20, left: 15, bottom: 35 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
                <XAxis 
                  dataKey="name" 
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8' }}
                  angle={-45}
                  textAnchor="end"
                  height={20}
                />
                <YAxis 
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: '#94a3b8' }}
                  tickFormatter={(value) => `$${value.toLocaleString()}`}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: 'black',
                    border: '1px solid #334155',
                    borderRadius: '15px',
                    color: '#f1f5f9',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.47)'
                  }}
                  formatter={(value, name) => [`$${value.toLocaleString()}`, 'Sales']}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar 
                  dataKey="value" 
                  fill="#3b82f6" 
                  radius={[5, 5, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

       
      </div>


      {/* Enhanced AI Insights Section */}
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
              <span>Showing first 10 rows</span>
              <span>•</span>
              <span>{datasetInfo?.row_count?.toLocaleString() || 0} total rows</span>
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
                {dataPreview.length > 0 ? Object.keys(dataPreview[0]).length : datasetInfo?.column_count || 0}
              </span> columns • 
              <span className="font-medium text-white ml-1">{datasetInfo?.row_count?.toLocaleString() || 0}</span> rows
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