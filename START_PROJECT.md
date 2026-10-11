# Quick Start Guide - Hybrid Router Agent

## ✅ Current Status
- ✅ RouteLLM router implemented and trained (64 examples)
- ✅ Router routing correctly: simple → local, complex → cloud
- ✅ Threshold fixed to +0.15 (handles positive score bias)
- ✅ Database migrated with router fields
- ✅ Frontend integrated with router display
- ✅ All 8 implementation tasks complete

## 🚀 Start the Project

### Step 1: Kill any running processes
```bash
lsof -ti:8000 -ti:5173 | xargs kill -9 2>/dev/null
```

### Step 2: Start Backend (Terminal 1)
```bash
cd /Users/amanjha/Desktop/projects/Hybrid-router-agent
uvicorn server:app --reload --port 8000
```
**Expected output:**
```
INFO:     Will watch for changes in these directories: ['/Users/amanjha/Desktop/projects/Hybrid-router-agent']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 3: Start Frontend (Terminal 2)
```bash
cd /Users/amanjha/Desktop/projects/Hybrid-router-agent/frontend
npm run dev
```
**Expected output:**
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Step 4: Access the Application
- **Frontend UI:** http://localhost:5173
- **Backend API:** http://127.0.0.1:8000
- **API Docs:** http://127.0.0.1:8000/docs

---

## 🧪 Test the Router

### Quick Router Test
```bash
cd /Users/amanjha/Desktop/projects/Hybrid-router-agent
python -c "
from src.router import get_router

router = get_router()
queries = ['hi', 'Explain quantum mechanics']

for q in queries:
    d = router.predict_route(q)
    print(f'{q:30} → {d.backend:10} (score: {d.score:.3f})')
"
```

**Expected output:**
```
hi                             → local      (score: 0.071)
Explain quantum mechanics      → fireworks  (score: 0.260)
```

### Test in the UI
1. Open http://localhost:5173
2. Try these queries:
   - **Simple (should route to local):**
     - "hi"
     - "What is 2+2?"
     - "Hello"
   - **Complex (should route to cloud):**
     - "Explain quantum mechanics in detail"
     - "Write a comprehensive guide on machine learning"

3. Check the **Router Decision** box in the UI to see:
   - Backend chosen (local/fireworks)
   - Router score
   - Confidence level
   - Reasoning

---

## 📊 Monitor Router Performance

### View Training Data Stats
```bash
python -c "
import json
with open('dev/router_training_data.json') as f:
    data = json.load(f)
    print(f'Total examples: {len(data)}')
    local = sum(1 for d in data if d['preferred_model'] == 'local')
    cloud = sum(1 for d in data if d['preferred_model'] == 'cloud')
    print(f'Local: {local} ({local/len(data)*100:.1f}%)')
    print(f'Cloud: {cloud} ({cloud/len(data)*100:.1f}%)')
"
```

### Calibrate Router (after collecting conversations)
```bash
python dev/calibrate_router.py
```
This analyzes router performance and suggests threshold adjustments.

---

## 🔧 Common Issues & Solutions

### Issue: "Port already in use"
**Solution:**
```bash
# Kill all ports
lsof -ti:8000 -ti:5173 | xargs kill -9 2>/dev/null
```

### Issue: "ModuleNotFoundError: No module named 'sentence_transformers'"
**Solution:**
```bash
pip install sentence-transformers scikit-learn numpy
```

### Issue: "Router model not found"
**Solution:**
```bash
# Retrain router
python dev/train_router.py
```

### Issue: Backend crashes with "No module named 'src'"
**Solution:**
```bash
# Make sure you're in the project root
cd /Users/amanjha/Desktop/projects/Hybrid-router-agent
# Then start backend
uvicorn server:app --reload --port 8000
```

### Issue: Router routing everything to cloud
**Check current threshold:**
```bash
python -c "from src.router import get_router; r = get_router(); print(f'Threshold: {r.threshold}')"
```
**Should be:** `0.15` (positive threshold)

---

## 📈 Next Steps for Improvement

### 1. Collect Real Conversations (1-2 weeks)
- Use the application normally
- Conversations are stored in `gateway.db`
- Target: 50-100 conversations with diverse queries

### 2. Retrain Router
```bash
python dev/train_router.py
```
This will:
- Extract conversations from database
- Add new training examples
- Retrain the model
- Save updated weights

**Expected improvement:** Confidence from ~52% → 75%+

### 3. Run Calibration
```bash
python dev/calibrate_router.py
```
This analyzes:
- Routing accuracy
- Token savings
- Cost reduction
- Optimal threshold

### 4. Monitor Token Economics
Check the **Stats Panel** in the UI to see:
- Total tokens used (local + cloud)
- Projected cost
- Token distribution
- Routing decisions

---

## 🎯 Success Metrics

### Current Performance
- **Router trained:** 64 examples (25 local, 39 cloud)
- **Threshold:** +0.15 (optimized for positive score bias)
- **Status:** Routing simple queries to local, complex to cloud ✅

### Target Metrics (after production use)
- **Token reduction:** 85% (vs 40% with quality validator)
- **Quality:** 95% (maintain high answer quality)
- **Training data:** 100+ conversations
- **Confidence:** 75%+ (vs current 52%)

---

## 📁 Key Files

### Router Implementation
- `src/router.py` - RouteLLM router logic (700 lines)
- `dev/train_router.py` - Training pipeline
- `dev/calibrate_router.py` - Performance analysis
- `dev/router_training_data.json` - Training examples
- `models/router_model.pkl` - Trained model weights

### Backend
- `server.py` - FastAPI server (saves router metrics)
- `src/streaming.py` - SSE streaming with router integration
- `db/models.py` - Database schema (includes router fields)

### Frontend
- `frontend/src/hooks/useStreamingChat.js` - Chat hook with router state
- `frontend/src/components/DebugChat.jsx` - Router display UI

### Documentation
- `ARCHITECTURE.md` - System architecture (600+ lines)
- `QUICK_START_ROUTELLM.md` - RouteLLM quick start
- `ROUTELLM_MIGRATION.md` - Migration guide
- `PROJECT_SPEC.md` - Original project spec

---

## 🆘 Need Help?

### View Logs
**Backend logs:**
```bash
# Backend terminal shows uvicorn logs
# Look for routing decisions: "Routing to local/fireworks"
```

**Frontend logs:**
```bash
# Browser console (F12) shows:
# - SSE connection status
# - Router decisions
# - Streaming events
```

### Debug Router
```bash
# Check router weights
python -c "from src.router import get_router; r = get_router(); print(f'Weights shape: {r.weights.shape}'); print(f'Weights mean: {r.weights.mean():.4f}')"

# Test specific query
python -c "from src.router import get_router; r = get_router(); d = r.predict_route('YOUR_QUERY'); print(vars(d))"
```

### Database Check
```bash
# View conversations
sqlite3 gateway.db "SELECT id, prompt, response_model, router_score FROM conversation_messages ORDER BY created_at DESC LIMIT 10;"
```

---

## ✅ Ready to Go!

Your hybrid router agent is fully operational. Start the backend and frontend using the commands above, then test with simple and complex queries to see intelligent routing in action!
