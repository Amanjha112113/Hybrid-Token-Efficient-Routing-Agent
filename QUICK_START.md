# 🚀 Quick Start Guide

## Starting the Application

### Option 1: Using Scripts (Easiest)

```bash
# Terminal 1 - Backend
./start_backend.sh

# Terminal 2 - Frontend
cd frontend && npm run dev
```

### Option 2: Manual Start

```bash
# Terminal 1 - Backend
env $(grep -v '^#' .env | xargs) uvicorn server:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend && npm run dev
```

## Access the Application

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## ✅ Verify Everything Works

1. Open http://localhost:5173
2. Click "+ New Conversation"
3. Send a simple message: "What is 2+2?"
4. You should see:
   - Message streams token-by-token
   - Local model badge (💻 Local)
   - Stats panel on the right
   - Quality score
   - Token savings

## 🎯 Demo Mode (For Presentations)

1. In the input area, toggle **Comparison Mode ON** (⚖️)
2. Send a question
3. Watch BOTH local and cloud models generate side-by-side
4. Perfect for showing your teacher/recruiter!

## Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# If yes, kill it
kill -9 $(lsof -t -i:8000)

# Then restart
./start_backend.sh
```

### Frontend shows black screen
```bash
# Clear cache and rebuild
cd frontend
rm -rf node_modules dist
npm install
npm run dev
```

### Ollama not detected
- Local model routing will automatically fall back to cloud
- This is normal if Ollama isn't installed
- Install from: https://ollama.ai

## Environment Variables

Create `.env` file with:
```env
FIREWORKS_API_KEY=your_key_here
FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1
ALLOWED_MODELS=accounts/fireworks/models/llama-v3p1-8b-instruct
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
USE_OLLAMA=true
```

## Next Steps

1. **Normal Usage**: Send messages, watch automatic routing
2. **Demo Mode**: Enable comparison to prove quality
3. **View Stats**: Check the right panel for token economics
4. **Present**: Show your teacher the quality validation!

---

**Need Help?** Check `TESTING_GUIDE.md` for detailed testing scenarios.
