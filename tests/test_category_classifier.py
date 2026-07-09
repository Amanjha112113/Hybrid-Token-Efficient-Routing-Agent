import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.category_classifier import (
    CODE_DEBUGGING,
    CODE_GENERATION,
    FACTUAL_KNOWLEDGE,
    LOGICAL_REASONING,
    MATHEMATICAL_REASONING,
    NAMED_ENTITY_RECOGNITION,
    SENTIMENT_CLASSIFICATION,
    TEXT_SUMMARISATION,
    classify_prompt,
)


def test_code_debugging():
    prompt = "This function has a bug:\n```python\ndef add(a, b):\n    return a - b\n```\nFix it."
    assert classify_prompt(prompt) == CODE_DEBUGGING


def test_code_generation():
    prompt = "Write a function that returns the nth Fibonacci number."
    assert classify_prompt(prompt) == CODE_GENERATION


def test_summarisation():
    prompt = "Summarise the following text in one sentence: The quick brown fox..."
    assert classify_prompt(prompt) == TEXT_SUMMARISATION


def test_ner():
    prompt = "Extract the entities (person, organization, location) from this text: Tim Cook leads Apple in Cupertino."
    assert classify_prompt(prompt) == NAMED_ENTITY_RECOGNITION


def test_sentiment():
    prompt = "Classify the sentiment of this review as positive or negative and justify it."
    assert classify_prompt(prompt) == SENTIMENT_CLASSIFICATION


def test_logic():
    prompt = "Solve this puzzle: all of the following must be true. Alice is not next to Bob..."
    assert classify_prompt(prompt) == LOGICAL_REASONING


def test_math():
    prompt = "If a shirt costs $40 and is discounted by 25%, calculate the final price."
    assert classify_prompt(prompt) == MATHEMATICAL_REASONING


def test_factual_default():
    prompt = "Explain how photosynthesis works."
    assert classify_prompt(prompt) == FACTUAL_KNOWLEDGE


if __name__ == "__main__":
    test_code_debugging()
    test_code_generation()
    test_summarisation()
    test_ner()
    test_sentiment()
    test_logic()
    test_math()
    test_factual_default()
    print("All category_classifier tests passed.")
