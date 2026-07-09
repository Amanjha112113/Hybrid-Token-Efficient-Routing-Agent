"""
result_writer.py

Assembles and writes the final /output/results.json. Malformed output
scores zero, so this module validates the structure twice: once against
the expected schema in Python, and once via a JSON round-trip, before
touching disk.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from src.escalation_controller import TaskResult

logger = logging.getLogger(__name__)


class ResultWriteError(Exception):
    """Raised if results cannot be validated or written correctly."""


def write_results(results: List[TaskResult], output_path: str = "/output/results.json") -> None:
    payload = [{"task_id": r.task_id, "answer": r.answer} for r in results]

    _validate_schema(payload)

    # Round-trip through JSON to catch any non-serializable edge case
    # before writing to disk.
    try:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        json.loads(serialized)  # re-parse to be certain it's valid JSON
    except (TypeError, ValueError) as exc:
        raise ResultWriteError(f"Result payload failed JSON round-trip: {exc}") from exc

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        out_path.write_text(serialized, encoding="utf-8")
    except OSError as exc:
        raise ResultWriteError(f"Could not write results to {output_path}: {exc}") from exc

    logger.info("Wrote %d results to %s", len(payload), output_path)


def _validate_schema(payload: List[dict]) -> None:
    if not isinstance(payload, list):
        raise ResultWriteError("Results payload must be a list")

    for i, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ResultWriteError(f"Result at index {i} is not an object")
        if set(entry.keys()) != {"task_id", "answer"}:
            raise ResultWriteError(
                f"Result at index {i} has unexpected keys: {list(entry.keys())}"
            )
        if not isinstance(entry["task_id"], str):
            raise ResultWriteError(f"Result at index {i} has non-string task_id")
        if not isinstance(entry["answer"], str):
            raise ResultWriteError(f"Result at index {i} has non-string answer")
