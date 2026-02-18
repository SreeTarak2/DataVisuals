import React, { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';
import { Send, Bot, User, Plus, Database, Copy, ChevronDown, ChevronUp, RotateCcw, Wifi, WifiOff, Pencil, X, Check, Sparkles, BarChart3, TrendingUp, MessageSquare, Lightbulb } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DOMPurify from 'dompurify';
import PlotlyChart from '@/components/features/charts/PlotlyChart';
import ChatHistoryModal from '@/components/features/observatory/ChatHistoryModal';
import { markdownComponents, streamingMarkdownComponents } from '@/components/features/chat/MarkdownRenderers';
import useChatStore from '@/store/chatStore';
import useDatasetStore from '@/store/datasetStore';
import useWebSocket from '@/hooks/useWebSocket';

// Memoized message component to prevent re-renders when typing
const ChatMessage = memo(({ msg, index, isUser, timestamp, editingMessageId, editContent, setEditContent, handleEditKeyDown, cancelEdit, saveEdit, startEditMessage, handleRerunMessage, copyToClipboard, toggleTechnicalDetails, expandedTechnicalDetails, highlightImportantText }) => {
  return (
    <motion.div
      key={msg.id || index}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "flex gap-3 px-4 py-4 group",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div className={cn(
        "flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center shadow-lg",
        isUser
          ? "bg-gradient-to-br from-blue-500 to-blue-600"
          : "bg-gradient-to-br from-purple-500 to-pink-500"
      )}>
        {isUser ? (
          <User className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-white" />
        )}
      </div>

      {/* Message Container */}
      <div className={cn(
        "flex flex-col",
        isUser ? "items-end max-w-[70%]" : "items-start max-w-[85%]"
      )}>
        {/* Name and Timestamp */}
        <div className={cn(
          "flex items-center gap-2 mb-1.5",
          isUser ? "flex-row-reverse" : "flex-row"
        )}>
          <span className="text-xs font-medium text-slate-300">
            {isUser ? 'You' : 'DataSage AI'}
          </span>
          {timestamp && (
            <span className="text-[10px] text-slate-500">
              {timestamp}
            </span>
          )}
          {msg.isEdited && (
            <span className="text-[10px] text-slate-500 italic">(edited)</span>
          )}
        </div>

        {/* Message Bubble */}
        <div
          className={cn(
            "relative transition-all break-words overflow-hidden",
            isUser
              ? "rounded-2xl rounded-br-md px-4 py-3 shadow-md text-white border border-slate-700/50"
              : "text-slate-200 px-1"
          )}
          style={{
            wordBreak: 'break-word',
            overflowWrap: 'anywhere',
            ...(isUser && { backgroundColor: '#212121' })
          }}
        >
          {/* Edit Mode */}
          {editingMessageId === msg.id ? (
            <div className="space-y-3 min-w-[300px]">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleEditKeyDown}
                className="w-full bg-slate-900 text-white rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 min-h-[80px] border border-slate-600"
                autoFocus
                rows={3}
              />
              <div className="flex items-center justify-end gap-2">
                <button
                  onClick={cancelEdit}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors rounded-lg hover:bg-slate-700"
                >
                  <X size={14} />
                  Cancel
                </button>
                <button
                  onClick={saveEdit}
                  className="px-4 py-1.5 text-xs bg-green-600 hover:bg-green-500 text-white rounded-lg flex items-center gap-1.5 transition-colors font-medium"
                >
                  <Check size={14} />
                  Save & Regenerate
                </button>
              </div>
            </div>
          ) : msg.content ? (
            /* Message Content */
            isUser ? (
              /* User messages - plain text, no markdown */
              <p className="text-[15px] leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </p>
            ) : (
              /* AI messages - render premium markdown */
              <div className="max-w-none [&>*:last-child]:mb-0 overflow-hidden">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {msg.content}
                </ReactMarkdown>
              </div>
            )
          ) : (
            <div className="text-red-400 text-sm italic">[Message content missing]</div>
          )}
        </div>

        {/* Chart Block - Premium container like code blocks */}
        {!isUser && msg.chart_config && (
          <div className="my-4 rounded-xl overflow-hidden border border-slate-700/60 bg-[#0d1117] shadow-lg">
            <div className="flex items-center justify-between px-4 py-2.5 bg-[#161b22] border-b border-slate-700/60">
              <div className="flex items-center gap-2">
                <BarChart3 size={14} className="text-slate-400" />
                <span className="text-xs font-medium text-slate-400 tracking-wide">
                  {msg.chart_config?.layout?.title?.text || msg.chart_config?.layout?.title || 'VISUALIZATION'}
                </span>
              </div>
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/50" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/20 border border-green-500/50" />
              </div>
            </div>
            {msg.chart_config?.data && msg.chart_config.data.length > 0 ? (
              <div className="p-3">
                <PlotlyChart
                  data={msg.chart_config.data}
                  layout={{
                    ...(msg.chart_config.layout || {}),
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(13,17,23,1)',
                    font: { color: '#94a3b8', size: 12, family: 'Inter, system-ui, sans-serif' },
                    height: 380,
                    margin: { t: 30, b: 50, l: 60, r: 20 },
                    xaxis: { ...(msg.chart_config.layout?.xaxis || {}), gridcolor: '#1e293b', zerolinecolor: '#334155' },
                    yaxis: { ...(msg.chart_config.layout?.yaxis || {}), gridcolor: '#1e293b', zerolinecolor: '#334155' },
                  }}
                  config={{ displayModeBar: false, responsive: true }}
                />
              </div>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-slate-500 text-sm">
                Chart data unavailable
              </div>
            )}
          </div>
        )}

        {/* Technical Details Expandable */}
        {!isUser && msg.technical_details && (
          <div className="mt-2 w-full">
            <button
              onClick={() => toggleTechnicalDetails(msg.id || index)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expandedTechnicalDetails[msg.id || index] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              <span>Technical Details</span>
            </button>
            <AnimatePresence>
              {expandedTechnicalDetails[msg.id || index] && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div
                    className="mt-2 p-3 bg-slate-900/50 rounded-lg text-xs text-slate-400 border border-slate-700/50"
                    dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(highlightImportantText(msg.technical_details)) }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Action Buttons - Appear on hover */}
        <div className={cn(
          "flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200",
          isUser ? "flex-row-reverse" : "flex-row"
        )}>
          {isUser && !editingMessageId && (
            <>
              <button
                onClick={() => startEditMessage(msg)}
                className="p-1.5 text-slate-500 hover:text-blue-400 hover:bg-slate-800 rounded-lg transition-all"
                title="Edit message"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => handleRerunMessage(msg.id)}
                className="p-1.5 text-slate-500 hover:text-green-400 hover:bg-slate-800 rounded-lg transition-all"
                title="Rerun this query"
              >
                <RotateCcw size={14} />
              </button>
            </>
          )}
          <button
            onClick={() => copyToClipboard(msg.content)}
            className="p-1.5 text-slate-500 hover:text-cyan-400 hover:bg-slate-800 rounded-lg transition-all"
            title="Copy to clipboard"
          >
            <Copy size={14} />
          </button>
        </div>
      </div>
    </motion.div>
  );
});

ChatMessage.displayName = 'ChatMessage';

const Chat = () => {
  const {
    getCurrentConversationMessages,
    sendMessage,
    loading,
    setCurrentConversation,
    getConversation,
    loadConversations,
    startNewConversation,
    // Streaming state
    isStreaming,
    streamingContent,
    startStreaming,
    appendStreamingToken,
    finishStreaming,
    cancelStreaming,
    currentConversationId,
    setLoading,
    editMessage,
    rerunMessage
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
  const [streamingChartConfig, setStreamingChartConfig] = useState(null);

  // Edit state
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editContent, setEditContent] = useState('');

  const messages = getCurrentConversationMessages();
  const isAITyping = loading || isStreaming;

  // Track message count to prevent unnecessary scrolls
  const messageCountRef = useRef(0);
  const pendingMessageRef = useRef(null);

  // WebSocket connection for streaming
  const { isConnected, connect, sendMessage: wsSendMessage } = useWebSocket({
    onToken: useCallback((token) => {
      appendStreamingToken(token);
      scrollToBottom();
    }, [appendStreamingToken]),

    onResponseComplete: useCallback(() => {
      // Response complete - content accumulated via onToken
    }, []),

    onChart: useCallback((chartConfig) => {
      setStreamingChartConfig(chartConfig);
    }, []),

    onDone: useCallback(({ conversationId, chartConfig }) => {

      // IMPORTANT: Set conversation ID BEFORE finishStreaming so it can add the message
      if (conversationId) {
        setCurrentChatId(conversationId);
        setCurrentConversation(conversationId);
      }

      // Finalize the streamed message
      const content = useChatStore.getState().streamingContent;
      finishStreaming(content, chartConfig || streamingChartConfig);
      setStreamingChartConfig(null);

      // Update URL params
      if (conversationId) {
        const newParams = new URLSearchParams(searchParams);
        newParams.set('chatId', conversationId);
        if (selectedDataset?.id) {
          newParams.set('dataset', selectedDataset.id);
        }
        setSearchParams(newParams, { replace: true });
      }
    }, [finishStreaming, streamingChartConfig, searchParams, selectedDataset?.id, setSearchParams, setCurrentConversation]),

    onError: useCallback((error) => {
      cancelStreaming();
      toast.error(error.detail || 'Connection error');
    }, [cancelStreaming]),

    onStatus: useCallback(() => {
      // Status updates received
    }, []),

    autoConnect: false
  });

  // Connect WebSocket when dataset is selected
  useEffect(() => {
    if (selectedDataset?.id && !isConnected) {
      connect();
    }
  }, [selectedDataset?.id, isConnected, connect]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Detect code blocks like ChatGPT
  const containsCodeBlock = (text) => {
    if (!text) return false;
    return text.includes("```") || /<pre.*?>|<code.*?>/i.test(text);
  };

  // Only scroll when message count changes (NOT when typing or AI typing state changes)
  useEffect(() => {
    const currentCount = messages.length;
    if (currentCount !== messageCountRef.current) {
      scrollToBottom();
      messageCountRef.current = currentCount;
    }
  }, [messages.length]);

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

    // Ensure we have a conversation
    let convId = currentChatId || currentConversationId;
    if (!convId) {
      convId = startNewConversation(selectedDataset.id);
      setCurrentChatId(convId);
    }

    // Add user message immediately to UI
    const userMessage = {
      id: `msg_${Date.now()}_user`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    useChatStore.setState(state => ({
      conversations: {
        ...state.conversations,
        [convId]: {
          ...state.conversations[convId],
          messages: [
            ...(state.conversations[convId]?.messages || []),
            userMessage
          ]
        }
      }
    }));

    // Try WebSocket streaming first
    if (isConnected) {
      console.log('Sending via WebSocket (streaming)');
      const msgId = `msg_${Date.now()}_ai`;
      startStreaming(msgId);

      wsSendMessage({
        message,
        datasetId: selectedDataset.id,
        conversationId: currentChatId,
        streaming: true
      });
    } else {
      // Fallback to HTTP API
      console.log('WebSocket not connected, using HTTP API');
      const result = await sendMessage(message, selectedDataset.id, currentChatId);
      if (result && !result.success) {
        toast.error(result.error);
      }
      if (result && result.conversationId) {
        setCurrentChatId(result.conversationId);
        const newParams = new URLSearchParams(searchParams);
        newParams.set('chatId', result.conversationId);
        if (selectedDataset?.id) {
          newParams.set('dataset', selectedDataset.id);
        }
        setSearchParams(newParams, { replace: true });
      }
    }
  };

  // Re-execute a query without adding a new user message (for edit/rerun)
  const reExecuteQuery = async (message, convId) => {
    if (!message || isAITyping || !selectedDataset?.id) return;

    // Try WebSocket streaming first
    if (isConnected) {
      console.log('Re-executing via WebSocket (streaming)');
      const msgId = `msg_${Date.now()}_ai`;
      startStreaming(msgId);

      wsSendMessage({
        message,
        datasetId: selectedDataset.id,
        conversationId: convId,
        streaming: true
      });
    } else {
      // Fallback to HTTP API
      console.log('WebSocket not connected, using HTTP API');
      const result = await sendMessage(message, selectedDataset.id, convId);
      if (result && !result.success) {
        toast.error(result.error);
      }
    }
  };

  const handleRerunMessage = (messageId) => {
    const result = rerunMessage(messageId, currentChatId);

    if (result?.success) {
      // Re-send the message content to get new AI response
      handleSendMessage(null, result.content);
    } else {
      toast.error('Failed to rerun message');
    }
  };

  // Edit message handlers
  const startEditMessage = (msg) => {
    setEditingMessageId(msg.id);
    setEditContent(msg.content);
  };

  const cancelEdit = () => {
    setEditingMessageId(null);
    setEditContent('');
  };

  const saveEdit = async () => {
    if (!editContent.trim() || !editingMessageId) {
      cancelEdit();
      return;
    }

    const result = editMessage(editingMessageId, editContent.trim(), currentChatId);

    if (result?.success) {
      if (result.truncatedCount > 0) {
        toast.success(`Edited message. ${result.truncatedCount} message(s) removed.`);
      }

      // Clear edit state
      cancelEdit();

      // Re-execute the edited message without adding new user message
      reExecuteQuery(result.newContent, result.conversationId);
    } else {
      toast.error('Failed to edit message');
    }
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      saveEdit();
    } else if (e.key === 'Escape') {
      cancelEdit();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(e);
      if (textareaRef.current) {
        textareaRef.current.style.height = '52px';
        textareaRef.current.classList.remove('scrolled');
      }
    }
  };

  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const minHeight = 52;
    const maxHeight = 200;

    // Store current scroll position of the chat container to prevent jumping
    const chatContainer = textarea.closest('.overflow-y-auto')?.parentElement?.querySelector('.overflow-y-auto');
    const scrollTop = chatContainer?.scrollTop;

    // Temporarily set to auto to measure, but do it without triggering reflow on the chat
    const currentHeight = textarea.style.height;
    textarea.style.height = 'auto';
    const newHeight = Math.min(maxHeight, Math.max(minHeight, textarea.scrollHeight));
    textarea.style.height = `${newHeight}px`;

    // Restore scroll position if it changed
    if (chatContainer && scrollTop !== undefined) {
      chatContainer.scrollTop = scrollTop;
    }

    if (newHeight >= maxHeight) {
      textarea.classList.add('scrolled');
    } else {
      textarea.classList.remove('scrolled');
    }
  }, []);

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

  // Generate starter suggestions based on selected dataset
  const starterSuggestions = useMemo(() => {
    if (!selectedDataset) return [];
    const name = selectedDataset.name || 'your dataset';
    return [
      { icon: TrendingUp, text: `What are the key trends in this data?`, color: 'from-blue-500/20 to-blue-600/20 border-blue-500/30' },
      { icon: BarChart3, text: `Show me a summary of the most important metrics`, color: 'from-purple-500/20 to-pink-500/20 border-purple-500/30' },
      { icon: Lightbulb, text: `What unusual patterns or outliers exist?`, color: 'from-amber-500/20 to-orange-500/20 border-amber-500/30' },
      { icon: MessageSquare, text: `Give me an executive summary of this dataset`, color: 'from-green-500/20 to-emerald-500/20 border-green-500/30' },
    ];
  }, [selectedDataset]);

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
    <div className="h-full flex flex-col bg-background relative">
      <header className="p-4 border-b border-border/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bot className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-lg font-semibold text-foreground">AI Assistant</h1>
            <div className="flex items-center gap-2">
              <p className="text-xs text-muted-foreground">Chatting about: {selectedDataset.name}</p>
              {/* WebSocket connection indicator */}
              <span className={cn(
                "flex items-center gap-1 text-xs",
                isConnected ? "text-green-400" : "text-yellow-400"
              )}>
                {isConnected ? (
                  <><Wifi className="w-3 h-3" /> Live</>
                ) : (
                  <><WifiOff className="w-3 h-3" /> Connecting...</>
                )}
              </span>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto overflow-x-hidden relative">
        <div className="mx-auto max-w-3xl pt-6 pb-28">
          {/* Starter Suggestions — shown when no messages */}
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex flex-col items-center justify-center pt-16 pb-8 px-4"
            >
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 flex items-center justify-center mb-6">
                <Sparkles className="w-8 h-8 text-purple-400" />
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">What can I help you explore?</h2>
              <p className="text-sm text-slate-400 mb-8 text-center max-w-md">
                Ask anything about <span className="text-slate-200 font-medium">{selectedDataset?.name || 'your dataset'}</span>. I can analyze trends, generate charts, find patterns, and provide insights.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
                {starterSuggestions.map((suggestion, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.08 }}
                    onClick={(e) => handleSendMessage(e, suggestion.text)}
                    className={cn(
                      "flex items-start gap-3 px-4 py-3.5 rounded-xl border text-left transition-all duration-200",
                      "bg-gradient-to-br hover:scale-[1.02] hover:shadow-lg",
                      suggestion.color
                    )}
                  >
                    <suggestion.icon size={18} className="text-slate-300 mt-0.5 flex-shrink-0" />
                    <span className="text-sm text-slate-200 leading-snug">{suggestion.text}</span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          <AnimatePresence mode="popLayout" initial={false}>
            {messages.map((msg, index) => {
              const isUser = msg.role === 'user';
              const timestamp = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

              return (
                <ChatMessage
                  key={msg.id || index}
                  msg={msg}
                  index={index}
                  isUser={isUser}
                  timestamp={timestamp}
                  editingMessageId={editingMessageId}
                  editContent={editContent}
                  setEditContent={setEditContent}
                  handleEditKeyDown={handleEditKeyDown}
                  cancelEdit={cancelEdit}
                  saveEdit={saveEdit}
                  startEditMessage={startEditMessage}
                  handleRerunMessage={handleRerunMessage}
                  copyToClipboard={copyToClipboard}
                  toggleTechnicalDetails={toggleTechnicalDetails}
                  expandedTechnicalDetails={expandedTechnicalDetails}
                  highlightImportantText={highlightImportantText}
                />
              );
            })}
          </AnimatePresence>

          {/* Streaming indicator with avatar */}
          {isAITyping && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 px-4 py-4"
            >
              {/* AI Avatar */}
              <div className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center bg-gradient-to-br from-purple-500 to-pink-500 shadow-lg">
                <Bot className="w-5 h-5 text-white" />
              </div>

              {/* Message Container */}
              <div className="flex flex-col items-start max-w-[80%]">
                <span className="text-xs font-medium text-slate-300 mb-1.5">DataSage AI</span>
                <div className="px-1 text-slate-200">
                  {isStreaming && streamingContent ? (
                    <div className="max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={streamingMarkdownComponents}
                      >
                        {streamingContent}
                      </ReactMarkdown>
                      <span className="inline-block w-1.5 h-5 bg-blue-400 rounded-sm animate-pulse ml-0.5 align-text-bottom" />
                    </div>
                  ) : (
                    <div className="flex gap-1.5 items-center py-1">
                      <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" />
                      <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area with glassmorphism effect like Grok */}
      <div
        className="absolute bottom-0 left-0 right-0 px-4 py-4 pointer-events-none"
        style={{
          background: 'linear-gradient(to top, rgba(17, 17, 17, 0.95) 0%, rgba(17, 17, 17, 0.8) 50%, transparent 100%)',
        }}
      >
        <form onSubmit={handleSendMessage} className="mx-auto max-w-3xl pointer-events-auto">
          <div
            className="relative flex items-end gap-3 rounded-3xl px-3 py-2 shadow-lg border border-slate-600/50"
            style={{
              backgroundColor: 'rgba(33, 33, 33, 0.85)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)'
            }}
          >

            <button
              type="button"
              className="h-9 w-9 shrink-0 rounded-full flex items-center justify-center hover:bg-slate-700/50 mb-1.5"
            >
              <Plus className="h-5 w-5 text-slate-400" />
            </button>

            <textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => {
                setInputMessage(e.target.value);
                adjustTextareaHeight();
              }}
              onKeyDown={handleKeyDown}
              onPaste={() => setTimeout(adjustTextareaHeight, 0)}
              onCut={() => setTimeout(adjustTextareaHeight, 100)}
              placeholder="Ask me anything about your data..."
              className="chat-textarea w-full min-h-[52px] max-h-[200px] resize-none border-0 bg-transparent px-3 py-3.5 text-white placeholder-slate-400 focus-visible:ring-0 focus-visible:ring-offset-0 transition-all duration-200 ease-out"
              style={{
                height: '52px',
                overflowY: 'auto',
                lineHeight: '1.5',
                fontSize: '0.95rem'
              }}
              rows={1}
              disabled={isAITyping}
            />

            <button
              type="submit"
              disabled={!inputMessage.trim() || isAITyping}
              className={cn(
                "h-9 w-9 flex items-center justify-center shrink-0 rounded-full transition-all mb-1.5",
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
    </div >
  );
};

export default Chat;
