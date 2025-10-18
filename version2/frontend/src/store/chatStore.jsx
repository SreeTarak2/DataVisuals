import { create } from 'zustand';
import { aiAPI } from '../services/api';

const useChatStore = create((set, get) => ({
  conversations: {},
  currentConversationId: null,
  loading: false,
  error: null,
  
  // Actions
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  clearError: () => set({ error: null }),
  
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
      const { response: aiResponse, chart_config, metadata_used, rag_used } = response.data;
      const chart = chart_config; // Map chart_config to chart for compatibility
      
      // Debug logging
      console.log('AI Response:', aiResponse);
      console.log('Chart Config:', chart_config);
      console.log('Chart Data:', chart?.data);
      
      // Add AI response
      const aiMessage = {
        id: `msg_${Date.now()}_ai`,
        role: 'assistant',
        content: aiResponse,
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
  
  // Clear conversation
  clearConversation: (conversationId) => {
    set((state) => {
      const newConversations = { ...state.conversations };
      delete newConversations[conversationId];
      return {
        conversations: newConversations,
        currentConversationId: state.currentConversationId === conversationId ? null : state.currentConversationId
      };
    });
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
}));

export default useChatStore;