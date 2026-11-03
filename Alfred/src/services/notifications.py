"""Subtle desktop notifications for Alfred.

Displays Windows desktop notifications without creating or opening any secondary window.
"""

from __future__ import annotations

import logging
from typing import Optional
from PySide6.QtWidgets import QSystemTrayIcon

logger = logging.getLogger("alfred.services.notifications")


class NotificationService:
    """Manages Windows system notifications via QSystemTrayIcon without secondary windows."""

    def __init__(self, tray_icon: Optional[QSystemTrayIcon] = None):
        self.tray_icon = tray_icon

    def set_tray_icon(self, tray_icon: QSystemTrayIcon) -> None:
        self.tray_icon = tray_icon

    def notify(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        timeout_ms: int = 8000,
    ) -> None:
        """Sends a native Windows 11 action center notification."""
        if self.tray_icon and self.tray_icon.isVisible():
            try:
                # Truncate message if too long for Windows toast
                display_msg = message if len(message) < 250 else message[:247] + "..."
                self.tray_icon.showMessage(title, display_msg, icon, timeout_ms)
                logger.info("Sent desktop notification: %s - %s", title, display_msg)
            except Exception as e:
                logger.warning("Failed to show tray notification: %s", e)
        else:
            logger.debug("Tray icon not available. Notification suppressed: %s - %s", title, message)

