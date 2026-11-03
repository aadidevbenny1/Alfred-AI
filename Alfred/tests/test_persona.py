"""Tests for Alfred butler persona, greetings, and text cleaners."""

from src.ai.persona import (
    ALFRED_SYSTEM_PROMPT,
    get_varied_greeting,
    get_varied_acknowledgement,
    get_varied_apology,
    get_varied_stop,
    detect_intent_hint,
)
from src.ai.gemini_client import GeminiClient
from src.config import AppConfig


def test_system_prompt_requirements():
    """Validates that system prompt emphasizes concise butler style and truthfulness."""
    prompt = ALFRED_SYSTEM_PROMPT
    assert "Sir" in prompt
    assert "concise" in prompt.lower() or "1 to 3 sentences" in prompt
    assert "never fabricate" in prompt.lower()
    assert "markdown" in prompt.lower() or "asterisks" in prompt.lower()


def test_varied_responses():
    """Ensures responses are varied non-empty strings."""
    greetings = {get_varied_greeting() for _ in range(20)}
    assert len(greetings) > 1

    acks = {get_varied_acknowledgement() for _ in range(20)}
    assert len(acks) > 1


def test_intent_detection():
    """Verifies intent hint classification for fair image balancing."""
    assert detect_intent_hint("congratulations on the achievement", "Thank you, Sir.") == "cheers"
    assert detect_intent_hint("what is 2+2", "My apologies, Sir, I encountered an error.") == "error"
    assert detect_intent_hint("good morning alfred", "Good morning, Sir.") == "greeting"
    assert detect_intent_hint("did you finish that task", "Task completed, Sir.") == "success"


def test_speech_cleaner():
    """Verifies markdown asterisks and citations are stripped for TTS."""
    client = GeminiClient(AppConfig())
    raw = "**Good evening**, Sir! The *markets* are up [1] by 2.5%.\n\nHere is `#1` priority."
    cleaned = client.clean_for_speech(raw)

    assert "**" not in cleaned
    assert "*" not in cleaned
    assert "[1]" not in cleaned
    assert "#" not in cleaned
    assert "Good evening, Sir! The markets are up by 2.5%. Here is 1 priority." == cleaned

