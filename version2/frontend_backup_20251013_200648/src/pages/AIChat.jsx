import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  Bot, 
  User, 
  Sparkles, 
  Database,
  MessageSquare,
  Loader2
} from 'lucide-react';
import { useDataset } from '../contexts/DatasetContext';
import toast from 'react-hot-toast';

const AIChat = () => {
  const { datasets, chatWithDataset, selectedDataset, setSelectedDataset } = useDataset();
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || !selectedDataset) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setLoading(true);

    try {
      const response = await chatWithDataset(
        selectedDataset.id,
        inputMessage,
        conversationId
      );

      if (response.success) {
        const botMessage = {
          id: Date.now() + 1,
          type: 'bot',
          content: response.data.response || response.data.message,
          timestamp: new Date()
        };

        setMessages(prev => [...prev, botMessage]);
        
        // Update conversation ID if provided
        if (response.data.conversation_id) {
          setConversationId(response.data.conversation_id);
        }
      } else {
        toast.error(response.error || 'Failed to get response');
      }
    } catch (error) {
      toast.error('An error occurred while sending message');
    } finally {
      setLoading(false);
    }
  };

  const suggestedQuestions = [
    "What are the key insights from this dataset?",
    "Show me the trends in the data",
    "What are the most significant patterns?",
    "Create a summary of the data",
    "What correlations can you find?"
  ];

  const handleSuggestedQuestion = (question) => {
    setInputMessage(question);
  };

  return (
    <div className="h-full flex flex-col" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Header */}
      <div className="border-b p-4" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold flex items-center" style={{ color: 'var(--text-primary)' }}>
              <MessageSquare className="w-5 h-5 mr-2" />
              AI Chat Assistant
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
              Ask questions about your data in natural language
            </p>
          </div>
          
          {/* Dataset selector */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <Database className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Dataset:</span>
            </div>
            <select
              value={selectedDataset?.id || ''}
              onChange={(e) => {
                const dataset = datasets.find(d => d.id === e.target.value);
                setSelectedDataset(dataset);
                setMessages([]);
                setConversationId(null);
              }}
              className="input-field px-3 py-1 text-sm"
            >
              <option value="">Select a dataset</option>
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name || 'Untitled Dataset'}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col" style={{ backgroundColor: 'var(--bg-primary)' }}>
        {!selectedDataset ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Database className="w-16 h-16 mx-auto mb-4" style={{ color: 'var(--text-secondary)' }} />
              <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                Select a Dataset
              </h3>
              <p style={{ color: 'var(--text-secondary)' }}>
                Choose a dataset from the dropdown above to start chatting
              </p>
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md">
              <Sparkles className="w-16 h-16 mx-auto mb-4" style={{ color: 'var(--accent-blue)' }} />
              <h3 className="text-lg font-medium mb-4" style={{ color: 'var(--text-primary)' }}>
                Start a conversation
              </h3>
              <p className="mb-6" style={{ color: 'var(--text-secondary)' }}>
                Ask questions about your "{selectedDataset.name}" dataset
              </p>
              
              <div className="space-y-2">
                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Suggested questions:</p>
                {suggestedQuestions.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => handleSuggestedQuestion(question)}
                    className="block w-full text-left p-3 rounded-lg border transition-colors duration-200 text-sm hover:border-accent-blue"
                    style={{ 
                      backgroundColor: 'var(--bg-surface)', 
                      borderColor: 'var(--border-color)',
                      color: 'var(--text-primary)'
                    }}
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`flex items-start space-x-3 max-w-3xl ${
                    message.type === 'user' ? 'flex-row-reverse space-x-reverse' : ''
                  }`}
                >
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                    style={{
                      backgroundColor: message.type === 'user' ? 'var(--accent-blue)' : 'var(--bg-surface)',
                      color: message.type === 'user' ? 'white' : 'var(--text-secondary)'
                    }}
                  >
                    {message.type === 'user' ? (
                      <User className="w-4 h-4" />
                    ) : (
                      <Bot className="w-4 h-4" />
                    )}
                  </div>
                  <div
                    className="px-4 py-3 rounded-lg"
                    style={{
                      backgroundColor: message.type === 'user' ? 'var(--accent-blue)' : 'var(--bg-surface)',
                      color: message.type === 'user' ? 'white' : 'var(--text-primary)',
                      border: message.type === 'user' ? 'none' : '1px solid var(--border-color)',
                      boxShadow: 'var(--shadow-subtle)'
                    }}
                  >
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    <p
                      className="text-xs mt-1"
                      style={{
                        color: message.type === 'user' ? 'rgba(255,255,255,0.7)' : 'var(--text-secondary)'
                      }}
                    >
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              </div>
            ))}
            
            {loading && (
              <div className="flex justify-start">
                <div className="flex items-start space-x-3 max-w-3xl">
                  <div 
                    className="w-8 h-8 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: 'var(--bg-surface)', color: 'var(--text-secondary)' }}
                  >
                    <Bot className="w-4 h-4" />
                  </div>
                  <div 
                    className="px-4 py-3 rounded-lg border"
                    style={{ 
                      backgroundColor: 'var(--bg-surface)', 
                      borderColor: 'var(--border-color)' 
                    }}
                  >
                    <div className="flex items-center space-x-2">
                      <Loader2 className="w-4 h-4 loading-spin" style={{ color: 'var(--accent-blue)' }} />
                      <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>AI is thinking...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input area - Fixed at bottom like ChatGPT */}
        {selectedDataset && (
          <div className="border-t p-4" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}>
            <div className="max-w-4xl mx-auto">
              <form onSubmit={handleSendMessage} className="relative">
                <div className="relative">
                  <textarea
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    placeholder="Ask a question about your data..."
                    className="w-full px-4 py-3 pr-12 rounded-lg resize-none focus:outline-none transition-all duration-200"
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-primary)',
                      minHeight: '52px',
                      maxHeight: '200px'
                    }}
                    disabled={loading}
                    rows={1}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage(e);
                      }
                    }}
                  />
                  <button
                    type="submit"
                    disabled={!inputMessage.trim() || loading}
                    className="absolute right-2 top-1/2 transform -translate-y-1/2 p-2 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{
                      backgroundColor: inputMessage.trim() ? 'var(--accent-blue)' : 'var(--text-muted)',
                      color: 'white'
                    }}
                  >
                    {loading ? (
                      <Loader2 className="w-4 h-4 loading-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </form>
              
              {/* Helper text */}
              <div className="mt-2 text-center">
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Press Enter to send, Shift + Enter for new line
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AIChat;


