import React, { useState, useEffect } from 'react';
import { Brain, Sparkles, TrendingUp, AlertTriangle, CheckCircle, Lightbulb } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import useDatasetStore from '../../store/datasetStore';

const AiInsightsCard = ({ datasetId }) => {
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);

  // Icon mapping for insights
  const iconMap = {
    TrendingUp,
    AlertTriangle,
    CheckCircle,
    Lightbulb
  };

  useEffect(() => {
    const loadInsights = async () => {
      if (!datasetId) {
        setLoading(false);
        return;
      }

      try {
        const token = localStorage.getItem('datasage-token');
        const response = await fetch(`/api/dashboard/${datasetId}/insights`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
          const data = await response.json();
          setInsights(data.insights || []);
        } else {
          setInsights([]);
        }
      } catch (error) {
        console.error('Failed to load insights:', error);
        setInsights([]);
      } finally {
        setLoading(false);
      }
    };

    loadInsights();
  }, [datasetId]);

  if (loading) {
    return (
      <GlassCard className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <h2 className="text-xl font-bold text-white">AI Insights</h2>
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="animate-pulse">
              <div className="h-4 bg-white/10 rounded w-3/4 mb-2"></div>
              <div className="h-3 bg-white/5 rounded w-full"></div>
            </div>
          ))}
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
          <Brain className="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">AI Insights</h2>
          <p className="text-sm text-slate-400">Powered by advanced analytics</p>
        </div>
        <div className="ml-auto">
          <div className="flex items-center gap-1 text-blue-400">
            <Sparkles className="w-4 h-4" />
            <span className="text-sm font-medium">Live</span>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {insights.length > 0 ? (
          insights.map((insight) => {
            const IconComponent = iconMap[insight.icon] || Brain;
            return (
              <div
                key={insight.id}
                className={`p-4 rounded-lg border ${insight.bgColor} ${insight.borderColor} transition-all hover:scale-[1.02]`}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-8 h-8 rounded-lg ${insight.bgColor} flex items-center justify-center flex-shrink-0`}>
                    <IconComponent className={`w-4 h-4 ${insight.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-white text-sm">{insight.title}</h3>
                      <span className={`text-xs px-2 py-1 rounded-full ${insight.bgColor} ${insight.color}`}>
                        {insight.confidence}%
                      </span>
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed">
                      {insight.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="text-center py-8 text-slate-400">
            <Brain className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No insights available</p>
          </div>
        )}
      </div>

      <div className="mt-6 pt-4 border-t border-white/10">
        <button className="w-full py-2 px-4 rounded-lg bg-gradient-to-r from-blue-500/20 to-cyan-500/20 border border-blue-500/30 text-blue-300 text-sm font-medium hover:from-blue-500/30 hover:to-cyan-500/30 transition-all">
          View All Insights
        </button>
      </div>
    </GlassCard>
  );
};

export default AiInsightsCard;