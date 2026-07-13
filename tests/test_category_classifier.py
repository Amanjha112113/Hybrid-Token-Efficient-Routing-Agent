#!/usr/bin/env python3
"""
tests/test_category_classifier.py

Pure-code, zero-network unit tests for src/category_classifier.py.
Run: python3 tests/test_category_classifier.py

These tests exist so a wrong classification is caught here, for free,
instead of silently costing you a wasted/mis-tiered Fireworks call during
a real (rate-limited) submission run.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.category_classifier import (
    CODE_DEBUGGING,
    CODE_GENERATION,
    FACTUAL_KNOWLEDGE,
    LOGICAL_REASONING,
    MATHEMATICAL_REASONING,
    NAMED_ENTITY_RECOGNITION,
    SENTIMENT_CLASSIFICATION,
    TEXT_SUMMARISATION,
    classify_prompt,
)

# (prompt, expected_category) — includes the 8 official practice tasks
# plus edge cases worth guarding against.
CASES = [
    # --- official practice tasks ---
    ("What is the capital of Australia, and what body of water is it near?", FACTUAL_KNOWLEDGE),
    ("A store has 240 items. It sells 15% on Monday and 60 more on Tuesday. How many items remain?", MATHEMATICAL_REASONING),
    ("Classify the sentiment of this review: The battery life is great, but the screen scratches too easily.", SENTIMENT_CLASSIFICATION),
    ("Summarize the following in exactly one sentence: The Industrial Revolution was a period ...", TEXT_SUMMARISATION),
    ("Extract all named entities and their types from: Maria Sanchez joined Fireworks AI in Berlin last March.", NAMED_ENTITY_RECOGNITION),
    ("This function should return the max of a list but has a bug: def get_max(nums): return nums[0]. Find and fix it.", CODE_DEBUGGING),
    ("Three friends, Sam, Jo, and Lee, each own a different pet: cat, dog, bird. Sam does not own the bird. Jo owns the dog. Who owns the cat?", LOGICAL_REASONING),
    ("Write a Python function that returns the second-largest number in a list, handling duplicates correctly.", CODE_GENERATION),

    # --- edge cases ---
    # Non-Python code generation — classifier should still call this code_generation.
    # (The validator's Python-only ast.parse() is a SEPARATE bug — see
    # test_answer_validator.py. This test only checks classification.)
    ("Write a JavaScript function that checks if a string is a palindrome.", CODE_GENERATION),
    ("Write a Java program that implements binary search.", CODE_GENERATION),

    # Math word problems phrased without obvious numeric symbols.
    # Both of these are genuinely computational (rate reasoning / algebra),
    # not trivia recall — they should NOT fall into factual_knowledge.
    ("If 5 machines take 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?", MATHEMATICAL_REASONING),
    ("Solve for x: 3x + 15 = 45", MATHEMATICAL_REASONING),

    # Sentiment phrased without the word "sentiment".
    ("Classify the sentiment: This restaurant has terrible service and the food was cold.", SENTIMENT_CLASSIFICATION),

    # Bare factual fallback — nothing else should match.
    ("Who wrote the play Romeo and Juliet?", FACTUAL_KNOWLEDGE),
    ("What is the largest planet in our solar system?", FACTUAL_KNOWLEDGE),
]


def run() -> None:
    failures = []
    for prompt, expected in CASES:
        actual = classify_prompt(prompt)
        if actual != expected:
            failures.append((prompt, expected, actual))

    if failures:
        print(f"FAILED: {len(failures)}/{len(CASES)} classification cases wrong\n")
        for prompt, expected, actual in failures:
            print(f"  prompt:   {prompt[:70]}...")
            print(f"  expected: {expected}")
            print(f"  actual:   {actual}\n")
        sys.exit(1)

    print(f"passed: category_classifier — {len(CASES)}/{len(CASES)} cases correct")


if __name__ == "__main__":
    run()
