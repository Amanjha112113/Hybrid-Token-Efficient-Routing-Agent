"""
concurrency_manager.py

Runs all tasks concurrently, bounded by a semaphore to avoid overwhelming
the Fireworks API or hitting aggressive rate limits, and aware of the
global runtime deadline so we never blow past the 10-minute ceiling
regardless of how many tasks are in the input file.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional

from src.escalation_controller import TaskResult, process_task
from src.fireworks_client import FireworksClient
from src.task_loader import Task
from src.tier_policy import TierPolicy

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 8


async def run_all_tasks(
    tasks: List[Task],
    client: FireworksClient,
    tier_policy: TierPolicy,
    deadline: float,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> List[TaskResult]:
    """
    Execute all tasks concurrently (bounded), returning one TaskResult per
    input task, in the same order as the input list — regardless of the
    order in which they actually complete.
    """
    if not tasks:
        return []

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded(task: Task) -> TaskResult:
        async with semaphore:
            time_left = deadline - time.monotonic()
            if time_left <= 0:
                logger.warning(
                    "Deadline already reached before starting task %s — skipping with empty answer",
                    task.task_id,
                )
                return TaskResult(
                    task_id=task.task_id,
                    answer="",
                    category="unknown",
                    tokens_used=0,
                    attempts=0,
                    succeeded_validation=False,
                )
            
            try:
                return await asyncio.wait_for(
                    process_task(task, client, tier_policy, deadline),
                    timeout=time_left
                )
            except asyncio.TimeoutError:
                logger.warning("Task %s timed out at global deadline", task.task_id)
                return TaskResult(
                    task_id=task.task_id,
                    answer="",
                    category="unknown",
                    tokens_used=0,
                    attempts=0,
                    succeeded_validation=False,
                )

    coroutines = [_bounded(task) for task in tasks]
    results = await asyncio.gather(*coroutines, return_exceptions=True)

    final_results: List[TaskResult] = []
    for task, result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error("Unhandled exception processing task %s: %s", task.task_id, result)
            final_results.append(
                TaskResult(
                    task_id=task.task_id,
                    answer="",
                    category="unknown",
                    tokens_used=0,
                    attempts=0,
                    succeeded_validation=False,
                )
            )
        else:
            final_results.append(result)

    return final_results
