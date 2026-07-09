"""
fireworks_client.py

Thin async wrapper around the Fireworks AI chat completions endpoint.
Every model call in this project goes through this module and therefore
through FIREWORKS_BASE_URL, as required by the submission rules. The
API key is read from the environment on every call — never cached to
disk, never bundled.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class FireworksClientError(Exception):
    """Raised when a Fireworks call fails after all retries are exhausted."""


@dataclass
class CompletionResult:
    text: str
    total_tokens: int
    model: str


class FireworksClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ):
        if not api_key:
            raise ValueError("FIREWORKS_API_KEY is required")
        if not base_url:
            raise ValueError("FIREWORKS_BASE_URL is required")

        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 600,
        temperature: float = 0.2,
        deadline: Optional[float] = None,
    ) -> CompletionResult:
        """
        Call the chat completions endpoint for a single prompt.

        `deadline` is an optional `time.monotonic()`-comparable timestamp;
        if provided and already passed, the call is skipped immediately
        rather than issued, to protect the global runtime budget.
        """
        if deadline is not None and _time_remaining(deadline) <= 0:
            raise FireworksClientError("Deadline already exceeded — call skipped")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            if deadline is not None and _time_remaining(deadline) <= 0:
                raise FireworksClientError("Deadline exceeded during retries")

            try:
                response = await self._client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                return _parse_completion(data, model)

            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                logger.warning(
                    "Transient error calling model %s (attempt %d/%d): %s",
                    model, attempt + 1, self._max_retries + 1, exc,
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                # Retry on server-side / rate-limit errors only.
                if status >= 500 or status == 429:
                    last_error = exc
                    logger.warning(
                        "Server/rate-limit error (%d) calling model %s (attempt %d/%d)",
                        status, model, attempt + 1, self._max_retries + 1,
                    )
                else:
                    # Client-side error (e.g. bad model id, bad request) — do not retry.
                    raise FireworksClientError(
                        f"Non-retryable error calling {model}: {status} {exc.response.text}"
                    ) from exc
            except (KeyError, ValueError, IndexError) as exc:
                # Malformed response body — do not spin retries forever.
                raise FireworksClientError(f"Malformed response from {model}: {exc}") from exc

            # Exponential backoff before retrying, but never past the deadline.
            if attempt < self._max_retries:
                backoff = min(2 ** attempt, 4)
                if deadline is not None:
                    backoff = min(backoff, max(_time_remaining(deadline), 0))
                await asyncio.sleep(backoff)

        raise FireworksClientError(f"Exhausted retries calling {model}: {last_error}")


def _parse_completion(data: dict, model: str) -> CompletionResult:
    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        raise KeyError("Response missing 'choices'")

    message = choices[0].get("message", {})
    text = message.get("content", "")
    if text is None:
        text = ""

    usage = data.get("usage", {}) or {}
    total_tokens = int(usage.get("total_tokens", 0))

    return CompletionResult(text=text.strip(), total_tokens=total_tokens, model=model)


def _time_remaining(deadline: float) -> float:
    import time
    return deadline - time.monotonic()
