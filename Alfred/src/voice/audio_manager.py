"""Audio manager coordinating wake word, speech recognition, and text-to-speech.

Ensures synchronization, prevents self-echo, provides subtle audio feedback (chimes),
and exposes a clean high-level voice interface.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional
from PySide6.QtCore import QObject, Signal, Slot

from src.config import AppConfig
from src.voice.text_to_speech import TextToSpeechService
from src.voice.speech_recognition import SpeechRecognitionService
from src.voice.wake_word import WakeWordDetector

logger = logging.getLogger("alfred.voice.audio_manager")


class AudioManager(QObject):
    """Coordinates voice input, wake phrase detection, and voice synthesis."""

    wake_word_triggered = Signal(str)  # immediate command string
    command_transcribed = Signal(str)
    command_failed = Signal(str)
    speech_started = Signal(str)
    speech_finished = Signal()
    stop_command = Signal()

    def __init__(self, config: AppConfig, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config

        self.tts = TextToSpeechService(config, self)
        self.stt = SpeechRecognitionService(config, self)
        self.wake_detector = WakeWordDetector(config, self)

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Wires internal audio subsystem events."""
        # TTS events -> Wake word echo suppression
        self.tts.started.connect(self._on_tts_started)
        self.tts.finished.connect(self._on_tts_finished)
        self.tts.interrupted.connect(self._on_tts_interrupted)

        # Wake detector events
        self.wake_detector.wake_word_detected.connect(self._on_wake_detected)
        self.wake_detector.stop_command_detected.connect(self._on_stop_detected)

        # STT events
        self.stt.transcription_complete.connect(self._on_stt_complete)
        self.stt.transcription_failed.connect(self._on_stt_failed)

    def start(self) -> None:
        """Starts background voice monitoring."""
        if self.config.microphone_enabled:
            self.wake_detector.start()

    def stop(self) -> None:
        """Stops all audio activities and background threads."""
        self.wake_detector.stop()
        self.stt.cancel()
        self.tts.stop()

    def play_wake_chime(self) -> None:
        """Plays a gentle, subtle audio chime on wake-word detection."""
        def _chime():
            try:
                import winsound
                # Subtle pleasant two-tone chime (high-low butler style)
                winsound.Beep(988, 80)   # B5
                winsound.Beep(1318, 120) # E6
            except Exception as e:
                logger.debug("Chime playback failed: %s", e)

        threading.Thread(target=_chime, daemon=True, name="Alfred-Chime").start()

    def toggle_microphone(self) -> bool:
        """Toggles microphone enabled state."""
        new_state = not self.wake_detector.is_enabled
        self.wake_detector.set_enabled(new_state)
        return new_state

    def listen_for_command(self) -> None:
        """Initiates listening for user's command after wake phrase."""
        self.stt.listen_for_command_async(timeout=5.0, phrase_time_limit=12.0)

    def speak(self, text: str) -> None:
        """Speaks text using TTS."""
        self.tts.speak(text)

    def interrupt(self) -> None:
        """Instantly stops speech and cancels listening."""
        self.tts.stop()
        self.stt.cancel()

    # --- Internal Slots ---

    @Slot(str)
    def _on_tts_started(self, text: str) -> None:
        self.wake_detector.set_speaking_state(True)
        self.speech_started.emit(text)

    @Slot()
    def _on_tts_finished(self) -> None:
        self.wake_detector.set_speaking_state(False)
        self.speech_finished.emit()

    @Slot()
    def _on_tts_interrupted(self) -> None:
        self.wake_detector.set_speaking_state(False)

    @Slot(str)
    def _on_wake_detected(self, command: str) -> None:
        self.play_wake_chime()
        self.wake_word_triggered.emit(command)

    @Slot()
    def _on_stop_detected(self) -> None:
        self.interrupt()
        self.stop_command.emit()

    @Slot(str)
    def _on_stt_complete(self, transcript: str) -> None:
        self.command_transcribed.emit(transcript)

    @Slot(str)
    def _on_stt_failed(self, reason: str) -> None:
        self.command_failed.emit(reason)

