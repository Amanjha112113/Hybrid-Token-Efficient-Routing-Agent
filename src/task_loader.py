"""
task_loader.py

Reads and validates the input task list. Fails loudly (raises) on any
schema problem so main.py can decide how to exit — we never silently
proceed with a malformed or partial task list.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class TaskLoadError(Exception):
    """Raised when /input/tasks.json is missing, unreadable, or malformed."""


@dataclass(frozen=True)
class Task:
    task_id: str
    prompt: str


def load_tasks(input_path: str = "/input/tasks.json") -> List[Task]:
    """
    Load and validate the task list.

    Expected schema:
        [
          {"task_id": "t1", "prompt": "..."},
          ...
        ]

    Raises:
        TaskLoadError: if the file is missing, not valid JSON, not a list,
            or any entry is missing required string fields.
    """
    path = Path(input_path)
    if not path.exists():
        raise TaskLoadError(f"Input file not found at {input_path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TaskLoadError(f"Could not read {input_path}: {exc}") from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise TaskLoadError(f"Input file is not valid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise TaskLoadError("Input JSON must be a list of task objects")

    if len(data) == 0:
        logger.warning("Task list is empty — nothing to do.")
        return []

    tasks: List[Task] = []
    seen_ids = set()

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            logger.warning("Task at index %d is not an object — skipping", i)
            continue

        task_id = entry.get("task_id")
        prompt = entry.get("prompt")

        if not isinstance(task_id, str) or not task_id.strip():
            logger.warning("Task at index %d has missing/invalid 'task_id' — skipping", i)
            continue
        if not isinstance(prompt, str) or not prompt.strip():
            logger.warning("Task at index %d ('%s') has missing/invalid 'prompt' — skipping", i, task_id)
            continue

        if task_id in seen_ids:
            logger.warning("Duplicate task_id encountered: '%s' — skipping duplicate", task_id)
            continue
        seen_ids.add(task_id)

        tasks.append(Task(task_id=task_id, prompt=prompt))

    logger.info("Loaded %d tasks from %s", len(tasks), input_path)
    return tasks
