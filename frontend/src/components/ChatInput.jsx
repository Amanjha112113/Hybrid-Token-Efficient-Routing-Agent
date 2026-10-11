/**
 * ChatInput.jsx
 * 
 * Multi-line chat input with token counter and keyboard shortcuts
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, StopCircle, Settings } from 'lucide-react';

export default function ChatInput({
  onSend,
  onCancel,
  isStreaming,
  disabled,
  modelPreference = 'auto',
  onModelPreferenceChange,
}) {
  const [input, setInput] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const textareaRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
  }, [input]);

  // Focus on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const estimatedTokens = Math.ceil(input.length / 4);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isStreaming && !disabled) {
      onSend(input);
      setInput('');
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e) => {
    // Cmd/Ctrl + Enter to send
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e);
    }
    
    // Shift + Enter for new line (default behavior)
  };

  const modelOptions = [
    { value: 'auto', label: '🎯 Auto (Smart Routing)', desc: 'System decides per message' },
    { value: 'local', label: '💻 Local Only', desc: 'Always use local model (free)' },
    { value: 'remote-efficient', label: '☁️ Cloud - Efficient', desc: 'Balanced cost/quality' },
    { value: 'remote-power', label: '⚡ Cloud - Maximum Power', desc: 'Best quality, higher cost' },
  ];

  return (
    <div className="chat-input-container">
      {/* Model Settings */}
      {showSettings && (
        <div className="input-settings">
          <div className="settings-header">
            <span>Routing Mode</span>
            <button onClick={() => setShowSettings(false)} className="btn-close">
              ×
            </button>
          </div>
          <div className="settings-options">
            {modelOptions.map(opt => (
              <label key={opt.value} className="setting-option">
                <input
                  type="radio"
                  name="model-preference"
                  value={opt.value}
                  checked={modelPreference === opt.value}
                  onChange={(e) => onModelPreferenceChange(e.target.value)}
                />
                <div className="option-content">
                  <div className="option-label">{opt.label}</div>
                  <div className="option-desc">{opt.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="chat-input-form">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Send a message... (Cmd+Enter to send)"
            disabled={disabled}
            rows={1}
            className="chat-textarea"
          />
          
          <div className="input-actions">
            <button
              type="button"
              onClick={() => setShowSettings(!showSettings)}
              className="btn-settings"
              title="Routing settings"
            >
              <Settings size={18} />
            </button>

            {isStreaming ? (
              <button
                type="button"
                onClick={onCancel}
                className="btn-send streaming"
                title="Stop generating"
              >
                <StopCircle size={20} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim() || disabled}
                className="btn-send"
                title="Send message (Cmd+Enter)"
              >
                <Send size={20} />
              </button>
            )}
          </div>
        </div>

        {/* Token Counter & Info */}
        <div className="input-footer">
          <div className="token-counter">
            ~{estimatedTokens} tokens
            {input.length > 0 && (
              <span className="char-count"> · {input.length} chars</span>
            )}
          </div>
          
          <div className="model-indicator">
            {modelOptions.find(o => o.value === modelPreference)?.label || 'Auto'}
          </div>
        </div>
      </form>
    </div>
  );
}
