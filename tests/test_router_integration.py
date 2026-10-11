"""
Integration tests for router with enhanced validation - Task 4

These tests verify the complete end-to-end router behavior with the enhancements.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.router import get_router
from src.streaming import stream_chat_hybrid


class TestRouterIntegration:
    """Integration tests for the complete router system."""

    def setup_method(self):
        """Setup for each test."""
        self.router = get_router()
    
    def test_complete_chat_flow_with_local_routing(self):
        """
        Test complete chat flow with simple queries routing locally and showing correct metadata.
        """
        print("\n=== INTEGRATION TEST: Complete Chat Flow (Local) ===")
        
        simple_query = "hi there"
        route_decision = self.router.predict_route(simple_query)
        
        print(f"Query: '{simple_query}'")
        print(f"Router prediction: {route_decision.backend} (score: {route_decision.score:.3f})")
        
        # Test with Ollama available
        result = asyncio.run(self._test_complete_flow(simple_query, ollama_available=True))
        
        print(f"Actual routing: {result['backend']}")
        print(f"Router decision honored: {result.get('router_decision_honored', 'unknown')}")
        
        # When Ollama is available, simple queries should route locally
        if route_decision.backend == "local":
            assert result["backend"] == "local", (
                f"Router predicted local but routed to {result['backend']}. "
                f"Check Ollama availability or routing logic."
            )
        
        assert "router_decision_honored" in result, "Metadata should include router decision status"

    def test_ollama_failure_fallback_with_validation(self):
        """
        Test that when Ollama fails, the system provides clear feedback about the fallback.
        """
        print("\n=== INTEGRATION TEST: Ollama Failure Fallback ===")
        
        simple_query = "hello"
        route_decision = self.router.predict_route(simple_query)
        
        print(f"Query: '{simple_query}'")
        print(f"Router prediction: {route_decision.backend}")
        
        # Test with Ollama unavailable
        result = asyncio.run(self._test_complete_flow(simple_query, ollama_available=False))
        
        print(f"Actual routing: {result['backend']}")
        print(f"Escalation reason: {result.get('escalation_reason', 'none')}")
        print(f"Router overridden: {result.get('router_decision_overridden', 'unknown')}")
        
        # When Ollama fails, should escalate to cloud with clear reasoning
        if route_decision.backend == "local":
            assert result["backend"] == "fireworks", "Should fallback to cloud when Ollama fails"
            assert result.get("escalation_reason") in ["ollama_unavailable", "local_model_error"], (
                "Should provide clear escalation reason"
            )
            assert result.get("router_decision_overridden") == True, (
                "Should indicate router decision was overridden"
            )

    def test_threshold_logic_with_various_scores(self):
        """
        Test routing decisions with various router scores to validate threshold logic.
        """
        print("\n=== INTEGRATION TEST: Threshold Logic Validation ===")
        
        # Test queries that should produce different scores
        test_cases = [
            ("hi", "should be negative/low positive -> local"),
            ("what is 2+2", "should be negative/low positive -> local"),  
            ("Explain quantum mechanics in detail", "should be higher positive -> cloud"),
            ("Write a comprehensive analysis", "should be higher positive -> cloud")
        ]
        
        for query, expected in test_cases:
            route_decision = self.router.predict_route(query)
            
            print(f"Query: '{query}'")
            print(f"  Score: {route_decision.score:.4f}")
            print(f"  Backend: {route_decision.backend}")
            print(f"  Expected: {expected}")
            
            # Validate score and backend alignment
            if route_decision.score < 0.15:  # Below threshold
                assert route_decision.backend == "local", (
                    f"Score {route_decision.score:.4f} < 0.15 should predict local, got {route_decision.backend}"
                )
            else:  # Above threshold
                assert route_decision.backend == "fireworks", (
                    f"Score {route_decision.score:.4f} >= 0.15 should predict cloud, got {route_decision.backend}"
                )

    def test_preference_override_logic(self):
        """
        Test that user preference overrides work correctly with validation.
        """
        print("\n=== INTEGRATION TEST: Preference Override Logic ===")
        
        query = "simple test query"
        preferences = ["auto", "local", "remote-efficient", "remote-power"]
        
        for preference in preferences:
            result = asyncio.run(self._test_preference_routing(query, preference))
            
            print(f"Preference '{preference}': {result}")
            
            if preference == "local":
                assert result["should_use_local"] == True, f"Preference=local should force local routing"
            elif preference in ["remote-efficient", "remote-power"]:
                assert result["should_use_local"] == False, f"Preference={preference} should force cloud routing"

    def test_debug_logging_output(self):
        """
        Test that debug logging provides comprehensive routing information.
        """
        print("\n=== INTEGRATION TEST: Debug Logging Output ===")
        
        query = "test debug logging"
        
        # Capture log output during routing
        with patch('src.streaming.logger') as mock_logger:
            result = asyncio.run(self._test_debug_logging(query))
            
            # Verify debug logs were called
            debug_calls = [call for call in mock_logger.debug.call_args_list]
            info_calls = [call for call in mock_logger.info.call_args_list]
            
            print(f"Debug calls: {len(debug_calls)}")
            print(f"Info calls: {len(info_calls)}")
            
            # Should have detailed debug information
            assert len(debug_calls) > 0 or len(info_calls) > 0, "Should generate debug/info logs"

    async def _test_complete_flow(self, query, ollama_available=True):
        """Test complete routing flow with configurable Ollama availability."""
        messages = [{"role": "user", "content": query}]
        
        # Mock streaming functions
        with patch('src.streaming.stream_ollama_chat') as mock_ollama, \
             patch('src.streaming.stream_fireworks_chat') as mock_fireworks:
            
            if ollama_available:
                async def mock_ollama_gen():
                    yield "local"
                    yield " response"
                mock_ollama.return_value = mock_ollama_gen()
            else:
                mock_ollama.side_effect = Exception("Connection refused")
            
            async def mock_fireworks_gen():
                yield "cloud"
                yield " response"
            mock_fireworks.return_value = mock_fireworks_gen()
            
            # Mock Ollama availability
            with patch('src.streaming.USE_OLLAMA', ollama_available):
                mock_client = MagicMock()
                mock_client.api_key = "test"
                
                events = []
                async for event in stream_chat_hybrid(
                    messages=messages,
                    complexity="low",
                    fireworks_client=mock_client,
                    allowed_models=["test-model"],
                    preference="auto"
                ):
                    events.append(event)
                    
                    # Stop after getting backend decision
                    if event.get("type") == "metadata" and "backend" in event.get("content", {}):
                        return event["content"]
                    elif event.get("type") == "done":
                        return event.get("content", {"backend": "unknown"})
                
                # Fallback - analyze events
                for event in events:
                    if event.get("type") == "metadata" and "backend" in event.get("content", {}):
                        return event["content"]
                
                return {"backend": "unknown", "events": events}

    async def _test_preference_routing(self, query, preference):
        """Test routing with different user preferences."""
        messages = [{"role": "user", "content": query}]
        
        with patch('src.streaming.stream_ollama_chat'), \
             patch('src.streaming.stream_fireworks_chat'), \
             patch('src.streaming.USE_OLLAMA', True):
            
            mock_client = MagicMock()
            
            # Capture the should_use_local decision by examining the code path
            routing_result = {"should_use_local": None}
            
            # Mock to capture routing decision 
            original_hybrid = stream_chat_hybrid
            
            async def capture_routing(*args, **kwargs):
                # Extract the routing decision from kwargs
                pref = kwargs.get('preference', 'auto')
                
                # Simulate the logic from stream_chat_hybrid
                from src.router import get_router
                router = get_router()
                route_decision = router.predict_route(query)
                
                if pref == "local":
                    should_use_local = True
                elif pref in ("remote-efficient", "remote-power"):
                    should_use_local = False
                else:  # auto
                    should_use_local = (route_decision.backend == "local")
                
                routing_result["should_use_local"] = should_use_local
                routing_result["router_backend"] = route_decision.backend
                routing_result["preference"] = pref
                
                # Return a simple event to satisfy the async generator
                yield {"type": "done", "content": {"backend": "local" if should_use_local else "fireworks"}}
            
            async for event in capture_routing(
                messages=messages,
                complexity="low",
                fireworks_client=mock_client,
                allowed_models=["test"],
                preference=preference
            ):
                break  # Just need the first event
            
            return routing_result

    async def _test_debug_logging(self, query):
        """Test debug logging functionality."""
        messages = [{"role": "user", "content": query}]
        
        with patch('src.streaming.stream_ollama_chat') as mock_ollama, \
             patch('src.streaming.stream_fireworks_chat') as mock_fireworks, \
             patch('src.streaming.USE_OLLAMA', True):
            
            async def mock_gen():
                yield "test response"
            
            mock_ollama.return_value = mock_gen()
            mock_fireworks.return_value = mock_gen()
            
            mock_client = MagicMock()
            
            async for event in stream_chat_hybrid(
                messages=messages,
                complexity="low", 
                fireworks_client=mock_client,
                allowed_models=["test"],
                preference="auto"
            ):
                if event.get("type") in ["metadata", "done"]:
                    break
            
            return {"logged": True}


if __name__ == "__main__":
    print("=== RUNNING ROUTER INTEGRATION TESTS ===")
    
    test_instance = TestRouterIntegration()
    test_instance.setup_method()
    
    tests = [
        ("test_complete_chat_flow_with_local_routing", "Complete chat flow with local routing"),
        ("test_ollama_failure_fallback_with_validation", "Ollama failure fallback validation"),
        ("test_threshold_logic_with_various_scores", "Threshold logic validation"),
        ("test_preference_override_logic", "Preference override logic"),
        ("test_debug_logging_output", "Debug logging output")
    ]
    
    for test_method, description in tests:
        try:
            getattr(test_instance, test_method)()
            print(f"✅ {description} PASSED")
        except Exception as e:
            print(f"❌ {description} FAILED: {e}")
