import React, { useState } from 'react';
import { History, ChevronDown, MessageSquare, Clock } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import GlassCard from './common/GlassCard';

const ChatHistoryDropdown = ({ onOpenFullHistory }) => {
  const [isOpen, setIsOpen] = useState(false);
  
  // Mock chat history data - in real app, this would come from a store/API
  const chatHistory = [
    { id: 1, title: 'Sales Analysis', timestamp: '2 hours ago', messageCount: 12 },
    { id: 2, title: 'Customer Insights', timestamp: '1 day ago', messageCount: 8 },
    { id: 3, title: 'Revenue Trends', timestamp: '3 days ago', messageCount: 15 },
    { id: 4, title: 'Data Quality Check', timestamp: '1 week ago', messageCount: 6 }
  ];

  return (
    <div className="relative">
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg glass-effect border border-border/50 text-foreground hover:bg-accent/50 focus-visible-ring transition-all"
        aria-label="Chat history"
      >
        <History className="w-4 h-4" />
        <span className="text-sm font-medium">History</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="absolute right-0 mt-2 w-64 max-h-80 overflow-y-auto z-50"
          >
            <GlassCard className="py-2 shadow-2xl">
              <div className="px-4 py-2 border-b border-border/20">
                <h3 className="text-sm font-semibold text-foreground">Recent Chats</h3>
              </div>
              
              {chatHistory.length === 0 ? (
                <div className="px-4 py-6 text-center text-muted-foreground">
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No chat history yet</p>
                </div>
              ) : (
                <div className="py-1">
                  {chatHistory.map((chat) => (
                    <motion.button
                      key={chat.id}
                      whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                      className="w-full px-4 py-3 text-left hover:bg-accent/50 focus-visible-ring transition-colors"
                      onClick={() => {
                        // In real app, this would load the chat
                        setIsOpen(false);
                      }}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">
                            {chat.title}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <Clock className="w-3 h-3 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">
                              {chat.timestamp}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1 ml-2">
                          <MessageSquare className="w-3 h-3 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground">
                            {chat.messageCount}
                          </span>
                        </div>
                      </div>
                    </motion.button>
                  ))}
                </div>
              )}
              
              <div className="px-4 py-2 border-t border-border/20">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => {
                    setIsOpen(false);
                    onOpenFullHistory();
                  }}
                  className="w-full py-2 px-3 rounded-lg bg-primary/20 text-primary hover:bg-primary/30 transition-colors text-sm font-medium"
                >
                  View All History
                </motion.button>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ChatHistoryDropdown;