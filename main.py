#!/usr/bin/env python3
"""
main.py

Entrypoint for the Hybrid Token-Efficient Routing Agent.

Contract (per AMD Developer Hackathon Track 1 submission rules):
  - Read tasks from /input/tasks.json on startup
  - Write results to /output/results.json before exiting
  - Exit code 0 on success, non-zero on failure
  - Maximum total runtime: 10 minutes
  - All inference routed through FIREWORKS_BASE_URL using models from
    ALLOWED_MODELS only — no hardcoded model IDs, no local inference in
    the execution path, no caching of answers.

This module owns the global time budget and guarantees a best-effort
write to /output/results.json even if individual tasks fail, so a
handful of bad tasks cannot zero out the entire submission.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

from src.concurrency_manager import run_all_tasks
from src.escalation_controller import TaskResult
from src.fireworks_client import FireworksClient
from src.local_client import LocalClient
from src.result_writer import ResultWriteError, write_results
from src.task_loader import TaskLoadError, load_tasks
from src.tier_policy import TierPolicy

# --- Configuration -----------------------------------------------------

INPUT_PATH = os.environ.get("TASKS_INPUT_PATH", "/input/tasks.json")
OUTPUT_PATH = os.environ.get("RESULTS_OUTPUT_PATH", "/output/results.json")
TIER_CONFIG_PATH = os.environ.get("TIER_CONFIG_PATH", "config/tier_mapping.yaml")

TOTAL_RUNTIME_BUDGET_SECONDS = 10 * 60
SAFETY_BUFFER_SECONDS = 30  # leave headroom to write output before the hard 10-min ceiling
EFFECTIVE_DEADLINE_SECONDS = TOTAL_RUNTIME_BUDGET_SECONDS - SAFETY_BUFFER_SECONDS

MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "8"))

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")


def _read_required_env() -> tuple[str, str, list[str]]:
    api_key = os.environ.get("FIREWORKS_API_KEY", "")
    base_url = os.environ.get("FIREWORKS_BASE_URL", "")
    allowed_models_raw = os.environ.get("ALLOWED_MODELS", "")

    missing = []
    if not api_key:
        missing.append("FIREWORKS_API_KEY")
    if not base_url:
        missing.append("FIREWORKS_BASE_URL")
    if not allowed_models_raw:
        missing.append("ALLOWED_MODELS")

    if missing:
        raise RuntimeError(f"Missing required environment variable(s): {', '.join(missing)}")

    allowed_models = [m.strip() for m in allowed_models_raw.split(",") if m.strip()]
    if not allowed_models:
        raise RuntimeError("ALLOWED_MODELS was set but contained no valid model IDs")

    return api_key, base_url, allowed_models


async def _run(start_time: float) -> list[TaskResult]:
    api_key, base_url, allowed_models = _read_required_env()

    tasks = load_tasks(INPUT_PATH)
    if not tasks:
        logger.warning("No tasks to process — writing empty results file.")
        return []

    # Try to find a local model
    local_client = None
    local_model_id = None
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    if os.path.exists(models_dir):
        ggufs = [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
        if ggufs:
            local_model_id = ggufs[0]
            try:
                local_client = LocalClient(os.path.join(models_dir, local_model_id))
            except Exception as exc:
                logger.warning("Failed to load local model %s: %s", local_model_id, exc)
                local_model_id = None
                local_client = None

    tier_policy = TierPolicy(
        allowed_models=allowed_models, 
        config_path=TIER_CONFIG_PATH,
        local_model_id=local_model_id
    )
    client = FireworksClient(api_key=api_key, base_url=base_url)

    deadline = start_time + EFFECTIVE_DEADLINE_SECONDS

    try:
        results = await run_all_tasks(
            tasks=tasks,
            client=client,
            tier_policy=tier_policy,
            deadline=deadline,
            max_concurrency=MAX_CONCURRENCY,
            local_client=local_client,
        )
    finally:
        await client.close()

    return results


def main() -> int:
    start_time = time.monotonic()
    logger.info("Starting run. Effective deadline: %ds", EFFECTIVE_DEADLINE_SECONDS)

    results: list[TaskResult] = []
    try:
        results = asyncio.run(_run(start_time))
    except (TaskLoadError, RuntimeError) as exc:
        # Fatal, unrecoverable setup errors (bad input file, missing env vars).
        # Nothing meaningful to write — exit non-zero per the rules.
        logger.error("Fatal error before task processing could begin: %s", exc)
        return 1
    except Exception:  # noqa: BLE001 - top-level safety net, log full trace
        logger.exception("Unhandled exception during task processing")
        # Fall through: attempt to write whatever partial results exist.

    try:
        write_results(results, OUTPUT_PATH)
    except ResultWriteError as exc:
        logger.error("Failed to write results: %s", exc)
        return 1

    elapsed = time.monotonic() - start_time
    total_tasks = len(results)
    succeeded = sum(1 for r in results if r.succeeded_validation)
    total_tokens = sum(r.tokens_used for r in results)
    logger.info(
        "Run complete in %.1fs | tasks=%d | validated_ok=%d | total_tokens=%d",
        elapsed, total_tasks, succeeded, total_tokens,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
