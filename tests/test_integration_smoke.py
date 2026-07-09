"""
Integration smoke test: runs the full pipeline (classifier -> tier policy ->
escalation controller -> concurrency manager -> result writer) with a fake
FireworksClient that returns canned answers instead of hitting the network.
Verifies orchestration, escalation-on-failure, and output schema end to end.
"""

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.concurrency_manager import run_all_tasks
from src.fireworks_client import CompletionResult
from src.result_writer import write_results
from src.task_loader import Task
from src.tier_policy import TierPolicy


class FakeFireworksClient:
    """Drop-in replacement for FireworksClient — no network calls."""

    def __init__(self, canned_responses):
        # canned_responses: dict[model] -> answer text (simulates per-model quality)
        self._canned = canned_responses
        self.call_log = []

    async def complete(self, model, prompt, max_tokens=600, temperature=0.2, deadline=None):
        self.call_log.append((model, prompt[:30]))
        text = self._canned.get(model, "")
        return CompletionResult(text=text, total_tokens=len(text.split()), model=model)

    async def close(self):
        pass


async def main():
    allowed_models = [
        "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "accounts/fireworks/models/llama-v3p1-70b-instruct",
    ]
    tier_policy = TierPolicy(allowed_models=allowed_models, config_path="config/tier_mapping.yaml")

    tasks = [
        Task(task_id="t1", prompt="Explain how photosynthesis works."),
        Task(task_id="t2", prompt="Classify the sentiment of this review as positive or negative: great product!"),
        Task(task_id="t3", prompt="Write a function that adds two numbers."),
    ]

    # Cheap model gives a weak/invalid answer for t3 (empty), forcing escalation.
    canned = {
        "accounts/fireworks/models/llama-v3p1-8b-instruct": "",
        "accounts/fireworks/models/llama-v3p1-70b-instruct": "```python\ndef add(a, b):\n    return a + b\n```",
    }
    client = FakeFireworksClient(canned)

    deadline = time.monotonic() + 60

    # Monkeypatch: run_all_tasks expects a FireworksClient-shaped object;
    # our fake satisfies the same interface (.complete, .close).
    results = await run_all_tasks(
        tasks=tasks, client=client, tier_policy=tier_policy, deadline=deadline, max_concurrency=4
    )

    assert len(results) == 3, f"expected 3 results, got {len(results)}"

    result_by_id = {r.task_id: r for r in results}

    # t1 (factual) and t2 (sentiment) both start cheap and get empty answers
    # from the cheap model -> must escalate to the 70b model to succeed.
    assert result_by_id["t3"].succeeded_validation is True
    assert "def add" in result_by_id["t3"].answer

    with tempfile.TemporaryDirectory() as tmp:
        out_path = str(Path(tmp) / "results.json")
        write_results(results, out_path)

        with open(out_path, "r", encoding="utf-8") as f:
            written = json.load(f)

        assert isinstance(written, list)
        assert len(written) == 3
        for entry in written:
            assert set(entry.keys()) == {"task_id", "answer"}

    print("Integration smoke test passed.")
    print(f"Total fake API calls made: {len(client.call_log)}")


if __name__ == "__main__":
    asyncio.run(main())
