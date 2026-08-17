import { useState, useRef, useCallback, useEffect } from 'react';

const isBackendConversationId = (value) =>
    typeof value === 'string' && /^[a-f0-9]{24}$/i.test(value);

import useAuthStore from '../store/authStore';

/**
 * Read auth token from the in-memory Zustand auth store.
 * The token is no longer persisted in localStorage (HttpOnly cookie handles auth),
 * but we keep it in memory for WebSocket connections that need to pass the
 * token as a query parameter during the upgrade handshake.
 */
const getAuthToken = () => {
    try {
        return useAuthStore.getState()?.token || localStorage.getItem('token') || localStorage.getItem('auth_token') || null;
    } catch (e) {
        return null;
    }
};

/**
 * Compute WebSocket URL from API base URL
 */
const computeWsUrl = () => {
    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    const explicit = import.meta.env.VITE_WS_URL;

    if (explicit) return explicit;

    try {
        const url = new URL(apiBase);
        url.pathname = url.pathname.replace(/\/api\/?$/, '');
        const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
        const path = url.pathname.endsWith('/') ? url.pathname.slice(0, -1) : url.pathname;
        return `${protocol}//${url.host}${path}/api/ws`;
    } catch (err) {
        console.warn('Failed to compute WS URL:', err);
        return 'ws://localhost:8000/api/ws';
    }
};

const WS_URL = computeWsUrl();

/**
 * WebSocket hook for streaming chat responses
 * 
 * @param {Object} options
 * @param {Function} options.onToken - Called with each token received
 * @param {Function} options.onResponseComplete - Called when full response is received
 * @param {Function} options.onChart - Called when chart data is received
 * @param {Function} options.onDone - Called when entire processing is done
 * @param {Function} options.onError - Called on errors
 * @param {Function} options.onStatus - Called with status updates
 * @param {boolean} options.autoConnect - Whether to connect automatically
 */
export const useWebSocket = ({
    onToken,
    onResponseComplete,
    onChart,
    onChartError,
    onDone,
    onError,
    onStatus,
    onCleaningRedirect,
    onThinkingStep,
    onRenderIntent,
    onBeliefSaved,
    onCancelAck,
    onModePhases,
    onRegenerateComplete,
    onNotification,
    onProcessingUpdate,
    onSessionRevoked,
    autoConnect = false
} = {}) => {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const maxReconnectAttempts = 5;
    const pendingMessagesRef = useRef(new Map()); // Track pending message callbacks
    const intentionalCloseSocketsRef = useRef(new WeakSet());
    const heartbeatIntervalRef = useRef(null);
    const lastPongRef = useRef(null);

    const connectionTimeoutRef = useRef(null);
    const WS_CONNECT_TIMEOUT = 15000;

    const cleanup = useCallback(() => {
        if (connectionTimeoutRef.current) {
            clearTimeout(connectionTimeoutRef.current);
            connectionTimeoutRef.current = null;
        }
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        if (heartbeatIntervalRef.current) {
            clearInterval(heartbeatIntervalRef.current);
            heartbeatIntervalRef.current = null;
        }
        if (wsRef.current) {
            intentionalCloseSocketsRef.current.add(wsRef.current);
            wsRef.current.close(1000, 'client cleanup');
            wsRef.current = null;
        }
        pendingMessagesRef.current.clear();
    }, []);

    const connect = useCallback(async () => {
        if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
            return;
        }

        let token = getAuthToken();

        setIsConnecting(true);
        // Do not run full cleanup here; calling cleanup would intentionally
        // close any existing socket and can race with concurrent connect()
        // calls, causing the client to close sockets while the server is
        // streaming. Only create a new socket when none exists.

        const wsUrl = WS_URL;

        // If there's an existing socket in CLOSING state, wait briefly and retry
        if (wsRef.current && wsRef.current.readyState === WebSocket.CLOSING) {
            const retryDelay = 500;
            reconnectTimeoutRef.current = setTimeout(() => connect(), retryDelay);
            return;
        }

        const urlObj = new URL(wsUrl);
        if (token) {
            urlObj.searchParams.append("token", token);
        }
        const ws = new WebSocket(urlObj.toString());
        wsRef.current = ws;

        // Connection timeout: if onopen doesn't fire within 15s, abort
        connectionTimeoutRef.current = setTimeout(() => {
            if (wsRef.current === ws && ws.readyState === WebSocket.CONNECTING) {
                console.warn('WebSocket connection timed out after', WS_CONNECT_TIMEOUT, 'ms');
                intentionalCloseSocketsRef.current.add(ws);
                ws.close(4000, 'connection timeout');
                setIsConnecting(false);
                onError?.({ type: 'timeout', detail: 'Connection timed out. Check your network or try again.' });
            }
        }, WS_CONNECT_TIMEOUT);

        ws.onopen = async () => {
            // Connection established — clear the connect timeout
            if (connectionTimeoutRef.current) {
                clearTimeout(connectionTimeoutRef.current);
                connectionTimeoutRef.current = null;
            }
            // Send auth token if available for backwards compatibility
            if (token) {
                ws.send(JSON.stringify({ type: "auth", token }));
            }

            // Start application-level heartbeat to keep proxies alive and detect dead peers.
            if (heartbeatIntervalRef.current) {
                clearInterval(heartbeatIntervalRef.current);
            }
            lastPongRef.current = Date.now();
            heartbeatIntervalRef.current = setInterval(() => {
                try {
                    if (!ws || ws.readyState !== WebSocket.OPEN) return;
                    ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
                    // If we haven't received a pong in 60s, assume connection is dead and close to trigger reconnect
                    if (lastPongRef.current && Date.now() - lastPongRef.current > 60000) {
                        console.warn('No pong received in 60s — forcing close to trigger reconnect');
                        try { ws.close(4000, 'heartbeat timeout'); } catch (e) { /* ignore */ }
                    }
                } catch (e) {
                    console.warn('Heartbeat send failed', e);
                }
            }, 25000);
        };

        ws.onmessage = (event) => {
            try {
                // Optional raw debug logging when VITE_WS_DEBUG is truthy
                try {
                    const debugFlag = import.meta.env.VITE_WS_DEBUG;
                    if (debugFlag) console.debug('[WS RAW]', event.data);
                } catch {
                    // ignore in environments without import.meta
                }

                const data = JSON.parse(event.data);
                // Handle application-level pong
                if (data && data.type === 'pong') {
                    lastPongRef.current = Date.now();
                    return;
                }
                // Handle server-initiated ping (server heartbeat)
                if (data && data.type === 'server_ping') {
                    try {
                        ws.send(JSON.stringify({
                            type: 'server_pong',
                            timestamp: data.timestamp
                        }));
                    } catch (e) {
                        console.warn('Failed to send server_pong', e);
                    }
                    return;
                }
                const { type, clientMessageId } = data;
                const conversationId = data.conversationId ?? data.conversation_id ?? null;
                const chartConfig = data.chartConfig ?? data.chart_config ?? null;
                const resultTable = data.resultTable ?? data.result_table ?? null;
                const fullResponse = data.fullResponse ?? data.full_response ?? data.message ?? null;
                const followUpSuggestions = data.follow_up_suggestions ?? data.followUpSuggestions ?? [];
                const showFollowUpSuggestions = data.show_follow_up_suggestions ?? data.showFollowUpSuggestions ?? false;
                const dataSummary = data.data_summary ?? data.dataSummary ?? '';
                const rateLimitRemaining = data.rate_limit_remaining ?? data.rateLimitRemaining ?? null;
                const sqlFallback = data.sql_fallback ?? data.sqlFallback ?? false;
                const columnCorrections = data.column_corrections ?? data.columnCorrections ?? {};

                if (type === 'auth_success') {
                    setIsConnected(true);
                    setIsConnecting(false);
                    reconnectAttemptsRef.current = 0; // Reset backoff on successful auth
                    lastReconnectAttemptRef.current = 0; // Reset cooldown so focus handler can retry immediately if connection drops
                    return;
                }

                switch (type) {
                    case 'status':
                        onStatus?.(data);
                        break;

                    case 'token':
                        // Individual token received
                        onToken?.(data.content, clientMessageId);
                        break;

                    case 'stream_chunk':
                        // Backend wraps the real stream event inside `chunk`
                        if (data.chunk && typeof data.chunk === 'object') {
                            try {
                                const debugFlag = import.meta.env.VITE_WS_DEBUG;
                                if (debugFlag) console.debug('[WS CHUNK]', data.chunk.type, data.chunk);
                            } catch {
                                // ignore in environments without import.meta
                            }
                            const chunkType = data.chunk.type;

                            switch (chunkType) {
                                case 'token':
                                    onToken?.(data.chunk.content, clientMessageId);
                                    break;
                                case 'response_complete':
                                    onResponseComplete?.(data.chunk.full_response, clientMessageId);
                                    break;
                                case 'chart':
                                    onChart?.(data.chunk.chart_config ?? data.chunk.chartConfig, clientMessageId);
                                    break;
                                case 'thinking_step':
                                    onThinkingStep?.({
                                        label: data.chunk.label,
                                        step: data.chunk.step,
                                        detail: data.chunk.detail,
                                        source: data.chunk.source,
                                        evidence: data.chunk.evidence,
                                        phase: data.chunk.phase,
                                        confidence: data.chunk.confidence,
                                    });
                                    break;
                                case 'render_intent':
                                    onRenderIntent?.({
                                        show_chart: data.chunk.show_chart,
                                        show_table: data.chunk.show_table,
                                        show_sql:   data.chunk.show_sql,
                                        response_mode: data.chunk.response_mode,
                                    });
                                    break;
                                case 'cleaning_redirect':
                                    // Cleaning guard blocked the query — send the
                                    // user to the Data Briefing to review pending
                                    // number-changing cleaning actions.
                                    onCleaningRedirect?.({
                                        redirectTo: data.chunk.redirect_to ?? 'briefing',
                                        pendingCritical: data.chunk.pending_critical ?? 0,
                                        clientMessageId,
                                    });
                                    break;
                                case 'error':
                                    onError?.(data.chunk);
                                    break;
                                case 'done':
                                    onDone?.({
                                        conversationId: data.chunk.conversation_id ?? data.chunk.conversationId ?? conversationId,
                                        chartConfig: data.chunk.chart_config ?? data.chunk.chartConfig ?? null,
                                        resultTable: data.chunk.result_table ?? data.chunk.resultTable ?? null,
                                        sql: data.chunk.sql,
                                        insights: data.chunk.insights || [],
                                        data_summary: data.chunk.data_summary ?? '',
                                        follow_up_suggestions: data.chunk.follow_up_suggestions || [],
                                        show_follow_up_suggestions: data.chunk.show_follow_up_suggestions ?? data.chunk.showFollowUpSuggestions ?? false,
                                        rate_limit_remaining: data.chunk.rate_limit_remaining ?? null,
                                        sql_fallback: data.chunk.sql_fallback ?? false,
                                        column_corrections: data.chunk.column_corrections ?? {},
                                        render_intent: data.chunk.render_intent ?? null,
                                        clientMessageId
                                    });
                                    pendingMessagesRef.current.delete(clientMessageId);
                                    break;
                                default:
                                    console.warn('Unknown streamed chunk type:', chunkType, data.chunk);
                            }
                        }
                        break;

                    case 'response_complete':
                        // Full text response complete
                        onResponseComplete?.(fullResponse, clientMessageId);
                        break;

                    case 'stream_end':
                        // Backward-compatible end event when the backend streams chunks
                        onResponseComplete?.(fullResponse, clientMessageId);
                        break;

                    case 'chart':
                        // Chart data received
                        onChart?.(chartConfig, clientMessageId);
                        break;

                    case 'chart_error':
                        onChartError?.(data.reason, clientMessageId);
                        break;

                    case 'done':
                        // Entire processing complete
                        onDone?.({
                            conversationId,
                            chartConfig,
                            resultTable,
                            sql: data.sql,
                            insights: data.insights || [],
                            data_summary: dataSummary,
                            follow_up_suggestions: followUpSuggestions,
                            show_follow_up_suggestions: showFollowUpSuggestions,
                            rate_limit_remaining: rateLimitRemaining,
                            sql_fallback: sqlFallback,
                            column_corrections: columnCorrections,
                            render_intent: data.render_intent ?? null,
                            clientMessageId
                        });
                        pendingMessagesRef.current.delete(clientMessageId);
                        break;

                    case 'assistant_message':
                        // Non-streaming full response (fallback)
                        onResponseComplete?.(data.message, clientMessageId);
                        if (chartConfig) {
                            onChart?.(chartConfig, clientMessageId);
                        }
                        onDone?.({
                            conversationId: conversationId ?? data.conversationId ?? null,
                            chartConfig,
                            resultTable,
                            sql: data.sql,
                            insights: data.insights || [],
                            data_summary: dataSummary,
                            follow_up_suggestions: followUpSuggestions,
                            show_follow_up_suggestions: showFollowUpSuggestions,
                            rate_limit_remaining: rateLimitRemaining,
                            sql_fallback: sqlFallback,
                            column_corrections: columnCorrections,
                            clientMessageId
                        });
                        pendingMessagesRef.current.delete(clientMessageId);
                        break;

                    case 'thinking_step':
                        onThinkingStep?.({
                            label: data.label,
                            step: data.step,
                            detail: data.detail,
                            source: data.source,
                            evidence: data.evidence,
                            phase: data.phase,
                            confidence: data.confidence,
                        });
                        break;

                    case 'error':
                        onError?.(data);
                        pendingMessagesRef.current.delete(clientMessageId);
                        break;

                    case 'belief_saved':
                        console.log('Belief saved from correction:', data.belief?.content);
                        onBeliefSaved?.(data.belief, clientMessageId);
                        break;

                    case 'notification':
                        // Real-time job notification (dataset ready / failed / resumed)
                        onNotification?.(data.notification ?? data, clientMessageId);
                        break;

                    case 'processing_update':
                        // Live pipeline progress (stage / status / percent)
                        onProcessingUpdate?.({
                            datasetId: data.dataset_id ?? data.datasetId,
                            status: data.status,
                            progress: data.progress,
                            stageLabel: data.stage_label ?? data.stageLabel,
                        });
                        break;

                    case 'session_revoked':
                        // This session was revoked server-side (logout on
                        // another device) — force the app back to login.
                        onSessionRevoked?.();
                        break;

                    case 'cancel_ack':
                        console.log('Cancel acknowledged:', clientMessageId);
                        onCancelAck?.(clientMessageId);
                        break;

                    case 'regenerate_complete':
                        console.log('Regenerate complete:', clientMessageId, 'version:', data.versionMessageId);
                        onRegenerateComplete?.({
                            versionMessageId: data.versionMessageId,
                            clientMessageId: data.clientMessageId,
                        });
                        break;

                    case 'mode_phases':
                        // Phase roadmap for the current copilot mode
                        onModePhases?.({
                            label: data.label,
                            phases: data.phases,
                            total_phases: data.total_phases,
                        });
                        break;

                    case 'stream_start':
                    case 'stream_end':
                        // Backend lifecycle events — no frontend action needed
                        break;

                    default:
                        console.warn('Unknown WebSocket message type:', type);
                }
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setIsConnecting(false);
            // Don't fire error callback here - let onclose handle it
            // onerror always fires before onclose, so we avoid duplicate error toasts
        };

        ws.onclose = (event) => {
            console.log('WebSocket closed:', event.code, event.reason);
            // Clear connection timeout if it fired before onclose
            if (connectionTimeoutRef.current) {
                clearTimeout(connectionTimeoutRef.current);
                connectionTimeoutRef.current = null;
            }
            const wasIntentionalClose = intentionalCloseSocketsRef.current.has(ws);
            if (wasIntentionalClose) {
                intentionalCloseSocketsRef.current.delete(ws);
            }
            const isCurrentSocket = wsRef.current === ws;

            if (!isCurrentSocket) {
                return;
            }

            setIsConnected(false);
            setIsConnecting(false);
            wsRef.current = null;

            // If there are pending messages AND it was an abnormal close, notify error
            if (pendingMessagesRef.current.size > 0 && !wasIntentionalClose && event.code !== 1000 && event.code !== 1001) {
                console.warn('WebSocket closed abnormally with pending messages:', pendingMessagesRef.current.size);
                onError?.({ type: 'disconnect', detail: 'Connection lost while processing' });
            }

            pendingMessagesRef.current.clear();

            if (wasIntentionalClose) {
                return;
            }

            // Do NOT reconnect for policy violations or connection limits
            // 1008 = policy violation (auth failure), 4008 = connection limit exceeded
            if (event.code === 1008 || event.code === 4008) {
                // Auth/policy failure — stop silently, HTTP REST will handle messages
                console.warn('WebSocket rejected (auth/policy), falling back to HTTP REST');
                return;
            }
            // 1006 = abnormal closure (server not accepting WS at all)
            // Limit retries to avoid log spam; HTTP REST fallback will handle chat.
            const maxAttempts = event.code === 1006 ? 2 : maxReconnectAttempts;
            if (reconnectAttemptsRef.current < maxAttempts) {
                const delay = Math.min(2000 * Math.pow(2, reconnectAttemptsRef.current), 16000);
                reconnectAttemptsRef.current += 1;
                console.log(`Scheduling reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxAttempts})...`);
                reconnectTimeoutRef.current = setTimeout(() => {
                    connect();
                }, delay);
            } else {
                // Silently give up — HTTP REST fallback handles all chat
                console.warn('WebSocket unavailable, using HTTP REST for chat.');
            }
        };
    }, [cleanup,    onToken,
    onResponseComplete,
    onChart,
    onDone,
    onError,
    onStatus,
    onCleaningRedirect, onChartError, onThinkingStep, onRenderIntent, onBeliefSaved, onCancelAck, onNotification, onProcessingUpdate, onSessionRevoked]);

    const disconnect = useCallback(() => {
        reconnectAttemptsRef.current = 0;
        cleanup();
        setIsConnected(false);
    }, [cleanup]);

    const sendMessage = useCallback(({
        message,
        datasetId,
        conversationId = null,
        streaming = true,
        mode = 'analyst',
        archetype = 'explorer'
    }) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.warn('WebSocket not connected, message will be sent via HTTP REST');
            return null;
        }

        const clientMessageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        const payload = {
            type: 'chat_message',
            clientMessageId,
            payload: {
                message,
                datasetId,
                conversationId: isBackendConversationId(conversationId) ? conversationId : null,
                streaming,
                mode,
                archetype
            }
        };

        pendingMessagesRef.current.set(clientMessageId, { sentAt: Date.now() });
        wsRef.current.send(JSON.stringify(payload));

        return clientMessageId;
    }, [onError, wsRef]);

    const sendCancel = useCallback((clientMessageId) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.warn('Cannot cancel - WebSocket not connected');
            return false;
        }

        const payload = {
            type: 'cancel',
            clientMessageId,
            timestamp: Date.now()
        };

        wsRef.current.send(JSON.stringify(payload));
        console.log('Cancel request sent for:', clientMessageId);
        return true;
    }, []);

    const sendRegenerate = useCallback(({ conversationId, messageId, datasetId }) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.warn('WebSocket not connected, cannot regenerate');
            return null;
        }

        const clientMessageId = `regen_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        const payload = {
            type: 'regenerate',
            clientMessageId,
            payload: {
                conversationId,
                messageId,
                datasetId,
            }
        };

        pendingMessagesRef.current.set(clientMessageId, { sentAt: Date.now() });
        wsRef.current.send(JSON.stringify(payload));

        return clientMessageId;
    }, []);

    // Auto-connect on mount if enabled
    useEffect(() => {
        if (autoConnect) {
            connect();
        }
    }, [autoConnect, connect]);

    // Reconnect when the tab becomes visible or window regains focus.
    // Uses a cooldown ref (not state) to prevent rapid reconnection loops
    // when multiple focus events fire or the internal retry backoff races
    // with these handlers. Reconnects at most once per 5s regardless of
    // how many times the user alt-tabs or clicks back.
    const lastReconnectAttemptRef = useRef(0);
    const MIN_RECONNECT_INTERVAL = 5000;

    useEffect(() => {
        const onVisibility = () => {
            if (document.visibilityState === 'visible' && !isConnected) {
                const now = Date.now();
                if (now - lastReconnectAttemptRef.current > MIN_RECONNECT_INTERVAL) {
                    lastReconnectAttemptRef.current = now;
                    console.debug('Tab became visible — attempting WS reconnect');
                    connect();
                }
            }
        };
        const onFocus = () => {
            if (!isConnected) {
                const now = Date.now();
                if (now - lastReconnectAttemptRef.current > MIN_RECONNECT_INTERVAL) {
                    lastReconnectAttemptRef.current = now;
                    console.debug('Window focused — attempting WS reconnect');
                    connect();
                }
            }
        };
        document.addEventListener('visibilitychange', onVisibility);
        window.addEventListener('focus', onFocus);
        return () => {
            document.removeEventListener('visibilitychange', onVisibility);
            window.removeEventListener('focus', onFocus);
        };
    }, [isConnected, connect]);

    // Always close the socket on unmount, but avoid closing/reopening it on every
    // render when callback identities change during streaming.
    useEffect(() => cleanup, [cleanup]);

    return {
        isConnected,
        isConnecting,
        connect,
        disconnect,
        sendMessage,
        sendCancel,
        sendRegenerate
    };
};

export default useWebSocket;
