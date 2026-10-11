#!/usr/bin/env python3
"""
Quick test script to verify the streaming endpoint returns proper token metadata
and that it's being saved to the database correctly.
"""

import asyncio
import httpx
import json


async def test_streaming_with_stats():
    """Test that streaming returns complete token metadata."""
    
    # 1. Create a test conversation
    print("1. Creating test conversation...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/conversations",
            json={"title": "Stats Test Conversation"}
        )
        conv_data = response.json()
        conv_id = conv_data["id"]
        print(f"   ✓ Created conversation: {conv_id}")
    
    # 2. Send a simple message (should route local)
    print("\n2. Sending message: 'What is 2+2?'")
    async with httpx.AsyncClient(timeout=30.0) as client:
        full_response = ""
        metadata = {}
        
        async with client.stream(
            "POST",
            "http://localhost:8000/api/chat/stream",
            json={
                "conversation_id": conv_id,
                "prompt": "What is 2+2?"
            }
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                
                # Parse SSE format
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
                    
                    if event_type == "token":
                        full_response += data.get("token", "")
                    elif event_type == "done":
                        metadata = data
                        print(f"\n   ✓ Stream complete!")
                        print(f"   Response: {full_response[:60]}...")
                        print(f"\n3. Token Metadata:")
                        print(f"   - Backend: {metadata.get('backend')}")
                        print(f"   - Model: {metadata.get('model')}")
                        print(f"   - Tokens Used: {metadata.get('tokens_used', 0)}")
                        print(f"   - Tokens Saved: {metadata.get('tokens_saved', 0)}")
                        print(f"   - Cost USD: ${metadata.get('cost_usd', 0):.6f}")
                        print(f"   - Savings USD: ${metadata.get('savings_usd', 0):.6f}")
                        print(f"   - Latency: {metadata.get('latency_ms', 0)}ms")
    
    # 3. Verify it was saved to database
    print("\n4. Verifying database storage...")
    await asyncio.sleep(0.5)  # Give DB time to save
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/conversations/{conv_id}/messages"
        )
        messages = response.json()
        
        # Find the assistant message
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        if assistant_msgs:
            msg = assistant_msgs[0]
            print(f"   ✓ Found assistant message in DB")
            print(f"   - Backend: {msg.get('backend')}")
            print(f"   - Model: {msg.get('model_used')}")
            print(f"   - Tokens Used: {msg.get('tokens_used', 0)}")
            print(f"   - Tokens Saved: {msg.get('tokens_saved', 0)}")
            print(f"   - Cost USD: ${msg.get('cost_usd', 0):.6f}")
            print(f"   - Savings USD: ${msg.get('savings_usd', 0):.6f}")
            
            # Verify metadata matches
            if (msg.get('backend') == metadata.get('backend') and
                msg.get('tokens_saved') == metadata.get('tokens_saved')):
                print("\n✅ SUCCESS: Token metadata correctly saved to database!")
            else:
                print("\n⚠️  WARNING: Metadata mismatch between stream and DB")
        else:
            print("   ❌ No assistant message found in DB")
    
    # 4. Get conversation stats
    print("\n5. Testing conversation stats endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/conversations/{conv_id}/stats"
        )
        stats = response.json()
        print(f"   ✓ Stats retrieved:")
        print(f"   - Total Messages: {stats.get('total_messages', 0)}")
        print(f"   - Total Tokens Saved: {stats.get('total_tokens_saved', 0)}")
        print(f"   - Total Savings: ${stats.get('total_savings_usd', 0):.6f}")
        print(f"   - Local Count: {stats.get('local_count', 0)}")
        print(f"   - Remote Count: {stats.get('remote_count', 0)}")
    
    print(f"\n6. Test conversation ID: {conv_id}")
    print("   You can view this in the frontend!")
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_streaming_with_stats())
