"""
Test for router logic inversion bug - Task 1

CRITICAL: This test MUST FAIL on unfixed code to confirm the bug exists.
DO NOT attempt to fix the test or the code when it fails.

Bug Condition: Router predicts local routing but system routes to cloud instead.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.router import get_router, RouteDecision
from src.streaming import stream_chat_hybrid


class TestRouterBugCondition:
    """Test suite to expose the router logic inversion bug."""

    def setup_method(self):
        """Setup for each test."""
        self.router = get_router()
    
    def test_simple_greeting_bug_condition(self):
        """
        Test that demonstrates the bug with simple greeting "hi".
        
        EXPECTED TO FAIL on unfixed code:
        - Router should predict local (backend="local")  
        - But stream_chat_hybrid should route to cloud (actual bug)
        """
        # Test router prediction
        route_decision = self.router.predict_route("hi")
        
        print(f"\n=== BUG CONDITION TEST: 'hi' ===")
        print(f"Router prediction: {route_decision.backend}")
        print(f"Router score: {route_decision.score}")
        print(f"Router confidence: {route_decision.confidence}")
        print(f"Router reasoning: {route_decision.reason}")
        
        # Router should predict local for simple greeting
        assert route_decision.backend == "local", f"Expected router to predict 'local' but got '{route_decision.backend}'"
        assert route_decision.confidence > 0.25, f"Expected confidence > 0.25 but got {route_decision.confidence}"
        
        # Now test actual routing behavior through streaming function
        result = asyncio.run(self._test_actual_routing("hi", route_decision))
        
        print(f"Actual routing result: {result}")
        
        # BUG CONDITION: Router predicts local but system routes to cloud
        # This assertion SHOULD FAIL on unfixed code
        assert result["backend"] == "local", (
            f"BUG CONFIRMED: Router predicted '{route_decision.backend}' but system routed to '{result['backend']}'. "
            f"This is the router logic inversion bug we need to fix."
        )

    def test_simple_math_bug_condition(self):
        """
        Test that demonstrates the bug with simple math "what is 2+2".
        
        EXPECTED TO FAIL on unfixed code:
        - Router should predict local for simple math
        - But system should route to cloud (actual bug)
        """
        query = "what is 2+2"
        route_decision = self.router.predict_route(query)
        
        print(f"\n=== BUG CONDITION TEST: '{query}' ===")
        print(f"Router prediction: {route_decision.backend}")
        print(f"Router score: {route_decision.score}")
        print(f"Router reasoning: {route_decision.reason}")
        
        # Router should predict local for simple math
        assert route_decision.backend == "local", f"Expected router to predict 'local' but got '{route_decision.backend}'"
        
        # Test actual routing behavior 
        result = asyncio.run(self._test_actual_routing(query, route_decision))
        
        # BUG CONDITION: This should fail demonstrating the inversion
        assert result["backend"] == "local", (
            f"BUG CONFIRMED: Router predicted '{route_decision.backend}' but system routed to '{result['backend']}'."
        )

    def test_multiple_simple_queries_bug_condition(self):
        """
        Test multiple simple queries that should all route locally but don't.
        
        This provides comprehensive evidence of the bug across various inputs.
        """
        simple_queries = [
            "hi", 
            "hello",
            "what is 2+2",
            "yes",
            "no", 
            "thanks",
            "ok"
        ]
        
        bug_cases = []
        
        for query in simple_queries:
            route_decision = self.router.predict_route(query)
            
            if route_decision.backend == "local" and route_decision.confidence > 0.25:
                result = asyncio.run(self._test_actual_routing(query, route_decision))
                
                if result["backend"] != "local":
                    bug_cases.append({
                        "query": query,
                        "router_prediction": route_decision.backend,
                        "actual_routing": result["backend"],
                        "score": route_decision.score,
                        "confidence": route_decision.confidence
                    })
        
        print(f"\n=== BUG CONDITION SUMMARY ===")
        print(f"Found {len(bug_cases)} cases where router predicted local but system routed to cloud:")
        
        for case in bug_cases:
            print(f"  '{case['query']}': predicted {case['router_prediction']} → actual {case['actual_routing']} (score: {case['score']:.3f})")
        
        # This should fail if bug exists - we expect to find inversion cases
        assert len(bug_cases) == 0, (
            f"BUG CONFIRMED: Found {len(bug_cases)} queries where router predicted local routing "
            f"but system routed to cloud instead. This demonstrates the router logic inversion bug."
        )

    async def _test_actual_routing(self, prompt, route_decision):
        """
        Test actual routing behavior by calling stream_chat_hybrid and capturing events.
        
        This reveals what the streaming function actually does vs what router predicted.
        """
        messages = [{"role": "user", "content": prompt}]
        
        # Mock the actual streaming functions to avoid network calls
        with patch('src.streaming.stream_ollama_chat') as mock_ollama, \
             patch('src.streaming.stream_fireworks_chat') as mock_fireworks:
            
            # Configure mocks to return simple responses
            async def mock_ollama_generator():
                yield "local"
                yield " response"
            
            async def mock_fireworks_generator():
                yield "fireworks"  
                yield " response"
            
            mock_ollama.return_value = mock_ollama_generator()
            mock_fireworks.return_value = mock_fireworks_generator()
            
            # Mock USE_OLLAMA to be True so local is available
            with patch('src.streaming.USE_OLLAMA', True):
                # Mock fireworks client
                mock_fireworks_client = MagicMock()
                mock_fireworks_client.api_key = "test-key"
                mock_fireworks_client.base_url = "https://api.fireworks.ai/inference/v1"
                allowed_models = ["accounts/fireworks/models/ember-1"]
                
                # Call the actual streaming function
                events = []
                async for event in stream_chat_hybrid(
                    messages=messages,
                    complexity="low", 
                    fireworks_client=mock_fireworks_client,
                    allowed_models=allowed_models,
                    preference="auto"  # This should respect router decisions
                ):
                    events.append(event)
                    
                    # Stop after we get the initial metadata to see routing decision
                    if event.get("type") == "metadata" and "backend" in event.get("content", {}):
                        backend = event["content"]["backend"]
                        return {"backend": backend, "events": events}
                    
                    # Also check for router event
                    if event.get("type") == "router":
                        router_backend = event["content"]["backend"]
                        continue
                
                # If we got here, check the accumulated events
                for event in events:
                    if event.get("type") == "metadata" and "backend" in event.get("content", {}):
                        return {"backend": event["content"]["backend"], "events": events}
                
                # Fallback - try to determine from events
                return {"backend": "unknown", "events": events}


if __name__ == "__main__":
    # Run the tests to demonstrate the bug
    print("=== RUNNING BUG CONDITION EXPLORATION TESTS ===")
    print("These tests are EXPECTED TO FAIL on unfixed code to demonstrate the bug exists.\n")
    
    test_instance = TestRouterBugCondition()
    test_instance.setup_method()
    
    try:
        test_instance.test_simple_greeting_bug_condition()
        print("✅ Simple greeting test PASSED (unexpected - bug may not exist)")
    except AssertionError as e:
        print(f"❌ Simple greeting test FAILED (expected - confirms bug exists): {e}")
    except Exception as e:
        print(f"⚠️  Simple greeting test ERROR: {e}")
    
    try:
        test_instance.test_simple_math_bug_condition()  
        print("✅ Simple math test PASSED (unexpected - bug may not exist)")
    except AssertionError as e:
        print(f"❌ Simple math test FAILED (expected - confirms bug exists): {e}")
    except Exception as e:
        print(f"⚠️  Simple math test ERROR: {e}")
        
    try:
        test_instance.test_multiple_simple_queries_bug_condition()
        print("✅ Multiple queries test PASSED (unexpected - bug may not exist)")  
    except AssertionError as e:
        print(f"❌ Multiple queries test FAILED (expected - confirms bug exists): {e}")
    except Exception as e:
        print(f"⚠️  Multiple queries test ERROR: {e}")
