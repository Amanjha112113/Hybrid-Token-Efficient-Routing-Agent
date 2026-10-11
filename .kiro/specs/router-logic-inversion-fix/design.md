# Router Logic Inversion Bugfix Design

## Overview

This document outlines the fix for a critical router logic inversion bug where the system correctly predicts that a local model can handle simple queries but then routes them to expensive cloud models instead. The bug manifests as a complete disconnect between the router's reasoning logic and its actual routing decision, causing 100% cloud usage instead of the expected 85% local routing for simple queries. The fix focuses on ensuring the RouteDecision.backend field is properly honored throughout the routing pipeline and validating threshold logic to prevent future inversions.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when router predicts local routing but system routes to cloud instead
- **Property (P)**: The desired behavior when router predicts local routing - system should honor the decision and route locally
- **Preservation**: Existing cloud routing behavior for complex queries that must remain unchanged by the fix
- **RouteDecision**: The data structure returned by router.predict_route() containing backend, score, confidence, and reasoning
- **stream_chat_hybrid**: The main routing function in streaming.py that processes RouteDecision and routes requests
- **threshold**: The routing score threshold (0.0) where negative scores favor local, positive scores favor cloud

## Bug Details

### Bug Condition

The bug manifests when the router correctly analyzes simple queries and predicts local routing, but the streaming pipeline routes to cloud models instead. The router displays accurate reasoning like "Local model can handle this (low complexity)" with "Marginal preference for local" but the system ignores this assessment.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type UserPrompt
  OUTPUT: boolean
  
  router_decision := router.predict_route(input.prompt)
  actual_backend := determine_actual_routing(input, router_decision)
  
  RETURN router_decision.backend == "local"
         AND actual_backend == "fireworks"
         AND router_decision.confidence > 0.0
END FUNCTION
```

### Examples

- **Simple greeting**: Query "hi" gets router prediction "Local model can handle this (low complexity)" with backend="local", but system routes to Fireworks Ember-1 cloud model
- **Low complexity factual**: Query "what is 2+2" gets router score -0.8 (negative = local preferred) but routes to expensive cloud API
- **Short queries**: Any query under 100 characters with simple keywords should route local per heuristic logic but routes to cloud
- **Marginal local preference**: Router displays "Marginal preference for local" but system overrides with cloud routing

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Complex queries requiring advanced reasoning must continue routing to cloud models
- High-complexity queries with router score > 0.0 must continue routing to Fireworks
- Fallback logic when router fails must continue working as designed
- User preference overrides (preference="remote-power") must continue forcing cloud routing

**Scope:**
All inputs where the router correctly predicts cloud routing (route_decision.backend == "fireworks") should be completely unaffected by this fix. This includes:
- Complex analytical queries that benefit from powerful cloud models
- Long prompts requiring extended context handling
- Queries with explicit reasoning or analysis keywords
- Cases where user has set preference to remote-efficient or remote-power

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **Router Decision Ignored**: The streaming.py may not be properly reading route_decision.backend field
   - Code shows: `should_use_local = (route_decision.backend == "local")` which appears correct
   - But actual routing behavior suggests this decision is being overridden somewhere

2. **Threshold Logic Inversion**: The router threshold comparison may have inverted logic
   - Current logic: `backend = "local" if score < self.threshold else "fireworks"`
   - With DEFAULT_THRESHOLD = 0.0, this should work correctly
   - But there may be a sign inversion in score calculation or threshold comparison

3. **Fallback Override**: The fallback heuristic routing may be overriding router decisions
   - When router model is not trained (is_trained=False), system uses fallback
   - Fallback logic may have different threshold behavior than trained router

4. **Preference Override Bug**: User preference logic may be incorrectly overriding router decisions
   - Code shows preference checks after router decision
   - Default preference="auto" should respect router decisions but may not be working

## Correctness Properties

Property 1: Bug Condition - Router Decision Honored

_For any_ input where the router predicts local routing (route_decision.backend == "local") and has confidence > 0.25, the fixed streaming system SHALL route the request to the local model, producing the expected cost savings and using local inference capabilities.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Complex Query Cloud Routing

_For any_ input where the router predicts cloud routing (route_decision.backend == "fireworks") or complexity is high, the fixed system SHALL produce exactly the same routing behavior as the original system, preserving cloud routing for queries that benefit from advanced model capabilities.

**Validates: Requirements 3.1, 3.2, 3.3**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/streaming.py`

**Function**: `stream_chat_hybrid`

**Specific Changes**:
1. **Add Router Decision Validation**: Add debug logging to verify route_decision.backend value is being read correctly
   - Log: `f"Router decision: {route_decision.backend} (score={route_decision.score})"`
   - Verify the decision object is populated correctly before routing logic

2. **Fix Threshold Logic**: Examine and correct any threshold comparison inversion
   - Verify: `should_use_local = (route_decision.backend == "local")` logic is correct
   - Add validation that router score interpretation matches streaming interpretation

3. **Add Decision Tracing**: Add comprehensive logging throughout routing decision pipeline
   - Log router prediction, preference override checks, final routing decision
   - Help identify where the disconnect between prediction and execution occurs

4. **Strengthen Router Decision Precedence**: Ensure router decisions take precedence over fallback logic
   - Move router decision logic to higher priority than preference overrides
   - Only allow user preference to override when explicitly set to force modes

5. **Add Validation Checks**: Implement runtime validation to catch future inversions
   - Assert that local predictions route locally and cloud predictions route to cloud
   - Add metrics to track routing decision accuracy vs router predictions

**File**: `src/router.py`

**Function**: `predict_route` and `_fallback_heuristic_route`

**Specific Changes**:
1. **Verify Threshold Logic**: Confirm threshold comparison direction is correct
   - Current: `"local" if score < self.threshold else "fireworks"`
   - Verify negative scores correctly indicate local preference

2. **Strengthen Fallback Consistency**: Ensure fallback routing uses same threshold logic as trained router
   - Both should use same decision boundary at score = 0.0
   - Both should interpret negative scores as local preference

3. **Add Score Validation**: Add bounds checking and validation for routing scores
   - Ensure score calculation produces sensible values (-5.0 to +5.0 range)
   - Add warnings for extreme scores that might indicate calculation errors

4. **Enhanced Decision Reasoning**: Improve reasoning text to make routing logic more transparent
   - Include actual score values in reason text
   - Make it clear why a particular backend was chosen

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate simple queries with known router predictions and assert that the actual routing matches the prediction. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Simple Greeting Test**: Send "hi" and verify router predicts local but system routes to cloud (will fail on unfixed code)
2. **Short Query Test**: Send "what is 2+2" and verify router score < 0 but routes to cloud (will fail on unfixed code)
3. **Heuristic Logic Test**: Send query that should score negative per heuristic but routes to cloud (will fail on unfixed code)
4. **Decision Tracing Test**: Log the complete decision pipeline to identify where inversion occurs (will reveal bug location)

**Expected Counterexamples**:
- Router correctly predicts local (backend="local") but stream_chat_hybrid routes to Fireworks
- Possible causes: decision field not read correctly, threshold logic inverted, preference override bug

### Fix Checking

**Goal**: Verify that for all inputs where the router predicts local routing, the fixed system produces the expected local routing behavior.

**Pseudocode:**
```
FOR ALL input WHERE router_predicts_local(input) DO
  result := stream_chat_hybrid_fixed(input)
  ASSERT result.backend == "local"
  ASSERT result.cost_usd == 0.0
  ASSERT result.tokens_saved > 0
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the router predicts cloud routing, the fixed system produces the same result as the original system.

**Pseudocode:**
```
FOR ALL input WHERE router_predicts_cloud(input) DO
  ASSERT stream_chat_hybrid_original(input).backend = stream_chat_hybrid_fixed(input).backend
  ASSERT routing_behavior_unchanged(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all cloud-routed inputs

**Test Plan**: Observe behavior on UNFIXED code first for complex queries, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Complex Query Preservation**: Verify queries with reasoning keywords continue routing to cloud
2. **High Complexity Preservation**: Verify long prompts continue routing to cloud models
3. **User Preference Preservation**: Verify explicit remote preferences continue working
4. **Fallback Preservation**: Verify fallback routing behavior continues working when router fails

### Unit Tests

- Test router decision object creation and field population
- Test threshold comparison logic with various score values (-2.0, -0.1, 0.0, 0.1, 2.0)
- Test preference override logic with all preference values
- Test fallback heuristic routing with simple and complex queries

### Property-Based Tests

- Generate random simple queries and verify they route locally when router predicts local
- Generate random complex queries and verify cloud routing preservation
- Generate random router scores and verify threshold logic consistency
- Test routing decisions across many conversation contexts and user preferences

### Integration Tests

- Test complete chat flow with simple queries routing locally
- Test cost savings accumulation with corrected local routing
- Test frontend display of router reasoning matches actual routing
- Test that debug logging reveals correct decision pipeline flow