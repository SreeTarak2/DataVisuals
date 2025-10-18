import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  LineChart, 
  Line, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { 
  TrendingUp, 
  TrendingDown, 
  BarChart3, 
  CheckCircle, 
  Zap, 
  ChevronRight, 
  Upload,
  Users,
  DollarSign,
  Activity
} from 'lucide-react';
import { Button } from '../components/Button';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const [kpiData, setKpiData] = useState([]);
  const [insights, setInsights] = useState([]);
  const [chartData, setChartData] = useState({});
  const [datasetInfo, setDatasetInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const selectedDataset = JSON.parse(localStorage.getItem('selectedDataset') || 'null');

  // Icon mapping for insights
  const iconMap = {
    'trending-up': TrendingUp,
    'trending-down': TrendingDown,
    'bar-chart': BarChart3,
    'check-circle': CheckCircle,
    'zap': Zap,
    'users': Users,
    'dollar-sign': DollarSign,
    'activity': Activity,
  };

  // Load dashboard data
  useEffect(() => {
    const loadDashboardData = async () => {
      if (!selectedDataset) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const token = localStorage.getItem('datasage-token');
        
        if (!token) {
          setError('No authentication token found');
          setLoading(false);
          return;
        }

        const headers = {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        };

        // Fetch all dashboard data in parallel
        const [overviewResponse, insightsResponse, chartsResponse] = await Promise.all([
          fetch(`/api/dashboard/${selectedDataset.id}/overview`, { headers }),
          fetch(`/api/dashboard/${selectedDataset.id}/insights`, { headers }),
          fetch(`/api/dashboard/${selectedDataset.id}/charts`, { headers })
        ]);

        // Handle 401 errors specifically
        if (overviewResponse.status === 401 || insightsResponse.status === 401 || chartsResponse.status === 401) {
          console.error('401 Unauthorized - Token may be expired');
          setError('Authentication expired. Please log in again.');
          return;
        }

        if (!overviewResponse.ok) {
          throw new Error(`Overview API error: ${overviewResponse.status}`);
        }
        if (!insightsResponse.ok) {
          throw new Error(`Insights API error: ${insightsResponse.status}`);
        }
        if (!chartsResponse.ok) {
          throw new Error(`Charts API error: ${chartsResponse.status}`);
        }

        const [overviewData, insightsData, chartsData] = await Promise.all([
          overviewResponse.json(),
          insightsResponse.json(),
          chartsResponse.json()
        ]);

        setKpiData(overviewData.kpis || []);
        setInsights(insightsData.insights || []);
        setChartData(chartsData);
        setDatasetInfo(overviewData.dataset_info);

      } catch (err) {
        console.error('Dashboard data loading error:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [selectedDataset]);

  // Extract chart data
  const revenueData = chartData.revenue_over_time || [];
  const salesData = chartData.sales_by_category || [];
  const mauData = chartData.activity_over_time || [];
  const trafficData = chartData.data_distribution || [];

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 bg-red-500/20 rounded-lg flex items-center justify-center mx-auto mb-4">
            <TrendingDown className="w-6 h-6 text-red-400" />
          </div>
          <p className="text-red-400 mb-4">{error}</p>
          <Button onClick={() => navigate('/login')}>Go to Login</Button>
        </div>
      </div>
    );
  }

  if (!selectedDataset) {
    return (
      <div className="min-h-screen bg-slate-950 p-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="w-16 h-16 bg-slate-800 rounded-xl flex items-center justify-center mx-auto mb-6">
            <BarChart3 className="w-8 h-8 text-slate-400" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-4">No Dataset Selected</h1>
          <p className="text-slate-400 mb-8">Please upload a dataset to view the dashboard</p>
          <Button onClick={() => navigate('/datasets')}>
            <Upload className="w-4 h-4 mr-2" />
            Upload Dataset
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white tracking-tight">Dashboard</h1>
          <p className="text-slate-400 text-lg mt-2">
            {selectedDataset?.name || 'Dataset Analysis'}
          </p>
        </div>
        <Button 
          onClick={() => navigate('/datasets')}
          className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
        >
          <Upload className="w-4 h-4 mr-2" />
          Upload Dataset
        </Button>
      </div>

      {/* Dataset Info */}
      {datasetInfo && (
        <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-6 text-sm text-slate-400">
            <span>Rows: <span className="text-white font-medium">{datasetInfo.row_count?.toLocaleString()}</span></span>
            <span>Columns: <span className="text-white font-medium">{datasetInfo.column_count}</span></span>
            <span>Last Updated: <span className="text-white font-medium">
              {new Date(datasetInfo.updated_at).toLocaleDateString()}
            </span></span>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <AnimatePresence>
          {kpiData.map((kpi, index) => (
            <motion.div
              key={kpi.id || index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-blue-400" />
                </div>
                <span className="text-xs px-2 py-1 rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
                  +{kpi.change || '0'}%
                </span>
              </div>
              <div>
                <p className="text-slate-400 text-sm mb-1">{kpi.label}</p>
                <p className="text-2xl font-bold text-white">{kpi.value}</p>
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
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
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
              {revenueData.length > 0 ? (
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
              ) : (
                <div className="flex items-center justify-center h-[400px] text-slate-400">
                  <div className="text-center">
                    <TrendingUp className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p className="text-lg font-medium">No revenue data available</p>
                    <p className="text-sm">Upload a dataset to see revenue trends</p>
                  </div>
                </div>
              )}
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
              <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-white mb-1">QUIS Insights</h3>
                    <p className="text-slate-400 text-xs">AI Analysis</p>
                  </div>
                  <div className="w-8 h-8 bg-purple-500/20 rounded-lg flex items-center justify-center">
                    <Zap className="w-5 h-5 text-purple-400" />
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-white">Strong Correlation</span>
                      <span className="text-xs px-2 py-1 bg-green-500/20 text-green-400 rounded-full">0.87</span>
                    </div>
                    <p className="text-xs text-slate-400">Price ↔ Sales</p>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-white">Pattern Found</span>
                      <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-400 rounded-full">Q4</span>
                    </div>
                    <p className="text-xs text-slate-400">Seasonal Peak</p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Data Quality - Second Priority */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }} 
              animate={{ opacity: 1, y: 0 }}
              className="group"
            >
              <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 text-center h-full">
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
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
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
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
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

        {/* Sales by Category - Separate Row */}
        <div className="grid grid-cols-1 lg:grid-cols-1 gap-6">
          <motion.div 
            initial={{ opacity: 0, y: 20 }} 
            animate={{ opacity: 1, y: 0 }}
            className="group"
          >
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
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
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={salesData} margin={{ top: 20, right: 30, left: 20, bottom: 40 }}>
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
                    formatter={(value, name) => [`$${value.toLocaleString()}`, 'Sales']}
                    labelStyle={{ color: '#94a3b8' }}
                  />
                  <Bar 
                    dataKey="value" 
                    fill="#3b82f6" 
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Enhanced AI Insights Section */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }} 
        animate={{ opacity: 1, y: 0 }}
        className="group"
      >
        <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
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
                className="flex items-start gap-4 p-4 rounded-lg border border-slate-800 bg-slate-800/30 hover:bg-slate-800/50 hover:border-slate-700 transition-all duration-200"
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
                <button className="ml-auto p-1 text-slate-400 hover:text-white transition-colors">
                  <ChevronRight className="w-4 h-4" />
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
    </div>
  );
};

export default Dashboard;


