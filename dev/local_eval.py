#!/usr/bin/env python3
"""
dev/local_eval.py

OFFLINE, DEV-ONLY helper. Not part of the submitted container image
(excluded via .dockerignore). Use this to sanity-check classification
and tier routing decisions against a set of sample prompts before you
build and push the final image — per the guide's suggestion to "run a
local eval step to check your output quality before submitting."

This script does NOT call Fireworks by default — it only exercises the
zero-token classifier + tier policy so you can eyeball routing decisions
for a batch of sample prompts. Flip CALL_LIVE_API=1 if you want to
actually hit Fireworks with your own dev credentials (loaded from a
local .env you create yourself — never commit or ship it).

Usage:
    python3 dev/local_eval.py path/to/sample_tasks.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.category_classifier import classify_prompt
from src.tier_policy import TierPolicy


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 dev/local_eval.py path/to/sample_tasks.json")
        sys.exit(1)

    sample_path = Path(sys.argv[1])
    tasks = json.loads(sample_path.read_text(encoding="utf-8"))

    allowed_models_raw = os.environ.get(
        "ALLOWED_MODELS",
        "accounts/fireworks/models/llama-v3p1-8b-instruct,"
        "accounts/fireworks/models/llama-v3p1-70b-instruct,"
        "accounts/fireworks/models/llama-v3p1-405b-instruct",
    )
    allowed_models = [m.strip() for m in allowed_models_raw.split(",") if m.strip()]
    tier_policy = TierPolicy(allowed_models=allowed_models, config_path="config/tier_mapping.yaml")

    print(f"{'task_id':<10} {'category':<28} {'model_sequence'}")
    print("-" * 100)
    for task in tasks:
        category = classify_prompt(task["prompt"])
        sequence = tier_policy.sequence_for_category(category)
        print(f"{task['task_id']:<10} {category:<28} {sequence}")


if __name__ == "__main__":
    main()
