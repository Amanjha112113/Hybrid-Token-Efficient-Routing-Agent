# 🧪 Testing Guide: Token Economics Dashboard

## Quick Start

### 1. Verify Services are Running

```bash
# Check backend (should show Python process on port 8000)
lsof -i :8000 | grep LISTEN

# Check frontend (should show Node process on port 5173)
lsof -i :5173 | grep LISTEN

# If not running, start them:
# Terminal 1 - Backend
python server.py

# Terminal 2 - Frontend
cd frontend && npm run dev
```

### 2. Open Frontend

Navigate to: **http://localhost:5173**

You should see:
- ✅ Dark theme interface (GitHub-style)
- ✅ Left sidebar with "CONVERSATIONS" section
- ✅ Green "+ New Conversation" button
- ✅ Empty chat area with 💬 icon

## Test Scenarios

### Scenario 1: Local Routing (Token Savings)

**Goal:** Verify local model routing and savings display

1. Click **"+ New Conversation"**
2. Send message: **"What is 2+2?"**
3. Observe:
   - ✅ Message streams token-by-token
   - ✅ Blue blinking cursor during streaming
   - ✅ Assistant message shows **💻 Local** badge (green)
   - ✅ **Stats panel appears** on the right
   - ✅ "💰 Token Economics" header visible
   - ✅ **Total Saved** card shows green value > $0
   - ✅ **Tokens Saved** count > 0
   - ✅ **Routing Distribution** bar is 100% green (local)
   - ✅ "🤖 Models Used" shows `qwen2.5:3b` with 💻 icon

### Scenario 2: Cloud Routing (Token Usage)

**Goal:** Verify cloud model routing and cost display

1. In same conversation, send: **"Write a detailed essay about quantum computing"**
2. Observe:
   - ✅ May route to **☁️ Cloud** (blue badge) if complexity is high
   - ✅ Stats panel updates:
     - **Tokens Used** increases (paid tokens)
     - **Cost USD** shows actual cost (> $0)
     - **Routing bar** now shows blue section
   - ✅ Per-message stats show individual cost

### Scenario 3: Mixed Conversation

**Goal:** Test cumulative statistics across multiple messages

1. Send 5 messages alternating simple/complex:
   - "Hi there" (local)
   - "Explain machine learning" (may be cloud)
   - "What's 5+3?" (local)
   - "Compare neural network architectures" (likely cloud)
   - "Thanks!" (local)

2. Verify stats panel shows:
   - ✅ **Total Messages** count increases
   - ✅ **Routing Distribution** bar shows split
   - ✅ **Efficiency Score** shows percentage
   - ✅ **Message History** shows last 5 with badges
   - ✅ **Key Insight** card summarizes savings

### Scenario 4: Multiple Conversations

**Goal:** Test conversation management

1. Create 3 conversations with different content
2. Click between them in sidebar
3. Observe:
   - ✅ Stats panel updates for each conversation
   - ✅ Message history loads correctly
   - ✅ Token counts are per-conversation
   - ✅ No data leakage between conversations

## Manual Backend Test

Run the integration test script:

```bash
python3 test_stats_integration.py
```

Expected output:
```
1. Creating test conversation...
   ✓ Created conversation: [UUID]
2. Sending message: 'What is 2+2?'
   ✓ Stream complete!
3. Token Metadata:
   - Backend: local
   - Model: qwen2.5:3b
   - Tokens Saved: [NUMBER]
   - Savings USD: $[AMOUNT]
✅ SUCCESS: Token metadata correctly saved to database!
```

## Inspect Database

```bash
sqlite3 gateway.db

-- View all conversations
SELECT id, title, total_messages FROM conversations;

-- View message with token stats
SELECT 
  role, 
  backend, 
  tokens_used, 
  tokens_saved, 
  cost_usd, 
  savings_usd 
FROM conversation_messages 
ORDER BY created_at DESC 
LIMIT 10;

-- Calculate total savings
SELECT 
  SUM(tokens_saved) as total_saved_tokens,
  SUM(savings_usd) as total_savings
FROM conversation_messages;
```

## Visual Verification Checklist

### Stats Panel Components

- [ ] **Header**: "💰 Token Economics" with subtitle
- [ ] **Card 1**: Total Saved (green gradient, trending down icon)
- [ ] **Card 2**: Cost Comparison (Actual vs Would Cost)
- [ ] **Card 3**: Token Usage Breakdown (3 rows with colors)
- [ ] **Card 4**: Routing Distribution (animated bar + labels)
- [ ] **Card 5**: Models Used (list with icons)
- [ ] **Card 6**: Conversation Info (4-cell grid)
- [ ] **Card 7**: Message History (last 5 with badges)
- [ ] **Card 8**: Key Insight (lightbulb icon, blue gradient)

### Layout Verification

- [ ] Left sidebar: 260px width
- [ ] Center chat: Flexible width
- [ ] Right stats: 360px width (only visible when conversation active)
- [ ] Total width fits on 1920px screen without scroll
- [ ] Scrollbars work independently for each column

### Color Coding

- [ ] Local messages: Green badge (#238636)
- [ ] Cloud messages: Blue badge (#1f6feb)
- [ ] Savings/success: Green text (#7ee787)
- [ ] Costs: White/gray text
- [ ] Routing bar: Green (local) + Blue (cloud)

## Expected Numbers

For a simple local message like "What is 2+2?":

```yaml
backend: "local"
model: "qwen2.5:3b"
tokens_used: 0
tokens_saved: 3-10 (approximate)
cost_usd: 0.0
savings_usd: 0.000001 (very small but > 0)
latency_ms: 1000-5000 (depends on hardware)
```

For a complex cloud message:

```yaml
backend: "fireworks"
model: "llama-v3p1-8b-instruct" or similar
tokens_used: 100-500 (depends on length)
tokens_saved: 0
cost_usd: 0.00001-0.0001 (depends on tokens)
savings_usd: 0.0
latency_ms: 2000-8000 (network dependent)
```

## Common Issues & Fixes

### Issue: Stats Panel Not Showing

**Cause:** No conversation selected  
**Fix:** Click "+ New Conversation" first

### Issue: All Stats Show Zero

**Cause:** No messages sent yet  
**Fix:** Send at least one message

### Issue: Streaming Not Working

**Check:**
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check Ollama is running (for local routing)
curl http://localhost:11434/api/tags
```

### Issue: Frontend Shows Black Screen

**Fix:** Clear browser cache and reload
- Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
- Check browser console for errors (F12)

### Issue: "Conversation not found" Error

**Cause:** Database might be out of sync  
**Fix:**
```bash
# Restart backend
# It will reconnect to database
pkill -f server.py
python server.py
```

## Performance Benchmarks

Expected performance (M1 MacBook or equivalent):

| Metric | Target | Acceptable |
|--------|--------|------------|
| Local response time | < 2s | < 5s |
| Cloud response time | < 3s | < 8s |
| UI update latency | < 100ms | < 500ms |
| Stats calculation | < 50ms | < 200ms |
| Token streaming rate | > 50 tokens/s | > 20 tokens/s |

## Browser Compatibility

Tested and working on:
- ✅ Chrome 120+
- ✅ Firefox 121+
- ✅ Safari 17+
- ✅ Edge 120+

## Success Criteria

You've successfully integrated the token economics dashboard when:

1. ✅ You can send messages and see streaming responses
2. ✅ Stats panel displays on the right side
3. ✅ Local messages show token savings (green)
4. ✅ Cloud messages show token costs (blue)
5. ✅ Routing distribution bar updates correctly
6. ✅ Cumulative savings increase across messages
7. ✅ Per-message history shows individual stats
8. ✅ Database stores all token metadata
9. ✅ Multiple conversations maintain separate stats
10. ✅ Interface is responsive and visually appealing

## Next Step: Demo Recording

Once all tests pass, record a demo:

1. Open screen recording
2. Create new conversation
3. Send 5-6 messages (mix of simple/complex)
4. Show stats panel updating in real-time
5. Switch between conversations
6. Highlight the savings metrics

This demonstrates your unique value proposition: **AI with transparent token economics**.

---

**Questions or issues?** Check server logs:
```bash
# Backend logs
tail -f /path/to/logs

# Or run with verbose logging
python server.py --log-level DEBUG
```
