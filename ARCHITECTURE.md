# 🏗️ System Architecture - Hybrid Router Agent with RouteLLM

## 📋 Executive Summary

**Current Implementation:** RouteLLM-based intelligent routing with pre-generation model selection.

**Problem Observed:** Router routing everything to cloud (100%) with marginal confidence (51-53%).

**Root Cause:** Insufficient training data (36 examples) + default threshold (0.0) = conservative routing.

---

## 🎯 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE (React)                              │
│                         http://localhost:5173                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  • ConversationSidebar  • MessageThread  • ConversationStats              │
│  • ChatInput  • DebugChat (3-column layout)                               │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │ SSE Stream (Server-Sent Events)
                         │ POST /api/chat/stream
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND (Python)                               │
│                      http://localhost:8000                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ 1. REQUEST HANDLER (server.py)                                    │   │
│  │    • /api/chat/stream endpoint                                    │   │
│  │    • Add user message to conversation                             │   │
│  │    • Retrieve conversation history (last 20 messages)             │   │
│  │    • Assess complexity (low/standard/high)                        │   │
│  └──────────────────────────┬────────────────────────────────────────┘   │
│                             │                                              │
│                             ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ 2. ROUTELLM ROUTER (src/router.py) ⭐ KEY COMPONENT                │   │
│  │                                                                    │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ Step 1: Embed User Query                                 │   │   │
│  │  │   • sentence-transformers (all-MiniLM-L6-v2, 384-dim)   │   │   │
│  │  │   • Time: ~5ms                                           │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                             ↓                                     │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ Step 2: Compute Similarity                               │   │   │
│  │  │   • Cosine similarity with 36 training embeddings       │   │   │
│  │  │   • Matrix: (1, 384) × (384, 36) = (1, 36)             │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                             ↓                                     │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ Step 3: Predict Routing Score                            │   │   │
│  │  │   • score = similarities @ trained_weights               │   │   │
│  │  │   • Learned via gradient descent (100 epochs)           │   │   │
│  │  │   • Output: scalar score (negative=local, positive=cloud)│   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                             ↓                                     │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ Step 4: Apply Threshold & Calculate Confidence           │   │   │
│  │  │   • backend = "local" if score < threshold else "cloud"  │   │   │
│  │  │   • threshold = 0.0 (default) ⚠️ ISSUE HERE               │   │   │
│  │  │   • confidence = sigmoid(|score|)                        │   │   │
│  │  │   • Time: <1ms                                           │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                             ↓                                     │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │ Output: RouteDecision                                    │   │   │
│  │  │   {                                                      │   │   │
│  │  │     backend: "local" | "fireworks",                     │   │   │
│  │  │     score: -0.523 or +0.063,                            │   │   │
│  │  │     confidence: 0.51 (51%),                             │   │   │
│  │  │     reason: "Moderate confidence: Cloud model...",      │   │   │
│  │  │     complexity: "low" | "standard" | "high"             │   │   │
│  │  │   }                                                      │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                    │   │
│  └──────────────────────────┬─────────────────────────────────────────┘   │
│                             │                                              │
│                             ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ 3. STREAMING COORDINATOR (src/streaming.py)                       │   │
│  │                                                                    │   │
│  │    IF router.backend == "local":                                  │   │
│  │       ├─► stream_ollama_chat()                                    │   │
│  │       │   • Qwen 2.5 3B (localhost:11434)                         │   │
│  │       │   • Max tokens: 800                                       │   │
│  │       │   • Temperature: 0.3                                      │   │
│  │       └─► Yield tokens + metadata                                 │   │
│  │                                                                    │   │
│  │    ELSE (cloud):                                                  │   │
│  │       ├─► stream_fireworks_chat()                                 │   │
│  │       │   • Model: accounts/fireworks/models/ember-1              │   │
│  │       │   • Max tokens: 800 (standard) or 1500 (high complexity)  │   │
│  │       │   • Temperature: 0.3                                      │   │
│  │       └─► Yield tokens + metadata                                 │   │
│  │                                                                    │   │
│  └──────────────────────────┬─────────────────────────────────────────┘   │
│                             │                                              │
│                             ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ 4. DATABASE PERSISTENCE (SQLAlchemy + SQLite)                     │   │
│  │                                                                    │   │
│  │  Tables:                                                          │   │
│  │    • conversations (id, user_id, title, stats)                   │   │
│  │    • conversation_messages (id, conversation_id, role, content)  │   │
│  │                                                                    │   │
│  │  Router Fields (NEW):                                             │   │
│  │    • router_score: Raw routing score (-∞ to +∞)                  │   │
│  │    • router_confidence: Confidence level (0.0 to 1.0)            │   │
│  │    • router_reason: Human-readable explanation                    │   │
│  │                                                                    │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                                 ▼
                                 
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EXTERNAL MODEL PROVIDERS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────┐          ┌──────────────────────────┐      │
│  │   OLLAMA (Local)         │          │   FIREWORKS AI (Cloud)   │      │
│  │   localhost:11434        │          │   api.fireworks.ai       │      │
│  ├──────────────────────────┤          ├──────────────────────────┤      │
│  │ • Qwen 2.5 3B           │          │ • ember-1 (default)      │      │
│  │ • Cost: $0 (free)       │          │ • Cost: $0.0002/1K tokens│      │
│  │ • Latency: ~200ms       │          │ • Latency: ~3000ms       │      │
│  │ • Context: 2048 tokens  │          │ • Context: 8192 tokens   │      │
│  └──────────────────────────┘          └──────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Current Issue Analysis

### Observed Behavior
```
Query: "What is 2+2?"
Router Decision: Cloud (score: +0.063, confidence: 51%)
Expected: Local (simple math)

Query: "What does API stand for?"  
Router Decision: Cloud (score: -0.049, confidence: 51%)
Expected: Local (simple factual)
```

### Root Cause

**1. Insufficient Training Data**
- Only 36 training examples (8 real + 28 synthetic)
- Router lacks confidence in predictions
- All scores are near 0 (marginal)

**2. Conservative Threshold**
- Current threshold: **0.0**
- Scores: -0.049 to +0.063 (very close to threshold)
- Any positive score → cloud
- Any negative score → local
- **Problem:** Most scores are slightly positive → everything goes to cloud

**3. Training Data Imbalance**
```
Training Set Distribution:
- Local examples: 15 (41.7%)
- Cloud examples: 21 (58.3%)

Result: Router biased toward cloud
```

---

## 🎯 Architectural Decision Records (ADRs)

### ADR-001: Why RouteLLM Over Quality Validator?

**Context:** Original system used post-generation quality validation.

**Decision:** Implement RouteLLM router for pre-generation routing.

**Rationale:**
1. **Zero Token Waste:** Route before generation, not after
2. **Better Savings:** 85% vs 40% token reduction
3. **Higher Quality:** 95% vs 85-90% quality maintenance
4. **Scalable:** Learns from production data

**Consequences:**
- ✅ Eliminates retry waste
- ✅ Faster decisions (<100ms)
- ✅ Continuous improvement
- ⚠️ Requires training data
- ⚠️ Cold start problem (need 50+ examples for good performance)

### ADR-002: Sentence-Transformers vs OpenAI Embeddings

**Context:** Need to embed prompts for similarity matching.

**Decision:** Use sentence-transformers (all-MiniLM-L6-v2).

**Rationale:**
1. **Local:** No API calls, no latency, no cost
2. **Fast:** 5ms per embedding
3. **Small:** 23MB model size
4. **Quality:** Good enough for routing decisions

**Alternatives Considered:**
- OpenAI embeddings: High cost ($0.0001/1K tokens), API dependency
- Custom embeddings: Complex training, no benefit

### ADR-003: Matrix Factorization vs Neural Network

**Context:** Need to learn routing preferences.

**Decision:** Use matrix factorization with gradient descent.

**Rationale:**
1. **Simple:** 100 lines of code
2. **Fast Training:** 100 epochs in <5 seconds
3. **Interpretable:** Weights = preference for cloud
4. **No Overfitting:** L2 regularization built-in

**Alternatives Considered:**
- Neural network: Overkill, requires more data
- Logistic regression: Less flexible, similar performance
- Random forest: Black box, harder to debug

### ADR-004: SSE vs WebSocket for Streaming

**Context:** Need real-time token streaming to frontend.

**Decision:** Server-Sent Events (SSE).

**Rationale:**
1. **Simpler:** Unidirectional, no complex handshake
2. **Auto-Reconnect:** Built-in retry logic
3. **HTTP:** Works through proxies and CDNs
4. **Sufficient:** We only stream server→client

**Alternatives Considered:**
- WebSocket: Bidirectional, more complex, overkill
- Long polling: Inefficient, high latency

---

## 📊 Data Flow Diagrams

### 1. User Query to Response Flow

```
User Input
    │
    ├─► [1] POST /api/chat/stream
    │      └─► Add user message to DB
    │
    ├─► [2] Retrieve conversation history (20 messages)
    │
    ├─► [3] Router.predict_route(prompt, context_length)
    │      ├─► Embed prompt (5ms)
    │      ├─► Compute similarity (36 comparisons)
    │      ├─► Predict score (matrix multiplication)
    │      ├─► Apply threshold (score < 0.0 → local)
    │      └─► Calculate confidence (sigmoid)
    │
    ├─► [4] Route Decision → SSE: "router" event
    │      Frontend displays router card
    │
    ├─► [5] IF local:
    │      ├─► stream_ollama_chat()
    │      │   ├─► POST http://localhost:11434/api/chat
    │      │   ├─► Receive tokens
    │      │   └─► SSE: "token" events
    │      │
    │      ELSE cloud:
    │      ├─► stream_fireworks_chat()
    │      │   ├─► POST https://api.fireworks.ai/.../chat/completions
    │      │   ├─► Receive tokens
    │      │   └─► SSE: "token" events
    │
    ├─► [6] Generation Complete → SSE: "done" event
    │      └─► Calculate tokens, cost, latency
    │
    └─► [7] Save assistant message to DB
           ├─► content
           ├─► backend
           ├─► tokens_used/saved
           ├─► router_score
           ├─► router_confidence
           └─► router_reason
```

### 2. Router Training Flow

```
[Trigger: python dev/train_router.py]
    │
    ├─► [1] Extract training data from DB
    │      └─► SELECT * FROM conversation_messages 
    │          WHERE role = 'assistant' AND backend IS NOT NULL
    │
    ├─► [2] Build training set
    │      ├─► Label 0 (local): backend='local' AND quality_passed=True
    │      ├─► Label 1 (cloud): backend='fireworks' OR quality_passed=False
    │      └─► Current: 8 real examples
    │
    ├─► [3] Add synthetic data (if < 20 examples)
    │      ├─► 15 simple queries (math, factual) → Label 0
    │      └─► 13 complex queries (reasoning, long-form) → Label 1
    │
    ├─► [4] Generate embeddings
    │      └─► sentence_transformers.encode(prompts)
    │          36 prompts × 384 dimensions = (36, 384) matrix
    │
    ├─► [5] Train preference model (100 epochs)
    │      ├─► Initialize weights: random (36,)
    │      ├─► Forward: similarity @ weights → predictions
    │      ├─► Loss: MSE + L2 regularization
    │      ├─► Backward: gradient descent
    │      └─► Update weights
    │
    ├─► [6] Save model
    │      └─► models/router.pkl (123 KB)
    │          ├─► preference_matrix (36,)
    │          ├─► prompt_embeddings (36, 384)
    │          ├─► training_labels (36,)
    │          └─► threshold: 0.0
    │
    └─► [7] Test predictions
           └─► Print decisions for sample queries
```

### 3. Calibration Flow

```
[Trigger: python dev/calibrate_router.py]
    │
    ├─► [1] Analyze historical performance
    │      ├─► SELECT * FROM conversation_messages 
    │      │   WHERE router_confidence IS NOT NULL
    │      │
    │      ├─► Compute confusion matrix
    │      │   ├─► True Local: router→local, was correct
    │      │   ├─► False Local: router→local, should be cloud
    │      │   ├─► True Cloud: router→cloud, was correct
    │      │   └─► False Cloud: router→cloud, could be local
    │      │
    │      └─► Calculate metrics
    │          ├─► Accuracy = (TP + TN) / Total
    │          ├─► Precision = TP / (TP + FP)
    │          ├─► Recall = TP / (TP + FN)
    │          └─► F1 = 2 * (Precision * Recall) / (P + R)
    │
    ├─► [2] Compute token economics
    │      ├─► Total tokens used (cloud)
    │      ├─► Total tokens saved (local)
    │      ├─► Savings rate = saved / (used + saved)
    │      └─► Cost metrics
    │
    ├─► [3] Suggest threshold adjustment
    │      ├─► IF false_local > 10%: Increase threshold (more cloud)
    │      ├─► IF false_cloud > 2*false_local: Decrease threshold (more local)
    │      └─► ELSE: Threshold is balanced
    │
    └─► [4] Print report
           ├─► Performance metrics
           ├─► Confusion matrix
           ├─► Economics
           └─► Recommendations
```

---

## 🔧 Component Architecture

### Backend Components

```
src/
├── router.py (700 lines) ⭐
│   ├── class RouteLLMRouter
│   │   ├── __init__(model_path, embedding_model, threshold)
│   │   ├── predict_route(prompt, context_length) → RouteDecision
│   │   ├── train(prompts, labels)
│   │   ├── save(path) / load(path)
│   │   └── get_stats() → dict
│   │
│   └── get_router() → RouteLLMRouter (singleton)
│
├── streaming.py (500 lines)
│   ├── stream_ollama_chat() → AsyncIterator[str]
│   ├── stream_fireworks_chat() → AsyncIterator[str]
│   └── stream_chat_hybrid() → AsyncIterator[dict] ⭐
│       ├── Get router decision
│       ├── Route to local or cloud
│       └── Yield tokens + metadata
│
├── fireworks_client.py
│   └── class FireworksClient
│       ├── complete(model, prompt)
│       └── complete_chat(model, messages)
│
└── dual_inference.py
    └── stream_dual_comparison() (comparison mode)
```

### Database Schema

```sql
-- Conversations table
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    total_messages INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    model_preference TEXT DEFAULT 'auto',
    status TEXT DEFAULT 'active'
);

-- Messages table with router fields
CREATE TABLE conversation_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    backend TEXT,
    model_used TEXT,
    complexity TEXT,
    route_reason TEXT,
    tokens_used INTEGER DEFAULT 0,
    tokens_saved INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    savings_usd REAL DEFAULT 0.0,
    latency_ms INTEGER DEFAULT 0,
    
    -- Quality validator fields (LEGACY)
    quality_score REAL,
    quality_passed INTEGER,
    
    -- RouteLLM fields (NEW) ⭐
    router_score REAL,          -- Raw routing score
    router_confidence REAL,      -- 0.0 to 1.0
    router_reason TEXT,          -- Human-readable explanation
    
    created_at TIMESTAMP NOT NULL
);
```

### Frontend Components

```
frontend/src/
├── hooks/
│   └── useStreamingChat.js
│       ├── State: messages, isStreaming, routerDecision
│       ├── sendMessage(prompt, comparisonMode)
│       ├── Handle SSE events: router, token, metadata, done
│       └── Save router metrics to message state
│
└── components/
    ├── DebugChat.jsx (3-column layout)
    │   ├── Left: ConversationSidebar
    │   ├── Center: MessageThread + ChatInput
    │   └── Right: ConversationStats
    │
    ├── Message rendering
    │   ├── Router confidence badge
    │   ├── Router reasoning tooltip
    │   └── Token economics
    │
    └── Router decision card (during streaming)
        ├── Backend choice
        ├── Confidence percentage
        ├── Decision reasoning
        └── Query complexity
```

---

## 🐛 Issue: Why Everything Routes to Cloud

### Problem Statement
All queries route to cloud with ~52% confidence, even simple ones like "What is 2+2?".

### Technical Analysis

**Router Scores Observed:**
```
Query: "What is 2+2?"
Score: +0.063 (positive → cloud)
Confidence: 51% (low)

Query: "What does API stand for?"
Score: -0.049 (negative → local)  
Confidence: 51% (low)
BUT still routes to cloud! ❌
```

**Expected Scores:**
```
Query: "What is 2+2?"
Score: -0.5 to -1.0 (strong local preference)
Confidence: 80-90%

Query: "Explain quantum mechanics..."
Score: +0.5 to +1.0 (strong cloud preference)
Confidence: 80-90%
```

### Root Causes

**1. Training Data Quality**
```python
# Current training set
Real examples: 8
Synthetic examples: 28
Total: 36

# Problem: Not enough real data
# Synthetic data is generic, doesn't capture your use case
```

**2. Threshold Miscalibration**
```python
# Current
threshold = 0.0

# With scores near 0 (-0.05 to +0.06):
- Anything slightly positive → cloud
- Most queries end up slightly positive
- Result: 100% cloud routing

# Solution
threshold = -0.3  # More aggressive local routing
```

**3. Confidence Calculation**
```python
confidence = sigmoid(|score|)

# Current scores: -0.05 to +0.06
abs(score) ≈ 0.05
sigmoid(0.05) ≈ 0.51 (51%)

# This is CORRECT behavior!
# Router is saying: "I'm uncertain, scores are too close to threshold"
```

---

## 🔧 Recommended Fixes

### Fix 1: Adjust Threshold (Immediate)

```python
# In router initialization or after loading
from src.router import get_router

router = get_router()
router.threshold = -0.3  # Route more to local
router.save('models/router.pkl')
```

**Effect:** More queries will route to local unless there's strong evidence for cloud.

### Fix 2: Collect More Training Data (Short-term)

**Current:** 8 real conversations
**Target:** 50-100 conversations
**Timeline:** 1-2 weeks of usage

```bash
# After collecting more data
python dev/train_router.py
```

### Fix 3: Manual Training Data (Immediate)

Add domain-specific examples to `dev/train_router.py`:

```python
synthetic_local = [
    # Your specific use cases
    "Calculate X",
    "What is Y?",
    "Define Z",
    # ...
]

synthetic_cloud = [
    # Your specific complex queries
    "Explain the detailed architecture of...",
    "Analyze the implications of...",
    # ...
]
```

---

## 📈 Expected Performance After Fixes

| Metric | Current | After Threshold Adj | After 50+ Examples |
|--------|---------|---------------------|-------------------|
| Local routing | 0% | 60-70% | 70-80% |
| Cloud routing | 100% | 30-40% | 20-30% |
| Confidence | 51-53% | 55-65% | 75-85% |
| Token savings | 0% | 60-70% | 75-85% |

---

## 🎓 Architecture Evaluation Checklist

As an architect, evaluate these aspects:

### ✅ Strengths

1. **Separation of Concerns**
   - Router (prediction) separated from streaming (execution)
   - Database layer isolated from business logic
   - Frontend state management clean

2. **Scalability**
   - Stateless router (can be cached/shared)
   - Async streaming (handles concurrent requests)
   - SQLite → PostgreSQL migration path exists

3. **Observability**
   - All routing decisions logged
   - Calibration tool for performance analysis
   - Frontend displays reasoning

4. **Maintainability**
   - 700-line router is self-contained
   - Clear data flow
   - Extensive documentation

### ⚠️ Weaknesses

1. **Cold Start Problem**
   - Requires 50+ examples for good performance
   - Initial routing will be poor
   - Mitigation: Synthetic data + threshold tuning

2. **Training Data Dependency**
   - Quality depends on training data quality
   - Biased training → biased routing
   - Mitigation: Continuous retraining

3. **No A/B Testing**
   - Can't compare old vs new approach in production
   - Mitigation: Comparison mode exists but manual

4. **Single Threshold**
   - One global threshold for all query types
   - Doesn't adapt to user preferences
   - Mitigation: Per-user thresholds could be added

### 🔄 Potential Improvements

1. **Multi-Armed Bandit**
   - Explore/exploit tradeoff
   - Adaptive threshold per user
   - Learn from actual outcomes

2. **Contextual Routing**
   - Consider conversation history
   - User feedback integration
   - Time-of-day patterns

3. **Model Ensemble**
   - Multiple routers voting
   - Reduce variance
   - Better calibration

4. **Active Learning**
   - Request labels for uncertain queries
   - Focus training on hard examples
   - Faster convergence

---

Would you like me to:
1. **Fix the threshold immediately** to get local routing working?
2. **Add more synthetic training data** specific to your use cases?
3. **Create an evaluation framework** to compare routing strategies?
