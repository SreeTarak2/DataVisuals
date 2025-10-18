import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  Plus, 
  Database,
  Sparkles,
  LayoutGrid,
  BarChart3,
  BrainCircuit
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useDataset } from '../contexts/DatasetContext';
import KPIWidget from '../components/KPIWidget';

const Dashboard = () => {
  const { user } = useAuth();
  const { datasets, loading: datasetsLoading } = useDataset();
  const navigate = useNavigate();

  const quickActions = [
    {
      title: 'Upload New Data',
      description: 'Start by adding a new dataset file.',
      icon: Plus,
      action: () => navigate('/datasets'),
      color: 'bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400',
    },
    {
      title: 'Design a Dashboard',
      description: 'Let our AI assistant build a layout.',
      icon: LayoutGrid,
      action: () => navigate('/datasets'), // Should navigate to a place where they can select a dataset first
      color: 'bg-green-100 text-green-600 dark:bg-green-900/40 dark:text-green-400',
      disabled: datasets.length === 0
    },
    {
      title: 'Generate Quick Insights',
      description: 'Run automated analysis on your data.',
      icon: Sparkles,
      action: () => navigate('/datasets'),
      color: 'bg-purple-100 text-purple-600 dark:bg-purple-900/40 dark:text-purple-400',
      disabled: datasets.length === 0
    },
    {
      title: 'Start AI Chat',
      description: 'Ask questions in natural language.',
      icon: BrainCircuit,
      action: () => navigate('/chat'),
      color: 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/40 dark:text-yellow-400',
      disabled: datasets.length === 0
    }
  ];
  
  const totalRows = datasets.reduce((sum, ds) => sum + (ds.row_count || 0), 0);
  const totalColumns = datasets.reduce((sum, ds) => sum + (ds.column_count || 0), 0);

  // Empty state for new users
  if (!datasetsLoading && datasets.length === 0) {
    return (
      <div className="text-center py-20">
        <div className="w-24 h-24 mx-auto mb-6 rounded-full flex items-center justify-center bg-bg-tertiary">
            <BarChart3 className="w-12 h-12 text-brand-primary" />
        </div>
        <h2 className="text-2xl font-bold text-text-primary mb-2">Welcome to DataSage, {user?.username}!</h2>
        <p className="text-text-secondary max-w-md mx-auto mb-8">
          It looks like you don't have any data yet. Start your journey by uploading your first dataset.
        </p>
        <button onClick={() => navigate('/datasets')} className="btn btn-primary px-8 py-3 text-base">
          <Plus className="w-5 h-5 mr-2" />
          Upload Your First Dataset
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-text-primary">
          Welcome back, {user?.username}!
        </h1>
        <p className="text-lg text-text-secondary mt-1">
          Here's a summary of your workspace. Ready to dive in?
        </p>
      </div>

      {/* Overview KPI Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <KPIWidget
          title="Total Datasets"
          value={datasets.length}
          subtitle="Active in your workspace"
          icon={Database}
          loading={datasetsLoading}
        />
        <KPIWidget
          title="Total Rows Analyzed"
          value={totalRows}
          subtitle="Across all datasets"
          icon={LayoutGrid}
          loading={datasetsLoading}
        />
        <KPIWidget
          title="Total Columns"
          value={totalColumns}
          subtitle="Available for analysis"
          icon={BarChart3}
          loading={datasetsLoading}
        />
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary mb-4">Quick Start</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.title}
                onClick={action.action}
                disabled={action.disabled}
                className="card p-5 text-left h-full disabled:opacity-50 disabled:cursor-not-allowed group"
              >
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${action.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-text-primary mb-1 group-hover:text-brand-primary transition-colors">
                  {action.title}
                </h3>
                <p className="text-sm text-text-secondary">
                  {action.description}
                </p>
              </button>
            );
          })}
        </div>
      </div>
      
      {/* Recent Datasets */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-text-primary">Recent Datasets</h2>
          <Link to="/datasets" className="text-sm font-medium text-brand-primary hover:text-brand-primary-hover">
            View all
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {datasetsLoading ? (
            // Skeleton loaders for recent datasets
            [...Array(3)].map((_, i) => <KPIWidget loading key={i} />)
          ) : (
            datasets.slice(0, 3).map((dataset) => (
              <div 
                key={dataset.id} 
                className="card p-5 text-left cursor-pointer"
                onClick={() => navigate('/datasets')} // Or to a specific dataset page
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-x-3">
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-bg-tertiary">
                      <Database className="w-5 h-5 text-text-secondary" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-text-primary truncate">
                        {dataset.name || 'Untitled Dataset'}
                      </h3>
                      <p className="text-xs text-text-muted">
                        Uploaded on {new Date(dataset.upload_date || dataset.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-start text-sm text-text-secondary gap-x-6">
                  <div className="text-center">
                    <p className="font-medium text-text-primary">{dataset.row_count || 0}</p>
                    <p className="text-xs text-text-muted">Rows</p>
                  </div>
                  <div className="text-center">
                    <p className="font-medium text-text-primary">{dataset.column_count || 0}</p>
                    <p className="text-xs text-text-muted">Columns</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;