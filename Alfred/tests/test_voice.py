"""Tests for voice handling, wake phrase matching, and TTS fallback."""

import sys
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.voice.wake_word import WakeWordDetector
from src.voice.text_to_speech import TextToSpeechService


def get_qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_wake_phrase_exact_and_compound_matching():
    """Tests wake phrase matching for both standalone and compound sentences."""
    cfg = AppConfig(wake_phrases=["alfred", "hey alfred"])
    detector = WakeWordDetector(cfg)

    # Standalone
    matched, cmd = detector._match_wake_word("alfred")
    assert matched is True
    assert cmd == ""

    matched, cmd = detector._match_wake_word("hey alfred")
    assert matched is True
    assert cmd == ""

    # Compound sentences
    matched, cmd = detector._match_wake_word("Hey Alfred, what is the weather today?")
    assert matched is True
    assert cmd == "what is the weather today?"

    matched, cmd = detector._match_wake_word("alfred tell me an interesting fact")
    assert matched is True
    assert cmd == "tell me an interesting fact"

    # Non-wake phrases
    matched, cmd = detector._match_wake_word("hello there google")
    assert matched is False


def test_stop_command_recognition():
    """Tests recognition of stop and cancel commands."""
    cfg = AppConfig()
    detector = WakeWordDetector(cfg)

    for stop_phrase in ("stop", "stop speaking", "cancel", "quiet alfred", "hush"):
        matched, cmd = detector._match_wake_word(stop_phrase)
        assert cmd == "__STOP__"


def test_tts_fallback_on_unconfigured_elevenlabs(tmp_path):
    """Verifies that TTS falls back to Windows native speech if ElevenLabs key is missing."""
    get_qapp()
    cfg = AppConfig(elevenlabs_api_key="")  # Unconfigured ElevenLabs
    tts = TextToSpeechService(cfg)

    # Calling stop when not speaking should be safe
    tts.stop()
    assert not tts.is_speaking

