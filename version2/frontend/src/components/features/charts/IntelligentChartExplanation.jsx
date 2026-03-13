import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lightbulb, Brain, TrendingUp, AlertTriangle, Target, Zap, Sparkles, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import { toast } from 'react-hot-toast';

const IntelligentChartExplanation = ({ component, datasetData, datasetId }) => {
  const [insightData, setInsightData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  // Generate intelligent explanation by routing to the backend API explicitly on user request
  const fetchRealInsights = async () => {
    if (!component || !datasetData.length) {
      toast.error('No data available to analyze.');
      return;
    }

    setLoading(true);
    setIsExpanded(true); // Auto-expand when fetching

    try {
      const token = localStorage.getItem('token');

      const payload = {
        dataset_id: datasetId,
        chart_config: component.config,
        chart_data: datasetData.slice(0, 1500) // Send a sample to avoid payload too large
      };

      const response = await fetch('/api/charts/insights', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Failed to generate insights');
      }

      const result = await response.json();

      // The backend chart_insights_service returns a structured dict
      // Typically formatted like { summary: "...", confidence: X, raw_llm_response: "{...}" }

      let parsedInsights = null;

      // Try to parse the inner JSON if the LLM returned it as a string
      if (result.raw_llm_response) {
        try {
          const cleanedText = result.raw_llm_response.replace(/```json/g, '').replace(/```/g, '').trim();
          parsedInsights = JSON.parse(cleanedText);
        } catch (e) {
          console.warn('Could not parse raw_llm_response into JSON', e);
        }
      }

      // If parsing fails, construct a standard object from the basic response
      if (!parsedInsights) {
        parsedInsights = {
          explanation: result.summary || "Analysis complete.",
          key_insights: result.key_findings || [],
          reading_guide: result.recommendations && result.recommendations.length > 0 ? result.recommendations[0] : "Explore the data further based on these insights."
        };
      }

      setInsightData(parsedInsights);

    } catch (error) {
      console.error('Error fetching AI insights:', error);
      toast.error('Could not generate chart insights.');
      setInsightData({
        explanation: "We could not reach the AI service to analyze this chart.",
        key_insights: [],
        reading_guide: "Please try again later."
      });
    } finally {
      setLoading(false);
    }
  };

  // Ensure consistent rendering arrays
  const keyInsightsArray = Array.isArray(insightData?.key_insights) ? insightData.key_insights : [];

  return (
    <div className="mt-4 border-t border-ui-border/50 pt-4">
      {/* Action Bar */}
      <div className="flex items-center justify-between">
        {!insightData && !loading ? (
          <button
            onClick={fetchRealInsights}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 hover:text-blue-300 transition-colors border border-blue-500/20 text-sm font-medium"
          >
            <Sparkles className="w-4 h-4" />
            Generate AI Insights
          </button>
        ) : (
          <div className="w-full flex items-center justify-between">
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
            >
              <Brain className="w-4 h-4 text-blue-400" />
              AI Analysis
              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            <button
              onClick={fetchRealInsights}
              disabled={loading}
              className="text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-50"
              title="Regenerate Insights"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
            </button>
          </div>
        )}
      </div>

      <AnimatePresence>
        {isExpanded && (loading || insightData) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden mt-3"
          >
            {loading && !insightData ? (
              <div className="bg-gradient-to-br from-blue-500/5 to-purple-500/5 rounded-lg p-4 border border-blue-500/10">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="w-4 h-4 text-blue-400 animate-pulse" />
                  <span className="text-sm font-semibold text-blue-300">Analyzing data context...</span>
                </div>
                <div className="space-y-2 mt-3">
                  <div className="h-2 bg-slate-800 rounded w-3/4 animate-pulse"></div>
                  <div className="h-2 bg-slate-800 rounded w-1/2 animate-pulse"></div>
                </div>
              </div>
            ) : insightData && (
              <div className="bg-gradient-to-br from-blue-500/10 to-purple-500/5 rounded-xl p-5 border border-blue-500/20">

                {/* Core Explanation */}
                {insightData.explanation && (
                  <div className="mb-4">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Lightbulb className="w-4 h-4 text-amber-400" />
                      <h4 className="text-sm font-bold text-slate-200">The Bottom Line</h4>
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed max-w-2xl pl-6">
                      {insightData.explanation}
                    </p>
                  </div>
                )}

                {/* Key Data Points */}
                {keyInsightsArray.length > 0 && (
                  <div className="mb-4">
                    <div className="flex items-center gap-2 mb-1.5">
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                      <h4 className="text-sm font-bold text-slate-200">Supporting Data</h4>
                    </div>
                    <ul className="space-y-1.5 pl-6 max-w-2xl">
                      {keyInsightsArray.map((insight, idx) => (
                        <li key={idx} className="text-sm text-slate-300 flex items-start gap-2 leading-relaxed">
                          <span className="text-blue-500/60 font-bold mt-0.5">•</span>
                          <span>{insight}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Reading Guide / Action */}
                {insightData.reading_guide && (
                  <div className="bg-slate-800/50 rounded-lg p-3 mt-4 max-w-2xl">
                    <div className="flex items-start gap-2">
                      <Target className="w-4 h-4 text-indigo-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <h4 className="text-xs font-bold text-indigo-300 mb-0.5 uppercase tracking-wider">Takeaway Action</h4>
                        <p className="text-sm text-slate-300">{insightData.reading_guide}</p>
                      </div>
                    </div>
                  </div>
                )}

              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default IntelligentChartExplanation;
