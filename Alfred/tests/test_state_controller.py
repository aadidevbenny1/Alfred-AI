"""Tests for StateController, transitions, and fair image balancing."""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

from src.storage.database import Database
from src.ui.state_controller import (
    StateController,
    AlfredState,
    IMG_SMOKING,
    IMG_CAT,
    IMG_THINKING,
    IMG_HAPPY,
    IMG_CHEERS,
    IMG_SAD,
    IMG_STOP,
)


def get_qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_state_mapping_defaults(tmp_path):
    """Verifies intended use mapping for key states."""
    get_qapp()
    db = Database(tmp_path / "test.db")
    ctrl = StateController(database=db, min_display_duration=0.0)

    # Idle must be smoking
    assert ctrl.determine_image_for_state(AlfredState.IDLE) == IMG_SMOKING

    # Listening must be cat
    assert ctrl.determine_image_for_state(AlfredState.LISTENING) == IMG_CAT

    # Thinking must be thinking
    assert ctrl.determine_image_for_state(AlfredState.THINKING) == IMG_THINKING

    # Error must be sad
    assert ctrl.determine_image_for_state(AlfredState.ERROR) == IMG_SAD

    # Cancelled must be stop
    assert ctrl.determine_image_for_state(AlfredState.CANCELLED) == IMG_STOP


def test_fair_image_balancing(tmp_path):
    """Verifies that fair rotation picks the least-used emotional image."""
    get_qapp()
    db = Database(tmp_path / "test.db")
    ctrl = StateController(database=db, min_display_duration=0.0)

    # Artificially record 5 usages for happy, 0 for cheers
    for _ in range(5):
        db.record_image_usage(IMG_HAPPY, "SUCCESS")

    # Now for SUCCESS, fair rotation should pick CHEERS
    chosen = ctrl.determine_image_for_state(AlfredState.SUCCESS)
    assert chosen == IMG_CHEERS

    # Now record 10 usages for cheers
    for _ in range(10):
        db.record_image_usage(IMG_CHEERS, "SUCCESS")

    # Now for SUCCESS, fair rotation should pick HAPPY
    chosen = ctrl.determine_image_for_state(AlfredState.SUCCESS)
    assert chosen == IMG_HAPPY


def test_state_transition_signals(tmp_path):
    """Verifies that transition_to emits the state_changed signal and updates current image."""
    get_qapp()
    db = Database(tmp_path / "test.db")
    ctrl = StateController(database=db, min_display_duration=0.0)

    received_signals = []
    ctrl.state_changed.connect(lambda s, img, msg: received_signals.append((s, img, msg)))

    ctrl.transition_to(AlfredState.LISTENING, status_text="Listening...")
    assert ctrl.current_state == AlfredState.LISTENING
    assert ctrl.current_image == IMG_CAT
    assert len(received_signals) == 1
    assert received_signals[0] == ("LISTENING", IMG_CAT, "Listening...")


def test_all_seven_images_can_be_selected(tmp_path):
    """Ensures every single one of the 7 images can be reached through state transitions."""
    get_qapp()
    db = Database(tmp_path / "test.db")
    ctrl = StateController(database=db, min_display_duration=0.0)

    selected_images = set()

    selected_images.add(ctrl.determine_image_for_state(AlfredState.IDLE))
    selected_images.add(ctrl.determine_image_for_state(AlfredState.LISTENING))
    selected_images.add(ctrl.determine_image_for_state(AlfredState.THINKING))
    selected_images.add(ctrl.determine_image_for_state(AlfredState.ERROR))
    selected_images.add(ctrl.determine_image_for_state(AlfredState.CANCELLED))

    # Happy and cheers through fair rotation
    db.record_image_usage(IMG_HAPPY, "TEST")
    selected_images.add(ctrl.determine_image_for_state(AlfredState.SUCCESS))
    db.record_image_usage(IMG_CHEERS, "TEST")
    db.record_image_usage(IMG_CHEERS, "TEST")
    selected_images.add(ctrl.determine_image_for_state(AlfredState.SUCCESS))

    expected = {
        IMG_SMOKING,
        IMG_CAT,
        IMG_THINKING,
        IMG_HAPPY,
        IMG_SAD,
        IMG_CHEERS,
        IMG_STOP,
    }
    assert selected_images == expected

