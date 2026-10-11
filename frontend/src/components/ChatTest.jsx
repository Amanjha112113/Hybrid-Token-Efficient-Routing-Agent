/**
 * ChatTest.jsx
 * 
 * Simple test component to verify streaming chat functionality
 */

import React, { useState } from 'react';
import { useStreamingChat, useConversations } from '../hooks/useStreamingChat';

export default function ChatTest() {
  const [currentConvId, setCurrentConvId] = useState(null);
  const [inputText, setInputText] = useState('');

  const {
    conversations,
    loading: convsLoading,
    createConversation,
    deleteConversation,
  } = useConversations();

  const {
    messages,
    isStreaming,
    currentStreamingMessage,
    streamMetadata,
    error,
    sendMessage,
    cancelStream,
  } = useStreamingChat(currentConvId);

  const handleCreateConv = async () => {
    const conv = await createConversation('Test Chat', 'auto');
    if (conv) {
      setCurrentConvId(conv.id);
    }
  };

  const handleSend = (e) => {
    e.preventDefault();
    if (inputText.trim() && currentConvId) {
      sendMessage(inputText);
      setInputText('');
    }
  };

  return (
    <div style={{ 
      padding: '20px', 
      maxWidth: '1200px', 
      margin: '0 auto',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <h1>🚀 Streaming Chat Test</h1>

      {/* Conversation Selection */}
      <div style={{ 
        marginBottom: '20px', 
        padding: '15px', 
        background: '#f5f5f5', 
        borderRadius: '8px' 
      }}>
        <h3>Conversations</h3>
        {convsLoading ? (
          <p>Loading conversations...</p>
        ) : (
          <>
            <button 
              onClick={handleCreateConv}
              style={{
                padding: '8px 16px',
                marginBottom: '10px',
                background: '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              + New Conversation
            </button>
            
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              {conversations.map(conv => (
                <div
                  key={conv.id}
                  style={{
                    padding: '8px 12px',
                    background: conv.id === currentConvId ? '#007bff' : 'white',
                    color: conv.id === currentConvId ? 'white' : 'black',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '14px',
                  }}
                  onClick={() => setCurrentConvId(conv.id)}
                >
                  {conv.title} ({conv.total_messages} msgs)
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteConversation(conv.id);
                      if (conv.id === currentConvId) setCurrentConvId(null);
                    }}
                    style={{
                      marginLeft: '8px',
                      background: 'transparent',
                      border: 'none',
                      color: 'inherit',
                      cursor: 'pointer',
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Chat Messages */}
      {currentConvId && (
        <div>
          <div style={{
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '15px',
            minHeight: '400px',
            maxHeight: '500px',
            overflowY: 'auto',
            marginBottom: '15px',
            background: 'white',
          }}>
            {messages.length === 0 && !isStreaming && (
              <p style={{ color: '#888', textAlign: 'center' }}>
                No messages yet. Start chatting!
              </p>
            )}

            {messages.map((msg, idx) => (
              <div
                key={msg.id || idx}
                style={{
                  marginBottom: '15px',
                  padding: '12px',
                  background: msg.role === 'user' ? '#e3f2fd' : '#f5f5f5',
                  borderRadius: '8px',
                  borderLeft: `4px solid ${msg.role === 'user' ? '#2196f3' : '#4caf50'}`,
                }}
              >
                <div style={{ 
                  fontWeight: 'bold', 
                  marginBottom: '5px',
                  color: msg.role === 'user' ? '#1976d2' : '#388e3c',
                }}>
                  {msg.role === 'user' ? '👤 You' : '🤖 Assistant'}
                  {msg.backend && (
                    <span style={{ 
                      marginLeft: '10px', 
                      fontSize: '12px',
                      padding: '2px 6px',
                      background: msg.backend === 'local' ? '#4caf50' : '#ff9800',
                      color: 'white',
                      borderRadius: '3px',
                    }}>
                      {msg.backend === 'local' ? '💻 Local' : '☁️ Cloud'}
                    </span>
                  )}
                </div>
                <div style={{ whiteSpace: 'pre-wrap' }}>
                  {msg.content}
                </div>
                {msg.role === 'assistant' && msg.tokens_used !== undefined && (
                  <div style={{ 
                    marginTop: '8px', 
                    fontSize: '11px', 
                    color: '#666' 
                  }}>
                    Tokens: {msg.tokens_used} used, {msg.tokens_saved} saved | 
                    Cost: ${msg.cost_usd.toFixed(6)} | 
                    Latency: {msg.latency_ms}ms
                  </div>
                )}
              </div>
            ))}

            {/* Streaming Message */}
            {isStreaming && (
              <div
                style={{
                  marginBottom: '15px',
                  padding: '12px',
                  background: '#f5f5f5',
                  borderRadius: '8px',
                  borderLeft: '4px solid #4caf50',
                }}
              >
                <div style={{ 
                  fontWeight: 'bold', 
                  marginBottom: '5px',
                  color: '#388e3c',
                }}>
                  🤖 Assistant
                  {streamMetadata?.backend && (
                    <span style={{ 
                      marginLeft: '10px', 
                      fontSize: '12px',
                      padding: '2px 6px',
                      background: streamMetadata.backend === 'local' ? '#4caf50' : '#ff9800',
                      color: 'white',
                      borderRadius: '3px',
                    }}>
                      {streamMetadata.backend === 'local' ? '💻 Local' : '☁️ Cloud'}
                    </span>
                  )}
                  <span style={{
                    marginLeft: '10px',
                    fontSize: '12px',
                    color: '#666',
                  }}>
                    ⏳ Streaming...
                  </span>
                </div>
                <div style={{ whiteSpace: 'pre-wrap' }}>
                  {currentStreamingMessage}
                  <span style={{ 
                    display: 'inline-block',
                    width: '8px',
                    height: '14px',
                    background: '#4caf50',
                    marginLeft: '2px',
                    animation: 'blink 1s infinite',
                  }}>|</span>
                </div>
                {streamMetadata?.complexity && (
                  <div style={{ 
                    marginTop: '8px', 
                    fontSize: '11px', 
                    color: '#666' 
                  }}>
                    Complexity: {streamMetadata.complexity} | {streamMetadata.reason}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Error Display */}
          {error && (
            <div style={{
              padding: '12px',
              background: '#ffebee',
              color: '#c62828',
              borderRadius: '4px',
              marginBottom: '15px',
              border: '1px solid #ef5350',
            }}>
              ❌ {error}
            </div>
          )}

          {/* Input Form */}
          <form onSubmit={handleSend} style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Type your message..."
              disabled={isStreaming}
              style={{
                flex: 1,
                padding: '12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                fontSize: '14px',
              }}
            />
            {isStreaming ? (
              <button
                type="button"
                onClick={cancelStream}
                style={{
                  padding: '12px 24px',
                  background: '#f44336',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px',
                }}
              >
                ⏹ Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!inputText.trim()}
                style={{
                  padding: '12px 24px',
                  background: inputText.trim() ? '#4caf50' : '#ccc',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: inputText.trim() ? 'pointer' : 'not-allowed',
                  fontSize: '14px',
                }}
              >
                📤 Send
              </button>
            )}
          </form>
        </div>
      )}

      {!currentConvId && (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          color: '#888',
          border: '2px dashed #ddd',
          borderRadius: '8px',
        }}>
          <p style={{ fontSize: '18px' }}>
            👈 Select or create a conversation to start chatting
          </p>
        </div>
      )}

      <style>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
