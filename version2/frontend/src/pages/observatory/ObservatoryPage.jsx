import React, { useState, useRef, useEffect, useCallback, memo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Send, Bot, User, Wifi, WifiOff, Loader2, Maximize2, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import ReactMarkdown from 'react-markdown'; // Ensure this is installed
import DOMPurify from 'dompurify'; // Ensure this is installed

import GlassPanel from '@/components/ui/GlassPanel';
import NeonButton from '@/components/ui/NeonButton';
import PlotlyChart from '@/components/features/charts/PlotlyChart';

import useChatStore from '@/store/chatStore';
import useDatasetStore from '@/store/datasetStore';
import useWebSocket from '@/hooks/useWebSocket';

// --- Chat Message Component ---
const ChatMessage = memo(({ msg, isUser }) => {
    return (
        <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className={`flex gap-3 mb-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
        >
            <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center border ${isUser ? 'bg-ocean/20 border-ocean/30 text-ocean' : 'bg-purple-500/20 border-purple-500/30 text-purple-400'
                }`}>
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            <div className={`flex flex-col max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
                <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${isUser
                    ? 'bg-ocean/10 border border-ocean/20 text-pearl rounded-tr-sm'
                    : 'bg-white/5 border border-white/10 text-gray-200 rounded-tl-sm'
                    }`}>
                    {isUser ? (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                    ) : (
                        <div className="prose prose-invert prose-sm max-w-none">
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                    )}
                </div>
                <div className="text-[10px] text-muted-foreground mt-1 px-1">
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
            </div>
        </motion.div>
    );
});

ChatMessage.displayName = 'ChatMessage';

// --- Observatory Component ---
// ... imports
import DeepAnalysisStory from '@/components/features/analysis/DeepAnalysisStory';
import { datasetAPI } from '@/services/api';

// ... existing code ...

const Observatory = () => {
    const { id } = useParams();
    const [searchParams, setSearchParams] = useSearchParams();
    const { selectedDataset, fetchDataset } = useDatasetStore();

    // Analysis State
    const [analysisResult, setAnalysisResult] = useState(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    // Chat Store Config
    const {
        getCurrentConversationMessages,
        sendMessage,
        loading,
        startNewConversation,
        isStreaming,
        streamingContent,
        startStreaming,
        appendStreamingToken,
        finishStreaming,
        cancelStreaming,
        currentConversationId,
        setCurrentConversation,
        loadConversations,
        getConversation
    } = useChatStore();

    const [inputMessage, setInputMessage] = useState('');
    const [activeChart, setActiveChart] = useState(null); // Chart config for right panel
    const messagesEndRef = useRef(null);
    const [streamingChartConfig, setStreamingChartConfig] = useState(null);

    // WebSocket Setup
    const { isConnected, connect, sendMessage: wsSendMessage } = useWebSocket({
        onToken: (token) => {
            appendStreamingToken(token);
            scrollToBottom();
        },
        onChart: (chartConfig) => {
            // Real-time chart updates
            setStreamingChartConfig(chartConfig);
            setActiveChart(chartConfig); // Auto-show chart in right panel (overrides narrative)
        },
        onDone: ({ conversationId, chartConfig }) => {
            const finalChart = chartConfig || streamingChartConfig;
            if (conversationId) setCurrentConversation(conversationId);
            finishStreaming(useChatStore.getState().streamingContent, finalChart);
            setStreamingChartConfig(null);
            if (finalChart) setActiveChart(finalChart);
        },
        onError: (error) => {
            cancelStreaming();
            toast.error("Connection Interrupted");
        },
        autoConnect: false
    });

    // Initialize & Auto-Trigger Analysis
    useEffect(() => {
        const init = async () => {
            if (id) {
                await fetchDataset(id); // Ensure dataset is loaded
                connect(); // Connect WS

                // Auto-trigger Deep Analysis if not already done
                if (!analysisResult && !isAnalyzing) {
                    setIsAnalyzing(true);
                    try {
                        console.log("Starting Deep Analysis...");
                        const result = await datasetAPI.analyzeDataset(id);
                        setAnalysisResult(result.data);
                    } catch (error) {
                        console.error("Analysis Failed:", error);
                        toast.error("Deep Analysis failed to initialize");
                    } finally {
                        setIsAnalyzing(false);
                    }
                }
            }
            await loadConversations();

            // Check for existing chat ID
            const chatId = searchParams.get('chatId');
            if (chatId) setCurrentConversation(chatId);
        };
        init();
    }, [id, fetchDataset, connect, loadConversations]);

    // Scroll handling
    const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    useEffect(() => scrollToBottom(), [getCurrentConversationMessages().length, isStreaming]);

    // Handle Sending
    const handleSendMessage = async (e) => {
        e.preventDefault();
        if (!inputMessage.trim() || loading || isStreaming) return;

        const message = inputMessage.trim();
        setInputMessage('');

        let convId = currentConversationId;
        if (!convId) {
            convId = startNewConversation(id);
            // Update URL
            const newParams = new URLSearchParams(searchParams);
            newParams.set('chatId', convId);
            setSearchParams(newParams);
        }

        // Add user message locally
        useChatStore.getState().addMessage(convId, {
            id: `msg_${Date.now()}_user`,
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });

        // Send via WebSocket if active, else HTTP
        if (isConnected) {
            startStreaming(`msg_${Date.now()}_ai`);
            wsSendMessage({
                message,
                datasetId: id,
                conversationId: convId,
                streaming: true
            });
        } else {
            // Fallback to HTTP (Simplified for this demo)
            await sendMessage(message, id, convId);
        }
    };

    // Extract chart from latest AI message if available and no active chart
    const messages = getCurrentConversationMessages();
    useEffect(() => {
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && !lastMsg.isUser && lastMsg.chart_config && !activeChart && !isStreaming) {
            setActiveChart(lastMsg.chart_config);
        }
    }, [messages, activeChart, isStreaming]);

    return (
        <div className="relative h-screen w-full flex overflow-hidden bg-noir">
            {/* Left Side: Chat Interface */}
            <div className="w-[400px] h-full flex flex-col z-20 border-r border-white/5 bg-noir/50 backdrop-blur-md">
                {/* Header */}
                <div className="p-4 border-b border-white/10 bg-midnight/20">
                    <div className="flex items-center justify-between mb-1">
                        <div className="text-xs font-bold tracking-[0.2em] text-ocean">OBSERVATORY LINK</div>
                        <div className={`flex items-center gap-1 text-[10px] ${isConnected ? 'text-emerald-400' : 'text-amber-400'}`}>
                            {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                            {isConnected ? 'ONLINE' : 'OFFLINE'}
                        </div>
                    </div>
                    <div className="text-pearl font-bold truncate text-sm">{selectedDataset?.name || 'INITIALIZING...'}</div>
                    {/* Agent Status Indicator */}
                    {isAnalyzing && (
                        <div className="mt-2 text-[10px] text-purple-400 flex items-center gap-2 animate-pulse">
                            <div className="w-1.5 h-1.5 bg-purple-400 rounded-full" />
                            AGENTS BUSY: ANALYZING DATA...
                        </div>
                    )}
                </div>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-midnight scrollbar-track-transparent">
                    {messages.map((msg, idx) => (
                        <ChatMessage key={msg.id || idx} msg={msg} isUser={msg.role === 'user'} />
                    ))}

                    {/* Streaming Message */}
                    {isStreaming && (
                        <div className="flex gap-3 mb-4 flex-row">
                            <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center border bg-purple-500/20 border-purple-500/30 text-purple-400">
                                <Bot className="w-4 h-4" />
                            </div>
                            <div className="flex flex-col max-w-[85%] items-start">
                                <div className="px-4 py-3 rounded-2xl text-sm leading-relaxed bg-white/5 border border-white/10 text-gray-200 rounded-tl-sm">
                                    <div className="prose prose-invert prose-sm max-w-none">
                                        <ReactMarkdown>{streamingContent}</ReactMarkdown>
                                    </div>
                                    <span className="inline-block w-2 h-4 bg-ocean rounded-sm animate-pulse ml-1 align-middle" />
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4 border-t border-white/10 bg-midnight/30">
                    <form onSubmit={handleSendMessage} className="relative">
                        <input
                            type="text"
                            value={inputMessage}
                            onChange={(e) => setInputMessage(e.target.value)}
                            placeholder="TRANSMIT QUERY..."
                            disabled={loading || isStreaming}
                            className="w-full bg-black/50 border border-white/10 rounded-lg pl-4 pr-12 py-3 text-sm text-pearl focus:outline-none focus:border-ocean transition-all placeholder:text-muted-foreground"
                        />
                        <button
                            type="submit"
                            disabled={!inputMessage.trim() || loading || isStreaming}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-ocean hover:text-white hover:bg-ocean/20 transition-all disabled:opacity-50"
                        >
                            {loading || isStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        </button>
                    </form>
                </div>
            </div>

            {/* Right Side: Visualization Canvas OR Deep Analysis Story */}
            <div className="flex-1 h-full p-4 overflow-hidden relative bg-gradient-to-br from-noir to-midnight/20">
                {/* Grid Overlay */}
                <div
                    className="absolute inset-0 opacity-10 pointer-events-none"
                    style={{
                        backgroundImage: `linear-gradient(rgba(91, 136, 178, 0.2) 1px, transparent 1px), linear-gradient(90deg, rgba(91, 136, 178, 0.2) 1px, transparent 1px)`,
                        backgroundSize: '40px 40px'
                    }}
                />

                <AnimatePresence mode="wait">
                    {activeChart ? (
                        <motion.div
                            key="chart"
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            transition={{ duration: 0.5, ease: "circOut" }}
                            className="w-full h-full rounded-2xl border border-white/5 bg-black/40 backdrop-blur-sm relative overflow-hidden shadow-2xl"
                        >
                            <div className="absolute top-4 right-4 z-10 flex gap-2">
                                <NeonButton variant="secondary" className="!px-3 !py-1" onClick={() => setActiveChart(null)}>
                                    CLOSE CHART
                                </NeonButton>
                            </div>
                            <PlotlyChart
                                data={activeChart.data}
                                layout={activeChart.layout}
                                config={{ responsive: true, displayModeBar: false }}
                                style={{ width: '100%', height: '100%' }}
                            />
                        </motion.div>
                    ) : (
                        // Default View: Deep Analysis Story (Automatic)
                        <motion.div
                            key="story-container"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="w-full h-full rounded-2xl border border-white/5 bg-black/40 backdrop-blur-sm relative overflow-hidden shadow-2xl"
                        >
                            <DeepAnalysisStory
                                analysisResult={analysisResult}
                                isLoading={isAnalyzing}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default Observatory;
