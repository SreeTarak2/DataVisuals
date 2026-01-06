/**
 * Charts.jsx - Refactored Version (Example Implementation)
 * 
 * This is a simplified example showing how to integrate with the new
 * /api/charts/render endpoint. Key changes:
 * 
 * 1. No more manual data transformations
 * 2. Backend returns Plotly-ready traces + layout
 * 3. Integrated AI explanations
 * 4. Cleaner component structure
 * 
 * Compare with original Charts.jsx (~943 lines) vs this (~300 lines)
 */

import React, { useState, useEffect } from 'react';
import { 
  Database, Save, Download, Settings, Loader2, Sparkles 
} from 'lucide-react';
import { motion } from 'framer-motion';
import GlassCard from '../components/common/GlassCard';
import PlotlyChart from '../components/PlotlyChart';
import ExplanationPanel from '../components/ExplanationPanel';
import { toast } from 'react-hot-toast';
import useDatasetStore from '../store/datasetStore';

const ChartsRefactored = () => {
  const { selectedDataset } = useDatasetStore();
  
  // Chart configuration
  const [chartType, setChartType] = useState('bar');
  const [fields, setFields] = useState([]);
  const [aggregation, setAggregation] = useState('sum');
  const [chartTitle, setChartTitle] = useState('');
  
  // Data
  const [columns, setColumns] = useState([]);
  const [chartResponse, setChartResponse] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  
  // UI State
  const [loading, setLoading] = useState(false);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);

  // Chart types with metadata
  const chartTypes = [
    { id: 'bar', label: 'Bar Chart', icon: '📊' },
    { id: 'line', label: 'Line Chart', icon: '📈' },
    { id: 'pie', label: 'Pie Chart', icon: '🥧' },
    { id: 'scatter', label: 'Scatter Plot', icon: '⚫' },
    { id: 'histogram', label: 'Histogram', icon: '📉' },
    { id: 'area', label: 'Area Chart', icon: '🏔️' },
    { id: 'heatmap', label: 'Heatmap', icon: '🌡️' },
  ];

  // Load columns on dataset selection
  useEffect(() => {
    if (selectedDataset) {
      loadColumns();
      loadRecommendations();
    }
  }, [selectedDataset]);

  const loadColumns = async () => {
    try {
      if (selectedDataset?.metadata?.column_metadata) {
        const columnNames = selectedDataset.metadata.column_metadata.map(col => col.name);
        setColumns(columnNames);
        
        // Auto-select first two columns
        if (columnNames.length >= 2) {
          setFields([columnNames[0], columnNames[1]]);
        }
      }
    } catch (error) {
      console.error('Failed to load columns:', error);
      toast.error('Failed to load dataset columns');
    }
  };

  // NEW: Load AI recommendations
  const loadRecommendations = async () => {
    if (!selectedDataset?.id) return;
    
    try {
      setLoadingRecommendations(true);
      const response = await fetch(
        `/api/charts/recommendations?dataset_id=${selectedDataset.id}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setRecommendations(data);
      }
    } catch (error) {
      console.error('Failed to load recommendations:', error);
    } finally {
      setLoadingRecommendations(false);
    }
  };

  // NEW: Unified chart generation using /api/charts/render
  const generateChart = async () => {
    if (!selectedDataset || fields.length < 1) {
      toast.error('Please select dataset and columns');
      return;
    }

    try {
      setLoading(true);
      setChartResponse(null);

      // Call new unified render endpoint
      const response = await fetch('/api/charts/render', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          dataset_id: selectedDataset.id,
          chart_type: chartType,
          fields: fields,
          aggregation: aggregation,
          title: chartTitle || `${chartType} Chart`
        })
      });

      if (!response.ok) {
        throw new Error('Failed to render chart');
      }

      const data = await response.json();
      
      // Data now contains: { traces, layout, explanation, confidence, metadata }
      setChartResponse(data);
      
      toast.success('Chart generated successfully!');
      
    } catch (error) {
      console.error('Chart generation failed:', error);
      toast.error('Failed to generate chart');
    } finally {
      setLoading(false);
    }
  };

  // Apply a recommendation
  const applyRecommendation = (recommendation) => {
    setChartType(recommendation.chart_type);
    setFields(recommendation.suitable_columns.slice(0, 2));
    setChartTitle(recommendation.title);
    toast.success(`Applied: ${recommendation.title}`);
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Chart Studio</h1>
          <p className="text-gray-400">Create beautiful visualizations</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT: Configuration Panel */}
        <GlassCard className="lg:col-span-1">
          <h2 className="text-lg font-semibold text-white mb-4">
            Chart Configuration
          </h2>

          {/* Chart Type Selector */}
          <div className="space-y-2 mb-4">
            <label className="text-sm text-gray-400">Chart Type</label>
            <div className="grid grid-cols-2 gap-2">
              {chartTypes.map(type => (
                <button
                  key={type.id}
                  onClick={() => setChartType(type.id)}
                  className={`p-3 rounded-lg border transition-all ${
                    chartType === type.id
                      ? 'border-purple-500 bg-purple-500/20 text-white'
                      : 'border-gray-700 hover:border-gray-600 text-gray-400'
                  }`}
                >
                  <div className="text-2xl mb-1">{type.icon}</div>
                  <div className="text-xs">{type.label}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Field Selectors */}
          <div className="space-y-3 mb-4">
            <div>
              <label className="text-sm text-gray-400 mb-1 block">
                Column 1 {chartType === 'bar' && '(X-Axis)'}
              </label>
              <select
                value={fields[0] || ''}
                onChange={(e) => setFields([e.target.value, fields[1]])}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
              >
                <option value="">Select column...</option>
                {columns.map(col => (
                  <option key={col} value={col}>{col}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1 block">
                Column 2 {chartType === 'bar' && '(Y-Axis)'}
              </label>
              <select
                value={fields[1] || ''}
                onChange={(e) => setFields([fields[0], e.target.value])}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
              >
                <option value="">Select column...</option>
                {columns.map(col => (
                  <option key={col} value={col}>{col}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Aggregation */}
          <div className="mb-4">
            <label className="text-sm text-gray-400 mb-1 block">Aggregation</label>
            <select
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
            >
              <option value="sum">Sum</option>
              <option value="count">Count</option>
              <option value="mean">Mean</option>
              <option value="nunique">Unique Count</option>
            </select>
          </div>

          {/* Title */}
          <div className="mb-4">
            <label className="text-sm text-gray-400 mb-1 block">Chart Title</label>
            <input
              type="text"
              value={chartTitle}
              onChange={(e) => setChartTitle(e.target.value)}
              placeholder="Optional title..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
            />
          </div>

          {/* Generate Button */}
          <button
            onClick={generateChart}
            disabled={loading || !fields[0]}
            className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 
                       hover:to-blue-700 text-white font-semibold py-3 rounded-lg transition-all
                       disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                Generate Chart
              </>
            )}
          </button>

          {/* AI Recommendations */}
          {recommendations.length > 0 && (
            <div className="mt-6 pt-6 border-t border-gray-700">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400" />
                AI Suggestions
              </h3>
              <div className="space-y-2">
                {recommendations.slice(0, 3).map((rec, index) => (
                  <button
                    key={index}
                    onClick={() => applyRecommendation(rec)}
                    className="w-full p-3 bg-gray-800/50 hover:bg-gray-800 border border-gray-700 
                               rounded-lg text-left transition-all"
                  >
                    <div className="text-sm font-medium text-white">{rec.title}</div>
                    <div className="text-xs text-gray-400 mt-1">{rec.description}</div>
                    <div className="text-xs text-purple-400 mt-1">
                      {rec.confidence} Confidence
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </GlassCard>

        {/* RIGHT: Chart Display */}
        <GlassCard className="lg:col-span-2">
          <h2 className="text-lg font-semibold text-white mb-4">
            Visualization
          </h2>

          {loading ? (
            <div className="flex items-center justify-center h-96">
              <Loader2 className="w-12 h-12 animate-spin text-purple-500" />
            </div>
          ) : chartResponse ? (
            <div>
              {/* NEW: Simply pass chartResponse to PlotlyChart */}
              <PlotlyChart chartResponse={chartResponse} />
              
              {/* NEW: Display AI Explanation */}
              <ExplanationPanel 
                explanation={chartResponse.explanation}
                confidence={chartResponse.confidence}
              />

              {/* Metadata */}
              {chartResponse.metadata && (
                <div className="mt-4 p-3 bg-gray-800/50 rounded-lg text-xs text-gray-400">
                  Rendered {chartResponse.metadata.rows_used?.toLocaleString()} rows 
                  in {chartResponse.metadata.render_time_ms?.toFixed(0)}ms
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-96 text-gray-500">
              <Database className="w-16 h-16 mb-4" />
              <p>Select chart type and columns to generate visualization</p>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
};

export default ChartsRefactored;
