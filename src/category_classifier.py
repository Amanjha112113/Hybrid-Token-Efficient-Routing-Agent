import re

FACTUAL_KNOWLEDGE = "factual_knowledge"
MATHEMATICAL_REASONING = "mathematical_reasoning"
SENTIMENT_CLASSIFICATION = "sentiment_classification"
TEXT_SUMMARISATION = "text_summarisation"
NAMED_ENTITY_RECOGNITION = "named_entity_recognition"
CODE_DEBUGGING = "code_debugging"
LOGICAL_REASONING = "logical_reasoning"
CODE_GENERATION = "code_generation"

ALL_CATEGORIES = [
    FACTUAL_KNOWLEDGE, MATHEMATICAL_REASONING, SENTIMENT_CLASSIFICATION,
    TEXT_SUMMARISATION, NAMED_ENTITY_RECOGNITION, CODE_DEBUGGING,
    LOGICAL_REASONING, CODE_GENERATION,
]

_CODE_FENCE_RE = re.compile(r"```")
_BUG_WORDS_RE = re.compile(
    r"\b(bug|error|fix|debug|incorrect|not working|fails?|traceback|exception|wrong output|doesn't work)\b",
    re.IGNORECASE,
)

_CODE_GEN_RE = re.compile(
    r"\b(write a function|implement a function|write a program|"
    r"create a function|develop a function|create a script|develop a module|"
    r"write a class|implement the following|"
    r"(write|create|implement|develop)\s+(\w+\s+){0,3}(code|function|program|script|class|module)\b)",
    re.IGNORECASE,
)

_SUMMARY_RE = re.compile(
    r"\b(summari[sz]e|summary|condense|tl;dr|shorten|in one sentence|in a few words)\b",
    re.IGNORECASE,
)

_NER_RE = re.compile(
    r"\b(extract (the )?entities|named entit(y|ies)|extract (all )?names|"
    r"find the persons|"
    r"(identify|list|find|extract) (all )?(the )?(people|persons|organi[sz]ations|"
    r"locations|companies|dates)\b.*\b(mentioned|in|from)|"
    r"who (are the )?(people|persons|organi[sz]ations) (mentioned|involved))\b",
    re.IGNORECASE,
)

_SENTIMENT_RE = re.compile(
    r"\b(sentiment|classify\s+(the\s+)?(sentiment|opinion|tone|emotion)|"
    r"positive or negative|positive, negative,? or neutral|"
    r"emotional tone|"
    r"is this (review|comment|feedback|text) (positive|negative|neutral)|"
    r"opinion (expressed|conveyed)|overall tone)\b",
    re.IGNORECASE,
)

_MATH_RE = re.compile(
    r"(?:\b(?:calculate|percent(?:age)?|how many|how much|total cost|sum of|"
    r"average of|difference between|projection|compound interest|"
    r"final price|final cost|final total|final amount|"
    r"what is the (?:price|cost|total|value|amount)|"
    r"how much (?:will|does|would)|round (up|down|to)|"
    r"solve for|equation|how long (?:would|does|will) it take|"
    r"prime factor|factori[sz]ation|remainder|modulo|gcd|lcm|"
    r"probability|ratio|fraction|algebra|geometry)\b)|"
    r"\b\d+\s*%|"
    r"\b\d+[a-z]?\s*[+\-*/=]\s*\d+\b",
    re.IGNORECASE,
)

_LOGIC_RE = re.compile(
    r"\b(puzzle|riddle|constraint|deduce|deduction|all of the following (must|are)|"
    r"who (owns|lives|sits)|"
    r"which (one|person|house|team)|satisf(y|ies) (all|the) conditions?|"
    r"what order|order (of|in which)|must be true|"
    r"(winner|win|won|finish(es|ed)?|place[sd]?|rank(s|ed)?) (?:of(?: the)?|the|a|this) (race|competition)|"
    r"who (is the )?winner|"
    r"(race|competition) (puzzle|between|among))\b",
    re.IGNORECASE,
)


def classify_prompt(prompt: str) -> str:
    text = prompt.strip()
    has_code_fence = bool(_CODE_FENCE_RE.search(text))
    has_bug_words = bool(_BUG_WORDS_RE.search(text))
    looks_like_code = _looks_like_code(text)

    # 1. Code debugging: bug words + code present
    if has_bug_words and (has_code_fence or looks_like_code):
        return CODE_DEBUGGING

    # 2. Code generation: explicit request to write/create code
    if _CODE_GEN_RE.search(text):
        return CODE_GENERATION

    # 3. Text summarisation
    if _SUMMARY_RE.search(text):
        return TEXT_SUMMARISATION

    # 4. Named entity recognition
    if _NER_RE.search(text):
        return NAMED_ENTITY_RECOGNITION

    # 5. Sentiment classification
    if _SENTIMENT_RE.search(text):
        return SENTIMENT_CLASSIFICATION

    # 6. Logical reasoning (before math, since puzzles can contain numbers)
    if _LOGIC_RE.search(text):
        return LOGICAL_REASONING

    # 7. Mathematical reasoning
    if _MATH_RE.search(text):
        return MATHEMATICAL_REASONING

    # 8. Fallback to factual
    return FACTUAL_KNOWLEDGE


def _looks_like_code(text: str) -> bool:
    """Heuristic for code not wrapped in triple backticks.
    Works for both multi-line blocks and single-line inline code."""
    code_signal_re = re.compile(
        r"(\bdef \w+\(|\bfunction \w+\(|\bclass \w+\s*[:({]|;\s*$|=>|\breturn\b)",
        re.MULTILINE,
    )
    lines = text.splitlines()
    code_like_lines = sum(1 for line in lines if code_signal_re.search(line))

    # Multi-line code: at least one code line in a multi-line snippet
    if code_like_lines >= 1 and len(lines) >= 2:
        return True

    # Single-line inline code: require at least two distinct code signals
    # to avoid false positives on prose that happens to contain "return".
    if len(lines) == 1:
        signal_count = len(code_signal_re.findall(text))
        return signal_count >= 2

    return False
