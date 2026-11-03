"""Wake word detection for Alfred.

Continuously and efficiently listens for "Alfred" and "Hey Alfred" in the background,
handles compound commands (e.g. "Hey Alfred, search the markets"), supports immediate
stop commands, and suppresses self-echo while speaking.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional
from PySide6.QtCore import QObject, Signal

import speech_recognition as sr
from src.config import AppConfig

logger = logging.getLogger("alfred.voice.wake_word")

STOP_PHRASES = [
    "stop",
    "stop speaking",
    "stop alfred",
    "quiet",
    "quiet alfred",
    "cancel",
    "cancel that",
    "shut up",
    "hush",
    "silence",
]


class WakeWordDetector(QObject):
    """Detects 'Alfred' and 'Hey Alfred' wake phrases and interruption stop commands."""

    wake_word_detected = Signal(str)  # Emits immediate_command (may be empty string)
    stop_command_detected = Signal()
    status_changed = Signal(str)

    def __init__(self, config: AppConfig, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config
        self.wake_phrases: List[str] = [p.lower() for p in self.config.wake_phrases]
        self.is_enabled = self.config.microphone_enabled

        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = 350
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.pause_threshold = 0.6

        self._running = False
        self._is_speaking_suppressed = False
        self._last_speech_finish_time = 0.0
        self._cooldown_duration = 1.0  # Seconds to wait after speech ends before wake word

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def set_speaking_state(self, is_speaking: bool) -> None:
        """Notifies the detector of TTS playback state for echo suppression."""
        self._is_speaking_suppressed = is_speaking
        if not is_speaking:
            self._last_speech_finish_time = time.time()

    def set_enabled(self, enabled: bool) -> None:
        """Enables or disables listening (e.g. via system tray toggle)."""
        self.is_enabled = enabled
        logger.info("Wake word detector enabled: %s", enabled)
        self.status_changed.emit("Active" if enabled else "Muted")

    def start(self) -> None:
        """Starts the background listening loop."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="Alfred-WakeWord-Thread",
        )
        self._thread.start()
        logger.info("Wake word detector started for phrases: %s", self.wake_phrases)

    def stop(self) -> None:
        """Stops the background listening loop."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        logger.info("Wake word detector stopped.")

    def _is_in_cooldown(self) -> bool:
        """Checks if we are currently in self-hearing cooldown."""
        if self._is_speaking_suppressed:
            return True
        if time.time() - self._last_speech_finish_time < self._cooldown_duration:
            return True
        return False

    def _match_wake_word(self, transcript: str) -> tuple[bool, str]:
        """Checks if transcript contains any wake phrase and extracts any subsequent command.
        
        Returns:
            (is_matched, immediate_command)
        """
        text = transcript.lower().strip()

        # Check for stop commands first
        for stop_p in STOP_PHRASES:
            if text == stop_p or text.startswith(stop_p + " ") or text.endswith(" " + stop_p):
                return False, "__STOP__"

        # Check for wake phrases
        for wp in self.wake_phrases:
            if text == wp:
                return True, ""
            # Check if phrase starts with wake word (e.g. "hey alfred what's the news")
            if text.startswith(wp + " ") or text.startswith(wp + ","):
                remainder = text[len(wp) :].lstrip(", ").strip()
                return True, remainder

            # Handle common phonetic variations like "alfrid", "elfred"
            for alt in ("alfrid", "elfred", "elvis"):
                if text == alt:
                    return True, ""
                if text.startswith(alt + " "):
                    remainder = text[len(alt) :].strip()
                    return True, remainder

        return False, ""

    def _detection_loop(self) -> None:
        """Main listening loop running in background."""
        while self._running and not self._stop_event.is_set():
            if not self.is_enabled:
                time.sleep(0.5)
                continue

            if self._is_in_cooldown():
                time.sleep(0.3)
                continue

            try:
                with sr.Microphone() as source:
                    # Quick ambient noise adjustment once
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.3)

                    while self._running and not self._stop_event.is_set():
                        if not self.is_enabled or self._is_in_cooldown():
                            time.sleep(0.2)
                            continue

                        try:
                            # Listen for short phrase
                            audio = self._recognizer.listen(source, timeout=2.0, phrase_time_limit=4.5)
                        except sr.WaitTimeoutError:
                            continue

                        # Check suppression again before transcribing
                        if self._is_in_cooldown():
                            continue

                        try:
                            transcript = self._recognizer.recognize_google(audio, language="en-US")
                            transcript = transcript.strip()
                            if not transcript:
                                continue

                            logger.debug("Wake listener heard: '%s'", transcript)

                            # Check for stop command or wake word
                            matched, command = self._match_wake_word(transcript)

                            if command == "__STOP__":
                                logger.info("Stop phrase recognized: '%s'", transcript)
                                self.stop_command_detected.emit()
                                continue

                            if matched:
                                logger.info(
                                    "Wake phrase matched! Transcript: '%s' | Extracted command: '%s'",
                                    transcript,
                                    command,
                                )
                                self.wake_word_detected.emit(command)
                                # Brief pause to allow state transition
                                time.sleep(0.5)

                        except sr.UnknownValueError:
                            # Normal ambient noise or non-verbal sound
                            pass
                        except sr.RequestError as e:
                            logger.debug("Wake recognizer network glitch: %s", e)
                            time.sleep(1.0)

            except Exception as e:
                logger.warning("Microphone error in wake detector loop: %s", e)
                time.sleep(2.0)

