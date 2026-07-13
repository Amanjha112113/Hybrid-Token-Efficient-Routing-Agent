"""
answer_validator.py

Cheap, rule-based, zero-token validation of model answers. This is what
lets the pipeline avoid a second LLM "verifier" call in the common case:
most failure modes (empty answer, refusal, non-parsing code, missing
sentiment label) are detectable in plain Python.

validate() returns (is_valid, reason) — reason is kept for local
debugging/telemetry only, never written to the submitted output.
"""

from __future__ import annotations

import ast
import re
from typing import Tuple

from src.category_classifier import (
    CODE_DEBUGGING,
    CODE_GENERATION,
    FACTUAL_KNOWLEDGE,
    LOGICAL_REASONING,
    MATHEMATICAL_REASONING,
    NAMED_ENTITY_RECOGNITION,
    SENTIMENT_CLASSIFICATION,
    TEXT_SUMMARISATION,
)

from src.fireworks_client import CompletionResult

_REFUSAL_RE = re.compile(
    r"\b(i cannot|i can't|as an ai|i am unable|i do not have access|"
    r"i don't have access|sorry, i can)\b",
    re.IGNORECASE,
)
_HARD_REFUSAL_RE = re.compile(
    r"\b(i cannot assist|i can't assist|as an ai (language model|assistant)|"
    r"i am unable to help|i don't have access to|sorry, i can(?:'t| not) help)\b",
    re.IGNORECASE,
)
_NARRATION_LEAK_RE = re.compile(
    r"\b(we are asked|the user (is asking|wants)|let me (think|verify|check)|"
    r"i (need to|should|'ll go with|'ll provide)|the (instruction|prompt) says|"
    r"^wait,|thus\s*$|so,? i (should|'ll))\b",
    re.IGNORECASE,
)
_CODE_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_PYTHON_FENCE_RE = re.compile(r"```(?:python|py)?\n(.*?)```", re.DOTALL)
# Detects prompts that explicitly ask for a non-Python language
_NON_PYTHON_LANG_RE = re.compile(
    r"\b(javascript|typescript|java(?!script)|ruby|go(lang)?|c\+\+|c#|kotlin|swift|rust|bash|shell)\b",
    re.IGNORECASE,
)


def validate_tier_a(result: CompletionResult, category: str, prompt: str = "") -> Tuple[bool, str]:
    """
    Tier A - Hard reject logic. Near zero-cost, deterministic.
    Returns (is_valid, reason). is_valid=False triggers Attempt 2/3.
    """
    if result is None or not result.text.strip():
        return False, "empty answer"

    if result.finish_reason == "length":
        return False, "truncated due to max_tokens (length)"

    if _NARRATION_LEAK_RE.search(result.text):
        return False, "answer leaks internal reasoning narration"

    refusal_pattern = _HARD_REFUSAL_RE if category == LOGICAL_REASONING else _REFUSAL_RE
    if refusal_pattern.search(result.text):
        return False, "answer looks like a refusal"

    if category in (CODE_DEBUGGING, CODE_GENERATION):
        return _validate_code(result.text, prompt=prompt)


    # All other categories: if it has content, didn't truncate, and isn't a refusal,
    # it passes Tier A. (Tier B self-consistency is handled in the controller).
    return True, "passed Tier A"


def _extract_code_block(answer: str) -> str:
    match = _PYTHON_FENCE_RE.search(answer)
    return match.group(1) if match else answer


def _detect_language_from_fence(answer: str) -> str:
    """Returns the lowercased language tag from the first code fence, or 'python' if absent."""
    match = _CODE_FENCE_RE.search(answer)
    if match and match.group(1):
        return match.group(1).lower()
    return "python"


def _validate_non_python_code(answer: str) -> Tuple[bool, str]:
    """Structural check for non-Python code — no AST, just presence of function-shaped body."""
    text = answer.strip()
    if not text:
        return False, "empty answer"
    # Must have a code fence
    if not _CODE_FENCE_RE.search(text):
        return False, "non-Python code answer missing code fence"
    # Must contain something function-shaped (keyword + name + parens / braces)
    if re.search(r"\b(function|def|class|=>|\{[\s\S]*\})", text):
        return True, "non-Python code has function-shaped structure"
    # Or at minimum a multi-line code block (not just a one-liner comment)
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        inner = fence_match.group(2).strip()
        if len(inner.splitlines()) >= 2:
            return True, "non-Python code block has multiple lines"
    return False, "non-Python code answer has no recognizable structure"


def _validate_code(answer: str, prompt: str = "") -> Tuple[bool, str]:
    """Language-aware code validation. Python uses ast.parse; others use structural checks."""
    lang = _detect_language_from_fence(answer)
    is_python = lang in ("python", "py", "")
    
    # Also check the prompt itself for explicit non-Python language requests
    if not is_python or _NON_PYTHON_LANG_RE.search(prompt):
        return _validate_non_python_code(answer)

    # Python path: try ast.parse
    code = _extract_code_block(answer)
    try:
        ast.parse(code)
        return True, "code parses"
    except SyntaxError:
        pass

    # The extracted block may include surrounding prose.
    # Retry using only lines that look code-like.
    code_like_lines = [
        line for line in code.splitlines()
        if re.match(r"^(\s+|def\s|class\s|import\s|from\s|if\s|for\s|while\s|try\s*:?|except\s|finally\s*:?|with\s|#|@|\w+\s*=|\w+\()", line)
        or line.strip() == ""
    ]

    # If there's no code fence AND it doesn't parse as python code, reject.
    if not _PYTHON_FENCE_RE.search(answer):
        if not code_like_lines:
            return False, "no code fence and no parseable python code found"

    if code_like_lines:
        try:
            ast.parse("\n".join(code_like_lines))
            return True, "code parses after stripping surrounding prose"
        except SyntaxError:
            pass

    return False, "code does not parse even after stripping surrounding prose"
