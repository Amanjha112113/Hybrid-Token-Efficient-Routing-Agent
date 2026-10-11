/**
 * useStreamingChat.js
 * 
 * Custom React hook for streaming chat with SSE (Server-Sent Events).
 * Handles token-by-token message streaming, conversation management, and state.
 */

import { useState, useCallback, useRef, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

/**
 * Hook for managing streaming chat conversations
 * 
 * @param {string} conversationId - Current conversation ID
 * @returns {Object} Chat state and control functions
 */
export function useStreamingChat(conversationId) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('');
  const [streamMetadata, setStreamMetadata] = useState(null);
  const [qualityScore, setQualityScore] = useState(null);
  const [routerDecision, setRouterDecision] = useState(null); // NEW: Router decision
  const [error, setError] = useState(null);
  
  const abortControllerRef = useRef(null);
  const currentConversationRef = useRef(conversationId);

  // Update conversation ref when ID changes
  useEffect(() => {
    currentConversationRef.current = conversationId;
  }, [conversationId]);

  /**
   * Load existing messages for a conversation
   */
  const loadMessages = useCallback(async () => {
    if (!conversationId) return;
    
    try {
      const response = await fetch(
        `${API_BASE}/api/conversations/${conversationId}/messages`
      );
      
      if (!response.ok) {
        throw new Error(`Failed to load messages: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Convert to UI message format
      const formattedMessages = data.map(msg => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        backend: msg.backend,
        model: msg.model_used,
        complexity: msg.complexity,
        tokens_used: msg.tokens_used,
        tokens_saved: msg.tokens_saved,
        cost_usd: msg.cost_usd,
        savings_usd: msg.savings_usd,
        latency_ms: msg.latency_ms,
        timestamp: msg.created_at,
      }));
      
      setMessages(formattedMessages);
    } catch (err) {
      console.error('Failed to load messages:', err);
      setError(err.message);
    }
  }, [conversationId]);

  /**
   * Load messages when conversation changes
   */
  useEffect(() => {
    if (conversationId) {
      loadMessages();
    } else {
      setMessages([]);
    }
  }, [conversationId, loadMessages]);

  /**
   * Send a message and stream the response
   */
  const sendMessage = useCallback(async (prompt, comparisonMode = false) => {
    if (!prompt.trim() || isStreaming || !conversationId) {
      return;
    }

    // Add user message immediately (optimistic update)
    const userMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsStreaming(true);
    setCurrentStreamingMessage('');
    setStreamMetadata(null);
    setQualityScore(null);
    setError(null);

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversation_id: conversationId,
          prompt: prompt,
          comparison_mode: comparisonMode,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`Stream failed: ${response.status}`);
      }

      // Process SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentEventType = null;
      let streamedContent = '';
      let localContent = '';
      let cloudContent = '';
      let finalMetadata = null;
      let isComparisonMode = comparisonMode;

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;

          if (line.startsWith('event:')) {
            currentEventType = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            const dataStr = line.substring(5).trim();
            
            try {
              const data = JSON.parse(dataStr);

              if (currentEventType === 'token') {
                // Accumulate tokens
                const token = data.token || '';
                streamedContent += token;
                setCurrentStreamingMessage(streamedContent);
                
              } else if (currentEventType === 'dual_token') {
                // Comparison mode - separate local and cloud tokens
                const source = data.source;
                const localToken = data.local?.token || '';
                const cloudToken = data.cloud?.token || '';
                
                if (source === 'local' && localToken) {
                  localContent += localToken;
                }
                if (source === 'cloud' && cloudToken) {
                  cloudContent += cloudToken;
                }
                
                // Update streaming message with both
                setCurrentStreamingMessage({
                  local: localContent,
                  cloud: cloudContent,
                  isComparison: true,
                });
                
              } else if (currentEventType === 'dual_done') {
                // Comparison mode complete
                finalMetadata = {
                  isDual: true,
                  local: data.local,
                  cloud: data.cloud,
                  comparison: data.comparison,
                };
                
              } else if (currentEventType === 'metadata') {
                // Update metadata (backend, model info)
                setStreamMetadata(data);
                
              } else if (currentEventType === 'router') {
                // NEW: Router decision
                setRouterDecision(data);
                
              } else if (currentEventType === 'quality') {
                // Quality validation scores (LEGACY)
                setQualityScore(data);
                
              } else if (currentEventType === 'done') {
                // Final stats
                finalMetadata = data;
                
              } else if (currentEventType === 'error') {
                throw new Error(data.message || 'Stream error');
              }
            } catch (parseError) {
              console.error('Failed to parse SSE data:', dataStr, parseError);
            }
          }
        }
      }

      // Add assistant message to state
      if (finalMetadata?.isDual) {
        // Comparison mode - add both responses
        const localMsg = {
          id: `msg-local-${Date.now()}`,
          role: 'assistant',
          content: localContent,
          backend: 'local',
          model: finalMetadata.local.model || 'qwen2.5:3b',
          tokens_used: 0,
          tokens_saved: finalMetadata.local.tokens_saved || 0,
          cost_usd: 0.0,
          savings_usd: finalMetadata.local.savings_usd || 0.0,
          latency_ms: finalMetadata.local.latency_ms || 0,
          quality_score: finalMetadata.local.quality_score || null,
          quality_passed: finalMetadata.local.quality_passed || null,
          isComparison: true,
          comparisonSide: 'local',
          timestamp: new Date().toISOString(),
        };
        
        const cloudMsg = {
          id: `msg-cloud-${Date.now()}`,
          role: 'assistant',
          content: cloudContent,
          backend: 'fireworks',
          model: finalMetadata.cloud.model || 'unknown',
          tokens_used: finalMetadata.cloud.tokens_used || 0,
          tokens_saved: 0,
          cost_usd: finalMetadata.cloud.cost_usd || 0.0,
          savings_usd: 0.0,
          latency_ms: finalMetadata.cloud.latency_ms || 0,
          quality_score: finalMetadata.cloud.quality_score || null,
          quality_passed: finalMetadata.cloud.quality_passed || null,
          isComparison: true,
          comparisonSide: 'cloud',
          comparisonData: finalMetadata.comparison,
          timestamp: new Date().toISOString(),
        };
        
        setMessages(prev => [...prev, localMsg, cloudMsg]);
      } else {
        // Normal mode - single response
        const assistantMessage = {
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: streamedContent || finalMetadata?.full_response || 'No response',
          backend: finalMetadata?.backend || 'unknown',
          model: finalMetadata?.model || 'unknown',
          tokens_used: finalMetadata?.tokens_used || 0,
          tokens_saved: finalMetadata?.tokens_saved || 0,
          cost_usd: finalMetadata?.cost_usd || 0,
          savings_usd: finalMetadata?.savings_usd || 0,
          latency_ms: finalMetadata?.latency_ms || 0,
          quality_score: finalMetadata?.quality_score || null,
          quality_passed: finalMetadata?.quality_passed || null,
          router_score: finalMetadata?.router_score || null,
          router_confidence: finalMetadata?.router_confidence || null,
          router_reason: finalMetadata?.router_reason || null,
          timestamp: new Date().toISOString(),
        };

        setMessages(prev => [...prev, assistantMessage]);
      }
      
      setCurrentStreamingMessage('');
      setStreamMetadata(null);
      setQualityScore(null);
      setRouterDecision(null);

    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Stream cancelled by user');
      } else {
        console.error('Stream error:', err);
        setError(err.message);
        
        // Add error message to chat
        setMessages(prev => [...prev, {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `❌ Error: ${err.message}`,
          isError: true,
          timestamp: new Date().toISOString(),
        }]);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [conversationId, isStreaming]);

  /**
   * Cancel ongoing stream
   */
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
      setCurrentStreamingMessage('');
    }
  }, []);

  /**
   * Clear conversation messages (UI only)
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
    setCurrentStreamingMessage('');
    setStreamMetadata(null);
    setError(null);
  }, []);

  return {
    // State
    messages,
    isStreaming,
    currentStreamingMessage,
    streamingMetadata: streamMetadata,
    qualityScore,
    routerDecision, // NEW: Router decision state
    error,
    
    // Actions
    sendMessage,
    cancelStream,
    loadMessages,
    clearMessages,
  };
}

/**
 * Hook for managing conversations list
 */
export function useConversations() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Load all conversations
   */
  const loadConversations = useCallback(async (status = 'active') => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `${API_BASE}/api/conversations?status=${status}&limit=100`
      );
      
      if (!response.ok) {
        throw new Error(`Failed to load conversations: ${response.status}`);
      }
      
      const data = await response.json();
      setConversations(data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Create a new conversation
   */
  const createConversation = useCallback(async (title = 'New Conversation', modelPreference = 'auto') => {
    try {
      const response = await fetch(`${API_BASE}/api/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title,
          model_preference: modelPreference,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to create conversation: ${response.status}`);
      }
      
      const newConv = await response.json();
      setConversations(prev => [newConv, ...prev]);
      return newConv;
    } catch (err) {
      console.error('Failed to create conversation:', err);
      setError(err.message);
      return null;
    }
  }, []);

  /**
   * Update conversation
   */
  const updateConversation = useCallback(async (conversationId, updates) => {
    try {
      const response = await fetch(
        `${API_BASE}/api/conversations/${conversationId}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(updates),
        }
      );
      
      if (!response.ok) {
        throw new Error(`Failed to update conversation: ${response.status}`);
      }
      
      const updated = await response.json();
      setConversations(prev =>
        prev.map(c => c.id === conversationId ? updated : c)
      );
      return updated;
    } catch (err) {
      console.error('Failed to update conversation:', err);
      setError(err.message);
      return null;
    }
  }, []);

  /**
   * Delete conversation
   */
  const deleteConversation = useCallback(async (conversationId, hardDelete = false) => {
    try {
      const response = await fetch(
        `${API_BASE}/api/conversations/${conversationId}?hard_delete=${hardDelete}`,
        {
          method: 'DELETE',
        }
      );
      
      if (!response.ok) {
        throw new Error(`Failed to delete conversation: ${response.status}`);
      }
      
      setConversations(prev => prev.filter(c => c.id !== conversationId));
      return true;
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      setError(err.message);
      return false;
    }
  }, []);

  /**
   * Search conversations
   */
  const searchConversations = useCallback(async (query) => {
    if (!query.trim()) {
      await loadConversations();
      return;
    }
    
    try {
      const response = await fetch(
        `${API_BASE}/api/conversations/search?q=${encodeURIComponent(query)}`
      );
      
      if (!response.ok) {
        throw new Error(`Failed to search conversations: ${response.status}`);
      }
      
      const data = await response.json();
      setConversations(data);
    } catch (err) {
      console.error('Failed to search conversations:', err);
      setError(err.message);
    }
  }, [loadConversations]);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  return {
    conversations,
    loading,
    error,
    loadConversations,
    createConversation,
    updateConversation,
    deleteConversation,
    searchConversations,
  };
}
