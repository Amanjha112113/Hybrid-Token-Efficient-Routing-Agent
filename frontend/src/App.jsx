import React, { useState, useEffect } from 'react';
import { 
  Zap, 
  Cpu, 
  Send, 
  Activity, 
  HelpCircle, 
  RefreshCw, 
  AlertTriangle,
  Code,
  FileText,
  BarChart3,
  TrendingDown,
  Layers
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

const TEMPLATES = [
  { label: 'Sentiment', prompt: "Classify the sentiment of this review: 'The package arrived three weeks late and the item inside was shattered.'" },
  { label: 'NER Extraction', prompt: "Extract all named entities and their types from: 'Larry Page and Sergey Brin founded Google in California on September 4, 1998.'" },
  { label: 'Factual Quiz', prompt: "What is the capital of Australia, and what body of water is it near?" },
  { label: 'Logic Puzzle', prompt: "Three friends, Sam, Jo, and Lee, each own a different pet: cat, dog, bird. Sam does not own the bird. Jo owns the dog. Who owns the cat?" },
  { label: 'Math Algebra', prompt: "Solve for x: 3x + 15 = 45" },
  { label: 'Code Debugging', prompt: "This Python function has a bug: def get_max(nums): return nums[0]. It should return the maximum element in the list. Fix it." }
];

export default function App() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [stats, setStats] = useState({
    total_requests: 0,
    local_count: 0,
    remote_count: 0,
    tokens_saved: 0,
    tokens_used: 0,
    history: []
  });
  const [activeStep, setActiveStep] = useState(0); // 0: Idle, 1: Classifying, 2: Routing, 3: Completed

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleRoute = async (e) => {
    e.preventDefault();
    if (!prompt.trim() || loading) return;

    setLoading(true);
    setResult(null);
    
    // Animate Flow steps
    setActiveStep(1); // Classifying
    
    try {
      await new Promise(r => setTimeout(r, 800));
      setActiveStep(2); // Routing
      
      const response = await fetch(`${API_BASE}/api/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });

      if (!response.ok) throw new Error("Server returned an error");
      const data = await response.json();
      
      await new Promise(r => setTimeout(r, 500));
      setResult(data);
      setActiveStep(3); // Completed
      fetchStats();
    } catch (err) {
      console.error(err);
      alert("Failed to connect to backend server. Make sure server.py is running on port 8000.");
      setActiveStep(0);
    } finally {
      setLoading(false);
    }
  };

  const costSavedDollars = (stats.tokens_saved * 0.0002 / 1000).toFixed(4); // Llama 8B equivalent cost
  const localRatio = stats.total_requests > 0 
    ? Math.round((stats.local_count / stats.total_requests) * 100) 
    : 0;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="logo-section">
          <h1>
            <Layers size={32} className="text-highlight" />
            Hybrid Token-Efficient Routing Agent
            <span className="logo-badge">AMD Hackathon</span>
          </h1>
        </div>
        <div className="response-meta">
          <Activity size={18} className="text-highlight" />
          <span>Local Model: Qwen 1.5B (GGUF)</span>
          <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
          <span>Remote API: Fireworks AI</span>
        </div>
      </header>

      {/* Stats Dashboard Grid */}
      <section className="stats-strip">
        <div className="glass-card stat-item">
          <span className="stat-label">Total API Tokens Saved</span>
          <span className="stat-val highlight">
            {stats.tokens_saved.toLocaleString()}
          </span>
          <span className="response-meta" style={{ color: 'var(--success)' }}>
            <TrendingDown size={14} /> Est. ${costSavedDollars} USD Saved
          </span>
        </div>
        <div className="glass-card stat-item">
          <span className="stat-label">Local Routing Ratio</span>
          <span className="stat-val highlight">
            {localRatio}%
          </span>
          <span className="response-meta">
            {stats.local_count} of {stats.total_requests} handled locally
          </span>
        </div>
        <div className="glass-card stat-item">
          <span className="stat-label">Total API Tokens Spent</span>
          <span className="stat-val" style={{ color: '#fff' }}>
            {stats.tokens_used.toLocaleString()}
          </span>
          <span className="response-meta">
            Used by remote Fireworks models
          </span>
        </div>
      </section>

      {/* Main Panel grid */}
      <main className="main-grid">
        {/* Left Side: Console & Response */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <section className="glass-card">
            <h2 className="console-title">
              <Code size={20} style={{ color: 'var(--text-highlight)' }} />
              Inference Sandbox Console
            </h2>

            <form onSubmit={handleRoute}>
              <div className="input-area">
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Enter a prompt, or choose one of the templates below..."
                  disabled={loading}
                />
              </div>

              <div className="quick-templates">
                {TEMPLATES.map((tmpl, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="template-btn"
                    onClick={() => setPrompt(tmpl.prompt)}
                    disabled={loading}
                  >
                    {tmpl.label}
                  </button>
                ))}
              </div>

              <div className="action-row">
                <button
                  type="submit"
                  className="route-btn"
                  disabled={loading || !prompt.trim()}
                >
                  {loading ? (
                    <>
                      <RefreshCw size={18} className="animate-spin" />
                      Routing Query...
                    </>
                  ) : (
                    <>
                      <Send size={18} />
                      Route Prompt
                    </>
                  )}
                </button>
              </div>
            </form>
          </section>

          {/* Active response box */}
          {result && (
            <section className="glass-card response-container">
              <div className="response-header">
                <h3 className="console-title" style={{ margin: 0 }}>
                  <FileText size={20} style={{ color: 'var(--text-highlight)' }} />
                  Inference Answer
                </h3>
                <div className="response-meta">
                  <span className={`history-tag ${result.backend}`}>
                    {result.backend === 'local' ? 'Offline Local Model' : 'Fireworks API'}
                  </span>
                  <span>Category: <strong>{result.category}</strong></span>
                  <span>Spent: <strong>{result.tokens_used} tokens</strong></span>
                  <span>Time: <strong>{result.elapsed_seconds.toFixed(2)}s</strong></span>
                </div>
              </div>

              <div className="response-body">
                {result.category.includes('code') || result.answer.includes('def ') || result.answer.includes('```') ? (
                  <pre className="code-block">
                    <code>{result.answer.replace(/```python|```/g, '')}</code>
                  </pre>
                ) : (
                  result.answer
                )}
              </div>
            </section>
          )}
        </div>

        {/* Right Side: Flow Visualization & History */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <section className="glass-card">
            <h2 className="console-title">
              <Activity size={20} style={{ color: 'var(--text-highlight)' }} />
              Live Routing Visualizer
            </h2>

            <div className="flow-diagram">
              <div className={`flow-node ${activeStep >= 1 ? 'active' : ''}`}>
                User Prompt Input
              </div>
              <div className="flow-arrow">↓</div>
              <div className={`flow-node ${activeStep >= 1 ? 'active' : ''}`}>
                Category Classifier
              </div>
              <div className="flow-arrow">↓</div>
              
              {/* Branch Decision Visualized */}
              <div style={{ display: 'flex', gap: '1rem', width: '100%' }}>
                <div className={`flow-node ${
                  activeStep === 3 && result?.backend === 'local' ? 'highlight-local' : ''
                }`} style={{ flex: 1 }}>
                  <Cpu size={16} />
                  Local Qwen (0 Cost)
                </div>
                <div className={`flow-node ${
                  activeStep === 3 && result?.backend === 'remote' || activeStep === 3 && result?.backend === 'fireworks' ? 'highlight-remote' : ''
                }`} style={{ flex: 1 }}>
                  <Zap size={16} />
                  Fireworks API
                </div>
              </div>
            </div>
          </section>

          {/* History log */}
          <section className="glass-card">
            <h2 className="console-title">
              <BarChart3 size={20} style={{ color: 'var(--text-highlight)' }} />
              Recent Logs
            </h2>

            <div className="history-list">
              {stats.history.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#8b9bb4', padding: '1rem' }}>
                  No requests handled yet. Send a prompt to populate the log.
                </div>
              ) : (
                stats.history.map((item, idx) => (
                  <div key={idx} className="history-item" onClick={() => setPrompt(item.prompt)}>
                    <div>
                      <div className="history-prompt">{item.prompt}</div>
                      <div className="response-meta" style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                        {item.category} • {item.elapsed_seconds}s
                      </div>
                    </div>
                    <span className={`history-tag ${item.backend}`}>
                      {item.backend}
                    </span>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
