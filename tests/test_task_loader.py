import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.task_loader import TaskLoadError, load_tasks


def _write_temp_json(data) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


def test_valid_tasks_load():
    path = _write_temp_json([{"task_id": "t1", "prompt": "Hello"}])
    tasks = load_tasks(path)
    assert len(tasks) == 1
    assert tasks[0].task_id == "t1"
    assert tasks[0].prompt == "Hello"


def test_empty_list_ok():
    path = _write_temp_json([])
    tasks = load_tasks(path)
    assert tasks == []


def test_missing_task_id_raises():
    path = _write_temp_json([{"prompt": "Hello"}])
    try:
        load_tasks(path)
        assert False, "expected TaskLoadError"
    except TaskLoadError:
        pass


def test_duplicate_task_id_raises():
    path = _write_temp_json([
        {"task_id": "t1", "prompt": "Hello"},
        {"task_id": "t1", "prompt": "World"},
    ])
    try:
        load_tasks(path)
        assert False, "expected TaskLoadError"
    except TaskLoadError:
        pass


def test_missing_file_raises():
    try:
        load_tasks("/nonexistent/path/tasks.json")
        assert False, "expected TaskLoadError"
    except TaskLoadError:
        pass


if __name__ == "__main__":
    test_valid_tasks_load()
    test_empty_list_ok()
    test_missing_task_id_raises()
    test_duplicate_task_id_raises()
    test_missing_file_raises()
    print("All task_loader tests passed.")
