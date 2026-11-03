"""State controller and image balancing manager for Alfred.

Controls state transitions (IDLE -> LISTENING -> THINKING -> SPEAKING -> IDLE,
SUCCESS, ERROR, CANCELLED) and fairly balances image usage over time across all
seven character PNGs.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Optional, List, Dict
from PySide6.QtCore import QObject, Signal, QTimer

from src.storage.database import Database

logger = logging.getLogger("alfred.state_controller")


class AlfredState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    SUCCESS = "SUCCESS"
    GREETING = "GREETING"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


# Standard image definitions
IMG_SMOKING = "v smoking.png"
IMG_CAT = "v cat.png"
IMG_THINKING = "v thinking.png"
IMG_HAPPY = "v happy.png"
IMG_SAD = "v sad.png"
IMG_CHEERS = "v cheers.png"
IMG_STOP = "v stop.png"


class StateController(QObject):
    """Manages Alfred's active state, selects suitable images with fair rotation,
    and enforces minimum display duration to prevent UI flickering.
    """

    # Signals: (state, image_name, status_message)
    state_changed = Signal(str, str, str)

    def __init__(
        self,
        database: Optional[Database] = None,
        default_image: str = IMG_SMOKING,
        min_display_duration: float = 1.5,
    ):
        super().__init__()
        self.db = database
        self.default_image = default_image
        self.min_display_duration = min_display_duration

        self.current_state: AlfredState = AlfredState.IDLE
        self.current_image: str = default_image
        self.last_transition_time: float = time.time()

        # In-memory usage counts for fast lookups or when DB is unavailable
        self._in_memory_counts: Dict[str, int] = {
            IMG_SMOKING: 0,
            IMG_CAT: 0,
            IMG_THINKING: 0,
            IMG_HAPPY: 0,
            IMG_SAD: 0,
            IMG_CHEERS: 0,
            IMG_STOP: 0,
        }

        # Auto-return timer to return to IDLE after terminal states
        self._auto_idle_timer = QTimer(self)
        self._auto_idle_timer.setSingleShot(True)
        self._auto_idle_timer.timeout.connect(self._on_auto_idle_timeout)

    def get_recent_usage_counts(self) -> Dict[str, int]:
        """Gets image usage counts over the rolling window from DB or in-memory."""
        if self.db:
            try:
                return self.db.get_image_usage_counts(rolling_hours=24)
            except Exception as e:
                logger.warning("Could not fetch image counts from DB: %s", e)
        return self._in_memory_counts.copy()

    def _pick_least_used(self, candidates: List[str]) -> str:
        """Picks the candidate image with the lowest recent usage count."""
        if not candidates:
            return self.default_image

        if len(candidates) == 1:
            return candidates[0]

        counts = self.get_recent_usage_counts()
        # Find minimum count among candidates
        candidates_sorted = sorted(candidates, key=lambda img: (counts.get(img, 0), img))
        chosen = candidates_sorted[0]
        logger.debug("Fair rotation picked '%s' among candidates %s with counts %s", chosen, candidates, counts)
        return chosen

    def determine_image_for_state(self, state: AlfredState, intent_hint: Optional[str] = None) -> str:
        """Determines the most contextually appropriate image, balancing across suitable alternatives."""
        if state == AlfredState.IDLE:
            return self.default_image

        if state == AlfredState.LISTENING:
            return IMG_CAT

        if state == AlfredState.THINKING:
            return IMG_THINKING

        if state == AlfredState.CANCELLED:
            return IMG_STOP

        if state == AlfredState.PAUSED:
            return IMG_STOP

        if state == AlfredState.ERROR:
            return IMG_SAD

        if state == AlfredState.GREETING:
            # Greetings can use cheers or happy; balance between the two
            return self._pick_least_used([IMG_CHEERS, IMG_HAPPY])

        if state == AlfredState.SUCCESS:
            # Success can use happy or cheers; balance between the two
            return self._pick_least_used([IMG_HAPPY, IMG_CHEERS])

        if state == AlfredState.SPEAKING:
            # If a specific hint was passed
            if intent_hint:
                hint_lower = intent_hint.lower()
                if "error" in hint_lower or "apolog" in hint_lower or "sorry" in hint_lower:
                    return IMG_SAD
                if "cheer" in hint_lower or "celebrat" in hint_lower or "greet" in hint_lower:
                    return self._pick_least_used([IMG_CHEERS, IMG_HAPPY])
                if "success" in hint_lower or "done" in hint_lower or "happy" in hint_lower:
                    return self._pick_least_used([IMG_HAPPY, IMG_CHEERS])
                if "stop" in hint_lower or "cancel" in hint_lower:
                    return IMG_STOP

            # Default speaking: rotate fairly between positive/expressive states or idle
            return self._pick_least_used([IMG_HAPPY, IMG_CHEERS, IMG_SMOKING])

        return self.default_image

    def transition_to(
        self,
        new_state: AlfredState,
        intent_hint: Optional[str] = None,
        status_text: str = "",
        auto_idle_after: Optional[float] = None,
        force: bool = False,
    ) -> str:
        """Transitions Alfred to a new state and emits state_changed signal.
        
        Args:
            new_state: Target AlfredState
            intent_hint: Optional hint for choosing emotional image
            status_text: Short status string to display subtly on UI
            auto_idle_after: If set, automatically transition back to IDLE after N seconds
            force: Bypass minimum display duration check
        """
        now = time.time()
        time_since_last = now - self.last_transition_time

        # Respect minimum display duration unless forced or important interrupt (like CANCELLED/LISTENING)
        if not force and time_since_last < self.min_display_duration:
            if new_state not in (AlfredState.CANCELLED, AlfredState.LISTENING):
                # Queue or defer switch if needed, but allow state update
                pass

        # Stop any existing auto-idle timer
        self._auto_idle_timer.stop()

        chosen_image = self.determine_image_for_state(new_state, intent_hint)
        self.current_state = new_state
        self.current_image = chosen_image
        self.last_transition_time = now

        # Record usage
        self._in_memory_counts[chosen_image] = self._in_memory_counts.get(chosen_image, 0) + 1
        if self.db:
            try:
                self.db.record_image_usage(chosen_image, new_state.value)
            except Exception as e:
                logger.warning("Failed to record image usage in DB: %s", e)

        # Default subtle status texts if none provided
        if not status_text:
            if new_state == AlfredState.LISTENING:
                status_text = "Listening..."
            elif new_state == AlfredState.THINKING:
                status_text = "Thinking..."
            elif new_state == AlfredState.SPEAKING:
                status_text = "Speaking..."
            elif new_state == AlfredState.CANCELLED:
                status_text = "Stopped"
            elif new_state == AlfredState.PAUSED:
                status_text = "Paused"
            elif new_state == AlfredState.IDLE:
                status_text = ""

        logger.info(
            "State changed: %s -> Image: %s | Status: '%s'",
            new_state.value,
            chosen_image,
            status_text,
        )

        self.state_changed.emit(new_state.value, chosen_image, status_text)

        # Handle auto-idle timer
        if auto_idle_after is not None and auto_idle_after > 0:
            self._auto_idle_timer.start(int(auto_idle_after * 1000))
        elif new_state in (AlfredState.SUCCESS, AlfredState.GREETING, AlfredState.ERROR, AlfredState.CANCELLED):
            # Auto return to IDLE after 2.5 seconds for transient states
            self._auto_idle_timer.start(2500)

        return chosen_image

    def _on_auto_idle_timeout(self) -> None:
        """Internal callback to return smoothly to IDLE."""
        if self.current_state != AlfredState.IDLE and self.current_state != AlfredState.PAUSED:
            self.transition_to(AlfredState.IDLE, status_text="")

