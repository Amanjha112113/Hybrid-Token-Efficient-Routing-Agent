#!/bin/bash
# Start the Hybrid Router backend server

cd "$(dirname "$0")"

echo "🚀 Starting Hybrid Router Backend..."
echo "================================================"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "✓ Loaded .env file"
else
    echo "⚠️  No .env file found - using defaults"
fi

# Check if Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama is running - Local model available"
else
    echo "ℹ️  Ollama not running - Will use Fireworks API only"
    echo "   (This is OK - the app will work fine with cloud models)"
fi

# Start the server
echo ""
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo "================================================"
echo ""

uvicorn server:app --reload --port 8000
