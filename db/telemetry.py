"""
db/telemetry.py

Background telemetry writer for the AI Gateway.

Designed to be called as a FastAPI ``BackgroundTask`` so it runs *after*
the HTTP response has already been sent to the client — zero latency impact
on the critical path.

Key design decisions:
- Errors are caught and logged, never re-raised (a DB failure must not
  crash the main request).
- All DB I/O is async so it doesn't block the event loop.
- The ``RequestLog.from_route_result`` factory centralises all derived-
  field computation (cost, savings, escalation path).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from db.engine import get_db_session
from db.models import RequestLog

logger = logging.getLogger(__name__)


async def log_request_to_db(
    *,
    task_id: str,
    prompt: str,
    category: str,
    backend: str,
    model_used: str,
    tokens_used: int,
    elapsed_ms: int,
    succeeded_validation: bool,
    attempts: int,
    served_from_cache: bool = False,
) -> None:
    """
    Persist a single routing event to the ``request_logs`` table.

    Intended to be scheduled as a ``BackgroundTask``::

        background_tasks.add_task(
            log_request_to_db,
            task_id=...,
            prompt=...,
            ...
        )

    This function is fully self-contained — it opens its own DB session so
    the main request handler never has to touch the database at all.
    """
    try:
        log_entry = RequestLog.from_route_result(
            task_id=task_id,
            prompt=prompt,
            category=category,
            backend=backend,
            model_used=model_used,
            tokens_used=tokens_used,
            elapsed_ms=elapsed_ms,
            succeeded_validation=succeeded_validation,
            attempts=attempts,
            served_from_cache=served_from_cache,
        )
        async with get_db_session() as session:
            session.add(log_entry)
        logger.debug(
            "Telemetry persisted: task_id=%s backend=%s tokens=%d cost=$%.6f",
            task_id,
            backend,
            tokens_used,
            log_entry.cost_usd,
        )
    except Exception as exc:  # noqa: BLE001
        # A telemetry failure must never bubble up to the user
        logger.error("Failed to persist telemetry for task %s: %s", task_id, exc)
