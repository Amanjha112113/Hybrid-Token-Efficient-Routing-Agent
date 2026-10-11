/**
 * MessageThread.jsx
 * 
 * Message display with streaming, markdown, and syntax highlighting
 */

import React, { useEffect, useRef } from 'react';
import { User, Bot, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

export default function MessageThread({
  messages,
  isStreaming,
  currentStreamingMessage,
  streamMetadata,
}) {
  const messagesEndRef = useRef(null);
  const [copiedId, setCopiedId] = React.useState(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentStreamingMessage]);

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const Message = ({ message, isLast }) => {
    const isUser = message.role === 'user';

    return (
      <div className={`message ${isUser ? 'user' : 'assistant'}`}>
        <div className="message-icon">
          {isUser ? <User size={20} /> : <Bot size={20} />}
        </div>
        
        <div className="message-content">
          <div className="message-header">
            <span className="message-role">
              {isUser ? 'You' : 'Assistant'}
            </span>
            
            {!isUser && message.backend && (
              <span className={`backend-badge ${message.backend}`}>
                {message.backend === 'local' ? '💻 Local' : '☁️ Cloud'}
                {message.model && ` · ${message.model.split('/').pop()}`}
              </span>
            )}
            
            {!isUser && (
              <button
                onClick={() => copyToClipboard(message.content, message.id)}
                className="btn-copy"
                title="Copy message"
              >
                {copiedId === message.id ? <Check size={14} /> : <Copy size={14} />}
              </button>
            )}
          </div>

          <div className="message-body">
            {isUser ? (
              <div className="message-text">{message.content}</div>
            ) : (
              <ReactMarkdown
                className="markdown"
                components={{
                  code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <SyntaxHighlighter
                        style={vscDarkPlus}
                        language={match[1]}
                        PreTag="div"
                        {...props}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            )}
          </div>

          {!isUser && message.tokens_used !== undefined && (
            <div className="message-meta">
              <span>Tokens: {message.tokens_used} used</span>
              {message.tokens_saved > 0 && (
                <span className="savings"> · {message.tokens_saved} saved</span>
              )}
              <span> · ${message.cost_usd.toFixed(6)}</span>
              {message.savings_usd > 0 && (
                <span className="savings"> (saved ${message.savings_usd.toFixed(6)})</span>
              )}
              <span> · {message.latency_ms}ms</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  const StreamingMessage = () => {
    return (
      <div className="message assistant streaming">
        <div className="message-icon">
          <Bot size={20} />
        </div>
        
        <div className="message-content">
          <div className="message-header">
            <span className="message-role">Assistant</span>
            
            {streamMetadata?.backend && (
              <span className={`backend-badge ${streamMetadata.backend}`}>
                {streamMetadata.backend === 'local' ? '💻 Local' : '☁️ Cloud'}
              </span>
            )}
            
            <span className="streaming-indicator">
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </span>
          </div>

          <div className="message-body">
            <ReactMarkdown
              className="markdown"
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={vscDarkPlus}
                      language={match[1]}
                      PreTag="div"
                      {...props}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {currentStreamingMessage || ' '}
            </ReactMarkdown>
            <span className="cursor">|</span>
          </div>

          {streamMetadata?.complexity && (
            <div className="message-meta">
              Complexity: {streamMetadata.complexity}
              {streamMetadata.reason && ` · ${streamMetadata.reason}`}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="message-thread">
      {messages.length === 0 && !isStreaming && (
        <div className="empty-thread">
          <Bot size={48} className="empty-icon" />
          <h3>Start a conversation</h3>
          <p>Send a message to begin. Simple queries run locally at $0 cost!</p>
        </div>
      )}

      {messages.map((msg, idx) => (
        <Message key={msg.id || idx} message={msg} isLast={idx === messages.length - 1} />
      ))}

      {isStreaming && <StreamingMessage />}

      <div ref={messagesEndRef} />
    </div>
  );
}
