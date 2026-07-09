"""
category_classifier.py

Deterministic, rule-based classification of a prompt into one of the
8 required capability categories. This is the "routing brain" and it
costs zero tokens and sub-millisecond latency — no LLM call is ever
used for this decision, by design.

Order of checks matters: more specific / structurally distinctive
categories are checked before falling back to broader ones. A prompt
that mentions both "function" and "bug" should land in code_debugging,
not code_generation, for example — so debugging cues are checked first.
"""

from __future__ import annotations

import re

# Canonical category names used throughout the pipeline.
FACTUAL_KNOWLEDGE = "factual_knowledge"
MATHEMATICAL_REASONING = "mathematical_reasoning"
SENTIMENT_CLASSIFICATION = "sentiment_classification"
TEXT_SUMMARISATION = "text_summarisation"
NAMED_ENTITY_RECOGNITION = "named_entity_recognition"
CODE_DEBUGGING = "code_debugging"
LOGICAL_REASONING = "logical_reasoning"
CODE_GENERATION = "code_generation"

ALL_CATEGORIES = [
    FACTUAL_KNOWLEDGE,
    MATHEMATICAL_REASONING,
    SENTIMENT_CLASSIFICATION,
    TEXT_SUMMARISATION,
    NAMED_ENTITY_RECOGNITION,
    CODE_DEBUGGING,
    LOGICAL_REASONING,
    CODE_GENERATION,
]

_CODE_FENCE_RE = re.compile(r"```")
_BUG_WORDS_RE = re.compile(
    r"\b(bug|error|fix|debug|incorrect|not working|fails?|traceback|exception|wrong output)\b",
    re.IGNORECASE,
)
_CODE_GEN_RE = re.compile(
    r"\b(write a function|implement a function|write code|write a program|"
    r"implement the following|create a function|develop a function)\b",
    re.IGNORECASE,
)
_SUMMARY_RE = re.compile(
    r"\b(summari[sz]e|summary|condense|tl;dr|shorten)\b", re.IGNORECASE
)
_NER_RE = re.compile(
    r"\b(extract (the )?entities|named entit(y|ies)|identify (all )?(the )?"
    r"(people|persons|organi[sz]ations|locations|dates) in)\b",
    re.IGNORECASE,
)
_SENTIMENT_RE = re.compile(
    r"\b(sentiment|positive or negative|classify.*(opinion|tone|emotion))\b",
    re.IGNORECASE,
)
_MATH_RE = re.compile(
    r"\b(calculate|percent(age)?|how many|how much|total cost|sum of|"
    r"average of|difference between|projection|compound interest|"
    r"\d+\s*[+\-*/]\s*\d+)\b",
    re.IGNORECASE,
)
_LOGIC_RE = re.compile(
    r"\b(puzzle|constraint|deduce|deduction|all of the following (must|are)|"
    r"who (is|owns|lives)|which (one|person|house)|satisf(y|ies) (all|the) conditions?)\b",
    re.IGNORECASE,
)


def classify_prompt(prompt: str) -> str:
    """
    Classify a prompt into one of ALL_CATEGORIES.

    Falls back to FACTUAL_KNOWLEDGE when no stronger signal is found,
    since "explain/define/how does X work" style prompts are the
    least structurally distinctive and factual explanation is a safe
    default for open-ended natural language questions.
    """
    text = prompt.strip()
    has_code_fence = bool(_CODE_FENCE_RE.search(text))
    has_bug_words = bool(_BUG_WORDS_RE.search(text))

    # 1. Code debugging: code present (fenced or clearly code-like) AND bug language.
    if has_bug_words and (has_code_fence or _looks_like_code(text)):
        return CODE_DEBUGGING

    # 2. Code generation: explicit "write/implement a function" style ask.
    if _CODE_GEN_RE.search(text):
        return CODE_GENERATION

    # 3. Text summarisation.
    if _SUMMARY_RE.search(text):
        return TEXT_SUMMARISATION

    # 4. Named entity recognition.
    if _NER_RE.search(text):
        return NAMED_ENTITY_RECOGNITION

    # 5. Sentiment classification.
    if _SENTIMENT_RE.search(text):
        return SENTIMENT_CLASSIFICATION

    # 6. Logical / deductive reasoning (checked before math since puzzles
    #    often contain numbers too, but the puzzle language is the
    #    stronger signal).
    if _LOGIC_RE.search(text):
        return LOGICAL_REASONING

    # 7. Mathematical reasoning.
    if _MATH_RE.search(text):
        return MATHEMATICAL_REASONING

    # 8. Fallback: general factual knowledge.
    return FACTUAL_KNOWLEDGE


def _looks_like_code(text: str) -> bool:
    """Heuristic fallback for code that wasn't wrapped in a fenced block."""
    code_signal_re = re.compile(
        r"(\bdef \w+\(|\bfunction \w+\(|\bclass \w+\s*[:({]|;\s*$|=>|\breturn\b)",
        re.MULTILINE,
    )
    lines = text.splitlines()
    code_like_lines = sum(1 for line in lines if code_signal_re.search(line))
    return code_like_lines >= 1 and len(lines) >= 2
