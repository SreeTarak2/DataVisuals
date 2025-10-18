import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Database, Loader2, AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '../components/Button';
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
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-4xl font-bold text-white tracking-tight">
            AI Dashboard
          </h1>
          <p className="text-slate-400 text-lg mt-2">
            {selectedDataset ? selectedDataset.name : 'No dataset selected'}
          </p>
          {datasetInfo && (
            <div className="flex items-center gap-4 mt-3 text-sm text-slate-500">
              <span>{datasetInfo.row_count?.toLocaleString() || 'N/A'} rows</span>
              <span>•</span>
              <span>{datasetInfo.column_count || 'N/A'} columns</span>
              <span>•</span>
              <span>Last updated</span>
              <span className="text-slate-200 font-medium">
                {new Date().toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Button 
            onClick={handleRefresh}
            variant="ghost"
            className="text-slate-400 hover:text-white"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <GlobalUploadButton variant="ghost" />
        </div>
      </motion.div>

      {/* Dynamic Dashboard Content */}
      <DynamicDashboardRenderer 
        layout={layout}
        datasetInfo={datasetInfo}
        loading={loading}
      />
    </div>
  );
};

export default Dashboard;

