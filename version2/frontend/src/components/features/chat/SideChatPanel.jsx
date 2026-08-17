/**
 * SideChatPanel — Unified AI Copilot Panel
 *
 * Orchestrates the chat experience: manages WebSocket streaming,
 * conversation state, message rendering, and mode-aware behavior.
 *
 * Components are imported from sibling files:
 *   - ChatMessage        renders user/AI message bubbles
 *   - ModernReasoningBlock  collapsible thinking trace
 *   - CopyButton          clipboard copy with feedback
 *   - QueryResultTable    SQL result table
 *   - chatUtils            constants + helper functions
 */
import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, Loader2, X, History, Plus, TrendingUp, BarChart3, Lightbulb, MessageSquare, HelpCircle, Code2 } from 'lucide-react';
import ChatInput from '@/components/features/playground/ChatInput';
import { motion } from 'framer-motion'; 
import { toast } from 'react-hot-toast';
import { cn } from '@/lib/utils';

import useChatStore from '@/store/chatStore';
import useAuthStore from '@/store/authStore';
import useDatasetStore from '@/store/datasetStore';
import useNotificationStore from '@/store/notificationStore';
import useWebSocket from '@/hooks/useWebSocket';
import InsightFeedback from '@/components/features/feedback/InsightFeedback';
import CorrectionCapture from '@/components/features/chat/CorrectionCapture';
import ChatHistoryModal from '@/components/features/observatory/ChatHistoryModal';
import SqlEditorPanel from '@/components/features/sql/SqlEditorPanel';
import Logo from '@/components/common/Logo';
import { insightAPI } from '@/services/api';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import ChatMessage from '@/components/features/chat/ChatMessage';
import ModernReasoningBlock from '@/components/features/chat/ModernReasoningBlock';
import {
  COPILOT_MODES,
  RATE_LIMIT_TOTAL,
  detectComponentIntent,
  msgVariants,
} from '@/components/features/chat/chatUtils';

import './SideChatPanel.css';

// =============================================================================
// SideChatPanel — Unified AI Copilot Panel
// =============================================================================
const SideChatPanel = ({ isOpen, onClose, className, chartContext, onClearChartContext, initialQuery, onClearInitialQuery, onInsertSql, onPinToCanvas, mode: modeProp = 'analyst', embedded = false }) => {
    const navigate = useNavigate();
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

    // Resizing logic
    const [width, setWidth] = useState(() => {
        const saved = parseInt(localStorage.getItem('chat_panel_width')) || 480;
        document.documentElement.style.setProperty('--chat-panel-width', `${saved}px`);
        return saved;
    });
    const [isResizing, setIsResizing] = useState(false);

    useEffect(() => {
        document.documentElement.style.setProperty('--chat-panel-width', `${width}px`);
    }, [width]);

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
    const [editingMessageId, setEditingMessageId] = useState(null);
    const [editingMessageContent, setEditingMessageContent] = useState('');
    const thinkingStepsRef = useRef([]);
    const [sharedSqlContent, setSharedSqlContent] = useState(null);

    const [dismissedMessages, setDismissedMessages] = useState(new Set());
    const [pendingBelief, setPendingBelief] = useState(null);
    const streamingMetaRef = useRef({ sql_fallback: false, column_corrections: {}, chart_error: false });
    const lastStreamingMsgIdRef = useRef(null);

    const messagesEndRef = useRef(null);
    const sendingGuardRef = useRef(false);
    const streamingChartConfigRef = useRef(null);
    const currentClientMessageIdRef = useRef(null);
    const initialQuerySentRef = useRef(false);
    const messages = getCurrentConversationMessages();
    const isAITyping = loading || isStreaming;

    const mode = modeProp;
    const modeConfig = COPILOT_MODES[mode] || COPILOT_MODES.analyst;

    streamingChartConfigRef.current = streamingChartConfig;
    // Sync thinkingSteps to ref so onDone callback can access the latest value
    useEffect(() => {
      thinkingStepsRef.current = thinkingSteps;
    }, [thinkingSteps]);

    // WebSocket — all callbacks use refs to keep identity stable
    const { isConnected, connect, disconnect, sendMessage: wsSendMessage, sendCancel, sendRegenerate } = useWebSocket({
        onNotification: useCallback((notification) => {
            // Real-time job notifications (dataset ready / failed / resumed) → inbox
            try {
                useNotificationStore.getState().handlePush(notification);
            } catch (e) {
                console.warn('Failed to handle notification push:', e);
            }
        }, []),
        onProcessingUpdate: useCallback((update) => {
            // Live pipeline progress → dataset store so the processing
            // indicator (and dashboard) update instantly across devices
            try {
                useDatasetStore.getState().applyProcessingUpdate(update.datasetId, update);
            } catch (e) {
                console.warn('Failed to handle processing update:', e);
            }
        }, []),
        onSessionRevoked: useCallback(() => {
            // Session revoked server-side (logged out on another device) —
            // clear local state; ProtectedRoute redirects to /login.
            try {
                useAuthStore.getState().handleSessionRevoked();
            } catch (e) {
                console.warn('Failed to handle session revocation:', e);
            }
        }, []),
        onToken: useCallback((token) => appendStreamingToken(token), [appendStreamingToken]),
        onResponseComplete: useCallback(() => {}, []),
        onChart: useCallback((config) => setStreamingChartConfig(config), [setStreamingChartConfig]),
        onChartError: useCallback(() => {
            streamingMetaRef.current.chart_error = true;
        }, []),
        onThinkingStep: useCallback((step) => {
            setThinkingSteps(prev => [...prev, step]);
        }, [setThinkingSteps]),
        onDone: useCallback(({ conversationId, chartConfig, sql, resultTable, insights = [], data_summary = '', follow_up_suggestions, show_follow_up_suggestions = false, rate_limit_remaining, sql_fallback, column_corrections }) => {
            if (conversationId) setCurrentConversation(conversationId);
            const content = useChatStore.getState().streamingContent;
            const savedSteps = thinkingStepsRef.current;
            finishStreaming(content, chartConfig || streamingChartConfigRef.current, sql, insights, data_summary, resultTable, follow_up_suggestions || [], show_follow_up_suggestions, null, savedSteps);
            setStreamingChartConfig(null);
            currentClientMessageIdRef.current = null;
            setThinkingSteps([]);
            thinkingStepsRef.current = [];
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
            // Auto-insert SQL into the editor when in SQL Analyst mode
            if (mode === 'sql_analyst' && onInsertSql) {
                let sqlToInsert = sql || null;
                if (!sqlToInsert && content) {
                    const match = content.match(/```sql\s*\n?([\s\S]*?)```/i);
                    if (match && match[1]?.trim()) {
                        sqlToInsert = match[1].trim();
                    }
                }
                if (sqlToInsert) {
                    onInsertSql(sqlToInsert);
                }
            }
        }, [finishStreaming, setCurrentConversation, setStreamingChartConfig, setThinkingSteps, setRateLimitRemaining, setFollowUpMap, setMsgMetaMap, mode, onInsertSql]),
        onError: useCallback((err) => {
            cancelStreaming();
            currentClientMessageIdRef.current = null;
            setThinkingSteps([]);
            if (err?.type === 'auth') return;
            if (err?.type === 'connection') return;
            const message = err?.detail || err?.content || '';
            const detail = String(message).toLowerCase();
            if (detail.includes('rate') || detail.includes('limit')) {
                const retryAfter = err?.retry_after_seconds || 60;
                setRateLimitCountdown(retryAfter);
                const interval = setInterval(() => {
                    setRateLimitCountdown(prev => {
                        if (prev <= 1) { clearInterval(interval); return null; }
                        return prev - 1;
                    });
                }, 1000);
            } else if (message) {
                toast.error(message);
            } else {
                console.warn('[Chat] onError with no message:', err);
            }
        }, [cancelStreaming, setThinkingSteps, setRateLimitCountdown]),
        onCleaningRedirect: useCallback(() => {
            // Cleaning guard blocked the query — jump to the Data Briefing so
            // the user can review pending number-changing cleaning actions.
            const datasetId = selectedDataset?.id;
            if (datasetId) {
                navigate(`/app/datasets/${datasetId}/briefing`);
            }
        }, [selectedDataset?.id, navigate]),
        onCancelAck: useCallback(() => {
            currentClientMessageIdRef.current = null;
        }, []),
        onBeliefSaved: useCallback((belief) => {
            setPendingBelief(belief);
        }, [setPendingBelief]),
        onRegenerateComplete: useCallback(({ versionMessageId }) => {
            console.log('[Regen] Version entry created:', versionMessageId);
        }, []),
    });

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

    useEffect(() => {
        if (isConnected) {
            panelConnectedRef.current = true;
        }
    }, [isConnected]);

    const handleDismissMessage = useCallback(async (msg) => {
        if (!selectedDataset?.id) return;
        setDismissedMessages((prev) => new Set(prev).add(msg.id));
        try {
            await insightAPI.dismiss({
                insightId: msg.id,
                insightText: msg.content?.slice(0, 1500) || '',
                datasetId: selectedDataset.id,
            });
            toast("I'll keep this in mind for future answers", {
                duration: 2000,
                style: { background: '#0f172a', color: '#e2e8f0', fontSize: '13px' },
                icon: '👁️',
            });
        } catch (error) {
            console.error('Dismiss failed:', error);
            setDismissedMessages((prev) => {
                const next = new Set(prev);
                next.delete(msg.id);
                return next;
            });
        }
    }, [selectedDataset?.id]);

    useEffect(() => {
        if (isOpen) {
            setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
        }
    }, [messages.length, streamingContent, isOpen]);

    // ── Chart-aware smart suggestions
    const chartSuggestions = chartContext ? [
        'Explain this chart',
        'Find trends & patterns',
        'Spot anomalies or outliers',
        'Suggest a better visualization',
    ] : null;

    // ── Dataset-aware starter suggestions
    const datasetSuggestions = useMemo(() => {
        if (!selectedDataset) return [];

        if (mode === 'sql_analyst') {
            const cols = selectedDataset.column_names || selectedDataset.columns || [];
            const numCols = cols.filter(c => /amount|price|revenue|sales|count|qty|quantity|total|value|rate|score|age|size/.test(c.toLowerCase()));
            const catCols = cols.filter(c => !numCols.includes(c));
            const firstNum = numCols[0] || cols[0] || 'value';
            const firstCat = catCols[0] || cols[1] || 'category';
            return [
                { icon: Code2, text: `Write a query to get the top 10 rows by ${firstNum}` },
                { icon: Code2, text: `Count rows grouped by ${firstCat}` },
                { icon: Code2, text: `Find all rows where ${firstNum} is above average` },
                { icon: HelpCircle, text: 'Show me all column names and their types' },
            ];
        }

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
        suggestions.push({ icon: Lightbulb, text: 'Find outliers or unusual patterns' });
        suggestions.push({ icon: MessageSquare, text: 'Give me an executive summary of this dataset' });
        return suggestions.slice(0, 4);
    }, [selectedDataset, mode]);

    const handleStopGeneration = useCallback(() => {
        const clientMsgId = currentClientMessageIdRef.current;
        if (clientMsgId) sendCancel(clientMsgId);
        cancelStreaming();
        setThinkingSteps([]);
        currentClientMessageIdRef.current = null;
    }, [sendCancel, cancelStreaming]);

    const handleAddComponent = useCallback(async (intent) => {
        const datasetId = selectedDataset?.id;
        if (!datasetId) return;

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
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Protection': '1' },
                credentials: 'include',
                body: JSON.stringify(body),
            });

            if (res.ok) {
                const data = await res.json();
                toast.success(`Added "${data.component?.title || intent.title}" to dashboard`);
                window.dispatchEvent(new CustomEvent('dashboard-component-added', {
                    detail: { type: data.type, component: data.component },
                }));
            } else {
                const err = await res.json().catch(() => ({}));
                toast.error(err.detail || 'Failed to add component');
            }
        } catch {
            toast.error('Failed to add component');
        }
    }, [selectedDataset]);

    const handleSendMessage = async (msgOverride = null) => {
        if (sendingGuardRef.current) return;
        sendingGuardRef.current = true;

        const rawMsg = msgOverride || inputMessage.trim();
        if (!rawMsg || isAITyping || !selectedDataset?.id) {
            sendingGuardRef.current = false;
            return;
        }

        // Check for component addition intent BEFORE sending to AI
        const columnNames = selectedDataset.column_names || selectedDataset.columns || [];
        const intent = detectComponentIntent(rawMsg, columnNames);

        if (intent) {
            setInputMessage('');
            sendingGuardRef.current = false;

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

            await handleAddComponent(intent);
            return;
        }

        // No intent detected — send to AI as normal
        setInputMessage('');
        setPendingBelief(null);

        let msg = rawMsg;
        if (chartContext && msgOverride) {
            const ctx = `[Chart: ${chartContext.chartType} — ${chartContext.yField} (${chartContext.aggregation}) by ${chartContext.xField}]`;
            msg = `${ctx} ${rawMsg}`;
        }

        if (chartContext) onClearChartContext?.();

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

        sendingGuardRef.current = false;

        const aiMsgId = `msg_${Date.now()}_ai`;
        lastStreamingMsgIdRef.current = aiMsgId;
        startStreaming(aiMsgId);

        try {
            if (isConnected) {
                const clientMsgId = wsSendMessage({
                    message: msg,
                    datasetId: selectedDataset.id,
                    conversationId: convId,
                    streaming: true,
                    mode: mode,
                    archetype: mode === 'investigator' ? 'analyst' : (mode === 'chart_expert' || mode === 'data_prep' || mode === 'sql_analyst') ? 'expert' : 'explorer',
                });
                if (clientMsgId) {
                    currentClientMessageIdRef.current = clientMsgId;
                } else {
                    await sendMessage(msg, selectedDataset.id, convId, { skipUserMessage: true });
                }
            } else {
                await sendMessage(msg, selectedDataset.id, convId, { skipUserMessage: true });
            }
        } catch (err) {
            console.error('Failed to process message:', err);
            cancelStreaming();
        }
    };

    // Auto-fill and submit initial queries
    useEffect(() => {
        if (isOpen && initialQuery && !initialQuerySentRef.current) {
            initialQuerySentRef.current = true;
            const timer = setTimeout(() => {
                handleSendMessage(initialQuery);
                onClearInitialQuery?.();
            }, 300);
            return () => clearTimeout(timer);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, initialQuery]);

    useEffect(() => {
        if (!initialQuery) {
            initialQuerySentRef.current = false;
        }
    }, [initialQuery]);

    // ── Version Management ──
    const [versionMap, setVersionMap] = useState({});  // { parentMsgId: [msg1, msg2, ...] }
    const [versionIndex, setVersionIndex] = useState({});  // { parentMsgId: 0 }

    const handleRegenerate = (messageId) => {
        // Find the AI message that the user wants to regenerate
        const msg = messages.find(m => m.id === messageId);
        if (!msg || msg.role !== 'assistant') return;

        // Find its parent (the user message before it)
        const msgIndex = messages.indexOf(msg);
        const parentMsg = msgIndex > 0 ? messages[msgIndex - 1] : null;
        if (!parentMsg || parentMsg.role !== 'user') return;
        const parentId = parentMsg.id;

        // Add current message to version map if not already there
        setVersionMap(prev => {
            const existing = prev[parentId] || [];
            if (!existing.find(m => m.id === msg.id)) {
                return { ...prev, [parentId]: [...existing, msg] };
            }
            return prev;
        });

        // Set version index to show the new version will be next
        setVersionIndex(prev => ({ ...prev, [parentId]: (prev[parentId] ?? 0) + 1 }));

        // Send regenerate via WebSocket — backend creates version entry and streams back
        if (!selectedDataset?.id || !currentConversationId) {
            // Fallback: fill input if no WebSocket or no conversation
            setInputMessage(parentMsg.content);
            return;
        }

        // Start streaming state so UI shows loading
        const aiMsgId = `msg_${Date.now()}_ai_regen`;
        lastStreamingMsgIdRef.current = aiMsgId;
        startStreaming(aiMsgId);
        setThinkingSteps([]);

        const regenClientId = sendRegenerate?.({
            conversationId: currentConversationId,
            messageId: msg.id,
            datasetId: selectedDataset.id,
        });

        if (regenClientId) {
            currentClientMessageIdRef.current = regenClientId;
        } else {
            // Fallback: WebSocket not connected or send failed
            cancelStreaming();
            setInputMessage(parentMsg.content);
        }
    };

    const handleVersionSwitch = (parentId, index) => {
        setVersionIndex(prev => ({ ...prev, [parentId]: index }));
    };

    // Helper to get visible message content considering versioning
    const getVisibleMessage = (msg, messageList) => {
        if (msg.role !== 'assistant') return msg;
        // Check if this is the last assistant message (may have versions)
        const msgIndex = messageList.indexOf(msg);
        if (msgIndex <= 0) return msg;
        const parentMsg = messageList[msgIndex - 1];
        if (parentMsg.role !== 'user') return msg;

        const parentId = parentMsg.id;
        const versions = versionMap[parentId] || [];
        const currentIdx = versionIndex[parentId] ?? 0;

        // If this message has versions and we're looking at a different version
        if (versions.length > 1) {
            const currentVersion = versions[currentIdx];
            if (currentVersion && currentVersion.id !== msg.id) {
                return { ...currentVersion, _isVersion: true, _parentId: parentId, _versions: versions, _versionIndex: currentIdx };
            }
        }
        return { ...msg, _parentId: parentId, _versions: versions, _versionIndex: currentIdx };
    };

    const handleRerun = (messageId) => {
        const msg = messages.find(m => m.id === messageId);
        if (!msg) return;
        if (msg.role === 'user') {
            setInputMessage(msg.content);
        } else {
            handleRegenerate(messageId);
        }
    };

    const handleEditStart = (messageId) => {
        const msg = messages.find(m => m.id === messageId);
        if (!msg) return;
        setEditingMessageId(messageId);
        setEditingMessageContent(msg.content);
    };

    const handleEditCancel = () => {
        setEditingMessageId(null);
        setEditingMessageContent('');
    };

    const handleEditSubmit = () => {
        if (!editingMessageId || !editingMessageContent.trim()) return;
        const messageToSend = editingMessageContent.trim();
        const result = useChatStore.getState().editMessage(editingMessageId, messageToSend);
        if (result?.success) {
            // Clear edit state immediately, then send the edited message
            setEditingMessageId(null);
            setEditingMessageContent('');
            // Use requestAnimationFrame to let React state settle before re-sending
            requestAnimationFrame(() => {
                handleSendMessage(messageToSend);
            });
        } else {
            setEditingMessageId(null);
            setEditingMessageContent('');
        }
    };

    if (!selectedDataset && !isOpen) return null;

    return (
        <div
            className={cn(
                embedded ? "chat-panel--embedded" : "chat-panel",
                !isOpen && "closed",
                !isOpen && "hidden pointer-events-none",
                isResizing && "resizing",
                className
            )}
            style={{
                width: isOpen ? `${width}px` : '0px',
                display: isOpen ? 'flex' : 'none',
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
                <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                        {modeConfig.icon} {modeConfig.label}
                    </span>
                    <span
                        title={isConnected ? "Connected" : "Disconnected"}
                        className={cn(
                            "chat-connection-dot",
                            isConnected ? "chat-connection-dot--connected" : "chat-connection-dot--disconnected"
                        )}
                    />
                </div>
                <div className="flex items-center gap-0.5">
                    {selectedDataset && (
                        <button onClick={() => startNewConversation(selectedDataset.id)} className="chat-toolbar-btn" title="New Chat"><Plus size={16} /></button>
                    )}
                    <button onClick={() => setShowHistoryModal(true)} className="chat-toolbar-btn" title="History"><History size={16} /></button>
                    <div className="w-px h-3.5 bg-white/[0.06] mx-1" />
                    <button onClick={onClose} className="chat-toolbar-btn" title="Close"><X size={16} /></button>
                </div>
            </header>

            {/* ── Messages ── */}
            <div className="chat-messages">
                {!selectedDataset ? (
                    <div className="chat-empty">
                        <div className="mx-auto mb-5">
                            <Logo size={48} />
                        </div>
                        <h3 className="text-xl font-semibold text-[var(--text-primary)] mb-2">No dataset selected</h3>
                        <p className="text-[14px] text-[var(--text-secondary)] max-w-xs mx-auto leading-relaxed">
                            Select a dataset from the sidebar or dashboard to start analyzing with AI.
                        </p>
                    </div>
                ) : messages.length === 0 ? (
                    <div className="chat-empty">
                        {chartContext?.chartImage && (
                            <div style={{ padding: '0 16px', marginBottom: 12, width: '100%' }}>
                                <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid rgba(202,210,253,0.08)', background: '#020203' }}>
                                    <img src={chartContext.chartImage} alt="Chart" style={{ width: '100%', height: 'auto', display: 'block', opacity: 0.9 }} />
                                </div>
                            </div>
                        )}
                        <div className="mx-auto mb-4">
                            <Logo size={40} />
                        </div>
                        <h3 className="text-2xl font-semibold text-[var(--text-primary)] tracking-tight mb-2">
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
                                : datasetSuggestions.map(s => {
                                    const Comp = s.icon;
                                    return (
                                        <button key={s.text} onClick={() => handleSendMessage(s.text)} className="chat-suggestion-chip flex items-center gap-1.5">
                                            <Comp size={12} className="opacity-60" />{s.text}
                                        </button>
                                    );
                                })}
                            
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col pb-4">
                        {chartContext && (
                            <motion.div
                                initial={{ opacity: 0, y: -8 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="chat-context-banner"
                            >
                                {chartContext.chartImage && (
                                    <div style={{ background: '#020203', borderBottom: '1px solid rgba(91,136,178,0.12)' }}>
                                        <img src={chartContext.chartImage} alt="Chart context" style={{ width: '100%', height: 80, objectFit: 'cover', display: 'block', opacity: 0.85 }} />
                                    </div>
                                )}
                                <div className="chat-context-banner__body">
                                    <Logo size={14} />
                                    <div className="flex-1 min-w-0">
                                        <p className="chat-context-banner__text">Chart context loaded</p>
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
                        {messages.map((msg, i) => {
                            const visibleMsg = getVisibleMessage(msg, messages);
                            const versions = visibleMsg._versions || [];
                            const parentId = visibleMsg._parentId || '';
                            const currentIdx = visibleMsg._versionIndex ?? 0;
                            return (
                                <React.Fragment key={msg.id || i}>
                                    {i > 0 && msg.role !== messages[i - 1]?.role && (
                                        <div className="chat-separator" />
                                    )}
                                    <ChatMessage
                                        msg={visibleMsg}
                                        isUser={visibleMsg.role === 'user'}
                                        index={i}
                                        toggleTechnicalDetails={(id) => setExpandedTechnicalDetails(p => ({ ...p, [id]: !p[id] }))}
                                        expandedTechnicalDetails={expandedTechnicalDetails}
                                        onRerun={handleRerun}
                                        onSuggestionClick={(s) => handleSendMessage(s)}
                                        followUpOverride={followUpMap[visibleMsg.id] || null}
                                        msgMeta={msgMetaMap[visibleMsg.id] || null}
                                        onEditSql={(id) => {
                                            const m = messages.find(x => x.id === id);
                                            if (m?.sql) setSharedSqlContent(m.sql);
                                        }}
                                        onInsertSql={onInsertSql}
                                        onDismiss={handleDismissMessage}
                                        isDismissed={dismissedMessages.has(visibleMsg.id)}
                                        onPinToCanvas={onPinToCanvas}
                                        onEditStart={handleEditStart}
                                        isEditing={editingMessageId === visibleMsg.id}
                                        editContent={editingMessageContent}
                                        onEditChange={setEditingMessageContent}
                                        onEditSubmit={handleEditSubmit}
                                        onEditCancel={handleEditCancel}
                                        versions={versions}
                                        currentVersionIndex={currentIdx}
                                        onVersionSwitch={(idx) => handleVersionSwitch(parentId, idx)}
                                        onRegenerate={() => handleRegenerate(visibleMsg.id)}
                                    />
                                    {visibleMsg.role === 'assistant' && pendingBelief && i === messages.length - 1 && (
                                        <CorrectionCapture
                                            belief={pendingBelief}
                                            datasetId={selectedDataset?.id}
                                            onDismiss={() => setPendingBelief(null)}
                                        />
                                    )}
                                </React.Fragment>
                            );
                        })}
                        {isAITyping && (
                            <motion.div className="chat-message--ai" variants={msgVariants} initial="hidden" animate="visible">
                                <div className="chat-ai-row">
                                    <div className="chat-ai-avatar">
                                        <div className="chat-thinking__logo">
                                            <Logo size={18} />
                                        </div>
                                    </div>
                                    <div className="chat-ai-body">
                                        <div className="chat-ai-content">
                                            {streamingContent ? (                                                    <div className="relative inline-block chat-streaming-content">
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
                                                            } catch { /* ignore parse errors */ }
                                                            return sc;
                                                        })()}
                                                    </ReactMarkdown>
                                                    <span className="chat-streaming-cursor" />
                                                </div>
                                            ) : (
                                                <ModernReasoningBlock thinkingSteps={thinkingSteps} isStreaming={true} />
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
                <div className="chat-rate-limit">
                    {rateLimitCountdown !== null ? (
                        <div className="chat-rate-limit__countdown">
                            <span className="w-1.5 h-1.5 rounded-full bg-yellow-600 animate-pulse inline-block" />
                            Rate limit — resets in <strong>{rateLimitCountdown}s</strong>
                        </div>
                    ) : (
                        <div className="chat-rate-limit__bar">
                            <div className="chat-rate-limit__track">
                                <div
                                    className={cn(
                                        "chat-rate-limit__fill",
                                        rateLimitRemaining <= 3 ? "chat-rate-limit__fill--low" : "chat-rate-limit__fill--medium"
                                    )}
                                    style={{ width: `${(rateLimitRemaining / RATE_LIMIT_TOTAL) * 100}%` }}
                                />
                            </div>
                            <span className={cn(
                                "chat-rate-limit__text",
                                rateLimitRemaining <= 3 ? "chat-rate-limit__text--low" : "chat-rate-limit__text--medium"
                            )}>
                                {rateLimitRemaining}/{RATE_LIMIT_TOTAL}
                            </span>
                        </div>
                    )}
                </div>
            )}

            {/* ── Shared SQL Editor (persistent, not per-message) ── */}
            {sharedSqlContent && (
                <div className="border-t border-border bg-surface flex flex-col" style={{ maxHeight: '320px' }}>
                    <div className="flex items-center justify-between px-3 py-1.5 border-b border-border/50 bg-elevated/10">
                        <span className="text-[9.5px] font-bold text-header uppercase tracking-wider">SQL Editor</span>
                        <button
                            onClick={() => setSharedSqlContent(null)}
                            className="p-1 rounded-md text-muted/50 hover:text-header hover:bg-elevated/40 transition-all"
                            title="Close SQL Editor"
                        >
                            <X size={12} />
                        </button>
                    </div>
                    <div className="flex-1 min-h-0 overflow-hidden">
                        <SqlEditorPanel
                            initialSql={sharedSqlContent}
                            datasetId={selectedDataset?.id}
                            columns={selectedDataset?.column_names || selectedDataset?.columns || []}
                            isOpen={true}
                            compact={true}
                        />
                    </div>
                </div>
            )}

            {/* ── Input ── */}
            <div className="px-3 py-3">
                <ChatInput
                    value={inputMessage}
                    onChange={setInputMessage}
                    onSend={handleSendMessage}
                    onStop={handleStopGeneration}
                    isLoading={isAITyping}
                    placeholder={mode === 'sql_analyst' ? 'Ask to generate, debug, or explain SQL...' : 'Ask anything...'}
                />
            </div>

            <ChatHistoryModal isOpen={showHistoryModal} onClose={() => setShowHistoryModal(false)} currentConversationId={currentConversationId} onSelectConversation={(id) => { setCurrentConversation(id); setShowHistoryModal(false); }} />
        </div>
    );
};

export default SideChatPanel;
