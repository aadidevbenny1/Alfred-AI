"""Main entry point for Alfred - Windows 11 Personal AI Desktop Assistant.

Initializes configuration, logging, Qt Application, and launches the single
floating character window.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# High-DPI and screen scaling for Windows 11 displays
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from src.config import AppConfig
from src.utils.logging_config import setup_logging
from src.app import AlfredApp


def main() -> int:
    """Launches the Alfred desktop assistant."""
    # 1. Load Configuration
    config = AppConfig.load()

    # 2. Setup Logging
    log_file = config.data_dir / "alfred.log"
    logger = setup_logging(level_name=config.log_level, log_file=str(log_file))
    logger.info("=" * 60)
    logger.info("Initializing Alfred Personal AI Desktop Assistant v1.0.0")
    logger.info("Project Root: %s", config.project_root)
    logger.info("Configured Wake Phrases: %s", config.wake_phrases)
    logger.info("Gemini Model: %s (Configured: %s)", config.gemini_model, config.has_gemini())
    logger.info("ElevenLabs Voice: %s (Configured: %s)", config.elevenlabs_voice_id, config.has_elevenlabs())
    logger.info("Financial News: %s (Configured: %s)", config.financial_news_provider, config.has_financial_news())
    logger.info("Daily Briefing: %s at %s (%s)", config.daily_briefing_enabled, config.daily_briefing_time, config.timezone)
    logger.info("=" * 60)

    # 3. Create Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("Alfred")
    app.setOrganizationName("AlfredAI")
    app.setQuitOnLastWindowClosed(False)  # Remains active in system tray

    # App icon from default smoking character
    default_img_path = config.assets_dir / config.default_image
    if default_img_path.exists():
        app.setWindowIcon(QIcon(str(default_img_path)))

    # 4. Instantiate Alfred Core Application
    try:
        alfred = AlfredApp(config)
        alfred.start()
    except Exception as e:
        logger.critical("Fatal error starting Alfred: %s", e, exc_info=True)
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

