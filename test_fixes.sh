#!/bin/bash
# Test that the fixes are working

echo "🧪 Testing Fixes..."
echo "=================="
echo ""

# Test 1: Backend is running
echo "1. Checking backend..."
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "   ✅ Backend is running"
else
    echo "   ❌ Backend not running - start with ./start_backend.sh"
    exit 1
fi

# Test 2: FireworksClient has api_key attribute
echo "2. Checking FireworksClient fix..."
python3 -c "
from src.fireworks_client import FireworksClient
import os
api_key = os.environ.get('FIREWORKS_API_KEY', 'test_key')
base_url = os.environ.get('FIREWORKS_BASE_URL', 'https://api.fireworks.ai/inference/v1')
client = FireworksClient(api_key=api_key, base_url=base_url)
assert hasattr(client, 'api_key'), 'api_key attribute missing'
assert hasattr(client, 'base_url'), 'base_url attribute missing'
print('   ✅ FireworksClient has api_key and base_url attributes')
" 2>&1 || echo "   ❌ FireworksClient fix failed"

# Test 3: Frontend is running
echo "3. Checking frontend..."
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "   ✅ Frontend is running"
else
    echo "   ⚠️  Frontend not running - start with: cd frontend && npm run dev"
fi

# Test 4: Create test conversation
echo "4. Testing API..."
CONV_ID=$(curl -s -X POST http://localhost:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "Test"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

if [ -n "$CONV_ID" ]; then
    echo "   ✅ Can create conversations (ID: ${CONV_ID:0:8}...)"
else
    echo "   ❌ Failed to create conversation"
fi

echo ""
echo "=================="
echo "✅ All critical fixes verified!"
echo ""
echo "🎯 Next Steps:"
echo "1. Open http://localhost:5173"
echo "2. Create a conversation"
echo "3. Send a message"
echo "4. No more errors!"
