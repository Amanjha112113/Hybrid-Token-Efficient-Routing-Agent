"""
uncertainty_signals.py

Zero-cost heuristics for deciding whether a Tier-A-valid answer is
worth double-checking with a Tier B self-consistency call, or whether
it's confident enough to trust as-is.

This exists because unconditional Tier B (calling every math/logic/code
task twice) was found to fire on ~100% of those tasks in practice,
turning a "catch genuine disagreement" safety net into a fixed 2x-3x
token tax on 4 of 8 categories regardless of whether the first answer
was actually shaky. These heuristics let us skip the second call when
the first answer shows no signs of uncertainty.
"""

from __future__ import annotations

import re

_HEDGE_RE = re.compile(
    r"\b(might|maybe|possibly|perhaps|not (entirely )?sure|i think|"
    r"it('s| is) (unclear|ambiguous|hard to (say|tell))|"
    r"could be|approximat(e|ely)|roughly|around \d|"
    r"cannot be (fully )?determined|insufficient (information|data)|"
    r"one (possible|potential) (answer|solution)|"
    r"there (may|might) be (multiple|several))\b",
    re.IGNORECASE,
)

# With code execution enabled, math and logic answers are now the literal STDOUT
# of a python script (e.g., just "42"). A 1-word answer is no longer suspicious,
# it is exactly what we expect. We rely on the hedge regex to catch uncertainty
# in the text/fallback path.


def needs_tier_b_check(answer_text: str, category: str) -> bool:
    """
    Return True if this Tier-A-valid answer shows a real signal of
    uncertainty and is worth double-checking with a second generation.
    Return False to trust attempt 1 and skip the extra call entirely.
    """
    text = answer_text.strip()

    # Signal 1: hedging / uncertainty language anywhere in the answer.
    if _HEDGE_RE.search(text):
        return True



    # No uncertainty signal found — trust attempt 1, skip Tier B.
    return False
