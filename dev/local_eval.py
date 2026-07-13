#!/usr/bin/env python3
"""
dev/local_eval.py

Offline, zero-token, zero-network sanity check: for each sample prompt,
show which category it's classified into and which model tier sequence
it would use — WITHOUT spending a single real Fireworks call.

This is step 1 of validating your idea before you burn a submission:
"does my routing logic even point the right prompts at the right tiers?"
If a factual question shows up starting at tier 1 instead of tier 0, or
a JS code-gen prompt shows up mis-tiered, you'll see it here for free.

Usage:
    python3 dev/local_eval.py dev/sample_tasks.json
    python3 dev/local_eval.py ../test_tasks.json   # or any tasks.json-shaped file

Never shipped in the image — excluded via .dockerignore.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.category_classifier import classify_prompt
from src.tier_policy import TierPolicy

# A fake ALLOWED_MODELS list, just for local eyeballing. Swap in whatever
# naming convention you think launch day will actually use, to stress-test
# the cheapest-to-most-expensive ordering heuristic before it matters.
FAKE_ALLOWED_MODELS = [
    "accounts/fireworks/models/llama-v3p1-8b-instruct",
    "accounts/fireworks/models/llama-v3p1-70b-instruct",
    "accounts/fireworks/models/llama-v3p1-405b-instruct",
    "accounts/fireworks/models/qwen2p5-3b-instruct",
]


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <path-to-tasks.json>")
        return 1

    tasks_path = sys.argv[1]
    with open(tasks_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    tier_policy = TierPolicy(allowed_models=FAKE_ALLOWED_MODELS, config_path="config/tier_mapping.yaml")

    print(f"Model tiers (cheapest -> most expensive), from FAKE_ALLOWED_MODELS:")
    for i, m in enumerate(tier_policy.ordered_models):
        print(f"  tier {i}: {m}")
    print()

    for task in tasks:
        task_id = task.get("task_id", "?")
        prompt = task.get("prompt", "")
        category = classify_prompt(prompt)
        sequence = tier_policy.sequence_for_category(category)
        gen_params = tier_policy.generation_params(category)

        print(f"[{task_id}] category={category}")
        print(f"    prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"    tier sequence: {sequence}")
        print(f"    max_tokens={gen_params['max_tokens']} temperature={gen_params['temperature']}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
