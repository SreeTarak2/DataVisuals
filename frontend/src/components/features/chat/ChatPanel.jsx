import React, { useState, useRef, useEffect, useCallback, memo } from 'react';
import { Send, Sparkles, Loader2, RefreshCw, X, History, ChevronDown, ChevronUp, Copy, Check, Edit, ArrowRight, Plus, Wifi, WifiOff } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import DOMPurify from 'dompurify';
import PlotlyChart from '@/components/features/charts/PlotlyChart';
import { DonutChart, BarChart, LineChart } from '@/components/ui/charts';
import useChatStore from '@/store/chatStore';
import useDatasetStore from '@/store/datasetStore';
import useWebSocket from '@/hooks/useWebSocket';
import InsightFeedback from '@/components/features/feedback/InsightFeedback';
import ChatHistoryModal from '@/components/features/observatory/ChatHistoryModal';
import './ChatPanel.css';

/* ─── Helpers ─── */
const formatTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const msgVariants = {
    hidden: { opacity: 0, y: 8 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: 'easeOut' } },
};

/* ─── Copy button with checkmark feedback ─── */
const CopyButton = memo(({ text, size = 13 }) => {
    const [copied, setCopied] = useState(false);
    const handleCopy = () => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };
    return (
        <button onClick={handleCopy} className="chat-action-btn" title={copied ? 'Copied!' : 'Copy'}>
            {copied ? <Check size={size} className="text-ocean" /> : <Copy size={size} />}
        </button>
    );
});
CopyButton.displayName = 'CopyButton';

// =============================================================================
// ChatMessage — Enhanced with animations, avatar, timestamps
// =============================================================================
const ChatMessage = memo(({ msg, index, isUser, toggleTechnicalDetails, expandedTechnicalDetails, onRerun }) => {
    if (isUser) {
        return (
            <motion.div className="chat-message--user group" variants={msgVariants} initial="hidden" animate="visible">
                <div className="chat-user-bubble">
                    {msg.content}
                </div>
                <div className="chat-user-footer">
                    {msg.timestamp && <span className="chat-timestamp">{formatTime(msg.timestamp)}</span>}
                    <div className="chat-user-actions">
                        <button
                            onClick={() => onRerun(msg.id)}
                            className="chat-action-btn"
                            title="Rerun"
                        >
                            <RefreshCw size={12} />
                        </button>
                        <CopyButton text={msg.content} size={12} />
                    </div>
                </div>
            </motion.div>
        );
    }

    // AI message
    return (
        <motion.div className="chat-message--ai" variants={msgVariants} initial="hidden" animate="visible">
            <div className="chat-ai-row">
                {/* AI Avatar */}
                <div className="chat-ai-avatar">
                    <Sparkles size={14} />
                </div>

                <div className="chat-ai-body">
                    <div className="chat-ai-content">
                        <ReactMarkdown
                            components={{
                                pre: ({ children }) => {
                                    const text = typeof children === 'string'
                                        ? children
                                        : (children?.props?.children ?? '');
                                    return (
                                        <div className="chat-code-block">
                                            <div className="chat-code-block__header">
                                                <span className="chat-code-block__label">Code</span>
                                                <CopyButton text={String(text)} size={12} />
                                            </div>
                                            {children}
                                        </div>
                                    );
                                },
                                code: ({ children, ...props }) => <code {...props}>{children}</code>,
                                table: ({ node, ...props }) => <div className="chat-table-wrapper"><table {...props} /></div>,
                            }}
                        >
                            {msg.content}
                        </ReactMarkdown>
                    </div>

                    {/* Chart */}
                    {msg.chart_config && (
                        <div className="chat-chart">
                            <div className="chat-chart__header">
                                <span className="chat-chart__title">Visualization</span>
                            </div>
                            <div style={{ height: '350px', padding: '10px' }}>
                                {(() => {
                                    const type = msg.chart_config.type || msg.chart_config.data?.[0]?.type || 'bar';

                                    if (type === 'pie' || type === 'donut') {
                                        return <DonutChart data={msg.chart_config.data} centerLabel="Total" />;
                                    }
                                    if (type === 'bar' || type === 'histogram') {
                                        return <BarChart data={msg.chart_config.data} />;
                                    }
                                    if (type === 'line' || type === 'scatter') {
                                        return <LineChart data={msg.chart_config.data} fillArea={type === 'scatter'} />;
                                    }

                                    // Fallback for complex charts
                                    return (
                                        <PlotlyChart
                                            data={msg.chart_config.data}
                                            layout={{ ...msg.chart_config.layout, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { color: '#6C6E79' } }}
                                            config={{ displayModeBar: false, responsive: true }}
                                        />
                                    );
                                })()}
                            </div>
                        </div>
                    )}

                    {/* Technical Details */}
                    {msg.technical_details && (
                        <button onClick={() => toggleTechnicalDetails(msg.id)} className="chat-technical-btn" style={{ marginTop: '8px' }}>
                            {expandedTechnicalDetails[msg.id] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            <span>Logic</span>
                        </button>
                    )}

                    <AnimatePresence>
                        {msg.technical_details && expandedTechnicalDetails[msg.id] && (
                            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                                <div className="chat-technical-content" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(msg.technical_details) }} />
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Action buttons + timestamp */}
                    <div className="chat-ai-footer">
                        <div className="chat-ai-actions">
                            <CopyButton text={msg.content} />
                            <button onClick={() => onRerun(msg.id)} className="chat-action-btn" title="Regenerate">
                                <RefreshCw size={13} />
                            </button>
                            {/* Belief Store Feedback */}
                            <InsightFeedback
                                variant="compact"
                                insightText={msg.content?.slice(0, 500) || ''}
                            />
                        </div>
                        {msg.timestamp && <span className="chat-timestamp">{formatTime(msg.timestamp)}</span>}
                    </div>
                </div>
            </div>
        </motion.div>
    );
});

ChatMessage.displayName = 'ChatMessage';

// =============================================================================
// ChatPanel — Antigravity IDE-inspired Contextual AI Slide-out
// =============================================================================
const ChatPanel = ({ isOpen, onClose, className, chartContext, onClearChartContext, initialQuery, onClearInitialQuery }) => {
    const {
        getCurrentConversationMessages,
        sendMessage,
        loading,
        setCurrentConversation,
        startNewConversation,
        isStreaming,
        streamingContent,
        startStreaming,
        appendStreamingToken,
        finishStreaming,
        cancelStreaming,
        currentConversationId,
    } = useChatStore();

    const { selectedDataset } = useDatasetStore();
    const [inputMessage, setInputMessage] = useState('');
    const [expandedTechnicalDetails, setExpandedTechnicalDetails] = useState({});
    const [streamingChartConfig, setStreamingChartConfig] = useState(null);
    const [showHistoryModal, setShowHistoryModal] = useState(false);

    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);
    const streamingChartConfigRef = useRef(null);
    const messages = getCurrentConversationMessages();
    const isAITyping = loading || isStreaming;

    // Keep ref in sync with state so callbacks stay stable
    streamingChartConfigRef.current = streamingChartConfig;

    // WebSocket — all callbacks use refs to keep identity stable
    const { isConnected, connect, disconnect, sendMessage: wsSendMessage } = useWebSocket({
        onToken: useCallback((token) => appendStreamingToken(token), [appendStreamingToken]),
        onChart: useCallback((config) => setStreamingChartConfig(config), []),
        onDone: useCallback(({ conversationId, chartConfig }) => {
            if (conversationId) setCurrentConversation(conversationId);
            const content = useChatStore.getState().streamingContent;
            finishStreaming(content, chartConfig || streamingChartConfigRef.current);
            setStreamingChartConfig(null);
        }, [finishStreaming, setCurrentConversation]),
        onError: useCallback((err) => {
            cancelStreaming();
            toast.error("Stream error: " + (err?.detail || 'Connection error'));
        }, [cancelStreaming])
    });

    // Connect when panel opens, disconnect when it closes
    useEffect(() => {
        if (isOpen && selectedDataset?.id) {
            if (!isConnected) connect();
        }
        return () => {
            // Disconnect when panel closes or unmounts
            if (!isOpen) disconnect();
        };
    }, [isOpen, selectedDataset?.id]); // eslint-disable-line react-hooks/exhaustive-deps

    // Auto-scroll
    useEffect(() => {
        if (isOpen) {
            setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
        }
    }, [messages.length, streamingContent, isOpen]);

    // Auto-resize textarea
    useEffect(() => {
        const el = textareaRef.current;
        if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px'; }
    }, [inputMessage]);

    // ── Chart-aware smart suggestions (short, action-oriented) ──
    const chartSuggestions = chartContext ? [
        'Explain this chart',
        'Find trends & patterns',
        'Spot anomalies or outliers',
        'Suggest a better visualization',
    ] : null;

    const handleSendMessage = async (msgOverride = null) => {
        const rawMsg = msgOverride || inputMessage.trim();
        if (!rawMsg || isAITyping || !selectedDataset?.id) return;
        setInputMessage('');

        // Enrich short chip suggestions with chart context for the AI
        let msg = rawMsg;
        if (chartContext && msgOverride) {
            const ctx = `[Chart: ${chartContext.chartType} — ${chartContext.yField} (${chartContext.aggregation}) by ${chartContext.xField}]`;
            msg = `${ctx} ${rawMsg}`;
        }

        // Clear chart context after first message uses it
        if (chartContext) onClearChartContext?.();

        if (textareaRef.current) textareaRef.current.style.height = 'auto';

        let convId = currentConversationId;
        if (!convId) convId = startNewConversation(selectedDataset.id);

        useChatStore.setState(state => ({
            conversations: {
                ...state.conversations,
                [convId]: {
                    ...state.conversations[convId],
                    messages: [...(state.conversations[convId]?.messages || []), {
                        id: `msg_${Date.now()}_user`, role: 'user', content: rawMsg, timestamp: new Date().toISOString()
                    }]
                }
            }
        }));

        if (isConnected) {
            startStreaming(`msg_${Date.now()}_ai`);
            wsSendMessage({ message: msg, datasetId: selectedDataset.id, conversationId: convId, streaming: true });
        } else {
            await sendMessage(msg, selectedDataset.id, convId);
        }
    };

    // Auto-fill and submit initial queries (e.g., from Insights buttons)
    useEffect(() => {
        if (isOpen && initialQuery) {
            // Slight delay to ensure connection/animations settle
            const timer = setTimeout(() => {
                handleSendMessage(initialQuery);
                onClearInitialQuery?.();
            }, 300);
            return () => clearTimeout(timer);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, initialQuery]);

    const handleRerun = (messageId) => {
        const msg = messages.find(m => m.id === messageId);
        if (!msg) return;
        if (msg.role === 'user') {
            setInputMessage(msg.content);
            textareaRef.current?.focus();
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); }
    };

    if (!selectedDataset) return null;

    return (
        <div className={cn(
            "chat-panel",
            isOpen ? "translate-x-0" : "translate-x-full pointer-events-none",
            className
        )}>
            {/* ── Header ── */}
            <header className="chat-header">
                <div className="flex items-center gap-2">
                    <span className="chat-header-title">AI Assistant</span>
                    {/* Connection indicator */}
                    <div className={cn("chat-conn-dot", isConnected ? "chat-conn-dot--on" : "chat-conn-dot--off")}
                        title={isConnected ? 'Connected' : 'Disconnected'} />
                </div>
                <div className="flex items-center gap-0.5">
                    <button onClick={() => startNewConversation(selectedDataset.id)} className="chat-toolbar-btn" title="New Chat"><Plus size={16} /></button>
                    <button onClick={() => setShowHistoryModal(true)} className="chat-toolbar-btn" title="History"><History size={16} /></button>
                    <div className="w-px h-3.5 bg-white/[0.06] mx-1" />
                    <button onClick={onClose} className="chat-toolbar-btn" title="Close"><X size={16} /></button>
                </div>
            </header>

            {/* ── Messages ── */}
            <div className="chat-messages">
                {messages.length === 0 ? (
                    <div className="chat-empty">
                        {chartContext?.chartImage ? (
                            /* ── Chart thumbnail preview ── */
                            <div style={{ padding: '0 16px', marginBottom: 12, width: '100%' }}>
                                <div style={{
                                    borderRadius: 10, overflow: 'hidden',
                                    border: '1px solid rgba(202,210,253,0.08)',
                                    background: '#020203',
                                }}>
                                    <img
                                        src={chartContext.chartImage}
                                        alt="Chart"
                                        style={{ width: '100%', height: 'auto', display: 'block', opacity: 0.9 }}
                                    />
                                </div>
                            </div>
                        ) : (
                            <div className="chat-empty__icon">
                                <Sparkles size={22} />
                            </div>
                        )}
                        <h3 className="chat-empty__title">
                            {chartContext ? 'Ask about your chart' : 'How can I help?'}
                        </h3>
                        {!chartContext && (
                            <p className="chat-empty__subtitle">
                                Analyzing <strong>{selectedDataset.name}</strong>
                            </p>
                        )}
                        <div className="chat-suggestions">
                            {(chartSuggestions || ['Summarize dataset', 'Show outliers', 'Plot trend', 'Key drivers']).map((s) => (
                                <button key={s} onClick={() => handleSendMessage(s)} className="chat-suggestion-chip">{s}</button>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col pb-4">
                        {/* Chart context banner */}
                        {chartContext && (
                            <motion.div
                                initial={{ opacity: 0, y: -8 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="mx-4 mt-3 mb-2 rounded-lg bg-ocean/5 border border-ocean/15 overflow-hidden"
                            >
                                {/* Thumbnail */}
                                {chartContext.chartImage && (
                                    <div style={{ background: '#020203', borderBottom: '1px solid rgba(91,136,178,0.12)' }}>
                                        <img
                                            src={chartContext.chartImage}
                                            alt="Chart context"
                                            style={{ width: '100%', height: 80, objectFit: 'cover', display: 'block', opacity: 0.85 }}
                                        />
                                    </div>
                                )}
                                <div className="px-3 py-2.5 flex items-start gap-2">
                                    <Sparkles size={12} className="text-ocean flex-shrink-0 mt-0.5" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-[10px] text-pearl font-medium mb-1.5">Chart context loaded</p>
                                        <div className="flex flex-wrap gap-1.5">
                                            {chartSuggestions?.slice(0, 3).map((s, i) => (
                                                <button key={i} onClick={() => handleSendMessage(s)} className="chat-suggestion-chip text-[10px]">{s}</button>
                                            ))}
                                        </div>
                                    </div>
                                    <button onClick={onClearChartContext} className="chat-action-btn flex-shrink-0" title="Dismiss">
                                        <X size={12} />
                                    </button>
                                </div>
                            </motion.div>
                        )}
                        {messages.map((msg, i) => (
                            <React.Fragment key={msg.id || i}>
                                {i > 0 && msg.role !== messages[i - 1]?.role && (
                                    <div className="chat-separator" />
                                )}
                                <ChatMessage
                                    msg={msg}
                                    isUser={msg.role === 'user'}
                                    index={i}
                                    toggleTechnicalDetails={(id) => setExpandedTechnicalDetails(p => ({ ...p, [id]: !p[id] }))}
                                    expandedTechnicalDetails={expandedTechnicalDetails}
                                    onRerun={handleRerun}
                                />
                            </React.Fragment>
                        ))}
                        {isAITyping && (
                            <motion.div className="chat-message--ai" variants={msgVariants} initial="hidden" animate="visible">
                                <div className="chat-ai-row">
                                    <div className="chat-ai-avatar chat-ai-avatar--thinking">
                                        <Sparkles size={14} />
                                    </div>
                                    <div className="chat-ai-body">
                                        <div className="chat-ai-content">
                                            {streamingContent ? (
                                                <ReactMarkdown>{streamingContent}</ReactMarkdown>
                                            ) : (
                                                <div className="chat-thinking">
                                                    <div className="chat-typing">
                                                        <span className="chat-typing-dot" />
                                                        <span className="chat-typing-dot" />
                                                        <span className="chat-typing-dot" />
                                                    </div>
                                                    <span className="chat-thinking-label">Thinking…</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>
                )}
            </div>

            {/* ── Input ── */}
            <div className="chat-input-area">
                <div className="chat-input-wrapper">
                    <textarea
                        ref={textareaRef}
                        value={inputMessage}
                        onChange={(e) => setInputMessage(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask anything..."
                        className="chat-input"
                        rows={1}
                    />
                    <div className="chat-input-actions">
                        <span className="chat-kbd-hint">⏎</span>
                        <button
                            onClick={() => handleSendMessage()}
                            disabled={!inputMessage.trim() || isAITyping}
                            className={cn("chat-send-btn", inputMessage.trim() ? "chat-send-btn--active" : "chat-send-btn--disabled")}
                            title="Send"
                        >
                            <ArrowRight size={16} />
                        </button>
                    </div>
                </div>
            </div>

            <ChatHistoryModal isOpen={showHistoryModal} onClose={() => setShowHistoryModal(false)} currentConversationId={currentConversationId} onSelectConversation={(id) => { setCurrentConversation(id); setShowHistoryModal(false); }} />
        </div>
    );
};

export default ChatPanel;
