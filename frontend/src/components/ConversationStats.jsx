/**
 * ConversationStats.jsx
 * 
 * Right-side panel showing token usage, costs, and routing analytics
 * This is the KEY feature - showing how the hybrid router saves money!
 */

import React from 'react';
import { TrendingDown, Cpu, Zap, DollarSign, Activity, PieChart } from 'lucide-react';
import '../styles/stats.css';

export default function ConversationStats({ conversation, messages }) {
  // Calculate statistics from messages
  const stats = React.useMemo(() => {
    let totalTokensUsed = 0;
    let totalTokensSaved = 0;
    let totalCost = 0;
    let totalSavings = 0;
    let localCount = 0;
    let remoteCount = 0;
    const modelUsage = {};
    let totalQualityScore = 0;
    let qualityCount = 0;
    let highQualityCount = 0;

    messages.forEach(msg => {
      if (msg.role === 'assistant') {
        totalTokensUsed += msg.tokens_used || 0;
        totalTokensSaved += msg.tokens_saved || 0;
        totalCost += msg.cost_usd || 0;
        totalSavings += msg.savings_usd || 0;

        if (msg.backend === 'local') {
          localCount++;
        } else {
          remoteCount++;
        }

        if (msg.model) {
          modelUsage[msg.model] = (modelUsage[msg.model] || 0) + 1;
        }
        
        // Track quality scores
        if (msg.quality_score !== null && msg.quality_score !== undefined) {
          totalQualityScore += msg.quality_score;
          qualityCount++;
          if (msg.quality_score >= 0.8) {
            highQualityCount++;
          }
        }
      }
    });

    const localPercentage = localCount + remoteCount > 0 
      ? Math.round((localCount / (localCount + remoteCount)) * 100)
      : 0;
    
    const avgQualityScore = qualityCount > 0 ? totalQualityScore / qualityCount : null;

    return {
      totalTokensUsed,
      totalTokensSaved,
      totalCost,
      totalSavings,
      localCount,
      remoteCount,
      localPercentage,
      modelUsage,
      totalMessages: messages.filter(m => m.role === 'assistant').length,
      avgQualityScore,
      qualityCount,
      highQualityCount,
    };
  }, [messages]);

  const theoreticalCost = (stats.totalTokensUsed + stats.totalTokensSaved) * 0.0002 / 1000;
  const savingsRate = theoreticalCost > 0 
    ? Math.round((stats.totalSavings / theoreticalCost) * 100)
    : 0;

  return (
    <div className="stats-panel">
      {/* Header */}
      <div className="stats-header">
        <h3>💰 Token Economics</h3>
        <p className="stats-subtitle">Real-time savings from intelligent routing</p>
      </div>

      {/* Main Savings Card */}
      <div className="stats-card highlight">
        <div className="stat-icon green">
          <TrendingDown size={24} />
        </div>
        <div className="stat-content">
          <div className="stat-label">Total Saved</div>
          <div className="stat-value green">${stats.totalSavings.toFixed(4)}</div>
          <div className="stat-meta">
            {stats.totalTokensSaved.toLocaleString()} tokens saved ({savingsRate}% savings)
          </div>
        </div>
      </div>

      {/* Cost Comparison */}
      <div className="stats-card">
        <div className="stat-row">
          <div className="stat-item">
            <div className="stat-label">💸 Actual Cost</div>
            <div className="stat-value">${stats.totalCost.toFixed(4)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">📊 Would Cost</div>
            <div className="stat-value muted">${theoreticalCost.toFixed(4)}</div>
          </div>
        </div>
      </div>

      {/* Token Usage */}
      <div className="stats-card">
        <h4>🎯 Token Usage</h4>
        <div className="token-breakdown">
          <div className="token-row">
            <span className="token-label">API Tokens Used:</span>
            <span className="token-value">{stats.totalTokensUsed.toLocaleString()}</span>
          </div>
          <div className="token-row success">
            <span className="token-label">Local Tokens (Free):</span>
            <span className="token-value">{stats.totalTokensSaved.toLocaleString()}</span>
          </div>
          <div className="token-row total">
            <span className="token-label">Total Tokens:</span>
            <span className="token-value">
              {(stats.totalTokensUsed + stats.totalTokensSaved).toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Routing Split */}
      <div className="stats-card">
        <h4>🔀 Routing Distribution</h4>
        
        <div className="routing-visual">
          <div className="routing-bar">
            <div 
              className="routing-segment local"
              style={{ width: `${stats.localPercentage}%` }}
              title={`Local: ${stats.localPercentage}%`}
            />
            <div 
              className="routing-segment remote"
              style={{ width: `${100 - stats.localPercentage}%` }}
              title={`Remote: ${100 - stats.localPercentage}%`}
            />
          </div>
          
          <div className="routing-labels">
            <div className="routing-label">
              <span className="dot local"></span>
              <span>Local: {stats.localCount} ({stats.localPercentage}%)</span>
            </div>
            <div className="routing-label">
              <span className="dot remote"></span>
              <span>Cloud: {stats.remoteCount} ({100 - stats.localPercentage}%)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Quality Metrics - PROOF OF ACCURACY */}
      {stats.avgQualityScore !== null && (
        <div className="stats-card">
          <h4>✅ Answer Quality Validation</h4>
          <div style={{ marginBottom: '12px' }}>
            <div style={{
              fontSize: '32px',
              fontWeight: '700',
              color: stats.avgQualityScore >= 0.7 ? '#7ee787' : '#f85149',
              marginBottom: '4px',
            }}>
              {Math.round(stats.avgQualityScore * 100)}%
            </div>
            <div style={{ fontSize: '12px', color: '#8b949e' }}>
              Average quality score across {stats.qualityCount} responses
            </div>
          </div>
          
          <div className="token-breakdown">
            <div className="token-row success">
              <span className="token-label">✓ High Quality (≥80%):</span>
              <span className="token-value">{stats.highQualityCount} / {stats.qualityCount}</span>
            </div>
            <div className="token-row">
              <span className="token-label">Validated Responses:</span>
              <span className="token-value">{stats.qualityCount}</span>
            </div>
          </div>
          
          <div style={{
            marginTop: '12px',
            padding: '10px',
            background: '#1a2f1a',
            borderRadius: '6px',
            borderLeft: '3px solid #238636',
            fontSize: '12px',
            lineHeight: '1.5',
            color: '#c9d1d9',
          }}>
            <strong style={{ color: '#7ee787' }}>💡 Quality Guaranteed:</strong> Every response is validated for completeness, coherence, and relevance. Low-quality answers automatically escalate to premium models.
          </div>
        </div>
      )}

      {/* Model Usage Breakdown */}
      {Object.keys(stats.modelUsage).length > 0 && (
        <div className="stats-card">
          <h4>🤖 Models Used</h4>
          <div className="model-list">
            {Object.entries(stats.modelUsage).map(([model, count]) => (
              <div key={model} className="model-item">
                <span className="model-name">
                  {model.includes('local') || model.includes('qwen') ? '💻' : '☁️'} 
                  {' '}{model.split('/').pop()}
                </span>
                <span className="model-count">{count}×</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conversation Info */}
      <div className="stats-card">
        <h4>📈 Conversation Info</h4>
        <div className="info-grid">
          <div className="info-item">
            <div className="info-label">Total Messages</div>
            <div className="info-value">{conversation?.total_messages || messages.length}</div>
          </div>
          <div className="info-item">
            <div className="info-label">Assistant Replies</div>
            <div className="info-value">{stats.totalMessages}</div>
          </div>
          <div className="info-item">
            <div className="info-label">Avg Cost/Message</div>
            <div className="info-value">
              ${stats.totalMessages > 0 ? (stats.totalCost / stats.totalMessages).toFixed(4) : '0.0000'}
            </div>
          </div>
          <div className="info-item">
            <div className="info-label">Efficiency Score</div>
            <div className="info-value success">{savingsRate}%</div>
          </div>
        </div>
      </div>

      {/* Per-Message Details */}
      <div className="stats-card">
        <h4>📝 Message History</h4>
        <div className="message-stats-list">
          {messages
            .filter(m => m.role === 'assistant')
            .slice(-5) // Last 5 messages
            .reverse()
            .map((msg, idx) => (
              <div key={idx} className="message-stat-item">
                <div className="message-stat-header">
                  <span className={`badge ${msg.backend}`}>
                    {msg.backend === 'local' ? '💻 Local' : '☁️ Cloud'}
                  </span>
                  <span className="message-stat-cost">
                    ${(msg.cost_usd || 0).toFixed(4)}
                  </span>
                </div>
                <div className="message-stat-tokens">
                  {msg.tokens_used > 0 ? `${msg.tokens_used} tokens used` : `${msg.tokens_saved} tokens saved`}
                  {msg.latency_ms && ` · ${msg.latency_ms}ms`}
                </div>
                {msg.quality_score !== null && msg.quality_score !== undefined && (
                  <div style={{
                    marginTop: '6px',
                    fontSize: '11px',
                    padding: '4px 8px',
                    background: msg.quality_score >= 0.7 ? '#1a2f1a' : '#2d1a1a',
                    borderRadius: '4px',
                    color: msg.quality_score >= 0.7 ? '#7ee787' : '#f85149',
                    fontWeight: '600',
                  }}>
                    ✓ Quality: {Math.round(msg.quality_score * 100)}% 
                    {msg.quality_score >= 0.8 && ' (Excellent)'}
                    {msg.quality_score >= 0.7 && msg.quality_score < 0.8 && ' (Good)'}
                    {msg.quality_score < 0.7 && ' (Escalated)'}
                  </div>
                )}
              </div>
            ))}
        </div>
      </div>

      {/* Key Insight */}
      <div className="stats-card insight">
        <div className="insight-icon">💡</div>
        <div className="insight-content">
          <strong>Smart Routing Impact:</strong>
          <p>
            By using local models for simple queries, you've saved 
            <strong> {stats.totalTokensSaved.toLocaleString()} tokens</strong> 
            {' '}(${stats.totalSavings.toFixed(4)}) in this conversation!
          </p>
        </div>
      </div>
    </div>
  );
}
