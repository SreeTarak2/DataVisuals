import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Bot, User, Plus, Database, Copy, ChevronDown, ChevronUp, RotateCcw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { cn } from '../lib/utils';
import ReactMarkdown from 'react-markdown';
import PlotlyChart from '../components/PlotlyChart';
import ChatHistoryModal from '../components/ChatHistoryModal';
import useChatStore from '../store/chatStore';
import useDatasetStore from '../store/datasetStore';

const Chat = () => {
  const {
    getCurrentConversationMessages,
    sendMessage,
    loading,
    setCurrentConversation,
    getConversation,
    loadConversations
  } = useChatStore();
  const { selectedDataset, setSelectedDataset, datasets } = useDatasetStore();
  const [inputMessage, setInputMessage] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [expandedTechnicalDetails, setExpandedTechnicalDetails] = useState({});

  const messages = getCurrentConversationMessages();
  const isAITyping = loading;
  
  // Track message count to prevent unnecessary scrolls
  const messageCountRef = useRef(0);

  // Debug: Log messages to see their structure
  useEffect(() => {
    console.log('Current messages:', messages);
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Detect code blocks like ChatGPT
  const containsCodeBlock = (text) => {
    if (!text) return false;
    return text.includes("```") || /<pre.*?>|<code.*?>/i.test(text);
  };

  // Adjust textarea height dynamically
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${scrollHeight}px`;
    }
  }, [inputMessage]);

  // Only scroll when message count changes or AI is typing
  useEffect(() => {
    const currentCount = messages.length;
    if (currentCount !== messageCountRef.current || isAITyping) {
      scrollToBottom();
      messageCountRef.current = currentCount;
    }
  }, [messages.length, isAITyping]);

  useEffect(() => {
    const initializeChat = async () => {
      await loadConversations();
      const chatId = searchParams.get('chatId');
      if (chatId) {
        setCurrentChatId(chatId);
        const conversation = getConversation(chatId);
        if (conversation) {
          setCurrentConversation(chatId);
        } else {
          toast.error('Conversation not found');
        }
      } else {
        setCurrentChatId(null);
        setCurrentConversation(null);
      }

      const datasetId = searchParams.get('dataset');
      if (datasetId && datasets.length > 0) {
        const dataset = datasets.find(d => d.id === datasetId);
        if (dataset) {
          setSelectedDataset(dataset);
        }
      }
    };
    initializeChat();
  }, [searchParams, getConversation, setCurrentConversation, loadConversations, datasets, setSelectedDataset]);

  const handleSendMessage = async (e, messageText = null) => {
    e?.preventDefault();
    const message = messageText || inputMessage.trim();
    if (!message || isAITyping || !selectedDataset?.id) return;

    if (!messageText) {
      setInputMessage('');
    }

    const result = await sendMessage(message, selectedDataset.id, currentChatId);
    if (result && !result.success) {
      toast.error(result.error);
    }
    if (result && result.conversationId) {
      setCurrentChatId(result.conversationId);
      // Update URL with conversation ID so page refresh preserves the chat
      const newParams = new URLSearchParams(searchParams);
      newParams.set('chatId', result.conversationId);
      if (selectedDataset?.id) {
        newParams.set('dataset', selectedDataset.id);
      }
      setSearchParams(newParams, { replace: true });
    }
  };

  const handleRerunMessage = (messageContent) => {
    handleSendMessage(null, messageContent);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(e);
    }
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
    setExpandedTechnicalDetails(prev => ({ ...prev, [messageId]: !prev[messageId] }));
  };

  const highlightImportantText = useCallback((text) => {
    if (!text) return '';
    const cleanText = text.replace(/<[^>]*>/g, '');
    return cleanText
      .replace(/(\d+\.?\d*%)/g, '<span class="text-blue-400 font-semibold">$1</span>')
      .replace(/(\$\d+[,.]?\d*)/g, '<span class="text-green-400 font-semibold">$1</span>')
      .replace(/\b(correlation|trend|pattern|insight|significant|increase|decrease)\b/gi, '<span class="text-purple-400 font-medium">$1</span>')
      .replace(/(["'])([^"']+)\1/g, '<span class="text-cyan-400 font-mono text-xs">$1$2$1</span>')
      .replace(/\n/g, '<br>');
  }, []);

  if (!selectedDataset) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-6">
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="text-center">
          <Database className="w-16 h-16 text-primary mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-foreground mb-2">Select a Dataset</h2>
          <p className="text-muted-foreground">Choose a dataset to start chatting with the AI.</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background">
      <header className="p-4 border-b border-border/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bot className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-lg font-semibold text-foreground">AI Assistant</h1>
            <p className="text-xs text-muted-foreground">Chatting about: {selectedDataset.name}</p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl pt-6">
          <AnimatePresence>
            {messages.map((msg, index) => (
              <motion.div
                key={msg.id || index}
                layout
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn("flex gap-4 px-4 py-6", msg.role === 'user' ? 'justify-end' : '')}
              >
                <div className={cn("space-y-2 overflow-hidden", msg.role === 'user' ? "max-w-2xl" : "flex-1")}>
                  <div className="font-semibold text-sm text-foreground">
                    {msg.role === 'assistant' ? 'Assistant' : 'You'}
                  </div>

                  {/* PATCHED CONTENT CONTAINER */}
                  <div
                    className={cn(
                      msg.role === "user"
                        ? "max-w-2xl ml-auto rounded-2xl bg-[#1f1f22] px-4 py-2 text-white"
                        : containsCodeBlock(msg.content)
                          ? "rounded-xl bg-[#1a1a1c] px-4 py-3 text-white"
                          : "text-white leading-relaxed py-1"
                    )}
                  >
                    {msg.content ? (
                      <div className="prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown
                          components={{
                            p: ({node, ...props}) => <p className="mb-2 last:mb-0 text-white" {...props} />,
                            ul: ({node, ...props}) => <ul className="list-disc ml-4 mb-2 text-white" {...props} />,
                            ol: ({node, ...props}) => <ol className="list-decimal ml-4 mb-2 text-white" {...props} />,
                            li: ({node, ...props}) => <li className="mb-1 text-white" {...props} />,
                            code: ({node, inline, ...props}) => 
                              inline ? 
                                <code className="bg-slate-700 px-1 py-0.5 rounded text-xs text-cyan-200" {...props} /> : 
                                <code className="block bg-slate-800 p-2 rounded text-xs overflow-x-auto text-white" {...props} />,
                            strong: ({node, ...props}) => <strong className="font-bold text-blue-300" {...props} />,
                            em: ({node, ...props}) => <em className="italic text-purple-300" {...props} />,
                            h1: ({node, ...props}) => <h1 className="text-xl font-bold mb-2 text-cyan-300" {...props} />,
                            h2: ({node, ...props}) => <h2 className="text-lg font-bold mb-2 text-cyan-300" {...props} />,
                            h3: ({node, ...props}) => <h3 className="text-base font-bold mb-1 text-cyan-300" {...props} />,
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="text-red-400 text-xs">
                        [Message content missing]
                      </div>
                    )}
                  </div>


                  {msg.chart_config && (
                    <div className="mt-4 bg-slate-900/50 rounded-xl p-2 border border-slate-600/50">
                      {msg.chart_config?.data && msg.chart_config.data.length > 0 ? (
                        <PlotlyChart
                          data={msg.chart_config.data}
                          layout={{
                            // Merge backend layout with frontend styling
                            ...(msg.chart_config.layout || {}),
                            paper_bgcolor: 'rgba(0,0,0,0)',
                            plot_bgcolor: 'rgba(0,0,0,0)',
                            font: { color: '#e2e8f0' },
                            height: 400,
                            margin: { t: 50, b: 50, l: 60, r: 20 },
                          }}
                          config={{ displayModeBar: false, responsive: true }}
                        />
                      ) : (
                        <div className="h-[400px] flex items-center justify-center text-slate-400 text-xs">
                          {msg.chart_config ? 
                            `Chart data empty. Debug: ${JSON.stringify(msg.chart_config).substring(0, 100)}...` : 
                            'Chart requested but no data available'
                          }
                        </div>
                      )}
                    </div>
                  )}

                  {msg.technical_details && (
                    <div className="mt-3 pt-3 border-t border-slate-600/50">
                      <button
                        onClick={() => toggleTechnicalDetails(msg.id || index)}
                        className="flex items-center gap-2 text-xs text-slate-400 hover:text-white"
                      >
                        {expandedTechnicalDetails[msg.id || index] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        Technical Explanation
                      </button>

                      <AnimatePresence>
                        {expandedTechnicalDetails[msg.id || index] && (
                          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                            <div
                              className="mt-2 p-3 bg-slate-900/50 rounded text-xs text-slate-300 border border-slate-700"
                              dangerouslySetInnerHTML={{ __html: highlightImportantText(msg.technical_details) }}
                            />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  <div className="flex items-center justify-end gap-2 mt-2">
                    {msg.role === 'user' && (
                      <button 
                        onClick={() => handleRerunMessage(msg.content)} 
                        className="text-slate-500 hover:text-white flex items-center gap-1 text-xs"
                        title="Rerun this query"
                      >
                        <RotateCcw size={14} />
                        <span>Rerun</span>
                      </button>
                    )}
                    <button 
                      onClick={() => copyToClipboard(msg.content)} 
                      className="text-slate-500 hover:text-white"
                      title="Copy to clipboard"
                    >
                      <Copy size={14} />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isAITyping && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-4 px-4 py-6">
              <div className="space-y-2 overflow-hidden">
                <div className="font-semibold text-sm text-foreground">Assistant</div>
                <div className="flex gap-1.5 items-center">
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '200ms' }} />
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '400ms' }} />
                </div>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t border-border/50 bg-background px-4 py-4">
        <form onSubmit={handleSendMessage} className="mx-auto max-w-3xl">
          <div className="relative flex items-center gap-3 rounded-full bg-slate-800/80 border border-slate-700/50 px-3 py-2 shadow-sm">

            <button
              type="button"
              className="h-9 w-9 shrink-0 rounded-full flex items-center justify-center hover:bg-slate-700/50"
            >
              <Plus className="h-5 w-5 text-slate-400" />
            </button>

            <textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything about your data..."
              className="w-full max-h-[120px] resize-none border-0 bg-transparent px-0 py-2.5 text-white placeholder-slate-400 focus-visible:ring-0 focus-visible:ring-offset-0 overflow-y-auto"
              rows={1}
              disabled={isAITyping}
            />

            <button
              type="submit"
              disabled={!inputMessage.trim() || isAITyping}
              className={cn(
                "h-9 w-9 flex items-center justify-center shrink-0 rounded-full transition-all",
                inputMessage.trim() && !isAITyping
                  ? "bg-blue-600 text-white"
                  : "bg-slate-600 text-slate-400"
              )}
            >
              <Send size={16} />
            </button>
          </div>
        </form>
      </div>

      <ChatHistoryModal isOpen={showHistoryModal} onClose={() => setShowHistoryModal(false)} />
    </div>
  );
};

export default Chat;
