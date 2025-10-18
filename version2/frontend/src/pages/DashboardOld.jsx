import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Database, TrendingUp, Activity, Zap, Loader2, FileText, ChevronRight, AlertTriangle, CheckCircle, Lightbulb, Upload, TrendingDown, BarChart3, RefreshCw } from 'lucide-react';
import { Button } from '../components/Button';
import GlassCard from '../components/common/GlassCard';
import GlobalUploadButton from '../components/GlobalUploadButton';
import DynamicDashboardRenderer from '../components/dashboard/DynamicDashboardRenderer';
import useDashboardData from '../hooks/useDashboardData';
import { useAuth } from '../contexts/AuthContext';
import useDatasetStore from '../store/datasetStore';
import { toast } from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const { user } = useAuth();
  const { datasets, selectedDataset, fetchDatasets } = useDatasetStore();
  const navigate = useNavigate();
  
  // Use the new dynamic dashboard hook
  const {
    layout,
    kpis,
    insights,
    charts,
    datasetInfo,
    loading,
    error,
    userExpertise,
    setUserExpertise,
    refreshDashboard
  } = useDashboardData(selectedDataset);

  // Handle refresh action
  const handleRefresh = () => {
    refreshDashboard();
    toast.success('Dashboard refreshed');
  };

  // No need for useEffect - data loading is handled by the hook

  // Load data preview
  const loadDataPreview = async (datasetId, token) => {
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

  // Get chart data from API or use defaults
  const revenueData = chartData.revenue_over_time || [];
  const salesData = chartData.sales_by_category || [];
  const mauData = chartData.monthly_active_users || [];
  const trafficData = chartData.traffic_source || [];

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 p-6">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <Loader2 className="w-12 h-12 animate-spin text-blue-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white mb-2">Loading Dashboard</h3>
            <p className="text-slate-400">AI is analyzing your data and generating insights...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!selectedDataset) {
    return (
      <div className="min-h-screen bg-slate-950 p-6">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <Database className="w-16 h-16 mx-auto mb-4 text-slate-500" />
            <h2 className="text-2xl font-bold text-white mb-2">No Dataset Selected</h2>
            <p className="text-slate-400 mb-6">Please select a dataset to view the dashboard</p>
            <GlobalUploadButton variant="default" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 p-6">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <AlertTriangle className="w-16 h-16 mx-auto mb-4 text-red-400" />
            <h2 className="text-2xl font-bold text-white mb-2">Error Loading Dashboard</h2>
            <p className="text-slate-400 mb-6">{error}</p>
            <Button onClick={handleRefresh} className="bg-blue-500 hover:bg-blue-600">
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry
            </Button>
          </div>
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
          <h1 className="text-4xl font-bold text-white tracking-tight">Analytics Dashboard</h1>
          <p className="text-slate-400 text-lg">
            {datasetInfo?.name || selectedDataset?.name ? (
              <>
                Analyzing: <span className="text-slate-200 font-medium">{datasetInfo?.name || selectedDataset?.name}</span>
                <span className="ml-4 text-sm bg-slate-800/50 px-3 py-1 rounded-full border border-slate-700">
                  {datasetInfo?.row_count || selectedDataset?.row_count || 0} rows • {datasetInfo?.column_count || selectedDataset?.column_count || 0} columns
                </span>
              </>
            ) : (
              "No dataset selected"
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
          <GlobalUploadButton variant="ghost" />
            </div>
      </motion.div>

      {/* Enhanced KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <AnimatePresence>
          {kpiData.map((kpi, i) => (
            <motion.div
              key={kpi.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="group"
            >
              <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-3xl p-6 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20">
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
            {revenueData.length > 0 ? (
              <ResponsiveContainer width="100%" height={600}>
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
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-7 hover:border-slate-700 transition-all duration-300 hover:shadow-xl hover:shadow-slate-900/20 h-full">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-2xl font-bold text-white mb-1">QUIS Insights</h3>
                <p className="text-slate-400 text-1xs">AI Analysis</p>
              </div>
              <div className="flex items-center gap-2">
                {/* Expertise Toggle */}
                <div className="flex bg-slate-800/50 rounded-lg p-1">
                  <button
                    onClick={() => setUserExpertise('beginner')}
                    className={`px-3 py-1 text-xs rounded-md transition-all duration-200 ${
                      userExpertise === 'beginner'
                        ? 'bg-blue-500 text-white shadow-lg'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    👤 Beginner
                  </button>
                  <button
                    onClick={() => setUserExpertise('expert')}
                    className={`px-3 py-1 text-xs rounded-md transition-all duration-200 ${
                      userExpertise === 'expert'
                        ? 'bg-blue-500 text-white shadow-lg'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    🔬 Expert
                  </button>
                </div>
                <div className="w-8 h-8 bg-purple-500/20 rounded-lg flex items-center justify-center">
                  <Zap className="w-5 h-5 text-purple-400" />
                </div>
              </div>
            </div>
              <div className="space-y-3">
                {getAdaptiveInsights().map((insight, index) => (
                  <div key={index} className="bg-slate-800/50 rounded-3xl p-4 border border-slate-700 hover:border-slate-600 transition-all duration-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">{insight.translated.title}</span>
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        insight.type === 'correlation' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                      }`}>
                        {insight.value}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mb-2">{insight.translated.description}</p>
                    {userExpertise === 'beginner' && (
                      <div className="text-xs text-blue-300 bg-blue-500/10 rounded-2xl p-2 border border-blue-500/20">
                        💡 <strong>What to do:</strong> {insight.translated.action}
                      </div>
                    )}
                    {userExpertise === 'expert' && (
                      <p className="text-xs text-slate-500 font-mono">{insight.description}</p>
                    )}
                  </div>
                ))}
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
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-white flex items-center gap-3">
              <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
                <Zap className="w-5 h-5 text-blue-400" />
              </div>
            AI Insights
          </h2>
            {/* Expertise Toggle for Main Insights */}
            <div className="flex bg-slate-800/50 rounded-lg p-1">
              <button
                onClick={() => setUserExpertise('beginner')}
                className={`px-3 py-1 text-xs rounded-md transition-all duration-200 ${
                  userExpertise === 'beginner'
                    ? 'bg-blue-500 text-white shadow-lg'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                👤 Beginner
              </button>
              <button
                onClick={() => setUserExpertise('expert')}
                className={`px-3 py-1 text-xs rounded-md transition-all duration-200 ${
                  userExpertise === 'expert'
                    ? 'bg-blue-500 text-white shadow-lg'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                🔬 Expert
              </button>
            </div>
          </div>
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
                    <p className="text-sm text-white font-medium">
                      {userExpertise === 'beginner' 
                        ? translateInsight({ title: insight.title }, 'beginner').title
                        : insight.title
                      }
                    </p>
                    <span className="text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                      {insight.confidence}%
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed mb-2">
                    {userExpertise === 'beginner' 
                      ? translateInsight({ title: insight.title }, 'beginner').description
                      : insight.description
                    }
                  </p>
                  {userExpertise === 'beginner' && (
                    <div className="text-xs text-blue-300 bg-blue-500/10 rounded-lg p-2 border border-blue-500/20">
                      💡 <strong>Action:</strong> {translateInsight({ title: insight.title }, 'beginner').action}
                    </div>
                  )}
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
  );
};

export default Dashboard;