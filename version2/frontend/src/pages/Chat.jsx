import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Mic, Database, Sparkles, Copy, Trash2, ChevronDown, ChevronUp, BarChart3 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import GlassCard from '../components/common/GlassCard';
import PlotlyChart from '../components/PlotlyChart';
import ChatHistoryModal from '../components/ChatHistoryModal';
import InsightCard from '../components/InsightCard';
import InteractiveKeyword from '../components/InteractiveKeyword';
import useChatStore from '../store/chatStore';
import useDatasetStore from '../store/datasetStore';
import { useSearchParams } from 'react-router-dom';
import { cn } from '../lib/utils';

const Chat = () => {
  const { 
    getCurrentConversationMessages, 
    sendMessage, 
    loading, 
    error,
    setCurrentConversation,
    getConversation,
    loadConversations
  } = useChatStore();
  const { selectedDataset } = useDatasetStore();
  const [inputMessage, setInputMessage] = useState('');
  const [searchParams] = useSearchParams();
  const messagesEndRef = useRef(null);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [recording, setRecording] = useState(false); // Voice stub
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [expandedTechnicalDetails, setExpandedTechnicalDetails] = useState({});
  
  const messages = getCurrentConversationMessages();
  const isAITyping = loading;

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

  useEffect(() => {
    scrollToBottom();
    if (messages.length > 0) setShowSuggestions(false);
  }, [messages]);

  // Load conversations and initialize chat from URL params
  useEffect(() => {
    const initializeChat = async () => {
      // First, load all conversations from the database
      await loadConversations();
      
    const chatId = searchParams.get('chatId');
    if (chatId) {
      setCurrentChatId(chatId);
        // Load the conversation from the store
        const conversation = getConversation(chatId);
        if (conversation) {
          setCurrentConversation(chatId);
        } else {
          toast.error('Conversation not found');
      }
    } else {
      setCurrentChatId(null);
    }
    };
    
    initializeChat();
  }, [searchParams, getConversation, setCurrentConversation, loadConversations]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isAITyping || !selectedDataset || !selectedDataset.id) return;

    const message = inputMessage.trim();
    setInputMessage('');
    setShowSuggestions(false);

    // Use currentChatId if available, otherwise let sendMessage create a new conversation
    const result = await sendMessage(message, selectedDataset.id, currentChatId);
    if (!result.success) toast.error(result.error);
  };

  const handleQuickReply = (reply) => {
    setInputMessage(reply);
    setShowSuggestions(false);
  };

  const handleVoice = () => {
    setRecording(!recording);
    toast(recording ? 'Stopped recording' : 'Recording... (stub)');
  };

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard');
    } catch (err) {
      toast.error('Failed to copy');
    }
  };

  const toggleTechnicalDetails = (messageId) => {
    setExpandedTechnicalDetails(prev => ({
      ...prev,
      [messageId]: !prev[messageId]
    }));
  };

  const parseInsightsFromMessage = (message) => {
    // Parse insights from AI response
    const insights = [];
    const content = message.content || '';
    
    // Look for patterns that indicate insights
    const insightPatterns = [
      {
        pattern: /Region ['"]([^'"]+)['"] shows a (remarkable|significant|notable) (increase|decrease|change) in ([^.]*)/gi,
        type: 'trend',
        extract: (match) => ({
          title: `${match[1]} Performance Trend`,
          description: `Region ${match[1]} shows a ${match[2]} ${match[3]} in ${match[4]}`,
          metrics: [{ label: 'Region', value: match[1] }]
        })
      },
      {
        pattern: /correlation between ([^.]*) and ([^.]*)/gi,
        type: 'correlation',
        extract: (match) => ({
          title: 'Variable Correlation',
          description: `Strong correlation found between ${match[1]} and ${match[2]}`,
          metrics: [{ label: 'Variables', value: `${match[1]} ↔ ${match[2]}` }]
        })
      },
      {
        pattern: /(\d+\.?\d*%) (increase|decrease) in ([^.]*)/gi,
        type: 'performance',
        extract: (match) => ({
          title: 'Performance Change',
          description: `${match[1]} ${match[2]} in ${match[3]}`,
          metrics: [{ label: 'Change', value: match[1] }]
        })
      }
    ];

    insightPatterns.forEach(({ pattern, type, extract }) => {
      let match;
      while ((match = pattern.exec(content)) !== null) {
        insights.push({
          id: `insight-${insights.length}`,
          type,
          confidence: 'High',
          ...extract(match)
        });
      }
    });

    return insights;
  };

  const handleInsightVisualize = async (insight) => {
    try {
      // Generate chart based on insight type
      const chartConfig = {
        type: insight.type,
        title: insight.title,
        description: insight.description,
        chartType: getChartTypeForInsight(insight.type),
        datasetName: selectedDataset?.name || 'Current Dataset'
      };

      // For now, create a mock chart data
      // In a real implementation, this would call the backend to generate the actual chart
      const mockChartData = generateMockChartData(insight.type);
      
      setActiveVisualization({
        ...chartConfig,
        chartData: mockChartData
      });

      toast.success('Visualization generated');
    } catch (error) {
      toast.error('Failed to generate visualization');
    }
  };

  const getChartTypeForInsight = (type) => {
    switch (type) {
      case 'trend': return 'line';
      case 'correlation': return 'scatter';
      case 'performance': return 'bar';
      default: return 'bar';
    }
  };

  const generateMockChartData = (type) => {
    // Mock data for demonstration
    const baseData = {
      data: [],
      layout: {
        title: '',
        xaxis: { title: '' },
        yaxis: { title: '' }
      }
    };

    switch (type) {
      case 'trend':
        return {
          ...baseData,
          data: [{
            x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            y: [100, 120, 140, 160, 180, 200],
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Sales Trend',
            line: { color: '#10b981' }
          }],
          layout: {
            ...baseData.layout,
            title: 'Sales Trend Over Time',
            xaxis: { title: 'Month' },
            yaxis: { title: 'Sales ($)' }
          }
        };
      case 'correlation':
        return {
          ...baseData,
          data: [{
            x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            y: [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            type: 'scatter',
            mode: 'markers',
            name: 'Correlation',
            marker: { color: '#3b82f6' }
          }],
          layout: {
            ...baseData.layout,
            title: 'Variable Correlation',
            xaxis: { title: 'Variable A' },
            yaxis: { title: 'Variable B' }
          }
        };
      default:
        return {
          ...baseData,
          data: [{
            x: ['A', 'B', 'C', 'D'],
            y: [20, 30, 25, 35],
            type: 'bar',
            name: 'Performance',
            marker: { color: '#8b5cf6' }
          }],
          layout: {
            ...baseData.layout,
            title: 'Performance Metrics',
            xaxis: { title: 'Category' },
            yaxis: { title: 'Value' }
          }
        };
    }
  };

  const handleKeywordVisualize = (keyword, type) => {
    // Handle keyword-based visualization
    const insight = {
      id: `keyword-${Date.now()}`,
      type: type || 'default',
      title: `Analysis: ${keyword}`,
      description: `Detailed analysis of ${keyword} in your dataset`,
      confidence: 'Medium'
    };
    
    handleInsightVisualize(insight);
  };

  const renderInteractiveText = (text) => {
    // Convert text to interactive elements
    return text
      .replace(/(\d+\.?\d*%)/g, (match) => 
        `<InteractiveKeyword type="percentage" onVisualize={handleKeywordVisualize}>${match}</InteractiveKeyword>`
      )
      .replace(/(\$\d+\.?\d*)/g, (match) => 
        `<InteractiveKeyword type="currency" onVisualize={handleKeywordVisualize}>${match}</InteractiveKeyword>`
      )
      .replace(/\b(correlation|trend|pattern|performance)\b/gi, (match) => 
        `<InteractiveKeyword type="${match.toLowerCase()}" onVisualize={handleKeywordVisualize} definition="Statistical relationship or pattern in the data">${match}</InteractiveKeyword>`
      );
  };

  const quickReplies = [
    'Analyze this data',
    'Generate insights',
    'Show me a chart',
    'What are the key trends?'
  ];

  // Function to highlight important text in AI responses
  const highlightImportantText = (text) => {
    if (!text) return '';
    
    // First, clean any existing HTML markup to prevent double-encoding
    const cleanText = text.replace(/<[^>]*>/g, '');
    
    return cleanText
      // Highlight percentages
      .replace(/(\d+\.?\d*%)/g, '<span class="text-blue-400 font-semibold">$1</span>')
      // Highlight currency values
      .replace(/(\$\d+\.?\d*)/g, '<span class="text-green-400 font-semibold">$1</span>')
      // Highlight numbers
      .replace(/(\b\d+\.?\d*\b)/g, '<span class="text-yellow-400 font-medium">$1</span>')
      // Highlight key terms
      .replace(/\b(correlation|trend|pattern|insight|significant|increase|decrease|growth|decline)\b/gi, '<span class="text-purple-400 font-medium">$1</span>')
      // Highlight column names (words in quotes or with underscores)
      .replace(/(["'])([^"']+)\1/g, '<span class="text-cyan-400 font-mono text-xs">$1$2$1</span>')
      .replace(/(\b\w+_\w+\b)/g, '<span class="text-cyan-400 font-mono text-xs">$1</span>')
      // Convert line breaks to HTML
      .replace(/\n/g, '<br>');
  };

  if (!selectedDataset) {
    return (
      <div className="h-full flex items-center justify-center glass-effect p-6">
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
          <Sparkles className="w-16 h-16 text-primary mb-4" />
          <h2 className="text-2xl font-bold text-foreground mb-2">Select a Dataset</h2>
          <p className="text-muted-foreground mb-6">Choose a dataset to start chatting with AI.</p>
          <button 
            onClick={() => window.location.href = '/datasets'}
            className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 focus-visible-ring"
          >
            Upload Dataset
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gradient-to-b from-background to-muted/20">
      {/* Minimal Header */}
      <div className="p-4 border-b border-border/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-primary" />
          <div>
            <h1 className="text-xl font-semibold text-foreground">AI Assistant</h1>
            {currentChatId && (
              <p className="text-xs text-muted-foreground">Chat from history</p>
            )}
          </div>
        </div>
        <GlassCard className="px-3 py-1 text-sm">
          <span className="text-primary font-medium truncate max-w-40">
            {selectedDataset.name || selectedDataset.filename || 'Unnamed Dataset'}
          </span>
        </GlassCard>
      </div>

      {/* Centered Single Column Layout */}
      <div className="flex-1 flex justify-center overflow-hidden">
        <div className="w-full max-w-4xl flex flex-col overflow-hidden">
      {/* Messages Canvas */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence>
          {messages.map((msg, index) => (
            <motion.div
              key={msg.id || index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.02 }}
              className={cn(
                "flex",
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              <div className="flex gap-3 max-w-2xl w-auto">
              <div className={cn(
                  "flex-1 rounded-3xl p-4 shadow-lg transition-all duration-200",
                msg.role === 'user' 
                    ? 'text-white order-2 shadow-lg' 
                    : 'bg-slate-800/80 backdrop-blur-sm border border-slate-700/50 text-slate-100 order-1 shadow-slate-900/20'
                )}
                style={msg.role === 'user' ? { backgroundColor: '#3b4252' } : {}}
                >
                  {msg.role === 'assistant' ? (
                    <div className="text-sm leading-relaxed">
                      {/* Simple Summary (Default) */}
                      <div 
                        dangerouslySetInnerHTML={{ __html: highlightImportantText(msg.content) }}
                      />
                      
                      {/* Insight Cards */}
                      {(() => {
                        const messageInsights = parseInsightsFromMessage(msg);
                        if (messageInsights.length > 0) {
                          return (
                            <div className="mt-4 space-y-3">
                              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                                Key Insights
                              </h4>
                              <div className="grid gap-3">
                                {messageInsights.map((insight, insightIndex) => (
                                  <InsightCard
                                    key={insight.id}
                                    insight={insight}
                                    index={insightIndex}
                                    onVisualize={handleInsightVisualize}
                                    onExplore={(insight) => {
                                      // Handle explore action
                                      toast.info(`Exploring: ${insight.title}`);
                                    }}
                                  />
                                ))}
                              </div>
                            </div>
                          );
                        }
                        return null;
                      })()}
                      
                      {/* Technical Details Toggle */}
                      {msg.technical_details && msg.technical_details !== msg.content && (
                        <div className="mt-3 pt-3 border-t border-slate-600/30">
                          <motion.button
                            whileTap={{ scale: 0.98 }}
                            onClick={() => toggleTechnicalDetails(msg.id || index)}
                            className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-300 transition-colors"
                          >
                            {expandedTechnicalDetails[msg.id || index] ? (
                              <>
                                <ChevronUp className="w-3 h-3" />
                                Hide technical explanation
                              </>
                            ) : (
                              <>
                                <ChevronDown className="w-3 h-3" />
                                Show technical explanation
                              </>
                            )}
                          </motion.button>
                          
                          {/* Technical Details (Expandable) */}
                          <AnimatePresence>
                            {expandedTechnicalDetails[msg.id || index] && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                transition={{ duration: 0.2 }}
                                className="mt-3 overflow-hidden"
                              >
                                <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/30">
                                  <div className="text-xs text-slate-400 mb-2 font-medium">Technical Analysis:</div>
                                  <div 
                                    className="text-xs leading-relaxed text-slate-300"
                                    dangerouslySetInnerHTML={{ __html: highlightImportantText(msg.technical_details) }}
                                  />
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      )}
                    </div>
                  ) : (
                <p className="text-sm leading-relaxed">{msg.content}</p>
                  )}
                {msg.chart && (
                  <div className="mt-4">
                    <div className="bg-slate-900/50 rounded-3xl p-4 border border-slate-700/30 shadow-lg">
                      {msg.chart.data ? (
                        <div className="relative">
                        <PlotlyChart 
                          data={msg.chart.data} 
                            layout={{
                              ...msg.chart.layout,
                              paper_bgcolor: 'rgba(0,0,0,0)',
                              plot_bgcolor: 'rgba(0,0,0,0)',
                              font: {
                                color: '#e2e8f0',
                                family: 'Inter, system-ui, sans-serif'
                              },
                              xaxis: {
                                ...msg.chart.layout?.xaxis,
                                gridcolor: 'rgba(148, 163, 184, 0.1)',
                                linecolor: 'rgba(148, 163, 184, 0.3)',
                                tickcolor: 'rgba(148, 163, 184, 0.3)'
                              },
                              yaxis: {
                                ...msg.chart.layout?.yaxis,
                                gridcolor: 'rgba(148, 163, 184, 0.1)',
                                linecolor: 'rgba(148, 163, 184, 0.3)',
                                tickcolor: 'rgba(148, 163, 184, 0.3)'
                              }
                            }}
                            config={{
                              displayModeBar: false,
                              responsive: true
                            }}
                            style={{ 
                              height: '300px',
                              width: '100%',
                              borderRadius: '8px'
                            }}
                          />
                          <div className="absolute top-2 right-2 bg-slate-800/80 backdrop-blur-sm rounded-lg px-2 py-1">
                            <div className="flex items-center gap-1 text-xs text-slate-300">
                              <Database className="w-3 h-3" />
                              <span>{msg.chart.chart_type || msg.chart.type || 'Chart'}</span>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-center h-40 text-slate-400">
                          <div className="text-center">
                            <Database className="w-10 h-10 mx-auto mb-3 opacity-50" />
                            <p className="text-sm font-medium">Chart data not available</p>
                            <p className="text-xs mt-1 opacity-75">Unable to render visualization</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between mt-2">
                  <p className="text-xs opacity-75">
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
                  <div className="flex gap-2">
                    <motion.button
                      whileTap={{ scale: 0.95 }}
                      onClick={() => copyToClipboard(msg.content)}
                      className="p-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                      title="Copy message"
                    >
                      <Copy className="w-3 h-3" />
                    </motion.button>
                    {msg.role === 'assistant' && (
                    <motion.button
                      whileTap={{ scale: 0.95 }}
                      onClick={() => {
                        // Stub: Clear this response
                        toast('Response cleared');
                      }}
                        className="p-1 text-xs text-muted-foreground hover:text-destructive transition-colors"
                        title="Delete message"
                    >
                      <Trash2 className="w-3 h-3" />
                    </motion.button>
                    )}
                  </div>
                </div>
              </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {isAITyping && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-center"
          >
            <div className="max-w-2xl w-full">
              <div className="rounded-2xl p-4 bg-slate-800/80 backdrop-blur-sm border border-slate-700/50 shadow-slate-900/20">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    {/* <MessageSquare className="w-4 h-4 text-slate-400" /> */}
                    <span className="text-sm text-slate-300 font-medium">AI is typing</span>
            </div>
                <div className="flex gap-1 ml-2">
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '200ms' }} />
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '400ms' }} />
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

      {/* Suggestions (if empty) */}
      {showSuggestions && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="p-5 flex justify-center"
        >
          <div className="w-full max-w-2xl">
          <h3 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            Quick starts:
          </h3>
          <div className="flex flex-wrap gap-2">
            {quickReplies.map((reply, i) => (
              <motion.button
                key={reply}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.1 }}
                onClick={() => handleQuickReply(reply)}
                className="px-3 py-2 rounded-full text-xs bg-primary/20 text-primary-white hover:bg-primary/30 transition-all"
              >
                {reply}
              </motion.button>
            ))}
          </div>
          </div>
        </motion.div>
      )}

          {/* Fixed Input Bar - Centered */}
      <motion.div
        initial={{ y: 50 }}
        animate={{ y: 0 }}
            className="p-4 border-t border-slate-700/30 backdrop-blur-sm flex justify-center"
        layout
      >
        <div className="w-full max-w-2xl">
            <form onSubmit={handleSendMessage} className="w-full">
            <div className="relative">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Ask AI about your data..."
                  className="w-full px-6 py-4 pr-20 rounded-lg bg-slate-800/80 backdrop-blur-sm border border-slate-700/50 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all shadow-lg"
                disabled={isAITyping}
                aria-label="Message input"
              />
              
              {/* Mic and Send buttons inside the input */}
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
                <motion.button
                  whileTap={{ scale: 0.95 }}
                  type="button"
                  onClick={handleVoice}
                    className="p-2 text-muted-foreground hover:text-primary focus-visible-ring rounded-full transition-colors"
                  disabled={isAITyping}
                  aria-label={recording ? 'Stop recording' : 'Start voice input'}
                >
                    <Mic className={cn('w-4 h-4', recording && 'text-primary animate-pulse')} />
                </motion.button>
                
                <motion.button
                  whileTap={{ scale: 0.95 }}
                  type="submit"
                  disabled={!inputMessage.trim() || isAITyping}
                    className="p-2 rounded-full text-white hover:bg-slate-600 transition-all disabled:opacity-50 shadow-lg focus-visible-ring"
                  style={{ backgroundColor: '#3b4252' }}
                  aria-label="Send message"
                >
                    <Send className="w-4 h-4" />
                </motion.button>
              </div>
            </div>
          </form>
        </div>
          </motion.div>
        </div>
      </div>

      {/* Chat History Modal */}
      <ChatHistoryModal 
        isOpen={showHistoryModal} 
        onClose={() => setShowHistoryModal(false)} 
      />
    </div>
  );
};

export default Chat;