"""Tests for AppConfig loading and validation."""

import os
from pathlib import Path
from src.config import AppConfig


def test_default_config():
    """Tests default configuration settings."""
    cfg = AppConfig()
    assert cfg.alfred_name == "Alfred"
    assert "alfred" in cfg.wake_phrases
    assert "hey alfred" in cfg.wake_phrases
    assert cfg.default_image == "v smoking.png"
    assert cfg.daily_briefing_time == "08:30"
    assert cfg.timezone == "Asia/Kolkata"
    assert cfg.window_size == 160


def test_missing_keys_graceful():
    """Missing API keys should not crash and should report False."""
    cfg = AppConfig(gemini_api_key="", elevenlabs_api_key="")
    assert not cfg.has_gemini()
    assert not cfg.has_elevenlabs()


def test_placeholder_keys_not_valid():
    """Placeholder keys starting with 'your_' should be treated as unconfigured."""
    cfg = AppConfig(
        gemini_api_key="your_actual_gemini_key",
        elevenlabs_api_key="your_actual_elevenlabs_key",
    )
    assert not cfg.has_gemini()
    assert not cfg.has_elevenlabs()


def test_valid_keys_reported():
    """Properly populated keys should report True."""
    cfg = AppConfig(
        gemini_api_key="AIzaSyTestValidGeminiKey123",
        elevenlabs_api_key="sk_elevenlabs_valid_key_456",
    )
    assert cfg.has_gemini()
    assert cfg.has_elevenlabs()


def test_custom_wake_phrases_parsing(tmp_path):
    """Custom wake phrases in env file should be parsed to lowercase list."""
    env_file = tmp_path / ".env.test"
    env_file.write_text("ALFRED_WAKE_PHRASES=Jarvis, Hey Jarvis, Alfred\n", encoding="utf-8")

    cfg = AppConfig.load(env_path=env_file)
    assert cfg.wake_phrases == ["jarvis", "hey jarvis", "alfred"]


def test_database_path_resolution(tmp_path):
    """Relative database path should resolve correctly against project root."""
    cfg = AppConfig(database_path="data/test.db")
    full_path = cfg.full_database_path
    assert full_path.is_absolute()
    assert full_path.name == "test.db"

