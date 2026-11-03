"""Tests for Database storage, preferences, and bounded history."""

from src.storage.database import Database, ALL_IMAGES


def test_database_initialization(tmp_path):
    """Verifies that all tables are created cleanly on init."""
    db_file = tmp_path / "alfred_test.db"
    db = Database(db_file)
    assert db_file.exists()


def test_preferences_save_and_retrieve(tmp_path):
    """Verifies saving and retrieving user preferences."""
    db = Database(tmp_path / "pref.db")
    db.save_preference("mic_enabled", "true")
    assert db.get_preference("mic_enabled") == "true"

    # Overwrite preference
    db.save_preference("mic_enabled", "false")
    assert db.get_preference("mic_enabled") == "false"

    # Default fallback
    assert db.get_preference("missing_key", "default_val") == "default_val"


def test_image_usage_tracking_and_rolling_counts(tmp_path):
    """Verifies recording and retrieving rolling image counts."""
    db = Database(tmp_path / "img.db")
    counts_initial = db.get_image_usage_counts(rolling_hours=24)

    # All 7 images must be present in dictionary with 0 initial count
    assert len(counts_initial) == 7
    for img in ALL_IMAGES:
        assert counts_initial[img] == 0

    # Record usages
    db.record_image_usage("v cat.png", "LISTENING")
    db.record_image_usage("v cat.png", "LISTENING")
    db.record_image_usage("v cheers.png", "GREETING")

    counts_after = db.get_image_usage_counts(rolling_hours=24)
    assert counts_after["v cat.png"] == 2
    assert counts_after["v cheers.png"] == 1
    assert counts_after["v smoking.png"] == 0


def test_bounded_conversation_history(tmp_path):
    """Verifies that conversation history is bounded and preserves order."""
    db = Database(tmp_path / "conv.db")

    # Add 10 turns with max_retained=5
    for i in range(10):
        db.add_conversation_turn("user", f"Question {i}", max_retained=5)

    recent = db.get_recent_conversation(limit=10)
    assert len(recent) == 5
    assert recent[-1]["content"] == "Question 9"
    assert recent[0]["content"] == "Question 5"

    # Test clearing history
    db.clear_conversation_history()
    assert len(db.get_recent_conversation()) == 0

