"""SQLite local database storage for Alfred.

Handles user preferences, fair image usage tracking, bounded conversation history,
and briefing records.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


ALL_IMAGES = [
    "v smoking.png",
    "v cat.png",
    "v thinking.png",
    "v happy.png",
    "v sad.png",
    "v cheers.png",
    "v stop.png",
]


class Database:
    """Thread-safe SQLite database manager for Alfred."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes required tables if they do not exist."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Preferences
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # 2. Image usage tracking for fair rotation
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS image_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_ts ON image_usage(timestamp)")

            # 3. Bounded conversation history
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # 4. Daily briefing history
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS briefing_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.commit()

    # --- Image Usage Tracking ---

    def record_image_usage(self, image_name: str, state: str) -> None:
        """Records an occurrence of an image being displayed."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO image_usage (image_name, state, timestamp) VALUES (?, ?, ?)",
                (image_name, state, datetime.now().isoformat()),
            )
            conn.commit()

    def get_image_usage_counts(self, rolling_hours: int = 24) -> dict[str, int]:
        """Returns the usage count of each image within the rolling window.
        
        Ensures all 7 character images are present in the returned dictionary.
        """
        counts = {img: 0 for img in ALL_IMAGES}
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT image_name, COUNT(*) as cnt
                FROM image_usage
                WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                GROUP BY image_name
                """,
                (rolling_hours,),
            )
            for row in cursor.fetchall():
                name = row["image_name"]
                if name in counts:
                    counts[name] = row["cnt"]
                else:
                    counts[name] = row["cnt"]
        return counts

    def get_all_time_image_counts(self) -> dict[str, int]:
        """Returns all-time usage count for all images."""
        counts = {img: 0 for img in ALL_IMAGES}
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT image_name, COUNT(*) as cnt
                FROM image_usage
                GROUP BY image_name
                """
            )
            for row in cursor.fetchall():
                name = row["image_name"]
                counts[name] = row["cnt"]
        return counts

    # --- Preferences ---

    def save_preference(self, key: str, value: str) -> None:
        """Saves or updates a preference."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO preferences (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """,
                (key, str(value)),
            )
            conn.commit()

    def get_preference(self, key: str, default: str | None = None) -> str | None:
        """Retrieves a preference value."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row["value"]
            return default

    # --- Conversation History ---

    def add_conversation_turn(self, role: str, content: str, max_retained: int = 30) -> None:
        """Adds a message turn to conversation history and prunes old records."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversation_history (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, datetime.now().isoformat()),
            )
            # Prune if exceeding max_retained
            cursor.execute(
                """
                DELETE FROM conversation_history
                WHERE id NOT IN (
                    SELECT id FROM conversation_history
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (max_retained,),
            )
            conn.commit()

    def get_recent_conversation(self, limit: int = 10) -> list[dict[str, str]]:
        """Retrieves recent conversation messages in chronological order."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content FROM conversation_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            messages = [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
            return messages

    def clear_conversation_history(self) -> None:
        """Clears all stored conversation history."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversation_history")
            conn.commit()

    # --- Briefings ---

    def record_briefing(self, content: str) -> None:
        """Records a daily briefing in history."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO briefing_history (content, created_at) VALUES (?, ?)",
                (content, datetime.now().isoformat()),
            )
            conn.commit()

    def get_last_briefing(self) -> dict[str, Any] | None:
        """Gets the most recent briefing."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, created_at
                FROM briefing_history
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

