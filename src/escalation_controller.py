"""
escalation_controller.py

Drives a single task through: classify -> pick model sequence -> call ->
validate -> escalate if needed, capped by the category's configured
max_escalations and the global time deadline. This is the module that
ties fireworks_client, tier_policy, and answer_validator together per task.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

from src.answer_validator import validate_tier_a
from src.category_classifier import (
    classify_prompt, 
    MATHEMATICAL_REASONING, 
    LOGICAL_REASONING, 
    CODE_DEBUGGING, 
    CODE_GENERATION,
    FACTUAL_KNOWLEDGE,
    SENTIMENT_CLASSIFICATION,
    NAMED_ENTITY_RECOGNITION,
    TEXT_SUMMARISATION
)
from src.fireworks_client import FireworksClient, FireworksClientError
from src.system_prompts import (
    UNIFIED_SYSTEM_PROMPT, CODE_EXECUTION_PROMPT
)
from src.code_executor import execute_code
from src.task_loader import Task
from src.tier_policy import TierPolicy
from src.uncertainty_signals import needs_tier_b_check

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    task_id: str
    answer: str
    category: str
    tokens_used: int
    attempts: int
    succeeded_validation: bool


def _normalize_code_signature(text: str) -> str:
    """Extract a comparable structural fingerprint from code: function names,
    arg counts, and return statement shapes — ignoring variable names,
    comments, and formatting."""
    _CODE_FENCE_RE_LOCAL = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)
    match = _CODE_FENCE_RE_LOCAL.search(text)
    code = match.group(1) if match else text
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return text.strip()  # fall back to raw text if it doesn't even parse

    signature_parts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            signature_parts.append(f"def:{node.name}:{len(node.args.args)}")
        elif isinstance(node, ast.Return):
            # Compare the *shape* of the return (is it an expr, a call, a binop?)
            signature_parts.append(f"return:{type(node.value).__name__}")
    return "|".join(sorted(signature_parts))


def _extract_logic_conclusion(text: str) -> str:
    """Logic puzzles usually end in a decisive sentence. Compare just the
    last non-empty line, lowercased and stripped of punctuation, rather
    than the full explanation."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return ""
    last = lines[-1].lower()
    return re.sub(r"[^\w\s]", "", last)


async def process_task(
    task: Task,
    client: FireworksClient,
    tier_policy: TierPolicy,
    deadline: float,
) -> TaskResult:
    """
    Process a single task end-to-end. Never raises on model/validation
    failure — always returns a best-effort TaskResult so one bad task
    cannot take down the whole run. Only truly unrecoverable conditions
    (e.g. zero models available) propagate up.
    """
    category = classify_prompt(task.prompt)
    model_sequence = tier_policy.sequence_for_category(category)
    gen_params = tier_policy.generation_params(category)
    
    is_code_exec = category in (MATHEMATICAL_REASONING, LOGICAL_REASONING)
    system_prompt = UNIFIED_SYSTEM_PROMPT

    user_prompt = task.prompt
    if is_code_exec:
        user_prompt += (
            "\n\nWrite a Python script to solve this. Wrap the code in a "
            "```python ... ``` block and print() only the final answer."
        )

    base_model = model_sequence[0]
    escalation_model = model_sequence[1] if len(model_sequence) > 1 else base_model

    last_answer = ""
    total_tokens = 0
    attempts = 0
    succeeded = False

    # ── PASS 1: LOCAL INFERENCE ──────────────────────────────────────────────
    if category in (SENTIMENT_CLASSIFICATION, NAMED_ENTITY_RECOGNITION, TEXT_SUMMARISATION):
        from src.local_model import answer_local
        local_answer = await answer_local(task.prompt, category)
        if local_answer:
            # Wrap in CompletionResult and run validation checks
            from src.fireworks_client import CompletionResult
            mock_result = CompletionResult(
                text=local_answer,
                total_tokens=0,
                model="local_model",
                finish_reason="stop"
            )
            is_valid_local, reason_local = validate_tier_a(mock_result, category, prompt=task.prompt)
            if is_valid_local:
                logger.info("Task %s (%s): answered locally (0 tokens spent).", task.task_id, category)
                return TaskResult(
                    task_id=task.task_id,
                    answer=local_answer,
                    category=category,
                    tokens_used=0,
                    attempts=1,
                    succeeded_validation=True,
                )
            else:
                logger.warning(
                    "Task %s (%s): local answer failed validation: %s. Falling back to API.",
                    task.task_id, category, reason_local
                )
        else:
            logger.debug("Task %s: local model unavailable or failed, falling back to API.", task.task_id)

    # ── PASS 2: API INFERENCE ──────────────────────────────────────────────
    # ATTEMPT 1: Cheapest Fireworks tier
    attempts += 1
    try:
        result1 = await client.complete(
            model=base_model,
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=gen_params["max_tokens"],
            temperature=gen_params["temperature"],
            deadline=deadline,
        )
        total_tokens += result1.total_tokens
        
        has_python_code = "```" in result1.text or is_code_exec
        if is_code_exec and has_python_code and result1.finish_reason != "length":
            success, exec_out = await asyncio.to_thread(execute_code, result1.text)
            if success:
                result1.text = exec_out
                is_valid, reason = validate_tier_a(result1, category, prompt=user_prompt)
            else:
                is_valid, reason = False, exec_out
        else:
            is_valid, reason = validate_tier_a(result1, category, prompt=user_prompt)
            
        last_answer = result1.text
        if not is_valid:
            logger.debug("Task %s Attempt 1 validation failed. Reason: %s", task.task_id, reason)
    except Exception as exc:
        logger.warning("Attempt 1 failed for task %s: %s", task.task_id, exc)
        is_valid = False
        result1 = None

    if is_valid:
        # Tier B: quick uncertainty check — if the answer shows hedging language
        # or is suspiciously terse for a math/logic task, escalate rather than
        # trusting a shaky first-attempt answer.
        if needs_tier_b_check(last_answer, category):
            logger.debug("Task %s: Tier B triggered, escalating for confidence check.", task.task_id)
            is_valid = False
        else:
            succeeded = True

            pass

    if not is_valid:
        current_max_tokens = gen_params["max_tokens"]

        # ATTEMPT 2: Escalate one tier up whenever we still don't have a
        # valid answer — whether that's from Tier B triggering on Attempt 1,
        # or a non-truncation Tier A failure.
        if not is_valid:
            attempts += 1
            current_max_tokens = max(current_max_tokens, gen_params["max_tokens"] * 2)
            if escalation_model == base_model:
                logger.debug("Task %s: no higher tier available, skipping Attempt 3", task.task_id)
            else:
                try:
                    result3 = await client.complete(
                        model=escalation_model,
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        max_tokens=current_max_tokens,
                        temperature=gen_params["temperature"],
                        deadline=deadline,
                    )
                    total_tokens += result3.total_tokens
                    
                    has_python_code = "```" in result3.text or is_code_exec
                    if is_code_exec and has_python_code and result3.finish_reason != "length":
                        success, exec_out = await asyncio.to_thread(execute_code, result3.text)
                        if success:
                            result3.text = exec_out
                            is_valid, reason3 = validate_tier_a(result3, category, prompt=user_prompt)
                        else:
                            is_valid, reason3 = False, exec_out
                    else:
                        is_valid, reason3 = validate_tier_a(result3, category, prompt=user_prompt)
                        
                    last_answer = result3.text
                    if not is_valid:
                        logger.debug("Task %s Attempt 3 validation failed. Reason: %s", task.task_id, reason3)
                except Exception:
                    pass


    if not last_answer.strip():
        last_answer = "Unable to process this request due to temporary API issues."
        logger.error("Task %s: all model calls failed, returning fallback", task.task_id)
    elif category in (CODE_GENERATION, CODE_DEBUGGING):
        # Strip markdown fences for code tasks — only for Python (ast-parseable)
        # Non-Python (JS, Java) answers should keep the fence so the grader can
        # identify the language. extract_python_code falls through to raw text
        # if there's no fence, so a bare function body (no fence) is returned as-is.
        from src.code_executor import extract_python_code
        from src.answer_validator import _detect_language_from_fence
        lang = _detect_language_from_fence(last_answer)
        if lang in ("python", "py", ""):
            last_answer = extract_python_code(last_answer)

    return TaskResult(
        task_id=task.task_id,
        answer=last_answer,
        category=category,
        tokens_used=total_tokens,
        attempts=attempts,
        succeeded_validation=is_valid,
    )
