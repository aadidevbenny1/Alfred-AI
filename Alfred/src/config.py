"""Configuration management for Alfred.

Loads environment variables from .env in the project root with strong defaults
and graceful validation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "t")


@dataclass
class AppConfig:
    """Application configuration for Alfred desktop assistant."""

    # Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    # Financial News
    financial_news_provider: str = "rss"
    financial_news_api_key: str = ""
    financial_news_base_url: str = ""

    # Alfred Application
    alfred_name: str = "Alfred"
    wake_phrases: list[str] = field(default_factory=lambda: ["alfred", "hey alfred"])
    default_image: str = "v smoking.png"

    # Voice settings
    voice_enabled: bool = True
    microphone_enabled: bool = True
    silence_timeout: float = 1.2

    # Daily briefing
    daily_briefing_enabled: bool = True
    daily_briefing_time: str = "08:30"
    timezone: str = "Asia/Kolkata"

    # Application storage & paths
    database_path: str = "data/alfred.db"
    log_level: str = "INFO"
    window_size: int = 160
    min_image_duration: float = 1.5

    # Base Paths
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    assets_dir: Path = field(default_factory=Path)
    data_dir: Path = field(default_factory=Path)

    def __post_init__(self):
        if not self.assets_dir or str(self.assets_dir) == ".":
            self.assets_dir = self.project_root / "assets"
        if not self.data_dir or str(self.data_dir) == ".":
            self.data_dir = self.project_root / "data"

    @classmethod
    def load(cls, env_path: str | Path | None = None) -> AppConfig:
        """Loads configuration from .env file or environment variables."""
        root = Path(__file__).resolve().parent.parent
        if env_path is None:
            env_file = root / ".env"
        else:
            env_file = Path(env_path)

        if env_file.exists():
            load_dotenv(dotenv_path=env_file, override=True)

        raw_wake = os.getenv("ALFRED_WAKE_PHRASES", "alfred,hey alfred")
        wake_list = [p.strip().lower() for p in raw_wake.split(",") if p.strip()]
        if not wake_list:
            wake_list = ["alfred", "hey alfred"]

        cfg = cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", "").strip(),
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB").strip(),
            elevenlabs_model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip(),
            financial_news_provider=os.getenv("FINANCIAL_NEWS_PROVIDER", "rss").strip().lower(),
            financial_news_api_key=os.getenv("FINANCIAL_NEWS_API_KEY", "").strip(),
            financial_news_base_url=os.getenv("FINANCIAL_NEWS_BASE_URL", "").strip(),
            alfred_name=os.getenv("ALFRED_NAME", "Alfred").strip(),
            wake_phrases=wake_list,
            default_image=os.getenv("ALFRED_DEFAULT_IMAGE", "v smoking.png").strip(),
            voice_enabled=_to_bool(os.getenv("ALFRED_VOICE_ENABLED"), default=True),
            microphone_enabled=_to_bool(os.getenv("ALFRED_MICROPHONE_ENABLED"), default=True),
            silence_timeout=float(os.getenv("ALFRED_SILENCE_TIMEOUT", "1.2")),
            daily_briefing_enabled=_to_bool(os.getenv("ALFRED_DAILY_BRIEFING_ENABLED"), default=True),
            daily_briefing_time=os.getenv("ALFRED_DAILY_BRIEFING_TIME", "08:30").strip(),
            timezone=os.getenv("ALFRED_TIMEZONE", "Asia/Kolkata").strip(),
            database_path=os.getenv("ALFRED_DATABASE_PATH", "data/alfred.db").strip(),
            log_level=os.getenv("ALFRED_LOG_LEVEL", "INFO").strip().upper(),
            project_root=root,
            assets_dir=root / "assets",
            data_dir=root / "data",
        )
        return cfg

    @property
    def full_database_path(self) -> Path:
        """Returns the absolute resolved path to the sqlite database."""
        db_p = Path(self.database_path)
        if db_p.is_absolute():
            return db_p
        return self.project_root / db_p

    def has_gemini(self) -> bool:
        """Checks if Gemini API key is configured."""
        return bool(self.gemini_api_key and not self.gemini_api_key.startswith("your_"))

    def has_elevenlabs(self) -> bool:
        """Checks if ElevenLabs API key is configured."""
        return bool(self.elevenlabs_api_key and not self.elevenlabs_api_key.startswith("your_"))

    def has_financial_news(self) -> bool:
        """Checks if financial news is available."""
        if self.financial_news_provider in ("rss", "free", "yahoo"):
            return True
        return bool(self.financial_news_api_key and not self.financial_news_api_key.startswith("your_"))

