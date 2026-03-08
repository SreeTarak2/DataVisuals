import React, { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';
import { Send, Plus, Database, Copy, ChevronDown, ChevronUp, RotateCcw, Pencil, Sparkles, BarChart3, TrendingUp, MessageSquare, Lightbulb, History, Maximize2, X, ArrowRight, Image, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DOMPurify from 'dompurify';
import PlotlyChart from '@/components/features/charts/PlotlyChart';
import ChatHistoryModal from '@/components/features/observatory/ChatHistoryModal';
import { markdownComponents, streamingMarkdownComponents } from '@/components/features/chat/MarkdownRenderers';
import { ChatErrorDisplay, RateLimitBanner, TypingIndicator } from '@/components/features/chat/ChatErrorDisplay';
import useChatStore from '@/store/chatStore';
import useDatasetStore from '@/store/datasetStore';
import { chatAPI } from '@/services/api';
import useWebSocket from '@/hooks/useWebSocket';
import InsightFeedback from '@/components/features/feedback/InsightFeedback';
import { AiBotIcon } from '@/components/svg/icons';

const getChartTitle = (chartConfig) => (
  chartConfig?.layout?.title?.text || chartConfig?.layout?.title || 'Visualization'
);

const IconActionButton = ({ icon, label, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={label}
    title={label}
    className="group relative inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700/80 bg-black/35 text-slate-300 transition-colors hover:border-slate-500 hover:bg-slate-900 hover:text-white"
  >
    {React.createElement(icon, { size: 14 })}
    <span className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-slate-700/80 bg-[#0a0d13] px-2 py-1 text-[10px] font-medium text-slate-200 opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100">
      {label}
    </span>
  </button>
);

const getAxisTitleText = (axisTitle) => {
  if (!axisTitle) return '';
  if (typeof axisTitle === 'string') return axisTitle;
  return axisTitle?.text || '';
};

const getChartMeta = (chartConfig) => {
  const layout = chartConfig?.layout || {};
  const traces = Array.isArray(chartConfig?.data) ? chartConfig.data : [];
  const firstTrace = traces[0] || {};
  const isPieLike = firstTrace?.type === 'pie' || firstTrace?.type === 'donut';

  const existingX = getAxisTitleText(layout?.xaxis?.title);
  const existingY = getAxisTitleText(layout?.yaxis?.title);

  let xLabel = existingX;
  let yLabel = existingY;

  if (!xLabel) {
    if (isPieLike || firstTrace?.labels) xLabel = 'Category';
    else if (firstTrace?.orientation === 'h') xLabel = 'Value';
    else xLabel = 'X Axis';
  }

  if (!yLabel) {
    if (isPieLike || firstTrace?.values) yLabel = 'Value';
    else if (firstTrace?.orientation === 'h') yLabel = 'Category';
    else if (typeof firstTrace?.name === 'string' && !/^trace/i.test(firstTrace.name)) yLabel = firstTrace.name;
    else yLabel = 'Y Axis';
  }

  const pointCount = traces.reduce((count, trace) => {
    if (Array.isArray(trace?.x)) return count + trace.x.length;
    if (Array.isArray(trace?.y)) return count + trace.y.length;
    if (Array.isArray(trace?.values)) return count + trace.values.length;
    return count;
  }, 0);

  return { xLabel, yLabel, pointCount };
};

const buildChartLayout = (chartConfig, height = 380) => {
  const meta = getChartMeta(chartConfig);
  return {
  ...(chartConfig?.layout || {}),
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(6,8,13,1)',
  font: { color: '#b3c0d4', size: 12, family: 'Rubik, system-ui, sans-serif' },
  height,
  margin: { t: 30, b: 50, l: 60, r: 20 },
  xaxis: {
    ...(chartConfig?.layout?.xaxis || {}),
    title: chartConfig?.layout?.xaxis?.title || { text: meta.xLabel },
    gridcolor: '#233247',
    zerolinecolor: '#3a4b62',
    tickfont: { color: '#a8b7cc', ...(chartConfig?.layout?.xaxis?.tickfont || {}) },
    titlefont: { color: '#c8d3e0', ...(chartConfig?.layout?.xaxis?.titlefont || {}) }
  },
  yaxis: {
    ...(chartConfig?.layout?.yaxis || {}),
    title: chartConfig?.layout?.yaxis?.title || { text: meta.yLabel },
    gridcolor: '#233247',
    zerolinecolor: '#3a4b62',
    tickfont: { color: '#a8b7cc', ...(chartConfig?.layout?.yaxis?.tickfont || {}) },
    titlefont: { color: '#c8d3e0', ...(chartConfig?.layout?.yaxis?.titlefont || {}) }
  },
};
};

const withPointMarkers = (chartData = []) => {
  if (!Array.isArray(chartData)) return [];
  return chartData.map((trace) => {
    if (trace?.type !== 'scatter') return trace;
    const currentMode = trace.mode || '';
    if (currentMode.includes('markers')) return trace;
    return {
      ...trace,
      mode: currentMode.includes('lines') ? 'lines+markers' : 'markers',
      marker: {
        size: trace?.marker?.size || 7,
        ...(trace?.marker || {})
      }
    };
  });
};

const extractFollowUpSuggestions = (content = '') => {
  if (!content) return [];
  const lines = content.split('\n');
  const anchorIndex = lines.findIndex((line) => /to explore.*further|you might want to|you could also|follow.?up|next.?steps|explore this/i.test(line));
  if (anchorIndex === -1) return [];

  const suggestions = [];
  for (let i = anchorIndex + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) {
      if (suggestions.length > 0) break;
      continue;
    }
    const match = line.match(/^[-*•\d.]+\s+(.+?)$/);
    if (!match) {
      if (suggestions.length > 0) break;
      continue;
    }
    const suggestion = match[1].replace(/`/g, '').trim();
    if (suggestion) suggestions.push(suggestion);
    if (suggestions.length >= 4) break;
  }

  return suggestions;
};

const stripFollowUpSection = (content = '') => {
  if (!content) return '';

  const lines = content.split('\n');
  const anchorIndex = lines.findIndex((line) => /to explore.*further|you might want to|you could also|follow.?up|next.?steps|explore this/i.test(line));
  if (anchorIndex === -1) return content;

  let endIndex = anchorIndex + 1;
  for (let i = anchorIndex + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) {
      if (i > anchorIndex + 1) {
        endIndex = i + 1;
        break;
      }
      continue;
    }
    const isBullet = /^[-*•]\s+(.+?)$/.test(line);
    if (isBullet) {
      endIndex = i + 1;
      continue;
    }
    if (i > anchorIndex + 1) {
      break;
    }
  }

  const cleanedLines = [...lines.slice(0, anchorIndex), ...lines.slice(endIndex)];
  return cleanedLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
};

const LEGACY_SQL_DETAILS_REGEX = /<details>\s*<summary>[\s\S]*?View SQL Query[\s\S]*?<\/summary>\s*```sql\s*([\s\S]*?)```\s*<\/details>/i;

const extractLegacySqlBlock = (content = '') => {
  if (!content) return { content: '', sql: null };
  const match = content.match(LEGACY_SQL_DETAILS_REGEX);
  if (!match) return { content, sql: null };

  const cleanedContent = content
    .replace(LEGACY_SQL_DETAILS_REGEX, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return {
    content: cleanedContent,
    sql: (match[1] || '').trim() || null,
  };
};

// Memoized message component to prevent re-renders when typing
const ChatMessage = memo(({ msg, index, isUser, timestamp, editingMessageId, editContent, setEditContent, handleEditKeyDown, cancelEdit, saveEdit, startEditMessage, handleRerunMessage, copyToClipboard, toggleTechnicalDetails, expandedTechnicalDetails, highlightImportantText, onExpandChart, onCopyChart, onSuggestionClick }) => {
  if (isUser) {
    const isEditing = editingMessageId === msg.id;

    return (
      <motion.div
        key={msg.id || index}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="flex flex-col items-end px-4 py-3 group"
      >
        {/* User Message Bubble — minimal dark pill, right-aligned */}
        <div
          className={cn(
            "relative border border-slate-700/40",
            isEditing
              ? "w-full max-w-[860px] rounded-2xl"
              : "max-w-[78%] md:max-w-[76%] rounded-2xl rounded-br-sm px-4 py-3"
          )}
          style={{
            backgroundColor: isEditing ? '#161616' : '#212121',
            wordBreak: 'break-word',
            overflowWrap: 'anywhere',
          }}
        >
          {isEditing ? (
            <div className="rounded-xl bg-[#1b1b1b] p-2 shadow-[0_10px_30px_rgba(0,0,0,0.35)]">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleEditKeyDown}
                className="w-full min-h-[112px] resize-none rounded-xl bg-[#323232] px-4 py-3 text-[16px] leading-relaxed text-slate-100 shadow-inner outline-none transition-all placeholder:text-slate-500 focus:border-blue-400/80 focus:ring-2 focus:ring-blue-400/50"
                // autoFocus
                rows={3}
              />
              <div className="mt-3 flex flex-col gap-3 px-1 sm:flex-row sm:items-center sm:justify-end">
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={cancelEdit}
                    className="rounded-xl border border-slate-500/70 px-5 py-2 text-sm text-slate-200 transition-colors hover:border-slate-400 hover:bg-white/5 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={saveEdit}
                    className="rounded-xl bg-zinc-300 px-5 py-2 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-200"
                  >
                    Save
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-[16px] leading-[1.62] whitespace-pre-wrap text-slate-200">
              {msg.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-0">{children}</p>,
                    img: ({ src, alt }) => (
                      <img
                        src={src}
                        alt={alt || 'Pasted image'}
                        className="max-w-full max-h-[300px] rounded-lg mt-2 border border-slate-600/40"
                        loading="lazy"
                      />
                    ),
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : (
                <span className="text-red-400 text-sm italic">[Message content missing]</span>
              )}
            </div>
          )}
        </div>

        {/* Footer row: timestamp + action icons */}
        {!isEditing && (
          <div className="flex items-center gap-2 mt-1.5 pr-1">
            {timestamp && (
              <span className="text-text-text-xs text-slate-500 tabular-nums opacity-0 group-hover:opacity-100 transition-opacity duration-200">{timestamp}</span>
            )}
            {msg.isEdited && (
              <span className="text-[10px] text-slate-500 italic">(edited)</span>
            )}
            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              {!editingMessageId && (
                <>
                  <button
                    onClick={() => handleRerunMessage(msg.id)}
                    className="p-1 text-slate-500 hover:text-slate-300 rounded-md transition-colors"
                    title="Rerun this query"
                  >
                    <RotateCcw size={15} />
                  </button>
                  <button
                    onClick={() => startEditMessage(msg)}
                    className="p-1 text-slate-500 hover:text-slate-300 rounded-md transition-colors"
                    title="Edit message"
                  >
                    <Pencil size={15} />
                  </button>
                </>
              )}
              <button
                onClick={() => copyToClipboard(msg.content)}
                className="p-1 text-slate-500 hover:text-slate-300 rounded-md transition-colors"
                title="Copy to clipboard"
              >
                <Copy size={15} />
              </button>
            </div>
          </div>
        )}
      </motion.div>
    );
  }

  // AI Message — keep existing design
  const { content: contentWithoutLegacySql, sql: legacySql } = extractLegacySqlBlock(msg.content || '');
  const sqlText = (msg.sql || legacySql || '').trim();
  const followUpSuggestions = extractFollowUpSuggestions(contentWithoutLegacySql);
  const cleanedContent = stripFollowUpSection(contentWithoutLegacySql);

  return (
    <motion.div
      key={msg.id || index}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex gap-3 px-4 py-4 group"
    >
      {/* AI Avatar */}
      <div className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center shadow-lg bg-slate-900/80 border border-slate-700/70 text-slate-100 overflow-hidden">
        <AiBotIcon className="w-5 h-5" />
      </div>

      {/* AI Message Container */}
      <div
        className={cn(
          "flex flex-col items-start w-full",
          msg.chart_config ? "max-w-[96%] lg:max-w-[98%]" : "max-w-[85%]"
        )}
      >
        {/* Name and Timestamp */}
        {/* <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-medium text-slate-300">DataSage AI</span>
          {timestamp && (
            <span className="text-[10px] text-slate-500">{timestamp}</span>
          )}
        </div> */}

        {/* AI Message Content */}
        <div className="text-slate-200 px-1 break-words overflow-hidden text-[15px] leading-[1.72]" style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
          {cleanedContent ? (
            <div className="max-w-none [&>*:last-child]:mb-0 overflow-hidden">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {cleanedContent}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="text-red-400 text-sm italic">[Message content missing]</div>
          )}
        </div>

        {sqlText && (
          <details className="group mt-1 mb-2 w-full overflow-hidden rounded-xl border border-slate-700/60 bg-[#0d1117] shadow-lg">
            <summary className="flex list-none w-full cursor-pointer items-center justify-between px-4 py-2.5 text-left transition-colors hover:bg-slate-800/30 [&::-webkit-details-marker]:hidden">
              <div className="flex items-center gap-2">
                <Database size={14} className="text-slate-400" />
                <span className="text-xs font-medium tracking-wide text-slate-300">SQL QUERY</span>
              </div>
              <ChevronDown size={14} className="text-slate-400 group-open:hidden" />
              <ChevronUp size={14} className="hidden text-slate-400 group-open:block" />
            </summary>
            <div className="overflow-hidden border-t border-slate-700/60 px-3 py-2 bg-[#0d1117]">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {['```sql', sqlText, '```'].join('\n')}
              </ReactMarkdown>
            </div>
          </details>
        )}

        {/* Chart Block — Centered between text and suggestions */}
        {msg.chart_config && (
          <div className="my-5 w-full max-w-3xl mx-auto overflow-hidden rounded-2xl bg-gradient-to-b from-[#10141f] via-[#080b12] to-[#020304] shadow-[0_16px_36px_rgba(0,0,0,0.38)] border border-slate-700/30">
            <div className="bg-black/30 px-4 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <BarChart3 size={15} className="text-slate-300 shrink-0" />
                    <span className="text-[15px] font-semibold tracking-tight text-slate-100 truncate">
                      {getChartTitle(msg.chart_config)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <IconActionButton icon={Copy} label="Copy Chart" onClick={() => onCopyChart(msg.chart_config)} />
                  <IconActionButton icon={Maximize2} label="Expand Chart" onClick={() => onExpandChart(msg.chart_config)} />
                </div>
              </div>
            </div>
            {msg.chart_config?.data && msg.chart_config.data.length > 0 ? (
              <div className="p-2 pt-0">
                <PlotlyChart
                  data={withPointMarkers(msg.chart_config.data)}
                  layout={buildChartLayout(msg.chart_config, 460)}
                  config={{ displayModeBar: false, responsive: true }}
                />
              </div>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-slate-400 text-sm">
                Chart data unavailable
              </div>
            )}
          </div>
        )}

        {/* Technical Details Expandable */}
        {msg.technical_details && (
          <div className="mt-2 w-full">
            <button
              onClick={() => toggleTechnicalDetails(msg.id || index)}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
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
                    className="mt-2 p-3 bg-slate-900/50 rounded-lg text-xs text-slate-300 border border-slate-700/50"
                    dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(highlightImportantText(msg.technical_details)) }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* AI Action Buttons */}
        <div className="flex items-center gap-4 mt-2 opacity-80 group-hover:opacity-100 transition-opacity duration-200">
          <button
            onClick={() => copyToClipboard(msg.content)}
            className="p-0.5 text-slate-400 hover:text-blue-300 rounded-md transition-colors"
            title="Copy to clipboard"
          >
            <Copy size={18} />
          </button>
          {msg.content && <InsightFeedback variant="compact" insightText={msg.content.slice(0, 500)} />}
        </div>

        {/* Follow-up Suggestions — prominent clickable cards at the bottom */}
        {followUpSuggestions.length > 0 && (
          <div className="mt-4 w-full">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Explore further</p>
            <div className="flex flex-col gap-2">
              {followUpSuggestions.map((suggestion, suggestionIndex) => (
                <button
                  key={`${msg.id || index}-suggestion-${suggestionIndex}`}
                  type="button"
                  onClick={() => onSuggestionClick(suggestion)}
                  className="group/sugg flex items-center gap-3 w-full text-left rounded-xl border border-slate-700/50 bg-slate-900/40 px-4 py-3 text-[14px] text-slate-200 transition-all duration-200 hover:bg-slate-800/60 hover:border-slate-600/60 hover:shadow-lg"
                >
                  <Lightbulb size={15} className="text-slate-500 shrink-0 group-hover/sugg:text-amber-400 transition-colors" />
                  <span className="flex-1 leading-snug">{suggestion}</span>
                  <ArrowRight size={14} className="text-slate-600 shrink-0 group-hover/sugg:text-slate-300 group-hover/sugg:translate-x-0.5 transition-all" />
                </button>
              ))}
            </div>
          </div>
        )}
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
  const location = useLocation();

  // Handle prefilled query from insights "Investigate" button
  useEffect(() => {
    if (location.state?.prefillQuery) {
      setInputMessage(location.state.prefillQuery);
      // Clear the state so it doesn't persist on refresh
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state?.prefillQuery]);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const composerRef = useRef(null);
  // pendingConvIdRef: the local convId used when a message was sent so onDone can
  // migrate messages from the temp ID to the backend-assigned ID when they differ.
  const pendingConvIdRef = useRef(null);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [expandedTechnicalDetails, setExpandedTechnicalDetails] = useState({});
  const [streamingChartConfig, setStreamingChartConfig] = useState(null);
  const [expandedChartConfig, setExpandedChartConfig] = useState(null);
  const [composerHeight, setComposerHeight] = useState(180);

  // Image attachment state
  const [pendingImages, setPendingImages] = useState([]);  // { id, file, previewUrl, uploading, url }
  const fileInputRef = useRef(null);

  // Edit state
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editContent, setEditContent] = useState('');

  // Error and rate limit state
  const [chatError, setChatError] = useState(null);
  const [rateLimitRemaining, setRateLimitRemaining] = useState(null);
  const [showRateLimitBanner, setShowRateLimitBanner] = useState(true);

  const messages = getCurrentConversationMessages();
  const isAITyping = loading || isStreaming;

  // Track message count to prevent unnecessary scrolls
  const messageCountRef = useRef(0);
  const pendingMessageRef = useRef(null);

  // Rate limit total (matches backend MAX_WS_MESSAGES_PER_MINUTE)
  const RATE_LIMIT_TOTAL = 30;

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

    onDone: useCallback(({ conversationId, chartConfig, sql }) => {
      const localConvId = pendingConvIdRef.current;

      if (conversationId && localConvId && conversationId !== localConvId) {
        // Backend assigned a different ID (first message of a new conversation).
        // Migrate the user message(s) from the temp local conv into the backend conv
        // so user and AI messages always live in the same conversation.
        useChatStore.setState(state => {
          const tempConv = state.conversations[localConvId];
          if (!tempConv) return { currentConversationId: conversationId };
          const newConversations = { ...state.conversations };
          delete newConversations[localConvId];
          newConversations[conversationId] = { ...tempConv, id: conversationId };
          return { conversations: newConversations, currentConversationId: conversationId };
        });
        setCurrentChatId(conversationId);
      } else if (conversationId) {
        // Existing conversation — just sync both state pointers.
        setCurrentChatId(conversationId);
        setCurrentConversation(conversationId);
      }

      // Finalize the streamed message (store already has the correct currentConversationId)
      const content = useChatStore.getState().streamingContent;
      finishStreaming(content, chartConfig || streamingChartConfig, sql);
      setStreamingChartConfig(null);

      // Update URL params
      const finalConvId = conversationId || localConvId;
      if (finalConvId) {
        const newParams = new URLSearchParams(searchParams);
        newParams.set('chatId', finalConvId);
        const dsId = selectedDataset?.id || selectedDataset?._id;
        if (dsId) newParams.set('dataset', dsId);
        setSearchParams(newParams, { replace: true });
      }
    }, [finishStreaming, streamingChartConfig, searchParams, selectedDataset, setSearchParams, setCurrentConversation]),

    onError: useCallback((error) => {
      cancelStreaming();
      // Set error state for display
      setChatError(error);
      // Don't show toast for rate limit errors - we show the banner instead
      const detail = String(error?.detail || '').toLowerCase();
      if (!detail.includes('rate') && !detail.includes('limit')) {
        toast.error(error?.detail || 'Connection error');
      }
    }, [cancelStreaming]),

    onStatus: useCallback((status) => {
      // Track rate limit remaining from status updates
      if (status?.rate_limit_remaining !== undefined) {
        setRateLimitRemaining(status.rate_limit_remaining);
      }
      // Clear any previous errors when processing starts
      setChatError(null);
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

  useEffect(() => {
    if (!composerRef.current) return;

    const updateComposerHeight = () => {
      const measuredHeight = composerRef.current?.offsetHeight || 180;
      setComposerHeight(measuredHeight);
    };

    updateComposerHeight();
    const resizeObserver = new ResizeObserver(updateComposerHeight);
    resizeObserver.observe(composerRef.current);

    return () => resizeObserver.disconnect();
  }, []);

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
    let message = messageText || inputMessage.trim();
    // Issue 5: normalise id shape — backend may return either .id or ._id
    const datasetId = selectedDataset?.id || selectedDataset?._id;

    // Check if any images are still uploading
    const stillUploading = pendingImages.some(img => img.uploading);
    if (stillUploading) {
      toast.error('Please wait for images to finish uploading');
      return;
    }

    // Prepend uploaded image markdown to the message
    const uploadedImages = pendingImages.filter(img => img.url);
    if (uploadedImages.length > 0) {
      const imageMarkdown = uploadedImages.map(img => `![](${img.url})`).join('\n');
      message = message ? `${imageMarkdown}\n${message}` : imageMarkdown;
    }

    if (!message || isAITyping || !datasetId) return;

    if (!messageText) {
      setInputMessage('');
    }

    // Clear pending images and revoke blob URLs
    if (uploadedImages.length > 0) {
      pendingImages.forEach(img => {
        if (img.previewUrl) URL.revokeObjectURL(img.previewUrl);
      });
      setPendingImages([]);
    }

    // Store message for retry on failure
    pendingMessageRef.current = message;
    let convId = currentChatId || currentConversationId;
    if (!convId) {
      convId = startNewConversation(datasetId);
      setCurrentChatId(convId);
    }

    // Issue 1: record convId so onDone can migrate the conversation if the backend
    // returns a different ID (which happens on the very first message).
    pendingConvIdRef.current = convId;

    // Add user message immediately to UI exactly once (for both WS and HTTP paths)
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
        datasetId,
        // Issue 1: use convId not stale currentChatId (React state update is async)
        conversationId: convId,
        streaming: true
      });
    } else {
      // Issue 2: user message is already appended above; tell the store action to
      // skip adding it again to prevent the duplicate-message bug.
      console.log('WebSocket not connected, using HTTP API');
      const result = await sendMessage(message, datasetId, convId, { skipUserMessage: true });
      if (result && !result.success) {
        toast.error(result.error);
      }
      if (result && result.conversationId) {
        setCurrentChatId(result.conversationId);
        const newParams = new URLSearchParams(searchParams);
        newParams.set('chatId', result.conversationId);
        if (datasetId) newParams.set('dataset', datasetId);
        setSearchParams(newParams, { replace: true });
      }
    }
  };

  // Re-execute a query without adding a new user message (for edit/rerun)
  const reExecuteQuery = async (message, convId) => {
    const datasetId = selectedDataset?.id || selectedDataset?._id;
    if (!message || isAITyping || !datasetId) return;

    // Try WebSocket streaming first
    if (isConnected) {
      console.log('Re-executing via WebSocket (streaming)');
      const msgId = `msg_${Date.now()}_ai`;
      startStreaming(msgId);

      wsSendMessage({
        message,
        datasetId,
        conversationId: convId,
        streaming: true
      });
    } else {
      // Issue 2: the caller (editMessage / rerunMessage) already manages the user
      // message in the store — skip adding it again here.
      console.log('WebSocket not connected, using HTTP API');
      const result = await sendMessage(message, datasetId, convId, { skipUserMessage: true });
      if (result && !result.success) {
        toast.error(result.error);
      }
    }
  };

  const handleRerunMessage = (messageId) => {
    const result = rerunMessage(messageId, currentChatId);

    if (result?.success) {
      // Issue 2: rerunMessage already truncated the AI response and kept the user
      // message in place — use reExecuteQuery (not handleSendMessage) so we don't
      // append another copy of the user message.
      reExecuteQuery(result.content, result.conversationId || currentChatId);
    } else {
      toast.error('Failed to rerun message');
    }
  };

  const handleSuggestionClick = (suggestion) => {
    handleSendMessage(null, suggestion);
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
        textareaRef.current.style.height = '68px';
        textareaRef.current.classList.remove('scrolled');
      }
    }
  };

  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const minHeight = 68;
    const maxHeight = 380;

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

  // ── Image upload helpers ──────────────────────────────────────────────
  const uploadImage = useCallback(async (file) => {
    const id = `img_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const previewUrl = URL.createObjectURL(file);

    // Validate on client side
    if (!file.type.startsWith('image/')) {
      toast.error('Only image files are allowed');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image must be under 5 MB');
      return;
    }

    // Add with loading state
    setPendingImages(prev => [...prev, { id, file, previewUrl, uploading: true, url: null }]);

    try {
      const res = await chatAPI.uploadChatImage(file);
      const url = res.data.url;
      setPendingImages(prev =>
        prev.map(img => img.id === id ? { ...img, uploading: false, url } : img)
      );
    } catch (err) {
      toast.error('Image upload failed');
      setPendingImages(prev => prev.filter(img => img.id !== id));
      URL.revokeObjectURL(previewUrl);
    }
  }, []);

  const removePendingImage = useCallback((id) => {
    setPendingImages(prev => {
      const img = prev.find(i => i.id === id);
      if (img?.previewUrl) URL.revokeObjectURL(img.previewUrl);
      return prev.filter(i => i.id !== id);
    });
  }, []);

  const handlePaste = useCallback(async (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const imageItem = Array.from(items).find(
      (item) => item.kind === 'file' && item.type.startsWith('image/')
    );
    if (!imageItem) {
      // Normal text paste — just adjust height
      setTimeout(adjustTextareaHeight, 0);
      return;
    }

    e.preventDefault();
    const file = imageItem.getAsFile();
    if (file) uploadImage(file);
  }, [uploadImage, adjustTextareaHeight]);

  const handleFileSelect = useCallback((e) => {
    const files = Array.from(e.target.files || []);
    files.forEach(f => uploadImage(f));
    // Reset input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [uploadImage]);

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

  const openExpandedChart = (chartConfig) => {
    setExpandedChartConfig(chartConfig);
  };

  const closeExpandedChart = () => {
    setExpandedChartConfig(null);
  };

  const copyChartAsImage = async (chartConfig) => {
    let Plotly = null;
    let container = null;
    try {
      if (!chartConfig?.data?.length) {
        toast.error('Chart data unavailable');
        return;
      }

      Plotly = (await import('plotly.js-dist-min')).default;
      container = document.createElement('div');
      container.style.position = 'fixed';
      container.style.left = '-10000px';
      container.style.top = '-10000px';
      container.style.width = '1600px';
      container.style.height = '900px';
      document.body.appendChild(container);

      await Plotly.newPlot(
        container,
        chartConfig.data,
        buildChartLayout(chartConfig, 900),
        { staticPlot: true, displayModeBar: false, responsive: false }
      );

      const imageData = await Plotly.toImage(container, {
        format: 'png',
        width: 1600,
        height: 900,
        scale: 2
      });

      const response = await fetch(imageData);
      const blob = await response.blob();

      if (navigator.clipboard?.write && window.ClipboardItem) {
        await navigator.clipboard.write([new window.ClipboardItem({ [blob.type]: blob })]);
        toast.success('Chart copied as image');
      } else {
        const link = document.createElement('a');
        link.href = imageData;
        link.download = 'chart.png';
        link.click();
        toast.success('Clipboard image is not supported here. Downloaded PNG instead.');
      }
    } catch (err) {
      console.error('Failed to copy chart image', err);
      toast.error('Failed to copy chart image');
    } finally {
      if (container) {
        try {
          if (Plotly) {
            Plotly.purge(container);
          }
        } catch (cleanupError) {
          console.error('Failed to cleanup temporary chart container', cleanupError);
        }
        if (container.parentNode) {
          container.parentNode.removeChild(container);
        }
      }
    }
  };

  useEffect(() => {
    if (!expandedChartConfig) return;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        closeExpandedChart();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [expandedChartConfig]);

  const highlightImportantText = useCallback((text) => {
    if (!text) return '';
    const cleanText = text.replace(/<[^>]*>/g, '');
    return cleanText
      .replace(/(\d+\.?\d*%)/g, '<span class="text-blue-400 font-semibold">$1</span>')
      .replace(/(\$\d+[,.]?\d*)/g, '<span class="text-green-400 font-semibold">$1</span>')
      .replace(/\b(correlation|trend|pattern|insight|significant|increase|decrease)\b/gi, '<span class="text-blue-300 font-medium">$1</span>')
      .replace(/(["'])([^"']+)\1/g, '<span class="text-blue-300 font-mono text-xs">$1$2$1</span>')
      .replace(/\n/g, '<br>');
  }, []);

  // Generate starter suggestions based on selected dataset
  const starterSuggestions = useMemo(() => {
    if (!selectedDataset) return [];
    const name = selectedDataset.name || 'your dataset';
    return [
      { icon: TrendingUp, text: `What are the key trends in this data?`, color: 'from-blue-500/20 to-blue-600/20 border-blue-500/30' },
      { icon: BarChart3, text: `Show me a summary of the most important metrics`, color: 'from-blue-500/15 to-blue-700/20 border-blue-500/25' },
      { icon: Lightbulb, text: `What unusual patterns or outliers exist?`, color: 'from-blue-400/15 to-blue-600/20 border-blue-400/25' },
      { icon: MessageSquare, text: `Give me an executive summary of this dataset`, color: 'from-blue-300/10 to-blue-500/20 border-blue-300/25' },
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
      <div className="absolute top-3 right-4 z-20 flex items-center gap-2">
        <button
          onClick={() => {
            const newId = startNewConversation(selectedDataset.id);
            setCurrentChatId(newId);
            const newParams = new URLSearchParams();
            if (selectedDataset?.id) newParams.set('dataset', selectedDataset.id);
            setSearchParams(newParams, { replace: true });
          }}
          className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border/70 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          title="New Chat"
          aria-label="Start a new chat"
        >
          <Plus size={15} />
          <span className="hidden sm:inline text-sm">New Chat</span>
        </button>
        <button
          onClick={() => setShowHistoryModal(true)}
          className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border/70 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          title="Chat History"
          aria-label="Open chat history"
        >
          <History size={15} />
          <span className="hidden sm:inline text-sm">History</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto overflow-x-hidden relative">
        <div
          className="mx-auto max-w-[52rem] pt-3"
          style={{ paddingBottom: `${composerHeight + 28}px` }}
        >
          {/* Rate Limit Warning Banner */}
          {rateLimitRemaining !== null && showRateLimitBanner && (
            <RateLimitBanner
              remaining={rateLimitRemaining}
              total={RATE_LIMIT_TOTAL}
              onClose={() => setShowRateLimitBanner(false)}
            />
          )}

          {/* Error Display */}
          <AnimatePresence>
            {chatError && (
              <ChatErrorDisplay
                error={chatError}
                onRetry={() => {
                  const lastMessage = pendingMessageRef.current;
                  setChatError(null);
                  if (lastMessage) {
                    handleSendMessage(null, lastMessage);
                  }
                }}
                onDismiss={() => setChatError(null)}
              />
            )}
          </AnimatePresence>

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
                  onExpandChart={openExpandedChart}
                  onCopyChart={copyChartAsImage}
                  onSuggestionClick={handleSuggestionClick}
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
              <div className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center bg-slate-900/80 border border-slate-700/70 shadow-lg text-slate-100 overflow-hidden">
                <AiBotIcon className="w-5 h-5 animate-pulse" />
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
                    <TypingIndicator stage={loading ? 'thinking' : 'generating'} />
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
        ref={composerRef}
        className="absolute bottom-0 left-0 right-0 px-4 py-3 pointer-events-none"
        style={{
          background: 'linear-gradient(to top, rgba(10, 10, 10, 0.84) 0%, rgba(10, 10, 10, 0.62) 52%, transparent 100%)',
        }}
      >
        <form onSubmit={handleSendMessage} className="mx-auto max-w-[55rem] pointer-events-auto">
          <div
            className="relative rounded-[28px] px-3.5 py-2 shadow-xl border border-slate-600/60"
            style={{
              backgroundColor: 'rgba(38, 38, 38, 0.9)',
              boxShadow: '0 10px 24px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.06)'
            }}
          >
            {/* Thumbnail strip for pending images */}
            {pendingImages.length > 0 && (
              <div className="flex items-center gap-2 px-3 pt-2.5 pb-1 overflow-x-auto">
                {pendingImages.map((img) => (
                  <div key={img.id} className="relative shrink-0 group/thumb">
                    <img
                      src={img.previewUrl}
                      alt="Pending upload"
                      className={cn(
                        "h-16 w-16 rounded-lg object-cover border",
                        img.uploading
                          ? "border-blue-500/60 opacity-60"
                          : "border-slate-600/60"
                      )}
                    />
                    {img.uploading && (
                      <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-black/40">
                        <Loader2 size={16} className="text-blue-400 animate-spin" />
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => removePendingImage(img.id)}
                      className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-red-600 text-white flex items-center justify-center text-xs opacity-0 group-hover/thumb:opacity-100 transition-opacity shadow-lg"
                    >
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => {
                setInputMessage(e.target.value);
                adjustTextareaHeight();
              }}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              onCut={() => setTimeout(adjustTextareaHeight, 100)}
              placeholder="Ask me anything about your data..."
              className="chat-textarea w-full min-h-[60px] max-h-[340px] resize-none border-0 bg-transparent px-3 py-3.5 text-[16px] text-slate-50 placeholder-slate-300/85 focus:outline-none focus:ring-0 transition-all duration-200 ease-out"
              style={{
                height: '60px',
                overflowY: 'auto',
                lineHeight: '1.6',
                fontSize: '1rem'
              }}
              rows={1}
              disabled={isAITyping}
            />

            {/* Hidden file input for Plus button */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/gif,image/webp"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />

            <div className="flex items-center justify-between px-1 pb-1.5">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                title="Attach image"
                className="h-9 w-9 shrink-0 rounded-full flex items-center justify-center hover:bg-slate-700/50 transition-colors"
              >
                <Plus className="h-5 w-5 text-slate-400" />
              </button>

              <button
                type="submit"
                disabled={(!inputMessage.trim() && pendingImages.filter(i => i.url).length === 0) || isAITyping}
                className={cn(
                  "h-9 w-9 flex items-center justify-center shrink-0 rounded-full transition-all",
                  (inputMessage.trim() || pendingImages.filter(i => i.url).length > 0) && !isAITyping
                    ? "bg-blue-600 text-white"
                    : "bg-slate-600 text-slate-400"
                )}
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </form>
      </div>

      <ChatHistoryModal
        isOpen={showHistoryModal}
        onClose={() => setShowHistoryModal(false)}
        currentConversationId={currentChatId}
        onSelectConversation={(id) => {
          const conv = getConversation(id);
          setCurrentConversation(id);
          setCurrentChatId(id);
          setShowHistoryModal(false);

          // Issue 3: sync selectedDataset to the dataset the conversation was created with
          // so subsequent queries are grounded in the correct data, not whatever is
          // currently selected globally.
          if (conv?.datasetId) {
            const matchingDataset = datasets.find(
              d => (d.id || d._id) === conv.datasetId
            );
            if (matchingDataset) setSelectedDataset(matchingDataset);
          }

          const newParams = new URLSearchParams(searchParams);
          newParams.set('chatId', id);
          const urlDatasetId = conv?.datasetId || selectedDataset?.id || selectedDataset?._id;
          if (urlDatasetId) newParams.set('dataset', urlDatasetId);
          setSearchParams(newParams, { replace: true });
        }}
      />

      <AnimatePresence>
        {expandedChartConfig && (
          <motion.div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeExpandedChart}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.16 }}
              className="w-full max-w-6xl overflow-hidden rounded-2xl bg-gradient-to-b from-[#10141f] via-[#080b12] to-[#020304] shadow-[0_30px_80px_rgba(0,0,0,0.5)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="bg-black/35 px-3 py-2 backdrop-blur-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <BarChart3 size={14} className="text-slate-400 shrink-0" />
                      <span className="text-sm font-semibold text-slate-100 truncate">
                        {getChartTitle(expandedChartConfig)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <IconActionButton icon={Copy} label="Copy Chart" onClick={() => copyChartAsImage(expandedChartConfig)} />
                    <IconActionButton icon={X} label="Close" onClick={closeExpandedChart} />
                  </div>
                </div>
              </div>
              <div className="p-2 pt-0">
                <PlotlyChart
                  data={withPointMarkers(expandedChartConfig.data)}
                  layout={buildChartLayout(expandedChartConfig, 700)}
                  config={{ displayModeBar: true, responsive: true }}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div >
  );
};

export default Chat;
