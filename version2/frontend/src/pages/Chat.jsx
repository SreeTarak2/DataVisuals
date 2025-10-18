import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Mic, Database, Sparkles, Copy, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import GlassCard from '../components/common/GlassCard';
import PlotlyChart from '../components/PlotlyChart';
import ChatHistoryModal from '../components/ChatHistoryModal';
import useChatStore from '../store/chatStore';
import useDatasetStore from '../store/datasetStore';
import { useSearchParams } from 'react-router-dom';
import { cn } from '../lib/utils';

const Chat = () => {
  const { 
    getCurrentConversationMessages, 
    sendMessage, 
    loading, 
    error 
  } = useChatStore();
  const { selectedDataset } = useDatasetStore();
  const [inputMessage, setInputMessage] = useState('');
  const [searchParams] = useSearchParams();
  const messagesEndRef = useRef(null);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [recording, setRecording] = useState(false); // Voice stub
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [currentChatId, setCurrentChatId] = useState(null);
  
  const messages = getCurrentConversationMessages();
  const isAITyping = loading;

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

  useEffect(() => {
    scrollToBottom();
    if (messages.length > 0) setShowSuggestions(false);
  }, [messages]);

  // Initialize chat from URL params
  useEffect(() => {
    const chatId = searchParams.get('chatId');
    if (chatId) {
      setCurrentChatId(chatId);
    } else {
      setCurrentChatId(null);
    }
  }, [searchParams]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isAITyping || !selectedDataset || !selectedDataset.id) return;

    const message = inputMessage.trim();
    setInputMessage('');
    setShowSuggestions(false);

    const result = await sendMessage(message, selectedDataset.id);
    if (!result.success) toast.error(result.error);
  };

  const handleQuickReply = (reply) => {
    setInputMessage(reply);
    setShowSuggestions(false);
  };

  const handleVoice = () => {
    setRecording(!recording);
    toast(recording ? 'Stopped recording' : 'Recording... (stub)');
    // TODO: Integrate Web Speech API
  };

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard');
    } catch (err) {
      toast.error('Failed to copy');
    }
  };

  const highlightImportantText = (text) => {
    // Highlight numbers, percentages, and key terms
    return text
      .replace(/(\d+\.?\d*%)/g, '<span class="text-emerald-400 font-semibold">$1</span>')
      .replace(/(\$\d+\.?\d*)/g, '<span class="text-green-400 font-semibold">$1</span>')
      .replace(/(\d+\.?\d*)/g, '<span class="text-blue-400 font-medium">$1</span>')
      .replace(/\b(high|low|increase|decrease|trend|pattern|correlation|significant|important)\b/gi, '<span class="text-yellow-400 font-medium">$1</span>');
  };

  const quickReplies = [
    'Analyze this data',
    'Generate insights',
    'Show me a chart',
    'What are the key trends?'
  ];

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
    <div className="h-full flex flex-col bg-gradient-to-b from-background to-muted/20 p-6">
      {/* Minimal Header */}
      <div className="p-4 border-b border-border/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary" />
          <h1 className="text-xl font-semibold text-foreground">AI Assistant</h1>
        </div>
        <GlassCard className="px-3 py-1 text-sm">
          <span className="text-primary font-medium truncate max-w-40">
            {selectedDataset.name || selectedDataset.filename || 'Unnamed Dataset'}
          </span>
        </GlassCard>
      </div>

      {/* Messages Canvas */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence>
          {messages.map((msg, index) => (
            <motion.div
              key={msg.id || index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.02 }}
              className="flex justify-center"
            >
              <div className="flex gap-3 max-w-4xl w-full">
                <div className={cn(
                  "flex-1 rounded-2xl p-4 shadow-lg transition-all duration-200",
                  msg.role === 'user' 
                    ? 'text-white order-2 shadow-lg' 
                    : 'bg-slate-800/80 backdrop-blur-sm border border-slate-700/50 text-slate-100 order-1 shadow-slate-900/20'
                )}
                style={msg.role === 'user' ? { backgroundColor: '#3b4252' } : {}}
                >
                  {msg.role === 'assistant' ? (
                    <div 
                      className="text-sm leading-relaxed"
                      dangerouslySetInnerHTML={{ __html: highlightImportantText(msg.content) }}
                    />
                  ) : (
                    <p className="text-sm leading-relaxed">{msg.content}</p>
                  )}
                {msg.chart && (
                  <div className="mt-4">
                    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700/30 shadow-lg">
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
            <div className="max-w-4xl w-full">
              <div className="rounded-2xl p-4 bg-slate-800/80 backdrop-blur-sm border border-slate-700/50 shadow-slate-900/20">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-slate-400" />
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
          className="p-5"
        >
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
        </motion.div>
      )}

      {/* Fixed Input Bar - Centered */}
      <motion.div
        initial={{ y: 50 }}
        animate={{ y: 0 }}
        className="p-6 border-t border-slate-700/30 backdrop-blur-sm"
        layout
      >
        <div className="flex justify-center">
          <form onSubmit={handleSendMessage} className="w-full max-w-4xl">
            <div className="relative">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Ask AI about your data..."
                className="w-full px-8 py-5 pr-24 rounded-2xl bg-slate-800/80 backdrop-blur-sm border border-slate-700/50 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all text-lg shadow-lg"
              disabled={isAITyping}
                aria-label="Message input"
              />
              
              {/* Mic and Send buttons inside the input */}
              <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-3">
                <motion.button
                  whileTap={{ scale: 0.95 }}
                  type="button"
                  onClick={handleVoice}
                  className="p-2.5 text-muted-foreground hover:text-primary focus-visible-ring rounded-full transition-colors"
                  disabled={isAITyping}
                  aria-label={recording ? 'Stop recording' : 'Start voice input'}
                >
                  <Mic className={cn('w-5 h-5', recording && 'text-primary animate-pulse')} />
                </motion.button>
                
                <motion.button
                  whileTap={{ scale: 0.95 }}
              type="submit"
              disabled={!inputMessage.trim() || isAITyping}
                  className="p-2.5 rounded-full text-white hover:bg-slate-600 transition-all disabled:opacity-50 shadow-lg focus-visible-ring"
                  style={{ backgroundColor: '#3b4252' }}
                  aria-label="Send message"
                >
                  <Send className="w-5 h-5" />
                </motion.button>
              </div>
            </div>
          </form>
        </div>
      </motion.div>

      {/* Chat History Modal */}
      <ChatHistoryModal 
        isOpen={showHistoryModal} 
        onClose={() => setShowHistoryModal(false)} 
      />
    </div>
  );
};

export default Chat;