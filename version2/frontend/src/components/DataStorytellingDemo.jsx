import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, BarChart3, TrendingUp, Lightbulb, Sparkles } from 'lucide-react';
import { Button } from './Button';

const DataStorytellingDemo = ({ datasetId, onClose }) => {
  const [activeTab, setActiveTab] = useState('story');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState({});

  const generateStory = async (storyType = 'business_impact') => {
    setLoading(true);
    try {
      const token = localStorage.getItem('datasage-token');
      const response = await fetch(`/api/ai/${datasetId}/generate-story`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ story_type: storyType })
      });

      if (response.ok) {
        const data = await response.json();
        setResults(prev => ({ ...prev, story: data }));
      }
    } catch (error) {
      console.error('Error generating story:', error);
    } finally {
      setLoading(false);
    }
  };

  const explainChart = async (chartConfig) => {
    setLoading(true);
    try {
      const token = localStorage.getItem('datasage-token');
      const response = await fetch(`/api/ai/${datasetId}/explain-chart`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          chart_config: chartConfig,
          chart_data: [] // Sample data would go here
        })
      });

      if (response.ok) {
        const data = await response.json();
        setResults(prev => ({ ...prev, chartExplanation: data }));
      }
    } catch (error) {
      console.error('Error explaining chart:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateBusinessInsights = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('datasage-token');
      const response = await fetch(`/api/ai/${datasetId}/business-insights`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          business_context: "General business analysis and strategic planning"
        })
      });

      if (response.ok) {
        const data = await response.json();
        setResults(prev => ({ ...prev, businessInsights: data }));
      }
    } catch (error) {
      console.error('Error generating business insights:', error);
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'story', label: 'Data Story', icon: BookOpen },
    { id: 'chart', label: 'Chart Explanation', icon: BarChart3 },
    { id: 'business', label: 'Business Insights', icon: TrendingUp }
  ];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-slate-900 rounded-2xl border border-slate-800 w-full max-w-4xl max-h-[90vh] overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Enhanced Data Storytelling</h2>
              <p className="text-sm text-slate-400">AI-powered narratives and insights</p>
            </div>
          </div>
          <Button 
            onClick={onClose}
            variant="outline"
            className="border-slate-700 text-slate-300 hover:bg-slate-800"
          >
            Close
          </Button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-800">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-6 py-4 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'text-purple-400 border-b-2 border-purple-400 bg-purple-500/10'
                    : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {activeTab === 'story' && (
            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <Button 
                  onClick={() => generateStory('business_impact')}
                  disabled={loading}
                  className="bg-purple-600 hover:bg-purple-700"
                >
                  {loading ? 'Generating...' : 'Generate Business Story'}
                </Button>
                <Button 
                  onClick={() => generateStory('trend_analysis')}
                  disabled={loading}
                  variant="outline"
                  className="border-slate-700 text-slate-300 hover:bg-slate-800"
                >
                  Generate Trend Story
                </Button>
              </div>

              {results.story && (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-slate-800/50 rounded-xl p-6 border border-slate-700"
                >
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-purple-400" />
                    {results.story.story?.title || 'Data Story'}
                  </h3>
                  
                  <div className="space-y-4">
                    <div className="bg-slate-700/50 rounded-lg p-4">
                      <h4 className="text-sm font-medium text-purple-400 mb-2">Opening Hook</h4>
                      <p className="text-slate-300">{results.story.story?.hook}</p>
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-purple-400 mb-2">Narrative</h4>
                      <p className="text-slate-300 leading-relaxed">{results.story.story?.narrative}</p>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <h4 className="text-sm font-medium text-purple-400 mb-2">Key Metrics</h4>
                        <ul className="space-y-1">
                          {results.story.story?.key_metrics?.map((metric, index) => (
                            <li key={index} className="text-sm text-slate-300">• {metric}</li>
                          ))}
                        </ul>
                      </div>
                      
                      <div>
                        <h4 className="text-sm font-medium text-purple-400 mb-2">Recommendations</h4>
                        <ul className="space-y-1">
                          {results.story.story?.recommendations?.map((rec, index) => (
                            <li key={index} className="text-sm text-slate-300">• {rec}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </div>
          )}

          {activeTab === 'chart' && (
            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <Button 
                  onClick={() => explainChart({ chart_type: 'bar', columns: ['category', 'value'] })}
                  disabled={loading}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {loading ? 'Explaining...' : 'Explain Bar Chart'}
                </Button>
                <Button 
                  onClick={() => explainChart({ chart_type: 'line', columns: ['date', 'value'] })}
                  disabled={loading}
                  variant="outline"
                  className="border-slate-700 text-slate-300 hover:bg-slate-800"
                >
                  Explain Line Chart
                </Button>
              </div>

              {results.chartExplanation && (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-slate-800/50 rounded-xl p-6 border border-slate-700"
                >
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-blue-400" />
                    Chart Explanation
                  </h3>
                  
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-medium text-blue-400 mb-2">Purpose</h4>
                      <p className="text-slate-300">{results.chartExplanation.explanation?.purpose}</p>
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-blue-400 mb-2">Key Patterns</h4>
                      <ul className="space-y-1">
                        {results.chartExplanation.explanation?.key_patterns?.map((pattern, index) => (
                          <li key={index} className="text-sm text-slate-300">• {pattern}</li>
                        ))}
                      </ul>
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-blue-400 mb-2">Business Meaning</h4>
                      <p className="text-slate-300">{results.chartExplanation.explanation?.business_meaning}</p>
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-blue-400 mb-2">Next Steps</h4>
                      <p className="text-slate-300">{results.chartExplanation.explanation?.next_steps}</p>
                    </div>
                  </div>
                </motion.div>
              )}
            </div>
          )}

          {activeTab === 'business' && (
            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <Button 
                  onClick={generateBusinessInsights}
                  disabled={loading}
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {loading ? 'Generating...' : 'Generate Business Insights'}
                </Button>
              </div>

              {results.businessInsights && (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-slate-800/50 rounded-xl p-6 border border-slate-700"
                >
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-emerald-400" />
                    Business Insights
                  </h3>
                  
                  <div className="space-y-6">
                    <div>
                      <h4 className="text-sm font-medium text-emerald-400 mb-2">Executive Summary</h4>
                      <p className="text-slate-300">{results.businessInsights.business_insights?.executive_summary}</p>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div>
                        <h4 className="text-sm font-medium text-emerald-400 mb-3">Opportunities</h4>
                        <div className="space-y-3">
                          {results.businessInsights.business_insights?.opportunities?.map((opp, index) => (
                            <div key={index} className="bg-slate-700/50 rounded-lg p-3">
                              <h5 className="text-sm font-medium text-white">{opp.title}</h5>
                              <p className="text-xs text-slate-400 mt-1">{opp.description}</p>
                              <div className="flex items-center gap-2 mt-2">
                                <span className={`text-xs px-2 py-1 rounded ${
                                  opp.potential_impact === 'High' ? 'bg-red-500/20 text-red-400' :
                                  opp.potential_impact === 'Medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                  'bg-green-500/20 text-green-400'
                                }`}>
                                  {opp.potential_impact} Impact
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      <div>
                        <h4 className="text-sm font-medium text-emerald-400 mb-3">Strategic Recommendations</h4>
                        <div className="space-y-3">
                          {results.businessInsights.business_insights?.strategic_recommendations?.map((rec, index) => (
                            <div key={index} className="bg-slate-700/50 rounded-lg p-3">
                              <h5 className="text-sm font-medium text-white">{rec.action}</h5>
                              <p className="text-xs text-slate-400 mt-1">Timeline: {rec.timeline}</p>
                              <p className="text-xs text-slate-400">Expected: {rec.expected_outcome}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
};

export default DataStorytellingDemo;

