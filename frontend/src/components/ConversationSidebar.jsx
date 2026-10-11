/**
 * ConversationSidebar.jsx
 * 
 * ChatGPT-style conversation sidebar with date grouping and search
 */

import React, { useState, useMemo } from 'react';
import { Search, Plus, Trash2, Edit2, Check, X } from 'lucide-react';

export default function ConversationSidebar({
  conversations,
  currentConvId,
  onSelectConversation,
  onCreateConversation,
  onUpdateConversation,
  onDeleteConversation,
  loading,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');

  // Group conversations by date
  const groupedConversations = useMemo(() => {
    const filtered = conversations.filter(conv =>
      conv.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);
    const lastMonth = new Date(today);
    lastMonth.setDate(lastMonth.getDate() - 30);

    const groups = {
      today: [],
      yesterday: [],
      lastWeek: [],
      lastMonth: [],
      older: [],
    };

    filtered.forEach(conv => {
      const convDate = new Date(conv.updated_at);
      const convDay = new Date(convDate.getFullYear(), convDate.getMonth(), convDate.getDate());

      if (convDay.getTime() === today.getTime()) {
        groups.today.push(conv);
      } else if (convDay.getTime() === yesterday.getTime()) {
        groups.yesterday.push(conv);
      } else if (convDay >= lastWeek) {
        groups.lastWeek.push(conv);
      } else if (convDay >= lastMonth) {
        groups.lastMonth.push(conv);
      } else {
        groups.older.push(conv);
      }
    });

    return groups;
  }, [conversations, searchQuery]);

  const startEdit = (conv) => {
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const saveEdit = async (convId) => {
    if (editTitle.trim() && editTitle !== conversations.find(c => c.id === convId)?.title) {
      await onUpdateConversation(convId, { title: editTitle.trim() });
    }
    setEditingId(null);
    setEditTitle('');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditTitle('');
  };

  const ConversationItem = ({ conv }) => {
    const isActive = conv.id === currentConvId;
    const isEditing = editingId === conv.id;

    return (
      <div
        className={`conv-item ${isActive ? 'active' : ''}`}
        onClick={() => !isEditing && onSelectConversation(conv.id)}
      >
        {isEditing ? (
          <div className="conv-edit">
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') saveEdit(conv.id);
                if (e.key === 'Escape') cancelEdit();
              }}
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
            <div className="edit-actions">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  saveEdit(conv.id);
                }}
                className="btn-icon success"
              >
                <Check size={14} />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  cancelEdit();
                }}
                className="btn-icon"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="conv-content">
              <div className="conv-title">{conv.title}</div>
              <div className="conv-meta">
                {conv.total_messages} messages · ${conv.total_cost_usd.toFixed(4)}
              </div>
            </div>
            <div className="conv-actions">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  startEdit(conv);
                }}
                className="btn-icon"
                title="Rename"
              >
                <Edit2 size={14} />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Delete "${conv.title}"?`)) {
                    onDeleteConversation(conv.id);
                  }
                }}
                className="btn-icon danger"
                title="Delete"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </>
        )}
      </div>
    );
  };

  const ConversationGroup = ({ title, conversations }) => {
    if (conversations.length === 0) return null;

    return (
      <div className="conv-group">
        <div className="group-title">{title}</div>
        {conversations.map(conv => (
          <ConversationItem key={conv.id} conv={conv} />
        ))}
      </div>
    );
  };

  return (
    <div className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <h2>Conversations</h2>
        <button
          onClick={onCreateConversation}
          className="btn-new-chat"
          disabled={loading}
        >
          <Plus size={18} />
          New Chat
        </button>
      </div>

      {/* Search */}
      <div className="sidebar-search">
        <Search size={16} className="search-icon" />
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="btn-clear"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Conversations List */}
      <div className="sidebar-list">
        {loading ? (
          <div className="loading-state">Loading conversations...</div>
        ) : conversations.length === 0 ? (
          <div className="empty-state">
            <p>No conversations yet</p>
            <p className="hint">Click "New Chat" to start</p>
          </div>
        ) : (
          <>
            <ConversationGroup title="Today" conversations={groupedConversations.today} />
            <ConversationGroup title="Yesterday" conversations={groupedConversations.yesterday} />
            <ConversationGroup title="Last 7 Days" conversations={groupedConversations.lastWeek} />
            <ConversationGroup title="Last 30 Days" conversations={groupedConversations.lastMonth} />
            <ConversationGroup title="Older" conversations={groupedConversations.older} />
          </>
        )}
      </div>
    </div>
  );
}
