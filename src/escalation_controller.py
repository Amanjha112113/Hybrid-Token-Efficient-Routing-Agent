"""
escalation_controller.py

Drives a single task through: classify -> pick model sequence -> call ->
validate -> escalate if needed, capped by the category's configured
max_escalations and the global time deadline. This is the module that
ties fireworks_client, tier_policy, and answer_validator together per task.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from src.answer_validator import validate
from src.category_classifier import classify_prompt
from src.fireworks_client import FireworksClient, FireworksClientError
from src.local_client import LocalClient
from src.task_loader import Task
from src.tier_policy import TierPolicy

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    task_id: str
    answer: str
    category: str
    tokens_used: int
    attempts: int
    succeeded_validation: bool


async def process_task(
    task: Task,
    client: FireworksClient,
    tier_policy: TierPolicy,
    deadline: float,
    local_client: Optional[LocalClient] = None,
) -> TaskResult:
    """
    Process a single task end-to-end. Never raises on model/validation
    failure — always returns a best-effort TaskResult so one bad task
    cannot take down the whole run. Only truly unrecoverable conditions
    (e.g. zero models available) propagate up.
    """
    category = classify_prompt(task.prompt)
    model_sequence = tier_policy.sequence_for_category(category)
    gen_params = tier_policy.generation_params()

    last_answer = ""
    total_tokens = 0
    attempts = 0
    succeeded = False

    for model in model_sequence:
        if time.monotonic() >= deadline:
            logger.warning(
                "Deadline reached while processing task %s — returning best effort",
                task.task_id,
            )
            break

        attempts += 1
        try:
            if model.startswith("local:") and local_client is not None:
                result = await local_client.complete(
                    prompt=task.prompt,
                    max_tokens=gen_params["max_tokens"],
                    temperature=gen_params["temperature"],
                    deadline=deadline,
                )
            else:
                result = await client.complete(
                    model=model,
                    prompt=task.prompt,
                    max_tokens=gen_params["max_tokens"],
                    temperature=gen_params["temperature"],
                    deadline=deadline,
                )
        except Exception as exc:
            logger.warning(
                "Model call failed for task %s on model %s: %s",
                task.task_id, model, exc,
            )
            continue

        last_answer = result.text
        total_tokens += result.total_tokens

        is_valid, reason = validate(result.text, category)
        logger.debug(
            "Task %s | model=%s | valid=%s | reason=%s", task.task_id, model, is_valid, reason
        )

        if is_valid:
            succeeded = True
            break
        # else: loop continues to next (more expensive) model in the sequence

    return TaskResult(
        task_id=task.task_id,
        answer=last_answer,
        category=category,
        tokens_used=total_tokens,
        attempts=attempts,
        succeeded_validation=succeeded,
    )
