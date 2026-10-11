# Implementation Plan

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Router Decision Honored
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test that when router predicts local routing (route_decision.backend == "local") with confidence > 0.25, the system routes to local model
  - Create test file `tests/test_router_bug_condition.py`
  - Test simple queries like "hi", "what is 2+2", and other low-complexity inputs
  - Verify router correctly predicts local but stream_chat_hybrid routes to cloud
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found to understand root cause
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.1, 2.2_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Complex Query Cloud Routing
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for complex queries (router predicts cloud routing)
  - Create test file `tests/test_router_preservation.py`
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Test complex analytical queries, long prompts, and queries with explicit reasoning keywords
  - Verify these continue routing to cloud models as designed
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 3. Fix for router logic inversion bug

  - [ ] 3.1 Add comprehensive debugging and logging to identify failure point
    - Add detailed logging to `src/streaming.py` in `stream_chat_hybrid` function
    - Log router decision details: `f"Router decision: {route_decision.backend} (score={route_decision.score}, confidence={route_decision.confidence})"`
    - Log should_use_local determination: `f"Should use local: {should_use_local} (preference={preference})"`
    - Log actual routing path taken: `f"Routing to: {'local' if using local path else 'fireworks'}"`
    - Add logging to router decision override logic for user preferences
    - Add validation assertions to catch routing inconsistencies at runtime
    - _Bug_Condition: isBugCondition(input) where router_decision.backend == "local" AND actual_backend == "fireworks"_
    - _Expected_Behavior: Debug logs reveal where disconnect occurs between router prediction and actual routing_
    - _Preservation: Logging should not affect routing behavior for complex queries_
    - _Requirements: 2.1, 2.2_

  - [ ] 3.2 Fix the core router decision logic inversion
    - Analyze debug logs from 3.1 to identify exact failure point
    - Fix routing logic in `src/streaming.py` where router decision is not properly honored
    - Ensure `should_use_local = (route_decision.backend == "local")` logic is working correctly
    - Verify router decision takes precedence over fallback logic when router is available
    - Add validation that router.backend field is populated correctly in `src/router.py`
    - Fix any threshold comparison inversions in router score calculation
    - Strengthen router decision precedence over preference overrides (only override when explicitly forced)
    - _Bug_Condition: isBugCondition(input) from design_
    - _Expected_Behavior: expectedBehavior(result) where local predictions route locally_
    - _Preservation: Cloud routing for complex queries remains unchanged_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_

  - [ ] 3.3 Add runtime validation checks to prevent regression
    - Add validation assertions in `stream_chat_hybrid` to catch future inversions
    - Assert that when route_decision.backend == "local", routing actually goes to local path
    - Assert that when route_decision.backend == "fireworks", routing goes to cloud path
    - Add metrics tracking to monitor routing decision accuracy vs router predictions
    - Implement warning logs for routing decisions that contradict router predictions
    - Add configuration option to enable strict validation mode for debugging
    - _Bug_Condition: Detection of routing inversions at runtime_
    - _Expected_Behavior: System prevents and reports routing inconsistencies_
    - _Preservation: Validation checks do not interfere with normal operation_
    - _Requirements: 2.1, 2.2_

  - [ ] 3.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Router Decision Honored
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify simple queries like "hi" and "what is 2+2" now route locally as router predicts
    - Document that counterexamples from task 1 now work correctly
    - _Requirements: Expected Behavior Properties from design_

  - [ ] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Complex Query Cloud Routing
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)
    - Verify complex queries, long prompts, and analytical queries still route to cloud
    - Verify user preference overrides still work correctly

- [ ] 4. Add comprehensive validation test suite
  - Create `tests/test_router_integration.py` for end-to-end validation
  - Test complete chat flow with simple queries routing locally and showing cost savings
  - Test that router reasoning displayed in frontend matches actual routing behavior
  - Test threshold logic with various score values (-2.0, -0.1, 0.0, 0.1, 2.0)
  - Test preference override logic with all preference values ("auto", "local", "remote-efficient", "remote-power")
  - Test fallback heuristic routing when router is unavailable
  - Verify debug logging output matches expected decision pipeline flow
  - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Run complete test suite: `python -m pytest tests/ -v`
  - Verify bug condition test passes (router predictions honored)
  - Verify preservation tests pass (complex queries still route to cloud)
  - Verify integration tests pass (end-to-end functionality)
  - Run manual validation with sample queries to confirm fix
  - Check debug logs show correct routing decision pipeline
  - Ensure all tests pass, ask the user if questions arise.