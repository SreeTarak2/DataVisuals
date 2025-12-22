import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { aiAPI, chatAPI } from '../services/api';

const DEFAULT_API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const computeHttpBase = () => {
  try {
    const url = new URL(DEFAULT_API_BASE);
    url.pathname = url.pathname.replace(/\/api\/?$/, '');
    return url;
  } catch (err) {
    console.warn('Failed to parse API base URL, falling back to defaults:', err);
    return new URL('http://localhost:8000');
  }
};

const WS_URL = (() => {
  const explicit = import.meta.env.VITE_WS_URL;
  if (explicit) return explicit;
  const baseUrl = computeHttpBase();
  const protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  const path = baseUrl.pathname.endsWith('/') ? baseUrl.pathname.slice(0, -1) : baseUrl.pathname;
  return `${protocol}//${baseUrl.host}${path}/ws/chat`;
})();

const useChatStore = create(
  persist(
    (set, get) => ({
      conversations: {},
      currentConversationId: null,
      loading: false,
      error: null,

      // Streaming state
      streamingMessageId: null,   // ID of message currently being streamed
      streamingContent: '',       // Accumulated streamed content
      isStreaming: false,         // Whether currently receiving stream

      // Actions
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),

      // Streaming actions
      startStreaming: (messageId) => set({
        streamingMessageId: messageId,
        streamingContent: '',
        isStreaming: true,
        loading: true
      }),

      appendStreamingToken: (token) => set(state => ({
        streamingContent: state.streamingContent + token
      })),

      finishStreaming: (fullContent, chartConfig = null) => {
        const state = get();
        const { currentConversationId, streamingMessageId } = state;

        if (!currentConversationId) {
          set({ isStreaming: false, streamingMessageId: null, streamingContent: '', loading: false });
          return;
        }

        // Create the final AI message
        const aiMessage = {
          id: streamingMessageId || `msg_${Date.now()}_ai`,
          role: 'assistant',
          content: fullContent,
          chart_config: chartConfig,
          timestamp: new Date().toISOString(),
        };

        // Add to conversation
        set(state => ({
          conversations: {
            ...state.conversations,
            [currentConversationId]: {
              ...state.conversations[currentConversationId],
              messages: [
                ...(state.conversations[currentConversationId]?.messages || []),
                aiMessage
              ]
            }
          },
          isStreaming: false,
          streamingMessageId: null,
          streamingContent: '',
          loading: false
        }));
      },

      cancelStreaming: () => set({
        isStreaming: false,
        streamingMessageId: null,
        streamingContent: '',
        loading: false
      }),

      // Message editing action
      editMessage: (messageId, newContent, conversationId) => {
        const state = get();
        const convId = conversationId || state.currentConversationId;

        if (!convId || !state.conversations[convId]) {
          console.error('Cannot edit message: conversation not found');
          return null;
        }

        const conversation = state.conversations[convId];
        const messageIndex = conversation.messages.findIndex(m => m.id === messageId);

        if (messageIndex === -1) {
          console.error('Cannot edit message: message not found');
          return null;
        }

        const originalMessage = conversation.messages[messageIndex];

        // Only allow editing user messages
        if (originalMessage.role !== 'user') {
          console.error('Cannot edit non-user messages');
          return null;
        }

        // Create edited message with history tracking
        const editedMessage = {
          ...originalMessage,
          content: newContent,
          isEdited: true,
          editHistory: [
            ...(originalMessage.editHistory || []),
            {
              content: originalMessage.content,
              editedAt: new Date().toISOString()
            }
          ],
          originalContent: originalMessage.originalContent || originalMessage.content
        };

        // Truncate all messages after the edited one (they become invalid)
        const truncatedMessages = conversation.messages.slice(0, messageIndex);
        truncatedMessages.push(editedMessage);

        // Update the conversation
        set(state => ({
          conversations: {
            ...state.conversations,
            [convId]: {
              ...state.conversations[convId],
              messages: truncatedMessages,
              updatedAt: new Date().toISOString()
            }
          }
        }));

        // Return the new content so caller can re-send
        return {
          success: true,
          newContent,
          conversationId: convId,
          truncatedCount: conversation.messages.length - messageIndex - 1
        };
      },

      // Load conversations from database
      loadConversations: async () => {
        try {
          set({ loading: true, error: null });
          const response = await chatAPI.getConversations();
          const dbConversations = response.data.conversations || [];

          console.log('Loaded conversations from backend:', dbConversations);

          // Convert database format to store format
          const conversations = {};
          dbConversations.forEach(conv => {
            // Map backend message format to frontend format
            const messages = (conv.messages || []).map((msg, idx) => ({
              id: msg.id || `msg_${conv._id}_${idx}`,
              role: msg.role === 'ai' ? 'assistant' : msg.role, // Map "ai" to "assistant"
              content: msg.content,
              chart_config: msg.chart_config || null,
              technical_details: msg.technical_details || null,
              timestamp: msg.timestamp || conv.created_at
            }));

            conversations[conv._id] = {
              id: conv._id,
              datasetId: conv.dataset_id,
              datasetName: conv.dataset_name,
              messages: messages,
              createdAt: conv.created_at,
              updatedAt: conv.updated_at || conv.created_at
            };
          });

          console.log('Mapped conversations:', conversations);

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

        // Get or create conversation (use temporary ID if new)
        let currentConvId = conversationId || get().currentConversationId;
        const isNewConversation = !currentConvId;
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

          // Backend returns: { response, chart_config, conversation_id }
          const backendConvId = response.data.conversation_id;
          const aiResponse = response.data.response;
          const chart_config = response.data.chart_config;

          // Debug logging
          console.log('Backend Response:', response.data);
          console.log('Conversation ID from backend:', backendConvId);
          console.log('AI Response:', aiResponse);
          console.log('Chart Config:', chart_config);

          // If backend returned a different conversation ID (first message), migrate the conversation
          let finalConvId = currentConvId;
          if (isNewConversation && backendConvId && backendConvId !== currentConvId) {
            finalConvId = backendConvId;
            // Move conversation to backend ID
            set((state) => {
              const tempConv = state.conversations[currentConvId];
              const newConversations = { ...state.conversations };
              delete newConversations[currentConvId];
              newConversations[finalConvId] = {
                ...tempConv,
                id: finalConvId
              };
              return {
                conversations: newConversations,
                currentConversationId: finalConvId
              };
            });
          }

          // Add AI response
          console.log('Chart config from backend:', chart_config);
          console.log('Chart config has data?', chart_config?.data);
          console.log('Chart config data length:', chart_config?.data?.length);
          if (chart_config?.data?.[0]) {
            console.log('First trace structure:', chart_config.data[0]);
            console.log('First trace keys:', Object.keys(chart_config.data[0]));
            console.log('X data sample:', chart_config.data[0].x?.slice(0, 5));
            console.log('Y data sample:', chart_config.data[0].y?.slice(0, 5));
          }

          const aiMessage = {
            id: `msg_${Date.now()}_ai`,
            role: 'assistant',
            content: aiResponse || 'No response from AI',
            chart_config: chart_config || null,
            timestamp: new Date().toISOString(),
          };

          set((state) => ({
            conversations: {
              ...state.conversations,
              [finalConvId]: {
                ...state.conversations[finalConvId],
                messages: [
                  ...(state.conversations[finalConvId]?.messages || []),
                  aiMessage
                ]
              }
            },
            currentConversationId: finalConvId,
            loading: false
          }));

          return { success: true, conversationId: finalConvId };
        } catch (error) {
          console.error('Send message error:', error);
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