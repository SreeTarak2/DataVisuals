import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Search, MessageSquare, Clock, Trash2, MoreVertical, Database, ExternalLink } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import GlassCard from './common/GlassCard';
import useDatasetStore from '../store/datasetStore';
import useChatStore from '../store/chatStore';
import { toast } from 'react-hot-toast';

const ChatHistoryModal = ({ isOpen, onClose }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedChats, setSelectedChats] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const { datasets } = useDatasetStore();
  const { conversations, clearConversation, setCurrentConversation, loadConversations, startNewChat } = useChatStore();
  const navigate = useNavigate();
  
  // Load conversations when modal opens
  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      loadConversations().finally(() => setLoading(false));
    }
  }, [isOpen, loadConversations]);
  
  // Get real chat history from the chat store
  const chatHistory = Object.values(conversations).map(conversation => {
    const dataset = datasets.find(d => d.id === conversation.datasetId);
    const messages = conversation.messages || [];
    const lastMessage = messages[messages.length - 1];
    
    return {
      id: conversation.id,
      title: `Chat with ${conversation.datasetName || dataset?.name || 'Unknown Dataset'}`,
      timestamp: conversation.createdAt,
      messageCount: messages.length,
      lastMessage: lastMessage?.content || 'No messages yet',
      datasetId: conversation.datasetId,
      datasetName: conversation.datasetName || dataset?.name || dataset?.filename || 'Unknown Dataset'
    };
  }).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)); // Sort by newest first

  const filteredChats = chatHistory.filter(chat =>
    chat.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    chat.datasetName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelectChat = (chatId, event) => {
    // If clicking on the main area (not on selection checkbox), open the conversation
    if (event.target.closest('.chat-open-area')) {
      handleOpenChat(chatId);
      return;
    }
    
    // Otherwise, handle selection for deletion
    const newSelected = new Set(selectedChats);
    if (newSelected.has(chatId)) {
      newSelected.delete(chatId);
    } else {
      newSelected.add(chatId);
    }
    setSelectedChats(newSelected);
  };

  const handleOpenChat = (chatId) => {
    try {
      // Set the current conversation in the store
      setCurrentConversation(chatId);
      
      // Navigate to the chat page with the conversation ID (correct route path)
      navigate(`/app/chat?chatId=${chatId}`);
      
      // Close the modal
      onClose();
      
      toast.success('Chat opened successfully');
    } catch (error) {
      console.error('Error opening chat:', error);
      toast.error('Failed to open chat');
    }
  };

  const handleNewChat = () => {
    try {
      // Start a new chat (clear current conversation)
      startNewChat();
      
      // Navigate to the chat page without a conversation ID
      navigate('/app/chat');
      
      // Close the modal
      onClose();
      
      toast.success('New chat started');
    } catch (error) {
      console.error('Error starting new chat:', error);
      toast.error('Failed to start new chat');
    }
  };

  const handleDeleteSelected = () => {
    if (selectedChats.size === 0) return;
    
    try {
      // Delete each selected conversation
      selectedChats.forEach(conversationId => {
        clearConversation(conversationId);
      });
      
      toast.success(`Deleted ${selectedChats.size} conversation${selectedChats.size > 1 ? 's' : ''}`);
      setSelectedChats(new Set());
    } catch (error) {
      console.error('Error deleting conversations:', error);
      toast.error('Failed to delete conversations');
    }
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInHours = (now - date) / (1000 * 60 * 60);
    
    if (diffInHours < 24) {
      return `${Math.floor(diffInHours)} hours ago`;
    } else if (diffInHours < 168) { // 7 days
      return `${Math.floor(diffInHours / 24)} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />
          
          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="relative w-full max-w-2xl mx-4"
          >
            <GlassCard className="p-4">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-xl font-bold text-foreground">Chat History</h2>
                  <p className="text-muted-foreground text-sm">
                    {loading ? 'Loading...' : `${filteredChats.length} conversation${filteredChats.length !== 1 ? 's' : ''}`}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleNewChat}
                    className="px-3 py-1.5 rounded-lg bg-primary/20 text-primary hover:bg-primary/30 transition-colors text-sm font-medium"
                  >
                    New Chat
                  </button>
                  <button
                    onClick={onClose}
                    className="p-2 rounded-lg hover:bg-accent/50 transition-colors"
                  >
                    <X className="w-4 h-4 text-muted-foreground" />
                  </button>
                </div>
              </div>

              {/* Search */}
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search conversations..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 rounded-lg glass-effect border border-border/50 text-foreground focus:ring-primary focus:border-primary transition-all text-sm"
                />
              </div>

              {/* Chat List */}
              <div className="max-h-96 overflow-y-auto space-y-2">
                {filteredChats.length === 0 ? (
                  <div className="text-center py-8">
                    <MessageSquare className="w-12 h-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                    <h3 className="text-sm font-medium text-foreground mb-1">
                      {searchQuery ? 'No conversations found' : 'No chat history'}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {searchQuery ? 'Try different search terms' : 'Start chatting to see history here'}
                    </p>
                  </div>
                ) : (
                  filteredChats.map((chat) => (
                    <motion.div
                      key={chat.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`p-4 rounded-2xl border transition-all ${
                        selectedChats.has(chat.id)
                          ? 'border-primary bg-primary/10'
                          : 'border-border/30 hover:border-border/50 hover:bg-accent/10'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Selection checkbox */}
                        <div 
                          className={`w-4 h-4 rounded-full border-2 mt-1 flex items-center justify-center cursor-pointer ${
                            selectedChats.has(chat.id)
                              ? 'border-primary bg-primary'
                              : 'border-border/50 hover:border-primary/50'
                          }`}
                          onClick={(e) => {
                            e.stopPropagation();
                            const newSelected = new Set(selectedChats);
                            if (newSelected.has(chat.id)) {
                              newSelected.delete(chat.id);
                            } else {
                              newSelected.add(chat.id);
                            }
                            setSelectedChats(newSelected);
                          }}
                        >
                          {selectedChats.has(chat.id) && (
                            <div className="w-2 h-2 bg-white rounded-full"></div>
                          )}
                        </div>
                        
                        {/* Chat content - clickable to open */}
                        <div 
                          className="flex-1 min-w-0 chat-open-area cursor-pointer"
                          onClick={(e) => handleSelectChat(chat.id, e)}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <h3 className="text-sm font-medium text-foreground truncate">
                              {chat.title}
                            </h3>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">
                                {formatTimestamp(chat.timestamp)}
                              </span>
                              <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                          </div>
                          
                          <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
                            {chat.lastMessage}
                          </p>
                          
                          <div className="flex items-center gap-4 text-xs text-muted-foreground">
                            <div className="flex items-center gap-1">
                              <MessageSquare className="w-3 h-3" />
                              <span>{chat.messageCount} messages</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <Database className="w-3 h-3" />
                              <span className="truncate max-w-32">{chat.datasetName}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>

              {/* Actions */}
              {selectedChats.size > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center justify-between mt-4 pt-4 border-t border-border/20"
                >
                  <span className="text-sm text-muted-foreground">
                    {selectedChats.size} selected
                  </span>
                  <button
                    onClick={handleDeleteSelected}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors text-sm"
                  >
                    <Trash2 className="w-3 h-3" />
                    Delete
                  </button>
                </motion.div>
              )}
            </GlassCard>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default ChatHistoryModal;