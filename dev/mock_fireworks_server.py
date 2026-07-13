#!/usr/bin/env python3
"""
dev/mock_fireworks_server.py

A tiny, dependency-free (stdlib only) stand-in for the Fireworks
/chat/completions endpoint. Point FIREWORKS_BASE_URL at this instead of
the real API to test the FULL container contract — input reading, output
writing, concurrency, retries, deadline handling, exit codes — without
spending real tokens or eating into your 10-pushes/hour submission quota.

It deliberately does NOT try to be a good model. It's for testing your
container's PLUMBING, not your prompt quality or accuracy. Use your real
dev Fireworks key against a small task set for that instead.

Usage:
    python3 dev/mock_fireworks_server.py --port 8899

Then run your container against it:
    docker run --rm \\
      -e FIREWORKS_API_KEY=dummy-key-not-checked \\
      -e FIREWORKS_BASE_URL=http://host.docker.internal:8899 \\
      -e ALLOWED_MODELS=mock-small,mock-medium,mock-large \\
      -v /tmp/input:/input \\
      -v /tmp/output:/output \\
      routing-agent:latest

Configurable via environment variables (set before starting the server):
    MOCK_FAIL_RATE           float 0-1, fraction of calls that raise a 500
                              (tests your retry/backoff logic). Default 0.
    MOCK_LATENCY_SECONDS      float, artificial delay per call, simulates a
                              slow model (tests deadline/timeout handling).
                              Default 0.
    MOCK_TRUNCATE_MODELS      comma-separated model-name substrings that
                              should always return finish_reason="length"
                              (tests your truncation-catch/escalation path).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FAIL_RATE = float(os.environ.get("MOCK_FAIL_RATE", "0"))
LATENCY_SECONDS = float(os.environ.get("MOCK_LATENCY_SECONDS", "0"))
TRUNCATE_MODELS = [
    m.strip() for m in os.environ.get("MOCK_TRUNCATE_MODELS", "").split(",") if m.strip()
]


def _canned_answer(prompt: str) -> str:
    """Crude prompt sniffing, just enough to exercise different validator
    branches (code fence, sentiment label, refusal-shaped text, etc.)."""
    lowered = prompt.lower()

    if ("bug" in lowered or "fix" in lowered) and "def" in lowered:
        return "```python\ndef fixed_function(nums):\n    return max(nums)\n```"
    if "write a" in lowered and ("function" in lowered or "program" in lowered):
        return "```python\ndef mock_generated_function():\n    return True\n```"
    if "sentiment" in lowered:
        return "Negative — mock reasoning about tone and word choice."
    if "summar" in lowered:
        return "This is a mock one-sentence summary of the provided text."
    if "extract" in lowered and ("entit" in lowered or "names" in lowered):
        return "- Mock Person: Person\n- Mock Org: Organization"
    return "This is a mock factual/general answer, long enough to pass basic checks."


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter default logging
        print(f"[mock-fireworks] {self.address_string()} - {fmt % args}")

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "unknown endpoint"}')
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "invalid json"}')
            return

        model = body.get("model", "unknown-model")
        messages = body.get("messages", [])
        prompt = ""
        for m in messages:
            if m.get("role") == "user":
                prompt = m.get("content", "")

        if LATENCY_SECONDS > 0:
            time.sleep(LATENCY_SECONDS)

        if FAIL_RATE > 0 and random.random() < FAIL_RATE:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "simulated server error"}).encode())
            return

        answer = _canned_answer(prompt)
        finish_reason = "stop"
        if any(sub in model for sub in TRUNCATE_MODELS):
            finish_reason = "length"
            answer = answer[: max(5, len(answer) // 3)]  # simulate a cut-off response

        prompt_tokens = max(1, len(prompt.split()))
        completion_tokens = max(1, len(answer.split()))

        response = {
            "id": "mock-completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

        body_bytes = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), MockHandler)
    print(f"Mock Fireworks server listening on http://0.0.0.0:{args.port}")
    print(f"  MOCK_FAIL_RATE={FAIL_RATE}  MOCK_LATENCY_SECONDS={LATENCY_SECONDS}  "
          f"MOCK_TRUNCATE_MODELS={TRUNCATE_MODELS or 'none'}")
    print("Point FIREWORKS_BASE_URL at this URL from your container. Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
