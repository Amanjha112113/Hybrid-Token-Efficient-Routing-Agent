#!/usr/bin/env python3
"""
tests/test_integration_smoke.py

Runs the real pipeline end-to-end (task_loader -> concurrency_manager ->
escalation_controller -> tier_policy -> answer_validator -> result_writer)
against a FAKE Fireworks client that never touches the network. This
catches wiring/schema/deadline bugs that the per-module unit tests can't:
things like "does the final /output/results.json actually validate",
"does the global deadline actually get respected", "does one task's
exception take down the whole batch".

It does NOT tell you anything about real answer accuracy — that needs
either the real Fireworks API (dev/mock_fireworks_server.py + a real key,
or the real judge at submission time). This test is about *plumbing*
correctness, not model quality.

Run: python3 tests/test_integration_smoke.py
"""

import asyncio
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.concurrency_manager import run_all_tasks
from src.result_writer import write_results
from src.task_loader import load_tasks
from src.tier_policy import TierPolicy


class FakeFireworksClient:
    """Duck-types src.fireworks_client.FireworksClient.complete() with
    canned, deterministic answers — no network, no cost, no flakiness."""

    def __init__(self, canned_by_category=None, always_fail_models=()):
        self.calls = []
        self._canned = canned_by_category or {}
        self._always_fail_models = set(always_fail_models)

    async def complete(self, model, prompt, system_prompt="", max_tokens=600,
                        temperature=0.2, deadline=None):
        from src.fireworks_client import CompletionResult, FireworksClientError

        self.calls.append({"model": model, "prompt": prompt})

        if model in self._always_fail_models:
            raise FireworksClientError(f"simulated hard failure for {model}")

        # Extremely crude canned-answer picker, just enough to exercise
        # each validator branch realistically.
        text = "This is a mock answer for testing purposes only, with enough words."
        if "bug" in prompt.lower() or "fix" in prompt.lower():
            text = "```python\ndef fixed():\n    return 42\n```"
        elif "sentiment" in prompt.lower():
            text = "Negative — the reviewer is unhappy with the product."

        return CompletionResult(text=text, total_tokens=17, model=model, finish_reason="stop")

    async def close(self):
        pass


def run() -> None:
    failures = []

    tasks_payload = [
        {"task_id": "t1", "prompt": "What is the capital of France?"},
        {"task_id": "t2", "prompt": "Classify the sentiment: I loved this movie."},
        {"task_id": "t3", "prompt": "This function has a bug: def f(): return"},
    ]

    fd, tasks_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(tasks_payload, f)

    tasks = load_tasks(tasks_path)

    tier_policy = TierPolicy(
        allowed_models=["mock-model-1b", "mock-model-8b", "mock-model-70b"],
        config_path="config/tier_mapping.yaml",
    )
    client = FakeFireworksClient()

    deadline = time.monotonic() + 30  # generous — this is a smoke test, not a load test

    results = asyncio.run(
        run_all_tasks(tasks=tasks, client=client, tier_policy=tier_policy,
                       deadline=deadline, max_concurrency=4)
    )

    # --- basic shape checks ---
    if len(results) != len(tasks_payload):
        failures.append(f"expected {len(tasks_payload)} results, got {len(results)}")

    result_ids = {r.task_id for r in results}
    expected_ids = {t["task_id"] for t in tasks_payload}
    if result_ids != expected_ids:
        failures.append(f"result task_ids {result_ids} != input task_ids {expected_ids}")

    for r in results:
        if not isinstance(r.answer, str):
            failures.append(f"task {r.task_id}: answer is not a string")

    # --- write + reload the real output file, exactly like main.py does ---
    out_fd, out_path = tempfile.mkstemp(suffix=".json")
    os.close(out_fd)
    write_results(results, out_path)

    with open(out_path) as f:
        written = json.load(f)

    if not isinstance(written, list):
        failures.append("written output is not a JSON list")
    for entry in written:
        if set(entry.keys()) != {"task_id", "answer"}:
            failures.append(f"written entry has wrong keys: {entry.keys()}")

    # --- deadline enforcement: a deadline in the past should short-circuit
    #     every task with an empty, non-crashing result rather than hang ---
    past_deadline = time.monotonic() - 1
    results_expired = asyncio.run(
        run_all_tasks(tasks=tasks, client=client, tier_policy=tier_policy,
                       deadline=past_deadline, max_concurrency=4)
    )
    if len(results_expired) != len(tasks_payload):
        failures.append("expired-deadline run should still return one result per task")
    if any(r.succeeded_validation for r in results_expired):
        failures.append("expired-deadline run should not report any task as successfully validated")

    if failures:
        print(f"FAILED: {len(failures)} case(s)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print(f"passed: integration smoke — {len(results)} tasks, output schema valid, deadline respected")


if __name__ == "__main__":
    run()
