import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useChatHistoryStore = create(
  persist(
    (set, get) => ({
      // Chat history data
      chatHistory: [],
      
      // Add a new chat to history
      addChat: (chatData) => {
        const { chatHistory } = get()
        const newChat = {
          id: Date.now().toString(),
          title: chatData.title || `Chat ${chatHistory.length + 1}`,
          datasetId: chatData.datasetId,
          datasetName: chatData.datasetName,
          messages: chatData.messages || [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messageCount: chatData.messages?.length || 0
        }
        
        set({
          chatHistory: [newChat, ...chatHistory].slice(0, 100) // Keep only last 100 chats
        })
      },
      
      // Update an existing chat
      updateChat: (chatId, updates) => {
        const { chatHistory } = get()
        const updatedHistory = chatHistory.map(chat => 
          chat.id === chatId 
            ? { ...chat, ...updates, updatedAt: new Date().toISOString() }
            : chat
        )
        set({ chatHistory: updatedHistory })
      },
      
      // Delete a chat
      deleteChat: (chatId) => {
        const { chatHistory } = get()
        set({
          chatHistory: chatHistory.filter(chat => chat.id !== chatId)
        })
      },
      
      // Get recent chats (for dropdown)
      getRecentChats: (limit = 5) => {
        const { chatHistory } = get()
        return chatHistory.slice(0, limit)
      },
      
      // Get all chats (for modal)
      getAllChats: () => {
        const { chatHistory } = get()
        return chatHistory
      },
      
      // Get chat by ID
      getChatById: (chatId) => {
        const { chatHistory } = get()
        return chatHistory.find(chat => chat.id === chatId)
      },
      
      // Clear all chat history
      clearAllChats: () => {
        set({ chatHistory: [] })
      },
      
      // Search chats
      searchChats: (query) => {
        const { chatHistory } = get()
        const lowercaseQuery = query.toLowerCase()
        return chatHistory.filter(chat => 
          chat.title.toLowerCase().includes(lowercaseQuery) ||
          chat.datasetName?.toLowerCase().includes(lowercaseQuery)
        )
      }
    }),
    {
      name: 'chat-history-storage',
      partialize: (state) => ({ chatHistory: state.chatHistory })
    }
  )
)

export default useChatHistoryStore

