import React, { useState, useRef, useEffect, useCallback, memo } from 'react';
import { Send, Sparkles, Loader2, RefreshCw, X, History, ChevronDown, ChevronUp, Copy, Edit, ArrowRight, Plus } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import DOMPurify from 'dompurify';
import PlotlyChart from '@/components/features/charts/PlotlyChart';
import useChatStore from '@/store/chatStore';
import useDatasetStore from '@/store/datasetStore';
import useWebSocket from '@/hooks/useWebSocket';
import ChatHistoryModal from '@/components/features/observatory/ChatHistoryModal';
import './ChatPanel.css';

// =============================================================================
// ChatMessage — Antigravity IDE-inspired
// =============================================================================
const ChatMessage = memo(({ msg, index, isUser, toggleTechnicalDetails, expandedTechnicalDetails, copyToClipboard, onRerun }) => {
    if (isUser) {
        return (
            <div className="chat-message--user">
                <div className="chat-user-bubble">
                    {msg.content}
                    <button
                        onClick={() => onRerun(msg.id)}
                        className="chat-user-rerun"
                        title="Edit & Rerun"
                    >
                        <RefreshCw size={12} />
                    </button>
                </div>
            </div>
        );
    }

    // AI message
    return (
        <div className="chat-message--ai">
            <div className="chat-ai-content">
                <ReactMarkdown
                    components={{
                        code: ({ node, inline, ...props }) =>
                            inline
                                ? <code {...props} />
                                : <div className="chat-code-block">
                                    <div className="chat-code-block__header">
                                        <span className="chat-code-block__label">Code</span>
                                        <button className="chat-action-btn" onClick={() => copyToClipboard(props.children)} title="Copy"><Copy size={12} /></button>
                                    </div>
                                    <code {...props} />
                                </div>,
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
                        <PlotlyChart
                            data={msg.chart_config.data}
                            layout={{ ...msg.chart_config.layout, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { color: '#94a3b8' } }}
                            config={{ displayModeBar: false, responsive: true }}
                        />
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

            {/* Action buttons */}
            <div className="chat-ai-actions">
                <button onClick={() => copyToClipboard(msg.content)} className="chat-action-btn" title="Copy">
                    <Copy size={13} />
                </button>
                <button onClick={() => onRerun(msg.id)} className="chat-action-btn" title="Regenerate">
                    <RefreshCw size={13} />
                </button>
            </div>
        </div>
    );
});

ChatMessage.displayName = 'ChatMessage';

// =============================================================================
// ChatPanel — Antigravity IDE-inspired
// =============================================================================
const ChatPanel = ({ isOpen, onClose, className }) => {
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
    const messages = getCurrentConversationMessages();
    const isAITyping = loading || isStreaming;

    // WebSocket
    const { isConnected, connect, sendMessage: wsSendMessage } = useWebSocket({
        onToken: useCallback((token) => appendStreamingToken(token), [appendStreamingToken]),
        onChart: useCallback((config) => setStreamingChartConfig(config), []),
        onDone: useCallback(({ conversationId, chartConfig }) => {
            if (conversationId) setCurrentConversation(conversationId);
            const content = useChatStore.getState().streamingContent;
            finishStreaming(content, chartConfig || streamingChartConfig);
            setStreamingChartConfig(null);
        }, [finishStreaming, streamingChartConfig, setCurrentConversation]),
        onError: useCallback((err) => {
            cancelStreaming();
            toast.error("Stream error: " + err.detail);
        }, [cancelStreaming])
    });

    useEffect(() => { if (isOpen && selectedDataset?.id && !isConnected) connect(); }, [isOpen, selectedDataset?.id, isConnected, connect]);

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

    const handleSendMessage = async (msgOverride = null) => {
        const msg = msgOverride || inputMessage.trim();
        if (!msg || isAITyping || !selectedDataset?.id) return;
        setInputMessage('');

        if (textareaRef.current) textareaRef.current.style.height = 'auto';

        let convId = currentConversationId;
        if (!convId) convId = startNewConversation(selectedDataset.id);

        useChatStore.setState(state => ({
            conversations: {
                ...state.conversations,
                [convId]: {
                    ...state.conversations[convId],
                    messages: [...(state.conversations[convId]?.messages || []), {
                        id: `msg_${Date.now()}_user`, role: 'user', content: msg, timestamp: new Date().toISOString()
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
                <span className="chat-header-title">AI Assistant</span>
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
                        <div className="chat-empty__icon">
                            <Sparkles size={22} />
                        </div>
                        <h3 className="chat-empty__title">How can I help?</h3>
                        <p className="chat-empty__subtitle">
                            Analyzing <strong>{selectedDataset.name}</strong>
                        </p>
                        <div className="chat-suggestions">
                            {['Summarize dataset', 'Show outliers', 'Plot trend', 'Key drivers'].map((s) => (
                                <button key={s} onClick={() => setInputMessage(s)} className="chat-suggestion-chip">{s}</button>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col pb-4">
                        {messages.map((msg, i) => (
                            <ChatMessage
                                key={msg.id || i}
                                msg={msg}
                                isUser={msg.role === 'user'}
                                index={i}
                                toggleTechnicalDetails={(id) => setExpandedTechnicalDetails(p => ({ ...p, [id]: !p[id] }))}
                                expandedTechnicalDetails={expandedTechnicalDetails}
                                copyToClipboard={(text) => navigator.clipboard.writeText(text)}
                                onRerun={handleRerun}
                            />
                        ))}
                        {isAITyping && (
                            <div className="chat-message--ai">
                                <div className="chat-ai-content">
                                    {streamingContent ? (
                                        <ReactMarkdown>{streamingContent}</ReactMarkdown>
                                    ) : (
                                        <div className="chat-typing">
                                            <span className="chat-typing-dot" />
                                            <span className="chat-typing-dot" />
                                            <span className="chat-typing-dot" />
                                        </div>
                                    )}
                                </div>
                            </div>
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

            <ChatHistoryModal isOpen={showHistoryModal} onClose={() => setShowHistoryModal(false)} currentConversationId={currentConversationId} onSelectConversation={(id) => { setCurrentConversation(id); setShowHistoryModal(false); }} />
        </div>
    );
};

export default ChatPanel;
