"""
Test for router preservation properties - Task 2

IMPORTANT: These tests should PASS on unfixed code to establish baseline behavior.
This ensures we don't break complex query routing when fixing the bug.
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


class TestRouterPreservation:
    """Test suite to ensure complex queries continue routing to cloud."""

    def setup_method(self):
        """Setup for each test."""
        self.router = get_router()
    
    def test_complex_analytical_queries_route_to_cloud(self):
        """
        Test that complex analytical queries continue routing to cloud models.
        
        EXPECTED TO PASS: Complex queries should route to Fireworks.
        """
        complex_queries = [
            "Explain the quantum mechanical principles behind superconductivity and their applications in modern technology",
            "Analyze the economic implications of artificial intelligence on labor markets over the next 20 years", 
            "Write a detailed comparative analysis of different machine learning architectures for natural language processing",
            "Develop a comprehensive business strategy for a startup entering the renewable energy market",
            "Explain the philosophical implications of consciousness in artificial intelligence systems"
        ]
        
        print("\n=== PRESERVATION TEST: Complex Analytical Queries ===")
        
        cloud_routed = 0
        local_routed = 0
        
        for query in complex_queries:
            route_decision = self.router.predict_route(query)
            
            print(f"Query: {query[:50]}...")
            print(f"  Router prediction: {route_decision.backend} (score: {route_decision.score:.3f})")
            
            if route_decision.backend == "fireworks":
                cloud_routed += 1
            else:
                local_routed += 1
        
        print(f"\nResults: {cloud_routed} cloud, {local_routed} local out of {len(complex_queries)} complex queries")
        
        # Most complex queries should route to cloud
        # Allow some flexibility but expect majority to be cloud-routed
        cloud_percentage = cloud_routed / len(complex_queries)
        assert cloud_percentage >= 0.6, (
            f"Expected at least 60% of complex queries to route to cloud, "
            f"but only {cloud_percentage:.1%} did. This may indicate router is too conservative."
        )

    def test_long_context_queries_route_appropriately(self):
        """
        Test that queries with long context route appropriately.
        
        Long queries often need more capable models.
        """
        long_queries = [
            "Given the following scenario: " + "A" * 500 + " Please analyze this situation and provide recommendations.",
            "I need help with a complex problem involving multiple variables: " + "B" * 300 + " What should I do?",
            "Here's a detailed description of my issue: " + "C" * 400 + " Please provide a comprehensive solution."
        ]
        
        print("\n=== PRESERVATION TEST: Long Context Queries ===")
        
        for query in long_queries:
            route_decision = self.router.predict_route(query)
            
            print(f"Query length: {len(query)} chars")
            print(f"  Router prediction: {route_decision.backend} (score: {route_decision.score:.3f})")
            print(f"  Complexity: {route_decision.complexity}")
            
            # Long queries should generally route to cloud, but this is more flexible
            # We're mainly documenting the behavior for preservation
            assert route_decision.backend in ["local", "fireworks"], f"Invalid backend: {route_decision.backend}"

    def test_technical_programming_queries(self):
        """
        Test that technical programming queries route consistently.
        
        These may go either way depending on complexity.
        """
        programming_queries = [
            "Write a complex Python decorator that handles async functions with retry logic and exponential backoff",
            "Explain the difference between microservices and monolithic architecture with pros and cons",
            "Design a distributed system architecture for handling 1 million concurrent users",
            "Implement a machine learning model for natural language processing with transformer architecture"
        ]
        
        print("\n=== PRESERVATION TEST: Technical Programming Queries ===")
        
        for query in programming_queries:
            route_decision = self.router.predict_route(query)
            
            print(f"Query: {query[:60]}...")
            print(f"  Router prediction: {route_decision.backend} (score: {route_decision.score:.3f})")
            print(f"  Reasoning: {route_decision.reason}")
            
            # Programming queries can go either way - we're documenting behavior
            assert route_decision.backend in ["local", "fireworks"], f"Invalid backend: {route_decision.backend}"
            assert route_decision.confidence >= 0.0, f"Invalid confidence: {route_decision.confidence}"

    def test_user_preference_overrides_work(self):
        """
        Test that user preference overrides continue working correctly.
        
        When user forces remote-efficient or remote-power, should go to cloud.
        """
        test_query = "what is 2+2"  # Simple query that would normally go local
        
        print("\n=== PRESERVATION TEST: User Preference Overrides ===")
        
        # Test with different preferences
        preferences = ["auto", "local", "remote-efficient", "remote-power"]
        
        for preference in preferences:
            result = asyncio.run(self._test_preference_override(test_query, preference))
            
            print(f"Preference '{preference}': routed to {result['backend']}")
            
            if preference == "local":
                assert result["backend"] == "local", f"Expected local routing with preference=local"
            elif preference in ["remote-efficient", "remote-power"]:
                assert result["backend"] == "fireworks", f"Expected cloud routing with preference={preference}"
            # auto can go either way based on router decision

    async def _test_preference_override(self, query, preference):
        """Test preference override behavior."""
        messages = [{"role": "user", "content": query}]
        
        with patch('src.streaming.stream_ollama_chat') as mock_ollama, \
             patch('src.streaming.stream_fireworks_chat') as mock_fireworks:
            
            async def mock_ollama_gen():
                yield "local response"
            
            async def mock_fireworks_gen():
                yield "cloud response"
            
            mock_ollama.return_value = mock_ollama_gen()
            mock_fireworks.return_value = mock_fireworks_gen()
            
            with patch('src.streaming.USE_OLLAMA', True):
                mock_client = MagicMock()
                mock_client.api_key = "test"
                
                async for event in stream_chat_hybrid(
                    messages=messages,
                    complexity="low",
                    fireworks_client=mock_client,
                    allowed_models=["test-model"],
                    preference=preference
                ):
                    if event.get("type") == "metadata" and "backend" in event.get("content", {}):
                        return {"backend": event["content"]["backend"]}
                
                return {"backend": "unknown"}


if __name__ == "__main__":
    print("=== RUNNING ROUTER PRESERVATION TESTS ===")
    print("These tests should PASS to establish baseline behavior to preserve.\n")
    
    test_instance = TestRouterPreservation()
    test_instance.setup_method()
    
    try:
        test_instance.test_complex_analytical_queries_route_to_cloud()
        print("✅ Complex analytical queries test PASSED")
    except Exception as e:
        print(f"❌ Complex analytical queries test FAILED: {e}")
    
    try:
        test_instance.test_long_context_queries_route_appropriately()
        print("✅ Long context queries test PASSED")
    except Exception as e:
        print(f"❌ Long context queries test FAILED: {e}")
        
    try:
        test_instance.test_technical_programming_queries()
        print("✅ Technical programming queries test PASSED")
    except Exception as e:
        print(f"❌ Technical programming queries test FAILED: {e}")
        
    try:
        test_instance.test_user_preference_overrides_work()
        print("✅ User preference overrides test PASSED")
    except Exception as e:
        print(f"❌ User preference overrides test FAILED: {e}")
