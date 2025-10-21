import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { aiAPI, chatAPI } from '../services/api';

const useChatStore = create(
  persist(
    (set, get) => ({
      conversations: {},
      currentConversationId: null,
      loading: false,
      error: null,
      
      // Actions
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),
      
      // Load conversations from database
      loadConversations: async () => {
        try {
          set({ loading: true, error: null });
          const response = await chatAPI.getConversations();
          const dbConversations = response.data.conversations || [];
          
          // Convert database format to store format
          const conversations = {};
          dbConversations.forEach(conv => {
            conversations[conv._id] = {
              id: conv._id,
              datasetId: conv.dataset_id,
              datasetName: conv.dataset_name,
              messages: conv.messages || [],
              createdAt: conv.created_at,
              updatedAt: conv.updated_at || conv.created_at
            };
          });
          
          set({ conversations, loading: false });
          return conversations;
        } catch (error) {
          console.error('Failed to load conversations:', error);
          set({ error: 'Failed to load chat history', loading: false });
          return {};
        }
      },
  
  // Start new conversation
  startNewConversation: (datasetId) => {
    const conversationId = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    set((state) => ({
      conversations: {
        ...state.conversations,
        [conversationId]: {
          id: conversationId,
          datasetId,
          messages: [],
          createdAt: new Date().toISOString(),
        }
      },
      currentConversationId: conversationId
    }));
    return conversationId;
  },
  
  // Send message
  sendMessage: async (message, datasetId, conversationId = null) => {
    set({ loading: true, error: null });
    
    // Get or create conversation
    let currentConvId = conversationId || get().currentConversationId;
    if (!currentConvId) {
      currentConvId = get().startNewConversation(datasetId);
    }
    
    // Add user message immediately
    const userMessage = {
      id: `msg_${Date.now()}_user`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };
    
    // Add user message to conversation immediately
    set((state) => ({
      conversations: {
        ...state.conversations,
        [currentConvId]: {
          ...state.conversations[currentConvId],
          messages: [
            ...(state.conversations[currentConvId]?.messages || []),
            userMessage
          ]
        }
      }
    }));
    
    try {
      const response = await aiAPI.processChat(datasetId, message, conversationId);
      const { response: aiResponse, technical_details, chart_config, metadata_used, rag_used } = response.data;
      const chart = chart_config; // Map chart_config to chart for compatibility
      
      // Debug logging
      console.log('AI Response:', aiResponse);
      console.log('Technical Details:', technical_details);
      console.log('Chart Config:', chart_config);
      console.log('Chart Data:', chart?.data);
      
      // Add AI response
      const aiMessage = {
        id: `msg_${Date.now()}_ai`,
        role: 'assistant',
        content: aiResponse,
        technical_details: technical_details || null,
        chart: chart || null,
        metadata_used: metadata_used || false,
        rag_used: rag_used || false,
        timestamp: new Date().toISOString(),
      };
      
      set((state) => ({
        conversations: {
          ...state.conversations,
          [currentConvId]: {
            ...state.conversations[currentConvId],
            messages: [
              ...(state.conversations[currentConvId]?.messages || []),
              aiMessage
            ]
          }
        },
        loading: false
      }));
      
      return { success: true, conversationId: currentConvId };
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || 'Failed to send message', 
        loading: false 
      });
      return { success: false, error: error.response?.data?.detail || 'Failed to send message' };
    }
  },
  
  // Get conversation messages
  getConversationMessages: (conversationId) => {
    const conversation = get().conversations[conversationId];
    return conversation ? conversation.messages : [];
  },
  
  // Get current conversation messages
  getCurrentConversationMessages: () => {
    const { currentConversationId, conversations } = get();
    return currentConversationId ? conversations[currentConversationId]?.messages || [] : [];
  },
  
  // Set current conversation
  setCurrentConversation: (conversationId) => {
    set({ currentConversationId: conversationId });
  },
  
  // Clear conversation (delete from both store and database)
  clearConversation: async (conversationId) => {
    try {
      // Delete from database
      await chatAPI.deleteConversation(conversationId);
      
      // Remove from store
      set((state) => {
        const newConversations = { ...state.conversations };
        delete newConversations[conversationId];
        return {
          conversations: newConversations,
          currentConversationId: state.currentConversationId === conversationId ? null : state.currentConversationId
        };
      });
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      // Still remove from store even if database deletion fails
      set((state) => {
        const newConversations = { ...state.conversations };
        delete newConversations[conversationId];
        return {
          conversations: newConversations,
          currentConversationId: state.currentConversationId === conversationId ? null : state.currentConversationId
        };
      });
    }
  },
  
  // Start a new chat (clear current conversation)
  startNewChat: () => {
    set({ currentConversationId: null });
  },
  
  // Clear all conversations
  clearAllConversations: () => {
    set({ conversations: {}, currentConversationId: null });
  },
  
  // Get conversation by ID
  getConversation: (conversationId) => {
    return get().conversations[conversationId] || null;
  },
  
  // Get all conversations for a dataset
  getDatasetConversations: (datasetId) => {
    const conversations = get().conversations;
    return Object.values(conversations).filter(conv => conv.datasetId === datasetId);
  },
}),
{
  name: 'datasage-chat-store', // unique name for localStorage key
  partialize: (state) => ({
    conversations: state.conversations,
    currentConversationId: state.currentConversationId
  }), // only persist these fields
}
));

export default useChatStore;