#!/usr/bin/env python3
"""
tests/test_answer_validator.py

Pure-code, zero-network unit tests for src/answer_validator.py.
Run: python3 tests/test_answer_validator.py

Each case is (description, CompletionResult, category, expected_is_valid).
Cases marked KNOWN_BUG are expected to currently FAIL — they document a
real gap (see review notes) rather than being silently skipped, so the
bug stays visible in the test output until it's actually fixed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.answer_validator import validate_tier_a
from src.category_classifier import (
    CODE_DEBUGGING,
    CODE_GENERATION,
    FACTUAL_KNOWLEDGE,
    MATHEMATICAL_REASONING,
    SENTIMENT_CLASSIFICATION,
    TEXT_SUMMARISATION,
)
from src.fireworks_client import CompletionResult


def r(text, finish_reason="stop"):
    return CompletionResult(text=text, total_tokens=50, model="test", finish_reason=finish_reason)


CASES = [
    # (description, result, category, expected_is_valid, known_bug)
    (
        "valid python code, code_generation",
        r("```python\ndef add(a, b):\n    return a + b\n```"),
        CODE_GENERATION, True, False,
    ),
    (
        "valid javascript code, code_generation — KNOWN BUG: validator is Python-only",
        r("```javascript\nfunction isPalindrome(str) {\n  const c = str.toLowerCase();\n  return c === c.split('').reverse().join('');\n}\n```"),
        CODE_GENERATION, True, True,
    ),
    (
        "syntactically broken python, code_debugging",
        r("```python\ndef get_max(nums)\n    return nums[0]\n```"),  # missing colon
        CODE_DEBUGGING, False, False,
    ),
    (
        "empty answer, any category",
        r(""),
        FACTUAL_KNOWLEDGE, False, False,
    ),
    (
        "truncated answer (finish_reason=length)",
        r("The capital of Australia is Can", finish_reason="length"),
        FACTUAL_KNOWLEDGE, False, False,
    ),
    (
        "hard refusal text",
        r("I cannot assist with that request."),
        FACTUAL_KNOWLEDGE, False, False,
    ),
    (
        "narration leak (chain-of-thought bleeding into the answer)",
        r("Let me think about this step by step. The user is asking for the capital."),
        FACTUAL_KNOWLEDGE, False, False,
    ),
    (
        "sentiment with justification",
        r("Negative — the reviewer complains about cold food and slow service."),
        SENTIMENT_CLASSIFICATION, True, False,
    ),
    (
        "sentiment, label only, no justification",
        r("Negative"),
        SENTIMENT_CLASSIFICATION, True, False,
    ),
    (
        "plain factual answer, non-empty prose",
        r("The capital of Australia is Canberra, near Lake Burley Griffin."),
        FACTUAL_KNOWLEDGE, True, False,
    ),
    (
        "plain summary, non-empty prose",
        r("The Industrial Revolution shifted economies toward efficient manufacturing."),
        TEXT_SUMMARISATION, True, False,
    ),
]


def run() -> None:
    real_failures = []
    known_bugs_still_present = []
    known_bugs_now_fixed = []

    for desc, result, category, expected, known_bug in CASES:
        actual, reason = validate_tier_a(result, category)
        if actual == expected:
            if known_bug:
                known_bugs_now_fixed.append(desc)
        else:
            if known_bug:
                known_bugs_still_present.append((desc, reason))
            else:
                real_failures.append((desc, expected, actual, reason))

    print(f"answer_validator — {len(CASES)} cases")
    if known_bugs_now_fixed:
        print(f"  🎉 known bug(s) now FIXED: {known_bugs_now_fixed}")
    if known_bugs_still_present:
        print(f"  ⚠️  known bug(s) still present ({len(known_bugs_still_present)}):")
        for desc, reason in known_bugs_still_present:
            print(f"      - {desc}  (validator said: {reason})")

    if real_failures:
        print(f"\nFAILED: {len(real_failures)} unexpected case(s)")
        for desc, expected, actual, reason in real_failures:
            print(f"  - {desc}: expected is_valid={expected}, got={actual} ({reason})")
        sys.exit(1)

    print("\npassed: no NEW/unexpected validator regressions")


if __name__ == "__main__":
    run()
