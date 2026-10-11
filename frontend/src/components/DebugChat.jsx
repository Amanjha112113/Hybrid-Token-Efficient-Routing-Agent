import React, { useState } from 'react';
import { useStreamingChat, useConversations } from '../hooks/useStreamingChat';
import ConversationStats from './ConversationStats';


// Safe numeric rendering utilities
const safeToFixed = (value, digits = 4) => (value != null && !isNaN(value)) ? Number(value).toFixed(digits) : '0.0000';
const safeMathRound = (value) => (value != null && !isNaN(value)) ? Math.round(Number(value)) : 0;

export default function DebugChat() {
  const [currentConvId, setCurrentConvId] = useState(null);
  const [input, setInput] = useState('');
  const [comparisonMode, setComparisonMode] = useState(false);

  const {
    conversations,
    createConversation,
    deleteConversation,
  } = useConversations();

  const {
    messages,
    isStreaming,
    currentStreamingMessage,
    streamingMetadata,
    qualityScore,
    routerDecision,
    error,
    sendMessage,
  } = useStreamingChat(currentConvId);

  const currentConversation = conversations.find(c => c.id === currentConvId);

  const handleCreate = async () => {
    const conv = await createConversation('New Conversation');
    if (conv) {
      setCurrentConvId(conv.id);
    }
  };

  const handleSend = async () => {
    if (input.trim() && currentConvId) {
      await sendMessage(input, comparisonMode);
      setInput('');
    }
  };

  // Get all messages including streaming
  const allMessages = [...messages];
  if (isStreaming && currentStreamingMessage) {
    if (typeof currentStreamingMessage === 'object' && currentStreamingMessage.isComparison) {
      // Comparison mode streaming - show both
      allMessages.push({
        role: 'assistant',
        content: currentStreamingMessage.local,
        backend: 'local',
        isStreaming: true,
        isComparison: true,
        comparisonSide: 'local',
      });
      allMessages.push({
        role: 'assistant',
        content: currentStreamingMessage.cloud,
        backend: 'fireworks',
        isStreaming: true,
        isComparison: true,
        comparisonSide: 'cloud',
      });
    } else {
      // Normal streaming
      allMessages.push({
        role: 'assistant',
        content: currentStreamingMessage,
        backend: 'streaming',
        tokens_used: 0,
        tokens_saved: 0,
        cost_usd: 0,
        savings_usd: 0,
      });
    }
  }

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      background: '#0d1117',
      color: '#c9d1d9',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      {/* Left Sidebar */}
      <div style={{
        width: '260px',
        background: '#161b22',
        borderRight: '1px solid #30363d',
        display: 'flex',
        flexDirection: 'column',
        padding: '16px',
      }}>
        <button 
          onClick={handleCreate}
          style={{
            padding: '12px',
            background: '#238636',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: '600',
            marginBottom: '16px',
            fontSize: '14px',
          }}
        >
          + New Conversation
        </button>
        
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '8px', fontWeight: '600' }}>
            CONVERSATIONS
          </div>
          {conversations.map(conv => (
            <div 
              key={conv.id}
              style={{
                padding: '10px',
                background: conv.id === currentConvId ? '#1f6feb' : 'transparent',
                marginBottom: '4px',
                borderRadius: '6px',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                transition: 'background 0.2s',
              }}
              onClick={() => setCurrentConvId(conv.id)}
              onMouseEnter={(e) => {
                if (conv.id !== currentConvId) e.currentTarget.style.background = '#21262d';
              }}
              onMouseLeave={(e) => {
                if (conv.id !== currentConvId) e.currentTarget.style.background = 'transparent';
              }}
            >
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <div style={{ fontSize: '14px', fontWeight: '500', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {conv.title}
                </div>
                <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '2px' }}>
                  {conv.total_messages} messages
                </div>
              </div>
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  deleteConversation(conv.id);
                  if (conv.id === currentConvId) setCurrentConvId(null);
                }}
                style={{
                  background: 'transparent',
                  color: '#8b949e',
                  border: 'none',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '18px',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#f85149'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
      }}>
        {currentConvId ? (
          <>
            {/* Messages Area */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: '24px',
            }}>
              {/* Show active model indicator while streaming */}
              {isStreaming && streamingMetadata && (
                <div style={{
                  position: 'sticky',
                  top: 0,
                  padding: '12px 16px',
                  background: 'linear-gradient(135deg, #1a2f1a 0%, #1a2633 50%, #0d1117 100%)',
                  border: '1px solid #30363d',
                  borderRadius: '8px',
                  marginBottom: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  zIndex: 10,
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
                }}>
                  <div style={{
                    width: '8px',
                    height: '8px',
                    background: streamingMetadata.backend === 'local' ? '#7ee787' : '#58a6ff',
                    borderRadius: '50%',
                    animation: 'pulse 2s ease-in-out infinite',
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '13px', fontWeight: '600', color: '#f0f6fc' }}>
                      {streamingMetadata.backend === 'local' ? '💻 Using Local Model' : '☁️ Using Cloud Model'}
                    </div>
                    <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '2px' }}>
                      {streamingMetadata.model || 'Loading...'}
                      {streamingMetadata.status && ` • ${streamingMetadata.status}`}
                      {streamingMetadata.escalating && ' • Escalating to ensure quality...'}
                    </div>
                  </div>
                  {qualityScore && (
                    <div style={{
                      padding: '4px 12px',
                      background: qualityScore.passed ? '#1a7f37' : '#da3633',
                      borderRadius: '12px',
                      fontSize: '11px',
                      fontWeight: '600',
                      color: 'white',
                    }}>
                      Quality: {Math.round(qualityScore.overall_score * 100)}%
                    </div>
                  )}
                </div>
              )}
              
              {/* Show router decision (before streaming starts) */}
              {routerDecision && isStreaming && (
                <div style={{
                  padding: '12px 16px',
                  background: '#161b22',
                  border: '1px solid #0969da',
                  borderRadius: '8px',
                  marginBottom: '16px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                    <span style={{ fontSize: '14px' }}>🎯</span>
                    <span style={{ fontSize: '13px', fontWeight: '600', color: '#58a6ff' }}>
                      Router Decision
                    </span>
                    <span style={{
                      fontSize: '10px',
                      padding: '2px 8px',
                      background: routerDecision.confidence >= 0.75 ? '#0969da' : '#6e7681',
                      borderRadius: '10px',
                      fontWeight: '600',
                      color: 'white',
                    }}>
                      {Math.round(routerDecision.confidence * 100)}% confident
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#8b949e' }}>
                    {routerDecision.reason}
                  </div>
                  <div style={{ fontSize: '11px', color: '#6e7681', marginTop: '4px' }}>
                    Complexity: {routerDecision.complexity} • Score: {safeToFixed(routerDecision.score, 3)}
                  </div>
                </div>
              )}
              
              {allMessages.map((msg, idx) => {
                // Group comparison messages together
                const isComparisonLocal = msg.isComparison && msg.comparisonSide === 'local';
                const nextMsg = allMessages[idx + 1];
                const isComparisonPair = isComparisonLocal && nextMsg?.isComparison && nextMsg?.comparisonSide === 'cloud';
                
                // Skip cloud message if we're rendering it as a pair
                if (msg.isComparison && msg.comparisonSide === 'cloud' && allMessages[idx - 1]?.isComparison) {
                  return null;
                }
                
                // Render comparison pair side-by-side
                if (isComparisonPair) {
                  const cloudMsg = nextMsg;
                  return (
                    <div key={idx} style={{ marginBottom: '24px' }}>
                      {/* Comparison Header */}
                      <div style={{
                        padding: '12px 16px',
                        background: 'linear-gradient(135deg, #1a2f1a 0%, #1a2633 100%)',
                        border: '1px solid #30363d',
                        borderRadius: '8px 8px 0 0',
                        fontSize: '13px',
                        fontWeight: '600',
                        color: '#f0f6fc',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                      }}>
                        <span>⚖️ Side-by-Side Comparison</span>
                        {cloudMsg.comparisonData && (
                          <span style={{
                            marginLeft: 'auto',
                            fontSize: '11px',
                            padding: '2px 8px',
                            background: cloudMsg.comparisonData.both_passed ? '#1a7f37' : '#da3633',
                            borderRadius: '10px',
                            color: 'white',
                          }}>
                            {cloudMsg.comparisonData.both_passed ? '✓ Both Passed Quality' : '⚠ Quality Difference'}
                          </span>
                        )}
                      </div>
                      
                      {/* Side-by-side messages */}
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '16px',
                        padding: '16px',
                        background: '#161b22',
                        border: '1px solid #30363d',
                        borderTop: 'none',
                        borderRadius: '0 0 8px 8px',
                      }}>
                        {/* Local Response */}
                        <div style={{
                          padding: '16px',
                          background: '#0d1117',
                          borderRadius: '8px',
                          border: '2px solid #238636',
                        }}>
                          <div style={{
                            fontSize: '13px',
                            fontWeight: '600',
                            color: '#7ee787',
                            marginBottom: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                          }}>
                            <span>💻 Local Model</span>
                            {msg.quality_score && (
                              <span style={{
                                fontSize: '10px',
                                padding: '2px 8px',
                                background: '#1a7f37',
                                borderRadius: '10px',
                                color: 'white',
                              }}>
                                {Math.round(msg.quality_score * 100)}%
                              </span>
                            )}
                          </div>
                          <div style={{
                            fontSize: '14px',
                            lineHeight: '1.6',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            color: '#c9d1d9',
                          }}>
                            {msg.content}
                            {msg.isStreaming && (
                              <span style={{
                                display: 'inline-block',
                                width: '8px',
                                height: '16px',
                                background: '#7ee787',
                                marginLeft: '2px',
                                animation: 'blink 1s infinite',
                              }} />
                            )}
                          </div>
                          {!msg.isStreaming && (
                            <div style={{
                              marginTop: '12px',
                              paddingTop: '12px',
                              borderTop: '1px solid #238636',
                              fontSize: '11px',
                              color: '#8b949e',
                            }}>
                              💰 Cost: $0.00 • ⚡ {msg.tokens_saved || 0} tokens saved • 🕐 {msg.latency_ms || 0}ms
                            </div>
                          )}
                        </div>
                        
                        {/* Cloud Response */}
                        <div style={{
                          padding: '16px',
                          background: '#0d1117',
                          borderRadius: '8px',
                          border: '2px solid #1f6feb',
                        }}>
                          <div style={{
                            fontSize: '13px',
                            fontWeight: '600',
                            color: '#58a6ff',
                            marginBottom: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                          }}>
                            <span>☁️ Cloud Model</span>
                            {cloudMsg.quality_score && (
                              <span style={{
                                fontSize: '10px',
                                padding: '2px 8px',
                                background: '#0969da',
                                borderRadius: '10px',
                                color: 'white',
                              }}>
                                {Math.round(cloudMsg.quality_score * 100)}%
                              </span>
                            )}
                          </div>
                          <div style={{
                            fontSize: '14px',
                            lineHeight: '1.6',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            color: '#c9d1d9',
                          }}>
                            {cloudMsg.content}
                            {cloudMsg.isStreaming && (
                              <span style={{
                                display: 'inline-block',
                                width: '8px',
                                height: '16px',
                                background: '#58a6ff',
                                marginLeft: '2px',
                                animation: 'blink 1s infinite',
                              }} />
                            )}
                          </div>
                          {!cloudMsg.isStreaming && (
                            <div style={{
                              marginTop: '12px',
                              paddingTop: '12px',
                              borderTop: '1px solid #1f6feb',
                              fontSize: '11px',
                              color: '#8b949e',
                            }}>
                              💰 Cost: ${safeToFixed(cloudMsg.cost_usd, 4)} • 📊 {cloudMsg.tokens_used || 0} tokens • 🕐 {cloudMsg.latency_ms || 0}ms
                            </div>
                          )}
                        </div>
                      </div>
                      
                      {/* Comparison stats */}
                      {cloudMsg.comparisonData && !cloudMsg.isStreaming && (
                        <div style={{
                          marginTop: '12px',
                          padding: '12px 16px',
                          background: '#1a2633',
                          border: '1px solid #1f6feb',
                          borderRadius: '6px',
                          fontSize: '12px',
                          color: '#c9d1d9',
                        }}>
                          <strong>📊 Comparison Result:</strong> Quality difference: {safeMathRound((cloudMsg.comparisonData?.quality_diff || 0) * 100)}% 
                          • Cost saved by using local: ${safeToFixed(cloudMsg.comparisonData?.cost_saved, 4)}
                          • Both models {cloudMsg.comparisonData.both_passed ? 'passed' : 'had issues with'} quality check
                        </div>
                      )}
                    </div>
                  );
                }
                
                // Normal single message rendering
                return (
                <div 
                  key={idx}
                  style={{
                    marginBottom: '24px',
                    display: 'flex',
                    gap: '16px',
                  }}
                >
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: msg.role === 'user' ? '#238636' : '#1f6feb',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    fontWeight: 'bold',
                    fontSize: '14px',
                  }}>
                    {msg.role === 'user' ? '👤' : '🤖'}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: '14px',
                      fontWeight: '600',
                      marginBottom: '8px',
                      color: msg.role === 'user' ? '#7ee787' : '#58a6ff',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      flexWrap: 'wrap',
                    }}>
                      <span>{msg.role === 'user' ? 'You' : 'Assistant'}</span>
                      {msg.backend && msg.backend !== 'streaming' && (
                        <span style={{
                          fontSize: '11px',
                          padding: '2px 8px',
                          background: msg.backend === 'local' ? '#1a7f37' : '#0969da',
                          borderRadius: '12px',
                          fontWeight: '500',
                        }}>
                          {msg.backend === 'local' ? '💻 Local Model' : '☁️ Cloud Model'}
                        </span>
                      )}
                      {msg.model && msg.backend !== 'streaming' && (
                        <span style={{
                          fontSize: '10px',
                          padding: '2px 8px',
                          background: '#21262d',
                          borderRadius: '10px',
                          fontWeight: '400',
                          color: '#8b949e',
                        }}>
                          {msg.model}
                        </span>
                      )}
                      {msg.quality_score !== null && msg.quality_score !== undefined && (
                        <span style={{
                          fontSize: '10px',
                          padding: '2px 8px',
                          background: msg.quality_passed ? '#1a7f37' : '#da3633',
                          borderRadius: '10px',
                          fontWeight: '600',
                          color: 'white',
                        }}>
                          ✓ Quality {Math.round(msg.quality_score * 100)}%
                        </span>
                      )}
                      {msg.router_confidence !== null && msg.router_confidence !== undefined && (
                        <span style={{
                          fontSize: '10px',
                          padding: '2px 8px',
                          background: msg.router_confidence >= 0.75 ? '#0969da' : msg.router_confidence >= 0.5 ? '#6e7681' : '#6e7681',
                          borderRadius: '10px',
                          fontWeight: '500',
                          color: 'white',
                          border: '1px solid rgba(255,255,255,0.1)',
                        }}>
                          🎯 Router {Math.round(msg.router_confidence * 100)}%
                        </span>
                      )}
                    </div>
                    <div style={{
                      fontSize: '14px',
                      lineHeight: '1.6',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}>
                      {msg.content}
                      {msg.backend === 'streaming' && (
                        <span style={{
                          display: 'inline-block',
                          width: '8px',
                          height: '16px',
                          background: '#58a6ff',
                          marginLeft: '2px',
                          animation: 'blink 1s infinite',
                        }} />
                      )}
                    </div>
                    {msg.tokens_used > 0 || msg.tokens_saved > 0 ? (
                      <div style={{
                        marginTop: '8px',
                        fontSize: '12px',
                        color: '#8b949e',
                      }}>
                        {msg.tokens_used > 0 && `${msg.tokens_used} tokens used`}
                        {msg.tokens_saved > 0 && `${msg.tokens_saved} tokens (free)`}
                        {(msg.cost_usd || 0) > 0 && ` · $${safeToFixed(msg.cost_usd, 4)}`}
                        {(msg.savings_usd || 0) > 0 && ` · saved $${safeToFixed(msg.savings_usd, 4)}`}
                      </div>
                    ) : null}
                    {msg.router_reason && (
                      <div style={{
                        marginTop: '6px',
                        fontSize: '11px',
                        color: '#6e7681',
                        fontStyle: 'italic',
                        padding: '6px 10px',
                        background: '#161b22',
                        borderLeft: '2px solid #0969da',
                        borderRadius: '4px',
                      }}>
                        💡 {msg.router_reason}
                      </div>
                    )}
                  </div>
                </div>
              );
              })}
              
              {error && (
                <div style={{
                  padding: '16px',
                  background: '#da3633',
                  borderRadius: '6px',
                  marginBottom: '16px',
                  color: 'white',
                }}>
                  ❌ Error: {error}
                </div>
              )}
            </div>

            {/* Input Area */}
            <div style={{
              borderTop: '1px solid #30363d',
              padding: '16px 24px',
              background: '#0d1117',
            }}>
              {/* Comparison Mode Toggle */}
              <div style={{
                marginBottom: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 12px',
                background: comparisonMode ? '#1a2f1a' : '#161b22',
                border: `1px solid ${comparisonMode ? '#238636' : '#30363d'}`,
                borderRadius: '6px',
              }}>
                <button
                  onClick={() => setComparisonMode(!comparisonMode)}
                  style={{
                    width: '44px',
                    height: '24px',
                    background: comparisonMode ? '#238636' : '#21262d',
                    border: 'none',
                    borderRadius: '12px',
                    cursor: 'pointer',
                    position: 'relative',
                    transition: 'background 0.2s',
                  }}
                >
                  <div style={{
                    width: '20px',
                    height: '20px',
                    background: 'white',
                    borderRadius: '50%',
                    position: 'absolute',
                    top: '2px',
                    left: comparisonMode ? '22px' : '2px',
                    transition: 'left 0.2s',
                  }} />
                </button>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '13px', fontWeight: '600', color: comparisonMode ? '#7ee787' : '#c9d1d9' }}>
                    {comparisonMode ? '⚖️ Comparison Mode ON' : '💬 Normal Mode'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
                    {comparisonMode 
                      ? 'Generate with BOTH local and cloud to compare quality'
                      : 'Automatic routing for best efficiency'}
                  </div>
                </div>
                {comparisonMode && (
                  <div style={{
                    padding: '4px 10px',
                    background: '#1f6feb',
                    borderRadius: '12px',
                    fontSize: '11px',
                    fontWeight: '600',
                    color: 'white',
                  }}>
                    DEMO MODE
                  </div>
                )}
              </div>
              
              <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Type your message... (Shift+Enter for new line)"
                  disabled={isStreaming}
                  rows={3}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    color: '#c9d1d9',
                    fontSize: '14px',
                    resize: 'none',
                    fontFamily: 'inherit',
                  }}
                />
                <button
                  onClick={handleSend}
                  disabled={isStreaming || !input.trim()}
                  style={{
                    padding: '12px 24px',
                    background: isStreaming || !input.trim() ? '#30363d' : '#238636',
                    color: isStreaming || !input.trim() ? '#8b949e' : 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: isStreaming || !input.trim() ? 'not-allowed' : 'pointer',
                    fontWeight: '600',
                    fontSize: '14px',
                    height: '46px',
                  }}
                >
                  {isStreaming ? '⏳ Sending...' : '📤 Send'}
                </button>
              </div>
              <div style={{
                marginTop: '8px',
                fontSize: '12px',
                color: '#8b949e',
              }}>
                {input.length > 0 && `${input.length} characters`}
              </div>
            </div>
          </>
        ) : (
          <div style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            gap: '16px',
            color: '#8b949e',
          }}>
            <div style={{ fontSize: '48px' }}>💬</div>
            <div style={{ fontSize: '18px', fontWeight: '600' }}>No conversation selected</div>
            <div style={{ fontSize: '14px' }}>Create a new conversation to get started</div>
          </div>
        )}
      </div>

      {/* Right Stats Panel */}
      {currentConvId && (
        <div style={{
          width: '360px',
          background: '#161b22',
          borderLeft: '1px solid #30363d',
          overflowY: 'auto',
        }}>
          <ConversationStats 
            conversation={currentConversation}
            messages={messages}
          />
        </div>
      )}

      <style>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
        
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.2); }
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        
        ::-webkit-scrollbar-track {
          background: transparent;
        }
        
        ::-webkit-scrollbar-thumb {
          background: #30363d;
          border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
          background: #484f58;
        }
      `}</style>
    </div>
  );
}
