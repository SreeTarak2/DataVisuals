import React, { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';
import { Send, Sparkles, Loader2, RefreshCw, X, History, ChevronDown, ChevronUp, Copy, Check, Edit, ArrowRight, ChevronRight, Plus, WifiOff, Square, TrendingUp, BarChart3, Lightbulb, MessageSquare, Table2, LayoutGrid } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DOMPurify from 'dompurify';
import PlotlyChart from '@/components/features/charts/PlotlyChart';
import useChatStore from '@/store/chatStore';
import useDatasetStore from '@/store/datasetStore';
import useWebSocket from '@/hooks/useWebSocket';
import InsightFeedback from '@/components/features/feedback/InsightFeedback';
import CorrectionCapture from '@/components/features/chat/CorrectionCapture';
import ChatHistoryModal from '@/components/features/observatory/ChatHistoryModal';
import './ChatPanel.css';

const RATE_LIMIT_TOTAL = 30;

/* ─── Intent Detection for Dashboard Component Addition ─── */
const COMPONENT_INTENT_PATTERNS = [
    // KPI patterns
    { type: 'kpi', regex: /^(show|add|display|create|put|give me)\s+(me\s+)?(a\s+)?(kpi|metric|card|number|total|sum|average|avg|count)\s+(of|for|on)\s+(.+)/i },
    { type: 'kpi', regex: /^(what'?s?\s+)?(the\s+)?(total|sum|average|avg|count|mean|median)\s+(of\s+)?(.+)/i },
    // Chart patterns
    { type: 'chart', regex: /^(show|add|display|create|plot|draw|make)\s+(me\s+)?(a\s+)?(chart|graph|visualization|viz|plot)\s+(of|for|on)\s+(.+)/i },
    { type: 'chart', regex: /^(show|plot|chart|graph)\s+(me\s+)?(.+)\s+(by|across|vs|versus|against)\s+(.+)/i },
    { type: 'chart', regex: /^(bar|line|pie|scatter|area|histogram)\s+(chart|graph|plot|of|for)\s+(.+)/i },
];

const AGGREGATION_MAP = {
    'total': 'sum', 'sum': 'sum',
    'average': 'mean', 'avg': 'mean', 'mean': 'mean',
    'median': 'median',
    'count': 'count', 'number of': 'count',
    'max': 'max', 'highest': 'max', 'peak': 'max',
    'min': 'min', 'lowest': 'min',
};

const CHART_TYPE_MAP = {
    'bar': 'bar', 'bar chart': 'bar',
    'line': 'line', 'line chart': 'line', 'trend': 'line',
    'pie': 'pie', 'pie chart': 'pie',
    'scatter': 'scatter', 'scatter plot': 'scatter',
    'area': 'area', 'area chart': 'area',
    'histogram': 'histogram', 'hist': 'histogram', 'distribution': 'histogram',
};

const detectComponentIntent = (message, columnNames = []) => {
    const trimmed = message.trim();

    for (const pattern of COMPONENT_INTENT_PATTERNS) {
        const match = trimmed.match(pattern.regex);
        if (!match) continue;

        const intent = { type: pattern.type, raw: trimmed };

        if (pattern.type === 'kpi') {
            // Extract aggregation and column
            const aggWord = match[1] || match[3] || '';
            const colPart = match[4] || match[5] || '';
            intent.aggregation = AGGREGATION_MAP[aggWord.toLowerCase()] || 'sum';
            intent.column = findBestColumnMatch(colPart, columnNames);
            intent.title = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
        } else if (pattern.type === 'chart') {
            // Extract chart type and columns
            const chartWord = match[1] || match[3] || '';
            const colPart = match[4] || match[5] || match[3] || '';
            const groupPart = match[5] || match[4] || '';
            intent.chart_type = CHART_TYPE_MAP[chartWord.toLowerCase()] || 'bar';
            intent.column = findBestColumnMatch(colPart, columnNames);
            intent.group_by = findBestColumnMatch(groupPart, columnNames);
            intent.aggregation = 'sum';
            intent.title = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
        }

        if (intent.column) return intent;
    }

    return null;
};

const findBestColumnMatch = (text, columnNames) => {
    if (!text || !columnNames.length) return null;
    const normalized = text.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim();
    const words = normalized.split(/\s+/).filter(w => w.length > 1);

    // Exact match
    for (const col of columnNames) {
        if (col.toLowerCase() === normalized) return col;
    }

    // Contains match
    for (const col of columnNames) {
        const colLower = col.toLowerCase();
        if (words.some(w => colLower.includes(w)) || colLower.includes(normalized)) return col;
    }

    // Fuzzy: first word match
    if (words.length > 0) {
        for (const col of columnNames) {
            if (col.toLowerCase().includes(words[0])) return col;
        }
    }

    return null;
};

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

const formatTableValue = (value) => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
    if (typeof value === 'boolean') return value ? 'True' : 'False';
    return String(value);
};

const getTableColumns = (table) => {
    if (!table?.columns?.length) {
        const firstRow = table?.rows?.[0];
        return firstRow && typeof firstRow === 'object'
            ? Object.keys(firstRow).map((key) => ({ key, label: key.replace(/_/g, ' ') }))
            : [];
    }
    return table.columns.map((column) => (
        typeof column === 'string'
            ? { key: column, label: column.replace(/_/g, ' ') }
            : { key: column.key, label: column.label || String(column.key).replace(/_/g, ' ') }
    )).filter((column) => column.key);
};

const QueryResultTable = ({ table }) => {
    const rows = Array.isArray(table?.rows) ? table.rows : [];
    const columns = getTableColumns(table);
    if (!rows.length || !columns.length) return null;

    const totalRows = table?.totalRows ?? rows.length;
    const displayedRows = table?.displayedRows ?? rows.length;

    return (
        <div className="chat-table-wrapper mt-3">
            <div className="flex items-center justify-between gap-2 border-b border-border bg-elevated/40 px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                    <Table2 size={13} className="text-muted shrink-0" />
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-muted">Query Results</span>
                </div>
                <span className="text-[10px] text-muted shrink-0">{displayedRows.toLocaleString()} of {totalRows.toLocaleString()}</span>
            </div>
            <div className="max-h-[260px] overflow-auto bg-surface">
                <table>
                    <thead>
                        <tr>
                            {columns.map((column) => (
                                <th key={column.key}>{column.label}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, rowIndex) => (
                            <tr key={rowIndex}>
                                {columns.map((column) => (
                                    <td key={`${rowIndex}-${column.key}`}>{formatTableValue(row?.[column.key])}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

// =============================================================================
// ChatMessage — Enhanced with animations, avatar, timestamps
// =============================================================================
const ChatMessage = memo(({ msg, index, isUser, toggleTechnicalDetails, expandedTechnicalDetails, onRerun, onSuggestionClick, followUpOverride, msgMeta }) => {
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

    const canShowFollowUps = msg.show_follow_up_suggestions === true;
    const visibleFollowUps = followUpOverride?.length > 0
        ? followUpOverride
        : canShowFollowUps
            ? (msg.follow_up_suggestions || [])
            : [];

    // Attempt to parse JSON content gracefully if backend returned raw JSON string
    let displayContent = msg.content || '';
    try {
        let cleanStr = displayContent.trim();
        if (cleanStr.startsWith('```json')) cleanStr = cleanStr.substring(7);
        else if (cleanStr.startsWith('```')) cleanStr = cleanStr.substring(3);
        if (cleanStr.endsWith('```')) cleanStr = cleanStr.substring(0, cleanStr.length - 3);
        cleanStr = cleanStr.trim();
        
        if (cleanStr.startsWith('{') && cleanStr.endsWith('}')) {
            const parsed = JSON.parse(cleanStr);
            if (parsed.response_text) displayContent = parsed.response_text;
            else if (parsed.response) displayContent = parsed.response;
            else if (parsed.message) displayContent = parsed.message;
        }
    } catch (e) {
        // Not valid JSON, ignore and use raw string
    }

    // AI message
    return (
        <motion.div className="chat-message--ai" variants={msgVariants} initial="hidden" animate="visible">
            <div className="chat-ai-row">
                {/* AI Avatar */}
                <div className="chat-ai-avatar">
                    <Sparkles size={14} className="text-ocean" />
                </div>

                <div className="chat-ai-body">
                    {msg.isCancelled && (
                        <div className="flex items-center gap-1.5 text-[10px] text-yellow-700 mb-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-yellow-600 inline-block" />
                            Partial response — stopped
                        </div>
                    )}

                    {/* Chart — use PlotlyChart consistently for all types */}
                    {msg.chart_config && msg.chart_config.data?.length > 0 && (
                        <div className="chat-chart">
                            <div className="chat-chart__header">
                                <BarChart3 size={13} className="opacity-50" />
                                <span className="chat-chart__title">
                                    {msg.chart_config.layout?.title?.text || msg.chart_config.layout?.title || 'Visualization'}
                                </span>
                            </div>
                            <div style={{ height: '300px', padding: '4px 0' }}>
                                <PlotlyChart
                                    data={msg.chart_config.data}
                                    layout={{
                                        ...msg.chart_config.layout,
                                        paper_bgcolor: 'transparent',
                                        plot_bgcolor: 'transparent',
                                        font: { color: 'var(--text-secondary, #6C6E79)', size: 11 },
                                        margin: { t: 20, b: 50, l: 50, r: 12 },
                                        height: 290,
                                        xaxis: { ...(msg.chart_config.layout?.xaxis || {}), gridcolor: 'rgba(255,255,255,0.06)' },
                                        yaxis: { ...(msg.chart_config.layout?.yaxis || {}), gridcolor: 'rgba(255,255,255,0.06)' },
                                    }}
                                    config={{ displayModeBar: false, responsive: true }}
                                />
                            </div>
                        </div>
                    )}

                    <div className="chat-ai-content">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
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
                            {displayContent}
                        </ReactMarkdown>
                    </div>

                    <QueryResultTable table={msg.result_table} />

                    {/* Transparency indicators */}
                    {msgMeta?.sql_fallback && (
                        <div className="flex items-center gap-1.5 text-[10px] text-yellow-700 mt-1 mb-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-yellow-600 inline-block shrink-0" />
                            Estimate — exact query couldn't execute, response is based on data structure
                        </div>
                    )}
                    {msgMeta?.chart_error && (
                        <div className="flex items-center gap-1.5 text-[10px] text-red-700 mt-1 mb-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-600 inline-block shrink-0" />
                            Chart couldn't be rendered
                        </div>
                    )}
                    {msgMeta?.column_corrections && Object.keys(msgMeta.column_corrections).length > 0 && (
                        <div className="flex items-center gap-1.5 text-[10px] text-blue-700 mt-1 mb-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-600 inline-block shrink-0" />
                            Chart column names were adjusted to match your data
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
                            <InsightFeedback
                                variant="compact"
                                insightText={msg.content?.slice(0, 500) || ''}
                            />
                        </div>
                        {msg.timestamp && <span className="chat-timestamp">{formatTime(msg.timestamp)}</span>}
                    </div>

                    {/* Follow-up suggestion chips */}
                    {visibleFollowUps.length > 0 && onSuggestionClick && (
                        <div className="mt-2 flex flex-col gap-1">
                            {visibleFollowUps.map((s, i) => (
                                <button
                                    key={i}
                                    onClick={() => onSuggestionClick(s)}
                                    className="flex items-center gap-2 text-left text-[12px] text-secondary hover:text-header px-2 py-1.5 rounded-lg hover:bg-elevated/60 transition-colors group"
                                >
                                    <ChevronRight size={11} className="text-muted shrink-0 group-hover:text-accent-primary transition-colors" />
                                    <span className="leading-snug">{s}</span>
                                </button>
                            ))}
                        </div>
                    )}
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

    // Resizing logic for ChatPanel
    const [width, setWidth] = useState(parseInt(localStorage.getItem('chat_panel_width')) || 480);
    const [isResizing, setIsResizing] = useState(false);

    const startResizing = useCallback((e) => {
        e.preventDefault();
        setIsResizing(true);
    }, []);

    const stopResizing = useCallback(() => {
        setIsResizing(false);
        localStorage.setItem('chat_panel_width', width);
    }, [width]);

    const resize = useCallback((e) => {
        if (isResizing) {
            const newWidth = window.innerWidth - e.clientX;
            // Constrain width between 350px and 80% of screen
            if (newWidth > 350 && newWidth < window.innerWidth * 0.5) {
                setWidth(newWidth);
            }
        }
    }, [isResizing]);

    useEffect(() => {
        if (isResizing) {
            window.addEventListener('mousemove', resize);
            window.addEventListener('mouseup', stopResizing);
        } else {
            window.removeEventListener('mousemove', resize);
            window.removeEventListener('mouseup', stopResizing);
        }
        return () => {
            window.removeEventListener('mousemove', resize);
            window.removeEventListener('mouseup', stopResizing);
        };
    }, [isResizing, resize, stopResizing]);

    const { selectedDataset } = useDatasetStore();
    const [inputMessage, setInputMessage] = useState('');
    const [expandedTechnicalDetails, setExpandedTechnicalDetails] = useState({});
    const [streamingChartConfig, setStreamingChartConfig] = useState(null);
    const [showHistoryModal, setShowHistoryModal] = useState(false);
    const [thinkingSteps, setThinkingSteps] = useState([]);
    const [rateLimitRemaining, setRateLimitRemaining] = useState(null);
    const [rateLimitCountdown, setRateLimitCountdown] = useState(null);
    const [followUpMap, setFollowUpMap] = useState({}); // { [msgId]: string[] }
    const [msgMetaMap, setMsgMetaMap] = useState({}); // { [msgId]: { sql_fallback, column_corrections, chart_error } }
    const [pendingBelief, setPendingBelief] = useState(null);
    const streamingMetaRef = useRef({ sql_fallback: false, column_corrections: {}, chart_error: false });
    const lastStreamingMsgIdRef = useRef(null);

    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);
    const streamingChartConfigRef = useRef(null);
    const currentClientMessageIdRef = useRef(null);
    const initialQuerySentRef = useRef(false); // Prevent double-sending initial query
    const messages = getCurrentConversationMessages();
    const isAITyping = loading || isStreaming;

    // Keep ref in sync with state so callbacks stay stable
    streamingChartConfigRef.current = streamingChartConfig;

    // WebSocket — all callbacks use refs to keep identity stable
    const { isConnected, connect, disconnect, sendMessage: wsSendMessage, sendCancel } = useWebSocket({
        onToken: useCallback((token) => appendStreamingToken(token), [appendStreamingToken]),
        onResponseComplete: useCallback((fullResponse) => {
            // Streaming response complete — content is accumulated via onToken
        }, []),
        onChart: useCallback((config) => setStreamingChartConfig(config), [setStreamingChartConfig]),
        onChartError: useCallback(() => {
            streamingMetaRef.current.chart_error = true;
        }, []),
        onThinkingStep: useCallback((label) => {
            setThinkingSteps(prev => [...prev, label]);
        }, [setThinkingSteps]),
        onDone: useCallback(({ conversationId, chartConfig, sql, resultTable, insights = [], data_summary = '', follow_up_suggestions, show_follow_up_suggestions = false, rate_limit_remaining, sql_fallback, column_corrections }) => {
            if (conversationId) setCurrentConversation(conversationId);
            const content = useChatStore.getState().streamingContent;
            finishStreaming(content, chartConfig || streamingChartConfigRef.current, sql, insights, data_summary, resultTable, follow_up_suggestions || [], show_follow_up_suggestions);
            setStreamingChartConfig(null);
            currentClientMessageIdRef.current = null;
            setThinkingSteps([]);
            if (rate_limit_remaining !== null && rate_limit_remaining !== undefined) {
                setRateLimitRemaining(rate_limit_remaining);
            }
            if (show_follow_up_suggestions && follow_up_suggestions?.length > 0 && lastStreamingMsgIdRef.current) {
                setFollowUpMap(prev => ({ ...prev, [lastStreamingMsgIdRef.current]: follow_up_suggestions }));
            }
            if (lastStreamingMsgIdRef.current) {
                const meta = {
                    sql_fallback: sql_fallback || streamingMetaRef.current.sql_fallback,
                    column_corrections: column_corrections || streamingMetaRef.current.column_corrections,
                    chart_error: streamingMetaRef.current.chart_error,
                };
                if (meta.sql_fallback || Object.keys(meta.column_corrections).length > 0 || meta.chart_error) {
                    setMsgMetaMap(prev => ({ ...prev, [lastStreamingMsgIdRef.current]: meta }));
                }
            }
            streamingMetaRef.current = { sql_fallback: false, column_corrections: {}, chart_error: false };
        }, [finishStreaming, setCurrentConversation, setStreamingChartConfig, setThinkingSteps, setRateLimitRemaining, setFollowUpMap, setMsgMetaMap]),
        onError: useCallback((err) => {
            cancelStreaming();
            currentClientMessageIdRef.current = null;
            setThinkingSteps([]);
            const detail = String(err?.detail || '').toLowerCase();
            if (detail.includes('rate') || detail.includes('limit')) {
                const retryAfter = err?.retry_after_seconds || 60;
                setRateLimitCountdown(retryAfter);
                const interval = setInterval(() => {
                    setRateLimitCountdown(prev => {
                        if (prev <= 1) { clearInterval(interval); return null; }
                        return prev - 1;
                    });
                }, 1000);
            } else {
                toast.error(err?.detail || 'Connection error');
            }
        }, [cancelStreaming, setThinkingSteps, setRateLimitCountdown]),
        onCancelAck: useCallback(() => {
            currentClientMessageIdRef.current = null;
        }, []),
        onBeliefSaved: useCallback((belief) => {
            setPendingBelief(belief);
        }, [setPendingBelief]),
    });

    // Connect when panel opens, disconnect when it closes — use a ref to
    // prevent reconnection loops triggered by isConnected state changes
    // (failed connections fire onerror → setIsConnecting(false) → re-render
    // → effect re-runs with isConnected still false → connect() called again).
    const panelConnectedRef = useRef(false);
    useEffect(() => {
        if (isOpen && selectedDataset?.id && !panelConnectedRef.current) {
            panelConnectedRef.current = true;
            connect();
        }
        if (!isOpen) {
            panelConnectedRef.current = false;
            disconnect();
        }
    }, [isOpen, selectedDataset?.id, connect, disconnect]);

    // Sync ref when connection actually establishes
    useEffect(() => {
        if (isConnected) {
            panelConnectedRef.current = true;
        }
    }, [isConnected]);

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

    // ── Chart-aware smart suggestions ──
    const chartSuggestions = chartContext ? [
        'Explain this chart',
        'Find trends & patterns',
        'Spot anomalies or outliers',
        'Suggest a better visualization',
    ] : null;

    // ── Dataset-aware starter suggestions using actual column names ──
    const datasetSuggestions = useMemo(() => {
        if (!selectedDataset) return [];
        const cols = selectedDataset.column_names || selectedDataset.columns || [];
        const meta = selectedDataset.column_metadata || [];
        const toLabel = (c) => (c || '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        const numCols = meta.length
            ? meta.filter(c => ['int64','float64','int32','float32','double','numeric'].includes((c.dtype || '').toLowerCase())).map(c => c.name)
            : cols.filter(c => /amount|price|revenue|sales|count|qty|quantity|total|value|rate|score|age|size/.test(c.toLowerCase()));
        const catCols = meta.length
            ? meta.filter(c => ['utf8','string','categorical','object','str'].includes((c.dtype || '').toLowerCase())).map(c => c.name)
            : cols.filter(c => !numCols.includes(c));
        const hasDate = cols.some(c => /date|time|year|month|day/.test(c.toLowerCase()));

        const suggestions = [];
        if (hasDate && numCols[0]) suggestions.push({ icon: TrendingUp, text: `Show the trend of ${toLabel(numCols[0])} over time` });
        else if (numCols[0]) suggestions.push({ icon: TrendingUp, text: `What are the highest and lowest ${toLabel(numCols[0])} values?` });
        if (catCols[0] && numCols[0]) suggestions.push({ icon: BarChart3, text: `Compare ${toLabel(numCols[0])} across ${toLabel(catCols[0])}` });
        suggestions.push({ icon: Lightbulb, text: `Find outliers or unusual patterns` });
        suggestions.push({ icon: MessageSquare, text: `Give me an executive summary of this dataset` });
        return suggestions.slice(0, 4);
    }, [selectedDataset]);

    const handleStopGeneration = useCallback(() => {
        const clientMsgId = currentClientMessageIdRef.current;
        if (clientMsgId) sendCancel(clientMsgId);
        cancelStreaming();
        setThinkingSteps([]);
        currentClientMessageIdRef.current = null;
    }, [sendCancel, cancelStreaming]);

    // ─── Handle component addition via chatbot intent ───
    const handleAddComponent = useCallback(async (intent) => {
        const datasetId = selectedDataset?.id;
        if (!datasetId) return;

        const token = localStorage.getItem('token');
        try {
            const body = {
                type: intent.type,
                column: intent.column,
                aggregation: intent.aggregation || 'sum',
                title: intent.title,
            };
            if (intent.chart_type) body.chart_type = intent.chart_type;
            if (intent.group_by) body.group_by = intent.group_by;

            const res = await fetch(`/api/datasets/${datasetId}/components/add`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(body),
            });

            if (res.ok) {
                const data = await res.json();
                toast.success(`Added "${data.component?.title || intent.title}" to dashboard`);
                // Dispatch event to notify dashboard of new component
                window.dispatchEvent(new CustomEvent('dashboard-component-added', {
                    detail: { type: data.type, component: data.component },
                }));
            } else {
                const err = await res.json().catch(() => ({}));
                toast.error(err.detail || 'Failed to add component');
            }
        } catch (e) {
            toast.error('Failed to add component');
        }
    }, [selectedDataset]);

    const handleSendMessage = async (msgOverride = null) => {
        const rawMsg = msgOverride || inputMessage.trim();
        if (!rawMsg || isAITyping || !selectedDataset?.id) return;

        // Check for component addition intent BEFORE sending to AI
        const columnNames = selectedDataset.column_names || selectedDataset.columns || [];
        const intent = detectComponentIntent(rawMsg, columnNames);

        if (intent) {
            setInputMessage('');
            if (textareaRef.current) textareaRef.current.style.height = 'auto';

            // Add user message to chat
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

            // Add AI confirmation message
            const aiMsgId = `msg_${Date.now()}_ai`;
            const actionLabel = intent.type === 'kpi' ? 'KPI card' : `${intent.chart_type || 'bar'} chart`;
            useChatStore.setState(state => ({
                conversations: {
                    ...state.conversations,
                    [convId]: {
                        ...state.conversations[convId],
                        messages: [...(state.conversations[convId]?.messages || []), {
                            id: aiMsgId,
                            role: 'assistant',
                            content: `Added ${actionLabel} for **${intent.column}** to your dashboard. You can drag and resize it in the dashboard view.`,
                            timestamp: new Date().toISOString(),
                        }]
                    }
                }
            }));

            // Actually add the component
            await handleAddComponent(intent);
            return;
        }

        // No intent detected — send to AI as normal
        setInputMessage('');
        setPendingBelief(null);

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
            const aiMsgId = `msg_${Date.now()}_ai`;
            lastStreamingMsgIdRef.current = aiMsgId;
            startStreaming(aiMsgId);
            const clientMsgId = wsSendMessage({ message: msg, datasetId: selectedDataset.id, conversationId: convId, streaming: true });
            currentClientMessageIdRef.current = clientMsgId;
        } else {
            await sendMessage(msg, selectedDataset.id, convId);
        }
    };

    // Auto-fill and submit initial queries (e.g., from Insights buttons)
    useEffect(() => {
        if (isOpen && initialQuery && !initialQuerySentRef.current) {
            // Mark as sent immediately to prevent double submission
            initialQuerySentRef.current = true;
            // Slight delay to ensure connection/animations settle
            const timer = setTimeout(() => {
                handleSendMessage(initialQuery);
                onClearInitialQuery?.();
            }, 300);
            return () => clearTimeout(timer);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, initialQuery]);

    // Reset the initial query sent flag when initialQuery changes
    useEffect(() => {
        if (!initialQuery) {
            initialQuerySentRef.current = false;
        }
    }, [initialQuery]);

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
        <div
            className={cn(
                "chat-panel",
                !isOpen && "closed",
                !isOpen && "pointer-events-none",
                isResizing && "resizing",
                className
            )}
            style={{
                width: isOpen ? `${width}px` : undefined,
                pointerEvents: isResizing ? 'auto' : undefined
            }}
        >
            {/* Resize Handle */}
            <div
                className="chat-resize-handle"
                onMouseDown={startResizing}
            />
            {/* ── Header ── */}
            <header className="chat-header">
                <div className="flex items-center gap-2">
                    <span className="text-[18px] font-bold text-header tracking-tight">AI Assistant</span>
                    {/* Connection status dot */}
                    {isConnected ? (
                        <span title="Connected" className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                    ) : (
                        <span title="Disconnected" className="flex items-center gap-1 text-[10px] text-muted">
                            <WifiOff size={11} />
                        </span>
                    )}
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
                        ) : null}
                        <h3 className="text-3xl font-bold text-header tracking-tighter mt-4 mb-2">
                            {chartContext ? 'Ask about your chart' : 'How can I help?'}
                        </h3>
                        {!chartContext && (
                            <p className="chat-empty__subtitle">
                                Analyzing <strong>{selectedDataset.name}</strong>
                            </p>
                        )}
                        <div className="chat-suggestions">
                            {chartSuggestions
                                ? chartSuggestions.map((s) => (
                                    <button key={s} onClick={() => handleSendMessage(s)} className="chat-suggestion-chip">{s}</button>
                                ))
                                : datasetSuggestions.map(({ icon: Icon, text }) => (
                                    <button key={text} onClick={() => handleSendMessage(text)} className="chat-suggestion-chip flex items-center gap-1.5">
                                        <Icon size={12} className="opacity-60" />{text}
                                    </button>
                                ))
                            }
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
                                    onSuggestionClick={(s) => handleSendMessage(s)}
                                    followUpOverride={followUpMap[msg.id] || null}
                                    msgMeta={msgMetaMap[msg.id] || null}
                                />
                                {msg.role === 'assistant' && pendingBelief && i === messages.length - 1 && (
                                    <CorrectionCapture
                                        belief={pendingBelief}
                                        datasetId={selectedDataset?.id}
                                        onDismiss={() => setPendingBelief(null)}
                                    />
                                )}
                            </React.Fragment>
                        ))}
                        {isAITyping && (
                            <motion.div className="chat-message--ai" variants={msgVariants} initial="hidden" animate="visible">
                                <div className="chat-ai-row">
                                    <div className="chat-ai-avatar chat-ai-avatar--thinking">
                                        <Sparkles size={14} className="text-ocean" />
                                    </div>
                                    <div className="chat-ai-body">
                                        <div className="chat-ai-content">
                                            {streamingContent ? (
                                                <ReactMarkdown
                                                    remarkPlugins={[remarkGfm]}
                                                >
                                                    {(() => {
                                                        let sc = streamingContent;
                                                        try {
                                                            let cleanStr = sc.trim();
                                                            if (cleanStr.startsWith('```json')) cleanStr = cleanStr.substring(7);
                                                            else if (cleanStr.startsWith('```')) cleanStr = cleanStr.substring(3);
                                                            if (cleanStr.endsWith('```')) cleanStr = cleanStr.substring(0, cleanStr.length - 3);
                                                            cleanStr = cleanStr.trim();
                                                            
                                                            if (cleanStr.startsWith('{') && cleanStr.endsWith('}')) {
                                                                const parsed = JSON.parse(cleanStr);
                                                                if (parsed.response_text) sc = parsed.response_text;
                                                                else if (parsed.response) sc = parsed.response;
                                                                else if (parsed.message) sc = parsed.message;
                                                            }
                                                        } catch (e) {}
                                                        return sc;
                                                    })()}
                                                </ReactMarkdown>
                                            ) : (
                                                <div className="chat-thinking">
                                                    <div className="chat-typing">
                                                        <span className="chat-typing-dot" />
                                                        <span className="chat-typing-dot" />
                                                        <span className="chat-typing-dot" />
                                                    </div>
                                                    {thinkingSteps.length > 0 ? (
                                                        <div className="flex flex-col gap-0.5">
                                                            {thinkingSteps.map((step, i) => (
                                                                <span
                                                                    key={i}
                                                                    className={cn(
                                                                        "chat-thinking-label",
                                                                        i < thinkingSteps.length - 1 && "opacity-40 line-through"
                                                                    )}
                                                                >
                                                                    {step}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    ) : (
                                                        <span className="chat-thinking-label">Thinking…</span>
                                                    )}
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

            {/* ── Rate limit indicator ── */}
            {(rateLimitCountdown !== null || (rateLimitRemaining !== null && rateLimitRemaining <= 10)) && (
                <div className="px-3 pb-1">
                    {rateLimitCountdown !== null ? (
                        <div className="flex items-center gap-1.5 text-[10px] text-yellow-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-yellow-600 animate-pulse inline-block" />
                            Rate limit — resets in <strong>{rateLimitCountdown}s</strong>
                        </div>
                    ) : (
                        <div className="flex items-center gap-2">
                            <div className="flex-1 h-0.5 rounded-full bg-border overflow-hidden">
                                <div
                                    className={cn("h-0.5 rounded-full transition-all", rateLimitRemaining <= 3 ? "bg-red-600" : "bg-yellow-600")}
                                    style={{ width: `${(rateLimitRemaining / RATE_LIMIT_TOTAL) * 100}%` }}
                                />
                            </div>
                            <span className={cn("text-[10px] tabular-nums", rateLimitRemaining <= 3 ? "text-red-700" : "text-yellow-700")}>
                                {rateLimitRemaining}/{RATE_LIMIT_TOTAL}
                            </span>
                        </div>
                    )}
                </div>
            )}

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
                        {!isAITyping && <span className="chat-kbd-hint">⏎</span>}
                        <button
                            onClick={isAITyping ? handleStopGeneration : () => handleSendMessage()}
                            disabled={!isAITyping && !inputMessage.trim()}
                            className={cn(
                                "chat-send-btn",
                                isAITyping ? "chat-send-btn--stop" : inputMessage.trim() ? "chat-send-btn--active" : "chat-send-btn--disabled"
                            )}
                            title={isAITyping ? "Stop generation" : "Send"}
                        >
                            {isAITyping ? <Square size={13} className="fill-current" /> : <ArrowRight size={16} />}
                        </button>
                    </div>
                </div>
            </div>

            <ChatHistoryModal isOpen={showHistoryModal} onClose={() => setShowHistoryModal(false)} currentConversationId={currentConversationId} onSelectConversation={(id) => { setCurrentConversation(id); setShowHistoryModal(false); }} />
        </div>
    );
};

export default ChatPanel;
