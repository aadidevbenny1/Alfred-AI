"""Single floating character window and system tray for Alfred.

Strictly maintains ONE compact, frameless, transparent floating window positioned
at top-center just below the webcam. Clicking the character never opens any secondary
window or panel.
"""

from __future__ import annotations

import logging
from typing import Optional
from PySide6.QtCore import Qt, QPoint, Signal, Slot
from PySide6.QtGui import QIcon, QAction, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QGraphicsDropShadowEffect,
)

from src.ui.image_manager import ImageManager
from src.ui.state_controller import StateController, AlfredState

logger = logging.getLogger("alfred.ui.floating_window")


class FloatingWindow(QWidget):
    """The sole floating character window for Alfred."""

    # Optional internal signals for user actions from tray
    toggle_mic_requested = Signal()
    trigger_briefing_requested = Signal()
    clear_history_requested = Signal()
    exit_requested = Signal()

    def __init__(
        self,
        image_manager: ImageManager,
        state_controller: StateController,
        window_size: int = 160,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.image_manager = image_manager
        self.state_controller = state_controller
        self.window_size = window_size

        self._drag_pos = QPoint()
        self._is_dragging = False

        self._init_window_flags()
        self._init_ui()
        self._init_tray()
        self.reposition_to_top_center()

        # Connect state controller signals
        self.state_controller.state_changed.connect(self.on_state_changed)

        # Initial display
        self.update_display(self.state_controller.current_image, "")

    def _init_window_flags(self) -> None:
        """Sets up frameless, transparent, always-on-top window attributes."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedSize(self.window_size, self.window_size)

    def _init_ui(self) -> None:
        """Constructs the minimalist single-window layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # 1. Main Character Image Label
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background: transparent;")

        # Subtle drop shadow for clarity on various backgrounds
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 2)
        shadow.setColor(Qt.GlobalColor.black)
        self.image_label.setGraphicsEffect(shadow)

        layout.addWidget(self.image_label, stretch=1)

        # 2. Subtle integrated status indicator (never changes window size)
        self.status_label = QLabel(self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            """
            QLabel {
                color: #F0F4F8;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
                font-weight: 600;
                background-color: rgba(18, 24, 38, 180);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 8px;
                padding: 1px 6px;
            }
            """
        )
        self.status_label.setFixedHeight(18)
        self.status_label.hide()  # Hidden by default in idle state
        layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _init_tray(self) -> None:
        """Initializes the Windows system tray icon and menu."""
        default_pixmap = self.image_manager.get_pixmap("v smoking.png", target_size=32)
        self.tray_icon = QSystemTrayIcon(QIcon(default_pixmap), self)

        menu = QMenu()
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #1E232A;
                color: #FFFFFF;
                border: 1px solid #333B47;
                padding: 4px;
                font-family: 'Segoe UI', sans-serif;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2D3748;
            }
            QMenu::separator {
                height: 1px;
                background-color: #333B47;
                margin: 4px 0;
            }
            """
        )

        self.title_action = QAction("Alfred — Butler Assistant", self)
        self.title_action.setEnabled(False)
        menu.addAction(self.title_action)

        menu.addSeparator()

        self.mic_action = QAction("Toggle Microphone", self)
        self.mic_action.triggered.connect(self.toggle_mic_requested.emit)
        menu.addAction(self.mic_action)

        self.briefing_action = QAction("Daily Briefing Now", self)
        self.briefing_action.triggered.connect(self.trigger_briefing_requested.emit)
        menu.addAction(self.briefing_action)

        self.clear_action = QAction("Clear Conversation Memory", self)
        self.clear_action.triggered.connect(self.clear_history_requested.emit)
        menu.addAction(self.clear_action)

        menu.addSeparator()

        exit_action = QAction("Exit Alfred", self)
        exit_action.triggered.connect(self.exit_requested.emit)
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.setToolTip("Alfred Personal Desktop Assistant")
        self.tray_icon.show()

    def reposition_to_top_center(self) -> None:
        """Positions the window at top-center of the primary monitor, directly below the webcam."""
        primary_screen = QGuiApplication.primaryScreen()
        if not primary_screen:
            return

        screen_geometry = primary_screen.availableGeometry()
        x = screen_geometry.x() + (screen_geometry.width() - self.window_size) // 2
        y = screen_geometry.y() + 15  # 15px down from the top edge (just below webcam)

        self.move(x, y)
        logger.info("Positioned Alfred window at top center: (%d, %d)", x, y)

    @Slot(str, str, str)
    def on_state_changed(self, state: str, image_name: str, status_text: str) -> None:
        """Slot invoked whenever Alfred changes state or emotion."""
        self.update_display(image_name, status_text)

    def update_display(self, image_name: str, status_text: str = "") -> None:
        """Updates the character image and subtle status text without changing window size."""
        # Character target size inside 160x160 window with status pill
        inner_img_size = self.window_size - 28
        pixmap = self.image_manager.get_pixmap(image_name, target_size=inner_img_size)

        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap)

        if status_text.strip():
            self.status_label.setText(status_text.strip())
            self.status_label.show()
        else:
            self.status_label.hide()

    # --- Mouse Event Handlers ---
    # Strictly adhering to: "Clicking Alfred's image must never open or drop down another window."
    # We allow smooth dragging so the user can slightly adjust Alfred's placement if needed.

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._is_dragging = False
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # Double clicking snaps back to top center
        if event.button() == Qt.MouseButton.LeftButton:
            self.reposition_to_top_center()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

