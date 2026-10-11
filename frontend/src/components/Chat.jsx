/**
 * Chat.jsx
 * 
 * Main chat interface - combines sidebar, thread, and input
 */

import React, { useState, useEffect } from 'react';
import ConversationSidebar from './ConversationSidebar';
import MessageThread from './MessageThread';
import ChatInput from './ChatInput';
import { useStreamingChat, useConversations } from '../hooks/useStreamingChat';

export default function Chat() {
  const [currentConvId, setCurrentConvId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const {
    conversations,
    loading: convsLoading,
    createConversation,
    updateConversation,
    deleteConversation,
    searchConversations,
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

  // Auto-select first conversation on load
  useEffect(() => {
    if (!currentConvId && conversations.length > 0 && !convsLoading) {
      setCurrentConvId(conversations[0].id);
    }
  }, [conversations, currentConvId, convsLoading]);

  const handleCreateConversation = async () => {
    const newConv = await createConversation('New Conversation', 'auto');
    if (newConv) {
      setCurrentConvId(newConv.id);
    }
  };

  const handleSendMessage = async (text) => {
    if (!currentConvId) {
      // Create conversation if none exists
      const newConv = await createConversation('New Conversation', 'auto');
      if (newConv) {
        setCurrentConvId(newConv.id);
        // Wait a tick for the conversation to be set
        setTimeout(() => sendMessage(text), 100);
      }
    } else {
      await sendMessage(text);
    }
  };

  const handleModelPreferenceChange = async (preference) => {
    if (currentConvId) {
      await updateConversation(currentConvId, { model_preference: preference });
    }
  };

  const currentConv = conversations.find(c => c.id === currentConvId);
  const modelPreference = currentConv?.model_preference || 'auto';

  return (
    <div className="chat-container">
      {/* Sidebar */}
      <div className={`chat-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <ConversationSidebar
          conversations={conversations}
          currentConvId={currentConvId}
          onSelectConversation={setCurrentConvId}
          onCreateConversation={handleCreateConversation}
          onUpdateConversation={updateConversation}
          onDeleteConversation={(id) => {
            deleteConversation(id);
            if (id === currentConvId) {
              setCurrentConvId(null);
            }
          }}
          loading={convsLoading}
        />
      </div>

      {/* Main Chat Area */}
      <div className="chat-main">
        {/* Header */}
        <div className="chat-header">
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="btn-toggle-sidebar"
          >
            {sidebarCollapsed ? '→' : '←'}
          </button>
          
          <div className="header-title">
            {currentConv ? (
              <>
                <h2>{currentConv.title}</h2>
                <div className="header-meta">
                  {currentConv.total_messages} messages · 
                  ${currentConv.total_cost_usd.toFixed(4)} cost
                </div>
              </>
            ) : (
              <h2>Hybrid AI Gateway</h2>
            )}
          </div>

          <div className="header-actions">
            <div className="status-badge">
              <span className="status-dot"></span>
              Connected
            </div>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="error-banner">
            ⚠️ {error}
            <button onClick={() => window.location.reload()}>Reload</button>
          </div>
        )}

        {/* Messages */}
        <div className="chat-content">
          <MessageThread
            messages={messages}
            isStreaming={isStreaming}
            currentStreamingMessage={currentStreamingMessage}
            streamMetadata={streamMetadata}
          />
        </div>

        {/* Input */}
        <div className="chat-input-wrapper">
          <ChatInput
            onSend={handleSendMessage}
            onCancel={cancelStream}
            isStreaming={isStreaming}
            disabled={false}
            modelPreference={modelPreference}
            onModelPreferenceChange={handleModelPreferenceChange}
          />
        </div>
      </div>
    </div>
  );
}
