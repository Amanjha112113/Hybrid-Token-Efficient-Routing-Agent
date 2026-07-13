#!/usr/bin/env python3
"""
tests/test_task_loader.py

Pure-code, zero-network unit tests for src/task_loader.py — the
/input/tasks.json contract. A bug here is the highest-severity kind:
per the rules, malformed I/O handling can zero your entire submission.

Run: python3 tests/test_task_loader.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.task_loader import TaskLoadError, load_tasks


def _write_temp(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def run() -> None:
    failures = []

    # --- valid, minimal, well-formed input ---
    path = _write_temp(json.dumps([{"task_id": "t1", "prompt": "hello"}]))
    tasks = load_tasks(path)
    if len(tasks) != 1 or tasks[0].task_id != "t1":
        failures.append("valid minimal input did not load correctly")

    # --- empty list is valid (should return [], not raise) ---
    path = _write_temp("[]")
    try:
        tasks = load_tasks(path)
        if tasks != []:
            failures.append("empty list should return an empty list")
    except TaskLoadError:
        failures.append("empty list should NOT raise TaskLoadError")

    # --- missing file should raise ---
    try:
        load_tasks("/tmp/definitely-does-not-exist-tasks.json")
        failures.append("missing input file should raise TaskLoadError")
    except TaskLoadError:
        pass

    # --- not valid JSON should raise ---
    path = _write_temp("{not valid json")
    try:
        load_tasks(path)
        failures.append("invalid JSON should raise TaskLoadError")
    except TaskLoadError:
        pass

    # --- JSON that isn't a list should raise ---
    path = _write_temp(json.dumps({"task_id": "t1", "prompt": "hello"}))
    try:
        load_tasks(path)
        failures.append("non-list JSON should raise TaskLoadError")
    except TaskLoadError:
        pass

    # --- one malformed entry among otherwise-valid entries ---
    mixed = [
        {"task_id": "t1", "prompt": "valid prompt"},
        {"task_id": "t2"},  # missing "prompt"
        {"task_id": "t3", "prompt": "also valid"},
    ]
    path = _write_temp(json.dumps(mixed))
    try:
        tasks = load_tasks(path)
        if len(tasks) != 2:
            failures.append(f"expected 2 valid tasks after skipping malformed, got {len(tasks)}")
    except TaskLoadError:
        failures.append("a task missing 'prompt' should be skipped, not raise TaskLoadError")

    # --- duplicate task_id should be skipped ---
    dup = [
        {"task_id": "t1", "prompt": "a"},
        {"task_id": "t1", "prompt": "b"},
    ]
    path = _write_temp(json.dumps(dup))
    try:
        tasks = load_tasks(path)
        if len(tasks) != 1:
            failures.append(f"expected 1 valid task after skipping duplicate, got {len(tasks)}")
    except TaskLoadError:
        failures.append("duplicate task_id should be skipped, not raise TaskLoadError")

    if failures:
        print(f"FAILED: {len(failures)} case(s)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("passed: task_loader — input contract behaves as documented")


if __name__ == "__main__":
    run()
