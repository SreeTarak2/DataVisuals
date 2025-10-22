import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Mic, Database, Sparkles, Copy, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { useSearchParams } from 'react-router-dom';
import { cn } from '../lib/utils';
import GlassCard from '../components/common/GlassCard';
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
    const [searchParams] = useSearchParams();
    const messagesEndRef = useRef(null);
    const [showSuggestions, setShowSuggestions] = useState(true);
    const [showHistoryModal, setShowHistoryModal] = useState(false);
    const [currentChatId, setCurrentChatId] = useState(null);
    const [expandedTechnicalDetails, setExpandedTechnicalDetails] = useState({});

    const messages = getCurrentConversationMessages();
    const isAITyping = loading;

    const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

    useEffect(() => {
        scrollToBottom();
        if (messages.length > 0) setShowSuggestions(false);
    }, [messages]);

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

    const handleSendMessage = async (e) => {
        e.preventDefault();
        if (!inputMessage.trim() || isAITyping || !selectedDataset?.id) return;

        const message = inputMessage.trim();
        setInputMessage('');
        setShowSuggestions(false);

        const result = await sendMessage(message, selectedDataset.id, currentChatId);
        if (result && !result.success) toast.error(result.error);
        if (result && result.conversationId) {
            setCurrentChatId(result.conversationId);
        }
    };

    const handleQuickReply = (reply) => {
        setInputMessage(reply);
        setShowSuggestions(false);
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

    const highlightImportantText = (text) => {
        if (!text) return '';
        const cleanText = text.replace(/<[^>]*>/g, '');
        return cleanText
            .replace(/(\d+\.?\d*%)/g, '<span class="text-blue-400 font-semibold">$1</span>')
            .replace(/(\$\d+[,.]?\d*)/g, '<span class="text-green-400 font-semibold">$1</span>')
            .replace(/\b(correlation|trend|pattern|insight|significant|increase|decrease)\b/gi, '<span class="text-purple-400 font-medium">$1</span>')
            .replace(/(["'])([^"']+)\1/g, '<span class="text-cyan-400 font-mono text-xs">$1$2$1</span>')
            .replace(/\n/g, '<br>');
    };

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
        <div className="h-full flex flex-col bg-gradient-to-b from-background to-muted/20">
            <div className="p-4 border-b border-border/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Bot className="w-6 h-6 text-primary" />
                    <div>
                        <h1 className="text-lg font-semibold text-foreground">AI Assistant</h1>
                        <p className="text-xs text-muted-foreground">Chatting about: {selectedDataset.name}</p>
                    </div>
                </div>
            </div>

            <div className="flex-1 flex justify-center overflow-hidden">
                <div className="w-full max-w-4xl flex flex-col">
                    <div className="flex-1 overflow-y-auto p-4 space-y-6">
                        <AnimatePresence>
                            {messages.map((msg, index) => (
                                <motion.div
                                    key={msg.id || index}
                                    layout
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className={cn("flex items-end gap-3", msg.role === 'user' ? 'justify-end' : 'justify-start')}
                                >
                                    {msg.role === 'assistant' && <Bot className="w-6 h-6 text-slate-400 flex-shrink-0" />}
                                    
                                    <div className={cn(
                                        "rounded-2xl p-4 max-w-xl shadow-lg",
                                        msg.role === 'user'
                                            ? 'bg-blue-600 text-white rounded-br-none'
                                            : 'bg-slate-700 text-slate-100 rounded-bl-none'
                                    )}>
                                        <div className="text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: highlightImportantText(msg.content) }} />
                                        
                                        {msg.chart_config && (
                                            <div className="mt-4 bg-slate-900/50 rounded-xl p-2 border border-slate-600/50">
                                                {msg.chart_config.data ? (
                                                    <PlotlyChart
                                                        data={msg.chart_config.data}
                                                        layout={{
                                                            paper_bgcolor: 'rgba(0,0,0,0)',
                                                            plot_bgcolor: 'rgba(0,0,0,0)',
                                                            font: { color: '#e2e8f0' },
                                                            height: 300,
                                                            margin: { t: 30, b: 40, l: 50, r: 10 },
                                                        }}
                                                        config={{ displayModeBar: false, responsive: true }}
                                                    />
                                                ) : (
                                                    <div className="h-[300px] flex items-center justify-center text-slate-400 text-xs">Chart data could not be generated.</div>
                                                )}
                                            </div>
                                        )}
                                        
                                        {msg.technical_details && (
                                            <div className="mt-3 pt-3 border-t border-slate-600/50">
                                                <button onClick={() => toggleTechnicalDetails(msg.id || index)} className="flex items-center gap-2 text-xs text-slate-400 hover:text-white">
                                                    {expandedTechnicalDetails[msg.id || index] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                                    Technical Explanation
                                                </button>
                                                <AnimatePresence>
                                                    {expandedTechnicalDetails[msg.id || index] && (
                                                        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                                                            <div className="mt-2 p-3 bg-slate-900/50 rounded text-xs text-slate-300 border border-slate-700" dangerouslySetInnerHTML={{ __html: highlightImportantText(msg.technical_details) }} />
                                                        </motion.div>
                                                    )}
                                                </AnimatePresence>
                                            </div>
                                        )}
                                        <div className="flex items-center justify-end gap-2 mt-2">
                                            <button onClick={() => copyToClipboard(msg.content)} className="text-slate-400 hover:text-white"><Copy size={12} /></button>
                                        </div>
                                    </div>

                                    {msg.role === 'user' && <User className="w-6 h-6 text-slate-400 flex-shrink-0" />}
                                </motion.div>
                            ))}
                        </AnimatePresence>

                        {isAITyping && (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-end gap-3">
                                <Bot className="w-6 h-6 text-slate-400 flex-shrink-0" />
                                <div className="rounded-2xl p-4 bg-slate-700 rounded-bl-none">
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

                    <motion.div layout className="p-4 border-t border-border/50">
                        <div className="w-full max-w-3xl mx-auto">
                            <form onSubmit={handleSendMessage}>
                                <div className="relative">
                                    <input
                                        type="text"
                                        value={inputMessage}
                                        onChange={(e) => setInputMessage(e.target.value)}
                                        placeholder={`Ask about ${selectedDataset.name}...`}
                                        className="w-full pl-4 pr-12 py-3 rounded-lg bg-slate-800/80 border border-slate-700 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        disabled={isAITyping}
                                    />
                                    <button
                                        type="submit"
                                        disabled={!inputMessage.trim() || isAITyping}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-blue-600 text-white disabled:bg-slate-600"
                                    >
                                        <Send size={16} />
                                    </button>
                                </div>
                            </form>
                        </div>
                    </motion.div>
                </div>
            </div>

            <ChatHistoryModal isOpen={showHistoryModal} onClose={() => setShowHistoryModal(false)} />
        </div>
    );
};

export default Chat;