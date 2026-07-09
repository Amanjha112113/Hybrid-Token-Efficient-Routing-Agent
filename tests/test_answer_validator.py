import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.answer_validator import validate
from src.category_classifier import (
    CODE_DEBUGGING,
    CODE_GENERATION,
    FACTUAL_KNOWLEDGE,
    MATHEMATICAL_REASONING,
    SENTIMENT_CLASSIFICATION,
)


def test_valid_code():
    answer = "```python\ndef add(a, b):\n    return a + b\n```"
    ok, _ = validate(answer, CODE_DEBUGGING)
    assert ok is True


def test_invalid_code_syntax_error():
    answer = "```python\ndef add(a, b)\n    return a + b\n```"
    ok, _ = validate(answer, CODE_GENERATION)
    assert ok is False


def test_empty_answer_rejected():
    ok, _ = validate("", FACTUAL_KNOWLEDGE)
    assert ok is False


def test_math_with_number_accepted():
    ok, _ = validate("The final price is $30.", MATHEMATICAL_REASONING)
    assert ok is True


def test_math_hedge_rejected():
    ok, _ = validate("There is not enough information to determine this.", MATHEMATICAL_REASONING)
    assert ok is False


def test_sentiment_label_accepted():
    ok, _ = validate("This review is Positive because it praises the product.", SENTIMENT_CLASSIFICATION)
    assert ok is True


def test_sentiment_missing_label_rejected():
    ok, _ = validate("This review has a nice tone overall.", SENTIMENT_CLASSIFICATION)
    assert ok is False


def test_refusal_rejected():
    ok, _ = validate("I cannot answer that question.", FACTUAL_KNOWLEDGE)
    assert ok is False


if __name__ == "__main__":
    test_valid_code()
    test_invalid_code_syntax_error()
    test_empty_answer_rejected()
    test_math_with_number_accepted()
    test_math_hedge_rejected()
    test_sentiment_label_accepted()
    test_sentiment_missing_label_rejected()
    test_refusal_rejected()
    print("All answer_validator tests passed.")
