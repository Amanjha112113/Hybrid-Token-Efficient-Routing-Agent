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

_REFUSAL_RE = re.compile(
    r"\b(i cannot|i can't|as an ai|i am unable|i do not have access|"
    r"i don't have access|sorry, i can)\b",
    re.IGNORECASE,
)
_SENTIMENT_LABELS_RE = re.compile(r"\b(positive|negative|neutral|mixed)\b", re.IGNORECASE)
_HEDGE_MATH_RE = re.compile(
    r"\b(cannot determine|not enough information|unclear|impossible to calculate)\b",
    re.IGNORECASE,
)
_CODE_FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def validate(answer: str, category: str) -> Tuple[bool, str]:
    """Return (is_valid, reason). is_valid=False triggers escalation."""
    if answer is None or not answer.strip():
        return False, "empty answer"

    if _REFUSAL_RE.search(answer) and category != LOGICAL_REASONING:
        return False, "answer looks like a refusal"

    if category in (CODE_DEBUGGING, CODE_GENERATION):
        return _validate_code(answer)

    if category == MATHEMATICAL_REASONING:
        return _validate_math(answer)

    if category == SENTIMENT_CLASSIFICATION:
        return _validate_sentiment(answer)

    if category == TEXT_SUMMARISATION:
        return _validate_summary(answer)

    if category == NAMED_ENTITY_RECOGNITION:
        return _validate_ner(answer)

    if category == LOGICAL_REASONING:
        return _validate_logic(answer)

    if category == FACTUAL_KNOWLEDGE:
        return _validate_factual(answer)

    # Unknown category — fall back to a minimal non-empty check.
    return True, "no specific validator for category, accepted by default"


def _extract_code_block(answer: str) -> str:
    match = _CODE_FENCE_RE.search(answer)
    return match.group(1) if match else answer


def _validate_code(answer: str) -> Tuple[bool, str]:
    code = _extract_code_block(answer)
    try:
        ast.parse(code)
        return True, "code parses"
    except SyntaxError:
        pass

    # The extracted block may include surrounding prose (e.g. "Here is the
    # fix:" before the code). Retry using only lines that look code-like,
    # since prose lines are what most often break ast.parse on an
    # otherwise-correct snippet.
    code_like_lines = [
        line for line in code.splitlines()
        if re.match(r"^\s*(def |class |return |if |for |while |import |from |#|@|\w+\s*=)", line)
        or line.strip() == ""
    ]
    if code_like_lines:
        try:
            ast.parse("\n".join(code_like_lines))
            return True, "code parses after stripping surrounding prose"
        except SyntaxError:
            pass

    return False, "code does not parse even after stripping surrounding prose"


def _validate_math(answer: str) -> Tuple[bool, str]:
    if _HEDGE_MATH_RE.search(answer):
        return False, "hedged / non-committal math answer"
    if not _NUMBER_RE.search(answer):
        return False, "no numeric value found in math answer"
    return True, "contains a numeric answer"


def _validate_sentiment(answer: str) -> Tuple[bool, str]:
    if not _SENTIMENT_LABELS_RE.search(answer):
        return False, "no recognizable sentiment label found"
    return True, "sentiment label present"


def _validate_summary(answer: str) -> Tuple[bool, str]:
    word_count = len(answer.split())
    if word_count < 2:
        return False, "summary too short to be meaningful"
    return True, "summary has content"


def _validate_ner(answer: str) -> Tuple[bool, str]:
    # Loose check: expect at least one capitalized token (likely an entity)
    # or a structured list/JSON-like format.
    has_capitalized_token = bool(re.search(r"\b[A-Z][a-zA-Z]+\b", answer))
    has_structure = bool(re.search(r"[:\-\u2022]|\{|\[", answer))
    if has_capitalized_token or has_structure:
        return True, "entity-like tokens or structure present"
    return False, "no entity-like tokens found"


def _validate_logic(answer: str) -> Tuple[bool, str]:
    word_count = len(answer.split())
    if word_count < 2:
        return False, "logic answer too short"
    if re.search(r"\bi don't know\b|\bunable to determine\b", answer, re.IGNORECASE):
        return False, "logic puzzle left unresolved"
    return True, "logic answer present"


def _validate_factual(answer: str) -> Tuple[bool, str]:
    word_count = len(answer.split())
    if word_count < 3:
        return False, "factual answer too short"
    return True, "factual answer has content"
