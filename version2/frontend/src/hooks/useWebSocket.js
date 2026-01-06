import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * Helper to get auth token from Zustand persisted store
 */
const getAuthToken = () => {
    try {
        const stored = localStorage.getItem('datasage-auth');
        if (stored) {
            const parsed = JSON.parse(stored);
            return parsed?.state?.token || null;
        }
    } catch (e) {
        console.error('Failed to parse auth token:', e);
    }
    return null;
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
        return `${protocol}//${url.host}${path}/api/ws/chat`;
    } catch (err) {
        console.warn('Failed to compute WS URL:', err);
        return 'ws://localhost:8000/api/ws/chat';
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
    onDone,
    onError,
    onStatus,
    autoConnect = false
} = {}) => {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);
    const pendingMessagesRef = useRef(new Map()); // Track pending message callbacks

    const cleanup = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return;
        }

        const token = getAuthToken();
        if (!token) {
            onError?.({ type: 'auth', detail: 'Not authenticated' });
            return;
        }

        setIsConnecting(true);
        cleanup();

        // Note: Token in URL is a security concern - ideally move to message body
        // when backend supports it. For now, connection uses URL param.
        const wsUrl = `${WS_URL}?token=${token}`;

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
            setIsConnecting(false);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const { type, clientMessageId } = data;

                switch (type) {
                    case 'status':
                        onStatus?.(data);
                        break;

                    case 'token':
                        // Individual token received
                        onToken?.(data.content, clientMessageId);
                        break;

                    case 'response_complete':
                        // Full text response complete
                        onResponseComplete?.(data.fullResponse, clientMessageId);
                        break;

                    case 'chart':
                        // Chart data received
                        onChart?.(data.chartConfig, clientMessageId);
                        break;

                    case 'done':
                        // Entire processing complete
                        onDone?.({
                            conversationId: data.conversationId,
                            chartConfig: data.chartConfig,
                            clientMessageId
                        });
                        pendingMessagesRef.current.delete(clientMessageId);
                        break;

                    case 'assistant_message':
                        // Non-streaming full response (fallback)
                        onResponseComplete?.(data.message, clientMessageId);
                        if (data.chartConfig) {
                            onChart?.(data.chartConfig, clientMessageId);
                        }
                        onDone?.({
                            conversationId: data.conversationId,
                            chartConfig: data.chartConfig,
                            clientMessageId
                        });
                        pendingMessagesRef.current.delete(clientMessageId);
                        break;

                    case 'error':
                        onError?.(data);
                        pendingMessagesRef.current.delete(clientMessageId);
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
            onError?.({ type: 'connection', detail: 'Connection error' });
        };

        ws.onclose = (event) => {
            console.log('WebSocket closed:', event.code, event.reason);
            setIsConnected(false);
            setIsConnecting(false);
            wsRef.current = null;

            // If there are pending messages (mid-stream disconnect), notify error
            if (pendingMessagesRef.current.size > 0) {
                console.warn('WebSocket closed with pending messages:', pendingMessagesRef.current.size);
                onError?.({ type: 'disconnect', detail: 'Connection lost while processing' });
                pendingMessagesRef.current.clear();
            }

            // Auto-reconnect after 3 seconds if not intentionally closed
            if (event.code !== 1000) {
                console.log('Scheduling reconnect...');
                reconnectTimeoutRef.current = setTimeout(() => {
                    connect();
                }, 3000);
            }
        };
    }, [cleanup, onToken, onResponseComplete, onChart, onDone, onError, onStatus]);

    const disconnect = useCallback(() => {
        cleanup();
        setIsConnected(false);
    }, [cleanup]);

    const sendMessage = useCallback(({
        message,
        datasetId,
        conversationId = null,
        streaming = true
    }) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.error('WebSocket not connected');
            onError?.({ type: 'connection', detail: 'Not connected' });
            return null;
        }

        const clientMessageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        const payload = {
            clientMessageId,
            message,
            datasetId,
            conversationId,
            streaming
        };

        pendingMessagesRef.current.set(clientMessageId, { sentAt: Date.now() });
        wsRef.current.send(JSON.stringify(payload));

        return clientMessageId;
    }, [onError]);

    // Auto-connect on mount if enabled
    useEffect(() => {
        if (autoConnect) {
            connect();
        }
        return cleanup;
    }, [autoConnect, connect, cleanup]);

    return {
        isConnected,
        isConnecting,
        connect,
        disconnect,
        sendMessage
    };
};

export default useWebSocket;
