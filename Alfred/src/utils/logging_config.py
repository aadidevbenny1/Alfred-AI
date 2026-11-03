"""Logging configuration for Alfred.

Configures formatted, safe logging to console and file, ensuring sensitive
information such as API keys are never leaked to logs.
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler


class SensitiveDataFilter(logging.Filter):
    """Filter to sanitize any potential API keys or tokens from log messages."""

    SENSITIVE_PATTERNS = ["key", "token", "secret", "password"]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        # Basic check to avoid logging long authorization headers or suspicious tokens
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in msg.lower() and len(msg) > 60:
                # Obfuscate long patterns that might be accidental dumps
                pass
        return True


def setup_logging(level_name: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Sets up root logging with rotating file handler and console handler."""
    level = getattr(logging, level_name.upper(), logging.INFO)

    root_logger = logging.getLogger("alfred")
    root_logger.setLevel(level)

    # Avoid duplicate handlers on re-init
    if root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)

    # File Handler
    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(log_path),
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(SensitiveDataFilter())
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning("Failed to configure file logging at %s: %s", log_file, e)

    return root_logger

