"""Tests for Single Floating Window behavior and constraints."""

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.storage.database import Database
from src.ui.image_manager import ImageManager
from src.ui.state_controller import StateController
from src.ui.floating_window import FloatingWindow


def get_qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_single_window_properties(tmp_path):
    """Verifies that the window is frameless, stays on top, translucent, and fixed size."""
    app = get_qapp()
    db = Database(tmp_path / "win.db")
    cfg = AppConfig()
    img_mgr = ImageManager(cfg.assets_dir)
    state_ctrl = StateController(database=db)

    window = FloatingWindow(image_manager=img_mgr, state_controller=state_ctrl, window_size=160)

    # Window flags
    flags = window.windowFlags()
    assert bool(flags & Qt.WindowType.FramelessWindowHint)
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)

    # Fixed dimensions
    assert window.width() == 160
    assert window.height() == 160
    assert window.minimumWidth() == 160
    assert window.maximumWidth() == 160
    assert window.minimumHeight() == 160
    assert window.maximumHeight() == 160

    # Ensure translucent background attribute
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def test_window_dimension_invariant_on_image_changes(tmp_path):
    """Ensures switching between different character PNGs never alters window size."""
    app = get_qapp()
    db = Database(tmp_path / "dim.db")
    cfg = AppConfig()
    img_mgr = ImageManager(cfg.assets_dir)
    state_ctrl = StateController(database=db)

    window = FloatingWindow(image_manager=img_mgr, state_controller=state_ctrl, window_size=160)

    for img_name in ("v cat.png", "v thinking.png", "v cheers.png", "v sad.png", "v smoking.png"):
        window.update_display(img_name, "Testing...")
        assert window.width() == 160
        assert window.height() == 160

