"""
local_client.py

Wraps llama_cpp to provide local inference with a cost of 0 tokens.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional
from llama_cpp import Llama

logger = logging.getLogger(__name__)

@dataclass
class LocalCompletionResult:
    text: str
    total_tokens: int
    model: str


class LocalClient:
    def __init__(self, model_path: str, n_ctx: int = 2048):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Local model not found at {model_path}")
        
        logger.info("Loading local model from %s...", model_path)
        self._model = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            verbose=False,
            n_gpu_layers=0  # purely CPU bound for this hackathon
        )
        self.model_name = os.path.basename(model_path)
        self._lock = asyncio.Lock()
        logger.info("Local model loaded successfully.")

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 600,
        temperature: float = 0.2,
        deadline: Optional[float] = None,
    ) -> LocalCompletionResult:
        """
        Call the local model to generate a response.
        Runs synchronously but is meant to be called in an async context,
        so it could block the event loop in high-concurrency (fine for this setup since it's one local model).
        Wait, to avoid blocking the event loop we should wrap the call in asyncio.to_thread.
        """
        import asyncio
        import time
        
        if deadline is not None and deadline - time.monotonic() <= 0:
            raise RuntimeError("Deadline already exceeded — local call skipped")

        def _run_inference():
            messages = [{"role": "user", "content": prompt}]
            # llama_cpp supports create_chat_completion out of the box
            response = self._model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response

        # Run inference in a separate thread so it doesn't stall other tasks
        # But we must serialize access to the same Llama instance to prevent GGML assertions
        async with self._lock:
            response = await asyncio.to_thread(_run_inference)
        
        text = ""
        if "choices" in response and len(response["choices"]) > 0:
            text = response["choices"][0].get("message", {}).get("content", "")
            
        # The true magic of the local tier: tokens cost ZERO towards the score!
        return LocalCompletionResult(
            text=text.strip(),
            total_tokens=0,  
            model=f"local:{self.model_name}"
        )
